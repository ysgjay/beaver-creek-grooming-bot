"""Delivery: email (Resend, opt-in list) and app notifications (Web Push from the Snow Desk app).

Each channel is independent: a failure in one never blocks the other.
Optional: NTFY_TOPIC still works for anyone who prefers the ntfy app.
"""
import logging
import os

from . import config, db, mailer, report, webpush
from .util import http

log = logging.getLogger(__name__)


def email(day, map_url):
    if not (os.environ.get("RESEND_API_KEY") and os.environ.get("DATABASE_URL")):
        return "skipped (email not configured)"
    with db.connect() as conn:
        recipients = db.active_subscribers(conn)
    if not recipients:
        return "no subscribers"
    sent = mailer.send_daily(recipients, report.subject(day), mailer.daily_html(day, map_url), report.compose(day))
    return f"sent to {sent}"


def push(day, map_url):
    """One notification per send. The powder alert, if any, rides along in it (never a second push)."""
    key = webpush.app_key()
    if not (os.environ.get("DATABASE_URL") and key):
        return "skipped (push not configured)"
    return _push_all(report.push_payload(day, map_url), key)


def _push_all(payload, key):
    ok = gone = failed = 0
    with db.connect() as conn:
        for sub in db.push_subscriptions(conn):
            try:
                status = webpush.send(http(), sub, payload, key, config.VAPID_SUBJECT)
            except Exception as e:
                log.warning("push failed: %s", e)
                status = 0
            db.record_push_result(conn, sub["endpoint"], status)
            ok += 200 <= status < 300
            gone += status in (404, 410)
            failed += not (200 <= status < 300 or status in (404, 410))
    return f"{ok} delivered, {gone} expired, {failed} failed"


def ntfy(day, map_url):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return "skipped"
    r = http().post(f"{config.NTFY_SERVER.rstrip('/')}/{topic}", timeout=30, params={
        "title": report.subject(day), "message": report.compose(day), "click": config.DASHBOARD_URL,
        "tags": "ski", **({"attach": map_url} if map_url else {})})
    r.raise_for_status()
    return "sent"


CHANNELS = {"email": email, "push": push, "ntfy": ntfy}


def send_all(day, map_url, channels=None):
    results = {}
    for name, fn in CHANNELS.items():
        if channels and name not in channels:
            continue
        try:
            results[name] = fn(day, map_url)
        except Exception as e:
            log.exception("%s failed", name)
            results[name] = f"FAILED: {e}"
    return results

