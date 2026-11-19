"""Machine-readable versions of the public pages, for AI assistants and anything else that reads text.

  /llms.txt                       what 0xSnow is and where every resort's data lives (llmstxt.org format)
  /resorts/<slug>.md              today's report as Markdown        (.json: the same as JSON)
  /resorts/<slug>/<date>.md       an archived report as Markdown    (.json too)
  /resorts/<slug>/guide.md        resort facts (hours, dates, passes, tickets, lessons) with sources
  /resorts/colorado.md            every resort in a state, one table

Same stored data and the same rules as the HTML pages: only real numbers, every fact with its source
and checked date, dates as MM/DD with the weekday. Each HTML page links to its Markdown twin with
<link rel="alternate" type="text/markdown">, and each Markdown response names its HTML page as canonical.
"""
from datetime import date

from . import mailer, report, resorts

ORG = "0xSnow"


def _site(path=""):
    from .pages import site
    return site(path)


def _inch(x):
    return mailer._inch(x)


def _day_label(iso):
    d = date.fromisoformat(iso)
    return f"{d.strftime('%a')} {report.mmdd(d)}"


# ---------- llms.txt ----------

def llms_txt():
    lines = [
        f"# {ORG}",
        "",
        "> Free daily grooming and snow reports for Colorado and Utah ski resorts: groomed runs, new snow, base depth, "
        "the hourly weather from first chair to last, a 10-day snow forecast, and sourced resort facts (opening and "
        "closing day, lift hours, pass blackout dates, lift tickets, lessons, trail map links).",
        "",
        "Reports update every morning in the resort's time zone (Mountain time). Numbers come from each resort's own "
        "snow report and grooming map, NRCS SNOTEL stations, the National Weather Service and Open-Meteo weather models. "
        f"{ORG} is independent and not affiliated with Vail Resorts, Alterra or any resort. Every resort fact links to "
        "the official page it came from and says when it was last checked. When quoting, please cite the page URL and "
        "the report date.",
        "",
        "Each resort has: today's report (HTML and Markdown at the same path plus .md, JSON with .json), an archive of "
        "past daily reports, and a guide with resort facts.",
        "",
        "## Today, every resort",
        "",
    ]
    for key, label in (("colorado", "Colorado"), ("utah", "Utah")):
        lines.append(f"- [{label} snow report today]({_site(f'resorts/{key}.md')}): every {label} resort in one table, "
                     "sorted by new snow")
    groups = {}
    for slug in resorts.enabled():
        r = resorts.get(slug)
        groups.setdefault(r["region"], []).append(r)
    for region in sorted(groups):
        lines += ["", f"## {region} resorts", ""]
        for r in sorted(groups[region], key=lambda x: x["name"]):
            s = r["slug"]
            lines.append(f"- [{r['name']} report today]({_site(f'resorts/{s}.md')}): grooming, new snow, base, hourly "
                         f"weather and snow forecast ({r['pass']} pass). JSON: {_site(f'resorts/{s}.json')}. "
                         f"Resort facts: {_site(f'resorts/{s}/guide.md')}")
    from . import pages  # local: pages imports this module
    lines += ["", "## Pass blackout dates", ""]
    for key, p in pages.PASSES.items():
        lines.append(f"- [{p['h1']}]({_site(f'passes/{key}')}): every blackout date, which passes they apply to and "
                     f"which resorts each pass covers. Calendar file: {_site(f'passes/{key}.ics')}")
    lines += ["", "## Optional", "",
              f"- [Sitemap]({_site('sitemap.xml')}): every page, including dated archive reports",
              f"- [RSS feed]({_site('feed.xml')}): the newest report for each resort",
              f"- [App]({_site()}): the full interactive app, cams and radar (JavaScript)"]
    return "\n".join(lines) + "\n"


# ---------- reports ----------

def _links(slug, day_str=None):
    html = _site(f"resorts/{slug}" + (f"/{day_str}" if day_str else ""))
    return html, _site(f"resorts/{slug}/guide.md")


