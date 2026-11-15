"""The pipeline: fetch -> verify -> forecast -> archive -> notify.

Triggered every 30 minutes through the early morning (Cloudflare cron -> /api/run on
Vercel). Most runs exit after one cheap check: a full run happens only when the grooming
map changed, the forecast is older than REFRESH_HOURS, or it's the first run of the day.

Each resort (resorts.py) runs on its own: its own archive folder, state, send rules and
subscribers. /api/run fans out one function call per resort.

CLI:
  python -m bcbot run [--resort vail] [--force] [--send]   # local run into public/ (no sending unless --send)
  python -m bcbot discover [--resort vail]                 # list the resort's cam ids
  python -m bcbot resorts-json                             # refresh public/resorts.json (the app's list)
"""
import argparse
import logging
import os
import re
import sys
from datetime import datetime, timedelta

from . import config, forecast, notify, report, resorts, verify
from .sources import grooming, nws, openmeteo, resort, snotel
from .store import get_store, resort_store
from .util import get, now_local

log = logging.getLogger("bcbot")


def _try(name, fn, errors, default=None):
    try:
        return fn()
    except Exception as e:
        log.exception("%s failed", name)
        errors.append(f"{name}: {e}")
        return default


def _hours_since(iso, now):
    try:
        return (now - datetime.fromisoformat(iso)).total_seconds() / 3600
    except (TypeError, ValueError):
        return 1e9


def _snapshot_stake(store, day_str):
    if not config.STAKE_SNAPSHOT_URL:
        return None
    try:
        r = get(config.STAKE_SNAPSHOT_URL, timeout=30, retries=1)
        r.raise_for_status()
        if not r.headers.get("Content-Type", "").startswith("image/"):
            raise ValueError(f"not an image: {r.headers.get('Content-Type')}")
        store.put_bytes(f"cams/{day_str}.jpg", r.content, "image/jpeg")
        return _public(store, f"cams/{day_str}.jpg")
    except Exception as e:
        log.warning("stake snapshot failed: %s", e)
        return None


def _public(store, path):
    """The URL path the app uses for a file this resort's store wrote."""
    return store.path(path) if hasattr(store, "path") else path


def day_summary(day):
    """The compact per-day row used by the calendar, stats and feed."""
    g = day.get("grooming") or {}
    runs = g.get("runs") or {}
    resort_rep = day.get("resort") or {}
    obs = day.get("observed") or {}
    fc = day.get("forecast") or {}
    return {
        "date": day["date"],
        "resort_24h": resort_rep.get("last_24h_in"),
        "snotel_24h": obs.get("snow_in"),
        "base_in": resort_rep.get("base_in"),
        "season_in": resort_rep.get("season_in"),
        "map": g.get("image") if g.get("new_map") else None,
        "map_date": runs.get("map_date"),
        "featured": runs.get("groomers_of_the_day", []),
        "overnight": runs.get("overnight", []),
        "morning": runs.get("morning", []),
        "cam": day.get("cam"),
        "next_1_5": fc.get("next_1_5"),
    }


def update_months(store, summary=None, snotel_daily=None):
    """Merge today's summary and SNOTEL's observed daily snowfall into month files.

    SNOTEL fills in snowfall for days the bot never ran, so the calendar has real
    numbers for every day of the season.
    """
    touched = {}

    def month(ym):
        if ym not in touched:
            touched[ym] = store.get_json(f"data/months/{ym}.json", None) or {"month": ym, "days": {}}
        return touched[ym]

    for d, row in (snotel_daily or {}).items():
        if row.get("depth_change_in") is None and row.get("precip_in") is None:
            continue
        entry = month(d[:7])["days"].setdefault(d, {"date": d})
        entry["snotel_new_in"] = max(0.0, row.get("depth_change_in") or 0.0)
        entry["snotel_precip_in"] = row.get("precip_in")
        entry["snotel_depth_in"] = row.get("depth_in")
    if summary:
        entry = month(summary["date"][:7])["days"].setdefault(summary["date"], {"date": summary["date"]})
        entry.update({k: v for k, v in summary.items() if v not in (None, [])})
    for ym, m in touched.items():
        m["days"] = dict(sorted(m["days"].items()))
        m["updated"] = now_local().isoformat(timespec="minutes")
        store.put_json(f"data/months/{ym}.json", m)
    return touched


