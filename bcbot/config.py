"""All tunable settings in one place. Secrets come from environment variables."""
import os
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent

TZ = ZoneInfo("America/Denver")

# Forecast point: Beaver Creek upper mountain, same elevation OpenSnow uses (10,476 ft).
# Open-Meteo applies a lapse-rate correction from the model's terrain height to this elevation.
LAT = 39.5893
LON = -106.5214
ELEVATION_M = 3193  # 10,476 ft
ELEVATION_FT = 10476

GROOMING_PDF_URL = "https://grooming.lumiplan.pro/beaver-creek-grooming-map.pdf"
RESORT_SNOW_REPORT_URL = (
    "https://www.beavercreek.com/the-mountain/mountain-conditions/snow-and-weather-report.aspx"
)

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

# SNOTEL ground truth. Vail Mountain (10,300 ft) is ~6 miles from Beaver Creek's upper mountain.
SNOTEL_STATIONS = ["842:CO:SNTL", "415:CO:SNTL"]  # Vail Mountain, Copper Mountain (fallback)

# Beaver Creek's cams are Brown Rice streams. Each has a live player page and a
# still JPEG at /snapshot/<id> (found by `python -m bcbot discover`). First = snow stake.
BROWNRICE = "https://player.brownrice.com"
CAM_IDS = [c.strip() for c in os.environ.get("CAM_IDS", "").split(",") if c.strip()] or [
    "bcsnowstake2:Snow stake",
    "bcspruce:Spruce Saddle",
    "bctalons:Talons",
    "bcmccoy:McCoy Park",
    "bcredbuffalo:Red Buffalo",
    "bcvillage:Village",
]
CAMS = [{"label": label, "image": f"{BROWNRICE}/snapshot/{cid}", "live": f"{BROWNRICE}/embed/{cid}"}
        for cid, _, label in (c.partition(":") for c in CAM_IDS)]
STAKE_SNAPSHOT_URL = os.environ.get("STAKE_SNAPSHOT_URL", CAMS[0]["image"] if CAMS else "")

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

POWDER_ALERT_INCHES = float(os.environ.get("POWDER_ALERT_INCHES", "6"))

USER_AGENT = "beaver-creek-grooming-bot (github.com/ysgjay/beaver-creek-grooming-bot)"
