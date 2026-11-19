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

from . import config, guide as guide_mod, mailer, report, resorts, webreport
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
    first = f"{name} snow report for {d.strftime('%A')} {report.mmdd(d)}"
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
    """Lead with "<Resort> snow report": it gets ~100x the searches of "grooming report" (docs/SEO.md)."""
    name = report.resort_name(day)
    when = report.mmdd(day["date"])
    return (f"{name} snow report {when}: grooming and new snow" if dated
            else f"{name} snow report today ({when}): grooming and forecast") + f" | {ORG}"


def description(day):
    return " ".join(summary(day))[:300]


# ---------- page shell ----------

THEME = """
:root{--bg:#dcebfa;--paper:#f5f9fc;--surface:#ffffff;--edge:#ffffff;--ink:#0c2a4a;--ink2:#52677b;--line:#c3d3e0;
--action:#365c7d;--btn:#7b1e2e;--btn-hover:#651826;--accent-soft:#f2e6e9;--accent-ink:#7b1e2e;--chip-line:#e3c9cf;--snow:#376f9b;
--tile-line:#dce8f2;--sel:#dce8f2;--ring:#9cc3e4;--bar:#edf4fbf2;--shadow:inset 0 1px 0 #fff,0 8px 24px rgba(12,42,74,.07),0 1px 3px rgba(12,42,74,.04);
--glow:radial-gradient(ellipse at 15% 0%,#ffffffd9,transparent 48%),linear-gradient(145deg,#eef5fc,#dcebfa 65%,#e8f1fa);color-scheme:light}
html[data-appearance="dark"]{--bg:#071b2e;--paper:#102a40;--surface:#18384f;--edge:#365870;--ink:#e7f2fc;--ink2:#a9bfd2;--line:#32516a;
--action:#b8dcf6;--btn:#8b2941;--btn-hover:#a13a53;--accent-soft:#402437;--accent-ink:#f0bfca;--chip-line:#6b3a4c;--snow:#8dc4eb;
--tile-line:#32516a;--sel:#24475e;--ring:#b8dcf6;--bar:#0b2135f2;--shadow:inset 0 1px 0 #c5e8ff12,0 8px 24px #00000024,0 1px 3px #00000018;
--glow:radial-gradient(ellipse at 15% 0%,#24517166,transparent 48%),linear-gradient(145deg,#0b243b,#071b2e 65%,#0c2940);color-scheme:dark}
@media (prefers-color-scheme:dark){html:not([data-appearance]){--bg:#071b2e;--paper:#102a40;--surface:#18384f;--edge:#365870;--ink:#e7f2fc;--ink2:#a9bfd2;--line:#32516a;
--action:#b8dcf6;--btn:#8b2941;--btn-hover:#a13a53;--accent-soft:#402437;--accent-ink:#f0bfca;--chip-line:#6b3a4c;--snow:#8dc4eb;
--tile-line:#32516a;--sel:#24475e;--ring:#b8dcf6;--bar:#0b2135f2;--shadow:inset 0 1px 0 #c5e8ff12,0 8px 24px #00000024,0 1px 3px #00000018;
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
.topbar{{position:sticky;top:0;z-index:5;background:var(--bar);border-bottom:1px solid var(--edge);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)}}
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
.cta{{background:var(--paper);border:1px solid var(--edge);border-radius:24px;padding:16px;margin:16px 0}}
.cta a.btn{{background:var(--btn);color:#fff;text-decoration:none;padding:12px 18px;border-radius:12px;font-weight:600;display:inline-block}}
footer{{margin-top:26px;font-size:12px;color:var(--ink2)}}
.topbar.wide .top{{max-width:1680px;padding:8px 20px}}
.wrap.wide{{max-width:1680px;padding:14px 20px 32px}}
.top .resort{{font:600 20px/1 {mailer.DISPLAY};color:var(--ink);text-decoration:none;white-space:nowrap;padding-left:12px;border-left:1px solid var(--line)}}
html{{scroll-padding-top:calc(var(--hdr,112px) + 12px)}}
@media (prefers-reduced-motion:no-preference){{html{{scroll-behavior:smooth}}}}
.rtabs,.chips{{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}}
.rtabs::-webkit-scrollbar,.chips::-webkit-scrollbar{{display:none}}
.rtabs a,.chips a{{flex:none;display:inline-flex;align-items:center;border-radius:999px;color:var(--ink);text-decoration:none;white-space:nowrap}}
.top .rtabs a{{height:44px;padding:0 14px;font:500 15px/1 {mailer.SANS}}}
.rtabs a:hover,.chips a:hover{{background:var(--paper)}}
.rtabs a[aria-current="page"],.chips a[aria-current="true"]{{background:var(--sel);font-weight:600}}
.rtabs a:focus-visible,.chips a:focus-visible{{outline:2px solid var(--btn);outline-offset:2px}}
.top .rtabs{{margin-left:6px;padding-left:10px;border-left:1px solid var(--line)}}
.chiprow{{max-width:1680px;margin:0 auto;padding:0 20px 4px}}
.chips{{padding:4px 0;-webkit-mask-image:linear-gradient(90deg,#000 calc(100% - 28px),transparent);mask-image:linear-gradient(90deg,#000 calc(100% - 28px),transparent)}}
.chips a{{height:36px;padding:0 13px;font:500 14px/1 {mailer.SANS};border:1px solid var(--line)}}
.chips a[aria-current="true"]{{border-color:transparent}}
.gd section[id],.gd div[id]{{border-radius:24px}}
.arrived>.card,section.arrived{{animation:arrive 1.4s ease-out}}
@keyframes arrive{{0%,40%{{box-shadow:0 0 0 2px var(--ring),var(--shadow)}}100%{{box-shadow:0 0 0 2px transparent,var(--shadow)}}}}
@media (prefers-reduced-motion:reduce){{.arrived>.card,section.arrived{{animation:none;outline:2px solid var(--ring);outline-offset:0}}}}
.gd h2[tabindex]:focus:not(:focus-visible){{outline:none}}
.hoursline{{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;width:fit-content;max-width:100%;box-sizing:border-box;background:var(--paper);border:1px solid var(--edge);
 border-radius:14px;box-shadow:var(--shadow);padding:10px 14px;margin:0 0 14px;font-size:15px}}
.hoursline .k{{font:600 10px/1.3 {mailer.MONO};letter-spacing:.05em;text-transform:uppercase;color:var(--ink2)}}
.hoursline span:nth-child(2){{font-weight:600}}
.hoursline a{{font-size:13px}}
@media (forced-colors:active){{.rtabs a[aria-current],.chips a[aria-current]{{outline:2px solid CanvasText}}}}
.top .short{{display:none}}
@media (max-width:820px){{.top .resort{{display:none}}}}
@media (max-width:520px){{.top .full{{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}} .top .short{{display:inline}} .top .home span{{display:none}} .top .rtabs{{margin-left:0;padding-left:8px}} .top .rtabs a{{padding:0 10px;font-size:14px}}
 .top .app{{padding:10px 12px}} .chiprow{{padding:0 12px 4px}}}}
""" + webreport.CSS + guide_mod.CSS


