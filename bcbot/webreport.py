"""The morning report as a web page (the public /resorts pages).

Same numbers and Day Ticket look as the email (mailer.daily_html), but built for the web: real
section headings, groomed runs as plain lists, a full-width grooming map that opens full size,
a semantic hourly table, and a wider two-column layout on desktop. The email stays as it is.
"""
from datetime import date
from html import escape

from . import mailer, report
from .mailer import DISPLAY, MONO

CSS = f"""
.wrap.wide{{max-width:1040px}}
.wrap.wide .lead,.wrap.wide .cta{{max-width:760px}}
.rp .card{{background:var(--paper);border:1px solid var(--edge);border-radius:20px;box-shadow:var(--shadow);padding:16px;margin:0 0 14px}}
.rp h2{{margin:0 0 10px}}
.rp .kick{{margin:0 0 6px;font:600 11px/1.3 {MONO};letter-spacing:.05em;text-transform:uppercase;color:var(--ink2)}}
.rp .sub{{margin:6px 0 0;color:var(--ink2);font-size:14px}}
.ticket{{display:flex;padding:0!important;overflow:hidden}}
.ticket .tk-main{{flex:1;padding:16px}}
.ticket .tk-stub{{width:112px;flex:none;border-left:2px dashed var(--line);background:var(--surface);text-align:center;padding:16px 6px;display:flex;flex-direction:column;justify-content:center}}
.tk-stub .dow{{font:400 13px/1.2 {MONO};color:var(--ink2)}}
.tk-stub .md{{font:600 24px/1.2 {DISPLAY}}}
.tk-stub .new{{margin-top:10px;font:600 32px/1 {DISPLAY};color:var(--snow)}}
.tk-stub .cap{{font-size:11px;color:var(--ink2)}}
dl.stats{{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:10px;margin:4px 0 0}}
dl.stats div{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:8px 10px}}
dl.stats dt{{font:600 10px/1.3 {MONO};letter-spacing:.05em;text-transform:uppercase;color:var(--ink2)}}
dl.stats dd{{margin:2px 0 0;font:600 20px/1.2 {DISPLAY}}}
.powder{{margin:12px 0 0;padding:6px 10px;border-left:3px solid var(--btn);background:var(--accent-soft);border-radius:6px;font-size:14px}}
.map figure{{margin:0}}
.map img{{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:12px;background:var(--surface)}}
.map figcaption{{display:flex;justify-content:space-between;gap:10px;margin:8px 2px 0;font-size:13px;color:var(--ink2)}}
.runs h3{{margin:14px 0 6px;font:600 11px/1.3 {MONO};letter-spacing:.05em;text-transform:uppercase;color:var(--ink2)}}
.runs ul{{margin:0;padding-left:18px;columns:3 170px;column-gap:20px}}
.runs li{{break-inside:avoid;padding:1px 0}}
.runs ul.gotd{{list-style:none;padding:0;columns:auto;display:flex;flex-wrap:wrap;gap:6px}}
.runs ul.gotd li{{padding:3px 10px;border-radius:8px;background:var(--accent-soft);border:1px solid var(--chip-line);color:var(--accent-ink);font-weight:600}}
.scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
table.hours{{width:100%;min-width:300px;border-collapse:separate;border-spacing:2px;font:400 12px {MONO};text-align:center}}
table.hours th{{font:600 10px/1.2 {MONO};letter-spacing:.03em;text-transform:uppercase;color:var(--ink2);text-align:left;padding-right:6px}}
table.hours thead th{{text-align:center;text-transform:none;font:400 12px {MONO}}}
table.hours td.t{{font-weight:600;color:var(--ink)}}
table.hours td.f{{color:var(--ink2)}}
table.hours td.g span{{display:block;border-radius:6px;padding:4px 0;font-weight:600;color:#0c2a4a}}
.fc-head{{margin:0 0 10px;font-size:15px}}
ol.days{{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(5,1fr);gap:6px}}
ol.days li{{text-align:center;font-size:11px;color:var(--ink2);line-height:1.25}}
ol.days .v{{display:block;border:1px solid var(--tile-line);border-radius:8px;padding:8px 0;margin-bottom:3px;font:600 14px {MONO};color:#0c2a4a}}
ol.days .r{{display:block;color:var(--snow);min-height:1.25em}}
.actions{{margin:4px 0 0;display:flex;flex-wrap:wrap;gap:10px;align-items:center}}
.actions a.btn{{background:var(--btn);color:#fff;text-decoration:none;padding:12px 18px;border-radius:12px;font-weight:600}}
.actions a{{color:var(--action)}}
@media (min-width:900px){{
 .rp .cols{{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}}
 .rp .cols .card{{margin:0}}
 .rp .cols+.actions{{margin-top:14px}}
 ol.days{{grid-template-columns:repeat(5,1fr)}}
 h1.page{{font-size:30px}}
}}
@media (max-width:420px){{.ticket .tk-stub{{width:92px}} dl.stats{{grid-template-columns:1fr 1fr}} table.hours th{{padding-right:2px;font-size:9px}} .rp .card{{padding:14px 12px}}}}
"""


