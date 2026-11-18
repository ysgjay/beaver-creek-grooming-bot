"""Public, crawlable report pages (SEO): one page per resort plus a dated daily report archive.

  /resorts                      every resort, by state
  /resorts/<slug>               today's report (the single-resort Day Ticket email, as a web page)
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

from . import config, mailer, report, resorts
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


def add_post(store, slug, day_str):
    """Record a sent report in the archive index (called by the daily run)."""
    dates = [d for d in post_dates(store, slug) if d != day_str]
    dates = sorted(dates + [day_str], reverse=True)[:MAX_POSTS]
    resort_store(slug, store).put_json("data/posts.json", {"dates": dates})
    return dates


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

CSS = f"""
@font-face{{font-family:Outfit;src:url(/brand/fonts/outfit.woff2) format('woff2');font-weight:100 900;font-display:swap}}
@font-face{{font-family:'IBM Plex Sans';src:url(/brand/fonts/plex-sans.woff2) format('woff2');font-weight:100 700;font-display:swap}}
@font-face{{font-family:'IBM Plex Mono';src:url(/brand/fonts/plex-mono.woff2) format('woff2');font-weight:400;font-display:swap}}
body{{margin:0;background:{mailer.ICE};color:{mailer.INK};font:16px/1.55 {mailer.SANS}}}
.wrap{{max-width:680px;margin:0 auto;padding:14px 16px 32px}}
a{{color:{mailer.QUIET}}}
.top{{display:flex;align-items:center;gap:10px;margin:4px 0 14px}}
.top a{{display:flex;align-items:center;gap:8px;text-decoration:none;color:{mailer.INK};font:600 17px/1 {mailer.DISPLAY}}}
.top .app{{margin-left:auto;background:{mailer.BURGUNDY};color:#fff;padding:9px 14px;border-radius:12px;font:600 14px/1 {mailer.SANS}}}
h1.page{{font:600 26px/1.2 {mailer.DISPLAY};margin:0 0 6px}}
.lead{{margin:0 0 14px;color:{mailer.INK}}}
.crumbs{{font-size:13px;color:{mailer.INK2};margin:0 0 6px}}
h2{{font:600 18px/1.3 {mailer.DISPLAY};margin:22px 0 8px}}
ul.dates{{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:6px}}
ul.dates a{{display:inline-block;padding:4px 10px;border-radius:8px;background:{mailer.FROST};border:1px solid {mailer.LINE};text-decoration:none;color:{mailer.INK};font:400 13px {mailer.MONO}}}
ul.list{{padding-left:18px}}
.cta{{background:{mailer.FROST};border:1px solid #fff;border-radius:20px;padding:16px;margin:16px 0}}
.cta a.btn{{background:{mailer.BURGUNDY};color:#fff;text-decoration:none;padding:12px 18px;border-radius:12px;font-weight:600;display:inline-block}}
footer{{margin-top:26px;font-size:12px;color:{mailer.INK2}}}
"""


def _ld(obj):
    data = json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{data}</script>'


def shell(*, page_title, desc, canonical, body, ld=None, image=None, noindex=False):
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
    lds = "".join(_ld(x) for x in (ld or []))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{chr(10).join(meta)}
<meta name="theme-color" content="{mailer.ICE}">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<style>{CSS}</style>{lds}</head>
<body><div class="wrap">
<header class="top"><a href="/"><img src="/brand/frosted-logo-email.png" width="36" height="36" alt="">{ORG}</a>
<a class="app" href="/">Open the app</a></header>
{body}
<footer><p>{DISCLAIMER} Grooming and snow totals come from each resort's own reports. Forecast data by
Open-Meteo.com (CC BY 4.0), NWS and NRCS SNOTEL.</p>
<p><a href="/resorts">All resorts</a> · <a href="/">0xSnow app</a> · <a href="/#help">Help</a></p></footer>
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
            + mailer.daily_html(day, map_url, hidden_preheader=False)
            + _cta(slug, name) + past)
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
    return shell(page_title=t, desc=desc, canonical=canonical, body=body, ld=[article, crumbs_ld], image=map_url)


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
        body += f"<h2>{escape(region)}</h2><ul class=\"list\">" + "".join(
            f'<li><a href="{resort_path(r["slug"])}">{escape(r["name"])} grooming report</a> '
            f'<span style="color:{mailer.INK2};font-size:13px">({escape(r["pass"])} pass)</span></li>'
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
    for s in slugs:
        ds = by.get(s) or []
        urls.append((site(resort_path(s)), ds[0] if ds else None, "daily"))
        urls += [(site(resort_path(s, d)), d, "never") for d in ds]
    rows = "".join(f"<url><loc>{escape(u)}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "")
                   + f"<changefreq>{f}</changefreq></url>" for u, m, f in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>')
