"""All tunable settings in one place. Secrets come from environment variables.

Per-resort settings (forecast point, bands, grooming PDF, snow report, SNOTEL, cams, time
zone, opening day) start as Beaver Creek's and are switched with `use(slug)` before a run
(see resorts.py). They live in a context variable, not module globals, so two resorts
running at once in one process (Vercel serves concurrent requests in one instance) never
see each other's settings: `config.LAT` reads the current request's resort.
"""
import contextvars
import os
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


# Forecast point, grooming PDF and snow report: set per resort by use() at the bottom.
# Elevation bands (base / mid / peak) shown beside the forecast: per resort, in resorts.py.

# Deterministic models pulled from Open-Meteo. Key = Open-Meteo model id.
# base weights: (days 1-2, days 3+). The weights are the "prior"; verification
# against SNOTEL then scales them by each model's recent skill at this spot.
MODELS = {
    "ncep_nbm_conus": {"label": "NBM (NOAA blend)", "w": (3.0, 3.0)},
    "gfs_hrrr": {"label": "HRRR 3 km", "w": (3.0, 0.0)},
    # ECMWF at 25 km flattens the mountain; it only votes on days the 9 km run is missing.
    "ecmwf_ifs025": {"label": "ECMWF 25 km", "w": (2.0, 2.5), "unless": "ecmwf_ifs"},
    # gfs_global, not gfs_seamless: "seamless" is HRRR for the first ~2 days, which would
    # count HRRR twice in the blend (and grade HRRR numbers as "GFS" in Snow Audit).
    "gfs_global": {"label": "GFS", "w": (1.0, 1.0)},
    "icon_seamless": {"label": "ICON (German)", "w": (1.5, 1.5)},
    "gem_seamless": {"label": "GEM (Canadian)", "w": (1.0, 1.0)},
    "ukmo_seamless": {"label": "UKMO", "w": (1.0, 1.0)},
    # Higher-resolution runs that see more of the terrain. `extra` models are fetched in
    # their own request, so one being unavailable never costs the core models.
    "ecmwf_ifs": {"label": "ECMWF 9 km", "w": (2.5, 3.0), "extra": True},
}
# NWS forecaster-edited gridded snowfall (2.5 km, days 1-7) joins the blend as its own "model".
NWS_MODEL = "nws"
NWS_WEIGHT = (2.5, 2.0)

ENSEMBLE_MODELS = ["ecmwf_ifs025", "gfs025", "ecmwf_aifs025", "icon_seamless", "gem_global",
                   "ukmo_global_ensemble_20km"]
# If the full request fails, the range still comes from these.
ENSEMBLE_CORE = ["ecmwf_ifs025", "gfs025"]
# Which scored model's bias correction each ensemble's members inherit, matched by a piece of
# the member's column name, first match wins (AIFS, ECMWF's AI model, has no scored twin).
ENSEMBLE_PARENT = [("aifs", None), ("ecmwf_ifs025", "ecmwf_ifs025"), ("gfs025", "gfs_global"),
                   ("gefs", "gfs_global"), ("icon", "icon_seamless"), ("gem", "gem_seamless"),
                   ("ukmo", "ukmo_seamless")]

FORECAST_DAYS = 10

# SNOTEL ground truth: per resort (resorts.py), nearest station first.

# Cams are Brown Rice streams: /snapshot/<id> is a still, /embed/<id> the live player.
# CAM_IDS ("id:Label,...") overrides Beaver Creek's list; first = snow stake.
BROWNRICE = "https://player.brownrice.com"
_CAMS_ENV = [c.strip() for c in os.environ.get("CAM_IDS", "").split(",") if c.strip()]


def _cams_from_ids(ids):
    return [{"label": label, "image": f"{BROWNRICE}/snapshot/{cid}", "live": f"{BROWNRICE}/embed/{cid}"}
            for cid, _, label in (c.partition(":") for c in ids)]