def report_md(slug, day, dated=False):
    from . import pages
    r = resorts.get(slug)
    name = r["name"]
    day = dict(day, resort_name=day.get("resort_name") or name, resort_slug=slug)
    d = date.fromisoformat(day["date"])
    rs, fc, g = day.get("resort") or {}, day.get("forecast") or {}, day.get("grooming") or {}
    runs = g.get("runs") or {}
    html, guide = _links(slug, day["date"] if dated else None)
    out = [f"# {name} grooming and snow report, {d.strftime('%A')} {report.mmdd(d)}/{d.year}", "",
           " ".join(pages.summary(day)), "",
           f"Source page: {html}  ",
           f"Region: {r['region']} · Pass: {r['pass']} · Report generated: {day.get('generated') or day['date']} (Mountain time)", ""]
    out += ["## Snow", ""]
    rows = [("New snow, 24 hours", mailer.new_snow(day)), ("Base depth", rs.get("base_in")),
            ("Last 7 days", rs.get("last_7d_in")), ("Season total", rs.get("season_in"))]
    rows = [(k, v) for k, v in rows if v is not None]
    if rows:
        out += ["| Measure | Inches |", "|---|---|"] + [f"| {k} | {_inch(v)} |" for k, v in rows]
        if rs.get("updated_time"):
            out.append(f"\nThe resort's snow report posted at {rs['updated_time']}.")
    else:
        out.append("The resort hasn't posted a snow report for this day.")
    out += ["", "## Grooming", ""]
    groomed = mailer.groomed_runs(runs)
    if runs.get("groomers_of_the_day"):
        out.append("Groomers of the day: " + ", ".join(runs["groomers_of_the_day"]) + ".")
    secs = [("Groomed overnight", runs.get("overnight")), ("Groomed this morning", runs.get("morning"))]
    secs += list((runs.get("areas") or {}).items()) or ([("Groomed", runs.get("groomed"))] if runs.get("groomed") else [])
    for t, names in secs:
        if names:
            out += ["", f"### {t}", ""] + [f"- {n}" for n in names]
    if not groomed:
        out.append(f"{name} hasn't posted grooming for this day.")
    if g.get("image"):
        out += ["", f"Grooming map image: {_site(g['image'])}" + (f" (printed {report.map_date(runs['map_date'])})" if runs.get("map_date") else "")]
    hrs = mailer.ski_hours(day)
    if hrs:
        out += ["", "## Hourly forecast at the resort", "", "| Hour | Temp °F | Feels like °F | Gust mph |", "|---|---|---|---|"]
        out += [f"| {mailer._clock(h['time'])} | {h['temp']} | {h['feels']} | {h.get('gust') or h.get('wind') or '–'} |" for h in hrs]
    days = (fc.get("days") or [])[:10]
    if days:
        out += ["", "## Snow forecast", ""]
        lo, hi = (fc.get("next_1_5_range") or [None, None])[:2]
        if fc.get("next_1_5") is not None:
            rng = f" (likely {_inch(lo)} to {_inch(hi)})" if lo is not None and hi is not None and hi > lo else ""
            out.append(f"Next 5 days: {_inch(fc['next_1_5'])}{rng}." + (f" Next 7 days: {_inch(mailer.next_7(fc))}." if mailer.next_7(fc) is not None else ""))
        out += ["", "| Day | Snow | Likely range |", "|---|---|---|"]
        for f in days:
            rng = f'{f["low"]:g} to {f["high"]:g}"' if f.get("low") is not None and f.get("high") is not None and f["high"] > f["low"] else "–"
            out.append(f"| {_day_label(f['date'])} | {_inch(f['snow']) if f['snow'] >= 0.1 else '–'} | {rng} |")
    out += ["", "## More", "", f"- Resort facts (hours, opening and closing day, passes, tickets, trail map): {guide}",
            f"- {r['region']} resorts today: {_site('resorts/' + r['region'].lower() + '.md')}",
            f"- Get this report free every morning: {_site('?resort=' + slug)}", "",
            f"_{ORG} is independent and not affiliated with any resort. Snow totals and grooming come from the resort's own "
            "reports; forecast data from Open-Meteo (CC BY 4.0), NWS and NRCS SNOTEL._"]
    return "\n".join(out) + "\n"