def _inch(x):
    return mailer._inch(x)


def _ticket(day):
    rs = day.get("resort") or {}
    obs = day.get("observed") or {}
    d = date.fromisoformat(day["date"])
    r24 = rs.get("last_24h_in", obs.get("snow_in"))
    stats = [("New, 24 hr", r24), ("Base", rs.get("base_in")), ("Last 7 days", rs.get("last_7d_in")),
             ("Season", rs.get("season_in"))]
    cells = "".join(f"<div><dt>{k}</dt><dd>{_inch(v)}</dd></div>" for k, v in stats if v is not None)
    kick = f"{d.strftime('%A')} {report.mmdd(d)}"
    if rs.get("updated_time"):
        kick += f" · snow report {escape(rs['updated_time'])}"
    note = ""
    if day.get("powder"):
        note = f'<p class="powder">{escape(day["powder"].lstrip("❄️ ").strip())}</p>'
    elif day.get("preseason"):
        from . import config
        note = f'<p class="sub">Opens {report.mmdd(config.OPENING_DAY)}</p>'
    main = (f'<p class="kick">{kick}</p>'
            + (f'<dl class="stats">{cells}</dl>' if cells else '<p class="sub">The snow report hasn\'t posted yet.</p>')
            + note)
    stub = (f'<div class="dow">{d.strftime("%a")}</div><div class="md">{report.mmdd(d)}</div>'
            f'<div class="new">{_inch(r24)}</div><div class="cap">new, 24 hr</div>')
    return f'<section class="card ticket" aria-label="Snow totals"><div class="tk-main">{main}</div><div class="tk-stub">{stub}</div></section>'


def _run_sections(runs):
    secs = [("Groomed overnight", runs.get("overnight")), ("Groomed this morning", runs.get("morning"))]
    areas = runs.get("areas")
    if areas:
        secs += list(areas.items())
    elif runs.get("groomed"):
        secs.append(("Groomed", runs["groomed"]))
    return [(t, n) for t, n in secs if n]


def _grooming(day, map_url):
    g = day.get("grooming") or {}
    runs = g.get("runs") or {}
    all_runs = mailer.groomed_runs(runs)
    name = escape(report.resort_name(day))
    if not map_url and not all_runs:
        return ('<section class="card runs" id="grooming"><h2>Grooming</h2>'
                f'<p class="sub" style="margin:0">{name} hasn\'t posted grooming for this day.</p></section>')
    out = '<section class="card runs map" id="grooming"><h2>Grooming</h2>'
    counts = []
    if all_runs:
        counts.append(f"{len(all_runs)} runs groomed")
    if runs.get("overnight") and runs.get("morning"):
        counts.append(f"{len(runs['overnight'])} overnight, {len(runs['morning'])} this morning")
    if counts:
        out += f'<p class="sub" style="margin:0 0 10px">{" · ".join(counts)}</p>'
    if map_url:
        stamp = f"Grooming map, printed {escape(report.map_date(runs['map_date']))}" if runs.get("map_date") else "Grooming map"
        if not g.get("new_map", True):
            stamp += " · no new map yet today"
        out += (f'<figure><a href="{map_url}" target="_blank" rel="noopener">'
                f'<img src="{map_url}" alt="Grooming map for {name}, {report.mmdd(day["date"])}" loading="eager"></a>'
                f'<figcaption><span>{stamp}</span><a href="{map_url}" target="_blank" rel="noopener">Open full size</a></figcaption></figure>')
    if runs.get("groomers_of_the_day"):
        out += '<h3>Groomers of the day</h3><ul class="gotd">' + "".join(
            f"<li>{escape(n)}</li>" for n in runs["groomers_of_the_day"]) + "</ul>"
    for t, names in _run_sections(runs):
        out += f"<h3>{escape(t)}</h3><ul>" + "".join(f"<li>{escape(n)}</li>" for n in names) + "</ul>"
    return out + "</section>"


