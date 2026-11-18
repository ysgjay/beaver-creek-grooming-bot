"""Turn raw model output into a Beaver Creek snow forecast.

Pipeline (the open-data version of what OpenSnow does):
  1. Raw hourly precip + temperature from many models at the forecast point, with
     temperature lapse-rate corrected to 10,476 ft (Open-Meteo `elevation`).
  2. Our own snow-to-liquid ratio from temperature. Open-Meteo's `snowfall` uses a
     fixed ~7:1 ratio, which badly under-forecasts dry Colorado snow (~12-18:1).
  3. Per-model bias correction learned from SNOTEL observations (verify.py), starting
     from each model's bias over last winter, then a snow calibration against the
     resort's own reported snowfall.
  4. Skill-weighted blend: short range leans on HRRR/NBM/NWS, longer range on
     ECMWF/NBM, each scaled by its recent accuracy at this spot.
  5. Forecast range from ensemble members (GFS 31 + ECMWF 51), and odds of a
     powder day.
"""
import math
from collections import defaultdict
from datetime import date, datetime, timedelta

from . import config
from .util import r1

# (temperature °F, snow:liquid ratio) - piecewise linear. Roughly the climatological
# curve for the Colorado Rockies: wet near freezing, fluffiest in the low teens.
_SLR_POINTS = [(34, 8.0), (30, 10.0), (24, 12.5), (18, 15.0), (12, 17.0), (5, 16.0), (-5, 13.0)]


def slr(temp_f):
    if temp_f is None:
        return 12.0
    pts = _SLR_POINTS
    if temp_f >= pts[0][0]:
        return pts[0][1]
    if temp_f <= pts[-1][0]:
        return pts[-1][1]
    for (t1, s1), (t2, s2) in zip(pts, pts[1:]):
        if t2 <= temp_f <= t1:
            return s1 + (s2 - s1) * (t1 - temp_f) / (t1 - t2)
    return 12.0


def wet_bulb_f(temp_f, rh):
    """Wet-bulb temperature (Stull 2011). Falling snow cools toward this in dry air,
    which is why it can snow at 36°F in Colorado and rain at 33°F in a soaked airmass."""
    t = (temp_f - 32) / 1.8
    rh = max(5.0, min(99.0, rh))
    tw = (t * math.atan(0.151977 * math.sqrt(rh + 8.313659)) + math.atan(t + rh) - math.atan(rh - 1.676331)
          + 0.00391838 * rh ** 1.5 * math.atan(0.023101 * rh) - 4.686035)
    return min(temp_f, tw * 1.8 + 32)


def snow_fraction(temp_f, rh=None):
    """Share of precip falling as snow.

    With humidity: by wet-bulb temperature, all snow at <=32°F and all rain at >=35.6°F
    (half and half near 34°F). Without it: all snow at <=31°F air temperature, rain at >=36°F.
    """
    if temp_f is None:
        return 1.0
    if rh is not None:
        tw = wet_bulb_f(temp_f, rh)
        return max(0.0, min(1.0, (35.6 - tw) / 3.6))
    if temp_f <= 31:
        return 1.0
    if temp_f >= 36:
        return 0.0
    return (36 - temp_f) / 5


def hourly_snow(precip_in, temp_f, rh=None):
    if not precip_in:
        return 0.0
    return precip_in * snow_fraction(temp_f, rh) * slr(temp_f)


def daily_totals(rows):
    """{date: {'snow': in, 'liquid': in}} from hourly rows (local-time ISO strings)."""
    days = defaultdict(lambda: {"snow": 0.0, "liquid": 0.0, "hours": 0})
    for r in rows:
        p = r.get("precipitation")
        if p is None:
            continue
        d = days[r["time"][:10]]
        d["liquid"] += p
        d["snow"] += hourly_snow(p, r.get("temperature_2m"), r.get("relative_humidity_2m"))
        d["hours"] += 1
    # Drop partial trailing days (a model whose run ends mid-day would look artificially dry).
    return {k: {"snow": v["snow"], "liquid": v["liquid"]} for k, v in days.items() if v["hours"] >= 20}


def _weight(model, lead):
    if model == config.NWS_MODEL:
        w = config.NWS_WEIGHT
    else:
        w = config.MODELS.get(model, {}).get("w", (1.0, 1.0))
    return w[0] if lead < 2 else w[1]


def _lead_group(lead):
    return "short" if lead < 2 else "mid" if lead < 5 else "long"


def _bias(st, lead):
    """The model's wet/dry correction for a call this many days ahead."""
    return (st.get("bias_by_lead") or {}).get(_lead_group(lead), st.get("bias_ratio", 1.0))


