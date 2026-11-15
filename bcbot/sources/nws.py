"""National Weather Service gridded forecast (2.5 km, forecaster-edited NBM). Snowfall per local day."""
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta

from .. import config
from ..util import get

log = logging.getLogger(__name__)

_DUR = re.compile(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?")


def _parse_interval(valid_time):
    start_s, dur_s = valid_time.split("/")
    start = datetime.fromisoformat(start_s)
    m = _DUR.fullmatch(dur_s)
    if not m:
        raise ValueError(f"bad duration {dur_s}")
    d, h, mi = (int(x) if x else 0 for x in m.groups())
    return start, timedelta(days=d, hours=h, minutes=mi)


MIN_HOURS = 20  # same rule as the models: a partly covered day would look artificially dry


def daily_from_intervals(values, to_inches=1 / 25.4, min_hours=0):
    """Spread each interval's amount evenly over its hours and sum by local date.

    With `min_hours`, days the grid covers for fewer hours are left out. The NWS grid starts
    at the current hour, so "today" holds only the snow still to come, while every model
    counts the whole day; blending the two dragged today's number down.
    """
    days = defaultdict(float)
    covered = defaultdict(int)
    for v in values:
        amount = v.get("value")
        if amount is None:
            continue
        start, dur = _parse_interval(v["validTime"])
        hours = max(1, int(dur.total_seconds() // 3600))
        per_hour = amount * to_inches / hours
        for i in range(hours):
            local = (start + timedelta(hours=i)).astimezone(config.TZ)
            days[local.date().isoformat()] += per_hour
            covered[local.date().isoformat()] += 1
    return {d: v for d, v in days.items() if covered[d] >= min_hours}


def fetch_snowfall():
    """Return {date: inches} of NWS forecast snowfall at the forecast point."""
    headers = {"Accept": "application/geo+json"}
    pts = get(f"https://api.weather.gov/points/{config.LAT:.4f},{config.LON:.4f}", headers=headers)
    pts.raise_for_status()
    grid_url = pts.json()["properties"]["forecastGridData"]
    g = get(grid_url, headers=headers)
    g.raise_for_status()
    snow = g.json()["properties"].get("snowfallAmount", {})
    uom = snow.get("uom", "wmoUnit:mm")
    factor = 1 / 25.4 if uom.endswith("mm") else (1 / 2.54 if uom.endswith("cm") else 1.0)
    return daily_from_intervals(snow.get("values", []), to_inches=factor, min_hours=MIN_HOURS)
