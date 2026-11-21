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
from datetime import date, datetime, timedelta

from . import alert, audit, config, forecast, notify, pages, report, resorts, verify
from .sources import dor, grooming, reportpal, mountain, vrterrain, nws, openmeteo, resort, snotel
from .store import get_store, resort_store
from .util import get, now_local

log = logging.getLogger("bcbot")


def _db_url():
    from .db import url
    return url()


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
        # True only when the report is dated that day; a stale report must not score the forecast.
        "resort_fresh": resort.is_fresh(resort_rep, date.fromisoformat(day["date"])),
        "snotel_24h": obs.get("snow_in"),
        "base_in": resort_rep.get("base_in"),
        "season_in": resort_rep.get("season_in"),
        "map": g.get("image") if g.get("new_map") else None,
        "map_date": runs.get("map_date"),
        "featured": runs.get("groomers_of_the_day", []),
        "overnight": runs.get("overnight", []),
        "morning": runs.get("morning", []),
        "groomed": runs.get("groomed", []),
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


def send_decision(state, now, *, map_new, resort_fresh, send=True, has_map=True):
    """What the daily send should do at `now`. Returns a reason to send, "quiet", or None (not yet).

    Pre-season (before OPENING_DAY): every morning at SEND_TIME, map or not.
    In season: as soon as (from SEND_EARLIEST) there's a new grooming map since the last report
      AND the resort's snow report is dated today. If the report has no readable date, the map
      alone counts from SEND_TIME. At SEND_LATEST, send whatever there is (in season) or stay
      quiet (the resort has stopped posting maps: season over).
    A resort with no grooming map (has_map=False) sends as soon as today's snow report is
    posted, and at SEND_LATEST regardless.
    """
    if not send or state.get("last_sent_date") == now.date().isoformat():
        return None
    if now >= _at(now, config.SEND_CUTOFF):  # too late for a morning report
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
        in_season = not has_map or _hours_since(state.get("last_map_change"), now) <= config.IN_SEASON_DAYS * 24
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

    # 1. Cheap check: has the grooming map changed? (Resorts with no map: nothing to wait for.)
    has_map = bool(config.GROOMING_PDF_URL)
    groom = _try("grooming map", lambda: grooming.fetch(state.get("last_map_hash")), errors, None) if has_map else None
    map_changed = bool(groom) and groom["hash"] != state.get("last_map_hash")
    last_change = now.isoformat(timespec="minutes") if map_changed else state.get("last_map_change")
    # "New" = changed since the last report went out (or in the last 18 hours if none has).
    ref = state.get("last_sent_at") or (now - timedelta(hours=18)).isoformat(timespec="minutes")
    map_new = _since(last_change, ref) if has_map else True

    # 2. Only when a send could happen: is the resort's snow report dated today?
    resort_report, resort_fresh = None, None
    in_window = (send and state.get("last_sent_date") != day_str and now.date() >= config.OPENING_DAY
                 and now >= _at(now, config.SEND_EARLIEST))
    if in_window and map_new:
        resort_report = resort.fetch()
        resort_fresh = resort.is_fresh(resort_report, now.date())

    decision = send_decision(state, now, map_new=map_new, resort_fresh=resort_fresh, send=send, has_map=has_map)

    age = _hours_since(state.get("last_full_run"), now)
    new_day = (state.get("last_full_run") or "")[:10] != day_str
    pre_send = 0 < (_at(now, config.SEND_TIME) - now).total_seconds() / 60 <= config.PRE_SEND_MINUTES
    stale_after = 1.0 if pre_send else config.REFRESH_HOURS
    full = force or map_changed or new_day or age >= stale_after or decision not in (None, "quiet")

    if not full and decision is None:
        log.info("nothing new (map unchanged, forecast %.1fh old)", age)
        retried = _retry_failed(store, state, now, day_str, slug, send, errors)
        if _watchdog(state, now, day_str, send, decision, errors) or retried:
            store.put_json("data/state.json", state)
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
            failed = {k: v for k, v in (delivered or {}).items() if str(v).startswith("FAILED")}
            if failed:
                errors.append(f"delivery: {failed}")
                alert.admin(f"0xSnow {config.RESORT_NAME}: send failed",
                            f"{day_str} {', '.join(f'{k} {v}' for k, v in failed.items())}")
                # Email is safe to send again (idempotency keys), so later ticks retry it.
                if "email" in failed:
                    state["retry"] = {"date": day_str, "channels": ["email"], "tries": 0,
                                      "preseason": decision == "preseason"}
            day["delivery"] = {"sent_at": now_local().isoformat(timespec="seconds"), "reason": decision,
                               "new_map": map_new, "snow_report_fresh": resort_fresh, "results": delivered}
            store.put_json(f"data/days/{day_str}.json", day)
            store.put_json("data/latest.json", day)
            _try("report archive", lambda: pages.add_post(store, slug, day_str, day), errors)
        state["last_sent_date"] = day_str
        state["last_sent_at"] = now.isoformat(timespec="minutes")
    elif in_window and map_new and not resort_fresh:
        log.info("new map is in; waiting for today's snow report")
    if decision is None:
        _retry_failed(store, state, now, day_str, slug, send, errors)

    _watchdog(state, now, day_str, send, decision, errors)
    store.put_json("data/state.json", state)
    return {"status": "ok", "resort": slug, "full_run": full, "map_changed": map_changed, "decision": decision,
            "sent": delivered, "errors": errors, "ok": bool(day.get("forecast")) and (groom is not None or not full or not has_map)}


