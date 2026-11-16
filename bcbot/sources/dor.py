"""Copper, Snowbird and Eldora (all POWDR resorts) publish their snow report and trail
status as open JSON on api.<resort>.com:

  /api/v1/dor/drupal/snow-reports   newest first: date ("2026-11-15 05:00:00", resort time),
                                    overnight_amount, base_depth, unit_of_measurement,
                                    computed {24_hour, 48_hour, 7_day, total, ...}
  /api/v1/dor/drupal/trails         every trail: name, sector {name}, type, season,
                                    status, groom_status ("groomed" / "not_groomed")

One reader covers all three. Checked from a browser on 11/16/2026.
"""
import logging

from .. import config
from ..util import get

log = logging.getLogger(__name__)

SNOW_REPORTS = "/api/v1/dor/drupal/snow-reports"
TRAILS = "/api/v1/dor/drupal/trails"


def _inches(v, unit):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return round(v / 2.54, 1) if (unit or "in").lower().startswith("cm") else v


def _clock(date_str):
    """'2026-11-15 05:00:00' -> '5:00 AM'."""
    try:
        hh, mm = (int(x) for x in date_str.split(" ")[1].split(":")[:2])
    except (IndexError, ValueError, AttributeError):
        return None
    return f"{(hh % 12) or 12}:{mm:02d} {'AM' if hh < 12 else 'PM'}"


def parse_snow_report(reports):
    """The newest report, in the same shape as resort.parse (inches)."""
    if not isinstance(reports, list) or not reports:
        return {}
    r = max(reports, key=lambda x: x.get("date") or "")
    unit, comp = r.get("unit_of_measurement"), r.get("computed") or {}
    out = {}
    for key, val in (("overnight_in", r.get("overnight_amount")), ("last_24h_in", comp.get("24_hour")),
                     ("last_48h_in", comp.get("48_hour")), ("last_7d_in", comp.get("7_day")),
                     ("base_in", r.get("base_depth")), ("season_in", comp.get("total"))):
        v = _inches(val, unit)
        if v is not None:
            out[key] = v
    if r.get("date"):
        out["stamps"] = {"date": r["date"]}  # resort-local time; is_fresh reads the date
        t = _clock(r["date"])
        if t:
            out["updated_time"] = t
    return out


def parse_trails(trails):
    """Groomed winter runs, by sector, in the shape grooming.parse_runs gives (area layout)."""
    areas = {}
    for t in trails if isinstance(trails, list) else []:
        if t.get("season", "winter") != "winter" or t.get("type") not in ("alpine_trail", "terrain_park_trail"):
            continue
        if (t.get("groom_status") or "not_groomed") == "not_groomed" or not t.get("name"):
            continue
        area = ((t.get("sector") or {}).get("name") or "Groomed").strip()
        areas.setdefault(area, []).append(t["name"].strip())
    return {"groomers_of_the_day": [], "overnight": [], "morning": [], "map_date": None,
            "groomed": [n for runs in areas.values() for n in runs], "areas": areas}


def fetch_snow_report():
    try:
        r = get(config.DOR_API + SNOW_REPORTS, headers={"Accept": "application/json"}, timeout=20)
        if not r.ok:
            log.warning("DOR snow report HTTP %s", r.status_code)
            return {}
        return parse_snow_report(r.json())
    except Exception as e:
        log.warning("DOR snow report failed: %s", e)
        return {}


def fetch_grooming():
    """Groomed runs right now, or None when the feed can't be read."""
    try:
        r = get(config.DOR_API + TRAILS, headers={"Accept": "application/json"}, timeout=20)
        r.raise_for_status()
        return parse_trails(r.json())
    except Exception as e:
        log.warning("DOR trails failed: %s", e)
        return None
