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
      <p style="margin:0 0 16px">Tap the button to get the grooming map, snow report and forecast by email every morning{", all your resorts in one email by 6:30 AM MT" if many else ""}.</p>
      <p style="margin:0 0 20px"><a href="{link}" style="{BUTTON}">Confirm my email</a></p>
      <p style="margin:0;color:{INK2};font-size:13px">If you didn't ask for this, ignore this email and nothing will be sent.</p>"""))
    return _post("/emails", {
        "from": _from(), "to": [email], "subject": f"Confirm your {_names(slugs)} morning report{'s' if many else ''}",
        "html": html, "text": f"Confirm your {_names(slugs)} morning report{'s' if many else ''}: {link}\n\nIf you didn't ask for this, ignore this email.",
    })


def send_resort_update(email, token, slugs):
    """An active subscriber submitted the sign-up form with a different set of resorts."""
    from urllib.parse import quote
    link = f"{resorts_url(token)}&pick={quote(','.join(slugs))}"
    names = escape(_names(slugs))
    html = _shell(_card(f"""
      {_brand_row()}
      <h1 style="margin:14px 0 8px;font:600 22px/1.25 {DISPLAY};color:{INK}">Update your morning emails</h1>
      <p style="margin:0 0 6px">You're already subscribed. Someone, probably you, asked for these resorts:</p>
      <p style="margin:0 0 16px;font-weight:600">{names}</p>
      <p style="margin:0 0 20px"><a href="{link}" style="{BUTTON}">Review and save</a></p>
      <p style="margin:0;color:{INK2};font-size:13px">Nothing changes until you tap Save on that page. If you didn't ask for this, ignore this email.</p>"""))
    return _post("/emails", {
        "from": _from(), "to": [email], "subject": "Update your morning report resorts",
        "html": html, "text": f"You're already subscribed. To get {_names(slugs)}, review and save: {link}\n\nNothing changes until you tap Save. If you didn't ask for this, ignore this email.",
    })


def _footer(token):
    unsub = unsubscribe_url(token)
    a = f"color:{BURGUNDY};text-decoration:underline"
    return (f'<p style="margin:4px 8px 0;color:{INK2};font-size:12px;line-height:1.5">You get this because you signed up at '
            f'<a href="{config.DASHBOARD_URL}" style="{a}">snow.0xm.studio</a>. '
            f'<a href="{resorts_url(token)}" style="{a}">Choose resorts</a> or '
            f'<a href="{unsub}" style="{a}">unsubscribe</a> with one tap. Chair 0 is not affiliated with Vail Resorts or any resort. '
            f'Forecast data by Open-Meteo.com (CC BY 4.0), NWS and NRCS SNOTEL.</p>')