def _hourly(day):
    hrs = mailer.ski_hours(day)
    if not hrs:
        return ""
    gusts = [h.get("gust") or h.get("wind") or 0 for h in hrs]
    lo = min(gusts)
    head = "".join(f'<th scope="col">{mailer._hour(h["time"])}</th>' for h in hrs)
    temp = "".join(f'<td class="t">{h["temp"]}°</td>' for h in hrs)
    feels = "".join(f'<td class="f">{h["feels"]}°</td>' for h in hrs)
    gust = "".join(f'<td class="g"><span style="background:{mailer._ramp(max(v - lo, 1), 18)}">{v}</span></td>' for v in gusts)
    peak = max(hrs, key=lambda h: h.get("gust") or 0)
    cap = "Temperature and feels like in °F, gusts in mph, at the resort."
    if peak.get("gust"):
        cap += f" Peak gust {peak['gust']} mph at {mailer._clock(peak['time'])}."
    return (f'<section class="card" id="hourly"><h2>First chair to last</h2>'
            f'<div class="scroll"><table class="hours"><thead><tr><td></td>{head}</tr></thead><tbody>'
            f'<tr><th scope="row">Temp</th>{temp}</tr><tr><th scope="row">Feels</th>{feels}</tr>'
            f'<tr><th scope="row">Gust</th>{gust}</tr></tbody></table></div><p class="sub">{cap}</p></section>')


def _forecast(day):
    fc = day.get("forecast") or {}
    tiles = ""
    for f in (fc.get("days") or [])[:10]:
        dd = date.fromisoformat(f["date"])
        s = f["snow"]
        val = "–" if s < 0.1 else (f'{round(s)}"' if s >= 1 else f'{round(s, 1)}"')
        rng = (f'{f["low"]:g}–{f["high"]:g}"' if s >= 0.1 and f.get("low") is not None and f.get("high") is not None
               and f["high"] > f["low"] else "")
        tiles += (f'<li><span class="v" style="background:{mailer._ramp(s)}">{val}</span>'
                  f'{dd.strftime("%a")}<br>{dd.month}/{dd.day}<span class="r">{rng}</span></li>')
    if not tiles:
        return ""
    lo, hi = (fc.get("next_1_5_range") or [None, None])[:2]
    head = (f'Next 5 days <b>{_inch(lo).rstrip(chr(34))} to {_inch(hi)}</b>, most likely {_inch(fc.get("next_1_5"))}'
            if lo is not None and hi is not None and hi > lo else f'Next 5 days <b>{_inch(fc.get("next_1_5"))}</b>')
    n7 = mailer.next_7(fc)
    if n7 is not None:
        head += f" · next 7 days <b>{_inch(n7)}</b>"
    if fc.get("next_6_10") is not None:
        head += f' · days 6–10 {_inch(fc.get("next_6_10"))}'
    return (f'<section class="card" id="forecast"><h2>Snow forecast</h2><p class="fc-head">{head}</p>'
            f'<ol class="days">{tiles}</ol><p class="sub">Likely range under each snowy day.</p></section>')


def render(day, map_url):
    """The report body for a web page. `day` is the stored day JSON (with resort_name/resort_slug set)."""
    app = report.app_url(day)
    side = _hourly(day) + _forecast(day)
    return ('<article class="rp">' + _ticket(day) + _grooming(day, map_url)
            + (f'<div class="cols">{side}</div>' if side else "")
            + f'<p class="actions"><a class="btn" href="{app}">See the full report</a>'
              f'<a href="{app}">Cams</a> · <a href="{app}#forecast">Forecast</a></p></article>')
