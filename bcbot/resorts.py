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


def _bands(base, mid, peak):
    return [{"key": k, "label": k.title(), "lat": la, "lon": lo, "elevation_ft": ft}
            for k, (la, lo, ft, _where) in zip(("base", "mid", "peak"), (base, mid, peak))]


RESORTS = {
    "beaver-creek": {
        "name": "Beaver Creek",
        "site": "https://www.beavercreek.com",
        "grooming_pdf": "https://grooming.lumiplan.pro/beaver-creek-grooming-map.pdf",
        # Upper mountain, the elevation OpenSnow uses (10,476 ft).
        "lat": 39.5893, "lon": -106.5214, "elevation_ft": 10476,
        # Base / mid / peak points on the mountain (never the town). Elevation is what temps are corrected to.
        "bands": _bands((39.6042, -106.5165, 8100, "Beaver Creek Village"), (39.5893, -106.5214, 10200, "Spruce Saddle level"),
                        (39.5730, -106.5300, 11440, "summit")),
        "snotel": ["842:CO:SNTL", "415:CO:SNTL"],  # Vail Mountain, Copper Mountain
        "snotel_label": "Vail Mountain",
        "cams": _cams([("bcsnowstake2", "Snow stake"), ("bcspruce", "Spruce Saddle"), ("bctalons", "Talons"),
                       ("bcmccoy", "McCoy Park"), ("bcredbuffalo", "Red Buffalo"), ("bcvillage", "Village")]),
        # From Beaver Creek's Safety on the Mountain page, checked Nov 15, 2026.
        "patrol": {"emergency": "(970) 754-6911", "non_emergency": "(970) 754-6610",
                   "security": "(970) 754-5848", "checked": "11/15/2026"},
        "tz": "America/Denver",
        "opening_day": "2026-11-25",
        "enabled": True,
    },
    "vail": {
        "name": "Vail",
        "site": "https://www.vail.com",
        # Area headings ("MID-VAIL") instead of Beaver Creek's sections; see sources/grooming.py.
        "grooming_pdf": "https://grooming.lumiplan.pro/vail-mountain-grooming-map.pdf",
        # Upper mountain near Mid-Vail, by the Vail Mountain SNOTEL (39.618, -106.380, 10,290 ft).
        "lat": 39.6145, "lon": -106.3720, "elevation_ft": 10350,
        "bands": _bands((39.6400, -106.3740, 8120, "Vail Village"), (39.6170, -106.3700, 10250, "Mid-Vail"),
                        (39.6060, -106.3550, 11570, "summit")),
        "snotel": ["842:CO:SNTL", "415:CO:SNTL"],  # Vail Mountain, Copper Mountain
        "snotel_label": "Vail Mountain",
        "cams": _cams([("vailsnowsummit", "Snow stake (summit)"), ("vaileaglesnest", "Eagle's Nest"),
                       ("vailch21", "Back Bowls"), ("vailch11", "Sun Up Bowl"), ("vailch2", "Gore Range")]),
        "patrol": None,
        "tz": "America/Denver",
        "opening_day": "2026-11-13",
        "enabled": True,
    },
    "breckenridge": {
        "name": "Breckenridge",
        "site": "https://www.breckenridge.com",
        "grooming_pdf": None,  # no Lumiplan map found (Nov 2026): snow report, cams and forecast only
        # Peak 8 mid-mountain, where the official snow stake is (11,237 ft).
        "lat": 39.4790, "lon": -106.0820, "elevation_ft": 11237,
        "bands": _bands((39.4800, -106.0670, 9600, "Peak 9 base"), (39.4790, -106.0820, 11237, "Peak 8 snow stake"),
                        (39.4700, -106.1000, 12998, "Imperial summit")),
        "snotel": ["415:CO:SNTL", "531:CO:SNTL"],  # Copper Mountain, Hoosier Pass
        "snotel_label": "Copper Mountain",
        "cams": [{"label": "Snow stake", "image": "https://cache.snow.com/Mtncams/BreckSnowStake.jpg", "live": None}]
                + _cams([("breckenridge10", "Peak 9"), ("breckenridge9", "Peak 8 from Peak 9"), ("breckenridge7", "Peak 7")]),
        "patrol": None,
        "tz": "America/Denver",
        "opening_day": "2026-11-06",
        "enabled": True,
    },
    "keystone": {
        "name": "Keystone",
        "site": "https://www.keystoneresort.com",
        "grooming_pdf": None,
        # Dercum Mountain, upper mountain.
        "lat": 39.5960, "lon": -105.9450, "elevation_ft": 11000,
        "bands": _bands((39.6050, -105.9440, 9280, "River Run"), (39.5920, -105.9440, 10600, "Dercum mid"),
                        (39.5870, -105.9430, 11640, "Dercum summit")),
        "snotel": ["505:CO:SNTL", "415:CO:SNTL"],  # Grizzly Peak, Copper Mountain
        "snotel_label": "Grizzly Peak",
        "cams": [{"label": "Snow stake", "image": "https://cache.snow.com/Mtncams/KeySnowStake.jpg", "live": None}]
                + _cams([("keystonedercum", "Dercum Mountain"), ("keystonenorthpeak", "North Peak"),
                         ("keystonebergman", "Bergman"), ("keystoneriverrun", "River Run"), ("keystonelakeside", "Lakeside Village")]),
        "patrol": None,
        "tz": "America/Denver",
        "opening_day": "2026-11-01",  # opened in October "as conditions allow"; any earlier date works
        "enabled": True,
    },
    "crested-butte": {
        "name": "Crested Butte",
        "site": "https://www.skicb.com",
        "snow_report_path": "/the-mountain/mountain-conditions/weather-report.aspx",  # differs from the others
        "grooming_pdf": None,
        # Upper mountain above the base, by the Butte SNOTEL (38.894, -106.953, 10,190 ft).
        "lat": 38.8930, "lon": -106.9710, "elevation_ft": 10500,
        "bands": _bands((38.8990, -106.9650, 9375, "base area"), (38.8930, -106.9710, 10500, "mid-mountain"),
                        (38.8840, -106.9830, 12162, "summit")),
        "snotel": ["380:CO:SNTL"],  # Butte
        "snotel_label": "Butte",
        "cams": _cams([("Crestedbuttebase", "Base"), ("Crestedbuttebar", "Umbrella Bar, Ten Peaks"),
                       ("Crestedbuttewarm", "Paradise Warming House")]),  # no snow stake cam
        "patrol": None,
        "tz": "America/Denver",
        "opening_day": "2026-11-25",
        "enabled": True,
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
    r["snow_report"] = r["site"] + r.get("snow_report_path", SNOW_REPORT_PATH)
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
                    "snotel": r["snotel_label"], "site": r["site"], "lat": r["lat"], "lon": r["lon"]})
    return {"default": DEFAULT, "resorts": out}
