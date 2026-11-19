"""The resort guide page (/resorts/<slug>/guide), laid out by what people search for.

Order follows docs/SEO.md: today's snow report first, then quick answers (open? blackout dates, trail map, cams,
grooming time), then blackout dates and passes, trail map and cams, season dates and hours, tickets and lessons,
and last how the 0xSnow report is built. Every fact keeps its source link and checked date (bcbot/facts.py).
"""

from datetime import date
from html import escape

from . import report, resorts, webreport
from .mailer import DISPLAY, MONO

CSS = f"""
.gd .hero{{display:grid;gap:14px;margin:4px 0 18px}}
.gd .hero h2{{margin:0 0 8px}}
.gd .snownow .ticket{{margin-bottom:10px}}
.gd .snownow .actions{{margin:0}}
.answers{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:0;padding:0;list-style:none}}
.answers a{{display:block;height:100%;box-sizing:border-box;background:var(--paper);border:1px solid var(--edge);border-radius:14px;
 box-shadow:var(--shadow);padding:10px 12px;text-decoration:none;color:var(--ink)}}
.answers a:hover{{border-color:var(--btn)}}
.answers .k{{display:block;font:600 10px/1.3 {MONO};letter-spacing:.05em;text-transform:uppercase;color:var(--ink2)}}
.answers b{{display:block;font:600 16px/1.25 {DISPLAY};margin-top:4px}}
.answers .s{{display:block;font-size:12px;color:var(--ink2);margin-top:2px}}
.answers .hot b{{color:var(--accent-ink)}}
.hours-v{{font:600 18px/1.4 {DISPLAY};margin:0}}
.hourscard .card{{margin:0}}
.gd .layout{{display:grid;gap:14px}}
.gd .layout>div>.card:last-child{{margin-bottom:0}}
.gd aside .cta{{margin:0 0 14px}}
.toc{{background:var(--paper);border:1px solid var(--edge);border-radius:24px;padding:14px 16px}}
.toc ol{{margin:6px 0 0;padding-left:18px;font-size:14px;line-height:1.8}}
.answer{{font:600 18px/1.35 {DISPLAY};margin:0 0 4px}}
.bo{{list-style:none;padding:0;margin:12px 0 8px;display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:8px}}
.bo li{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:8px 10px}}
.bo li b{{display:block;font:600 13px/1.3 {MONO}}}
.bo li span{{font-size:12px;color:var(--ink2)}}
.bo li.next,.bo li.on{{background:var(--accent-soft);border-color:var(--chip-line)}}
.bo li.next span,.bo li.on span{{color:var(--accent-ink);font-weight:600}}
.bo li.past{{opacity:.5}}
table.passes{{width:100%;border-collapse:collapse;font-size:14px;margin:6px 0 0}}
table.passes th,table.passes td{{border-top:1px solid var(--line);padding:8px 0;vertical-align:top;text-align:left}}
table.passes th{{font-weight:600;width:40%;padding-right:10px}}
.src{{font-size:12px;color:var(--ink2);margin:8px 0 0}}
.src b{{color:var(--accent-ink)}}
dl.facts{{margin:0}}
dl.facts>div{{padding:12px 0;border-top:1px solid var(--line)}}
dl.facts>div:first-child{{border-top:0;padding-top:0}}
dl.facts dt{{font:600 11px/1.3 {MONO};letter-spacing:.05em;text-transform:uppercase;color:var(--ink2)}}
dl.facts dd{{margin:3px 0 0;font-size:16px}}
dl.facts .note{{font-size:14px;color:var(--ink2);margin-top:2px}}
.links{{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 0}}
.links a{{display:inline-block;border:1px solid var(--line);background:var(--surface);color:var(--ink);padding:10px 14px;
 border-radius:12px;text-decoration:none;font-weight:600;font-size:14px}}
.links a:hover{{border-color:var(--btn)}}
.maps{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px;margin:0 0 12px}}
.maps figure{{margin:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--surface)}}
.maps img{{display:block;width:100%;height:auto;aspect-ratio:4/3;object-fit:cover}}
.maps figcaption{{display:flex;justify-content:space-between;gap:8px;padding:8px 10px;font-size:13px}}
.maps figcaption span{{color:var(--ink-2)}}
table.glance{{width:100%;border-collapse:collapse;font-size:14px;margin-top:10px}}
table.glance td{{border-top:1px solid var(--line);padding:6px 0}}
table.glance td:first-child{{color:var(--ink2);width:40%}}
@media (min-width:640px){{.answers{{grid-template-columns:repeat(3,minmax(0,1fr))}}}}
@media (min-width:900px){{
 .gd .hero{{grid-template-columns:minmax(0,1fr) minmax(0,1fr);align-items:start}}
 .gd .hero .qa{{grid-column:1 / -1}}
 .answers{{grid-template-columns:repeat(6,minmax(0,1fr))}}
 .gd .layout{{grid-template-columns:minmax(0,1fr) 300px;align-items:start}}
 .gd aside{{position:sticky;top:calc(var(--hdr,112px) + 12px)}}
}}
@media (min-width:1300px){{
 .gd .hero{{grid-template-columns:minmax(0,1.15fr) minmax(0,.85fr) minmax(0,1.2fr)}}
 .gd .hero .qa{{grid-column:auto}}
 .answers{{grid-template-columns:repeat(3,minmax(0,1fr))}}
 .gd .layout{{grid-template-columns:minmax(0,1fr) 340px}}
}}
"""