# Notifications
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://snow.0xm.studio/")
# Notifications go out only when this is "1" (so a new deployment can't double-post).
SEND_ENABLED = os.environ.get("SEND_ENABLED") == "1"
# A run with no new grooming map still refreshes the forecast when it's older than this.
REFRESH_HOURS = float(os.environ.get("REFRESH_HOURS", "6"))
# Daily send timing (in each resort's own time zone, resorts.py "tz"):
#   before OPENING_DAY: every morning at SEND_TIME, grooming map or not;
#   in season: as soon as a new map AND today's resort snow report are confirmed, from
#   SEND_EARLIEST; at SEND_LATEST whatever is available goes out.
# Beaver Creek's; other resorts have their own in resorts.py (env OPENING_DAY_<SLUG> overrides).
SEND_TIME = os.environ.get("SEND_TIME", "07:00")
SEND_EARLIEST = os.environ.get("SEND_EARLIEST", "05:00")
SEND_LATEST = os.environ.get("SEND_LATEST", "09:00")
# No morning report goes out after this (a resort added, or a run forced, in the evening
# refreshes its data but waits for the next morning to send).
SEND_CUTOFF = os.environ.get("SEND_CUTOFF", "12:00")
# In the half hour before SEND_TIME, refresh anything older than an hour.
PRE_SEND_MINUTES = 30
# After opening: if the map hasn't changed in this many days, the season is over; stay quiet.
IN_SEASON_DAYS = 3
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
# Web Push: identifies the sender to browser push services (RFC 8292).
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "https://snow.0xm.studio")
# The private key lives only in Vercel (VAPID_PRIVATE_KEY, raw 32-byte scalar, base64url).
# Its public half is derived from it and served by GET /api/push.

POWDER_ALERT_INCHES = float(os.environ.get("POWDER_ALERT_INCHES", "6"))

USER_AGENT = "beaver-creek-grooming-bot (github.com/ysgjay/beaver-creek-grooming-bot)"


_PER_RESORT = ("RESORT", "RESORT_NAME", "TZ", "OPENING_DAY", "LAT", "LON", "ELEVATION_FT", "ELEVATION_M",
               "GROOMING_PDF_URL", "RESORT_SNOW_REPORT_URL", "SNOTEL_STATIONS", "ELEVATION_BANDS", "CAMS",
               "STAKE_SNAPSHOT_URL", "DOR_API", "REPORTPAL", "REPORT_FEED", "IN_US")
_current = contextvars.ContextVar("snow_desk_resort", default=None)
_defaults = {}


def _settings(slug):
    from . import resorts
    r = resorts.get(slug)
    cams = _cams_from_ids(_CAMS_ENV) if slug == resorts.DEFAULT and _CAMS_ENV else r["cams"]
    stake = (os.environ.get("STAKE_SNAPSHOT_URL") if slug == resorts.DEFAULT else None) or (
        cams[0]["image"] if cams and "stake" in cams[0]["label"].lower() else "")
    return r, {
        "RESORT": slug, "RESORT_NAME": r["name"],
        "TZ": ZoneInfo(r["tz"]),  # send times, "today" and every date are in the resort's own zone
        "OPENING_DAY": r["opening_day"],
        "LAT": r["lat"], "LON": r["lon"], "ELEVATION_FT": r["elevation_ft"], "ELEVATION_M": r["elevation_m"],
        "GROOMING_PDF_URL": r["grooming_pdf"], "RESORT_SNOW_REPORT_URL": r["snow_report"],
        "SNOTEL_STATIONS": r["snotel"], "ELEVATION_BANDS": r["bands"],
        "CAMS": cams, "STAKE_SNAPSHOT_URL": stake, "DOR_API": r.get("dor_api"), "REPORTPAL": r.get("reportpal"),
        "REPORT_FEED": r.get("report_feed"),
        "IN_US": r["country"] == "US",  # NWS only covers the US
    }


def use(slug):
    """Point every per-resort setting at `slug` for the current thread/request. Returns the resort dict."""
    r, values = _settings(slug)
    _current.set(values)
    return r


def __getattr__(name):
    if name in _PER_RESORT:
        values = _current.get()
        if values is None:  # a thread or request that hasn't picked a resort: Beaver Creek
            from . import resorts
            values = _defaults.get("v") or _defaults.setdefault("v", _settings(resorts.DEFAULT)[1])
        return values[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