def _ld(obj):
    data = json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{data}</script>'


def resort_tabs(slug, current):
    """Level 1: the resort's two pages. `current` is "report" or "guide"."""
    tabs = [("report", "Snow report", "Report", resort_path(slug)), ("guide", "Resort guide", "Guide", resort_path(slug, "guide"))]
    links = "".join(f'<a href="{h}"{" aria-current=\"page\"" if k == current else ""}><span class="full">{escape(t)}</span>'
                    f'<span class="short" aria-hidden="true">{escape(sh)}</span></a>' for k, t, sh, h in tabs)
    return f'<nav class="rtabs" aria-label="{escape(resorts.get(slug)["name"])} pages">{links}</nav>'


# Level 2 (guide page only): section chips with scroll-spy. Sets --hdr to the header height so anchor
# jumps land below the sticky header, marks the chip for the section being read (aria-current="true"),
# rings the section you jumped to, and moves focus to its heading. Never rewrites the URL hash.
NAV_JS = """<script>(function(){
var hdr=document.querySelector('.topbar'),root=document.documentElement;
function setH(){root.style.setProperty('--hdr',hdr.offsetHeight+'px')}
setH();if(window.ResizeObserver)new ResizeObserver(setH).observe(hdr);
var nav=document.querySelector('.chips');if(!nav)return;
var links=[].slice.call(nav.querySelectorAll('a')),secs=links.map(function(a){return document.getElementById(a.hash.slice(1))});
var still=window.matchMedia('(prefers-reduced-motion: reduce)').matches,paused=0;
function mark(i){links.forEach(function(a,j){if(j===i)a.setAttribute('aria-current','true');else a.removeAttribute('aria-current')});
 if(i>=0){var c=links[i];nav.scrollTo({left:c.offsetLeft-16,behavior:still?'auto':'smooth'})}}
function spy(){if(paused)return;var line=hdr.offsetHeight+24,cur=-1;
 secs.forEach(function(s,i){if(s&&s.getBoundingClientRect().top<=line)cur=i});
 if(innerHeight+scrollY>=document.documentElement.scrollHeight-2)cur=secs.length-1;mark(cur)}
function arrive(s){if(!s)return;s.classList.remove('arrived');void s.offsetWidth;s.classList.add('arrived');
 setTimeout(function(){s.classList.remove('arrived')},1600)}
links.forEach(function(a,i){a.addEventListener('click',function(){mark(i);paused=1;var s=secs[i];
 var done=function(){paused=0;removeEventListener('scrollend',done);spy()};addEventListener('scrollend',done);setTimeout(done,800);
 setTimeout(function(){arrive(s);var h=s&&s.querySelector('h2');if(h)h.focus({preventScroll:true})},still?0:350)})});
addEventListener('scroll',spy,{passive:true});addEventListener('resize',spy);
if(location.hash){var t=document.getElementById(location.hash.slice(1));if(t)setTimeout(function(){arrive(t)},200)}
spy()})()</script>"""


