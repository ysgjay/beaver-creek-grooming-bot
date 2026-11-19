"""Public, crawlable report pages (SEO): one page per resort plus a dated daily report archive.

  /resorts                      every resort, by state
  /resorts/<slug>               today's report (the Day Ticket, laid out for the web: bcbot/webreport.py)
  /resorts/<slug>/<YYYY-MM-DD>  that day's report, kept as an archive post
  /sitemap.xml                  home, the hub, every resort page and every post

The app itself draws everything with JavaScript, so search engines see no report text there.
These pages are plain HTML from the same stored day JSON (data/<slug>/days/<date>.json) that the
emails are built from. The archive index is data/<slug>/posts.json, appended on each daily send.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from html import escape

from . import config, mailer, report, resorts, webreport
from .store import resort_store

ORG = "0xSnow"
DISCLAIMER = "0xSnow is independent and not affiliated with Vail Resorts, Alterra or any resort."
MAX_POSTS = 400


def site(path=""):
    return f"{config.DASHBOARD_URL.rstrip('/')}/{path.lstrip('/')}"


def resort_path(slug, day_str=None):
    return f"/resorts/{slug}" + (f"/{day_str}" if day_str else "")


def valid_date(s):
    try:
        return date.fromisoformat(s).isoformat() == s
    except (TypeError, ValueError):
        return False


# ---------- archive index ----------

def post_dates(store, slug):
    """Dates with a report, newest first. Built once from the Blob listing when the index is missing."""
    rs = resort_store(slug, store)
    idx = rs.get_json("data/posts.json")
    if isinstance(idx, dict) and isinstance(idx.get("dates"), list):
        return idx["dates"]
    inner = rs.inner
    if not hasattr(inner, "list"):
        return []
    prefix = rs.path("data/days/")
    dates = sorted({p[len(prefix):-5] for p in inner.list(prefix) if p.endswith(".json")
                    and valid_date(p[len(prefix):-5])}, reverse=True)[:MAX_POSTS]
    try:
        rs.put_json("data/posts.json", {"dates": dates})
    except Exception:  # a read-only token must not break the page
        pass
    return dates


def add_post(store, slug, day_str, day=None, ping=True):
    """Record a sent report in the archive (called by the daily run). The day as it was sent is
    kept at data/posts/<date>.json, so the post stays the morning report while the day's data
    keeps refreshing. Then search engines are told the new URLs (IndexNow)."""
    rs = resort_store(slug, store)
    if day:
        rs.put_json(f"data/posts/{day_str}.json", day)
    dates = [d for d in post_dates(store, slug) if d != day_str]
    dates = sorted(dates + [day_str], reverse=True)[:MAX_POSTS]
    rs.put_json("data/posts.json", {"dates": dates})
    if ping:
        region = resorts.get(slug)["region"].lower()
        indexnow([site(resort_path(slug, day_str)), site(resort_path(slug)), site(resort_path(region)),
                  site("resorts"), site(f"resorts/{slug}/feed.xml")])
    return dates


def post_day(store, slug, day_str):
    """A post's day: the snapshot taken when it was sent, else the day file (older posts)."""
    rs = resort_store(slug, store)
    return rs.get_json(f"data/posts/{day_str}.json") or rs.get_json(f"data/days/{day_str}.json")


def latest_day(store, slug, dates=None):
    """What the resort page shows: today's sent report once it's out, else the latest data."""
    rs = resort_store(slug, store)
    latest = rs.get_json("data/latest.json")
    dates = dates if dates is not None else post_dates(store, slug)
    if dates and (not latest or latest.get("date") == dates[0]):
        return rs.get_json(f"data/posts/{dates[0]}.json") or latest
    return latest


# ---------- IndexNow: tell Bing (and Yandex, Seznam, Naver) about new URLs right away ----------

INDEXNOW_KEY = "a156955085e0f01a4754e933d5369d7f"  # public by design; served at /<key>.txt


def indexnow(urls):
    """Best effort, never raises. Only from production (previews have other hosts)."""
    import os
    from urllib.parse import urlsplit
    from .util import http
    if os.environ.get("VERCEL_ENV") != "production":
        return None
    host = urlsplit(site()).netloc
    try:
        r = http().post("https://api.indexnow.org/indexnow", timeout=10, json={
            "host": host, "key": INDEXNOW_KEY, "keyLocation": site(f"{INDEXNOW_KEY}.txt"), "urlList": urls})
        return r.status_code
    except Exception:
        return None


# ---------- words: a short plain summary that search engines can read ----------

def _n(x):
    return mailer._inch(x)