def _at(now, hhmm):
    hh, mm = (int(x) for x in hhmm.split(":"))
    return now.replace(hour=hh, minute=mm, second=0, microsecond=0)


def _since(iso, ref_iso):
    """True when timestamp `iso` is later than `ref_iso` (missing ref = always)."""
    if not iso:
        return False
    if not ref_iso:
        return True
    return datetime.fromisoformat(iso) > datetime.fromisoformat(ref_iso)


def send_decision(state, now, *, map_new, resort_fresh, send=True):
    """What the daily send should do at `now`. Returns a reason to send, "quiet", or None (not yet).

    Pre-season (before OPENING_DAY): every morning at SEND_TIME, map or not.
    In season: as soon as (from SEND_EARLIEST) there's a new grooming map since the last report
      AND the resort's snow report is dated today. If the report has no readable date, the map
      alone counts from SEND_TIME. At SEND_LATEST, send whatever there is (in season) or stay
      quiet (the resort has stopped posting maps: season over).
    """
    if not send or state.get("last_sent_date") == now.date().isoformat():
        return None
    if now.date() < config.OPENING_DAY:
        return "preseason" if now >= _at(now, config.SEND_TIME) else None
    if now < _at(now, config.SEND_EARLIEST):
        return None
    if map_new and resort_fresh is True:
        return "ready"
    if map_new and resort_fresh is None and now >= _at(now, config.SEND_TIME):
        return "ready (map; report has no date)"
    if now >= _at(now, config.SEND_LATEST):
        in_season = _hours_since(state.get("last_map_change"), now) <= config.IN_SEASON_DAYS * 24
        return "deadline" if in_season else "quiet"
    return None


def run_all(store=None, force=False, send=None, now=None):
    """Every enabled resort, one after another (local runs and the fallback path)."""
    out = {}
    for slug in resorts.enabled():
        try:
            out[slug] = run(store, force=force, send=send, now=now, slug=slug)
        except Exception as e:
            log.exception("%s run failed", slug)
            out[slug] = {"status": "error", "error": str(e)}
    return out


