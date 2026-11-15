"""Vercel Python function: POST/GET /api/run runs the pipeline.

Called by the Cloudflare Worker cron (every 30 min, early morning) and by Vercel's own
daily cron as a backup. Both send `Authorization: Bearer $CRON_SECRET`.
"""
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bcbot.main import run, send_test  # noqa: E402

logging.basicConfig(level=logging.INFO)


class handler(BaseHTTPRequestHandler):
    def _go(self):
        secret = os.environ.get("CRON_SECRET", "")
        if not secret or self.headers.get("Authorization") != f"Bearer {secret}":
            return self._reply(401, {"error": "unauthorized"})
        force = "force=1" in (self.path or "")
        try:
            if "test=1" in (self.path or ""):
                result = send_test()
                return self._reply(200 if result.get("status") == "ok" else 409, result)
            result = run(force=force)
            code = 200 if result.get("status") == "skipped" or result.get("ok") else 500
        except Exception as e:  # report, don't hide
            logging.exception("run failed")
            result, code = {"status": "error", "error": str(e)}, 500
        self._reply(code, result)

    def _reply(self, code, body):
        data = json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    do_GET = _go
    do_POST = _go
