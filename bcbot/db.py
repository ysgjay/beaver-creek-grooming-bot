"""Private subscriber store (Neon Postgres). Email opt-ins and app push subscriptions.

Kept out of the public Blob archive on purpose: nothing here is ever served to the app.

Each email subscriber and each app subscription has a `resorts` list (slugs from
resorts.py) and only gets those resorts' reports. Schema: docs/schema.sql.
"""
import os
import secrets
from contextlib import contextmanager

import psycopg

CONFIRM_RESEND_MINUTES = 10
CONFIRMS_PER_HOUR_CAP = 10  # protects the daily email quota (Resend free plan: 100/day,
CONFIRMS_PER_DAY_CAP = 25   # shared with the morning reports) from sign-up abuse


def url():
    """The 0xM Neon database (SNOWDB_DATABASE_URL, set by the Vercel Neon integration),
    falling back to the original DATABASE_URL."""
    return os.environ.get("SNOWDB_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""


@contextmanager
def connect():
    url_ = url()
    if not url_:
        raise RuntimeError("SNOWDB_DATABASE_URL / DATABASE_URL is not set")
    with psycopg.connect(url_, connect_timeout=10, autocommit=True) as conn:
        yield conn


def request_signup(conn, email, resorts=("beaver-creek",)):
    """Create or refresh a sign-up for `resorts`.

    Returns (token, action): "confirm" (email a confirmation link), "update" (an active
    subscriber asked for a different set of resorts: email them a link to their own
    resort page with that set pre-checked) or None (send nothing). The caller shows the
    same message either way, so the form never reveals who is subscribed. An active
    subscriber's resorts are never changed here (anyone could type their address); the
    change only happens from the link in their own inbox.
    """
    resorts = list(resorts)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM subscribers WHERE confirm_sent_at > now() - interval '1 hour'")
        if cur.fetchone()[0] >= CONFIRMS_PER_HOUR_CAP:
            return None, None
        cur.execute("SELECT count(*) FROM subscribers WHERE confirm_sent_at > now() - interval '1 day'")
        if cur.fetchone()[0] >= CONFIRMS_PER_DAY_CAP:
            return None, None
        cur.execute("SELECT token, status, confirm_sent_at > now() - make_interval(mins => %s), resorts "
                    "FROM subscribers WHERE lower(email) = lower(%s)", (CONFIRM_RESEND_MINUTES, email))
        row = cur.fetchone()
        if row:
            token, status, recent, current = row
            if recent:
                return token, None
            if status == "active":
                if sorted(current or []) == sorted(resorts):
                    return token, None
                cur.execute("UPDATE subscribers SET confirm_sent_at = now() WHERE token = %s", (token,))
                return token, "update"
            cur.execute("UPDATE subscribers SET status = 'pending', confirm_sent_at = now(), unsubscribed_at = NULL, "
                        "resorts = %s WHERE token = %s", (resorts, token))
            return token, "confirm"
        token = secrets.token_urlsafe(24)
        cur.execute("INSERT INTO subscribers (email, token, confirm_sent_at, resorts) VALUES (%s, %s, now(), %s)",
                    (email, token, resorts))
        return token, "confirm"


def confirm(conn, token):
    with conn.cursor() as cur:
        cur.execute("UPDATE subscribers SET status = 'active', confirmed_at = coalesce(confirmed_at, now()) "
                    "WHERE token = %s AND status <> 'unsubscribed' RETURNING email", (token,))
        row = cur.fetchone()
        return row[0] if row else None


def unsubscribe(conn, token):
    with conn.cursor() as cur:
        cur.execute("UPDATE subscribers SET status = 'unsubscribed', unsubscribed_at = now() "
                    "WHERE token = %s RETURNING email", (token,))
        return cur.fetchone() is not None


def active_subscribers(conn, resort=None, single_only=False):
    """[(email, token)] of active subscribers; only those who picked `resort` when given.

    single_only: just the ones who picked that resort alone. Everyone with two or more
    resorts gets one combined email instead (bcbot/digest.py)."""
    with conn.cursor() as cur:
        if resort:
            cur.execute("SELECT email, token FROM subscribers WHERE status = 'active' AND %s = ANY(resorts) "
                        + ("AND cardinality(resorts) = 1 " if single_only else "") + "ORDER BY id", (resort,))
        else:
            cur.execute("SELECT email, token FROM subscribers WHERE status = 'active' ORDER BY id")
        return cur.fetchall()


def subscriber_resorts(conn, token):
    """(email, [resorts]) for a subscriber's own link, or None."""
    with conn.cursor() as cur:
        cur.execute("SELECT email, resorts FROM subscribers WHERE token = %s AND status = 'active'", (token,))
        row = cur.fetchone()
        return (row[0], list(row[1])) if row else None


def set_subscriber_resorts(conn, token, resorts):
    with conn.cursor() as cur:
        cur.execute("UPDATE subscribers SET resorts = %s WHERE token = %s AND status = 'active' RETURNING email",
                    (list(resorts), token))
        return cur.fetchone() is not None


def save_push(conn, sub, resorts=("beaver-creek",)):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO push_subscriptions (endpoint, p256dh, auth, resorts) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (endpoint) DO UPDATE SET p256dh = excluded.p256dh, auth = excluded.auth, "
                    "resorts = excluded.resorts, failures = 0",
                    (sub["endpoint"], sub["p256dh"], sub["auth"], list(resorts)))


