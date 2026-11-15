"""GET /api/confirm?t=... -> activates the subscription and returns to the app."""
from bcbot.web import Handler
from bcbot import db


class handler(Handler):
    def do_GET(self):
        token = self.query("t")
        email = None
        if token:
            with db.connect() as conn:
                email = db.confirm(conn, token)
        self.redirect("/?email=confirmed#help" if email else "/?email=invalid#help")
