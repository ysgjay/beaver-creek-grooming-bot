"""Open-Meteo: one free API that serves the same raw model output OpenSnow starts from
(GFS, HRRR, NBM, ECMWF, ICON, GEM, UKMO) at a point, plus ensembles for a forecast range."""
import logging

from .. import config
from ..util import get

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
HISTORY_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"

HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "snowfall",
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_direction_10m",
    "cloud_cover",
]


def _base_params():
    return {
        "latitude": config.LAT,
        "longitude": config.LON,
        "elevation": config.ELEVATION_M,
        "timezone": config.TZ.key,
        "forecast_days": config.FORECAST_DAYS,
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
    }


def _split_models(payload, models):
    """Turn Open-Meteo's `var_model` columns into {model: [hour dicts]}."""
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    out = {}
    for m in models:
        suffix = "" if len(models) == 1 else f"_{m}"
        cols = {v: hourly.get(v + suffix) for v in HOURLY_VARS}
        if cols["precipitation"] is None or cols["temperature_2m"] is None:
            log.warning("Open-Meteo sent no %s columns (keys: %s)", m, sorted(k for k in hourly if m in k)[:6])
            continue
        rows = []
        for i, t in enumerate(times):
            row = {"time": t}
            for v, col in cols.items():
                row[v] = col[i] if col is not None and i < len(col) else None
            rows.append(row)
        if any(r["precipitation"] is not None for r in rows):
            out[m] = rows
        else:
            log.warning("Open-Meteo sent only empty precipitation for %s (%d hours)", m, len(rows))
    return out


def fetch_models(models=None):
    """Core models in one request, then the `extra` (newer, higher-resolution) ones in another."""
    if models is None:
        core = [m for m, c in config.MODELS.items() if not c.get("extra")]
        extra = [m for m, c in config.MODELS.items() if c.get("extra")]
        out = _fetch_models(core)
        if extra:
            try:
                out.update(_fetch_models(extra, timeout=15, retries=0))  # the run has 60 s in all
            except Exception as e:  # never lose the core models over an extra one
                log.warning("Open-Meteo extra models failed: %s", e)
        return out
    return _fetch_models(list(models))


def _fetch_models(models, **opts):
    params = _base_params() | {"hourly": ",".join(HOURLY_VARS), "models": ",".join(models)}
    r = get(FORECAST_URL, params=params, **opts)
    if r.ok:
        return _split_models(r.json(), models)
    # One unknown/retired model id fails the whole request: retry one at a time.
    log.warning("Open-Meteo multi-model request failed (%s): %s", r.status_code, r.text[:200])
    out = {}
    for m in models:
        rr = get(FORECAST_URL, params=params | {"models": m}, **opts)
        if rr.ok:
            out.update(_split_models(rr.json(), [m]))
        else:
            log.warning("Open-Meteo model %s unavailable: %s", m, rr.text[:120])
    return out


def fetch_ensemble():
    """Return {member_key: [hour dicts with precipitation/temperature_2m]} across ensemble models."""
    params = _base_params() | {
        "hourly": "precipitation,temperature_2m,relative_humidity_2m",
        "models": ",".join(config.ENSEMBLE_MODELS),
    }
    r = get(ENSEMBLE_URL, params=params, timeout=60)
    if not r.ok:  # humidity only sharpens the rain/snow line; the range works without it
        log.warning("Open-Meteo ensemble with humidity failed (%s); retrying without", r.status_code)
        r = get(ENSEMBLE_URL, params=params | {"hourly": "precipitation,temperature_2m"}, timeout=60)
    r.raise_for_status()
    return split_ensemble(r.json())


def split_ensemble(payload):
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    members = {}
    for key, col in hourly.items():
        if not key.startswith("precipitation"):
            continue
        member = key[len("precipitation"):]  # e.g. "_member03_gfs025" or "_ecmwf_ifs025"
        temps = hourly.get("temperature_2m" + member)
        if temps is None or col is None:
            continue
        rh = hourly.get("relative_humidity_2m" + member)
        rows = [
            {"time": t, "precipitation": col[i], "temperature_2m": temps[i],
             "relative_humidity_2m": rh[i] if rh else None}
            for i, t in enumerate(times)
        ]
        if any(r["precipitation"] is not None for r in rows):
            members[member.lstrip("_") or "control"] = rows
    return members


BAND_VARS = ["temperature_2m", "relative_humidity_2m", "apparent_temperature", "precipitation", "wind_speed_10m", "wind_gusts_10m"]


def fetch_bands(bands=None):
    """Hourly weather at each elevation band (base / mid / peak) in one request.

    Returns {band key: [hour dicts]}. Uses Open-Meteo's best-match model; each band's
    temperature is lapse-rate corrected to that band's own elevation.
    """
    bands = list(bands or config.ELEVATION_BANDS)
    params = _base_params() | {
        "latitude": ",".join(f"{b['lat']:.4f}" for b in bands),
        "longitude": ",".join(f"{b['lon']:.4f}" for b in bands),
        "elevation": ",".join(str(round(b["elevation_ft"] * 0.3048)) for b in bands),
        "hourly": ",".join(BAND_VARS),
    }
    r = get(FORECAST_URL, params=params)
    r.raise_for_status()
    return split_bands(r.json(), bands)


def split_bands(payload, bands):
    """Open-Meteo answers several locations with a list, in request order (one location: a dict)."""
    locations = payload if isinstance(payload, list) else [payload]
    out = {}
    for band, loc in zip(bands, locations):
        hourly = loc.get("hourly", {})
        temps = hourly.get("temperature_2m")
        if not temps:
            continue
        out[band["key"]] = [
            {"time": t} | {v: (hourly[v][i] if hourly.get(v) and i < len(hourly[v]) else None) for v in BAND_VARS}
            for i, t in enumerate(hourly.get("time", []))
        ]
    return out


def fetch_history(start, end, models=None):
    """Daily liquid precip each model forecast at the point over a past period.

    Open-Meteo's historical forecast archive stitches together each model's shortest-range
    output, so this is what the model said at the time, not a later reanalysis.
    Returns {model: {date: inches}}.
    """
    models = list(models or config.MODELS)
    params = _base_params() | {"daily": "precipitation_sum", "models": ",".join(models),
                               "start_date": start.isoformat(), "end_date": end.isoformat()}
    params.pop("forecast_days")
    r = get(HISTORY_URL, params=params, timeout=20, retries=0)  # runs inside the 60 s daily job
    if r.ok:
        return split_history(r.json(), models)
    log.warning("Open-Meteo history request failed (%s): %s", r.status_code, r.text[:200])
    out = {}
    for m in models:  # a model the archive doesn't hold fails the whole request
        rr = get(HISTORY_URL, params=params | {"models": m}, timeout=10, retries=0)
        if rr.ok:
            out.update(split_history(rr.json(), [m]))
    return out


def split_history(payload, models):
    daily = payload.get("daily", {})
    times = daily.get("time", [])
    out = {}
    for m in models:
        col = daily.get("precipitation_sum" if len(models) == 1 else f"precipitation_sum_{m}")
        if not col:
            continue
        days = {t: v for t, v in zip(times, col) if v is not None}
        if days:
            out[m] = days
    return out
