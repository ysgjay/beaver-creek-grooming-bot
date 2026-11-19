"""Vercel Python function: POST/GET /api/run runs the pipeline.

Called by the Cloudflare Worker cron and by Vercel's own daily cron as a backup. Both send
`Authorization: Bearer $CRON_SECRET`.

  /api/run                 every enabled resort. In production each resort runs in its own
                           function call (so one slow resort can't eat another's time limit).
                           Then the combined email for multi-resort subscribers (bcbot/digest.py).
  /api/run?resort=vail     one resort
  &force=1                 full refresh
  &test=1                  labeled test send (needs ?resort=, default Beaver Creek)
"""
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bcbot import config, resorts  # noqa: E402
from bcbot.main import run, send_test  # noqa: E402
from bcbot.util import http  # noqa: E402

logging.basicConfig(level=logging.INFO)


def _ok(result):
    return result.get("status") == "skipped" or bool(result.get("ok"))


def due(slugs, force=False, user_agent="", now=None):
    """Which resorts this tick should run. Resorts with nothing to watch between refreshes
    (no grooming map, no snow report that's read) only need the ticks on the hour and half
    hour, which still cover every refresh and the 7:00 send. That keeps the free plans'
    request counts low as resorts are added. Vercel's own backup cron always runs them all."""
    if force or "vercel-cron" in user_agent.lower():
        return list(slugs)
    from datetime import datetime, timezone
    minute = (now or datetime.now(timezone.utc)).minute
    return [s for s in slugs if minute % 30 < 2 or not resorts.is_static(s)]


TICK_SECONDS = 55   # Vercel stops the function at 60 s (vercel.json maxDuration)


def _digest(deadline=None):
    """After the resorts run: the combined email for people with several resorts, once all of
    theirs are in (or at the cutoff). Never fails the tick. With a deadline it leaves anything
    it can't finish in time for the next tick rather than risk being cut off mid-send."""
    try:
        from bcbot import digest
        return digest.run(deadline=deadline)
    except Exception as e:
        logging.exception("digest failed")
        from bcbot import alert
        alert.admin("0xSnow: combined email failed", str(e)[:500])
        return {"status": "error", "error": str(e)}


class handler(BaseHTTPRequestHandler):
    def _go(self):
        import time
        started = time.monotonic()
        secret = os.environ.get("CRON_SECRET", "")
        auth = self.headers.get("Authorization")
        if not secret or auth != f"Bearer {secret}":
            return self._reply(401, {"error": "unauthorized"})
        q = parse_qs(urlsplit(self.path or "").query)
        force = q.get("force", [""])[0] == "1"
        slug = q.get("resort", [""])[0]
        if slug and slug not in resorts.enabled():
            return self._reply(400, {"error": f"unknown or disabled resort {slug!r}"})
        try:
            if q.get("test", [""])[0] == "1":
                result = send_test(slug=slug or resorts.DEFAULT)
                return self._reply(200 if result.get("status") == "ok" else 409, result)
            if slug:
                result = run(force=force, slug=slug)
                return self._reply(200 if _ok(result) else 500, result)
            results = self._fan_out(auth, force)
            code = 200 if all(_ok(r) for r in results.values()) else 500
            return self._reply(code, {"status": "ok", "resorts": results, "digest": _digest(deadline=started + TICK_SECONDS)})
        except Exception as e:  # report, don't hide
            logging.exception("run failed")
            return self._reply(500, {"status": "error", "error": str(e)})

    def _fan_out(self, auth, force):
        slugs = due(resorts.enabled(), force, self.headers.get("User-Agent", ""))
        if not slugs:
            return {}
        host = urlsplit(config.DASHBOARD_URL).netloc  # never the request's Host: the secret goes along
        # Production: one function call per resort, in parallel. Previews sit behind Vercel
        # login protection (a self-call would bounce), so they run the resorts in this call.
        if os.environ.get("VERCEL_ENV") != "production" or not host or len(slugs) == 1:
            out = {}
            for s in slugs:
                try:
                    out[s] = run(force=force, slug=s)
                except Exception as e:
                    logging.exception("%s run failed", s)
                    out[s] = {"status": "error", "error": str(e)}
            return out

        def one(s):
            try:
                r = http().post(f"https://{host}/api/run", params={"resort": s, **({"force": "1"} if force else {})},
                                headers={"Authorization": auth}, timeout=58)
                return s, r.json()
            except Exception as e:
                return s, {"status": "error", "error": str(e)}

        with ThreadPoolExecutor(max_workers=len(slugs)) as pool:
            return dict(pool.map(one, slugs))

    def _reply(self, code, body):
        data = json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    do_GET = _go
    do_POST = _go