RETRY_MAX = 3   # extra tries for a failed email, one per tick, before giving up for the day


def _retry_failed(store, state, now, day_str, slug, send, errors):
    """The daily email failed earlier today: try it again on this tick (Resend's idempotency
    key makes a repeat of anything that did go out a no-op). True when state changed."""
    r = state.get("retry") or {}
    if not send or r.get("date") != day_str or r.get("tries", 0) >= RETRY_MAX or now >= _at(now, config.SEND_CUTOFF):
        return False
    day = store.get_json("data/latest.json", {}) or {}
    if day.get("date") != day_str:
        return False
    g = day.get("grooming", {})
    map_url = f"{config.DASHBOARD_URL.rstrip('/')}/{g['image']}" if g.get("image") else None
    powder = report.powder_alert(day.get("forecast"))
    res = notify.send_all(dict(day, preseason=r.get("preseason"), powder=powder), map_url,
                          channels=r.get("channels") or ["email"], slug=slug)
    failed = [k for k, v in res.items() if str(v).startswith("FAILED")]
    r["tries"] = r.get("tries", 0) + 1
    delivery = day.get("delivery") or {}
    delivery.setdefault("retries", []).append({"at": now.isoformat(timespec="minutes"), "results": res})
    delivery["results"] = (delivery.get("results") or {}) | res
    day["delivery"] = delivery
    store.put_json(f"data/days/{day_str}.json", day)
    store.put_json("data/latest.json", day)
    if failed:
        errors.append(f"delivery retry {r['tries']}: {res}")
        state["retry"] = dict(r, channels=failed)
        if r["tries"] >= RETRY_MAX:
            alert.admin(f"0xSnow {config.RESORT_NAME}: email still failing",
                        f"{day_str}: gave up after {RETRY_MAX} retries: {res}")
    else:
        state.pop("retry", None)
        log.info("email retry %d worked: %s", r["tries"], res)
    return True


def _watchdog(state, now, day_str, send, decision, errors):
    """Half an hour past the deadline and still no report today: tell the owner, once a day."""
    if (send and state.get("last_sent_date") != day_str and state.get("missed_alert") != day_str
            and now >= _at(now, config.SEND_LATEST) + timedelta(minutes=30)):
        state["missed_alert"] = day_str
        alert.admin(f"0xSnow {config.RESORT_NAME}: no report yet",
                    f"{day_str}: nothing sent by {now.strftime('%H:%M')} (decision {decision!r}, errors {errors})")
        return True
    return False


