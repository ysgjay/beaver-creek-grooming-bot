"""Owner alerts: a phone notification (ntfy) when a send fails or a morning report is missed.

Set ADMIN_NTFY_TOPIC in Vercel (and in the Cloudflare Worker for trigger failures), then
subscribe to the same topic in the ntfy app. Without it, alerts are still logged at error
level, so they show up in Vercel's runtime errors. An alert never raises.
"""
import logging
import os

from . import config
from .util import http

log = logging.getLogger("bcbot.alert")


def admin(title, body):
    log.error("ALERT %s: %s", title, body)
    topic = os.environ.get("ADMIN_NTFY_TOPIC")
    if not topic:
        return False
    try:
        r = http().post(f"{config.NTFY_SERVER.rstrip('/')}/{topic}", data=str(body)[:1000].encode(), timeout=15,
                        headers={"Title": title[:200], "Tags": "warning", "Priority": "4"})
        return r.ok
    except Exception as e:
        log.warning("admin alert failed: %s", e)
        return False
