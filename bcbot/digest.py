"""One combined morning email for subscribers with two or more resorts.

Each resort still sends on its own schedule (bcbot/main.py), but only to people who picked
that resort alone. After every scheduler tick, this looks at everyone with several resorts:
once all of their resorts have sent today, or at the 6:30 AM cutoff (Young, 11/16: "get all
ski resort info possible by 6:30am and send out the email aggregated"), they get one email
summarizing all of them with whatever each resort has posted so far, and a link to each
resort's full report. A resort with no data for today by then shows as "report pending". One email per person per day,
enforced by a database claim, so the Resend daily cap counts people, not people x resorts.
"""
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from . import db, mailer, resorts
from .store import get_store, resort_store

log = logging.getLogger(__name__)

TZ = ZoneInfo("America/Denver")   # every resort covered is on Mountain time
CUTOFF = (6, 30)                  # local 6:30 AM: send with everything that's in by then


def _today_day(store, slug, today):
    day = resort_store(slug, store).get_json("data/latest.json", {}) or {}
    return day if day.get("date") == today else None


def plan(subs, sent, days, now):
    """[(email, token, ready, pending)] to send now. Pure, for tests."""
    out = []
    for email, token, picked in subs:
        picked = [s for s in picked if s in resorts.RESORTS]
        cutoff = (now.hour, now.minute) >= CUTOFF
        if not cutoff and not all(s in sent and days.get(s) for s in picked):
            continue                       # before 6:30, only when every resort has sent
        ready = [s for s in picked if days.get(s)]
        pending = [s for s in picked if s not in ready]
        if not ready:
            continue
        out.append((email, token, ready, pending))
    return out


def run(now=None, store=None):
    """Send any combined emails that are due. Safe to call on every tick."""
    if not (os.environ.get("RESEND_API_KEY") and db.url()):
        return {"status": "skipped (email not configured)"}
    now = now or datetime.now(TZ)
    today = now.date().isoformat()
    store = store or get_store()
    with db.connect() as conn:
        subs = db.multi_resort_subscribers(conn)
        if not subs:
            return {"status": "ok", "sent": 0}
        sent = db.sent_resorts(conn, today)
        done = db.digest_sent(conn, today)
        subs = [s for s in subs if s[1] not in done]
        wanted = {r for _, _, picked in subs for r in picked if r in resorts.RESORTS}
        days = {}
        for slug in wanted:
            try:
                days[slug] = _today_day(store, slug, today)
            except Exception:
                log.exception("digest: could not read %s", slug)
        due = plan(subs, sent, days, now)
        messages = []
        for email, token, ready, pending in due:
            if not db.claim_digest(conn, today, token, ready, pending):
                continue
            ordered = sorted(ready, key=lambda s: -(mailer.new_snow(days[s]) or 0))
            picked = [(s, days[s]) for s in ordered]
            messages.append((email, token, mailer.digest_subject(picked, pending),
                             mailer.digest_html(picked, pending, now), mailer.digest_text(picked, pending)))
    if messages:
        mailer.send_personal(messages)
    return {"status": "ok", "sent": len(messages), "waiting": len(subs) - len(due)}
