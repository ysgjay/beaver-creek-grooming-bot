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
        try:  # grooming watch + finder results (bcbot/groomwatch.py), merged into the coverage rows
            from bcbot import groomwatch
            from bcbot.store import get_store
            st = get_store()
            gw = {x["resort"]: x for x in (st.get_json(groomwatch.WATCH_PATH, {}) or {}).get("rows", [])}
            gf = {x["resort"]: x for x in (st.get_json(groomwatch.FIND_PATH, {}) or {}).get("results", [])}
            for row in out["coverage"]:
                w, f = gw.get(row["resort"], {}), gf.get(row["resort"], {})
                row.update(last_grooming=w.get("last_grooming"), grooming_problem=w.get("problem", ""),
                           grooming_found=[x["kind"] for x in f.get("found", [])],
                           grooming_links=f.get("links", []), grooming_hints=f.get("providers", []))
        except Exception:
            logging.exception("grooming coverage failed")
        out["facts"] = facts.grid()  # resort facts table: filled, not posted, missing, and freshness
        self.reply(200, out)
