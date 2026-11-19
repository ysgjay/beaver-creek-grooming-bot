"""Daily resort-facts watch (bcbot/facts.py): reads each fact's source page, notes changes, and
writes data/facts/status.json with what's due for a re-check. Vercel cron, Bearer $CRON_SECRET."""
import logging
import os

from bcbot.web import Handler
from bcbot import facts
from bcbot.store import get_store
from bcbot.util import http

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"


def fetch(url):
    try:
        r = http().get(url, timeout=8, headers={"User-Agent": UA, "Accept": "text/html"})
        return r.text if r.ok else None
    except Exception:
        return None


class handler(Handler):
    def do_GET(self):
        if "queue=1" in (self.path or ""):
            # Read-only work list for the re-check task. Public data only (facts and lines from public pages).
            st = get_store().get_json("data/facts/status.json", {}) or {}
            return self.reply(200, {"generated": st.get("generated"), "queue": st.get("queue", []),
                                    "failing": st.get("failing", [])})
        secret = os.environ.get("CRON_SECRET", "")
        if not secret or self.headers.get("Authorization") != f"Bearer {secret}":
            return self.reply(401, {"error": "unauthorized"})
        try:
            status = facts.watch(get_store(), fetch)
            if status["changed_today"] or status["failing"] or any(d["overdue_days"] >= 2 for d in status["due"]):
                from bcbot import alert
                alert.admin("0xSnow: resort facts to re-check",
                            f"changed: {', '.join(status['changed_today']) or 'none'}; "
                            f"failing 3+ days: {', '.join(status['failing']) or 'none'}; "
                            f"due: {', '.join(d['resort'] + ' ' + d['fact'] for d in status['due'][:10]) or 'none'}")
            return self.reply(200, {"changed": status["changed_today"], "failing": status["failing"],
                                    "due": status["due"], "queue": len(status["queue"])})
        except Exception as e:
            logging.exception("facts watch failed")
            return self.reply(500, {"error": str(e)})