def shell(*, page_title, desc, canonical, body, ld=None, image=None, noindex=False, feed=None, wide=False,
          app_href="/", where=None, markdown=None, tabs=None, chips=""):
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
    sub = ""
    if tabs:
        slug, current = tabs
        where_html = (f'<a class="resort" href="{resort_path(slug)}">{escape(resorts.get(slug)["name"])}</a>'
                      + resort_tabs(slug, current))
    if chips:
        sub = f'<div class="chiprow">{chips}</div>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{chr(10).join(meta)}
<meta name="theme-color" content="{mailer.ICE}">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<script src="/appearance.js"></script>
<style>{CSS}</style>{lds}</head>
<body><header class="topbar{' wide' if wide else ''}"><div class="top"><a class="home" href="/"><img src="/brand/frosted-logo-email.png" width="36" height="36" alt=""><span>{ORG}</span></a>
{where_html}<a class="app" href="{escape(app_href)}"><span class="full">Open in the app</span><span class="short" aria-hidden="true">App</span></a></div>{sub}</header>
<div class="wrap{' wide' if wide else ''}">
{body}
<footer><p>{DISCLAIMER} Grooming and snow totals come from each resort's own reports. Forecast data by
Open-Meteo.com (CC BY 4.0), NWS and NRCS SNOTEL.</p>
<p><a href="/resorts">All resorts</a> · <a href="/">0xSnow app</a> · <a href="/#help">Help</a> · <a href="/llms.txt">For AI assistants</a>{f' · <a href="{markdown}">Markdown version</a>' if markdown else ""}</p></footer>
</div>{NAV_JS if tabs else ""}</body></html>"""


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
    h1 = (f"{name} snow report, {d.strftime('%a')} {report.mmdd(d)}" if dated
          else f"{name} snow report today, {d.strftime('%a')} {report.mmdd(d)}")
    crumbs = (f'<p class="crumbs"><a href="/resorts">Resorts</a> › <a href="{resort_path(slug)}">{escape(name)}</a>'
              + (f" › {report.mmdd(d)}" if dated else "") + "</p>")
    others = [x for x in dates if x != day_str][:60]
    past = ("<h2>Past reports</h2><ul class=\"dates\">" + "".join(
        f'<li><a href="{resort_path(slug, x)}">{date.fromisoformat(x).strftime("%a")} {report.mmdd(x)}</a></li>'
        for x in others) + "</ul>") if others else ""
    body = (crumbs + f'<h1 class="page">{escape(h1)}</h1>'
            + f'<p class="lead">{escape(" ".join(words))}</p>'
            + _quick_links(slug, name) + _hours_line(slug, name)
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
                 where=name, app_href=f"/?resort={slug}", tabs=(slug, "report"),
                 markdown=f"/resorts/{slug}/{day_str}.md" if dated else f"/resorts/{slug}.md")


def empty_resort_page(slug):
    """No report stored yet (a resort just added): a thin page that asks not to be indexed."""
    name = resorts.get(slug)["name"]
    body = (f'<p class="crumbs"><a href="/resorts">Resorts</a> › {escape(name)}</p>'
            f'<h1 class="page">{escape(name)} snow report today</h1>'
            f'<p class="lead">The first {escape(name)} report is on its way. It posts each morning once the resort\'s '
            f'grooming and snow report are in.</p>' + _cta(slug, name))
    return shell(page_title=f"{name} snow report today: grooming and forecast | {ORG}",
                 desc=f"Daily {name} snow report: new snow, base, grooming and the forecast.", canonical=site(resort_path(slug)),
                 body=body, noindex=True)


def hub_page():
    groups = {}
    for slug in resorts.enabled():
        r = resorts.get(slug)
        groups.setdefault(r["region"], []).append(r)
    body = ('<h1 class="page">Colorado and Utah ski resort snow reports</h1>'
            '<p class="lead">A short report for each resort every morning: what was groomed, new snow, base, '
            'the weather from first chair to last and the snow forecast. Free, and updated daily.</p>')
    for region in sorted(groups):
        body += (f"<h2>{escape(region)}</h2><p style=\"margin:0 0 6px\"><a href=\"{resort_path(region.lower())}\">"
                 f"{escape(region)} snow report today: every resort in one table</a></p><ul class=\"list\">") + "".join(
            f'<li><a href="{resort_path(r["slug"])}">{escape(r["name"])} snow report</a> '
            f'<span style="color:var(--ink2);font-size:13px">({escape(r["pass"])} pass) · '
            f'<a href="{resort_path(r["slug"], "guide")}">guide</a></span></li>'
            for r in sorted(groups[region], key=lambda r: r["name"])) + "</ul>"
    body += ('<h2>Pass blackout dates</h2><ul class="list">'
             + "".join(f'<li><a href="/passes/{k}">{escape(v["h1"])}</a></li>' for k, v in PASSES.items()) + "</ul>")
    body += _cta(resorts.DEFAULT, "morning")
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Ski resort snow reports",
          "url": site("resorts"), "publisher": _org(), "hasPart": [
              {"@type": "WebPage", "name": f'{resorts.get(s)["name"]} snow report', "url": site(resort_path(s))}
              for s in resorts.enabled()]}
    return shell(page_title=f"Colorado and Utah ski resort snow reports today: grooming and forecast | {ORG}",
                 desc="Daily snow reports, grooming, new snow, base depth and snow forecasts for 22 Colorado and Utah "
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
    urls += [(site(f"passes/{k}"), None, "weekly") for k in PASSES]
    for s in slugs:
        ds = by.get(s) or []
        urls.append((site(resort_path(s)), ds[0] if ds else None, "daily"))
        urls.append((site(resort_path(s, "guide")), None, "weekly"))
        urls += [(site(resort_path(s, d)), d, "never") for d in ds]
    rows = "".join(f"<url><loc>{escape(u)}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "")
                   + f"<changefreq>{f}</changefreq></url>" for u, m, f in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>')


def _hours_line(slug, name):
    """Lift hours on the report page too: one of the most asked questions (links to the guide's hours card)."""
    from . import facts as F
    f = (F.FACTS.get(slug) or {}).get("lift_hours")
    if not f:
        return ""
    shown = f.get("value") or "Not posted yet"
    return (f'<p class="hoursline"><span class="k">Lift hours</span><span>{escape(shown)}</span>'
            f'<a href="{resort_path(slug, "guide")}#hours">Details and source</a></p>')


def _quick_links(slug, name):
    """One line under the lead answering the next searches people make (trail map, cams, grooming PDF, blackout dates)."""
    from . import facts as F
    r = resorts.get(slug)
    links = []
    tm = (F.FACTS.get(slug) or {}).get("trail_map") or {}
    if tm.get("value"):
        links.append(f'<a href="{escape(tm["value"])}" rel="nofollow">{escape(name)} trail map</a>')
    if r.get("cams"):
        links.append(f'<a href="/?resort={slug}">{escape(name)} webcams</a>')
    if r.get("grooming_pdf"):
        links.append(f'<a href="{escape(r["grooming_pdf"])}" rel="nofollow">Grooming map PDF</a>')
    for key, p in PASSES.items():
        if p["pass"] in r["pass"]:
            links.append(f'<a href="/passes/{key}">{p["pass"]} Pass blackout dates</a>')
    links.append(f'<a href="{resort_path(slug, "guide")}">Hours and opening day</a>')
    return f'<p class="crumbs" style="font-size:14px;margin:0 0 14px">{" · ".join(links)}</p>'


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
    table = (f'<div style="overflow-x:auto;background:var(--paper);border:1px solid var(--edge);border-radius:24px;padding:8px">'
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


def guide_page(slug, summary=None, day=None, today=None):
    """Resort guide, laid out by search demand (bcbot/guide.py, docs/SEO.md)."""
    from . import guide
    title, desc, h1, body, ld = guide.render(slug, summary, day, today)
    name = resorts.get(slug)["name"]
    return shell(page_title=title, desc=desc, canonical=site(resort_path(slug, "guide")), body=body, ld=ld,
                 feed=(f"/resorts/{slug}/feed.xml", f"{name} daily reports"), wide=True, where=name,
                 app_href=f"/?resort={slug}", markdown=f"/resorts/{slug}/guide.md", tabs=(slug, "guide"),
                 chips=guide.chips(slug))


def _guide_label(slug, name):
    from . import facts as F
    words = guide_mod.covers(slug)
    return (f"{name} guide: {guide_mod._join(words)}" if words
            else f"How the {name} grooming and snow report works")


# ---------- pass blackout dates: one page per pass ----------
# "epic pass blackout dates" and "ikon pass blackout dates" each get about half the searches of
# "vail snow report" (docs/SEO.md). Dates come from bcbot/facts.py, so one re-check updates every page.

PASSES = {
    "epic-blackout-dates": {
        "pass": "Epic", "h1": "Epic Pass blackout dates 2026/27",
        "also": "Epic calls them restricted peak dates.",
        "ranges": [("2026-11-27", "2026-11-28", "Thanksgiving"), ("2026-12-26", "2026-12-31", "Holidays"),
                   ("2027-01-16", "2027-01-16", "MLK weekend"), ("2027-02-13", "2027-02-14", "Presidents Day weekend")],
        "who": "the Epic Local Pass (at resorts where it says \"not valid on peak dates\") and the Epic Day Pass",
        "free": "The full Epic Pass has no blackout dates.",
        "source": "EPIC_PEAK",
    },
    "ikon-blackout-dates": {
        "pass": "Ikon", "h1": "Ikon Pass blackout dates 2026/27",
        "also": "Only the Ikon Base Pass has blackout dates.",
        "ranges": [("2026-12-26", "2026-12-30", "Holidays"), ("2027-01-16", "2027-01-17", "MLK weekend"),
                   ("2027-02-13", "2027-02-14", "Presidents Day weekend")],
        "who": "the Ikon Base Pass",
        "free": "The full Ikon Pass and the Ikon Session Pass have no blackout dates.",
        "source": "IKON_BASE_BLACKOUTS",
    },
}


def _today_mt():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/Denver")).date()


def _range_text(a, b):
    da, db = date.fromisoformat(a), date.fromisoformat(b)
    one = f"{da.strftime('%a')} {report.mmdd(da)}"
    return one if a == b else f"{one} to {db.strftime('%a')} {report.mmdd(db)}"


def pass_status(key, today=None):
    """(is today restricted?, the next range as (start, end, label) or None)."""
    today = today or _today_mt()
    for a, b, label in PASSES[key]["ranges"]:
        if date.fromisoformat(a) <= today <= date.fromisoformat(b):
            return True, (a, b, label)
        if date.fromisoformat(a) > today:
            return False, (a, b, label)
    return False, None


CAL_CSS = """
.cal{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:4px 0 6px}
@media (min-width:760px){.cal{grid-template-columns:repeat(4,1fr)}}
.cal .m{background:var(--paper);border:1px solid var(--edge);border-radius:16px;padding:10px 10px 8px}
.cal .mt{font:600 13px/1.2 Outfit,sans-serif;margin:0 0 6px}
.cal table{width:100%;border-collapse:collapse;table-layout:fixed}
.cal th{font:600 10px/1 'IBM Plex Mono',monospace;color:var(--ink2);padding:0 0 4px}
.cal td{text-align:center;padding:1px 0}
.cal td span{display:inline-block;width:24px;height:24px;line-height:24px;border-radius:7px;font:400 12px/24px 'IBM Plex Mono',monospace;color:var(--ink)}
.cal td.b span{background:var(--btn);color:#fff;font-weight:600}
.cal td.t span{box-shadow:inset 0 0 0 2px var(--action)}
.cal td.p span{opacity:.45}
.calkey{font-size:12px;color:var(--ink2);margin:0 0 16px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.calkey i{display:inline-block;width:12px;height:12px;border-radius:4px;vertical-align:-2px;margin-right:5px}
"""


def blackout_days(key):
    from datetime import timedelta
    out = set()
    for a, b, _ in PASSES[key]["ranges"]:
        d, end = date.fromisoformat(a), date.fromisoformat(b)
        while d <= end:
            out.add(d)
            d += timedelta(days=1)
    return out


def pass_calendar(key, today=None):
    """Small month grids for every month with a blackout date: days filled, today ringed, past days faded."""
    import calendar
    today = today or _today_mt()
    days = blackout_days(key)
    months = sorted({(d.year, d.month) for d in days})
    cal = calendar.Calendar(firstweekday=6)
    out = ""
    for y, m in months:
        rows = ""
        for week in cal.monthdatescalendar(y, m):
            cells = ""
            for d in week:
                if d.month != m:
                    cells += "<td></td>"
                    continue
                cls = " ".join(c for c, on in (("b", d in days), ("t", d == today), ("p", d < today)) if on)
                label = f' aria-label="{d.strftime("%a")} {report.mmdd(d)}, blackout date"' if d in days else ""
                cells += f'<td class="{cls}"{label}><span>{d.day}</span></td>'
            rows += f"<tr>{cells}</tr>"
        out += (f'<div class="m"><p class="mt">{calendar.month_name[m]} {y}</p><table><thead><tr>'
                + "".join(f"<th>{w}</th>" for w in "SMTWTFS") + f"</tr></thead><tbody>{rows}</tbody></table></div>")
    key_html = ('<p class="calkey"><span><i style="background:var(--btn)"></i>Blackout date</span>'
                '<span><i style="box-shadow:inset 0 0 0 2px var(--action)"></i>Today</span>'
                f'<a href="/passes/{key}.ics">Add these dates to your calendar</a></p>')
    return f'<style>{CAL_CSS}</style><div class="cal">{out}</div>' + key_html


def pass_ics(key):
    """All-day events, one per blackout range, for phone calendars."""
    from datetime import timedelta
    p = PASSES[key]
    ev = []
    for a, b, label in p["ranges"]:
        end = date.fromisoformat(b) + timedelta(days=1)
        ev += ["BEGIN:VEVENT", f"UID:{key}-{a}@snow.0xm.studio", "DTSTAMP:20261119T000000Z",
               f"DTSTART;VALUE=DATE:{a.replace('-', '')}", f"DTEND;VALUE=DATE:{end.isoformat().replace('-', '')}",
               f"SUMMARY:{p['pass']} Pass blackout ({label})",
               f"DESCRIPTION:Blackout date for {p['who'].replace(',', chr(92) + ',')}. {site('passes/' + key)}",
               "TRANSP:TRANSPARENT", "END:VEVENT"]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//{ORG}//Blackout dates//EN", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:{p['h1']}"] + ev + ["END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def pass_page(key, today=None):
    from . import facts as F
    p = PASSES[key]
    today = today or _today_mt()
    src_url, src_name = getattr(F, p["source"])
    on, nxt = pass_status(key, today)
    if on:
        answer = f"Yes. Today ({report.mmdd(today)}) is a blackout date for {p['who']}."
    elif nxt:
        days = (date.fromisoformat(nxt[0]) - today).days
        answer = (f"No, today ({report.mmdd(today)}) is not a blackout date. The next one is "
                  f"{_range_text(nxt[0], nxt[1])} ({nxt[2]}), {days} day{'s' if days != 1 else ''} away.")
    else:
        answer = "No. All 2026/27 blackout dates have passed."
    all_dates = "; ".join(f"{_range_text(a, b)} ({lbl})" for a, b, lbl in p["ranges"])
    lead = f"{p['h1']}: {all_dates}. They apply to {p['who']}. {p['free']} {p['also']}"
    rows = "".join(f'<tr><td style="padding:6px 8px;border-bottom:1px solid var(--line)">{escape(lbl)}</td>'
                   f'<td style="padding:6px 8px;border-bottom:1px solid var(--line);font-family:\'IBM Plex Mono\',monospace;font-size:14px">'
                   f'{escape(_range_text(a, b))}</td></tr>' for a, b, lbl in p["ranges"])
    access = F.EPIC_ACCESS if p["pass"] == "Epic" else F.IKON_ACCESS
    enabled = set(resorts.enabled())
    res = ""
    for slug, acc in access.items():
        if slug not in enabled:
            continue
        name = resorts.get(slug)["name"]
        if p["pass"] == "Epic":
            local = acc[1] or "not included"
            blocked = "Yes" if acc[1] and "not valid on peak" in acc[1] else ("No" if acc[1] else "–")
            cols = (escape(local), blocked)
        else:
            base = acc[1] or "not included"
            cols = (escape(base), "Yes" if acc[1] else "–")
        res += (f'<tr><td style="padding:6px 8px;border-bottom:1px solid var(--line)"><a href="{resort_path(slug)}">{escape(name)}</a></td>'
                + "".join(f'<td style="padding:6px 8px;border-bottom:1px solid var(--line);font-size:14px">{c}</td>' for c in cols) + "</tr>")
    lesser = "Epic Local Pass" if p["pass"] == "Epic" else "Ikon Base Pass"
    th = 'style="padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;font-size:12px;color:var(--ink2)"'
    box = '<div style="overflow-x:auto;background:var(--paper);border:1px solid var(--edge);border-radius:24px;padding:8px">{}</div>'
    other = [k for k in PASSES if k != key][0]
    body = (f'<p class="crumbs"><a href="/resorts">Resorts</a> › Passes</p>'
            f'<h1 class="page">{escape(p["h1"])}</h1>'
            f'<div class="cta" style="margin-top:8px"><b>Is today a blackout date?</b> {escape(answer)}</div>'
            + pass_calendar(key, today)
            + f'<p class="lead">{escape(lead)}</p>'
            f'<h2>2026/27 dates</h2>' + box.format(f'<table style="width:100%;border-collapse:collapse"><tbody>{rows}</tbody></table>')
            + f'<h2>{p["pass"]} resorts we cover</h2>'
            + box.format(f'<table style="width:100%;border-collapse:collapse"><thead><tr><th {th}>Resort</th>'
                         f'<th {th}>{lesser}</th><th {th}>Blacked out on these dates?</th></tr></thead><tbody>{res}</tbody></table>')
            + f'<p style="font-size:12px;color:var(--ink2)">Source: <a href="{escape(src_url)}" rel="nofollow">{escape(src_name)}</a> · '
              f'checked {report.mmdd(F.CHECKED_SHARED)}. Passes can change, so check the source before you buy or go.</p>'
            + _cta(resorts.DEFAULT, "morning")
            + f'<p><a href="/passes/{other}">{escape(PASSES[other]["h1"])}</a> · <a href="/resorts">Snow reports for every resort</a></p>')
    canonical = site(f"passes/{key}")
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": f"What are the {p['pass']} Pass blackout dates for 2026/27?",
         "acceptedAnswer": {"@type": "Answer", "text": f"{all_dates}. They apply to {p['who']}. {p['free']}"}},
        {"@type": "Question", "name": f"Does the full {p['pass']} Pass have blackout dates?",
         "acceptedAnswer": {"@type": "Answer", "text": p["free"]}}]}
    title = (f"{p['h1']}: is today blacked out?" + (" (restricted peak dates)" if p["pass"] == "Epic" else "")
             + f" | {ORG}")
    return shell(page_title=title, desc=lead[:300], canonical=canonical, body=body, ld=[faq], where="Passes")
