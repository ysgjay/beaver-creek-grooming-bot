"""Tiny helpers shared by the Vercel Python endpoints in api/."""
import json
import logging
import re
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logging.basicConfig(level=logging.INFO)

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[A-Za-z]{2,}$")


class Handler(BaseHTTPRequestHandler):
    def query(self, name):
        return (parse_qs(urlsplit(self.path).query).get(name) or [""])[0]

    def body_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n or n > 8192:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw)
        except ValueError:
            return {k: v[0] for k, v in parse_qs(raw.decode(errors="ignore")).items()}

    def reply(self, code, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else (json.dumps(body) if content_type == "application/json" else body).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if "json" in content_type or "text" in content_type else ""))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
