"""Render background worker: runs the resort readers and the daily pipeline off Vercel.

Vercel functions stop at 60 s each, so every resort needs its own call and the fan-out grows
with the resort list. This worker is one long-running process with no time limit. It ticks on
the same UTC schedule as the Cloudflare Worker (cloudflare/worker.js) and runs the due resorts
in a small thread pool, then the combined email.

  python -m bcbot.worker             loop forever (Render startCommand)
  python -m bcbot.worker --once      one tick now, every enabled resort (smoke test)

Modes (WORKER_MODE):
  shadow (default)  reads the live archive, writes to a local folder only (store.ShadowStore),
                    never sends. Safe to run beside Vercel to check the readers on Render.
  live              writes the real archive and sends. Switch only after turning the Cloudflare
                    trigger off, so one scheduler drives the pipeline (docs/RENDER.md).
"""
import argparse
import ctypes
import gc
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

log = logging.getLogger("bcbot.worker")


def mode():
    return "live" if os.environ.get("WORKER_MODE", "shadow").strip().lower() == "live" else "shadow"


def _configure_mode():
    """Shadow mode must be decided before bcbot.config reads the environment."""
    if mode() == "shadow":
        os.environ["STORE_MODE"] = "shadow"
        os.environ["SEND_ENABLED"] = "0"


def is_tick(now):
    """Same minutes as the Cloudflare crons: */5 11-13, */15 9-10 and 14-17, 0 21 (UTC)."""
    h, m = now.hour, now.minute
    return (11 <= h <= 13 and m % 5 == 0) or ((9 <= h <= 10 or 14 <= h <= 17) and m % 15 == 0) or (h == 21 and m == 0)


def tick(force=False, now=None):
    from bcbot import resorts
    from bcbot.main import run
    from api.run import due

    # Shadow mode also runs the resorts that are being checked before launch (resorts.shadow()).
    slugs = due(resorts.enabled() + (resorts.shadow() if mode() == "shadow" else []), force=force, now=now)
    # 2 at a time: each full run holds a forecast, ensembles and images, and the Starter plan has 512 MB.
    workers = max(1, int(os.environ.get("WORKER_CONCURRENCY", "2")))

    def one(slug):
        try:
            return slug, run(force=force, slug=slug)
        except Exception as e:
            log.exception("%s run failed", slug)
            return slug, {"status": "error", "error": str(e)}

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = dict(pool.map(one, slugs))
    digest = None
    if mode() == "live":
        from api.run import _digest
        digest = _digest()
    if mode() == "shadow":
        compare_forecasts([s for s, r in results.items() if r.get("full_run") and s in resorts.enabled()])
    bad = [s for s, r in results.items() if r.get("status") == "error" or (r.get("status") != "skipped" and not r.get("ok"))]
    log.info("tick (%s): %d resorts in %.0fs, %d with problems %s, %s MB", mode(), len(results),
             time.monotonic() - started, len(bad), bad, _release_memory())
    return {"mode": mode(), "resorts": results, "digest": digest}


def _snow(day, n=3):
    days = ((day or {}).get("forecast") or {}).get("days") or []
    return round(sum(d.get("snow") or 0 for d in days[:n]), 1) if days else None


def compare_forecasts(slugs):
    """Shadow check before going live: for each live resort this tick refreshed, log the next
    3 days of snow from our run (self-hosted forecast) beside what the app shows now (Vercel,
    public API). One line per tick, so the logs show whether the two agree."""
    from bcbot import store
    shadow = store.get_store()
    if not slugs or not isinstance(shadow, store.ShadowStore):
        return None
    rows, big = [], []
    for slug in slugs:
        try:
            ours = _snow(store.ResortStore(shadow.local, slug).get_json("data/latest.json"))
            live = _snow(store.ResortStore(shadow.live, slug).get_json("data/latest.json"))
        except Exception as e:
            log.warning("compare %s failed: %s", slug, e)
            continue
        if ours is None or live is None:
            continue
        rows.append(f"{slug} {ours}/{live}")
        if abs(ours - live) > max(1.0, 0.25 * max(ours, live)):
            big.append(slug)
    if rows:
        log.info("compare 3-day snow in (render/vercel), %d differ by more than 25%%: %s | %s",
                 len(big), big, ", ".join(rows))
    return {"rows": rows, "differ": big}


def _release_memory():
    """Give memory from the tick back to the system, so the worker idles low between ticks.
    Python keeps freed memory by default, which left it near its limit before the next tick.
    Returns resident memory in MB (None if it can't be read)."""
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass
    try:
        with open("/proc/self/status") as f:
            return next(int(line.split()[1]) // 1024 for line in f if line.startswith("VmRSS:"))
    except Exception:
        return None


def _start_tick_due():
    """The start-up check runs once per deploy, not after every restart. An out-of-memory restart
    used to run a full forced tick again, which ran out of memory again (a crash loop on 11/19)."""
    from pathlib import Path
    commit = os.environ.get("RENDER_GIT_COMMIT") or "local"
    marker = Path(os.environ.get("SHADOW_DIR") or "/tmp/0xsnow-shadow") / ".start-tick"
    try:
        if marker.read_text().strip() == commit:
            return False
    except OSError:
        pass
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(commit)  # written before the tick, so a crash during it doesn't repeat it
    except OSError:
        pass
    return True


def check_forecast_server():
    """Log whether our own Open-Meteo server answers, and how fast (first call is a cold cache)."""
    from bcbot.sources import openmeteo
    base = openmeteo.self_hosted_base()
    if not base:
        log.info("no self-hosted Open-Meteo configured; using the public API")
        return None
    from bcbot.util import http
    try:
        t = time.monotonic()
        r = http().get(f"{base}/v1/forecast", timeout=60, params={
            "latitude": 39.6, "longitude": -106.5, "hourly": "temperature_2m,precipitation",
            "models": "gfs_global,ncep_nbm_conus,gfs_hrrr,ecmwf_ifs025", "forecast_days": 3})
        log.info("forecast server %s: HTTP %s in %.1fs %s", base, r.status_code, time.monotonic() - t,
                 "" if r.ok else r.text[:200])
        return r.ok
    except Exception as e:
        log.warning("forecast server %s unreachable: %s", base, e)
        return False


def loop():
    log.info("0xSnow worker started in %s mode", mode())
    check_forecast_server()
    if mode() == "shadow" and os.environ.get("WORKER_TICK_ON_START", "1") == "1" and _start_tick_due():
        try:  # every deploy checks every reader once; harmless in shadow mode
            tick(force=True)
        except Exception:
            log.exception("start-up tick failed")
    last = None
    while True:
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        if now != last and is_tick(now):
            last = now
            try:
                tick(now=now)
            except Exception:
                log.exception("tick failed")
        time.sleep(max(1.0, 60 - datetime.now(timezone.utc).second))


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="bcbot.worker")
    ap.add_argument("--once", action="store_true", help="one forced tick now, then exit")
    a = ap.parse_args(argv)
    _configure_mode()
    if a.once:
        out = tick(force=True)
        print({s: r.get("status") for s, r in out["resorts"].items()})
        bad = [s for s, r in out["resorts"].items() if r.get("status") == "error"]
        return 1 if bad else 0   # a resort that crashed fails the smoke test
    loop()
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.exit(main())
