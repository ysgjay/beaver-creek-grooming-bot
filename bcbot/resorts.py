"""The resorts Snow Desk covers. Each one has its own grooming map, snow report, cams,
forecast point, archive folder, subscribers and once-a-day send.

All five are Vail Resorts' Colorado mountains, which share one website platform (the
`snowReportData` block on the snow report page) and post Lumiplan grooming PDFs.

`enabled` resorts are run by the scheduler and shown in the app. Turn one on only after
its sources are checked (see docs/RESORTS.md). The RESORTS env var (comma-separated
slugs) overrides the list without a code change.
"""
import os
from datetime import date

BROWNRICE = "https://player.brownrice.com"
DEFAULT = "beaver-creek"


def _cams(ids):
    return [{"label": label, "image": f"{BROWNRICE}/snapshot/{cid}", "live": f"{BROWNRICE}/embed/{cid}"}
            for cid, label in ids]


RESORTS = {
    "beaver-creek": {
        "name": "Beaver Creek",
        "site": "https://www.beavercreek.com",
        "grooming_pdf": "https://grooming.lumiplan.pro/beaver-creek-grooming-map.pdf",
        # Upper mountain, the elevation OpenSnow uses (10,476 ft).
        "lat": 39.5893, "lon": -106.5214, "elevation_ft": 10476,
        "snotel": ["842:CO:SNTL", "415:CO:SNTL"],  # Vail Mountain, Copper Mountain
        "snotel_label": "Vail Mountain",
        "cams": _cams([("bcsnowstake2", "Snow stake"), ("bcspruce", "Spruce Saddle"), ("bctalons", "Talons"),
                       ("bcmccoy", "McCoy Park"), ("bcredbuffalo", "Red Buffalo"), ("bcvillage", "Village")]),
        "patrol": {"emergency": "(970) 754-6911", "security": "(970) 754-5848"},
        "tz": "America/Denver",
        "opening_day": "2026-11-25",
        "enabled": True,
    },
    "vail": {
        "name": "Vail",
        "site": "https://www.vail.com",
        "grooming_pdf": "https://grooming.lumiplan.pro/vail-mountain-grooming-map.pdf",
        # Mid-Vail / Two Elk ridge, upper mountain.
        "lat": 39.6145, "lon": -106.3720, "elevation_ft": 10350,
        "snotel": ["842:CO:SNTL", "415:CO:SNTL"],  # Vail Mountain sits on the ski area
        "snotel_label": "Vail Mountain",
        "cams": [],
        "patrol": None,
        "enabled": False,
    },
    "breckenridge": {
        "name": "Breckenridge",
        "site": "https://www.breckenridge.com",
        "grooming_pdf": None,
        "lat": 39.4760, "lon": -106.0790, "elevation_ft": 11000,
        "snotel": ["531:CO:SNTL", "415:CO:SNTL"],  # Hoosier Pass, Copper Mountain
        "snotel_label": "Hoosier Pass",
        "cams": [],
        "patrol": None,
        "enabled": False,
    },
    "keystone": {
        "name": "Keystone",
        "site": "https://www.keystoneresort.com",
        "grooming_pdf": None,
        "lat": 39.5950, "lon": -105.9440, "elevation_ft": 11200,
        "snotel": ["505:CO:SNTL", "415:CO:SNTL"],  # Grizzly Peak, Copper Mountain
        "snotel_label": "Grizzly Peak",
        "cams": [],
        "patrol": None,
        "enabled": False,
    },
    "crested-butte": {
        "name": "Crested Butte",
        "site": "https://www.skicb.com",
        "grooming_pdf": None,
        "lat": 38.8990, "lon": -106.9650, "elevation_ft": 10500,
        "snotel": ["380:CO:SNTL"],  # Butte
        "snotel_label": "Butte",
        "cams": [],
        "patrol": None,
        "enabled": False,
    },
}

SNOW_REPORT_PATH = "/the-mountain/mountain-conditions/snow-and-weather-report.aspx"
CAMS_PATH = "/the-mountain/mountain-conditions/mountain-cams.aspx"


def enabled():
    """Slugs the scheduler runs and the app offers, in display order."""
    env = [s.strip() for s in os.environ.get("RESORTS", "").split(",") if s.strip() in RESORTS]
    return env or [k for k, r in RESORTS.items() if r["enabled"]]


def get(slug):
    if slug not in RESORTS:
        raise KeyError(f"unknown resort {slug!r}")
    r = dict(RESORTS[slug], slug=slug)
    r["snow_report"] = r["site"] + SNOW_REPORT_PATH
    r["cams_page"] = r["site"] + CAMS_PATH
    r["elevation_m"] = round(r["elevation_ft"] * 0.3048)
    r.setdefault("tz", "America/Denver")
    env = os.environ.get("OPENING_DAY_" + slug.upper().replace("-", "_")) or (
        os.environ.get("OPENING_DAY") if slug == DEFAULT else None)
    r["opening_day"] = date.fromisoformat(env or r.get("opening_day") or "2026-11-25")
    return r


def valid(slugs):
    """Keep only known, enabled slugs (in order, no repeats). Used for sign-up input."""
    on, out = set(enabled()), []
    for s in slugs or []:
        if s in on and s not in out:
            out.append(s)
    return out


def public_list():
    """What the app needs to show the switcher (written to public/resorts.json)."""
    out = []
    for slug in enabled():
        r = get(slug)
        out.append({"slug": slug, "name": r["name"], "timezone": r["tz"], "cams": r["cams"], "patrol": r["patrol"],
                    "snotel": r["snotel_label"], "site": r["site"]})
    return {"default": DEFAULT, "resorts": out}
