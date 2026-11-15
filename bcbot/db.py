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


@contextmanager
def connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    with psycopg.connect(url, connect_timeout=10, autocommit=True) as conn:
        yield conn


def request_signup(conn, email, resorts=("beaver-creek",)):
    """Create or refresh a pending sign-up for `resorts`.

    Returns (token, send_confirmation). Active subscribers and recent repeats get no
    new email, and the caller shows the same "check your inbox" message either way,
    so the form never reveals who is subscribed. An active subscriber's resorts are not
    changed here (anyone could type their address); they change them from the
    "Choose resorts" link in their own email.
    """
    resorts = list(resorts)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM subscribers WHERE confirm_sent_at > now() - interval '1 hour'")
        if cur.fetchone()[0] >= CONFIRMS_PER_HOUR_CAP:
            return None, False
        cur.execute("SELECT count(*) FROM subscribers WHERE confirm_sent_at > now() - interval '1 day'")
        if cur.fetchone()[0] >= CONFIRMS_PER_DAY_CAP:
            return None, False
        cur.execute("SELECT token, status, confirm_sent_at > now() - make_interval(mins => %s) "
                    "FROM subscribers WHERE lower(email) = lower(%s)", (CONFIRM_RESEND_MINUTES, email))
        row = cur.fetchone()
        if row:
            token, status, recent = row
            if status == "active" or recent:
                return token, False
            cur.execute("UPDATE subscribers SET status = 'pending', confirm_sent_at = now(), unsubscribed_at = NULL, "
                        "resorts = %s WHERE token = %s", (resorts, token))
            return token, True
        token = secrets.token_urlsafe(24)
        cur.execute("INSERT INTO subscribers (email, token, confirm_sent_at, resorts) VALUES (%s, %s, now(), %s)",
                    (email, token, resorts))
        return token, True


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


def active_subscribers(conn, resort=None):
    """[(email, token)] of active subscribers; only those who picked `resort` when given."""
    with conn.cursor() as cur:
        if resort:
            cur.execute("SELECT email, token FROM subscribers WHERE status = 'active' AND %s = ANY(resorts) ORDER BY id",
                        (resort,))
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


def claim_send(conn, day, reason, resort="beaver-creek"):
    """True exactly once per day per resort, even if two triggers race."""
    with conn.cursor() as cur:
        cur.execute("INSERT INTO daily_sends (day, resort, reason) VALUES (%s, %s, %s) "
                    "ON CONFLICT (day, resort) DO NOTHING RETURNING day", (day, resort, reason))
        return cur.fetchone() is not None