def summary(day):
    """3 to 5 plain sentences from the day's numbers. Nothing here is invented: every clause
    needs its number, and is left out when the number is missing."""
    name = report.resort_name(day)
    d = date.fromisoformat(day["date"])
    rs = day.get("resort") or {}
    fc = day.get("forecast") or {}
    runs = ((day.get("grooming") or {}).get("runs")) or {}
    groomed = mailer.groomed_runs(runs)
    out = []
    first = f"{name} grooming and snow report for {d.strftime('%A')} {report.mmdd(d)}"
    if groomed:
        first += f": {len(groomed)} runs groomed"
        top = runs.get("groomers_of_the_day") or groomed
        first += f", including {', '.join(top[:3])}"
    out.append(first + ".")
    r24 = mailer.new_snow(day)
    snow = []
    if r24 is not None:
        snow.append(f"{_n(r24)} of new snow in the last 24 hours")
    if rs.get("base_in") is not None:
        snow.append(f"{_n(rs['base_in'])} base")
    if rs.get("season_in") is not None:
        snow.append(f"{_n(rs['season_in'])} so far this season")
    if snow:
        out.append("The resort reports " + ", ".join(snow[:-1]) + (" and " if len(snow) > 1 else "") + snow[-1] + ".")
    if rs.get("updated_time"):
        out.append(f"The snow report posted at {rs['updated_time']}.")
    hrs = mailer.ski_hours(day)
    if hrs:
        h0, peak = hrs[0], max(hrs, key=lambda h: h.get("gust") or 0)
        s = f"Expect {h0['temp']}°F at {mailer._clock(h0['time'])}, feeling like {h0['feels']}°"
        if peak.get("gust"):
            s += f", with gusts to {peak['gust']} mph around {mailer._clock(peak['time'])}"
        out.append(s + ".")
    if fc.get("next_1_5") is not None:
        lo, hi = (fc.get("next_1_5_range") or [None, None])[:2]
        if lo is not None and hi is not None and hi > lo:
            out.append(f"The next 5 days look like {_n(lo).rstrip(chr(34))} to {_n(hi)} of snow, most likely {_n(fc['next_1_5'])}.")
        else:
            out.append(f"The next 5 days look like {_n(fc['next_1_5'])} of snow.")
    return out


def title(day, dated):
    name = report.resort_name(day)
    when = report.mmdd(day["date"])
    return (f"{name} grooming report and snow forecast, {when}" if dated
            else f"{name} grooming report today and snow forecast") + f" | {ORG}"


def description(day):
    return " ".join(summary(day))[:300]


# ---------- page shell ----------

THEME = """
:root{--bg:#dcebfa;--paper:#f5f9fc;--surface:#ffffff;--edge:#ffffff;--ink:#0c2a4a;--ink2:#52677b;--line:#c3d3e0;
--action:#365c7d;--btn:#7b1e2e;--btn-hover:#651826;--accent-soft:#f2e6e9;--accent-ink:#7b1e2e;--chip-line:#e3c9cf;--snow:#376f9b;
--tile-line:#dce8f2;--bar:#dcebfaee;--shadow:inset 0 1px 0 #fff,0 8px 24px rgba(12,42,74,.07),0 1px 3px rgba(12,42,74,.04);
--glow:radial-gradient(ellipse at 15% 0%,#ffffffd9,transparent 48%),linear-gradient(145deg,#eef5fc,#dcebfa 65%,#e8f1fa);color-scheme:light}
html[data-appearance="dark"]{--bg:#071b2e;--paper:#102a40;--surface:#18384f;--edge:#365870;--ink:#e7f2fc;--ink2:#a9bfd2;--line:#32516a;
--action:#b8dcf6;--btn:#8b2941;--btn-hover:#a13a53;--accent-soft:#402437;--accent-ink:#f0bfca;--chip-line:#6b3a4c;--snow:#8dc4eb;
--tile-line:#32516a;--bar:#0b2135f2;--shadow:inset 0 1px 0 #c5e8ff12,0 8px 24px #00000024,0 1px 3px #00000018;
--glow:radial-gradient(ellipse at 15% 0%,#24517166,transparent 48%),linear-gradient(145deg,#0b243b,#071b2e 65%,#0c2940);color-scheme:dark}
@media (prefers-color-scheme:dark){html:not([data-appearance]){--bg:#071b2e;--paper:#102a40;--surface:#18384f;--edge:#365870;--ink:#e7f2fc;--ink2:#a9bfd2;--line:#32516a;
--action:#b8dcf6;--btn:#8b2941;--btn-hover:#a13a53;--accent-soft:#402437;--accent-ink:#f0bfca;--chip-line:#6b3a4c;--snow:#8dc4eb;
--tile-line:#32516a;--bar:#0b2135f2;--shadow:inset 0 1px 0 #c5e8ff12,0 8px 24px #00000024,0 1px 3px #00000018;
--glow:radial-gradient(ellipse at 15% 0%,#24517166,transparent 48%),linear-gradient(145deg,#0b243b,#071b2e 65%,#0c2940);color-scheme:dark}}
html[data-appearance="dark"] :is(ol.days .v,table.hours td.g span){color:#e7f2fc;box-shadow:inset 0 0 0 99px rgba(7,27,46,.6)}
"""