SECTION_ORDER = ("trail_map", "opening_day", "blackout_dates", "lift_hours", "lift_tickets", "lessons")
SEARCH_WORDS = {"trail_map": "trail map", "opening_day": "opening day", "blackout_dates": "blackout dates",
                "lift_hours": "lift hours", "lift_tickets": "ticket prices", "lessons": "lessons"}


def _join(parts):
    return ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + (parts[-1] if parts else "")


def covers(slug):
    """What the page answers, in search-demand order (docs/SEO.md): trail map, opening day, blackout dates..."""
    from . import facts as F
    have = F.FACTS.get(slug) or {}
    return [SEARCH_WORDS[k] for k in SECTION_ORDER if k in have]


def _day(iso):
    d = date.fromisoformat(iso)
    return f"{d.strftime('%a')} {report.mmdd(d)}"


def _long_day(iso):
    d = date.fromisoformat(iso)
    return f"{d.strftime('%A')} {report.mmdd(d)}/{d.year}"


def _src(f, kind, today):
    from . import facts as F
    flag = " · <b>re-checking</b>" if F.stale(f, kind, today) else ""
    return (f'<p class="src">Source: <a href="{escape(f["source"])}" rel="nofollow">{escape(f.get("source_name") or f["source"])}</a>'
            f' · checked {report.mmdd(f["checked"])}{flag}</p>')


def _cap(s):
    return s[:1].upper() + s[1:] if s else s


def _season_answer(name, kinds, opening_default, today):
    """('Opened Fri 11/13' style tile text, sentence)."""
    f = kinds.get("opening_day")
    iso = (f or {}).get("value") or opening_default.isoformat()
    d = date.fromisoformat(iso)
    if d <= today:
        close = (kinds.get("closing_day") or {}).get("value")
        if close and date.fromisoformat(close) < today:
            return "Closed for the season", f"{name} closed on {_long_day(close)}."
        return f"Open since {_day(iso)}", f"{name} opened for the 2026/27 season on {_long_day(iso)}."
    return f"Opens {_day(iso)}", f"{name} opens for the 2026/27 season on {_long_day(iso)}."


