"""Daily pipeline: fetch -> forecast -> verify -> archive -> notify -> (site built by workflow).

Usage:
  python -m bcbot run [--dry-run] [--force-send]
  python -m bcbot site          # build _site/ from data/
  python -m bcbot discover      # print candidate cam image URLs from the resort site
Env DRY_RUN=1 behaves like --dry-run (no notifications, state not advanced).
"""
import argparse
import logging
import os
import re
import sys

from . import config, forecast, notify, report, site, verify
from .sources import grooming, nws, openmeteo, resort, snotel
from .util import get, now_local, read_json, write_json

log = logging.getLogger("bcbot")
D = config.DATA_DIR


def _try(name, fn, errors, default=None):
    try:
        return fn()
    except Exception as e:
        log.exception("%s failed", name)
        errors.append(f"{name}: {e}")
        return default


def _archive_cam(day_str):
    if not config.CAMS:
        return None
    try:
        r = get(config.CAMS[0], timeout=30)
        r.raise_for_status()
        path = D / "cams" / f"{day_str}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
        return f"data/cams/{day_str}.jpg"
    except Exception as e:
        log.warning("stake cam snapshot failed: %s", e)
        return None


def _update_index(day):
    index = read_json(D / "index.json", {"days": []})
    entry = {
        "date": day["date"],
        "map": day["grooming"].get("image"),
        "new_map": day["grooming"].get("new_map", False),
        "next_1_5": (day.get("forecast") or {}).get("next_1_5"),
        "snow_24h": (day.get("observed") or {}).get("snow_in"),
        "resort_24h": (day.get("resort") or {}).get("last_24h_in"),
    }
    days = [d for d in index["days"] if d["date"] != day["date"]] + [entry]
    index["days"] = sorted(days, key=lambda d: d["date"], reverse=True)
    index["updated"] = now_local().isoformat(timespec="minutes")
    write_json(D / "index.json", index)


def run(dry_run=False, force_send=False):
    errors = []
    now = now_local()
    today = now.date()
    day_str = today.isoformat()
    state = read_json(D / "state.json", {})

    # 1. Sources (each one optional)
    models = _try("open-meteo", openmeteo.fetch_models, errors, {})
    ens = _try("open-meteo ensemble", openmeteo.fetch_ensemble, errors, {})
    nws_daily = _try("nws", nws.fetch_snowfall, errors, {})
    obs = _try("snotel", snotel.fetch, errors, {})
    resort_report = resort.fetch()
    groom = _try("grooming map", grooming.fetch, errors, None)

    # 2. Verification first, so today's blend uses the freshest bias/skill numbers.
    verification = verify.compute(obs.get("daily", {})) if obs else read_json(D / "verification.json", {})
    if obs:
        verification["station"] = obs.get("station")
        write_json(D / "verification.json", verification)

    # 3. Forecast
    fc = forecast.build(models, nws_daily, ens, verification, today=today) if (models or nws_daily) else None
    if fc:
        write_json(D / "forecasts" / f"{day_str}.json", fc)
    hourly = forecast.hourly_outlook(models, now=now) if models else {"hours": []}

    # 4. Grooming map (only archive when the PDF actually changed)
    last_hash = state.get("last_map_hash")
    g = {"new_map": False, "image": state.get("last_map_image")}
    if groom:
        g["hash"] = groom["hash"]
        g["last_modified"] = groom["last_modified"]
        if groom["hash"] != last_hash:
            path = D / "maps" / f"{day_str}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(groom["jpeg"])
            g.update(new_map=True, image=f"data/maps/{day_str}.jpg", text=groom["text_lines"][:200])
            state["last_map_hash"] = groom["hash"]
            state["last_map_image"] = g["image"]
    elif not g["image"]:
        g["image"] = None

    prev = read_json(D / "days" / f"{day_str}.json", {})
    day = {
        "date": day_str,
        "generated": now.isoformat(timespec="minutes"),
        "grooming": g if (g["new_map"] or not prev.get("grooming", {}).get("new_map")) else prev["grooming"],
        "forecast": {k: v for k, v in (fc or {}).items() if k != "raw"},
        "hourly": hourly,
        "observed": (obs or {}).get("last_24h", {}) | ({"station": obs["station"]} if obs else {}),
        "resort": resort_report,
        "cam": prev.get("cam") or _archive_cam(day_str),
        "errors": errors,
    }
    write_json(D / "days" / f"{day_str}.json", day)
    write_json(D / "latest.json", day)
    _update_index(day)

    # 5. Notify: once per new grooming map (several cron runs a morning catch a late upload).
    text = report.compose(day)
    print("\n----- message -----\n" + text + "\n-------------------")
    image = groom["jpeg"] if groom else None
    should_send = force_send or (day["grooming"].get("new_map") and state.get("last_sent_date") != day_str)
    if should_send and not dry_run:
        results = notify.send_all(text, image)
        log.info("delivery: %s", results)
        state["last_sent_date"] = day_str
        alert = report.powder_alert(fc)
        if alert and state.get("last_alert_date") != day_str:
            notify.send_all(alert, channels=["ntfy"])
            state["last_alert_date"] = day_str
    elif dry_run:
        log.info("dry run: would %s", "send" if should_send else "not send")
    else:
        log.info("no new grooming map -> not sending (use --force-send to override)")

    if not dry_run:
        write_json(D / "state.json", state)

    if errors:
        log.warning("source errors: %s", errors)
    # Fail the job (GitHub emails the owner) only if the core of the report is missing.
    if not fc or not groom:
        return 1
    return 0


def discover():
    """Print image URLs on the resort cams page, to fill in CAM_URLS."""
    for url in ["https://www.beavercreek.com/the-mountain/mountain-conditions/mountain-cams.aspx",
                config.RESORT_SNOW_REPORT_URL]:
        try:
            html = get(url).text
        except Exception as e:
            print(url, "->", e)
            continue
        found = set(re.findall(r'https?://[^"\'\s>]+?\.(?:jpe?g|png)(?:\?[^"\'\s>]*)?', html, re.I))
        found |= set(re.findall(r'https?://[^"\'\s>]*(?:cam|stake)[^"\'\s>]*', html, re.I))
        print(f"{url}: {len(html)} bytes")
        for f in sorted(found):
            print("  ", f)


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="bcbot")
    ap.add_argument("command", choices=["run", "site", "discover"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-send", action="store_true")
    a = ap.parse_args(argv)
    if a.command == "site":
        print(site.build())
        return 0
    if a.command == "discover":
        discover()
        return 0
    dry = a.dry_run or os.environ.get("DRY_RUN") == "1"
    force = a.force_send or os.environ.get("FORCE_SEND") == "1"
    return run(dry_run=dry, force_send=force)


if __name__ == "__main__":
    sys.exit(main())
