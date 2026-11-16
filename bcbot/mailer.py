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


# Frosted Snow (docs/BRAND.md), inlined because most mail apps strip <style>. Light mode only.
ICE, FROST, WHITE, INK, INK2 = "#dcebfa", "#f5f9fc", "#ffffff", "#0c2a4a", "#52677b"
BURGUNDY, BURGUNDY_TINT, LINE, QUIET = "#7b1e2e", "#f2e6e9", "#c3d3e0", "#365c7d"
SNOW, SNOW_LO, SNOW_HI = "#376f9b", (0xE5, 0xF1, 0xFA), (0x88, 0xB2, 0xD5)
SANS = "'IBM Plex Sans',-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
DISPLAY = "Outfit,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MONO = "'IBM Plex Mono',Menlo,Consolas,monospace"
CARD = f"background:{FROST};border:1px solid {WHITE};border-radius:20px;box-shadow:0 2px 8px rgba(12,42,74,.08)"
KICKER = f"margin:0 0 6px;font:600 11px/1.3 {MONO};letter-spacing:.05em;text-transform:uppercase;color:{INK2}"
BUTTON = (f"background:{BURGUNDY};color:#ffffff;text-decoration:none;padding:12px 18px;border-radius:12px;"
          f"font:600 15px/1.2 {SANS};display:inline-block")
LINK = f"color:{QUIET};text-decoration:underline"


def _site(path=""):
    return f"{config.DASHBOARD_URL.rstrip('/')}/{path.lstrip('/')}"