def _claim_send(day_str, reason, slug=resorts.DEFAULT):
    """Atomic once-per-day-per-resort guard. Without a database (tests, local runs) it always allows."""
    if not _db_url():
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


PRIORS_VERSION = 2  # 2: learned per forecast range from runs made 1, 3 and 5 days ahead


def _terrain_priors(store, today, errors, saved_only=False):
    """{model: {lead group: bias_ratio}} over last winter. Worked out once a season and kept in
    data/priors.json; a failed attempt is retried on the next day, not on every run.
    `saved_only` never fetches (for runs where SNOTEL is already down)."""
    start, end = verify.prior_season(today)
    saved = store.get_json("data/priors.json", {}) or {}
    current = saved.get("season") == start.isoformat() and saved.get("version") == PRIORS_VERSION
    if current and (saved.get("models") or saved.get("tried") == today.isoformat()):
        return _prior_ratios(saved.get("models") or {})
    if saved_only:
        return {}
    doc = {"version": PRIORS_VERSION, "season": start.isoformat(), "season_end": end.isoformat(),
           "tried": today.isoformat(), "models": {}}
    try:
        obs = snotel.fetch_daily_precip(start, end + timedelta(days=1))
        if not obs:
            raise ValueError("no SNOTEL history")
        doc["station"] = obs["station"]
        for group, daily in openmeteo.fetch_history_by_lead(start, end).items():
            for m, v in verify.terrain_priors(daily, obs["daily"]).items():
                doc["models"].setdefault(m, {})[group] = v
    except Exception as e:
        log.warning("terrain priors failed: %s", e)
        errors.append(f"terrain priors: {e}")
    store.put_json("data/priors.json", doc)
    return _prior_ratios(doc["models"])


def _prior_ratios(models):
    return {m: {g: v["bias_ratio"] for g, v in groups.items()} for m, groups in models.items()}


def _resort_daily(store, today):
    """{date: inches} of the resort's reported 24h snowfall, from the month files."""
    out = {}
    first = today - timedelta(days=verify.WINDOW_DAYS)
    for ym in sorted({(first + timedelta(days=i)).isoformat()[:7] for i in range(verify.WINDOW_DAYS + 1)}):
        for d, row in ((store.get_json(f"data/months/{ym}.json", {}) or {}).get("days") or {}).items():
            if row.get("resort_24h") is not None and row.get("resort_fresh"):
                out[d] = row["resort_24h"]
    return out


def _mountain():
    """Avalanche danger, the NWS discussion link, and on-mountain readings (Synoptic when a token
    is set, else snow depth at nearby ski-area and SNOTEL stations from NOAA's snow center)."""
    nohrsc = mountain.fetch_nohrsc()
    stations = mountain.fetch_stations() or mountain.mountain_depth(nohrsc, mountain.base_elevation())
    return {"avalanche": mountain.fetch_avalanche(), "discussion": mountain.fetch_discussion(),
            "stations": stations, "nohrsc": nohrsc}


