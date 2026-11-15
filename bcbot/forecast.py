"""Turn raw model output into a Beaver Creek snow forecast.

Pipeline (the open-data version of what OpenSnow does):
  1. Raw hourly precip + temperature from many models at the forecast point, with
     temperature lapse-rate corrected to 10,476 ft (Open-Meteo `elevation`).
  2. Our own snow-to-liquid ratio from temperature. Open-Meteo's `snowfall` uses a
     fixed ~7:1 ratio, which badly under-forecasts dry Colorado snow (~12-18:1).
  3. Per-model bias correction learned from SNOTEL observations (verify.py).
  4. Skill-weighted blend: short range leans on HRRR/NBM/NWS, longer range on
     ECMWF/NBM, each scaled by its recent accuracy at this spot.
  5. Forecast range from ensemble members (GFS 31 + ECMWF 51), and odds of a
     powder day.
"""
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


def snow_fraction(temp_f):
    """Share of precip falling as snow: all snow at <=31°F, all rain at >=36°F."""
    if temp_f is None:
        return 1.0
    if temp_f <= 31:
        return 1.0
    if temp_f >= 36:
        return 0.0
    return (36 - temp_f) / 5


def hourly_snow(precip_in, temp_f):
    if not precip_in:
        return 0.0
    return precip_in * snow_fraction(temp_f) * slr(temp_f)


def daily_totals(rows):
    """{date: {'snow': in, 'liquid': in}} from hourly rows (local-time ISO strings)."""
    days = defaultdict(lambda: {"snow": 0.0, "liquid": 0.0, "hours": 0})
    for r in rows:
        p = r.get("precipitation")
        if p is None:
            continue
        d = days[r["time"][:10]]
        d["liquid"] += p
        d["snow"] += hourly_snow(p, r.get("temperature_2m"))
        d["hours"] += 1
    # Drop partial trailing days (a model whose run ends mid-day would look artificially dry).
    return {k: {"snow": v["snow"], "liquid": v["liquid"]} for k, v in days.items() if v["hours"] >= 20}


def _weight(model, lead):
    if model == config.NWS_MODEL:
        w = config.NWS_WEIGHT
    else:
        w = config.MODELS.get(model, {}).get("w", (1.0, 1.0))
    return w[0] if lead < 2 else w[1]


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

    ens_daily = {k: daily_totals(rows) for k, rows in (ensemble_rows or {}).items()}

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
            st = vstats.get(m, {})
            corrected = daily[d]["snow"] * st.get("bias_ratio", 1.0)
            values[m] = r1(corrected)
            w *= st.get("skill", 1.0)
            num += w * corrected
            den += w
        if not values:
            continue
        snow = num / den
        ens = [e[d]["snow"] for e in ens_daily.values() if d in e]
        if len(ens) >= 10:
            low, high = _percentile(ens, 0.1), _percentile(ens, 0.9)
        else:
            low, high = min(values.values()), max(values.values())
        days.append({
            "date": d,
            "snow": r1(snow),
            "low": r1(min(low, snow)),
            "high": r1(max(high, snow)),
            "models": values,
        })

    def total(sl):
        return r1(sum(x["snow"] for x in days[sl]))

    def rng(sl):
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
        "days": days,
        "next_1_5": total(slice(0, 5)),
        "next_1_5_range": rng(slice(0, 5)),
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


_HOURLY_PREF = ["gfs_hrrr", "ncep_nbm_conus", "ecmwf_ifs025", "gfs_seamless"]


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
                    "snow": r1(hourly_snow(r.get("precipitation") or 0, r.get("temperature_2m"))),
                } for r in rows[:hours]],
            }
    return {"model": None, "hours": []}


def _round(x):
    return None if x is None else round(x)


def compass(deg):
    if deg is None:
        return ""
    names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return names[round(deg / 22.5) % 16]
