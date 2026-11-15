"""Email through Resend, from report@snow.0xm.studio (its own subdomain, own reputation)."""
import os
from datetime import date as _d
from html import escape

from . import config, report
from .util import http

API = "https://api.resend.com"
BATCH_MAX = 100


def _from():
    return os.environ.get("EMAIL_FROM", "Snow Desk <report@snow.0xm.studio>")


def _post(path, payload):
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        raise RuntimeError("RESEND_API_KEY is not set")
    r = http().post(API + path, json=payload, timeout=30,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if not r.ok:
        raise RuntimeError(f"Resend {path} {r.status_code}: {r.text[:300]}")
    return r.json()


def unsubscribe_url(token):
    return f"{config.DASHBOARD_URL.rstrip('/')}/api/unsubscribe?t={token}"


def resorts_url(token):
    return f"{config.DASHBOARD_URL.rstrip('/')}/api/resorts?t={token}"


def _names(slugs):
    from . import resorts
    names = [resorts.get(s)["name"] for s in slugs if s in resorts.RESORTS] or ["Beaver Creek"]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def send_confirmation(email, token, slugs=("beaver-creek",)):
    link = f"{config.DASHBOARD_URL.rstrip('/')}/api/confirm?t={token}"
    names = escape(_names(slugs))
    many = len(slugs) > 1
    html = _shell(f"""
      <h1 style="margin:0 0 8px;font-size:22px">Confirm your {names} report{"s" if many else ""}</h1>
      <p style="margin:0 0 16px">Tap the button to get the grooming report, snow forecast and cams by email every morning{", one email per resort" if many else ""}.</p>
      <p style="margin:0 0 20px"><a href="{link}" style="background:#0a5bd3;color:#ffffff;text-decoration:none;padding:12px 18px;border-radius:12px;font-weight:600;display:inline-block">Confirm my email</a></p>
      <p style="margin:0;color:#4a6382;font-size:13px">If you didn't ask for this, ignore this email and nothing will be sent.</p>""")
    return _post("/emails", {
        "from": _from(), "to": [email], "subject": f"Confirm your {_names(slugs)} morning report{'s' if many else ''}",
        "html": html, "text": f"Confirm your {_names(slugs)} morning report{'s' if many else ''}: {link}\n\nIf you didn't ask for this, ignore this email.",
    })


def send_daily(recipients, subject, html_body, text_body):
    """recipients: [(email, token)]. One email each, so each has its own unsubscribe link."""
    sent = 0
    for i in range(0, len(recipients), BATCH_MAX):
        batch = []
        for email, token in recipients[i:i + BATCH_MAX]:
            unsub = unsubscribe_url(token)
            footer = (f'<p style="margin:20px 0 0;color:#4a6382;font-size:12px">You get this because you signed up at '
                      f'<a href="{config.DASHBOARD_URL}" style="color:#0a5bd3">snow.0xm.studio</a>. '
                      f'<a href="{resorts_url(token)}" style="color:#0a5bd3">Choose resorts</a> or '
                      f'<a href="{unsub}" style="color:#0a5bd3">unsubscribe</a> with one tap.</p>')
            batch.append({
                "from": _from(), "to": [email], "subject": subject,
                "html": _shell(html_body + footer), "text": f"{text_body}\n\nChoose resorts: {resorts_url(token)}\nUnsubscribe: {unsub}",
                "headers": {"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
            })
        _post("/emails/batch", batch)
        sent += len(batch)
    return sent


def _shell(inner):
    return f"""<!doctype html><html><body style="margin:0;background:#dcebfa;padding:16px 0">
<div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:20px;padding:20px;font:15px/1.5 -apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0c2a4a">
{inner}
</div></body></html>"""


def daily_html(day, map_url):
    """The morning report as an email body (inline styles only; email clients strip CSS)."""
    fc = day.get("forecast") or {}
    rs = day.get("resort") or {}
    obs = day.get("observed") or {}
    runs = (day.get("grooming") or {}).get("runs") or {}
    r24 = rs.get("last_24h_in", obs.get("snow_in"))

    def inch(x):
        return "–" if x is None else (f'{x:.0f}"' if x >= 1 or x == 0 else f'{x:.1f}"')

    def chips(title, names):
        if not names:
            return ""
        items = "".join(f'<span style="display:inline-block;margin:0 6px 6px 0;padding:3px 10px;border-radius:8px;background:#eef5fd">{escape(n)}</span>' for n in names)
        return f'<p style="margin:10px 0 4px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#4a6382">{title}</p>{items}'

    cells = ""
    for d in (fc.get("days") or [])[:10]:
        t = min(1, d["snow"] / 10)
        bg = "#eef5fd" if d["snow"] < 0.1 else f"rgba(10,91,211,{0.16 + t * 0.84:.2f})"
        ink = "#ffffff" if t > 0.5 else "#0c2a4a"
        dd = _d.fromisoformat(d["date"])
        cells += (f'<td style="padding:2px;text-align:center"><div style="background:{bg};color:{ink};border-radius:7px;padding:8px 0;font-weight:600;font-family:Menlo,monospace;font-size:13px">'
                  f'{"–" if d["snow"] < 0.1 else (round(d["snow"]) if d["snow"] >= 1 else round(d["snow"], 1))}</div>'
                  f'<div style="font-size:10px;color:#4a6382;margin-top:3px">{dd.month}/{dd.day}</div></td>')
    hours = (day.get("hourly") or {}).get("hours", [])
    now = hours[0] if hours else None
    weather = f"{now['temp']}°F, feels {now['feels']}°, {now['dir']} {now['wind']} mph" if now else ""
    return f"""
      <h1 style="margin:0;font-size:22px">{escape(report.resort_name(day))} · {report.pretty_date(day['date'])}</h1>
      <p style="margin:2px 0 14px;color:#4a6382">New snow {inch(r24)} · Base {inch(rs.get('base_in'))} · {escape(weather)}{f" · Snow report {escape(rs['updated_time'])}" if rs.get('updated_time') else ""}</p>
      {f'<a href="{report.app_url(day)}"><img src="{map_url}" alt="Grooming map" width="520" style="width:100%;max-width:520px;border-radius:12px;display:block"></a>' if map_url else ''}
      {f'<p style="margin:6px 0 0;color:#4a6382;font-size:13px">Map dated {escape(report.map_date(runs["map_date"]))}{"" if (day.get("grooming") or {}).get("new_map") else " · no new map posted today"}</p>' if runs.get("map_date") else ''}
      {chips("Groomers of the day", runs.get("groomers_of_the_day"))}{chips("Groomed overnight", runs.get("overnight"))}{chips("Morning grooming", runs.get("morning"))}{"".join(chips(escape(a), l) for a, l in (runs.get("areas") or {"Groomed": runs.get("groomed")}).items())}
      <p style="margin:16px 0 6px;font-weight:600">Snow forecast: {inch(fc.get('next_1_5'))} next 5 days, {inch(fc.get('next_6_10'))} days 6–10</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="table-layout:fixed"><tr>{cells}</tr></table>
      <p style="margin:18px 0 0"><a href="{report.app_url(day)}" style="background:#0a5bd3;color:#ffffff;text-decoration:none;padding:10px 16px;border-radius:12px;font-weight:600;display:inline-block">Open Snow Desk</a></p>"""