def run(store=None, force=False, send=None, now=None, slug=resorts.DEFAULT):
    """One trigger for one resort: a cheap check, a full refresh when something changed,
    and that resort's daily send."""
    config.use(slug)
    store = resort_store(slug, store)
    send = config.SEND_ENABLED if send is None else send
    now = now or now_local()
    day_str = now.date().isoformat()
    errors = []
    state = store.get_json("data/state.json", {}) or {}

    # 1. Cheap check: has the grooming map changed?
    groom = _try("grooming map", grooming.fetch, errors, None)
    map_changed = bool(groom) and groom["hash"] != state.get("last_map_hash")
    last_change = now.isoformat(timespec="minutes") if map_changed else state.get("last_map_change")
    # "New" = changed since the last report went out (or in the last 18 hours if none has).
    ref = state.get("last_sent_at") or (now - timedelta(hours=18)).isoformat(timespec="minutes")
    map_new = _since(last_change, ref)

    # 2. Only when a send could happen: is the resort's snow report dated today?
    resort_report, resort_fresh = None, None
    in_window = (send and state.get("last_sent_date") != day_str and now.date() >= config.OPENING_DAY
                 and now >= _at(now, config.SEND_EARLIEST))
    if in_window and map_new:
        resort_report = resort.fetch()
        resort_fresh = resort.is_fresh(resort_report, now.date())

    decision = send_decision(state, now, map_new=map_new, resort_fresh=resort_fresh, send=send)

    age = _hours_since(state.get("last_full_run"), now)
    new_day = (state.get("last_full_run") or "")[:10] != day_str
    pre_send = 0 < (_at(now, config.SEND_TIME) - now).total_seconds() / 60 <= config.PRE_SEND_MINUTES
    stale_after = 1.0 if pre_send else config.REFRESH_HOURS
    full = force or map_changed or new_day or age >= stale_after or decision not in (None, "quiet")

    if not full and decision is None:
        log.info("nothing new (map unchanged, forecast %.1fh old)", age)
        return {"status": "skipped", "resort": slug, "forecast_age_h": round(age, 1), "map_new": map_new}

    if full:
        day = _full_run(store, state, groom, map_changed, now, day_str, errors, resort_report)
    else:
        day = store.get_json("data/latest.json", {}) or {}

    # 3. The daily send (exactly once per day, enforced by a database claim)
    delivered = None
    if decision == "quiet":
        state["last_sent_date"] = day_str
        log.info("season over (no new map in %s days): not sending", config.IN_SEASON_DAYS)
    elif decision and day.get("date") == day_str:
        if _claim_send(day_str, decision, slug):
            g = day.get("grooming", {})
            map_url = f"{config.DASHBOARD_URL.rstrip('/')}/{g['image']}" if g.get("image") else None
            powder = report.powder_alert(day.get("forecast"))
            delivered = notify.send_all(dict(day, preseason=decision == "preseason", powder=powder), map_url, slug=slug)
            day["delivery"] = {"sent_at": now_local().isoformat(timespec="seconds"), "reason": decision,
                               "new_map": map_new, "snow_report_fresh": resort_fresh, "results": delivered}
            store.put_json(f"data/days/{day_str}.json", day)
            store.put_json("data/latest.json", day)
        state["last_sent_date"] = day_str
        state["last_sent_at"] = now.isoformat(timespec="minutes")
    elif in_window and map_new and not resort_fresh:
        log.info("new map is in; waiting for today's snow report")

    store.put_json("data/state.json", state)
    return {"status": "ok", "resort": slug, "full_run": full, "map_changed": map_changed, "decision": decision,
            "sent": delivered, "errors": errors, "ok": bool(day.get("forecast")) and (groom is not None or not full)}


def _claim_send(day_str, reason, slug=resorts.DEFAULT):
    """Atomic once-per-day-per-resort guard. Without a database (tests, local runs) it always allows."""
    if not os.environ.get("DATABASE_URL"):
        return True
    from . import db
    with db.connect() as conn:
        return db.claim_send(conn, day_str, reason, slug)


TEST_MAX_RECIPIENTS = 5


def send_test(store=None, slug=resorts.DEFAULT):
    """Send one resort's current report now, labeled as a test, to that resort's subscribers.
    Leaves the daily schedule untouched.

    Refuses when there are more than TEST_MAX_RECIPIENTS email subscribers or app
    subscriptions in total (any resort), so a test can never reach the whole list.
    """
    config.use(slug)
    store = resort_store(slug, store)
    day = store.get_json("data/latest.json", {}) or {}
    if not day.get("date"):
        return {"status": "error", "error": "no report yet"}
    from . import db
    with db.connect() as conn:
        n = len(db.active_subscribers(conn))
        p = len(db.push_subscriptions(conn))
    if n > TEST_MAX_RECIPIENTS or p > TEST_MAX_RECIPIENTS:
        return {"status": "refused",
                "error": f"{n} email subscribers, {p} app subscriptions; tests are limited to {TEST_MAX_RECIPIENTS} each"}
    g = day.get("grooming", {})
    map_url = f"{config.DASHBOARD_URL.rstrip('/')}/{g['image']}" if g.get("image") else None
    return {"status": "ok", "test": True, "resort": slug,
            "sent": notify.send_all(dict(day, test=True), map_url, slug=slug)}


