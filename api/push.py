"""App notifications.

GET    /api/push                                     -> {publicKey} for PushManager.subscribe
POST   /api/push  {endpoint, keys: {p256dh, auth}, resorts: [slug]} -> save this browser's push subscription
                                                       (posting again with new resorts updates the choice)
DELETE /api/push  {endpoint}                         -> remove it
"""
import logging

from bcbot.web import Handler
from bcbot import db, resorts, webpush


class handler(Handler):
    def do_GET(self):
        # Derived from the private key in Vercel, so it always matches what the server signs with.
        key = webpush.app_key()
        if not key:
            logging.error("VAPID_PRIVATE_KEY is not set")
            return self.reply(503, {"ok": False})
        self.reply(200, {"publicKey": webpush.vapid_public_b64(key)})

    def do_POST(self):
        sub = self.body_json()
        keys = sub.get("keys") or {}
        endpoint = str(sub.get("endpoint", ""))
        if not endpoint.startswith("https://") or len(endpoint) > 1000 or not keys.get("p256dh") or not keys.get("auth"):
            return self.reply(400, {"ok": False})
        try:
            with db.connect() as conn:
                picked = sub.get("resorts")
                picked = resorts.valid(picked if isinstance(picked, list) else []) or [resorts.DEFAULT]
                db.save_push(conn, {"endpoint": endpoint, "p256dh": keys["p256dh"], "auth": keys["auth"]}, picked)
        except Exception:
            logging.exception("push subscribe failed")
            return self.reply(500, {"ok": False})
        self.reply(200, {"ok": True})

    def do_DELETE(self):
        endpoint = str(self.body_json().get("endpoint", ""))
        if endpoint:
            with db.connect() as conn:
                db.delete_push(conn, endpoint)
        self.reply(200, {"ok": True})
