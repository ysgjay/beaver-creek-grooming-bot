"""All tunable settings in one place. Secrets come from environment variables.

Per-resort settings (forecast point, grooming PDF, snow report, SNOTEL, cams) start as
Beaver Creek's and are switched with `use(slug)` before a run (see resorts.py).
"""
import os
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent

TZ = ZoneInfo("America/Denver")

# Forecast point, grooming PDF and snow report: set per resort by use() at the bottom.
RESORT = RESORT_NAME = GROOMING_PDF_URL = RESORT_SNOW_REPORT_URL = None
LAT = LON = ELEVATION_M = ELEVATION_FT = None
# Elevation bands (base / mid / peak) shown beside the forecast: per resort, in resorts.py.
ELEVATION_BANDS = []

# Deterministic models pulled from Open-Meteo. Key = Open-Meteo model id.
# base weights: (days 1-2, days 3+). The weights are the "prior"; verification
# against SNOTEL then scales them by each model's recent skill at this spot.
MODELS = {
    "ncep_nbm_conus": {"label": "NBM (NOAA blend)", "w": (3.0, 3.0)},
    "gfs_hrrr": {"label": "HRRR 3 km", "w": (3.0, 0.0)},
    "ecmwf_ifs025": {"label": "ECMWF", "w": (2.0, 2.5)},
    "gfs_seamless": {"label": "GFS", "w": (1.0, 1.0)},
    "icon_seamless": {"label": "ICON (German)", "w": (1.5, 1.5)},
    "gem_seamless": {"label": "GEM (Canadian)", "w": (1.0, 1.0)},
    "ukmo_seamless": {"label": "UKMO", "w": (1.0, 1.0)},
}
# NWS forecaster-edited gridded snowfall (2.5 km, days 1-7) joins the blend as its own "model".
NWS_MODEL = "nws"
NWS_WEIGHT = (2.5, 2.0)

ENSEMBLE_MODELS = ["ecmwf_ifs025", "gfs025"]

FORECAST_DAYS = 10

# SNOTEL ground truth: per resort (resorts.py), nearest station first.
SNOTEL_STATIONS = []

# Cams are Brown Rice streams: /snapshot/<id> is a still, /embed/<id> the live player.
# CAM_IDS ("id:Label,...") overrides Beaver Creek's list; first = snow stake.
BROWNRICE = "https://player.brownrice.com"
_CAMS_ENV = [c.strip() for c in os.environ.get("CAM_IDS", "").split(",") if c.strip()]


def _cams_from_ids(ids):
    return [{"label": label, "image": f"{BROWNRICE}/snapshot/{cid}", "live": f"{BROWNRICE}/embed/{cid}"}
            for cid, _, label in (c.partition(":") for c in ids)]


CAMS, STAKE_SNAPSHOT_URL = [], ""

# Notifications
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://snow.0xm.studio/")
# Notifications go out only when this is "1" (so a new deployment can't double-post).
SEND_ENABLED = os.environ.get("SEND_ENABLED") == "1"
# A run with no new grooming map still refreshes the forecast when it's older than this.
REFRESH_HOURS = float(os.environ.get("REFRESH_HOURS", "6"))
# Daily send timing (local, America/Denver):
#   before OPENING_DAY: every morning at SEND_TIME, grooming map or not;
#   in season: as soon as a new map AND today's resort snow report are confirmed, from
#   SEND_EARLIEST; at SEND_LATEST whatever is available goes out.
# Beaver Creek's; other resorts have their own in resorts.py (env OPENING_DAY_<SLUG> overrides).
OPENING_DAY = date.fromisoformat(os.environ.get("OPENING_DAY", "2026-11-25"))
SEND_TIME = os.environ.get("SEND_TIME", "07:00")
SEND_EARLIEST = os.environ.get("SEND_EARLIEST", "05:00")
SEND_LATEST = os.environ.get("SEND_LATEST", "09:00")
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


def use(slug):
    """Point every per-resort setting at `slug`. Returns the resort dict."""
    from . import resorts
    global RESORT, RESORT_NAME, LAT, LON, ELEVATION_M, ELEVATION_FT, GROOMING_PDF_URL
    global RESORT_SNOW_REPORT_URL, SNOTEL_STATIONS, CAMS, STAKE_SNAPSHOT_URL, TZ, OPENING_DAY, ELEVATION_BANDS
    r = resorts.get(slug)
    TZ = ZoneInfo(r["tz"])  # send times, "today" and every date are in the resort's own zone
    OPENING_DAY = r["opening_day"]
    RESORT, RESORT_NAME = slug, r["name"]
    LAT, LON, ELEVATION_FT, ELEVATION_M = r["lat"], r["lon"], r["elevation_ft"], r["elevation_m"]
    GROOMING_PDF_URL = r["grooming_pdf"]
    RESORT_SNOW_REPORT_URL = r["snow_report"]
    SNOTEL_STATIONS = r["snotel"]
    ELEVATION_BANDS = r["bands"]
    if slug == resorts.DEFAULT and _CAMS_ENV:
        CAMS = _cams_from_ids(_CAMS_ENV)
    else:
        CAMS = r["cams"]
    STAKE_SNAPSHOT_URL = (os.environ.get("STAKE_SNAPSHOT_URL") if slug == resorts.DEFAULT else None) or (
        CAMS[0]["image"] if CAMS and "stake" in CAMS[0]["label"].lower() else "")
    return r


use("beaver-creek")
