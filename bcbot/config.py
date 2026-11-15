"""All tunable settings in one place. Secrets come from environment variables."""
import os
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
# The daily report goes out at this local time (America/Denver), every day in season.
SEND_TIME = os.environ.get("SEND_TIME", "07:00")
# In the half hour before SEND_TIME, refresh anything older than an hour so 7:00 is fresh.
PRE_SEND_MINUTES = 30
# If the resort hasn't posted a new map by SEND_TIME, keep checking; at this many minutes
# past SEND_TIME send anyway (noting there's no new map).
SEND_FALLBACK_MINUTES = int(os.environ.get("SEND_FALLBACK_MINUTES", "120"))
# "In season" = the grooming map changed within this many days. Off-season, nothing is sent.
IN_SEASON_DAYS = 3
TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "@bcskireport")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
EMAIL_TO = [e.strip() for e in os.environ.get("EMAIL_TO", "").split(",") if e.strip()]
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")  # public sheet of form sign-ups
SIGNUP_FORM_URL = os.environ.get("SIGNUP_FORM_URL", "")  # the Google Form that feeds that sheet

POWDER_ALERT_INCHES = float(os.environ.get("POWDER_ALERT_INCHES", "6"))

USER_AGENT = "beaver-creek-grooming-bot (github.com/ysgjay/beaver-creek-grooming-bot)"