# Sanity anchor: the blend may not run more than this far above both the NWS forecasters and
# NOAA's own blend (and at least ANCHOR_MIN_IN above the larger of them).
ANCHORS = ("nws", "ncep_nbm_conus")
ANCHOR_RATIO = 1.5
ANCHOR_MIN_IN = 1.0


def _ensemble_parent(member):
    """'member03_gfs025' -> the scored model whose bias correction it inherits."""
    for piece, parent in config.ENSEMBLE_PARENT:
        if piece in member:
            return parent
    return None


def _percentile(values, q):
    v = sorted(values)
    if not v:
        return None
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def build(model_rows, nws_daily=None, ensemble_rows=None, verification=None, today=None):
    """Return the forecast document stored in data/ and rendered by the dashboard."""
    today = today or date.today()
    verification = verification or {}
    vstats = verification.get("models", {})
    dates = [(today + timedelta(days=i)).isoformat() for i in range(config.FORECAST_DAYS)]

    per_model = {m: daily_totals(rows) for m, rows in model_rows.items()}
    if nws_daily:
        per_model[config.NWS_MODEL] = {d: {"snow": s, "liquid": None} for d, s in nws_daily.items()}

    # Calibration of the finished snow number against the resort's own reports.
    snow_cal = (verification.get("snow_cal") or {}).get("ratio", 1.0)

    # Ensemble members get the same corrections as the headline number, so the range
    # sits around it instead of around the uncorrected models.
    lead_of = {d: i for i, d in enumerate(dates)}
    ens_daily = {}
    for k, rows in (ensemble_rows or {}).items():
        st = vstats.get(_ensemble_parent(k), {})
        ens_daily[k] = {d: {"snow": v["snow"] * _bias(st, lead_of.get(d, 0)) * snow_cal, "liquid": v["liquid"]}
                        for d, v in daily_totals(rows).items()}

    days = []
    for lead, d in enumerate(dates):
        num = den = 0.0
        values = {}
        for m, daily in per_model.items():
            if d not in daily:
                continue
            w = _weight(m, lead)
            if w <= 0:
                continue
            if d in per_model.get(config.MODELS.get(m, {}).get("unless"), {}):
                continue  # its higher-resolution version covers this day
            st = vstats.get(m, {})
            corrected = daily[d]["snow"] * _bias(st, lead) * snow_cal
            values[m] = r1(corrected)
            w *= st.get("skill", 1.0)
            num += w * corrected
            den += w
        if not values:
            continue
        snow = num / den
        anchors = [values[a] for a in ANCHORS if a in values]
        capped = False
        if len(anchors) == len(ANCHORS):
            cap = max(ANCHOR_RATIO * max(anchors), max(anchors) + ANCHOR_MIN_IN)
            if snow > cap:
                snow, capped = cap, True
        ens = [e[d]["snow"] for e in ens_daily.values() if d in e]
        if len(ens) >= 10:
            low, high = _percentile(ens, 0.1), _percentile(ens, 0.9)
            # The ceiling never sits below a model's own call: the ensembles are coarse
            # versions of two models, and a sharper model can see more snow than any of them.
            high = max(high, max(values.values()))
        else:
            low, high = min(values.values()), max(values.values())
        days.append({
            "date": d,
            "snow": r1(snow),
            "low": r1(min(low, snow)),
            "high": r1(max(high, snow)),
            "models": values,
        } | ({"capped": True} if capped else {}))

    def total(sl):
        return r1(sum(x["snow"] for x in days[sl]))

    def rng(sl):
        """Range of the bucket total. Summing daily percentiles overstates the spread,
        so use each ensemble member's own total when there are enough members."""
        bucket = [x["date"] for x in days[sl]]
        tot = total(sl)
        if len(ens_daily) >= 10 and bucket:
            sums = [sum(e.get(d, {}).get("snow", 0) for d in bucket) for e in ens_daily.values()]
            # Same rule as a single day: no lower than any model that covers the whole bucket.
            model_sums = [sum(x["models"][m] for x in days[sl]) for m in days[sl][0]["models"]
                          if all(m in x["models"] for x in days[sl])]
            return [r1(min(tot, _percentile(sums, 0.1))), r1(max([tot, _percentile(sums, 0.9)] + model_sums))]
        return [r1(sum(x["low"] for x in days[sl])), r1(sum(x["high"] for x in days[sl]))]

    # Odds of a powder day: share of ensemble members with >= threshold in any one day of days 1-5.
    powder_odds = None
    if len(ens_daily) >= 10:
        hits = 0
        for e in ens_daily.values():
            if any(e.get(d, {}).get("snow", 0) >= config.POWDER_ALERT_INCHES for d in dates[:5]):
                hits += 1
        powder_odds = round(100 * hits / len(ens_daily))

    return {
        "issued": today.isoformat(),
        "point": {"lat": config.LAT, "lon": config.LON, "elevation_ft": config.ELEVATION_FT},
        "snow_cal": snow_cal,
        "days": days,
        "next_1_5": total(slice(0, 5)),
        "next_1_5_range": rng(slice(0, 5)),
        "next_1_7": total(slice(0, 7)),
        "next_1_7_range": rng(slice(0, 7)),
        "next_6_10": total(slice(5, 10)),
        "next_6_10_range": rng(slice(5, 10)),
        "powder_odds_pct": powder_odds,
        "ensemble_members": len(ens_daily),
        "models_used": sorted(per_model),
        "model_labels": {m: (config.MODELS[m]["label"] if m in config.MODELS else "NWS forecasters")
                         for m in per_model},
        "raw": {m: {d: {"snow": r1(v["snow"]), "liquid": None if v["liquid"] is None else round(v["liquid"], 2)}
                    for d, v in daily.items()} for m, daily in per_model.items()},
    }


