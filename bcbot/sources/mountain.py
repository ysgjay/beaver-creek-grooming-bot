"""Extra mountain context around the forecast, all from free public services.

- Avalanche danger for the backcountry zone around the resort (avalanche.org, every US center).
- A link to the local NWS office's forecast discussion (the forecasters' written reasoning).
- Observations near the resort from NOAA's snow center (NOHRSC): snow depth at ski-area and
  SNOTEL stations, and 24-hour snowfall reports. Free and keyless.
- Live readings from weather stations on or near the ski area (Synoptic / MesoWest), only when
  `SYNOPTIC_TOKEN` is set (a paid service, so normally off).
Each one returns None on any failure; none of them can fail a run.
"""
import html
import logging
import os
import re

from .. import config
from ..util import get

log = logging.getLogger(__name__)

AVALANCHE_URL = "https://api.avalanche.org/v2/public/products/map-layer"
NWS_HEADERS = {"Accept": "application/geo+json", "User-Agent": "0xSnow (snow.0xm.studio)"}
SYNOPTIC_URL = "https://api.synopticdata.com/v2/stations/latest"
NOHRSC_URL = "https://www.nohrsc.noaa.gov/nearest/index.html"
# A depth station counts as "on this mountain" only this close to the resort's point. Farther
# out the nearest one is often another ski area (Beaver Creek's was Vail Mid-Mtn, 7.7 mi away)
# or a pass, which reads as the wrong resort; better to show nothing.
ON_MOUNTAIN_MI = 1.5
DANGER = {1: "Low", 2: "Moderate", 3: "Considerable", 4: "High", 5: "Extreme"}


def _inside(lon, lat, ring):
    """Ray casting: is the point inside this polygon ring of [lon, lat] pairs?"""
    hit = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def _contains(geom, lon, lat):
    polys = geom.get("coordinates", [])
    if geom.get("type") == "Polygon":
        polys = [polys]
    for poly in polys:
        if poly and _inside(lon, lat, [tuple(p[:2]) for p in poly[0]]) and not any(
                _inside(lon, lat, [tuple(p[:2]) for p in hole]) for hole in poly[1:]):
            return True
    return False


def avalanche_zone(payload, lat, lon):
    """The avalanche forecast zone containing the point, from avalanche.org's map layer."""
    for f in payload.get("features", []):
        if not _contains(f.get("geometry") or {}, lon, lat):
            continue
        p = f.get("properties") or {}
        try:
            level = int(p.get("danger_level"))
        except (TypeError, ValueError):
            level = -1
        return {"zone": p.get("name"), "center": p.get("center"), "center_id": p.get("center_id"),
                "level": level if level in DANGER else None, "danger": DANGER.get(level),
                "off_season": str(p.get("off_season")).lower() == "true", "link": p.get("link")}
    return None


def fetch_avalanche():
    try:
        r = get(AVALANCHE_URL, headers={"User-Agent": NWS_HEADERS["User-Agent"]}, timeout=10, retries=0)
        r.raise_for_status()
        return avalanche_zone(r.json(), config.LAT, config.LON)
    except Exception as e:
        log.warning("avalanche.org failed: %s", e)
        return None


def fetch_discussion():
    """{office, issued, url} for the latest Area Forecast Discussion from the resort's NWS office."""
    if not config.IN_US:
        return None  # NWS has no office for Canadian resorts
    try:
        pts = get(f"https://api.weather.gov/points/{config.LAT:.4f},{config.LON:.4f}",
                  headers=NWS_HEADERS, timeout=10, retries=0)
        pts.raise_for_status()
        office = pts.json()["properties"]["cwa"]
        r = get(f"https://api.weather.gov/products/types/AFD/locations/{office}",
                headers=NWS_HEADERS, timeout=10, retries=0)
        r.raise_for_status()
        latest = (r.json().get("@graph") or [{}])[0]
        return {"office": office, "issued": latest.get("issuanceTime"),
                "url": f"https://forecast.weather.gov/product.php?site=NWS&issuedby={office}&product=AFD&format=txt"}
    except Exception as e:
        log.warning("NWS discussion failed: %s", e)
        return None


