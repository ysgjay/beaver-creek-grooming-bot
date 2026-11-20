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

from . import db, mailer, radar, resorts
from .store import get_store, resort_store

log = logging.getLogger(__name__)

TZ = ZoneInfo("America/Denver")   # default zone (tests, and a subscriber with no known resort)
CUTOFF = (6, 30)                  # local 6:30 AM: send with everything that's in by then


def home_zone(picked):
    """The time zone a subscriber's 6:30 AM is in: the zone most of their resorts are in
    (ties go to the resort they picked first). Someone with Stowe and Killington gets it at
    6:30 Eastern; someone with Vail and Stowe at 6:30 Mountain, with whatever is in by then."""
    zones = [resorts.get(s)["tz"] for s in picked if s in resorts.RESORTS]
    if not zones:
        return TZ
    return ZoneInfo(max(zones, key=lambda z: (zones.count(z), -zones.index(z))))


def resort_today(slug, now):
    """The resort's own local date at `now`."""
    return now.astimezone(ZoneInfo(resorts.get(slug)["tz"])).date().isoformat()


def _today_day(store, slug, today):
    day = resort_store(slug, store).get_json("data/latest.json", {}) or {}
    return day if day.get("date") == today else None


def plan(subs, sent, days, now):
    """[(email, token, ready, pending)] to send now. Pure, for tests. Each subscriber's 6:30
    cutoff and noon cap are in their home zone (home_zone)."""
    out = []
    for email, token, picked, *_ in subs:
        picked = [s for s in picked if s in resorts.RESORTS]
        local = now.astimezone(home_zone(picked))
        if (local.hour, local.minute) >= LATEST:
            continue                       # too late for a morning email
        cutoff = (local.hour, local.minute) >= CUTOFF
        if not cutoff and not all(s in sent and days.get(s) for s in picked):
            continue                       # before 6:30, only when every resort has sent
        ready = [s for s in picked if days.get(s)]
        pending = [s for s in picked if s not in ready]
        if not ready:
            continue
        out.append((email, token, ready, pending))
    return out


LATEST = (12, 0)   # no combined "morning" email after noon (same as SEND_CUTOFF for one resort)
MIN_SECONDS = 15   # with less time than this left in the tick, leave the claims for the next tick
RADAR_SECONDS = 30  # the radar picture renders only with this much time to spare


def run(now=None, store=None, deadline=None):
    """Send any combined emails that are due. Safe to call on every tick.
    deadline: time.monotonic() value the tick must finish by (Vercel's function limit)."""
    import time
    if os.environ.get("SEND_ENABLED") != "1":
        return {"status": "skipped (sending off)"}
    if not (os.environ.get("RESEND_API_KEY") and db.url()):
        return {"status": "skipped (email not configured)"}
    left = (lambda: deadline - time.monotonic()) if deadline else (lambda: float("inf"))
    if left() < MIN_SECONDS:
        return {"status": "skipped (no time left this tick)"}
    now = now or datetime.now(TZ)
    zones = {r["tz"] for r in map(resorts.get, resorts.enabled())} or {"America/Denver"}
    if all((now.astimezone(ZoneInfo(z)).hour, now.astimezone(ZoneInfo(z)).minute) >= LATEST for z in zones):
        return {"status": "skipped (past noon)"}
    store = store or get_store()
    with db.connect() as conn:
        subs = db.multi_resort_subscribers(conn)
        if not subs:
            return {"status": "ok", "sent": 0}
        sub_day = {t: now.astimezone(home_zone(p)).date().isoformat() for _, t, p, *_ in subs}
        done = set()
        for d in set(sub_day.values()):
            done |= {t for t in db.digest_sent(conn, d) if sub_day.get(t) == d}
        subs = [s for s in subs if s[1] not in done]
        wanted = {r for _, _, picked, *_ in subs for r in picked if r in resorts.RESORTS}
        maps_on = {t: m for _, t, _, m in subs}
        local_day = {slug: resort_today(slug, now) for slug in wanted}
        sent = set()
        for d in set(local_day.values()):
            sent |= {s for s in db.sent_resorts(conn, d) if local_day.get(s) == d}
        days = {}
        for slug in wanted:
            try:
                days[slug] = _today_day(store, slug, local_day[slug])
            except Exception:
                log.exception("digest: could not read %s", slug)
        due = plan(subs, sent, days, now)
        messages = []
        radar_url = radar.snapshot(store, now) if due and left() > RADAR_SECONDS else None
        if due and left() < MIN_SECONDS:
            return {"status": "skipped (no time left this tick)", "waiting": len(subs)}
        by_day = {}
        for email, token, ready, pending in due:
            today = sub_day[token]
            if not db.claim_digest(conn, today, token, ready, pending):
                continue
            local = now.astimezone(home_zone(ready + pending))
            ordered = sorted(ready, key=lambda s: -(mailer.new_snow(days[s]) or 0))
            picked = [(s, days[s]) for s in ordered]
            by_day.setdefault(today, []).append(
                (email, token, mailer.digest_subject(picked, pending),
                 mailer.digest_html(picked, pending, local, radar_url=radar_url, maps=maps_on.get(token), token=token),
                 mailer.digest_text(picked, pending)))
        messages = [m for ms in by_day.values() for m in ms]
        failure = None
        for today, ms in by_day.items():
            try:
                mailer.send_personal(ms, kind="digest", day=today)
            except Exception as e:
                # Hand the claims back so the next tick tries again. The batch idempotency key
                # stops anything that did go out from going out twice.
                db.release_digest(conn, today, [m[1] for m in ms])
                failure = e
        if failure:
            raise failure
    return {"status": "ok", "sent": len(messages), "waiting": len(subs) - len(due)}
