"""Best-effort read of Beaver Creek's own snow report (resort-reported totals).

Vail Resorts pages embed the report as a JS object. If the page shape changes or the
site blocks the request, this returns {} and the rest of the report still goes out.
"""
import json
import logging
import re

from .. import config
from ..util import get

log = logging.getLogger(__name__)

_BLOB = re.compile(r"snowReportData\s*=\s*(\{.*?\});", re.S)
_WANTED = {
    "overnightsnowfall": "overnight_in",
    "twentyfourhoursnowfall": "last_24h_in",
    "fortyeighthoursnowfall": "last_48h_in",
    "sevendaysnowfall": "last_7d_in",
    "basedepth": "base_in",
    "currentseason": "season_in",
}


def _inches(v):
    if isinstance(v, dict):
        v = v.get("Inches", v.get("inches"))
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse(html):
    m = _BLOB.search(html)
    if not m:
        return {}
    try:
        blob = json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}
    out = {}
    for k, v in blob.items():
        key = _WANTED.get(k.lower())
        if key:
            val = _inches(v)
            if val is not None:
                out[key] = val
    # When was the report published? Keep every date/time-looking field (and the key list)
    # so the freshness rule can be built on the resort's real field names.
    stamps = {}
    for k, v in blob.items():
        if isinstance(v, (str, int, float)) and re.search(r"date|time|updated|asof|report", k, re.I):
            stamps[k] = v
    if stamps:
        out["stamps"] = stamps
    out["keys"] = sorted(blob.keys())[:60]
    return out


def fetch():
    try:
        r = get(config.RESORT_SNOW_REPORT_URL, headers={"Accept": "text/html"})
        if not r.ok:
            log.warning("Resort snow report HTTP %s", r.status_code)
            return {}
        return parse(r.text)
    except Exception as e:
        log.warning("Resort snow report failed: %s", e)
        return {}
