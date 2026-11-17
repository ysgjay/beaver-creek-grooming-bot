"""Extra mountain context around the forecast, all from free public services.

- Avalanche danger for the backcountry zone around the resort (avalanche.org, every US center).
- A link to the local NWS office's forecast discussion (the forecasters' written reasoning).
- Live readings from weather stations on or near the ski area (Synoptic / MesoWest), only when
  `SYNOPTIC_TOKEN` is set. Each one returns None on any failure; none of them can fail a run.
"""
import logging
import os

from .. import config
from ..util import get

log = logging.getLogger(__name__)

AVALANCHE_URL = "https://api.avalanche.org/v2/public/products/map-layer"
NWS_HEADERS = {"Accept": "application/geo+json", "User-Agent": "Chair 0 Snow Desk (snow.0xm.studio)"}
SYNOPTIC_URL = "https://api.synopticdata.com/v2/stations/latest"
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
        base = min((b["elevation_ft"] for b in config.ELEVATION_BANDS), default=0) - 300
        return parse_stations(r.json(), base)
    except Exception as e:
        log.warning("Synoptic failed: %s", e)
        return None