def report_json(slug, day, dated=False):
    from . import facts as F
    from . import pages
    r = resorts.get(slug)
    day = dict(day, resort_name=day.get("resort_name") or r["name"], resort_slug=slug)
    rs, fc, g = day.get("resort") or {}, day.get("forecast") or {}, day.get("grooming") or {}
    runs = g.get("runs") or {}
    html, _ = _links(slug, day["date"] if dated else None)
    return {
        "resort": {"slug": slug, "name": r["name"], "region": r["region"], "pass": r["pass"],
                   "lat": r["lat"], "lon": r["lon"]},
        "date": day["date"], "generated": day.get("generated"), "url": html,
        "summary": " ".join(pages.summary(day)),
        "snow_in": {"new_24h": mailer.new_snow(day), "base": rs.get("base_in"), "last_7d": rs.get("last_7d_in"),
                    "season": rs.get("season_in"), "report_posted": rs.get("updated_time")},
        "grooming": {"groomers_of_the_day": runs.get("groomers_of_the_day") or [],
                     "overnight": runs.get("overnight") or [], "morning": runs.get("morning") or [],
                     "areas": runs.get("areas") or {}, "all": mailer.groomed_runs(runs),
                     "map_image": _site(g["image"]) if g.get("image") else None},
        "hourly": [{"time": h["time"], "temp_f": h.get("temp"), "feels_f": h.get("feels"), "gust_mph": h.get("gust")}
                   for h in mailer.ski_hours(day)],
        "forecast": {"next_5_days_in": fc.get("next_1_5"), "next_5_days_range_in": fc.get("next_1_5_range"),
                     "next_7_days_in": mailer.next_7(fc),
                     "days": [{"date": f["date"], "snow_in": f["snow"], "low_in": f.get("low"), "high_in": f.get("high")}
                              for f in (fc.get("days") or [])[:10]]},
        "facts": {k: {kk: vv for kk, vv in v.items() if kk in ("value", "note", "label", "checked", "source", "source_name")}
                  for k, v in F.public(slug).items()},
        "attribution": f"{ORG} ({_site()}). Not affiliated with any resort. Forecast data: Open-Meteo (CC BY 4.0), NWS, NRCS SNOTEL.",
    }


# ---------- guide and state tables ----------

def guide_md(slug):
    from . import facts as F
    r = resorts.get(slug)
    name = r["name"]
    out = [f"# {name}: resort facts", "", f"Source page: {_site(f'resorts/{slug}/guide')}  ",
           f"Region: {r['region']} · Pass: {r['pass']}", ""]
    kinds = F.public(slug)
    if not kinds:
        out += [f"0xSnow hasn't collected sourced facts for {name} yet. Opening day on file: "
                f"{r['opening_day'].strftime('%A')} {report.mmdd(r['opening_day'])}.", ""]
    else:
        out += ["Every fact links to the official page it came from and gives the date it was last checked. "
                "Prices change by date; check the source before you go.", ""]
        for kind, label in F.LABELS.items():
            f = kinds.get(kind)
            if not f:
                continue
            v = f.get("value")
            if kind in ("opening_day", "closing_day") and v:
                d = date.fromisoformat(v)
                v = f"{d.strftime('%A')} {report.mmdd(d)}/{d.year}"
            shown = v or ("Not announced yet" if kind in ("opening_day", "closing_day") else "Not posted yet")
            out += [f"## {label}", "", shown]
            if f.get("note"):
                out.append(f"\n{f['note']}")
            out += ["", f"Source: [{f.get('source_name') or f['source']}]({f['source']}), checked {report.mmdd(f['checked'])}/{f['checked'][:4]}", ""]
    out += [f"Today's {name} report: {_site(f'resorts/{slug}.md')}"]
    return "\n".join(out) + "\n"


def region_md(store, region):
    from . import pages
    rows = pages.region_rows(store, region)
    label = pages.REGIONS[region]
    today = max((x["date"] for x in rows if x["date"]), default=date.today().isoformat())
    out = [f"# {label} snow report today, {_day_label(today)}", "", f"Source page: {_site('resorts/' + region)}", "",
           "| Resort | Pass | New 24 hr | Base | Groomed runs | Next 5 days | Report date |", "|---|---|---|---|---|---|---|"]
    for x in rows:
        out.append(f"| [{x['name']}]({_site('resorts/' + x['slug'] + '.md')}) | {x['pass']} | {_inch(x['new'])} | "
                   f"{_inch(x['base'])} | {x['groomed'] if x['groomed'] is not None else '–'} | {_inch(x['next5'])} | "
                   f"{_day_label(x['date']) if x['date'] else '–'} |")
    out += ["", "Sorted by new snow. Groomed counts only where the resort publishes groomed runs."]
    return "\n".join(out) + "\n"