CSS = THEME + f"""
@font-face{{font-family:Outfit;src:url(/brand/fonts/outfit.woff2) format('woff2');font-weight:100 900;font-display:swap}}
@font-face{{font-family:'IBM Plex Sans';src:url(/brand/fonts/plex-sans.woff2) format('woff2');font-weight:100 700;font-display:swap}}
@font-face{{font-family:'IBM Plex Mono';src:url(/brand/fonts/plex-mono.woff2) format('woff2');font-weight:400;font-display:swap}}
body{{margin:0;background-color:var(--bg);background-image:var(--glow);min-height:100vh;color:var(--ink);font:16px/1.55 {mailer.SANS}}}
.wrap{{max-width:680px;margin:0 auto;padding:14px 16px 32px}}
a{{color:var(--action)}}
.topbar{{position:sticky;top:0;z-index:5;background:var(--bar);border-bottom:1px solid var(--line);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px)}}
.top{{display:flex;align-items:center;gap:10px;max-width:1040px;margin:0 auto;padding:10px 16px}}
.top .where{{color:var(--ink2);font:500 15px/1 {mailer.SANS};white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.top a{{display:flex;align-items:center;gap:8px;text-decoration:none;color:var(--ink);font:600 17px/1 {mailer.DISPLAY}}}
.top .app{{margin-left:auto;flex:none;background:var(--btn);color:#fff;padding:10px 14px;border-radius:12px;font:600 14px/1 {mailer.SANS}}}
.top .app:hover,.cta a.btn:hover,.actions a.btn:hover{{background:var(--btn-hover)}}
.wrap>.crumbs:first-child{{margin-top:16px}}
h1.page{{font:600 26px/1.2 {mailer.DISPLAY};margin:0 0 6px}}
.lead{{margin:0 0 14px;color:var(--ink)}}
.crumbs{{font-size:13px;color:var(--ink2);margin:0 0 6px}}
h2{{font:600 18px/1.3 {mailer.DISPLAY};margin:22px 0 8px}}
ul.dates{{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:6px}}
ul.dates a{{display:inline-block;padding:4px 10px;border-radius:8px;background:var(--paper);border:1px solid var(--line);text-decoration:none;color:var(--ink);font:400 13px {mailer.MONO}}}
ul.list{{padding-left:18px}}
.cta{{background:var(--paper);border:1px solid var(--edge);border-radius:20px;padding:16px;margin:16px 0}}
.cta a.btn{{background:var(--btn);color:#fff;text-decoration:none;padding:12px 18px;border-radius:12px;font-weight:600;display:inline-block}}
footer{{margin-top:26px;font-size:12px;color:var(--ink2)}}
""" + webreport.CSS


def _ld(obj):
    data = json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{data}</script>'


def shell(*, page_title, desc, canonical, body, ld=None, image=None, noindex=False, feed=None, wide=False,
          app_href="/", where=None, markdown=None):
    image = image or site("brand/share-1200x630.png")
    meta = [
        f"<title>{escape(page_title)}</title>",
        f'<meta name="description" content="{escape(desc)}">',
        f'<link rel="canonical" href="{escape(canonical)}">',
        '<meta property="og:type" content="article">',
        f'<meta property="og:site_name" content="{ORG}">',
        f'<meta property="og:title" content="{escape(page_title)}">',
        f'<meta property="og:description" content="{escape(desc)}">',
        f'<meta property="og:url" content="{escape(canonical)}">',
        f'<meta property="og:image" content="{escape(image)}">',
        '<meta name="twitter:card" content="summary_large_image">',
    ]
    if noindex:
        meta.append('<meta name="robots" content="noindex">')
    feed = feed or ("/feed.xml", f"{ORG} daily reports")
    meta.append(f'<link rel="alternate" type="application/rss+xml" title="{escape(feed[1])}" href="{feed[0]}">')
    if markdown:
        meta.append(f'<link rel="alternate" type="text/markdown" title="Markdown version" href="{markdown}">')
    meta.append('<link rel="alternate" type="text/plain" title="Guide for AI assistants" href="/llms.txt">')
    lds = "".join(_ld(x) for x in (ld or []))
    where_html = f'<span class="where">/ {escape(where)}</span>' if where else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{chr(10).join(meta)}