def _blackout(slug, name, kinds, today):
    """(tile, section html) for blackout dates, or (None, '')."""
    from . import pages
    f = kinds.get("blackout_dates")
    if not f:
        return None, ""
    key = f.get("pass_key")
    passes = kinds.get("passes") or {}
    rows = passes.get("rows") or []
    table = ("<table class=\"passes\">" + "".join(f"<tr><th scope=\"row\">{escape(p)}</th><td>{escape(_cap(a))}</td></tr>"
                                                 for p, a in rows) + "</table>") if rows else (
        f'<p>{escape(passes["value"])}</p>' if passes.get("value") else "")
    if key and key in pages.PASSES:
        p = pages.PASSES[key]
        on, nxt = pages.pass_status(key, today)
        if on:
            tile = ("Today", "Blackout day")
            answer = f"Today ({report.mmdd(today)}) is a blackout date at {name} for the {f['applies']}."
        elif nxt:
            tile = ("Next", pages._range_text(nxt[0], nxt[1]))
            answer = (f"Today isn't a blackout date at {name}. The next one is {pages._range_text(nxt[0], nxt[1])} "
                      f"({nxt[2]}).")
        else:
            tile = ("Next", "None left this season")
            answer = f"No blackout dates are left this season at {name}."
        chips = ""
        for a, b, label in p["ranges"]:
            cls = ("on" if date.fromisoformat(a) <= today <= date.fromisoformat(b) else
                   "past" if date.fromisoformat(b) < today else
                   "next" if nxt and a == nxt[0] else "")
            chips += f'<li class="{cls}"><b>{escape(pages._range_text(a, b))}</b><span>{escape(label)}</span></li>'
        body = (f'<p class="answer">{escape(answer)}</p><ul class="bo">{chips}</ul>'
                f'<p class="sub">These apply to the {escape(f["applies"])}. {escape(p["free"])} '
                f'<a href="/passes/{key}">All {p["pass"]} Pass blackout dates</a></p>')
    else:
        tile = ("At " + name, "None")
        body = f'<p class="answer">{escape(f["value"])}</p>'
    html_ = (f'<section class="card" id="blackout-dates"><h2 tabindex="-1">{escape(name)} blackout dates and passes</h2>{body}'
             + _src(f, "blackout_dates", today)
             + (f'<h3 class="kick" style="margin-top:16px">Which passes work at {escape(name)}</h3>{table}'
                + _src(passes, "passes", today) if passes else "")
             + "</section>")
    return tile, html_


def _fact_rows(kinds, keys, today, name):
    out = ""
    from . import facts as F
    for kind in keys:
        f = kinds.get(kind)
        if not f:
            continue
        v = f.get("value")
        if kind in ("opening_day", "closing_day"):
            shown = _long_day(v) if v else "Not announced yet"
        elif kind == "lift_tickets":
            shown = v or "No fixed price posted"
        else:
            shown = v or "Not posted yet"
        note = f'<div class="note">{escape(f["note"])}</div>' if f.get("note") else ""
        out += f'<div><dt>{F.LABELS[kind]}</dt><dd>{escape(shown)}{note}{_src(f, kind, today)}</dd></div>'
    return f'<dl class="facts">{out}</dl>' if out else ""


def map_gallery(tm):
    """Every trail map the resort posts (big mountains have several). Images load from the resort's own
    server, never copied to ours; maps that only come as a PDF get a link instead."""
    out = ""
    for m in (tm or {}).get("maps") or []:
        full = m.get("image") or m.get("pdf")
        if not full:
            continue
        cap = (f'<figcaption><b>{escape(m["label"])}</b><span>{escape(m.get("season") or "")}'
               f'{" · PDF" if m.get("pdf") and not m.get("image") else ""}</span></figcaption>')
        if m.get("image"):
            out += (f'<figure><a href="{escape(full)}" rel="nofollow noopener" target="_blank">'
                    f'<img src="{escape(m["image"])}" alt="{escape(m["label"])} trail map" loading="lazy" '
                    f'referrerpolicy="no-referrer"></a>{cap}</figure>')
        elif m.get("pdf") and len(tm["maps"]) > 1:
            out += f'<figure><a class="pdf" href="{escape(m["pdf"])}" rel="nofollow noopener" target="_blank">{cap}</a></figure>'
    return f'<div class="maps">{out}</div>' if out else ""


