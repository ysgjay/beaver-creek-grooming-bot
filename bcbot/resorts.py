"""The resorts Snow Desk covers. Each one has its own grooming map, snow report, cams,
forecast point, archive folder, subscribers and once-a-day send.

Colorado and Utah on the Epic and Ikon passes. Vail Resorts' own mountains share one website
platform (the `snowReportData` block on the snow report page) and some post Lumiplan grooming
PDFs; the other resorts' own reports aren't read yet (`snow_report_path: None`).

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

    # ---- Added 11/15/2026: the rest of Colorado and Utah on the Epic and Ikon passes. ----
    # Park City runs on the Vail platform (snow report + Lumiplan map). The others run their own
    # sites, which Snow Desk doesn't read yet (snow_report_path None): their report is the
    # forecast, SNOTEL and, where known, cams, sent at 7:00. Coordinates are on the mountain;
    # SNOTEL stations are the nearest active ones (NRCS station list, checked 11/15/2026).
    "park-city": {
        "name": "Park City", "region": "Utah", "pass": "Epic",
        "site": "https://www.parkcitymountain.com",
        "snow_report_path": "/the-mountain/mountain-conditions/weather-report.aspx",
        "grooming_pdf": "https://grooming.lumiplan.pro/park-city-grooming-map.pdf",
        "lat": 40.6280, "lon": -111.5400, "elevation_ft": 9000,
        "bands": _bands((40.6510, -111.5080, 6900, "Park City base"), (40.6280, -111.5400, 9000, "mid-mountain"),
                        (40.6200, -111.5530, 10000, "Jupiter Peak")),
        "snotel": ["814:UT:SNTL", "366:UT:SNTL"],  # Thaynes Canyon, Brighton
        "snotel_label": "Thaynes Canyon",
        "cams": _cams([("parkcitylookoutcabin", "Lookout Cabin"), ("parkcityhighmeadow", "High Meadow"),
                       ("parkcitytopcrescent", "Top of Crescent"), ("parkcitycnskibeach", "Canyons Village"),
                       ("parkcitymtnvillage", "Mountain Village")]),
        "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-20", "enabled": True,
    },
    "telluride": {
        "name": "Telluride", "region": "Colorado", "pass": "Epic",
        "site": "https://tellurideskiresort.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 37.9160, "lon": -107.8360, "elevation_ft": 10800,
        "bands": _bands((37.9360, -107.8460, 8725, "base"), (37.9160, -107.8360, 10800, "mid-mountain"),
                        (37.9070, -107.8400, 12570, "summit")),
        "snotel": ['1344:CO:SNTL', '713:CO:SNTL'],
        "snotel_label": "Alta Lakes",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-26", "enabled": True,
    },
    "snowmass": {
        "name": "Snowmass", "region": "Colorado", "pass": "Ikon",
        "site": "https://www.aspensnowmass.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 39.1900, "lon": -106.9620, "elevation_ft": 10500,
        "bands": _bands((39.2090, -106.9500, 8104, "base"), (39.1900, -106.9620, 10500, "mid-mountain"),
                        (39.1690, -106.9700, 12510, "summit")),
        "snotel": ['669:CO:SNTL', '737:CO:SNTL'],
        "snotel_label": "North Lost Trail",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-26", "enabled": True,
    },
    "aspen-mountain": {
        "name": "Aspen Mountain", "region": "Colorado", "pass": "Ikon",
        "site": "https://www.aspensnowmass.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 39.1680, "lon": -106.8220, "elevation_ft": 10300,
        "bands": _bands((39.1860, -106.8180, 7945, "base"), (39.1680, -106.8220, 10300, "mid-mountain"),
                        (39.1550, -106.8170, 11212, "summit")),
        "snotel": ['1326:CO:SNTL', '1101:CO:SNTL'],
        "snotel_label": "Castle Peak",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-26", "enabled": True,
    },
    "aspen-highlands": {
        "name": "Aspen Highlands", "region": "Colorado", "pass": "Ikon",
        "site": "https://www.aspensnowmass.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 39.1600, "lon": -106.8660, "elevation_ft": 10300,
        "bands": _bands((39.1820, -106.8560, 8040, "base"), (39.1600, -106.8660, 10300, "mid-mountain"),
                        (39.1350, -106.8600, 11675, "summit")),
        "snotel": ['1326:CO:SNTL', '1141:CO:SNTL'],
        "snotel_label": "Castle Peak",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-12-12", "enabled": True,
    },
    "buttermilk": {
        "name": "Buttermilk", "region": "Colorado", "pass": "Ikon",
        "site": "https://www.aspensnowmass.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 39.1940, "lon": -106.8730, "elevation_ft": 9000,
        "bands": _bands((39.2060, -106.8610, 7870, "base"), (39.1940, -106.8730, 9000, "mid-mountain"),
                        (39.1800, -106.8850, 9900, "summit")),
        "snotel": ['1326:CO:SNTL', '1101:CO:SNTL'],
        "snotel_label": "Castle Peak",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-12-12", "enabled": True,
    },
    "steamboat": {
        "name": "Steamboat", "region": "Colorado", "pass": "Ikon",
        "site": "https://www.steamboat.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 40.4590, "lon": -106.7800, "elevation_ft": 9500,
        "bands": _bands((40.4570, -106.8050, 6900, "base"), (40.4590, -106.7800, 9100, "mid-mountain"),
                        (40.4520, -106.7430, 10568, "summit")),
        "snotel": ['457:CO:SNTL', '825:CO:SNTL'],
        "snotel_label": "Dry Lake",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-21", "enabled": True,
    },
    "winter-park": {
        "name": "Winter Park", "region": "Colorado", "pass": "Ikon",
        "site": "https://www.winterparkresort.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 39.8690, "lon": -105.7730, "elevation_ft": 10700,
        "bands": _bands((39.8860, -105.7630, 9000, "base"), (39.8690, -105.7730, 10700, "mid-mountain"),
                        (39.8570, -105.7860, 12060, "summit")),
        "snotel": ['335:CO:SNTL', '1186:CO:SNTL'],
        "snotel_label": "Berthoud Summit",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-13", "enabled": True,
    },
    "copper": {
        "name": "Copper Mountain", "region": "Colorado", "pass": "Ikon",
        "site": "https://www.coppercolorado.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 39.4800, "lon": -106.1600, "elevation_ft": 11000,
        "bands": _bands((39.5020, -106.1520, 9712, "base"), (39.4800, -106.1600, 11000, "mid-mountain"),
                        (39.4670, -106.1700, 12313, "summit")),
        "snotel": ['415:CO:SNTL', '485:CO:SNTL'],
        "snotel_label": "Copper Mountain",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-06", "enabled": True,
    },
    "arapahoe-basin": {
        "name": "Arapahoe Basin", "region": "Colorado", "pass": "Ikon",
        "site": "https://www.arapahoebasin.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 39.6350, "lon": -105.8730, "elevation_ft": 11500,
        "bands": _bands((39.6420, -105.8710, 10520, "base"), (39.6350, -105.8730, 11500, "mid-mountain"),
                        (39.6270, -105.8780, 12500, "summit")),
        "snotel": ['505:CO:SNTL', '602:CO:SNTL'],
        "snotel_label": "Grizzly Peak",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-10-28", "enabled": True,
    },
    "eldora": {
        "name": "Eldora", "region": "Colorado", "pass": "Ikon",
        "site": "https://www.eldora.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 39.9400, "lon": -105.5970, "elevation_ft": 10000,
        "bands": _bands((39.9380, -105.5830, 9200, "base"), (39.9400, -105.5970, 10000, "mid-mountain"),
                        (39.9420, -105.6070, 10800, "summit")),
        "snotel": ['564:CO:SNTL', '838:CO:SNTL'],
        "snotel_label": "Lake Eldora",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-13", "enabled": True,
    },
    "deer-valley": {
        "name": "Deer Valley", "region": "Utah", "pass": "Ikon",
        "site": "https://www.deervalley.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 40.6220, "lon": -111.4910, "elevation_ft": 8800,
        "bands": _bands((40.6370, -111.4790, 7200, "base"), (40.6220, -111.4910, 8800, "mid-mountain"),
                        (40.6110, -111.5100, 9570, "summit")),
        "snotel": ['814:UT:SNTL', '366:UT:SNTL'],
        "snotel_label": "Thaynes Canyon",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-12-05", "enabled": True,
    },
    "solitude": {
        "name": "Solitude", "region": "Utah", "pass": "Ikon",
        "site": "https://www.solitudemountain.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 40.6100, "lon": -111.6000, "elevation_ft": 9400,
        "bands": _bands((40.6200, -111.5920, 7988, "base"), (40.6100, -111.6000, 9400, "mid-mountain"),
                        (40.5960, -111.6090, 10488, "summit")),
        "snotel": ['366:UT:SNTL', '1308:UT:SNTL'],
        "snotel_label": "Brighton",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-20", "enabled": True,
    },
    "brighton": {
        "name": "Brighton", "region": "Utah", "pass": "Ikon",
        "site": "https://www.brightonresort.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 40.5920, "lon": -111.5800, "elevation_ft": 9600,
        "bands": _bands((40.5980, -111.5830, 8755, "base"), (40.5920, -111.5800, 9600, "mid-mountain"),
                        (40.5800, -111.5600, 10500, "summit")),
        "snotel": ['366:UT:SNTL', '1308:UT:SNTL'],
        "snotel_label": "Brighton",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-27", "enabled": True,
    },
    "alta": {
        "name": "Alta", "region": "Utah", "pass": "Ikon",
        "site": "https://www.alta.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 40.5810, "lon": -111.6280, "elevation_ft": 9600,
        "bands": _bands((40.5880, -111.6380, 8530, "base"), (40.5810, -111.6280, 9600, "mid-mountain"),
                        (40.5700, -111.6230, 10550, "summit")),
        "snotel": ['1308:UT:SNTL', '766:UT:SNTL'],
        "snotel_label": "Atwater",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-20", "enabled": True,
    },
    "snowbird": {
        "name": "Snowbird", "region": "Utah", "pass": "Ikon",
        "site": "https://www.snowbird.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 40.5700, "lon": -111.6600, "elevation_ft": 9600,
        "bands": _bands((40.5810, -111.6560, 7760, "base"), (40.5700, -111.6600, 9600, "mid-mountain"),
                        (40.5600, -111.6560, 11000, "summit")),
        "snotel": ['766:UT:SNTL', '1308:UT:SNTL'],
        "snotel_label": "Snowbird",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-27", "enabled": True,
    },
    "snowbasin": {
        "name": "Snowbasin", "region": "Utah", "pass": "Ikon",
        "site": "https://www.snowbasin.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 41.2050, "lon": -111.8700, "elevation_ft": 8500,
        "bands": _bands((41.2160, -111.8570, 6450, "base"), (41.2050, -111.8700, 8000, "mid-mountain"),
                        (41.2000, -111.8800, 9350, "summit")),
        "snotel": ['332:UT:SNTL', '1300:UT:SNTL'],
        "snotel_label": "Ben Lomond Peak",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-27", "enabled": True,
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
    r["snow_report"] = r["site"] + (r.get("snow_report_path") or SNOW_REPORT_PATH)
    r["cams_page"] = r["site"] + CAMS_PATH
    r["elevation_m"] = round(r["elevation_ft"] * 0.3048)
    r.setdefault("tz", "America/Denver")
    r.setdefault("region", "Colorado")
    r.setdefault("pass", "Epic")
    if "snow_report_path" in r and r["snow_report_path"] is None:
        r["snow_report"] = None  # this resort's own snow report isn't read (yet)
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
                    "snotel": r["snotel_label"], "site": r["site"], "lat": r["lat"], "lon": r["lon"],
                    "region": r["region"], "pass": r["pass"], "snow_report": bool(r["snow_report"]),
                    "grooming": bool(r["grooming_pdf"])})
    return {"default": DEFAULT, "resorts": out}


def is_static(slug):
    """Nothing to watch for between refreshes: no grooming map and no snow report that's read.
    The scheduler only needs to run these every half hour (refresh + the 7:00 send)."""
    r = get(slug)
    return not r["grooming_pdf"] and not r["snow_report"]