_HOURLY_PREF = ["gfs_hrrr", "ncep_nbm_conus", "ecmwf_ifs025", "gfs_global"]


def hourly_outlook(model_rows, now=None, hours=12):
    """Next N hours of weather from the best available short-range model."""
    now = now or datetime.now(config.TZ)
    start = now.replace(minute=0, second=0, microsecond=0, tzinfo=None).isoformat(timespec="minutes")
    for m in _HOURLY_PREF + list(model_rows):
        rows = [r for r in model_rows.get(m, []) if r["time"] >= start and r.get("temperature_2m") is not None]
        if len(rows) >= hours:
            return {
                "model": m,
                "hours": [{
                    "time": r["time"],
                    "temp": _round(r.get("temperature_2m")),
                    "feels": _round(r.get("apparent_temperature")),
                    "wind": _round(r.get("wind_speed_10m")),
                    "gust": _round(r.get("wind_gusts_10m")),
                    "dir": compass(r.get("wind_direction_10m")),
                    "cloud": _round(r.get("cloud_cover")),
                    "snow": r1(hourly_snow(r.get("precipitation") or 0, r.get("temperature_2m"),
                                           r.get("relative_humidity_2m"))),
                } for r in rows[:hours]],
            }
    return {"model": None, "hours": []}


def band_outlook(band_rows, now=None, bands=None, hours=12):
    """Weather by elevation: [{key, label, elevation_ft, now, hours, days}] for base / mid / peak.

    `hours` is the next N hours (same clock hours as `hourly_outlook`) and `now` is the
    first of them. Each day has the high, the low and `snow_pct`:
    the share of that day's precipitation falling as snow at that elevation (None when dry),
    which is what separates rain at the base from snow up top.
    """
    now = now or datetime.now(config.TZ)
    hour = now.replace(minute=0, second=0, microsecond=0, tzinfo=None).isoformat(timespec="minutes")
    out = []
    for band in (bands or config.ELEVATION_BANDS):
        rows = [r for r in band_rows.get(band["key"], []) if r.get("temperature_2m") is not None]
        if not rows:
            continue
        ahead = [{
            "time": r["time"],
            "temp": _round(r.get("temperature_2m")),
            "feels": _round(r.get("apparent_temperature")),
            "wind": _round(r.get("wind_speed_10m")),
            "gust": _round(r.get("wind_gusts_10m")),
        } for r in rows if r["time"] >= hour][:hours]
        by_day = defaultdict(list)
        for r in rows:
            by_day[r["time"][:10]].append(r)
        days = []
        for d, hrs in sorted(by_day.items()):
            if len(hrs) < 20:  # partial day: its high or low would be wrong
                continue
            liquid = sum(r.get("precipitation") or 0 for r in hrs)
            frozen = sum((r.get("precipitation") or 0)
                         * snow_fraction(r["temperature_2m"], r.get("relative_humidity_2m")) for r in hrs)
            days.append({
                "date": d,
                "high": round(max(r["temperature_2m"] for r in hrs)),
                "low": round(min(r["temperature_2m"] for r in hrs)),
                "snow_pct": round(100 * frozen / liquid) if liquid >= 0.01 else None,
            })
        out.append({
            "key": band["key"],
            "label": band["label"],
            "elevation_ft": band["elevation_ft"],
            "now": ahead[0] if ahead and ahead[0]["time"] == hour else None,
            "hours": ahead,
            "days": days,
        })
    return out


def _round(x):
    return None if x is None else round(x)


def compass(deg):
    if deg is None:
        return ""
    names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return names[round(deg / 22.5) % 16]