<meta name="theme-color" content="{mailer.ICE}">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<script src="/appearance.js"></script>
<style>{CSS}</style>{lds}</head>
<body><header class="topbar"><div class="top"><a href="/"><img src="/brand/frosted-logo-email.png" width="36" height="36" alt="">{ORG}</a>
{where_html}<a class="app" href="{escape(app_href)}">Open in the app</a></div></header>
<div class="wrap{' wide' if wide else ''}">
{body}
<footer><p>{DISCLAIMER} Grooming and snow totals come from each resort's own reports. Forecast data by
Open-Meteo.com (CC BY 4.0), NWS and NRCS SNOTEL.</p>
<p><a href="/resorts">All resorts</a> · <a href="/">0xSnow app</a> · <a href="/#help">Help</a> · <a href="/llms.txt">For AI assistants</a>{f' · <a href="{markdown}">Markdown version</a>' if markdown else ""}</p></footer>
</div></body></html>"""


def _cta(slug, name):
    return (f'<div class="cta"><p style="margin:0 0 10px"><b>Get the {escape(name)} report every morning.</b> '
            f'Free email or app notification, once a day, when the new grooming map and snow report are in.</p>'
            f'<a class="btn" href="/?resort={slug}">Sign up free</a></div>')


def _org():
    return {"@type": "Organization", "name": ORG, "url": site(), "logo": site("brand/app-icon-dark-512.png")}


# ---------- pages ----------

def resort_page(slug, day, dates, dated=False):
    """Today's report (dated=False) or an archive post. `day` is the stored day JSON."""
    r = resorts.get(slug)
    name = r["name"]
    day = dict(day, resort_name=day.get("resort_name") or name, resort_slug=slug)
    day_str = day["date"]
    g = day.get("grooming") or {}
    map_url = site(g["image"]) if g.get("image") else None
    canonical = site(resort_path(slug, day_str if dated else None))
    t = title(day, dated)
    desc = description(day)
    words = summary(day)
    d = date.fromisoformat(day_str)
    h1 = (f"{name} grooming report, {d.strftime('%a')} {report.mmdd(d)}" if dated
          else f"{name} grooming report and snow forecast")
    crumbs = (f'<p class="crumbs"><a href="/resorts">Resorts</a> › <a href="{resort_path(slug)}">{escape(name)}</a>'
              + (f" › {report.mmdd(d)}" if dated else "") + "</p>")
    others = [x for x in dates if x != day_str][:60]
    past = ("<h2>Past reports</h2><ul class=\"dates\">" + "".join(
        f'<li><a href="{resort_path(slug, x)}">{date.fromisoformat(x).strftime("%a")} {report.mmdd(x)}</a></li>'
        for x in others) + "</ul>") if others else ""
    body = (crumbs + f'<h1 class="page">{escape(h1)}</h1>'
            + f'<p class="lead">{escape(" ".join(words))}</p>'
            + webreport.render(day, map_url)
            + _cta(slug, name) + past + _more(slug, name))
    article = {
        "@context": "https://schema.org", "@type": "BlogPosting" if dated else "WebPage",
        "headline": h1, "description": desc, "url": canonical, "inLanguage": "en-US",
        "datePublished": (day.get("delivery") or {}).get("sent_at") or day.get("generated") or day_str,
        "dateModified": day.get("generated") or day_str,
        "author": _org(), "publisher": _org(),
        "about": {"@type": "SkiResort", "name": name, "address": {"@type": "PostalAddress", "addressRegion": r["region"],
                                                                 "addressCountry": "US"},
                  "geo": {"@type": "GeoCoordinates", "latitude": r["lat"], "longitude": r["lon"]}},
    }
    if map_url:
        article["image"] = map_url
    crumbs_ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Resorts", "item": site("resorts")},
        {"@type": "ListItem", "position": 2, "name": name, "item": site(resort_path(slug))}]
        + ([{"@type": "ListItem", "position": 3, "name": report.mmdd(d), "item": canonical}] if dated else [])}
    return shell(page_title=t, desc=desc, canonical=canonical, body=body, ld=[article, crumbs_ld], image=map_url,
                 feed=(f"/resorts/{slug}/feed.xml", f"{name} daily reports"), wide=True,
                 where=name, app_href=f"/?resort={slug}",
                 markdown=f"/resorts/{slug}/{day_str}.md" if dated else f"/resorts/{slug}.md")


def empty_resort_page(slug):
    """No report stored yet (a resort just added): a thin page that asks not to be indexed."""
    name = resorts.get(slug)["name"]
    body = (f'<p class="crumbs"><a href="/resorts">Resorts</a> › {escape(name)}</p>'
            f'<h1 class="page">{escape(name)} grooming report and snow forecast</h1>'
            f'<p class="lead">The first {escape(name)} report is on its way. It posts each morning once the resort\'s '
            f'grooming and snow report are in.</p>' + _cta(slug, name))
    return shell(page_title=f"{name} grooming report and snow forecast | {ORG}",
                 desc=f"Daily {name} grooming report, new snow and forecast.", canonical=site(resort_path(slug)),
                 body=body, noindex=True)