def faq(slug, name, kinds, timing, today):
    qa = []
    for kind in ("opening_day", "closing_day", "lift_hours", "trail_map", "passes", "blackout_dates", "lift_tickets", "lessons"):
        f = kinds.get(kind)
        if not f:
            continue
        v = f.get("value")
        if kind in ("opening_day", "closing_day"):
            verb = "open" if kind == "opening_day" else "close"
            past = bool(v) and date.fromisoformat(v) < today
            q = f"When {'did' if past else 'does'} {name} {verb} for the 2026/27 season?"
            if not v:
                ans = f"{name} hasn't announced its {'opening' if kind == 'opening_day' else 'closing'} day yet."
            else:
                ans = f"{name} {verb + 'ed' if past else verb + 's'} on {_long_day(v)}."
        elif kind == "trail_map":
            q, ans = f"Where is the {name} trail map?", f"The official map is on the resort's site: {v}"
        else:
            q = {"lift_hours": f"What are {name}'s lift hours?",
                 "passes": f"Which ski passes work at {name}?",
                 "blackout_dates": f"What are the {name} blackout dates for 2026/27?",
                 "lift_tickets": f"How much is a lift ticket at {name}?",
                 "lessons": f"What ski and snowboard lessons does {name} offer?"}[kind]
            ans = v or f.get("note") or "Not posted yet."
        qa.append({"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": ans}})
    qa.append({"@type": "Question", "name": f"When does the {name} grooming report come out?",
               "acceptedAnswer": {"@type": "Answer", "text": timing}})
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": qa}


def chips(slug):
    """Level-2 nav for the guide: one chip per section, in page order (scroll-spy in pages.NAV_JS)."""
    from . import facts as F
    r = resorts.get(slug)
    kinds = F.FACTS.get(slug) or {}
    items = [("hours", "Lift hours"), ("blackout-dates", "Blackout dates") if kinds.get("blackout_dates") else None,
             ("trail-map", "Trail map and cams") if (kinds.get("trail_map") or r.get("cams")) else None,
             ("season", "Opening day"), ("tickets", "Tickets and lessons") if (kinds.get("lift_tickets") or kinds.get("lessons")) else None,
             ("grooming", "Grooming times"), ("how", "How it works")]
    links = "".join(f'<a href="#{i}">{escape(t)}</a>' for i, t in filter(None, items))
    return f'<nav class="chips" aria-label="On this page">{links}</nav>'


