"""POST /api/subscribe {email} -> double opt-in: store as pending, email a confirmation link."""
import logging

from bcbot.web import EMAIL_RE, Handler
from bcbot import db, mailer

OK = {"ok": True, "message": "Check your inbox for a confirmation link."}


class handler(Handler):
    def do_POST(self):
        data = self.body_json()
        email = str(data.get("email", "")).strip()
        if data.get("website"):          # honeypot field humans never fill
            return self.reply(200, OK)
        if len(email) > 254 or not EMAIL_RE.match(email):
            return self.reply(400, {"ok": False, "message": "That doesn't look like an email address."})
        try:
            with db.connect() as conn:
                token, send = db.request_signup(conn, email)
            if send:
                mailer.send_confirmation(email, token)
        except Exception:
            logging.exception("subscribe failed")
            return self.reply(500, {"ok": False, "message": "Sign-up is having trouble. Please try again later."})
        return self.reply(200, OK)  # same answer either way: never reveals who is subscribed
