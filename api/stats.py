"""GET /api/stats (Authorization: Bearer ADMIN_KEY) -> the owner's numbers for /admin."""
import logging
import time

from bcbot.web import Handler
from bcbot import db, facts, resorts, stats


class handler(Handler):
    def do_GET(self):
        if not stats.authorized(self.headers.get("Authorization")):
            time.sleep(1)  # slows guessing
            return self.reply(401, {"error": "unauthorized"})
        try:
            with db.connect() as conn:
                out = stats.summary(conn)
        except Exception:
            logging.exception("stats failed")
            return self.reply(500, {"error": "stats failed"})
        out["names"] = {k: v["name"] for k, v in resorts.RESORTS.items()}
        out["coverage"] = resorts.coverage()  # cams and snow report source per resort
        try:
            from bcbot.store import get_store
            confirmed = (get_store().get_json("data/facts/status.json", {}) or {}).get("confirmed")
        except Exception:
            confirmed = None
        out["facts"] = facts.grid(confirmed=confirmed)  # resort facts table: filled, not posted, missing, and freshness
        self.reply(200, out)