def hub_page():
    groups = {}
    for slug in resorts.enabled():
        r = resorts.get(slug)
        groups.setdefault(r["region"], []).append(r)
    body = ('<h1 class="page">Ski resort grooming reports for Colorado and Utah</h1>'
            '<p class="lead">A short report for each resort every morning: what was groomed, new snow, base, '
            'the weather from first chair to last and the snow forecast. Free, and updated daily.</p>')
    for region in sorted(groups):
        body += (f"<h2>{escape(region)}</h2><p style=\"margin:0 0 6px\"><a href=\"{resort_path(region.lower())}\">"
                 f"{escape(region)} snow report today: every resort in one table</a></p><ul class=\"list\">") + "".join(
            f'<li><a href="{resort_path(r["slug"])}">{escape(r["name"])} grooming report</a> '
            f'<span style="color:var(--ink2);font-size:13px">({escape(r["pass"])} pass)</span></li>'
            for r in sorted(groups[region], key=lambda r: r["name"])) + "</ul>"
    body += _cta(resorts.DEFAULT, "morning")
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Ski resort grooming reports",
          "url": site("resorts"), "publisher": _org(), "hasPart": [
              {"@type": "WebPage", "name": f'{resorts.get(s)["name"]} grooming report', "url": site(resort_path(s))}
              for s in resorts.enabled()]}
    return shell(page_title=f"Colorado and Utah ski resort grooming reports, daily | {ORG}",
                 desc="Daily grooming reports, new snow, base depth and snow forecasts for 22 Colorado and Utah "
                      "ski resorts on the Epic and Ikon passes.",
                 canonical=site("resorts"), body=body, ld=[ld])


def sitemap(store):
    slugs = resorts.enabled()

    def dates(s):
        try:
            return s, post_dates(store, s)
        except Exception:
            return s, []

    with ThreadPoolExecutor(max_workers=8) as pool:
        by = dict(pool.map(dates, slugs))
    urls = [(site(), None, "daily"), (site("resorts"), None, "daily")]
    urls += [(site(resort_path(r)), None, "daily") for r in REGIONS]
    for s in slugs:
        ds = by.get(s) or []
        urls.append((site(resort_path(s)), ds[0] if ds else None, "daily"))
        urls.append((site(resort_path(s, "guide")), None, "weekly"))
        urls += [(site(resort_path(s, d)), d, "never") for d in ds]
    rows = "".join(f"<url><loc>{escape(u)}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "")
                   + f"<changefreq>{f}</changefreq></url>" for u, m, f in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>')


def _more(slug, name):
    region = resorts.get(slug)["region"]
    return (f'<h2>More for {escape(name)}</h2><ul class="list">'
            f'<li><a href="{resort_path(slug, "guide")}">{escape(_guide_label(slug, name))}</a></li>'
            f'<li><a href="{resort_path(region.lower())}">{escape(region)} snow report today</a></li>'
            f'<li><a href="/resorts/{slug}/feed.xml">RSS feed of {escape(name)} reports</a></li></ul>')


# ---------- state pages: every resort in one table ----------

REGIONS = {"colorado": "Colorado", "utah": "Utah"}


def _row(slug, day):
    day = day or {}
    rs = day.get("resort") or {}
    runs = ((day.get("grooming") or {}).get("runs")) or {}
    fc = day.get("forecast") or {}
    return {"slug": slug, "name": resorts.get(slug)["name"], "pass": resorts.get(slug)["pass"],
            "date": day.get("date"), "new": mailer.new_snow(day) if day else None, "base": rs.get("base_in"),
            "groomed": len(mailer.groomed_runs(runs)) or None, "next5": fc.get("next_1_5"),
            "posted": rs.get("updated_time")}


def region_rows(store, region):
    slugs = [s for s in resorts.enabled() if resorts.get(s)["region"].lower() == region]

    def one(s):
        try:
            return _row(s, latest_day(store, s))
        except Exception:
            return _row(s, None)

    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(one, slugs))
    return sorted(rows, key=lambda r: (-(r["new"] or 0), -(r["next5"] or 0), r["name"]))


