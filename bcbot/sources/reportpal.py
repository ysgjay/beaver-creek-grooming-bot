"""Boyne Resorts (Big Sky, Brighton, Sugarloaf, Sunday River, Loon) publish their mountain report as JSON on
each resort's own site, the same feed their Current Conditions pages load:

  <site>/api/reportpal?resortName=<code>&useReportPal=true
    updated / trailsUpdated            ISO UTC
    currentConditions.resortLocations.location   snowOverNight, snow24Hours, snow48Hours, snow7Days,
                                                  snowSeasonTotal, base  ({inches, centimeters})
    facilities.areas.area[].trails.trail[]       name, status, groomed (bool)

Checked from a browser on 11/19/2026 (codes bs, br, sl, sr, lm). One reader covers all five.
"""
import logging
from datetime import datetime

from .. import config
from ..util import get

log = logging.getLogger(__name__)

_SNOW = (("snowOverNight", "overnight_in"), ("snow24Hours", "last_24h_in"), ("snow48Hours", "last_48h_in"),
         ("snow7Days", "last_7d_in"), ("base", "base_in"), ("snowSeasonTotal", "season_in"))


def url(site, code):
    return f"{site.rstrip('/')}/api/reportpal?resortName={code}&useReportPal=true"


def _list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _inches(v):
    if isinstance(v, dict):
        v = v.get("inches")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _local(iso, tz):
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(tz)
    except (TypeError, ValueError):
        return None


def parse_snow_report(j, tz=None):
    """The resort-wide numbers, in the same shape as resort.parse (inches)."""
    if not isinstance(j, dict):
        return {}
    tz = tz or config.TZ
    locs = _list(((j.get("currentConditions") or {}).get("resortLocations") or {}).get("location"))
    if not locs:
        return {}
    loc, out = locs[0], {}
    for src, key in _SNOW:
        v = _inches(loc.get(src))
        if v is not None:
            out[key] = v
    when = _local(j.get("updated"), tz)
    if when:
        out["stamps"] = {"updated": when.date().isoformat()}  # resort-local date; is_fresh reads it
        out["updated_time"] = f"{(when.hour % 12) or 12}:{when.minute:02d} {'AM' if when.hour < 12 else 'PM'}"
    return out


def parse_trails(j):
    """Groomed runs by area, in the shape grooming.parse_runs gives (area layout)."""
    areas = {}
    for a in _list(((j or {}).get("facilities") or {}).get("areas", {}).get("area")):
        for t in _list((a.get("trails") or {}).get("trail")):
            if t.get("groomed") is True and t.get("name"):
                areas.setdefault((a.get("name") or "Groomed").strip(), []).append(t["name"].strip())
    return {"groomers_of_the_day": [], "overnight": [], "morning": [], "map_date": None,
            "groomed": [n for runs in areas.values() for n in runs], "areas": areas}


def _fetch():
    r = get(config.RESORT_SNOW_REPORT_URL, headers={"Accept": "application/json"}, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_snow_report():
    try:
        return parse_snow_report(_fetch())
    except Exception as e:
        log.warning("ReportPal snow report failed: %s", e)
        return {}


def fetch_grooming():
    """Groomed runs right now, or None when the feed can't be read."""
    try:
        return parse_trails(_fetch())
    except Exception as e:
        log.warning("ReportPal trails failed: %s", e)
        return None
