"""POST /api/hit {v, t, r, s, m} -> count one app view (bcbot/stats.py). Always answers 204."""
import logging

from bcbot.web import Handler
from bcbot import db, resorts, stats


class handler(Handler):
    def do_POST(self):
        ua = (self.headers.get("User-Agent") or "").lower()
        hit = None if any(b in ua for b in ("bot", "spider", "crawl", "headless", "preview")) else \
            stats.clean_hit(self.body_json(), resorts.RESORTS)
        if hit:
            try:
                with db.connect() as conn:
                    stats.record_hit(conn, hit)
            except Exception:
                logging.exception("hit failed")
        self.send_response(204)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