def render(slug, summary=None, day=None, today=None):
    """-> (title, description, h1, body html, [json-ld]) for the guide page."""
    from . import facts as F
    from . import pages
    today = today or pages._today_mt()
    r = resorts.get(slug)
    name = r["name"]
    kinds = F.FACTS.get(slug) or {}
    report_url = pages.resort_path(slug)
    app = f"/?resort={slug}"

    # When the report posts, and how grooming is read.
    times = pages.posting_times(summary, slug)
    when = []
    if "grooming" in times:
        when.append(f'the grooming update usually lands around {times["grooming"]["time"]}')
    if "snow" in times:
        when.append(f'the official snow report usually updates around {times["snow"]["time"]}')
    days = max([t["days"] for t in times.values()], default=0)
    timing = (f"In 0xSnow's posting-time study ({days} morning{'s' if days != 1 else ''} since 11/16), "
              + " and ".join(when) + " Mountain time." if when else
              f"0xSnow is still measuring when {name} posts its morning updates; times will appear here.")
    if r.get("grooming_pdf"):
        groom = (f"{name} publishes a grooming map each night as a PDF. 0xSnow reads the run names off that map "
                 "and shows the full map in the morning report.")
    elif r.get("dor_api"):
        groom = f"{name} publishes groomed runs in its trail status feed. 0xSnow lists every groomed run from it."
    else:
        groom = (f"0xSnow doesn't read {name}'s grooming yet, so its report covers snow, weather and the forecast. "
                 "Grooming will be added when a public source is checked.")

    # Hero: today's snow report (the #1 search) beside the quick answers.
    open_tile, open_sentence = _season_answer(name, kinds, r["opening_day"], today)
    if day and day.get("date"):
        snow = webreport._ticket(dict(day, resort_name=name, resort_slug=slug))
    else:
        msg = (f"The daily {name} report starts on opening day. {open_sentence}" if open_tile.startswith("Opens")
               else f"{name}'s snow report hasn't posted yet today.")
        snow = f'<section class="card"><p class="sub" style="margin:0">{escape(msg)}</p></section>'
    snow = (f'<div class="snownow"><h2>{escape(name)} snow report today</h2>{snow}'
            f'<p class="actions"><a class="btn" href="{report_url}">Today\'s full report</a>'
            f'<a href="{app}">Open in the app</a></p></div>')

    # Lift hours: one of the most asked questions, so it sits in the hero.
    lh = kinds.get("lift_hours")
    if lh and lh.get("value"):
        hours_body = (f'<p class="hours-v">{escape(lh["value"])}</p>'
                      + (f'<p class="sub">{escape(lh["note"])}</p>' if lh.get("note") else "") + _src(lh, "lift_hours", today))
    elif lh:
        hours_body = f'<p class="hours-v">Not posted yet</p><p class="sub">{escape(lh.get("note") or "")}</p>' + _src(lh, "lift_hours", today)
    else:
        hours_body = (f'<p class="sub" style="margin:0">0xSnow hasn\'t checked {escape(name)}\'s lift hours yet. '
                      f'<a href="{escape(r["site"])}" rel="nofollow">See the resort\'s site</a>.</p>')
    hours = (f'<div class="hourscard" id="hours"><h2 tabindex="-1">{escape(name)} lift hours</h2>'
             f'<section class="card">{hours_body}</section></div>')

    tiles = []
    tiles.append(("#season", "Open?", open_tile, ""))
    bo_tile, bo_html = _blackout(slug, name, kinds, today)
    if bo_tile:
        tiles.append(("#blackout-dates", "Blackout dates", bo_tile[1], "Next one" if bo_tile[0] == "Next" else ""))
    rows = (kinds.get("passes") or {}).get("rows") or []
    valid = [p.replace(" Pass", "") for p, a in rows if a != "Not included" and "Day Pass" not in p]
    if valid:
        tiles.append(("#blackout-dates", "Passes", _join(valid), "work here"))
    tm = kinds.get("trail_map")
    if tm or r.get("cams"):
        tiles.append(("#trail-map", "Trail map", "Official map" if tm else "Not linked yet", f"on {r['site'].split('//')[-1].removeprefix('www.')}" if tm else ""))
    if r.get("cams"):
        tiles.append(("#trail-map", "Webcams", f"{len(r['cams'])} cams", "in the 0xSnow app"))
    g_time = (times.get("grooming") or {}).get("time")
    tiles.append(("#grooming", "Grooming", f"About {g_time}" if g_time else ("Nightly PDF" if r.get("grooming_pdf")
                                                                     else "Trail status feed" if r.get("dor_api")
                                                                     else "Not tracked yet"),
                  "usual posting time" if g_time else ""))
    if kinds.get("lift_tickets"):
        tiles.append(("#tickets", "Lift tickets", "Prices", ""))
    answers = '<ul class="answers">' + "".join(
        f'<li><a href="{h}"{" class=\"hot\"" if k == "Blackout dates" and "Blackout day" in b else ""}>'
        f'<span class="k">{escape(k)}</span><b>{escape(b)}</b>' + (f'<span class="s">{escape(s)}</span>' if s else "") + "</a></li>"
        for h, k, b, s in tiles[:6]) + "</ul>"

    # Main sections.
    sections = [bo_html] if bo_html else []
    if tm or r.get("cams"):
        links = ""
        if tm:
            links += f'<a href="{escape(tm["value"])}" rel="nofollow">{escape(tm.get("label") or "Official trail map")} ↗</a>'
        if r.get("cams"):
            links += f'<a href="{app}">{len(r["cams"])} live cams in the app</a>'
        if r.get("grooming_pdf"):
            links += f'<a href="{escape(r["grooming_pdf"])}" rel="nofollow">Tonight\'s grooming map (PDF) ↗</a>'
        sections.append(f'<section class="card" id="trail-map"><h2 tabindex="-1">{escape(name)} trail map and webcams</h2>'
                        f'<p class="sub" style="margin:0 0 10px">0xSnow links to the resort\'s own trail map and shows its '
                        f'public cams in the app.</p>{map_gallery(tm)}<div class="links">{links}</div>'
                        + (_src(tm, "trail_map", today) if tm else "") + "</section>")
    season = _fact_rows(kinds, ("opening_day", "closing_day"), today, name)
    sections.append(f'<section class="card" id="season"><h2 tabindex="-1">{escape(name)} opening and closing day</h2>'
                    + (season or f'<p class="answer">{escape(open_sentence)}</p>') + "</section>")
    tickets = _fact_rows(kinds, ("lift_tickets", "lessons"), today, name)
    if tickets:
        sections.append(f'<section class="card" id="tickets"><h2 tabindex="-1">{escape(name)} lift tickets and lessons</h2>{tickets}'
                        f'<p class="src">Prices change by date. Check the source before you buy.</p></section>')
    sections.append(f'<section class="card" id="grooming"><h2 tabindex="-1">{escape(name)} grooming report: when it posts</h2>'
                    f'<p style="margin:0 0 8px">{escape(timing)}</p><p style="margin:0">{escape(groom)}</p></section>')

    bands = {b["key"]: b for b in r.get("bands") or []}
    elev = ", ".join(f'{k} {bands[k]["elevation_ft"]:,} ft' for k in ("base", "mid", "peak") if k in bands)
    glance = [("Region and pass", f'{r["region"]}, {r["pass"]} pass'),
              ("Forecast points", elev or f'{r["elevation_ft"]:,} ft'),
              ("Snow station", f'{r["snotel_label"]} SNOTEL' if r.get("snotel_label") else "Resort report only"),
              ("Cams in the app", str(len(r.get("cams") or [])) if r.get("cams") else "Not yet")]
    sections.append(
        f'<section class="card" id="how"><h2 tabindex="-1">How the 0xSnow {escape(name)} report works</h2>'
        f'<p style="margin:0 0 8px">Before opening day, 0xSnow sends the {escape(name)} report at 7:00 AM. From opening day, '
        f'it goes out as soon as both the new grooming and that morning\'s snow report are in, and by 9:00 AM at the latest.</p>'
        f'<p style="margin:0">New snow, base and season totals come from the resort\'s own report when it posts, or the nearest '
        f'SNOTEL station otherwise. The forecast blends public weather models and the National Weather Service at base, '
        f'mid-mountain and summit, and is graded every day against what fell (see the <a href="/audit/{slug}">Snow Audit</a>).</p>'
        f'<table class="glance">' + "".join(f"<tr><td>{escape(k)}</td><td>{escape(v)}</td></tr>" for k, v in glance)
        + "</table></section>")

    aside = (pages._cta(slug, name)
             + f'<p class="src">Every fact links to the page it came from. '
               f'<a href="{pages.resort_path(slug, "guide")}.md">Markdown version</a></p>')

    words = covers(slug)
    h1 = f"{name} guide: " + _join((words[:3] + ["more"]) if len(words) > 4 else (words or ["snow report", "grooming"])) + " 2026/27"
    title = f"{name} " + _join(words or ["snow report", "grooming report times"]) + f" 2026/27 | {pages.ORG}"
    parts = ["Today's snow report", "blackout dates" if bo_html else None, "trail map" if tm else None,
             "cams" if r.get("cams") else None, "when grooming posts"]
    lead = f"{open_sentence} {_join([p for p in parts if p])}, each answer linked to the official page it came from."
    desc = f"{name} " + _join(words or ["snow report"]) + (
        " for 2026/27, each with its source and the date we checked it, plus today's snow report and when grooming posts.")
    body = (f'<p class="crumbs"><a href="/resorts">Resorts</a> › <a href="{report_url}">{escape(name)}</a> › Guide</p>'
            f'<h1 class="page">{escape(h1)}</h1><p class="lead">{escape(lead)}</p>'
            f'<article class="rp gd"><div class="hero">{snow}{hours}<div class="qa"><h2>Quick answers</h2>{answers}</div></div>'
            f'<div class="layout"><div>{"".join(sections)}</div><aside>{aside}</aside></div></article>')
    ld = [{"@context": "https://schema.org", "@type": "Article", "headline": h1,
           "url": pages.site(pages.resort_path(slug, "guide")), "author": pages._org(), "publisher": pages._org(),
           "dateModified": max((f.get("checked") or "" for f in kinds.values() if isinstance(f, dict)), default="")
           or None,
           "about": {"@type": "SkiResort", "name": name, "url": r["site"],
                     "geo": {"@type": "GeoCoordinates", "latitude": r["lat"], "longitude": r["lon"]}}},
          faq(slug, name, kinds, timing, today)]
    return title, desc, h1, body, ld
