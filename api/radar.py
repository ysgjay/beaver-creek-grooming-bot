"""GET /api/radar -> 303 to the current email radar snapshot (rendered at most once per 10 minutes).

Lets anyone preview the image the combined morning email carries."""
from datetime import datetime

from bcbot.web import Handler
from bcbot import digest, radar
from bcbot.store import get_store


class handler(Handler):
    def do_GET(self):
        url = radar.snapshot(get_store(), datetime.now(digest.TZ))
        if not url:
            return self.reply(503, {"ok": False, "message": "Radar is unavailable right now."})
        self.redirect(url)