def parse_stations(payload, min_elev_ft):
    """Nearest stations at or above the base, as [{name, id, elevation_ft, temp_f, depth_in, wind_mph, time}]."""
    out = []
    for s in payload.get("STATION", []):
        try:
            elev = float(s.get("ELEVATION") or 0)
        except ValueError:
            continue
        if elev < min_elev_ft:
            continue
        obs = s.get("OBSERVATIONS") or {}

        def val(key):
            v = obs.get(key) or {}
            return v.get("value"), v.get("date_time")
        temp, t1 = val("air_temp_value_1")
        depth, t2 = val("snow_depth_value_1")
        wind, t3 = val("wind_speed_value_1")
        if temp is None and depth is None:
            continue
        out.append({"name": s.get("NAME"), "id": s.get("STID"), "elevation_ft": round(elev),
                    "distance_mi": s.get("DISTANCE"), "temp_f": None if temp is None else round(temp),
                    "depth_in": None if depth is None else round(depth),
                    "wind_mph": None if wind is None else round(wind), "time": t1 or t2 or t3})
    out.sort(key=lambda x: x.get("distance_mi") or 99)
    return out[:3]


def fetch_stations():
    token = os.environ.get("SYNOPTIC_TOKEN")
    if not token:
        return None
    try:
        r = get(SYNOPTIC_URL, params={
            "token": token, "radius": f"{config.LAT},{config.LON},8", "limit": 15, "within": 180,
            "vars": "air_temp,snow_depth,wind_speed", "units": "english",
            "status": "active"}, timeout=10, retries=0)
        r.raise_for_status()
        return parse_stations(r.json(), base_elevation())
    except Exception as e:
        log.warning("Synoptic failed: %s", e)
        return None


_SECTIONS = {"Raw Snowfall Observations": "snowfall", "Snow Depth Observations": "depth",
             "Snow Water Equivalent Observations": "swe"}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_nohrsc(page):
    """{snowfall|depth|swe: [{id, name, elevation_ft, value_in, hours?, time_utc, distance_mi}]}
    from NOHRSC's "nearest observations" page (one table per kind, nearest first)."""
    out = {}
    for table in re.findall(r"<table class=\"gray_data_table\".*?</table>", page, flags=re.S):
        cap = re.search(r"<caption><strong>(.*?)</strong>", table)
        key = _SECTIONS.get(cap.group(1).strip()) if cap else None
        if not key:
            continue
        rows = []
        for tr in re.findall(r"<tr>(.*?)</tr>", table, flags=re.S):
            cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)]
            if len(cells) < 6:
                continue
            row = {"id": cells[0], "name": cells[1].title(), "elevation_ft": _num(cells[2]), "value_in": _num(cells[3])}
            if len(cells) >= 7:  # snowfall has a duration column
                row["hours"], row["time_utc"], dist = _num(cells[4]), cells[5], cells[6]
            else:
                row["time_utc"], dist = cells[4], cells[5]
            m = re.match(r"([\d.]+)\s*mi", dist)
            row["distance_mi"] = float(m.group(1)) if m else None
            if row["value_in"] is not None:
                rows.append(row)
        out[key] = rows
    return out


def fetch_nohrsc():
    try:
        r = get(NOHRSC_URL, params={"city": f"{config.LAT:.4f},{config.LON:.4f}", "county": "", "l": 10,
                                    "u": "e", "b": 1}, headers={"User-Agent": NWS_HEADERS["User-Agent"]},
                timeout=10, retries=0)
        r.raise_for_status()
        return parse_nohrsc(r.text) or None
    except Exception as e:
        log.warning("NOHRSC failed: %s", e)
        return None


def mountain_depth(nohrsc, min_elev_ft):
    """Nearest snow-depth readings on the mountain (at or above the base) as station rows."""
    rows = [r for r in (nohrsc or {}).get("depth", []) if (r.get("elevation_ft") or 0) >= min_elev_ft
            and r.get("distance_mi") is not None and r["distance_mi"] <= ON_MOUNTAIN_MI]
    return [{"name": r["name"], "id": r["id"], "elevation_ft": round(r["elevation_ft"]),
             "distance_mi": r["distance_mi"], "temp_f": None, "depth_in": round(r["value_in"]),
             "wind_mph": None, "time": r["time_utc"], "source": "NOHRSC"} for r in rows[:3]]


def base_elevation():
    return min((b["elevation_ft"] for b in config.ELEVATION_BANDS), default=0) - 300