def send_confirmation(email, token, slugs=("beaver-creek",)):
    link = f"{config.DASHBOARD_URL.rstrip('/')}/api/confirm?t={token}"
    names = escape(_names(slugs))
    many = len(slugs) > 1
    html = _shell(_card(f"""
      {_brand_row()}
      <h1 style="margin:14px 0 8px;font:600 22px/1.25 {DISPLAY};color:{INK}">Confirm your {names} report{"s" if many else ""}</h1>
      <p style="margin:0 0 16px">Tap the button to get the grooming map, snow report and forecast by email every morning{", one email per resort" if many else ""}.</p>
      <p style="margin:0 0 20px"><a href="{link}" style="{BUTTON}">Confirm my email</a></p>
      <p style="margin:0;color:{INK2};font-size:13px">If you didn't ask for this, ignore this email and nothing will be sent.</p>"""))
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
            a = f"color:{BURGUNDY};text-decoration:underline"
            footer = (f'<p style="margin:4px 8px 0;color:{INK2};font-size:12px;line-height:1.5">You get this because you signed up at '
                      f'<a href="{config.DASHBOARD_URL}" style="{a}">snow.0xm.studio</a>. '
                      f'<a href="{resorts_url(token)}" style="{a}">Choose resorts</a> or '
                      f'<a href="{unsub}" style="{a}">unsubscribe</a> with one tap. Chair 0 is not affiliated with Vail Resorts.</p>')
            batch.append({
                "from": _from(), "to": [email], "subject": subject,
                "html": _shell(html_body + footer), "text": f"{text_body}\n\nChoose resorts: {resorts_url(token)}\nUnsubscribe: {unsub}",
                "headers": {"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
            })
        _post("/emails/batch", batch)
        sent += len(batch)
    return sent


def _shell(inner):
    """Ice page, one 640px column. Fonts load where the app allows it (Apple Mail); others fall back."""
    fonts = "".join(f"@font-face{{font-family:{fam};src:url('{_site('brand/fonts/' + f)}') format('woff2');font-weight:{w}}}"
                    for fam, f, w in [("Outfit", "outfit.woff2", "100 900"), ("'IBM Plex Sans'", "plex-sans.woff2", "100 700"),
                                      ("'IBM Plex Mono'", "plex-mono.woff2", "400")])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light only">
<style>{fonts}:root{{color-scheme:light only}}</style></head>
<body style="margin:0;padding:0;background:{ICE}">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" bgcolor="{ICE}" style="background:{ICE};background-image:radial-gradient(circle at 0 0,rgba(255,255,255,.75),rgba(255,255,255,0) 420px)"><tr><td align="center" style="padding:14px 10px 22px">
<div style="max-width:640px;margin:0 auto;text-align:left;font:15px/1.5 {SANS};color:{INK}">
{inner}
</div></td></tr></table></body></html>"""


def _card(inner, pad="16px", extra=""):
    return f'<div style="{CARD};padding:{pad};margin:0 0 10px;{extra}">{inner}</div>'


def _brand_row():
    return (f'<table role="presentation" cellspacing="0" cellpadding="0"><tr>'
            f'<td style="vertical-align:middle"><img src="{_site("brand/frosted-logo-email.png")}" width="44" height="44" alt="" style="display:block;border:0"></td>'
            f'<td style="vertical-align:middle;padding-left:8px;font:600 14px/1.2 {DISPLAY};color:{INK}">Chair 0<br>'
            f'<span style="font:400 12px/1.3 {SANS};color:{INK2}">Snow Desk</span></td></tr></table>')


def _inch(x):
    return "–" if x is None else (f'{x:.0f}"' if x >= 1 or x == 0 else f'{x:.1f}"')


def _ramp(x, full=6.0):
    """Snow amount to the ice/blue data ramp (never burgundy); dark labels throughout."""
    if x is None or x < 0.1:
        return FROST
    t = min(1.0, x / full)
    return "#%02x%02x%02x" % tuple(round(a + (b - a) * t) for a, b in zip(SNOW_LO, SNOW_HI))


def _hour(iso):
    from datetime import datetime
    h = datetime.fromisoformat(iso).hour
    return f"{(h % 12) or 12}{'a' if h < 12 else 'p'}"


def _clock(iso):
    return _hour(iso).replace("a", " AM").replace("p", " PM")


def ski_hours(day):
    """The forecast hours from first chair to last (8a-4p) that the report has, else its first nine."""
    hours = (day.get("hourly") or {}).get("hours") or []
    lift = [h for h in hours if 8 <= int(h["time"][11:13]) <= 16]
    return lift if len(lift) >= 4 else hours[:9]


def groomed_runs(runs):
    """Every groomed run once, in report order (groomers of the day first)."""
    seen, out = set(), []
    lists = [runs.get("groomers_of_the_day"), runs.get("overnight"), runs.get("morning"), runs.get("groomed")]
    lists += list((runs.get("areas") or {}).values())
    for names in lists:
        for n in names or []:
            if n not in seen:
                seen.add(n)
                out.append(n)
    return out


def preheader(day):
    """The inbox preview line: groomers of the day, morning weather, report time."""
    runs = (day.get("grooming") or {}).get("runs") or {}
    rs = day.get("resort") or {}
    bits = []
    if runs.get("groomers_of_the_day"):
        bits.append("Groomers of the day: " + ", ".join(runs["groomers_of_the_day"][:4]) + ".")
    hrs = ski_hours(day)
    if hrs:
        first, peak = hrs[0], max(hrs, key=lambda h: h.get("gust") or 0)
        bits.append(f"{first['temp']}°F at {_clock(first['time'])}, feels {first['feels']}°.")
        if peak.get("gust"):
            bits.append(f"Gusts to {peak['gust']} mph by {_clock(peak['time'])}.")
    if rs.get("updated_time"):
        bits.append(f"Snow report {rs['updated_time']}.")
    return " ".join(bits)


def daily_html(day, map_url):
    """The morning report as an email: the Day Ticket layout (inline styles only; email clients strip CSS)."""
    from datetime import date as _date
    fc = day.get("forecast") or {}
    rs = day.get("resort") or {}
    obs = day.get("observed") or {}
    g = day.get("grooming") or {}
    runs = g.get("runs") or {}
    r24 = rs.get("last_24h_in", obs.get("snow_in"))
    d = _date.fromisoformat(day["date"])
    app = report.app_url(day)
    sub = f"margin:2px 0 0;color:{INK2};font-size:13px"

    # Hidden inbox preview text, padded so mail apps don't pull body text into it.
    pre = escape(preheader(day))
    out = (f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:{ICE}">'
           f'{pre}{"&#847;&zwnj;&nbsp;" * 60}</div>')

    # 1. Day ticket: resort and report facts, with a dashed stub for the day and new snow.
    facts = []
    if rs.get("updated_time"):
        facts.append(f"Snow report {escape(rs['updated_time'])}")
    if rs.get("base_in") is not None:
        facts.append(f'base {_inch(rs["base_in"])}')
    more = []
    if rs.get("last_7d_in") is not None:
        more.append(f'7 days {_inch(rs["last_7d_in"])}')
    if rs.get("season_in") is not None:
        more.append(f'season {_inch(rs["season_in"])}')
    note = ""
    if day.get("powder"):
        note = (f'<p style="margin:10px 0 0;padding:6px 10px;border-left:3px solid {BURGUNDY};background:{BURGUNDY_TINT};'
                f'border-radius:6px;font-size:13px">{escape(day["powder"].lstrip("❄️ ").strip())}</p>')
    elif day.get("preseason"):
        note = f'<p style="{sub}">Opens {report.mmdd(config.OPENING_DAY)}</p>'
    out += _card(f"""<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
      <td style="padding:14px 14px 14px 16px;vertical-align:top">{_brand_row()}
        <h1 style="margin:12px 0 0;font:600 23px/1.2 {DISPLAY};color:{INK}">{escape(report.resort_name(day))}</h1>
        {f'<p style="{sub}">{" · ".join(facts)}</p>' if facts else ''}{f'<p style="{sub}">{" · ".join(more)}</p>' if more else ''}{note}</td>
      <td width="104" style="width:104px;border-left:2px dashed {LINE};text-align:center;padding:14px 6px;background:{WHITE};vertical-align:middle">
        <div style="font:400 12px/1.2 {MONO};color:{INK2}">{d.strftime('%a')}</div>
        <div style="font:600 23px/1.2 {DISPLAY};color:{INK}">{report.mmdd(d)}</div>
        <div style="margin-top:10px;font:600 30px/1 {DISPLAY};color:{SNOW}">{_inch(r24)}</div>
        <div style="font-size:11px;color:{INK2}">new, 24 hr</div></td></tr></table>""", pad="0", extra="overflow:hidden")

    # 2. Grooming: the full-resolution map every day it exists, then groomers of the day.
    all_runs = groomed_runs(runs)
    chips = "".join(f'<span style="display:inline-block;margin:0 5px 5px 0;padding:3px 10px;border-radius:8px;background:{BURGUNDY_TINT};'
                    f'border:1px solid #e3c9cf;color:{BURGUNDY};font-weight:600;font-size:14px">{escape(n)}</span>'
                    for n in runs.get("groomers_of_the_day") or [])
    counts = []
    if all_runs:
        counts.append(f"{len(all_runs)} groomed")
    if runs.get("overnight") and runs.get("morning"):
        counts.append(f"{len(runs['overnight'])} overnight, {len(runs['morning'])} this morning")
    if map_url:
        stamp = f"Grooming map · printed {escape(report.map_date(runs['map_date']))}" if runs.get("map_date") else "Grooming map"
        if not g.get("new_map", True):
            stamp += " · no new map yet today"
        body = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 8px"><tr>'
                f'<td style="padding:4px 4px 0"><p style="{KICKER};margin:0">{stamp}</p></td>'
                f'<td align="right" style="padding:4px 4px 0;font-size:13px"><a href="{map_url}" style="{LINK}">Full size</a></td></tr></table>'
                f'<a href="{map_url}"><img src="{map_url}" alt="Grooming map for {escape(report.resort_name(day))}" width="616" '
                f'style="display:block;width:100%;max-width:616px;height:auto;border:1px solid {LINE};border-radius:12px"></a>')
        rest = ""
        if chips:
            rest += f'<p style="{KICKER};margin-top:12px">Groomers of the day</p>{chips}'
        if counts:
            rest += f'<p style="{sub}">{" · ".join(counts)} · <a href="{app}" style="{LINK}">full list</a></p>'
        out += _card(body + (f'<div style="padding:0 4px 4px">{rest}</div>' if rest else ""), pad="10px")
    elif all_runs or chips:
        # Resorts without a Lumiplan map: the groomed list takes the map's place.
        sections = [("Groomers of the day", runs.get("groomers_of_the_day"), True), ("Groomed overnight", runs.get("overnight"), False),
                    ("Morning grooming", runs.get("morning"), False)]
        sections += [(a, l, False) for a, l in (runs.get("areas") or {"Groomed": runs.get("groomed")}).items()]
        body = ""
        for title, names, feat in sections:
            if names:
                style = (f"background:{BURGUNDY_TINT};border:1px solid #e3c9cf;color:{BURGUNDY};font-weight:600" if feat
                         else f"background:{WHITE};border:1px solid {LINE}")
                body += (f'<p style="{KICKER};margin-top:10px">{escape(title)}</p>'
                         + "".join(f'<span style="display:inline-block;margin:0 5px 5px 0;padding:3px 10px;border-radius:8px;{style};font-size:14px">{escape(n)}</span>' for n in names))
        out += _card(body)

    # 3. First chair to last: temperature, feels like and gusts by hour (forecast).
    hrs = ski_hours(day)
    if hrs:
        gusts = [h.get("gust") or h.get("wind") or 0 for h in hrs]
        lo = min(gusts)
        td = "padding:1px;text-align:center"
        r1 = "".join(f'<td style="{td};font:400 11px {MONO};color:{INK2};padding-bottom:4px">{_hour(h["time"])}</td>' for h in hrs)
        r2 = "".join(f'<td style="{td}"><div style="font:600 13px {MONO};color:{INK}">{h["temp"]}°</div>'
                     f'<div style="font-size:10px;color:{INK2}">{h["feels"]}°</div></td>' for h in hrs)
        r3 = "".join(f'<td style="{td};padding-top:4px"><div style="background:{_ramp(max(v - lo, 1), 18)};border-radius:6px;padding:4px 0;'
                     f'font:600 12px {MONO};color:{INK}">{v}</div></td>' for v in gusts)
        peak = max(hrs, key=lambda h: h.get("gust") or 0)
        cap = f"Temp, feels like, then gusts in mph." + (f" Peak gust {peak['gust']} mph at {_clock(peak['time'])}." if peak.get("gust") else "")
        out += _card(f'<p style="{KICKER}">First chair to last · forecast</p>'
                     f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="table-layout:fixed"><tr>{r1}</tr><tr>{r2}</tr><tr>{r3}</tr></table>'
                     f'<p style="{sub};margin-top:6px">{cap}</p>')

    # 4. Snow forecast: ten days, weekday over MM/DD, likely range under each snowy day.
    cells = ""
    for f in (fc.get("days") or [])[:10]:
        dd = _date.fromisoformat(f["date"])
        s = f["snow"]
        val = "–" if s < 0.1 else (round(s) if s >= 1 else round(s, 1))
        rng = (f'{f["low"]:g}–{f["high"]:g}' if s >= 0.1 and f.get("low") is not None and f.get("high") is not None
               and f["high"] > f["low"] else "&nbsp;")
        cells += (f'<td style="padding:1px;text-align:center"><div style="background:{_ramp(s)};border:1px solid #dce8f2;border-radius:7px;'
                  f'padding:7px 0;font:600 13px {MONO};color:{INK}">{val}</div>'
                  f'<div style="font-size:10px;line-height:1.25;color:{INK2};margin-top:3px">{dd.strftime("%a")}<br>{dd.month}/{dd.day}</div>'
                  f'<div style="font-size:10px;color:{SNOW}">{rng}</div></td>')
    if cells:
        lo, hi = (fc.get("next_1_5_range") or [None, None])[:2]
        head = (f'Next 5 days <b>{_inch(lo).rstrip(chr(34))} to {_inch(hi)}</b>, most likely {_inch(fc.get("next_1_5"))}'
                if lo is not None and hi is not None and hi > lo else f'Next 5 days <b>{_inch(fc.get("next_1_5"))}</b>')
        head += f' · days 6–10 {_inch(fc.get("next_6_10"))}' if fc.get("next_6_10") is not None else ""
        out += _card(f'<p style="{KICKER}">Snow forecast · likely range under each day</p>'
                     f'<p style="margin:0 0 8px;font-size:14px">{head}</p>'
                     f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="table-layout:fixed"><tr>{cells}</tr></table>'
                     f'<p style="margin:14px 0 0"><a href="{app}" style="{BUTTON}">See the full report</a>'
                     f'&nbsp;&nbsp;<a href="{app}" style="{LINK};font-size:14px">Cams</a> · '
                     f'<a href="{app}#forecast" style="{LINK};font-size:14px">Forecast</a></p>')
    else:
        out += _card(f'<p style="margin:0"><a href="{app}" style="{BUTTON}">See the full report</a></p>')
    return out