def region_page(store, region, today=None):
    label = REGIONS[region]
    rows = region_rows(store, region)
    today = today or max((r["date"] for r in rows if r["date"]), default=date.today().isoformat())
    d = date.fromisoformat(today)
    fresh = [r for r in rows if r["date"] == today]
    top = [r for r in fresh if (r["new"] or 0) >= 0.1][:3]
    lead = f"{label} ski resort snow report for {d.strftime('%A')} {report.mmdd(d)}, {len(rows)} resorts in one table."
    if top:
        lead += " Most new snow: " + ", ".join(f'{r["name"]} {_n(r["new"])}' for r in top) + "."
    big = sorted(fresh, key=lambda r: -(r["next5"] or 0))[:1]
    if big and (big[0]["next5"] or 0) >= 1:
        lead += f' Biggest 5-day forecast: {big[0]["name"]}, {_n(big[0]["next5"])}.'
    cell = 'style="padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;font-family:\'IBM Plex Mono\',monospace;font-size:13px"'
    head = 'style="padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;font-size:12px;color:var(--ink2)"'
    trs = ""
    for r in rows:
        stale = "" if r["date"] == today else ' style="opacity:.6"'
        trs += (f"<tr{stale}><td style=\"padding:6px 8px;border-bottom:1px solid var(--line)\"><a href=\"{resort_path(r['slug'])}\">"
                f"{escape(r['name'])}</a> <span style=\"font-size:11px;color:var(--ink2)\">{escape(r['pass'])}</span></td>"
                f"<td {cell}>{_n(r['new'])}</td><td {cell}>{_n(r['base'])}</td>"
                f"<td {cell}>{r['groomed'] if r['groomed'] is not None else '–'}</td><td {cell}>{_n(r['next5'])}</td></tr>")
    table = (f'<div style="overflow-x:auto;background:var(--paper);border:1px solid var(--edge);border-radius:20px;padding:8px">'
             f'<table style="width:100%;border-collapse:collapse"><thead><tr>'
             f'<th style="padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;font-size:12px;color:var(--ink2)">Resort</th>'
             f'<th {head}>New 24 hr</th><th {head}>Base</th><th {head}>Groomed</th><th {head}>Next 5 days</th></tr></thead>'
             f'<tbody>{trs}</tbody></table></div>'
             f'<p style="font-size:12px;color:var(--ink2)">Sorted by new snow. Groomed counts only where the resort publishes '
             f'groomed runs. Faded rows have no report for {report.mmdd(d)} yet. Updated through the morning.</p>')
    other = [k for k in REGIONS if k != region]
    body = (f'<p class="crumbs"><a href="/resorts">Resorts</a> › {label}</p>'
            f'<h1 class="page">{label} snow report today</h1><p class="lead">{escape(lead)}</p>{table}'
            + _cta(resorts.DEFAULT, "morning")
            + "".join(f'<p><a href="{resort_path(o)}">{REGIONS[o]} snow report today</a></p>' for o in other))
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": f"{label} snow report today",
          "url": site(resort_path(region)), "dateModified": today, "publisher": _org(), "description": lead}
    return shell(page_title=f"{label} snow report today: new snow and grooming at {len(rows)} resorts | {ORG}",
                 desc=lead[:300], canonical=site(resort_path(region)), body=body, ld=[ld], where=label,
                 markdown=f"/resorts/{region}.md")


# ---------- RSS ----------

def _rfc822(day_str, hhmm="07:00"):
    from datetime import datetime
    from email.utils import format_datetime
    from zoneinfo import ZoneInfo
    h, m = (int(x) for x in hhmm.split(":"))
    return format_datetime(datetime.fromisoformat(day_str).replace(hour=h, minute=m, tzinfo=ZoneInfo("America/Denver")))


def feed_xml(store, slug=None):
    """One resort's posts (newest 30), or every resort's newest post."""
    if slug:
        name = resorts.get(slug)["name"]
        items = [(slug, d) for d in post_dates(store, slug)[:30]]
        title, link = f"{name} grooming report | {ORG}", site(resort_path(slug))
        desc = f"Daily {name} grooming report, new snow and forecast."
    else:
        def newest(s):
            try:
                ds = post_dates(store, s)
                return (s, ds[0]) if ds else None
            except Exception:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            items = sorted(filter(None, pool.map(newest, resorts.enabled())), key=lambda x: x[1], reverse=True)
        title, link = f"{ORG} daily ski reports, Colorado and Utah", site("resorts")
        desc = "The newest daily grooming and snow report for every resort 0xSnow covers."
    out = ""
    for s, d in items:
        n = resorts.get(s)["name"]
        dd = date.fromisoformat(d)
        url = site(resort_path(s, d))
        out += (f"<item><title>{escape(n)} grooming report, {dd.strftime('%a')} {report.mmdd(dd)}</title>"
                f"<link>{url}</link><guid isPermaLink=\"true\">{url}</guid><pubDate>{_rfc822(d)}</pubDate>"
                f"<description>{escape(f'{n} grooming, new snow, weather and forecast for {report.mmdd(dd)}.')}</description></item>")
    self_url = site(f"resorts/{slug}/feed.xml" if slug else "feed.xml")
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
            f"<title>{escape(title)}</title><link>{link}</link><description>{escape(desc)}</description>"
            f'<atom:link href="{self_url}" rel="self" type="application/rss+xml"/><language>en-us</language>'
            f"{out}</channel></rss>")


# ---------- evergreen guide per resort ----------

def posting_times(summary, slug):
    """Median first morning change (3 to 10 AM, Mountain time) per source, from the posting-time study."""
    from statistics import median
    first = {}
    for c in (summary or {}).get("changes") or []:
        if c.get("resort") != slug or not c.get("at") or not ("03:00" <= c["at"] <= "10:00"):
            continue
        key = (c.get("source"), c.get("day"))
        if key not in first or c["at"] < first[key]:
            first[key] = c["at"]
    out = {}
    for source in ("grooming", "snow"):
        mins = [int(t[:2]) * 60 + int(t[3:]) for (src, _), t in first.items() if src == source]
        if mins:
            m = round(median(mins))
            h = m // 60
            out[source] = {"time": f"{(h % 12) or 12}:{m % 60:02d} {'AM' if h < 12 else 'PM'}", "days": len(mins)}
    return out


