"""Choose which resorts' morning emails a subscriber gets (the link in every email).

GET  /api/resorts?t=...                  -> a page with a checkbox per resort
POST /api/resorts?t=...  resort=a&resort=b -> saves the choice (none checked = keep as is)
"""
from html import escape
from urllib.parse import parse_qs

from bcbot.web import Handler
from bcbot import db, resorts

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Choose resorts · Chair 0</title></head>
<body style="margin:0;background:#dcebfa;font:16px/1.5 -apple-system,'Segoe UI',Roboto,sans-serif;color:#0c2a4a">
<div style="max-width:420px;margin:10vh auto;background:#fff;border-radius:24px;padding:24px">{body}</div></body></html>"""
BTN = "font:600 16px inherit;background:#0a5bd3;color:#fff;border:0;border-radius:12px;padding:12px 18px;cursor:pointer"


class handler(Handler):
    def _form(self, token, picked, note=""):
        boxes = "".join(
            f'<label style="display:flex;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid #e3edf8">'
            f'<input type="checkbox" name="resort" value="{slug}"{" checked" if slug in picked else ""} style="width:20px;height:20px">'
            f'{escape(resorts.get(slug)["name"])}</label>' for slug in resorts.enabled())
        return PAGE.format(body=(
            f'<h1 style="margin:0 0 6px;font-size:22px">Your morning emails</h1>'
            f'<p style="margin:0 0 12px;color:#4a6382">One email per resort, each once a day.</p>{note}'
            f'<form method="post" action="/api/resorts?t={escape(token)}">{boxes}'
            f'<button style="{BTN};margin-top:16px">Save</button></form>'
            f'<p style="margin:16px 0 0;font-size:13px"><a href="/api/unsubscribe?t={escape(token)}" style="color:#0a5bd3">Unsubscribe from all</a></p>'))

    def _missing(self):
        self.reply(200, PAGE.format(body='<h1 style="margin:0 0 8px;font-size:22px">Link not recognized</h1>'
                                         '<p style="margin:0">It may be unsubscribed. <a href="/#help" style="color:#0a5bd3">Sign up again</a></p>'), "text/html")

    def do_GET(self):
        token = self.query("t")
        with db.connect() as conn:
            found = db.subscriber_resorts(conn, token) if token else None
        if not found:
            return self._missing()
        self.reply(200, self._form(token, found[1]), "text/html")

    def do_POST(self):
        token = self.query("t")
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode(errors="ignore") if 0 < n <= 4096 else ""
        picked = resorts.valid(parse_qs(raw).get("resort", []))
        with db.connect() as conn:
            found = db.subscriber_resorts(conn, token) if token else None
            if not found:
                return self._missing()
            if picked:
                db.set_subscriber_resorts(conn, token, picked)
        note = ('<p style="margin:0 0 8px;color:#1b7a3e;font-weight:600">Saved.</p>' if picked else
                '<p style="margin:0 0 8px;color:#c8102e">Pick at least one resort, or unsubscribe below.</p>')
        self.reply(200, self._form(token, picked or found[1], note), "text/html")
