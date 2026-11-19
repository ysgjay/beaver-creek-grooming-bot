"""Vercel Python function: /api/audit, the Snow Audit (bcbot/audit.py).

  GET /api/audit (or ?job=1)              cron (Bearer CRON_SECRET): replay a few past months,
                                          then rebuild the report cards in data/audit/
  GET /api/audit?resort=vail&log=1        the raw log for the page: one entry per day with
        [&from=2026-10-01&to=2026-11-16]  every call for it (default: the last 45 days)
  GET /api/audit?resort=vail&format=csv   the same calls as a CSV, one row per call
        [&kind=live|replay&source=...&lead=0-9&from&to]    (default: everything for the resort)

The log and CSV are public, read-only history. Only the job needs the secret.
"""
import csv
import io
import json
import logging
import os
import re
import sys
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bcbot import audit, db, resorts  # noqa: E402

logging.basicConfig(level=logging.INFO)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_LOG_DAYS = 400


def _date(q, key, default):
    v = q.get(key, [""])[0]
    return date.fromisoformat(v) if DATE.match(v) else default


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlsplit(self.path or "").query)
        try:
            if q.get("job", [""])[0] == "1" or not q.get("resort"):
                secret = os.environ.get("CRON_SECRET", "")
                if not secret or self.headers.get("Authorization") != f"Bearer {secret}":
                    return self._json(401, {"error": "unauthorized"})
                return self._json(200, audit.job())
            slug = q.get("resort", [""])[0]
            if slug not in resorts.enabled():  # shadow resorts stay unannounced
                return self._json(400, {"error": "unknown resort"})
            today = date.today()
            if q.get("format", [""])[0] == "csv":
                start, end = _date(q, "from", date(2024, 1, 1)), _date(q, "to", today + timedelta(days=10))
                with db.connect() as conn:
                    lead = q.get("lead", [""])[0]
                    rows = audit.csv_rows(conn, slug, start, end, q.get("kind", [""])[0] or None,
                                          q.get("source", [""])[0] or None, int(lead) if lead.isdigit() else None)
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerow(audit.CSV_HEAD)
                w.writerows(rows)
                return self._send(200, buf.getvalue().encode(), "text/csv; charset=utf-8",
                                  {"Content-Disposition": f'attachment; filename="snow-audit-{slug}.csv"'})
            end = _date(q, "to", today)
            start = max(_date(q, "from", end - timedelta(days=45)), end - timedelta(days=MAX_LOG_DAYS))
            with db.connect() as conn:
                return self._json(200, {"resort": slug, "from": start.isoformat(), "to": end.isoformat(),
                                        "days": audit.log_days(conn, slug, start, end)}, cache=300)
        except Exception as e:
            logging.exception("audit failed")
            return self._json(500, {"status": "error", "error": str(e)})

    def _json(self, code, body, cache=0):
        return self._send(code, json.dumps(body, default=str).encode(), "application/json",
                          {"Cache-Control": f"public, max-age={cache}" if cache and code == 200 else "no-store"})

    def _send(self, code, data, ctype, headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)