def _full_run(store, state, groom, map_changed, now, day_str, errors, resort_report=None):
    models = _try("open-meteo", openmeteo.fetch_models, errors, {})
    ens = _try("open-meteo ensemble", openmeteo.fetch_ensemble, errors, {})
    nws_daily = _try("nws", nws.fetch_snowfall, errors, {})
    obs = _try("snotel", snotel.fetch, errors, {})
    resort_report = resort_report if resort_report is not None else resort.fetch()

    if obs:
        verification = verify.compute(obs.get("daily", {}),
                                      lambda d: store.get_json(f"data/forecasts/{d}.json"), today=now.date())
        verification["station"] = obs.get("station")
        store.put_json("data/verification.json", verification)
    else:
        verification = store.get_json("data/verification.json", {}) or {}
    fc = forecast.build(models, nws_daily, ens, verification, today=now.date()) if (models or nws_daily) else None
    if fc:
        store.put_json(f"data/forecasts/{day_str}.json", fc)
    hourly = forecast.hourly_outlook(models, now=now) if models else {"hours": []}

    prev = store.get_json(f"data/days/{day_str}.json", {}) or {}
    g = dict(prev.get("grooming") or {"new_map": False, "image": state.get("last_map_image")})
    if groom and not g.get("runs"):
        g["runs"] = groom.get("runs")  # same map as before: still show its run names and date
    if groom and map_changed:
        store.put_bytes(f"maps/{day_str}.jpg", groom["jpeg"], "image/jpeg")
        path = _public(store, f"maps/{day_str}.jpg")
        g = {"new_map": True, "image": path, "hash": groom["hash"], "runs": groom.get("runs"),
             "last_modified": groom.get("last_modified")}
        state.update(last_map_hash=groom["hash"], last_map_image=path,
                     last_map_change=now.isoformat(timespec="minutes"))

    day = {
        "date": day_str,
        "resort_slug": config.RESORT,
        "resort_name": config.RESORT_NAME,
        "generated": now.isoformat(timespec="minutes"),
        "grooming": g,
        "forecast": {k: v for k, v in (fc or {}).items() if k != "raw"},
        "hourly": hourly,
        "observed": (obs or {}).get("last_24h", {}) | ({"station": obs["station"]} if obs else {}),
        "resort": resort_report,
        "cam": prev.get("cam") or _snapshot_stake(store, day_str),
        "delivery": prev.get("delivery"),
        "errors": errors,
    }
    store.put_json(f"data/days/{day_str}.json", day)
    store.put_json("data/latest.json", day)
    update_months(store, day_summary(day), (obs or {}).get("daily"))
    state["last_full_run"] = now.isoformat(timespec="minutes")
    return day


def discover(slug=resorts.DEFAULT):
    """List the Brown Rice cam ids on a resort's cams page (to fill in its cams in resorts.py)."""
    html = get(resorts.get(slug)["cams_page"]).text.replace("\\/", "/")
    for cam_id in sorted(set(re.findall(r"player\.brownrice\.com/embed/([\w-]+)", html))):
        r = get(f"https://player.brownrice.com/snapshot/{cam_id}", timeout=15, retries=0)
        print(f"{cam_id}: snapshot {r.status_code} {r.headers.get('Content-Type', '')}")


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="bcbot")
    ap.add_argument("command", choices=["run", "discover", "resorts-json"])
    ap.add_argument("--resort", choices=sorted(resorts.RESORTS), help="one resort (default: every enabled one)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args(argv)
    if a.command == "resorts-json":  # rewrite public/resorts.json after editing resorts.py
        import json
        (config.ROOT / "public" / "resorts.json").write_text(json.dumps(resorts.public_list(), indent=1) + "\n")
        return 0
    if a.command == "discover":
        discover(a.resort or resorts.DEFAULT)
        return 0
    send = True if a.send else None
    results = ({a.resort: run(force=a.force, send=send, slug=a.resort)} if a.resort
               else run_all(force=a.force, send=send))
    print(results)
    return 0 if all(r.get("status") == "skipped" or r.get("ok") for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
