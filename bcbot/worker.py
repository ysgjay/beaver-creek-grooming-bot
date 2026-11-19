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

    slugs = due(resorts.enabled(), force=force, now=now)
    workers = max(1, int(os.environ.get("WORKER_CONCURRENCY", "4")))

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
    bad = [s for s, r in results.items() if r.get("status") == "error" or (r.get("status") != "skipped" and not r.get("ok"))]
    log.info("tick (%s): %d resorts in %.0fs, %d with problems %s", mode(), len(results),
             time.monotonic() - started, len(bad), bad)
    return {"mode": mode(), "resorts": results, "digest": digest}


def loop():
    log.info("0xSnow worker started in %s mode", mode())
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
        return 0
    loop()
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.exit(main())