def _message(email, token, subject, html_body, text_body):
    unsub = unsubscribe_url(token)
    return {
        "from": _from(), "to": [email], "subject": subject,
        "html": _shell(html_body + _footer(token)), "text": f"{text_body}\n\nChoose resorts: {resorts_url(token)}\nUnsubscribe: {unsub}",
        "headers": {"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
    }


def send_personal(messages):
    """messages: [(email, token, subject, html_body, text_body)], each its own content."""
    sent = 0
    for i in range(0, len(messages), BATCH_MAX):
        batch = [_message(*m) for m in messages[i:i + BATCH_MAX]]
        _post("/emails/batch", batch)
        sent += len(batch)
    return sent


def send_daily(recipients, subject, html_body, text_body):
    """recipients: [(email, token)]. One email each, so each has its own unsubscribe link."""
    return send_personal([(email, token, subject, html_body, text_body) for email, token in recipients])


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
        lab = (f"width:46px;padding:1px 6px 1px 0;text-align:left;vertical-align:middle;"
               f"font:600 10px/1.2 {MONO};letter-spacing:.03em;text-transform:uppercase;color:{INK2}")
        r1 = f'<td style="{lab}">&nbsp;</td>' + "".join(
            f'<td style="{td};font:400 11px {MONO};color:{INK2};padding-bottom:4px">{_hour(h["time"])}</td>' for h in hrs)
        r2 = f'<td style="{lab}">Temp</td>' + "".join(
            f'<td style="{td};font:600 13px {MONO};color:{INK}">{h["temp"]}°</td>' for h in hrs)
        r3 = f'<td style="{lab}">Feels</td>' + "".join(
            f'<td style="{td};font:400 11px {MONO};color:{INK2};padding-bottom:4px">{h["feels"]}°</td>' for h in hrs)
        r4 = f'<td style="{lab}">Gust</td>' + "".join(
            f'<td style="{td};padding-top:2px"><div style="background:{_ramp(max(v - lo, 1), 18)};border-radius:6px;padding:4px 0;'
            f'font:600 12px {MONO};color:{INK}">{v}</div></td>' for v in gusts)
        peak = max(hrs, key=lambda h: h.get("gust") or 0)
        cap = "Hourly forecast at the resort: temperature and feels like in °F, gusts in mph." + (f" Peak gust {peak['gust']} mph at {_clock(peak['time'])}." if peak.get("gust") else "")
        out += _card(f'<p style="{KICKER}">First chair to last · forecast</p>'
                     f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="table-layout:fixed">'
                     f'<tr>{r1}</tr><tr>{r2}</tr><tr>{r3}</tr><tr>{r4}</tr></table>'
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
        head += f' · next 7 days <b>{_inch(next_7(fc))}</b>' if next_7(fc) is not None else ""
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


# ---------- combined email: one per subscriber with two or more resorts ----------

def new_snow(day):
    rs = day.get("resort") or {}
    return rs.get("last_24h_in", (day.get("observed") or {}).get("snow_in"))


def _resort_name(slug, day=None):
    return (day or {}).get("resort_name") or resorts_get_name(slug)


def resorts_get_name(slug):
    from . import resorts
    return resorts.get(slug)["name"] if slug in resorts.RESORTS else slug


def _peak_gust(day):
    return max([h.get("gust") or 0 for h in ski_hours(day)] or [0]) or None


def _fact(day):
    """The one thing that leads for a resort in the subject line."""
    s = new_snow(day)
    n = len(groomed_runs((day.get("grooming") or {}).get("runs") or {}))
    if s is not None and s >= 0.5:
        return f'{_inch(s)} new'
    if n:
        return f"{n} groomed"
    return "report in"


def digest_subject(picked, pending):
    """'Vail 2" new, Copper Mountain 14 groomed, Alta pending'."""
    parts = [f"{_resort_name(s, d)} {_fact(d)}" for s, d in picked]
    parts += [f"{resorts_get_name(s)} pending" for s in pending]
    head = ", ".join(parts[:3]) + (f", +{len(parts) - 3} more" if len(parts) > 3 else "")
    return head


def digest_preheader(picked, pending):
    bits = []
    for s, d in picked[:3]:
        gotd = ((d.get("grooming") or {}).get("runs") or {}).get("groomers_of_the_day") or []
        if gotd:
            bits.append(f"{_resort_name(s, d)}: {', '.join(gotd[:2])}.")
    bits.append(f"{len(picked)} of {len(picked) + len(pending)} reports in.")
    return " ".join(bits)


def digest_text(picked, pending):
    lines = []
    for s, d in picked:
        rs = d.get("resort") or {}
        runs = (d.get("grooming") or {}).get("runs") or {}
        fc = d.get("forecast") or {}
        lines.append(f"{_resort_name(s, d)}: new {_inch(new_snow(d))}, base {_inch(rs.get('base_in'))}, "
                     f"{len(groomed_runs(runs))} groomed, next 5 days {_inch(fc.get('next_1_5'))}, "
                     f"next 7 days {_inch(next_7(fc))}")
        if runs.get("groomers_of_the_day"):
            lines.append("  Groomers of the day: " + ", ".join(runs["groomers_of_the_day"]))
        lines.append("  Full report: " + report.app_url(d))
    for s in pending:
        lines.append(f"{resorts_get_name(s)}: report pending")
    return "\n".join(lines)


def digest_html(picked, pending, now, radar_url=None, maps=False, token=None):
    """Departure-board summary: one row per resort (sorted by new snow), a short card per
    resort with its groomers of the day and links, then the 5-day outlook side by side."""
    from datetime import date as _date
    sub = f"margin:2px 0 0;color:{INK2};font-size:13px"
    total = len(picked) + len(pending)
    pre = escape(digest_preheader(picked, pending))
    out = (f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:{ICE}">'
           f'{pre}{"&#847;&zwnj;&nbsp;" * 60}</div>')
    d0 = _date.fromisoformat(picked[0][1]["date"])

    th = f"padding:0 0 6px;font:600 10px/1.2 {MONO};letter-spacing:.05em;text-transform:uppercase;color:{INK2}"
    rows = (f'<tr><td style="{th}">Resort</td><td style="{th};text-align:center">New</td><td style="{th};text-align:center">Base</td>'
            f'<td style="{th};text-align:center">Temp</td><td style="{th};text-align:right">Groomed</td></tr>')
    cell = f"border-top:1px solid {LINE};padding:8px 0;vertical-align:middle"
    for s, d in picked:
        rs = d.get("resort") or {}
        hrs = ski_hours(d)
        first = hrs[0] if hrs else None
        gust = _peak_gust(d)
        small = " · ".join(x for x in [f"report {escape(rs['updated_time'])}" if rs.get("updated_time") else "",
                                        f"gusts {gust} mph" if gust else ""] if x)
        snow = new_snow(d)
        temp = f"{first['temp']}°" if first and first.get("temp") is not None else "–"
        small_div = f'<div style="color:{INK2};font-size:11px">{small}</div>' if small else ""
        rows += (f'<tr><td style="{cell}"><a href="{report.app_url(d)}" style="color:{INK};text-decoration:none;font-weight:600">{escape(_resort_name(s, d))}</a>'
                 f'{small_div}</td>'
                 f'<td style="{cell};text-align:center"><span style="display:inline-block;min-width:36px;padding:5px 0;border-radius:7px;'
                 f'background:{_ramp(snow)};border:1px solid #dce8f2;font:700 13px {MONO};color:{INK}">{_inch(snow)}</span></td>'
                 f'<td style="{cell};text-align:center;font:400 13px {MONO}">{_inch(rs.get("base_in"))}</td>'
                 f'<td style="{cell};text-align:center;font:400 13px {MONO}">{temp}</td>'
                 f'<td style="{cell};text-align:right;font:400 13px {MONO}">{len(groomed_runs((d.get("grooming") or {}).get("runs") or {})) or "–"}</td></tr>')
    for s in pending:
        rows += (f'<tr><td style="{cell};color:{INK2}"><b>{escape(resorts_get_name(s))}</b>'
                 f'<div style="font-size:11px">not posted by {DIGEST_CUTOFF_LABEL}</div></td>'
                 f'<td colspan="4" style="{cell};text-align:right"><span style="display:inline-block;padding:2px 8px;border-radius:99px;'
                 f'background:#e8eef3;color:{INK2};font:600 10.5px {MONO};letter-spacing:.04em;text-transform:uppercase">Report pending</span></td></tr>')
    out += _card(f"""{_brand_row()}
      <h1 style="margin:12px 0 0;font:600 23px/1.2 {DISPLAY};color:{INK}">Your mountains</h1>
      <p style="{sub}">{d0.strftime('%a')} {report.mmdd(d0)} · {len(picked)} of {total} reports in · sorted by new snow</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:10px;font-size:13px">{rows}</table>""")

    for s, d in picked:
        runs = (d.get("grooming") or {}).get("runs") or {}
        g = d.get("grooming") or {}
        fc = d.get("forecast") or {}
        chips = "".join(f'<span style="display:inline-block;margin:0 5px 5px 0;padding:3px 10px;border-radius:8px;background:{BURGUNDY_TINT};'
                        f'border:1px solid #e3c9cf;color:{BURGUNDY};font-weight:600;font-size:13px">{escape(n)}</span>'
                        for n in (runs.get("groomers_of_the_day") or [])[:5])
        facts = []
        n = len(groomed_runs(runs))
        if n:
            facts.append(f"{n} groomed")
        elif g.get("image") and not g.get("new_map", True):
            facts.append("no new grooming map yet")
        if fc.get("next_1_5") is not None:
            facts.append(f'next 5 days {_inch(fc["next_1_5"])}')
        if next_7(fc) is not None:
            facts.append(f'next 7 days {_inch(next_7(fc))}')
        links = [f'<a href="{report.app_url(d)}" style="{LINK}">Full report</a>']
        if g.get("image"):
            links.append(f'<a href="{_site(g["image"])}" style="{LINK}">Grooming map</a>')
        img = ""
        if maps and g.get("image"):
            img = (f'<a href="{_site(g["image"])}"><img src="{_site(g["image"])}" alt="Grooming map for {escape(_resort_name(s, d))}" width="608" '
                   f'style="display:block;width:100%;max-width:608px;height:auto;margin-top:10px;border:1px solid {LINE};border-radius:12px"></a>')
        out += _card(f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>'
                     f'<td style="font:600 16px/1.3 {DISPLAY};color:{INK}">{escape(_resort_name(s, d))}</td>'
                     f'<td align="right" style="font-size:13px">{" · ".join(links)}</td></tr></table>'
                     + (f'<div style="margin-top:8px">{chips}</div>' if chips else "")
                     + (f'<p style="{sub}">{" · ".join(facts)}</p>' if facts else "") + img, pad="12px 16px")

    if radar_url:
        out += _card(f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 8px"><tr>'
                     f'<td style="padding:4px 4px 0"><p style="{KICKER};margin:0">Radar · Colorado and Utah · {_clock_now(now)}</p></td>'
                     f'<td align="right" style="padding:4px 4px 0;font-size:13px"><a href="{_site()}" style="{LINK}">Live radar</a></td></tr></table>'
                     f'<a href="{_site()}"><img src="{radar_url}" alt="Weather radar over Colorado and Utah" width="616" '
                     f'style="display:block;width:100%;max-width:616px;height:auto;border:1px solid {LINE};border-radius:12px"></a>'
                     f'<p style="{sub};margin:6px 4px 0">Darker blue is heavier precipitation. Dots are the resorts. NOAA radar via Iowa State Mesonet. Map © OpenStreetMap contributors.</p>',
                     pad="10px")

    bars = ""
    vals = [(s, d, (d.get("forecast") or {}).get("next_1_5"), next_7(d.get("forecast") or {})) for s, d in picked]
    top = max([max(v5 or 0, v7 or 0) for _, _, v5, v7 in vals] + [1])
    for s, d, v5, v7 in vals:
        w = 4 if not v7 else max(4, round(100 * v7 / top))
        bars += (f'<tr><td style="padding:3px 8px 3px 0;width:36%;font-size:13px">{escape(_resort_name(s, d))}</td>'
                 f'<td style="padding:3px 0"><div style="height:14px;width:{w}%;background:{SNOW_HEAT};border-radius:4px"></div></td>'
                 f'<td style="padding:3px 0 3px 8px;width:44px;text-align:right;font:400 13px {MONO}">{_inch(v5)}</td>'
                 f'<td style="padding:3px 0 3px 8px;width:44px;text-align:right;font:600 13px {MONO}">{_inch(v7)}</td></tr>')
    th = f'padding:0 0 4px 8px;text-align:right;font:600 11px {MONO};color:{INK2};letter-spacing:.06em'
    out += _card(f'<p style="{KICKER}">Snow forecast · next 5 and 7 days</p>'
                 f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">'
                 f'<tr><td></td><td></td><td style="{th}">5 DAY</td><td style="{th}">7 DAY</td></tr>{bars}</table>'
                 f'<p style="margin:14px 0 0"><a href="{_site("#forecast")}" style="{BUTTON}">See every forecast</a></p>')
    if token and not maps and any((d.get("grooming") or {}).get("image") for _, d in picked):
        out += (f'<p style="margin:0 8px 6px;color:{INK2};font-size:13px">Want grooming maps in this email? '
                f'<a href="{resorts_url(token)}" style="{LINK}">Turn them on</a></p>')
    return out


def next_7(fc):
    """Forecast snow over the next 7 days. Older saved forecasts lack next_1_7, so sum the days."""
    if fc.get("next_1_7") is not None:
        return fc["next_1_7"]
    days = fc.get("days") or []
    if len(days) < 7:
        return None
    return round(sum(x.get("snow") or 0 for x in days[:7]), 1)


def _clock_now(now):
    h = now.hour
    return f"{(h % 12) or 12}:{now.minute:02d} {'AM' if h < 12 else 'PM'} MT"


SNOW_HEAT = "#88b2d5"
DIGEST_CUTOFF_LABEL = "6:30 AM"
