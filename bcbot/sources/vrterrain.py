"""Groomed runs from Vail Resorts' "Lift Operations & Terrain Updates" page, for the Vail Resorts
mountains that post no Lumiplan grooming map (Whistler Blackcomb, Breckenridge, Keystone, Heavenly,
Northstar, Stowe and the rest).

Every Vail Resorts site has the same page, which embeds the trail status as a JS object:

  <site>/the-mountain/mountain-conditions/terrain-and-lift-status.aspx
    FR.TerrainStatusFeed = {"Date": ..., "GroomingAreas": [{"Name": "Peak 8",
        "Trails": [{"Name": "Freeway", "IsGroomed": true, "IsOpen": true, "Difficulty": "Blue", ...}]}],
        "IsSuccessful": true}

The page carries the object twice (an older "/Date(...)/" copy and an ISO-dated copy); both list the
same trails. Checked from a browser on 11/20/2026 on Whistler Blackcomb and Breckenridge.
"""
import json
import logging
import re

from .. import config
from ..util import get

log = logging.getLogger(__name__)

PATH = "/the-mountain/mountain-conditions/terrain-and-lift-status.aspx"
_START = re.compile(r"FR\.TerrainStatusFeed\s*=\s*")


def url(site):
    return site.rstrip("/") + PATH


def _feeds(html):
    """Every FR.TerrainStatusFeed object on the page, decoded."""
    dec = json.JSONDecoder()
    for m in _START.finditer(html or ""):
        try:
            obj, _ = dec.raw_decode(html, m.end())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            yield obj


def parse(html):
    """Groomed runs by area, in the shape grooming.parse_runs gives, or None when the page has no feed."""
    feed = next((f for f in _feeds(html) if f.get("IsSuccessful", True) and f.get("GroomingAreas")), None)
    if feed is None:
        return None
    areas = {}
    for area in feed.get("GroomingAreas") or []:
        name = (area.get("Name") or "Groomed").strip()
        for t in area.get("Trails") or []:
            if t.get("IsGroomed") and (t.get("Name") or "").strip():
                runs = areas.setdefault(name, [])
                if t["Name"].strip() not in runs:
                    runs.append(t["Name"].strip())
    return {"groomers_of_the_day": [], "overnight": [], "morning": [], "map_date": None,
            "groomed": [n for runs in areas.values() for n in runs], "areas": areas}


def fetch_grooming():
    """Groomed runs right now, or None when the page can't be read."""
    if not config.TERRAIN_STATUS_URL:
        return None
    try:
        r = get(config.TERRAIN_STATUS_URL, headers={"Accept": "text/html"}, timeout=20, retries=1)
        if not r.ok:
            log.warning("terrain status HTTP %s", r.status_code)
            return None
        return parse(r.text)
    except Exception as e:
        log.warning("terrain status failed: %s", e)
        return None