def guide_page(slug, summary=None):
    r = resorts.get(slug)
    name = r["name"]
    times = posting_times(summary, slug)
    if r.get("grooming_pdf"):
        groom = (f"{name} publishes a grooming map each night as a PDF. 0xSnow reads the run names off that map "
                 "and shows the full map in the morning report.")
    elif r.get("dor_api"):
        groom = f"{name} publishes groomed runs in its trail status feed. 0xSnow lists every groomed run from it."
    else:
        groom = (f"0xSnow doesn't read {name}'s grooming yet, so its report covers snow, weather and the forecast. "
                 "Grooming will be added when a public source is checked.")
    when = []
    if "grooming" in times:
        when.append(f'the grooming update usually lands around {times["grooming"]["time"]}')
    if "snow" in times:
        when.append(f'the official snow report usually updates around {times["snow"]["time"]}')
    days = max([t["days"] for t in times.values()], default=0)
    timing = (f"In 0xSnow's posting-time study ({days} morning{'s' if days != 1 else ''} since 11/16), " + " and ".join(when) + " Mountain time."
              if when else f"0xSnow is still measuring when {name} posts its morning updates; times will appear here.")
    bands = {b["key"]: b for b in r.get("bands") or []}
    elev = ", ".join(f'{k} {bands[k]["elevation_ft"]:,} ft' for k in ("base", "mid", "peak") if k in bands)
    opening = r["opening_day"]
    facts = [
        ("Region and pass", f'{r["region"]}, {r["pass"]} pass'),
        ("Opening day" if opening <= date.today() else "Scheduled opening", f"{opening.strftime('%a')} {report.mmdd(opening)}"),
        ("Forecast points", elev or f'{r["elevation_ft"]:,} ft'),
        ("Snow station", f'{r["snotel_label"]} SNOTEL' if r.get("snotel_label") else "Resort report only"),
        ("Cams in the app", str(len(r.get("cams") or [])) if r.get("cams") else "Not yet"),
    ]
    rows = "".join(f'<tr><td style="padding:6px 8px;border-bottom:1px solid var(--line);color:var(--ink2)">{escape(k)}</td>'
                   f'<td style="padding:6px 8px;border-bottom:1px solid var(--line)">{escape(v)}</td></tr>' for k, v in facts)
    info, faq = _facts_section(slug, name)
    if info:
        facts = [f for f in facts if f[0] not in ("Opening day", "Scheduled opening")]
        rows = "".join(f'<tr><td style="padding:6px 8px;border-bottom:1px solid var(--line);color:var(--ink2)">{escape(k)}</td>'
                       f'<td style="padding:6px 8px;border-bottom:1px solid var(--line)">{escape(v)}</td></tr>' for k, v in facts)
    h1 = (f"{name}: hours, opening and closing day, trail map" if info
          else f"How the {name} grooming and snow report works")
    body = (f'<p class="crumbs"><a href="/resorts">Resorts</a> › <a href="{resort_path(slug)}">{escape(name)}</a> › Guide</p>'
            f'<h1 class="page">{escape(h1)}</h1>'
            f'<p class="lead">Everything 0xSnow knows about when and how {escape(name)} reports grooming and snow, '
            f'and how the daily 0xSnow report is put together. <a href="{resort_path(slug)}">See today\'s report</a>.</p>'
            + info +
            f'<h2>When the report posts</h2><p>{escape(timing)}</p>'
            f'<p>Before opening day, 0xSnow sends the {escape(name)} report at 7:00 AM. From opening day, it goes out as '
            f'soon as both the new grooming and that morning\'s snow report are in, and by 9:00 AM at the latest.</p>'
            f'<h2>Grooming</h2><p>{escape(groom)}</p>'
            f'<h2>Snow totals and forecast</h2><p>New snow, base and season totals come from the resort\'s own report when '
            f'it posts, or the nearest SNOTEL station otherwise. The forecast blends public weather models and the '
            f'National Weather Service at base, mid-mountain and summit, and is graded every day against what fell '
            f'(see the <a href="/audit/{slug}">Snow Audit</a>).</p>'
            f'<h2>At a glance</h2><div style="background:var(--paper);border:1px solid var(--edge);border-radius:20px;padding:8px">'
            f'<table style="width:100%;border-collapse:collapse;font-size:14px">{rows}</table></div>'
            + _cta(slug, name))
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": f"How the {name} grooming and snow report works",
          "url": site(resort_path(slug, "guide")), "author": _org(), "publisher": _org(),
          "about": {"@type": "SkiResort", "name": name}}
    if info:
        ld["headline"] = h1
    title = (f"{name} hours, opening day, closing day and trail map | {ORG}" if info
             else f"When does the {name} grooming report come out? | {ORG}")
    desc = (f"{name} lift hours, opening and closing day, trail map, pass blackout dates, lift ticket prices and "
            f"lessons, each with its source and the date we checked it." if info else
            f"When {name} posts its grooming and snow report each morning, where the numbers come from, "
            f"and how to get the {name} report free every day.")
    return shell(page_title=title, desc=desc,
                 canonical=site(resort_path(slug, "guide")), body=body, ld=[ld] + ([faq] if faq else []),
                 feed=(f"/resorts/{slug}/feed.xml", f"{name} daily reports"), where=name, app_href=f"/?resort={slug}",
                 markdown=f"/resorts/{slug}/guide.md")


