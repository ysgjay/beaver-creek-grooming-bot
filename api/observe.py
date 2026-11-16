"""Vercel Python function: GET /api/observe, the one-week posting-time observer (bcbot/observer.py).

Called every 5 minutes by Vercel cron with `Authorization: Bearer $CRON_SECRET`. Read-only:
it polls sources and writes rows to Neon `posting_polls`. It never sends email or push.
`?force=1` polls every source now, outside the window too.
"""
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bcbot import observer  # noqa: E402

logging.basicConfig(level=logging.INFO)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        secret = os.environ.get("CRON_SECRET", "")
        if not secret or self.headers.get("Authorization") != f"Bearer {secret}":
            return self._reply(401, {"error": "unauthorized"})
        force = parse_qs(urlsplit(self.path or "").query).get("force", [""])[0] == "1"
        try:
            return self._reply(200, observer.run(force=force))
        except Exception as e:
            logging.exception("observe failed")
            return self._reply(500, {"status": "error", "error": str(e)})

    do_POST = do_GET

    def _reply(self, code, body):
        data = json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
