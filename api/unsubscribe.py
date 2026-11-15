"""Unsubscribe.

GET  /api/unsubscribe?t=...   -> a page with one button (link scanners can't unsubscribe people)
POST /api/unsubscribe?t=...   -> unsubscribes. Also the RFC 8058 one-click target that
                                 Gmail and Apple Mail call from their own Unsubscribe button.
"""
from html import escape

from bcbot.web import Handler
from bcbot import db

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Unsubscribe · Snow Desk</title></head>
<body style="margin:0;background:#dcebfa;font:16px/1.5 -apple-system,'Segoe UI',Roboto,sans-serif;color:#0c2a4a">
<div style="max-width:420px;margin:12vh auto;background:#fff;border-radius:24px;padding:24px">{body}</div></body></html>"""


class handler(Handler):
    def do_GET(self):
        token = escape(self.query("t"))
        body = (f'<h1 style="margin:0 0 8px;font-size:22px">Stop the morning email?</h1>'
                f'<p style="margin:0 0 18px">You won\'t get the Beaver Creek report by email anymore. You can sign up again any time in the app.</p>'
                f'<form method="post" action="/api/unsubscribe?t={token}"><button style="font:600 16px inherit;background:#0a5bd3;color:#fff;border:0;border-radius:12px;padding:12px 18px;cursor:pointer">Unsubscribe</button></form>')
        self.reply(200, PAGE.format(body=body), "text/html")

    def do_POST(self):
        token = self.query("t")
        done = False
        if token:
            with db.connect() as conn:
                done = db.unsubscribe(conn, token)
        body = ('<h1 style="margin:0 0 8px;font-size:22px">You\'re unsubscribed</h1><p style="margin:0">No more morning emails. '
                '<a href="/" style="color:#0a5bd3">Open Snow Desk</a></p>') if done else \
               '<h1 style="margin:0 0 8px;font-size:22px">Link not recognized</h1><p style="margin:0">It may already be unsubscribed.</p>'
        self.reply(200, PAGE.format(body=body), "text/html")