def _full_run(store, state, groom, map_changed, now, day_str, errors, resort_report=None):
    models = _try("open-meteo", openmeteo.fetch_models, errors, {})
    ens = _try("open-meteo ensemble", openmeteo.fetch_ensemble, errors, {})
    nws_daily = _try("nws", nws.fetch_snowfall, errors, {})
    band_rows = _try("open-meteo bands", openmeteo.fetch_bands, errors, {})
    obs = _try("snotel", snotel.fetch, errors, {})
    resort_report = resort_report if resort_report is not None else resort.fetch()
    # Readers return {} instead of raising; record that so missing data doesn't look normal.
    if not obs and config.SNOTEL_STATIONS:
        errors.append("snotel: no station answered")
    if not resort_report and (config.DOR_API or config.REPORTPAL or config.REPORT_FEED or config.RESORT_SNOW_REPORT_URL):
        errors.append("resort snow report: empty or unreadable")

    if obs:
        verification = verify.compute(obs.get("daily", {}),
                                      lambda d: store.get_json(f"data/forecasts/{d}.json"), today=now.date(),
                                      priors=_terrain_priors(store, now.date(), errors),
                                      resort_daily=_resort_daily(store, now.date()))
        verification["station"] = obs.get("station")
        store.put_json("data/verification.json", verification)
    else:
        # Nothing new to score, but the current priors and limits still apply.
        verification = verify.refresh(store.get_json("data/verification.json", {}) or {},
                                      _terrain_priors(store, now.date(), errors, saved_only=True),
                                      no_prior=openmeteo.NO_PRIOR_MODELS)
    fc = forecast.build(models, nws_daily, ens, verification, today=now.date(), now=now) if (models or nws_daily) else None
    if fc:
        store.put_json(f"data/forecasts/{day_str}.json", fc)
    # Snow Audit: freeze the morning call and log what fell (never fails the run).
    audit.record(config.RESORT, fc, obs, resort_report, verification, now,
                 fresh=bool(resort.is_fresh(resort_report, now.date())))
    hourly = forecast.hourly_outlook(models, now=now) if models else {"hours": []}

    prev = store.get_json(f"data/days/{day_str}.json", {}) or {}
    g = dict(prev.get("grooming") or {"new_map": False, "image": state.get("last_map_image"),
                                      "extra_images": state.get("last_map_extra") or []})
    if not config.GROOMING_PDF_URL:
        g = {"new_map": False, "image": None, "none": True}  # this resort posts no grooming map
        feed = (dor if config.DOR_API else reportpal if config.REPORTPAL
                else vrterrain if config.TERRAIN_STATUS_URL else None)
        if feed:  # no map, but the resort's trail feed says which runs are groomed
            runs = _try("grooming feed", feed.fetch_grooming, errors, None)
            if runs is not None:
                g = {"new_map": bool(runs["groomed"]), "image": None, "runs": runs, "list": True}
    if groom and not g.get("runs"):
        g["runs"] = groom.get("runs")  # same map as before: still show its run names and date
    if groom and map_changed:
        store.put_bytes(f"maps/{day_str}.jpg", groom["jpeg"], "image/jpeg")
        path = _public(store, f"maps/{day_str}.jpg")
        # Pages 2+ of a multi-page sheet (Vail posts two): maps/<day>-p2.jpg, ...
        extra = []
        for n, jpeg in enumerate(groom.get("extra_jpegs") or [], start=2):
            store.put_bytes(f"maps/{day_str}-p{n}.jpg", jpeg, "image/jpeg")
            extra.append(_public(store, f"maps/{day_str}-p{n}.jpg"))
        g = {"new_map": True, "image": path, "extra_images": extra, "hash": groom["hash"], "runs": groom.get("runs"),
             "last_modified": groom.get("last_modified")}
        state.update(last_map_hash=groom["hash"], last_map_image=path, last_map_extra=extra,
                     last_map_change=now.isoformat(timespec="minutes"))

    day = {
        "date": day_str,
        "resort_slug": config.RESORT,
        "resort_name": config.RESORT_NAME,
        "generated": now.isoformat(timespec="minutes"),
        "grooming": g,
        "forecast": {k: v for k, v in (fc or {}).items() if k != "raw"},
        "hourly": hourly,
        "bands": forecast.band_outlook(band_rows, now=now) if band_rows else [],
        "observed": (obs or {}).get("last_24h", {}) | ({"station": obs["station"]} if obs else {}),
        "resort": resort_report,
        "cam": prev.get("cam") or _snapshot_stake(store, day_str),
        "mountain": _mountain(),
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