def _fact_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.strftime('%A')} {report.mmdd(d)}/{d.year}"


def _facts_section(slug, name, today=None):
    """Hours, dates and trail map with a source and checked date on each. ('', None) if none."""
    from . import facts as F
    kinds = F.FACTS.get(slug)
    if not kinds:
        return "", None
    today = today or date.today()
    items, more, qa = "", "", []
    for kind in ("opening_day", "closing_day", "lift_hours", "trail_map", "passes", "blackout_dates", "lift_tickets", "lessons"):
        f = kinds.get(kind)
        if not f:
            continue
        v = f.get("value")
        if kind in ("opening_day", "closing_day"):
            said = _fact_date(v) if v else "Not announced yet"
            q = f"When {'does' if not v or date.fromisoformat(v) >= today else 'did'} {name} " \
                f"{'open' if kind == 'opening_day' else 'close'} for the 2026/27 season?"
            ans = (f"{name} {'opens' if kind == 'opening_day' else 'closes'} on {said}." if v
                   else f"{name} hasn't announced its {'opening' if kind == 'opening_day' else 'closing'} day yet.")
            if v and date.fromisoformat(v) < today:
                ans = f"{name} {'opened' if kind == 'opening_day' else 'closed'} on {said}."
            shown = escape(said)
        elif kind == "lift_hours":
            q, ans = f"What are {name}'s lift hours?", (v or f.get("note") or "Not posted yet.")
            shown = escape(v or "Not posted yet")
        elif kind == "trail_map":
            q, ans = f"Where is the {name} trail map?", f"The official map is on the resort's site: {v}"
            shown = f'<a href="{escape(v)}" rel="nofollow">{escape(f.get("label") or "Official trail map")}</a>'
        else:
            q = {"passes": f"Which ski passes work at {name}?",
                 "blackout_dates": f"What are the {name} blackout dates for 2026/27?",
                 "lift_tickets": f"How much is a lift ticket at {name}?",
                 "lessons": f"What ski and snowboard lessons does {name} offer?"}[kind]
            ans = v or f.get("note") or "Not posted yet."
            shown = escape(v or "No fixed price posted")
        note = f'<div style="font-size:13px;margin-top:2px">{escape(f["note"])}</div>' if f.get("note") and v else ""
        if f.get("note") and not v and kind != "lift_hours":
            note = f'<div style="font-size:13px;margin-top:2px">{escape(f["note"])}</div>'
        flag = ' · <b style="color:var(--accent-ink)">re-checking</b>' if F.stale(f, kind, today) else ""
        row = (f'<div style="padding:10px 4px;border-bottom:1px solid var(--line)">'
                  f'<div style="font:600 11px/1.3 \'IBM Plex Mono\',monospace;letter-spacing:.05em;text-transform:uppercase;color:var(--ink2)">{F.LABELS[kind]}</div>'
                  f'<div style="font-size:16px;margin-top:2px">{shown}</div>{note}'
                  f'<div style="font-size:12px;color:var(--ink2);margin-top:4px">Source: <a href="{escape(f["source"])}" rel="nofollow">'
                  f'{escape(f.get("source_name") or f["source"])}</a> · checked {report.mmdd(f["checked"])}{flag}</div></div>')
        if kind in ("passes", "blackout_dates", "lift_tickets", "lessons"):
            more += row
        else:
            items += row
        qa.append({"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": ans}})
    box = '<div style="background:var(--paper);border:1px solid var(--edge);border-radius:20px;padding:6px 12px">{}</div>'
    html_ = (f'<h2>Hours, dates and trail map</h2>' + box.format(items)
             + (f'<h2>Passes, tickets and lessons</h2>' + box.format(more) if more else "")
             + f'<p style="font-size:12px;color:var(--ink2)">Every fact links to the resort page it came from. Dates and hours '
             f'can change with conditions and prices change by date, so check the source before you go. 0xSnow re-checks '
             f'closing dates, passes and blackout dates every 2 days from March, opening dates every 2 days in the fall '
             f'and ticket prices weekly in season.</p>')
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": qa}
    return html_, faq


def _guide_label(slug, name):
    from . import facts as F
    return (f"{name} hours, opening and closing day, trail map" if slug in F.FACTS
            else f"How the {name} grooming and snow report works")
