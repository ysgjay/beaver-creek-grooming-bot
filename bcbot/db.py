"""Private subscriber store (Neon Postgres). Email opt-ins and app push subscriptions.

Kept out of the public Blob archive on purpose: nothing here is ever served to the app.
"""
import os
import secrets
from contextlib import contextmanager

import psycopg

CONFIRM_RESEND_MINUTES = 10
CONFIRMS_PER_HOUR_CAP = 40  # protects the daily email quota from sign-up abuse


@contextmanager
def connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    with psycopg.connect(url, connect_timeout=10, autocommit=True) as conn:
        yield conn


def request_signup(conn, email):
    """Create or refresh a pending sign-up.

    Returns (token, send_confirmation). Active subscribers and recent repeats get no
    new email, and the caller shows the same "check your inbox" message either way,
    so the form never reveals who is subscribed.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM subscribers WHERE confirm_sent_at > now() - interval '1 hour'")
        if cur.fetchone()[0] >= CONFIRMS_PER_HOUR_CAP:
            return None, False
        cur.execute("SELECT token, status, confirm_sent_at > now() - make_interval(mins => %s) "
                    "FROM subscribers WHERE lower(email) = lower(%s)", (CONFIRM_RESEND_MINUTES, email))
        row = cur.fetchone()
        if row:
            token, status, recent = row
            if status == "active" or recent:
                return token, False
            cur.execute("UPDATE subscribers SET status = 'pending', confirm_sent_at = now(), unsubscribed_at = NULL "
                        "WHERE token = %s", (token,))
            return token, True
        token = secrets.token_urlsafe(24)
        cur.execute("INSERT INTO subscribers (email, token, confirm_sent_at) VALUES (%s, %s, now())", (email, token))
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


def active_subscribers(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT email, token FROM subscribers WHERE status = 'active' ORDER BY id")
        return cur.fetchall()


def save_push(conn, sub):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO push_subscriptions (endpoint, p256dh, auth) VALUES (%s, %s, %s) "
                    "ON CONFLICT (endpoint) DO UPDATE SET p256dh = excluded.p256dh, auth = excluded.auth, failures = 0",
                    (sub["endpoint"], sub["p256dh"], sub["auth"]))


def delete_push(conn, endpoint):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM push_subscriptions WHERE endpoint = %s", (endpoint,))


def push_subscriptions(conn):
    with conn.cursor() as cur:
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


def vapid_keys(conn):
    """The app's Web Push keypair, created on first use and kept only in this database."""
    from .webpush import generate_vapid_keys
    with conn.cursor() as cur:
        cur.execute("SELECT name, value FROM app_secrets WHERE name IN ('vapid_private', 'vapid_public')")
        found = dict(cur.fetchall())
        if len(found) == 2:
            return found["vapid_private"], found["vapid_public"]
        priv, pub = generate_vapid_keys()
        cur.execute("INSERT INTO app_secrets (name, value) VALUES ('vapid_private', %s), ('vapid_public', %s) "
                    "ON CONFLICT (name) DO NOTHING", (priv, pub))
        cur.execute("SELECT name, value FROM app_secrets WHERE name IN ('vapid_private', 'vapid_public')")
        found = dict(cur.fetchall())  # another request may have won the race; use what's stored
        return found["vapid_private"], found["vapid_public"]
