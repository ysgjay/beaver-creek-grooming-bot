"""Delivery channels. Each one is independent: a failure in one never blocks the others.

- Telegram: existing @bcskireport channel (Bot API over plain HTTPS).
- ntfy:     free push notifications to iPhone/Android, no carrier or SMS gateway.
            Subscribers install the ntfy app and follow the topic.
- Email:    Gmail SMTP with an app password; recipients from EMAIL_TO and/or a public
            Google Sheet of form sign-ups (any column containing an email address).
"""
import csv
import io
import logging
import re
import smtplib
from email.message import EmailMessage
from html import escape

from . import config
from .util import get, http

log = logging.getLogger(__name__)

TELEGRAM_CAPTION_LIMIT = 1024


def telegram(text, image=None):
    if not config.TELEGRAM_BOT_TOKEN:
        return "skipped (no BOT_TOKEN)"
    base = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
    chat = config.TELEGRAM_CHAT_ID
    if image and len(text) <= TELEGRAM_CAPTION_LIMIT:
        r = http().post(f"{base}/sendPhoto", data={"chat_id": chat, "caption": text},
                        files={"photo": ("grooming.jpg", image, "image/jpeg")}, timeout=60)
    else:
        if image:
            http().post(f"{base}/sendPhoto", data={"chat_id": chat},
                        files={"photo": ("grooming.jpg", image, "image/jpeg")}, timeout=60).raise_for_status()
        r = http().post(f"{base}/sendMessage", data={"chat_id": chat, "text": text,
                                                     "disable_web_page_preview": True}, timeout=30)
    r.raise_for_status()
    return "sent"


def ntfy(text, image=None, title="Beaver Creek grooming report", tags="ski", priority=3):
    if not config.NTFY_TOPIC:
        return "skipped (no NTFY_TOPIC)"
    url = f"{config.NTFY_SERVER.rstrip('/')}/{config.NTFY_TOPIC}"
    # Query params instead of headers so emoji/UTF-8 in the message survive.
    params = {"title": title, "message": text, "click": config.DASHBOARD_URL,
              "tags": tags, "priority": str(priority)}
    if image:
        r = http().put(url, params=params, data=image, headers={"Filename": "grooming.jpg"}, timeout=60)
    else:
        r = http().post(url, params=params, timeout=30)
    r.raise_for_status()
    return "sent"


_EMAIL = re.compile(r"[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}")


def sheet_recipients():
    if not config.GOOGLE_SHEET_ID:
        return []
    url = f"https://docs.google.com/spreadsheets/d/{config.GOOGLE_SHEET_ID}/export?format=csv"
    r = get(url)
    r.raise_for_status()
    found = []
    for row in csv.reader(io.StringIO(r.text)):
        for cell in row:
            found += _EMAIL.findall(cell)
    return found


def email(text, image=None, subject="Beaver Creek grooming report"):
    if not (config.GMAIL_USER and config.GMAIL_APP_PASSWORD):
        return "skipped (no GMAIL_USER/GMAIL_APP_PASSWORD)"
    try:
        sheet = sheet_recipients()
    except Exception as e:
        log.warning("Could not read sign-up sheet: %s", e)
        sheet = []
    recipients = sorted({r.lower() for r in config.EMAIL_TO + sheet})
    if not recipients:
        return "skipped (no recipients)"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_USER
    msg["To"] = config.GMAIL_USER
    msg["Bcc"] = ", ".join(recipients)
    msg.set_content(text)
    body = "<br>".join(escape(line) for line in text.splitlines())
    html = f'<div style="font-family:system-ui,sans-serif;font-size:15px;line-height:1.45">{body}</div>'
    if image:
        html += '<p><img src="cid:map" style="max-width:100%" alt="Grooming map"></p>'
    msg.add_alternative(html, subtype="html")
    if image:
        msg.get_payload()[1].add_related(image, "image", "jpeg", cid="<map>")
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=60) as s:
        s.starttls()
        s.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
        s.send_message(msg)
    return f"sent to {len(recipients)}"


CHANNELS = {"telegram": telegram, "ntfy": ntfy, "email": email}


def send_all(text, image=None, channels=None):
    results = {}
    for name, fn in CHANNELS.items():
        if channels and name not in channels:
            continue
        try:
            results[name] = fn(text, image)
        except Exception as e:
            log.exception("%s failed", name)
            results[name] = f"FAILED: {e}"
    return results
