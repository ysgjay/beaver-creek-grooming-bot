"""Open-Meteo: one free API that serves the same raw model output OpenSnow starts from
(GFS, HRRR, NBM, ECMWF, ICON, GEM, UKMO) at a point, plus ensembles for a forecast range."""
import logging
import os

from .. import config
from ..util import get as _http_get

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
HISTORY_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"


def self_hosted_base():
    """Our own Open-Meteo server (Render, docs/RENDER.md), if configured: OPEN_METEO_URL
    (e.g. http://snow-meteo:8080), or OPEN_METEO_HOST (the private host name a Render blueprint
    hands out) plus OPEN_METEO_PORT (default 8080, the port the image listens on)."""
    url = os.environ.get("OPEN_METEO_URL", "").strip().rstrip("/")
    host = os.environ.get("OPEN_METEO_HOST", "").strip()
    if not url and host:
        url = f"http://{host}:{os.environ.get('OPEN_METEO_PORT', '').strip() or '8080'}"
    return url or None


_SELF_PATHS = {FORECAST_URL: "/v1/forecast", ENSEMBLE_URL: "/v1/ensemble"}


def _has_data(r):
    """A 200 from our server can still be empty (no hourly block, or every value null) while
    it warms up. Treat that as a miss so the public API answers instead."""
    try:
        j = r.json()
    except Exception:
        return False
    # Several places in one call come back as a list of answers, one per place: each needs data.
    answers = j if isinstance(j, list) else [j]
    return bool(answers) and all(_answer_has_data(a) for a in answers)


def _answer_has_data(j):
    if not isinstance(j, dict):
        return False
    blocks = [b for b in (j.get("hourly"), j.get("daily")) if isinstance(b, dict)]
    return any(isinstance(v, list) and any(x is not None for x in v)
               for b in blocks for k, v in b.items() if k != "time")


def get(url, **opts):
    """Forecast and ensemble calls go to our own server first when one is configured, and fall
    back to the public API if it errors or refuses (a model it can't serve yet, a cold start).
    History and previous-runs stay on the public API: they run once a season or in backfill."""
    base = self_hosted_base()
    path = _SELF_PATHS.get(url)
    if base and path:
        try:
            r = _http_get(base + path, **(opts | {"retries": 0}))
            if r.ok and _has_data(r):
                return r
            log.warning("self-hosted Open-Meteo %s returned %s; using the public API: %s",
                        path, r.status_code, r.text[:160])
        except Exception as e:
            log.warning("self-hosted Open-Meteo %s failed (%s); using the public API", path, e)
    r = _http_get(url, **opts)
    if r.status_code == 429:  # the free public API's per-minute limit: wait it out once, with jitter
        import random
        import time
        try:
            wait = float(r.headers.get("Retry-After") or 0)
        except (TypeError, ValueError, AttributeError):
            wait = 0
        time.sleep(min(max(wait, 3.0), 8.0) + random.uniform(0, 2))
        log.warning("Open-Meteo 429 on %s; trying once more", url)
        r = _http_get(url, **opts)
    return r

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
        here = config.models_here()
        core = [m for m, c in here.items() if not c.get("extra")]
        extra = [m for m, c in here.items() if c.get("extra")]
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
    r = get(ENSEMBLE_URL, params=params, timeout=30, retries=0)
    if r.status_code == 429:  # rate limited even after waiting: smaller asks would only add to it
        r.raise_for_status()
    if not r.ok:  # one extra ensemble being down must not cost the core two
        log.warning("Open-Meteo full ensemble failed (%s); retrying with the core models", r.status_code)
        r = get(ENSEMBLE_URL, params=params | {"models": ",".join(config.ENSEMBLE_CORE)}, timeout=30)
    if not r.ok:  # humidity only sharpens the rain/snow line; the range works without it
        log.warning("Open-Meteo ensemble with humidity failed (%s); retrying without", r.status_code)
        r = get(ENSEMBLE_URL, params=params | {"models": ",".join(config.ENSEMBLE_CORE),
                                               "hourly": "precipitation,temperature_2m"}, timeout=30)
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
    models = list(models or config.models_here())
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


# Forecast range group -> how many days before the target day the run was made. The
# historical archive above only holds each model's newest run, which is far wetter than the
# same model a few days out, so a correction learned there over-corrects days 2-9.
LEAD_DAYS = {"short": 1, "mid": 3, "long": 5}
# The archive's "HRRR" is GFS stitched in (identical day for day), so it gets no prior.
NO_PRIOR_MODELS = {"gfs_hrrr"}


def fetch_history_by_lead(start, end, models=None):
    """Daily liquid precip each model forecast 1, 3 and 5 days ahead over a past period.

    Returns {lead group: {model: {date: inches}}}. A day counts only when 20+ hours are present.
    """
    models = [m for m in (models or config.models_here()) if m not in NO_PRIOR_MODELS]
    hourly = ",".join(f"precipitation_previous_day{n}" for n in LEAD_DAYS.values())
    params = _base_params() | {"hourly": hourly, "models": ",".join(models),
                               "start_date": start.isoformat(), "end_date": end.isoformat()}
    params.pop("forecast_days")
    r = get(PREVIOUS_RUNS_URL, params=params, timeout=25, retries=0)
    if r.ok:
        return split_history_by_lead(r.json(), models)
    log.warning("Open-Meteo previous-runs request failed (%s): %s", r.status_code, r.text[:200])
    out = {g: {} for g in LEAD_DAYS}
    for m in models:  # a model the archive doesn't hold fails the whole request
        rr = get(PREVIOUS_RUNS_URL, params=params | {"models": m}, timeout=10, retries=0)
        if rr.ok:
            for g, v in split_history_by_lead(rr.json(), [m]).items():
                out[g].update(v)
    return out


def split_history_by_lead(payload, models):
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    out = {g: {} for g in LEAD_DAYS}
    for g, n in LEAD_DAYS.items():
        for m in models:
            col = hourly.get(f"precipitation_previous_day{n}" + ("" if len(models) == 1 else f"_{m}"))
            if not col:
                continue
            sums, hours = {}, {}
            for t, v in zip(times, col):
                if v is None:
                    continue
                d = t[:10]
                sums[d] = sums.get(d, 0.0) + v
                hours[d] = hours.get(d, 0) + 1
            days = {d: round(v, 3) for d, v in sums.items() if hours[d] >= 20}
            if days:
                out[g][m] = days
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
