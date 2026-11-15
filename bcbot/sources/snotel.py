"""NRCS SNOTEL ground truth (snow depth, snow water equivalent, accumulated precip).

This is the same class of station data OpenSnow's PEAKS 2.0 uses to bias-correct models.
Daily SNOTEL values are midnight readings, so what fell *on* date D is value[D+1] - value[D].
"""
import logging
from datetime import date, timedelta

from .. import config
from ..util import get

log = logging.getLogger(__name__)

API = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data"


def _fetch(triplet, duration, begin, end, elements="SNWD,WTEQ,PREC,TOBS"):
    r = get(
        API,
        params={
            "stationTriplets": triplet,
            "elements": elements,
            "duration": duration,
            "beginDate": begin,
            "endDate": end,
        },
        timeout=45,
    )
    r.raise_for_status()
    series = {}
    for station in r.json():
        for el in station.get("data", []):
            code = el["stationElement"]["elementCode"]
            series[code] = {v["date"]: v.get("value") for v in el.get("values", []) if "date" in v}
    return series


def daily_observations(series):
    """{date: {'precip_in', 'depth_change_in', 'depth_in'}} for each complete day."""
    prec, depth = series.get("PREC", {}), series.get("SNWD", {})
    out = {}
    for d in sorted(set(prec) | set(depth)):
        nxt = (date.fromisoformat(d[:10]) + timedelta(days=1)).isoformat()
        row = {"depth_in": depth.get(d)}
        if prec.get(d) is not None and prec.get(nxt) is not None:
            row["precip_in"] = round(max(0.0, prec[nxt] - prec[d]), 2)
        if depth.get(d) is not None and depth.get(nxt) is not None:
            row["depth_change_in"] = depth[nxt] - depth[d]
        out[d[:10]] = row
    return out


def last_24h(hourly):
    """New snow over the last 24 hours from hourly snow depth (positive change only)."""
    depth = [(k, v) for k, v in sorted(hourly.get("SNWD", {}).items()) if v is not None]
    prec = [(k, v) for k, v in sorted(hourly.get("PREC", {}).items()) if v is not None]
    out = {}
    if len(depth) >= 24:
        recent = [v for _, v in depth[-25:]]
        # Max rise from the 24h-ago reading (depth settles after the storm, so use the peak).
        out["snow_in"] = max(0.0, max(recent) - recent[0])
        out["depth_in"] = depth[-1][1]
        out["as_of"] = depth[-1][0]
    if len(prec) >= 24:
        out["precip_in"] = round(max(0.0, prec[-1][1] - prec[-25][1]), 2)
    return out


def fetch(days_back=21):
    today = date.today()
    begin = (today - timedelta(days=days_back)).isoformat()
    for triplet in config.SNOTEL_STATIONS:
        try:
            daily = _fetch(triplet, "DAILY", begin, today.isoformat())
            hourly = _fetch(
                triplet, "HOURLY", (today - timedelta(days=2)).isoformat(),
                (today + timedelta(days=1)).isoformat(), elements="SNWD,PREC",
            )
            obs = daily_observations(daily)
            if not obs:
                raise ValueError("no data")
            return {"station": triplet, "daily": obs, "last_24h": last_24h(hourly)}
        except Exception as e:  # station offline -> try the next one
            log.warning("SNOTEL %s failed: %s", triplet, e)
    return {}
