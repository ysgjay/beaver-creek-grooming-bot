"""Grooming coverage: notice when a resort's grooming is missing once its season starts, and look
each week for a grooming source for the resorts that don't have one yet.

Runs from /api/groom (Vercel cron, daily). Two parts:

  watch()  every day: for each live resort past opening day, was there a new grooming map or any
           groomed runs today? Remembers the last day with grooming in data/groomwatch.json and
           alerts the owner once when a resort has no source, or its source has been empty for
           EMPTY_DAYS days in a row after opening.
  find()   Mondays (or ?find=1): for each live resort with no source, tries the formats 0xSnow can
           read (Lumiplan map, Vail Resorts terrain page, POWDR trails feed) and collects hints from
           the resort's home page (grooming page links, Mountain Powder / Lumiplan mentions).
           Results go to data/groomfind.json. Nothing is switched on automatically: a person (or the
           weekly Claude task) checks a candidate and wires it up in resorts.py in a PR.
"""
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from . import resorts
from .sources import vrterrain

log = logging.getLogger(__name__)

EMPTY_DAYS = 3
WATCH_PATH = "data/groomwatch.json"
FIND_PATH = "data/groomfind.json"
LUMIPLAN = "https://grooming.lumiplan.pro/{}-grooming-map.pdf"
DOR_TRAILS = "/api/v1/dor/drupal/trails"


def source(r):
    """Where this resort's grooming comes from, as a short label ('' when it has none)."""
    if r.get("grooming_pdf"):
        return "Lumiplan map"
    if r.get("dor_api"):
        return "POWDR feed"
    if r.get("reportpal"):
        return "Boyne feed"
    if r.get("terrain_status"):
        return "Vail terrain page"
    return ""


def had_grooming(day, today_iso):
    """True when a saved day report shows grooming for today: a new map, or any groomed runs."""
    if not day or day.get("date") != today_iso:
        return False
    g = day.get("grooming") or {}
    if g.get("image") and g.get("new_map"):
        return True
    runs = g.get("runs") or {}
    if g.get("list"):
        return any(runs.get(k) for k in ("groomed", "overnight", "morning", "groomers_of_the_day", "featured"))
    return False


def _today(r, now):
    return now.astimezone(ZoneInfo(r["tz"])).date()


def watch(store, now=None, slugs=None):
    """Update data/groomwatch.json. Returns {"rows": [...], "alerts": [...new problems...]}."""
    now = now or datetime.now(ZoneInfo("UTC"))
    state = store.get_json(WATCH_PATH, {}) or {}
    last_runs, alerted = dict(state.get("last_runs") or {}), dict(state.get("alerted") or {})
    rows, alerts = [], []
    for slug in slugs or resorts.enabled():
        r = resorts.get(slug)
        today = _today(r, now)
        src = source(r)
        latest = store.get_json(f"data/{slug}/latest.json" if slug != resorts.DEFAULT else "data/latest.json", {}) or {}
        if had_grooming(latest, today.isoformat()):
            last_runs[slug] = today.isoformat()
        in_season = today >= r["opening_day"]
        since = date.fromisoformat(last_runs[slug]) if slug in last_runs else None
        quiet_from = max(r["opening_day"], since) if since else r["opening_day"]
        quiet_days = (today - quiet_from).days
        problem = ""
        if in_season and not src:
            problem = "no source"
        elif in_season and quiet_days >= EMPTY_DAYS:
            problem = f"empty {quiet_days} days"
        kind = problem.split(" ")[0] if problem else ""
        if kind and alerted.get(slug) != kind:
            alerts.append({"resort": slug, "name": r["name"], "problem": problem})
        if kind:
            alerted[slug] = kind
        else:
            alerted.pop(slug, None)
        rows.append({"resort": slug, "name": r["name"], "source": src, "opening_day": r["opening_day"].isoformat(),
                     "in_season": in_season, "last_grooming": last_runs.get(slug), "problem": problem})
    store.put_json(WATCH_PATH, {"checked": now.isoformat(timespec="minutes"), "last_runs": last_runs,
                                "alerted": alerted, "rows": rows})
    return {"rows": rows, "alerts": alerts}


# ---------------- finder ----------------

def _slug_variants(r):
    name = re.sub(r"[^a-z0-9]+", "-", r["name"].lower()).strip("-")
    host = urlparse(r["site"]).hostname or ""
    base = re.sub(r"^www\.", "", host).split(".")[0]
    out = []
    for v in (r["slug"], name, base, r["slug"] + "-mountain", name + "-mountain", r["slug"] + "-resort"):
        if v and v not in out:
            out.append(v)
    return out


def _root_domain(site):
    host = urlparse(site).hostname or ""
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


_HREF = re.compile(r"""href=["']([^"'#]+)["']""", re.I)


def page_hints(html, site):
    """Grooming page links and feed providers mentioned on a resort page."""
    hints, links = [], []
    for href in _HREF.findall(html or ""):
        if re.search(r"groom", href, re.I):
            u = urljoin(site, href)
            if u not in links:
                links.append(u)
    low = (html or "").lower()
    for word, label in (("mtnpowder", "Mountain Powder feed"), ("mtnfeed", "Mountain Powder feed"),
                        ("lumiplan", "Lumiplan"), ("reportpal", "Boyne ReportPal feed"), ("liftie", "Liftie"),
                        ("skiresort.info", "skiresort.info")):
        if word in low and label not in hints:
            hints.append(label)
    return {"links": links[:5], "providers": hints}


def probe(r, fetch, head):
    """Try every format 0xSnow can read for one resort. fetch(url) -> text or None; head(url) -> status."""
    found = []
    for v in _slug_variants(r):
        u = LUMIPLAN.format(v)
        if head(u) == 200:
            found.append({"kind": "lumiplan", "url": u, "set": f'"grooming_pdf": "{u}"'})
            break
    terrain = vrterrain.url(r["site"])
    runs = vrterrain.parse(fetch(terrain) or "")
    if runs is not None:
        found.append({"kind": "vail_terrain", "url": terrain, "groomed_now": len(runs["groomed"]),
                      "set": "Vail Resorts platform: give it a snow_report_path so terrain_status is set"})
    api = f"https://api.{_root_domain(r['site'])}"
    try:
        trails = json.loads(fetch(api + DOR_TRAILS) or "null")
    except ValueError:
        trails = None
    if isinstance(trails, list) and trails and isinstance(trails[0], dict) and "groom_status" in trails[0]:
        found.append({"kind": "powdr", "url": api + DOR_TRAILS, "set": f'"dor_api": "{api}"'})
    hints = page_hints(fetch(r["site"]) or "", r["site"])
    return {"resort": r["slug"], "name": r["name"], "found": found, **hints}


def find(store, fetch, head, now=None, slugs=None):
    """Probe every live resort without a grooming source. Writes data/groomfind.json and returns
    {"results": [...], "new": [...candidates not reported before...]}."""
    now = now or datetime.now(ZoneInfo("UTC"))
    targets = [resorts.get(s) for s in (slugs or resorts.enabled())]
    targets = [r for r in targets if not source(r)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda r: probe(r, fetch, head), targets))
    prev = store.get_json(FIND_PATH, {}) or {}
    seen = {(x["resort"], f["url"]) for x in prev.get("results", []) for f in x.get("found", [])}
    new = [{"resort": x["resort"], "name": x["name"], **f} for x in results for f in x["found"]
           if (x["resort"], f["url"]) not in seen]
    store.put_json(FIND_PATH, {"checked": now.isoformat(timespec="minutes"), "results": results})
    return {"results": results, "new": new}
