"""The pipeline: fetch -> verify -> forecast -> archive -> notify.

Triggered every 30 minutes through the early morning (Cloudflare cron -> /api/run on
Vercel). Most runs exit after one cheap check: a full run happens only when the grooming
map changed, the forecast is older than REFRESH_HOURS, or it's the first run of the day.

CLI:
  python -m bcbot run [--force] [--send]   # local run into public/ (no sending unless --send)
  python -m bcbot discover                 # list the resort's cam ids
"""
import argparse
import logging
import re
import sys
from datetime import datetime

from . import config, forecast, notify, report, verify
from .sources import grooming, nws, openmeteo, resort, snotel
from .store import get_store
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
        path = f"cams/{day_str}.jpg"
        store.put_bytes(path, r.content, "image/jpeg")
        return path
    except Exception as e:
        log.warning("stake snapshot failed: %s", e)
        return None


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


def _send_at(now):
    hh, mm = (int(x) for x in config.SEND_TIME.split(":"))
    return now.replace(hour=hh, minute=mm, second=0, microsecond=0)


def run(store=None, force=False, send=None, now=None):
    """One trigger. Cheap unless something changed or the daily send is due.

    Send rule (once per day, never twice):
      at SEND_TIME, if today's grooming map is new -> send;
      if it isn't new yet -> keep checking each trigger, send the moment it appears;
      at SEND_TIME + SEND_FALLBACK_MINUTES -> send anyway (in season) with a note.
    """
    store = store or get_store()
    send = config.SEND_ENABLED if send is None else send
    now = now or now_local()
    day_str = now.date().isoformat()
    errors = []
    state = store.get_json("data/state.json", {}) or {}

    send_at = _send_at(now)
    minutes_to_send = (send_at - now).total_seconds() / 60
    send_pending = send and state.get("last_sent_date") != day_str and minutes_to_send <= 0
    pre_send = 0 < minutes_to_send <= config.PRE_SEND_MINUTES

    # 1. Cheap check
    groom = _try("grooming map", grooming.fetch, errors, None)
    map_changed = bool(groom) and groom["hash"] != state.get("last_map_hash")
    age = _hours_since(state.get("last_full_run"), now)
    new_day = (state.get("last_full_run") or "")[:10] != day_str
    stale_after = 1.0 if (pre_send or send_pending) else config.REFRESH_HOURS
    full = force or map_changed or new_day or age >= stale_after

    if not full and not send_pending:
        log.info("nothing new (map unchanged, forecast %.1fh old)", age)
        return {"status": "skipped", "forecast_age_h": round(age, 1)}

    if full:
        day = _full_run(store, state, groom, map_changed, now, day_str, errors)
    else:
        day = store.get_json("data/latest.json", {}) or {}

    # 2. The daily send
    delivered = None
    if send_pending and day.get("date") == day_str:
        new_map = bool(day.get("grooming", {}).get("new_map"))
        in_season = _hours_since(state.get("last_map_change"), now) <= config.IN_SEASON_DAYS * 24
        fallback = minutes_to_send <= -config.SEND_FALLBACK_MINUTES
        if new_map or (fallback and in_season):
            text = report.compose(day)
            g = day.get("grooming", {})
            image = groom["jpeg"] if (groom and map_changed) else (store.get_bytes(g["image"]) if g.get("image") else None)
            delivered = notify.send_all(text, image)
            alert = report.powder_alert(day.get("forecast"))
            if alert:
                notify.send_all(alert, channels=["ntfy"])
            state["last_sent_date"] = day_str
            day["delivery"] = {"sent_at": now_local().isoformat(timespec="seconds"),
                               "scheduled": send_at.isoformat(timespec="minutes"),
                               "new_map": new_map, "results": delivered}
            store.put_json(f"data/days/{day_str}.json", day)
            store.put_json("data/latest.json", day)
        elif fallback:
            state["last_sent_date"] = day_str  # off-season: nothing to send today
            log.info("off-season (no new map in %s days): not sending", config.IN_SEASON_DAYS)
        else:
            log.info("send due but today's map isn't posted yet; checking again next trigger")

    store.put_json("data/state.json", state)
    return {"status": "ok", "full_run": full, "map_changed": map_changed, "sent": delivered,
            "errors": errors, "ok": bool(day.get("forecast")) and (groom is not None or not full)}


def _full_run(store, state, groom, map_changed, now, day_str, errors):
    models = _try("open-meteo", openmeteo.fetch_models, errors, {})
    ens = _try("open-meteo ensemble", openmeteo.fetch_ensemble, errors, {})
    nws_daily = _try("nws", nws.fetch_snowfall, errors, {})
    obs = _try("snotel", snotel.fetch, errors, {})
    resort_report = resort.fetch()

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
    if groom and map_changed:
        path = f"maps/{day_str}.jpg"
        store.put_bytes(path, groom["jpeg"], "image/jpeg")
        g = {"new_map": True, "image": path, "hash": groom["hash"], "runs": groom.get("runs"),
             "last_modified": groom.get("last_modified")}
        state.update(last_map_hash=groom["hash"], last_map_image=path,
                     last_map_change=now.isoformat(timespec="minutes"))

    day = {
        "date": day_str,
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


def discover():
    """List the Brown Rice cam ids on the resort's cams page (to update CAM_IDS)."""
    url = "https://www.beavercreek.com/the-mountain/mountain-conditions/mountain-cams.aspx"
    html = get(url).text.replace("\\/", "/")
    for cam_id in sorted(set(re.findall(r"player\.brownrice\.com/embed/([\w-]+)", html))):
        r = get(f"https://player.brownrice.com/snapshot/{cam_id}", timeout=15, retries=0)
        print(f"{cam_id}: snapshot {r.status_code} {r.headers.get('Content-Type', '')}")


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="bcbot")
    ap.add_argument("command", choices=["run", "discover"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args(argv)
    if a.command == "discover":
        discover()
        return 0
    result = run(force=a.force, send=True if a.send else None)
    print(result)
    return 0 if result.get("status") == "skipped" or result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
