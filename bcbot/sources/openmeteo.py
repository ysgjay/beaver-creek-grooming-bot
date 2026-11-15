"""Open-Meteo: one free API that serves the same raw model output OpenSnow starts from
(GFS, HRRR, NBM, ECMWF, ICON, GEM, UKMO) at a point, plus ensembles for a forecast range."""
import logging

from .. import config
from ..util import get

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"

HOURLY_VARS = [
    "temperature_2m",
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
            continue
        rows = []
        for i, t in enumerate(times):
            row = {"time": t}
            for v, col in cols.items():
                row[v] = col[i] if col is not None and i < len(col) else None
            rows.append(row)
        if any(r["precipitation"] is not None for r in rows):
            out[m] = rows
    return out


def fetch_models(models=None):
    models = list(models or config.MODELS)
    params = _base_params() | {"hourly": ",".join(HOURLY_VARS), "models": ",".join(models)}
    r = get(FORECAST_URL, params=params)
    if r.ok:
        return _split_models(r.json(), models)
    # One unknown/retired model id fails the whole request: retry one at a time.
    log.warning("Open-Meteo multi-model request failed (%s): %s", r.status_code, r.text[:200])
    out = {}
    for m in models:
        rr = get(FORECAST_URL, params=params | {"models": m})
        if rr.ok:
            out.update(_split_models(rr.json(), [m]))
        else:
            log.warning("Open-Meteo model %s unavailable: %s", m, rr.text[:120])
    return out


def fetch_ensemble():
    """Return {member_key: [hour dicts with precipitation/temperature_2m]} across ensemble models."""
    params = _base_params() | {
        "hourly": "precipitation,temperature_2m",
        "models": ",".join(config.ENSEMBLE_MODELS),
    }
    r = get(ENSEMBLE_URL, params=params, timeout=60)
    r.raise_for_status()
    hourly = r.json().get("hourly", {})
    times = hourly.get("time", [])
    members = {}
    for key, col in hourly.items():
        if not key.startswith("precipitation"):
            continue
        member = key[len("precipitation"):]  # e.g. "_member03_gfs025" or "_ecmwf_ifs025"
        temps = hourly.get("temperature_2m" + member)
        if temps is None or col is None:
            continue
        rows = [
            {"time": t, "precipitation": col[i], "temperature_2m": temps[i]}
            for i, t in enumerate(times)
        ]
        if any(r["precipitation"] is not None for r in rows):
            members[member.lstrip("_") or "control"] = rows
    return members