def delete_push(conn, endpoint):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM push_subscriptions WHERE endpoint = %s", (endpoint,))


def push_subscriptions(conn, resort=None):
    with conn.cursor() as cur:
        if resort:
            cur.execute("SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE %s = ANY(resorts) ORDER BY id",
                        (resort,))
        else:
            cur.execute("SELECT endpoint, p256dh, auth FROM push_subscriptions ORDER BY id")
        return [{"endpoint": e, "p256dh": p, "auth": a} for e, p, a in cur.fetchall()]


def record_push_result(conn, endpoint, status):
    with conn.cursor() as cur:
        if status in (404, 410):  # the browser dropped this subscription
            cur.execute("DELETE FROM push_subscriptions WHERE endpoint = %s", (endpoint,))
        elif 200 <= status < 300:
            cur.execute("UPDATE push_subscriptions SET last_sent_at = now(), failures = 0 WHERE endpoint = %s", (endpoint,))
        else:
            cur.execute("UPDATE push_subscriptions SET failures = failures + 1 WHERE endpoint = %s", (endpoint,))
            cur.execute("DELETE FROM push_subscriptions WHERE endpoint = %s AND failures >= 5", (endpoint,))


# Same as docs/migrations/003_digest_sends.sql (docs/ isn't deployed with the functions).
DIGEST_SCHEMA = """CREATE TABLE IF NOT EXISTS digest_sends (   -- once-a-day claim, per multi-resort subscriber
  day      date NOT NULL,
  token    text NOT NULL,
  resorts  text[] NOT NULL,          -- the resorts that were ready and in the email
  pending  text[] NOT NULL DEFAULT '{}',
  sent_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (day, token)
);"""


def multi_resort_subscribers(conn):
    """[(email, token, [resorts])] of active subscribers with two or more resorts."""
    with conn.cursor() as cur:
        cur.execute("SELECT email, token, resorts FROM subscribers WHERE status = 'active' AND cardinality(resorts) > 1 ORDER BY id")
        return [(e, t, list(r)) for e, t, r in cur.fetchall()]


def sent_resorts(conn, day):
    """Resorts whose daily send has gone out (been claimed) for `day`."""
    with conn.cursor() as cur:
        cur.execute("SELECT resort FROM daily_sends WHERE day = %s", (day,))
        return {r[0] for r in cur.fetchall()}


def claim_digest(conn, day, token, ready, pending):
    """True exactly once per day per subscriber, even if two triggers race."""
    with conn.cursor() as cur:
        cur.execute(DIGEST_SCHEMA)
        cur.execute("INSERT INTO digest_sends (day, token, resorts, pending) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (day, token) DO NOTHING RETURNING day", (day, token, list(ready), list(pending)))
        return cur.fetchone() is not None


def digest_sent(conn, day):
    """Tokens that already got today's combined email."""
    with conn.cursor() as cur:
        cur.execute(DIGEST_SCHEMA)
        cur.execute("SELECT token FROM digest_sends WHERE day = %s", (day,))
        return {r[0] for r in cur.fetchall()}


def claim_send(conn, day, reason, resort="beaver-creek"):
    """True exactly once per day per resort, even if two triggers race."""
    with conn.cursor() as cur:
        cur.execute("INSERT INTO daily_sends (day, resort, reason) VALUES (%s, %s, %s) "
                    "ON CONFLICT (day, resort) DO NOTHING RETURNING day", (day, resort, reason))
        return cur.fetchone() is not None
