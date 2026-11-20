"""Grooming coverage (bcbot/groomwatch.py): daily watch for resorts whose grooming is missing after
opening day, plus the weekly finder (Mondays, or ?find=1) that looks for grooming sources for the
resorts without one. Vercel cron, Bearer $CRON_SECRET. GET ?status=1 is a public read of both results."""
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from bcbot.web import Handler
from bcbot import groomwatch
from bcbot.store import get_store
from bcbot.util import http

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"


def fetch(url):
    try:
        r = http().get(url, timeout=8, headers={"User-Agent": UA, "Accept": "text/html,application/json"})
        return r.text if r.ok else None
    except Exception:
        return None


def head(url):
    try:
        return http().head(url, timeout=8, headers={"User-Agent": UA}, allow_redirects=True).status_code
    except Exception:
        return None


class handler(Handler):
    def do_GET(self):
        path = self.path or ""
        store = get_store()
        if "status=1" in path:  # public data only: resort names, sources and dates
            return self.reply(200, {"watch": store.get_json(groomwatch.WATCH_PATH, {}) or {},
                                    "find": store.get_json(groomwatch.FIND_PATH, {}) or {}})
        secret = os.environ.get("CRON_SECRET", "")
        if not secret or self.headers.get("Authorization") != f"Bearer {secret}":
            return self.reply(401, {"error": "unauthorized"})
        try:
            from bcbot import alert
            now = datetime.now(ZoneInfo("UTC"))
            w = groomwatch.watch(store, now)
            if w["alerts"]:
                alert.admin("0xSnow: grooming missing",
                            "; ".join(f"{a['name']}: {a['problem']}" for a in w["alerts"]))
            out = {"alerts": w["alerts"]}
            if "find=1" in path or now.astimezone(ZoneInfo("America/Denver")).weekday() == 0:
                f = groomwatch.find(store, fetch, head, now)
                if f["new"]:
                    alert.admin("0xSnow: grooming source found",
                                "; ".join(f"{n['name']}: {n['kind']} {n['url']}" for n in f["new"]))
                out["found"] = f["new"]
            return self.reply(200, out)
        except Exception as e:
            logging.exception("groom watch failed")
            return self.reply(500, {"error": str(e)})
