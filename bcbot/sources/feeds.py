"""Small per-resort snow report readers, picked by a resort's "report_feed" in resorts.py:

  {"kind": "text", "url": <report page>, "start": <heading>, "order": "after"|"before"}
                                                               server-rendered page (sources/textpage.py)
  {"kind": "json", "url": <feed>, "fields": {our key: dotted path}, "stamp": <path>}
                                                               a resort's own report JSON (Jackson Hole, Taos)

Each parser returns the same shape as resort.parse (inches, plus "stamps" with a resort-local date).
"""
import logging
import re

from .. import config
from ..util import get
from . import textpage

log = logging.getLogger(__name__)


def _num(v):
    if isinstance(v, dict):
        v = v.get("value")
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _at(obj, path):
    for part in (path or "").split("."):
        if not part:
            continue
        if isinstance(obj, list):
            obj = obj[int(part)] if part.isdigit() and int(part) < len(obj) else None
        elif isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


def parse_json(j, feed):
    """A resort's own report JSON. feed["fields"] maps our keys to dotted paths, e.g.
    {"last_24h_in": "snowData.last24Hours"}; feed["stamp"] is a path to an ISO time in resort time
    ("2026-11-18T08:30:00-07:00"). Values may be numbers, numeric strings or {"value": ...}."""
    out = {}
    for key, path in feed["fields"].items():
        v = _num(_at(j, path))
        if v is not None:
            out[key] = round(v / 2.54, 1) if feed.get("cm") else v
    if not out:
        return {}
    stamp = str(_at(j, feed.get("stamp")) or "") if feed.get("stamp") else ""
    if re.match(r"20\d\d-\d\d-\d\d", stamp):
        out["stamps"] = {"updated": stamp[:10]}
        m = re.search(r"T(\d\d):(\d\d)", stamp)
        if m:
            hh, mm = int(m.group(1)), int(m.group(2))
            out["updated_time"] = f"{(hh % 12) or 12}:{mm:02d} {'AM' if hh < 12 else 'PM'}"
    return out


def parse_text(html, feed=None):
    feed = feed or {}
    return textpage.parse(html, feed.get("start"), feed.get("order", "after"))


KINDS = {"json": (parse_json, "json"), "text": (parse_text, "html")}


def fetch_snow_report(feed=None):
    feed = feed or config.REPORT_FEED
    parse, fmt = KINDS[feed["kind"]]
    try:
        r = get(feed["url"], headers={"Accept": "application/json" if fmt == "json" else "text/html"}, timeout=20)
        if not r.ok:
            log.warning("%s snow report HTTP %s", feed["kind"], r.status_code)
            return {}
        return parse(r.json() if fmt == "json" else r.text, feed)
    except Exception as e:
        log.warning("%s snow report failed: %s", feed["kind"], e)
        return {}
