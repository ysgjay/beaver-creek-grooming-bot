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
    # When was the report published? Beaver Creek's is LastUpdatedText,
    # e.g. "Updated November 15, 2026 at 5:34 AM MST". Any date/time field is kept.
    stamps = {}
    for k, v in blob.items():
        if isinstance(v, (str, int, float)) and re.search(r"date|time|updated|asof|report", k, re.I):
            stamps[k] = v
    if stamps:
        out["stamps"] = stamps
        t = re.search(r"(\d{1,2}:\d{2}\s?[AP]M)", " ".join(str(v) for v in stamps.values()))
        if t:
            out["updated_time"] = t.group(1)
    return out


_MONTHS = "january february march april may june july august september october november december".split()


def _stamp_dates(value):
    """Every calendar date found in one stamp value (ISO, US, 'November 15, 2026', /Date(ms)/)."""
    from datetime import date, datetime, timezone
    s = str(value)
    out = []
    for y, m, d in re.findall(r"(20\d\d)-(\d{1,2})-(\d{1,2})", s):
        out.append(date(int(y), int(m), int(d)))
    for m, d, y in re.findall(r"\b(\d{1,2})/(\d{1,2})/(20\d\d)\b", s):
        out.append(date(int(y), int(m), int(d)))
    for mon, d, y in re.findall(r"([A-Za-z]+)\.? (\d{1,2}),? (20\d\d)", s):
        if mon.lower()[:3] in [x[:3] for x in _MONTHS]:
            out.append(date(int(y), [x[:3] for x in _MONTHS].index(mon.lower()[:3]) + 1, int(d)))
    for ms in re.findall(r"/Date\((\d{12,13})", s):
        out.append(datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).astimezone(config.TZ).date())
    return out


def is_fresh(report, today):
    """True/False when the report carries a recognizable date; None when it doesn't."""
    dates = [d for v in (report or {}).get("stamps", {}).values() for d in _stamp_dates(v)]
    if not dates:
        return None
    return max(dates) >= today


def fetch():
    if not config.RESORT_SNOW_REPORT_URL:  # this resort's report isn't read (yet)
        return {}
    try:
        r = get(config.RESORT_SNOW_REPORT_URL, headers={"Accept": "text/html"})
        if not r.ok:
            log.warning("Resort snow report HTTP %s", r.status_code)
            return {}
        return parse(r.text)
    except Exception as e:
        log.warning("Resort snow report failed: %s", e)
        return {}
