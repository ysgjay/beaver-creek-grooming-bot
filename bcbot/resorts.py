"""The resorts 0xSnow covers. Each one has its own grooming map, snow report, cams,
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


def _jpg_cams(base, ids):
    """Cams that are plain JPEGs on the resort's own server (loaded from there, never copied)."""
    return [{"label": label, "image": f"{base}{name}.jpg", "live": None} for name, label in ids]


def _url_cams(items):
    """Cams given as full image URLs on the resort's own cam host (loaded from there, never copied)."""
    return [{"label": label, "image": url, "live": None} for url, label in items]


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
        "opening_day": "2026-10-30",  # opened in October "as conditions allow"; any earlier date works
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
    # sites, which 0xSnow doesn't read yet (snow_report_path None): their report is the
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
        "site": "https://tellurideskiresort.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://tellurideskiresort.com/snow-report/", "start": "Snow depth"}, "grooming_pdf": None,
        "lat": 37.9160, "lon": -107.8360, "elevation_ft": 10800,
        "bands": _bands((37.9360, -107.8460, 8725, "base"), (37.9160, -107.8360, 10800, "mid-mountain"),
                        (37.9070, -107.8400, 12570, "summit")),
        "snotel": ['1344:CO:SNTL', '713:CO:SNTL'],
        "snotel_label": "Alta Lakes",
        "cams": _url_cams([("https://g1.ipcamlive.com/player/snapshot.php?alias=powcam", "Prospect Basin (Powcam)"),
                          ("https://g1.ipcamlive.com/player/snapshot.php?alias=plazacam", "Mountain Village"),
                          ("https://g1.ipcamlive.com/player/snapshot.php?alias=bonvivant", "Black Iron Bowl"),
                          ("https://g1.ipcamlive.com/player/snapshot.php?alias=jointpoint", "See Forever")]), "patrol": None, "tz": "America/Denver", "opening_day": "2026-12-05", "enabled": True,
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
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-27", "enabled": True,
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
        "site": "https://www.coppercolorado.com", "snow_report_path": None, "dor_api": "https://api.coppercolorado.com", "grooming_pdf": None,
        "lat": 39.4800, "lon": -106.1600, "elevation_ft": 11000,
        "bands": _bands((39.5020, -106.1520, 9712, "base"), (39.4800, -106.1600, 11000, "mid-mountain"),
                        (39.4670, -106.1700, 12313, "summit")),
        "snotel": ['415:CO:SNTL', '485:CO:SNTL'],
        "snotel_label": "Copper Mountain",
        "cams": _url_cams([("https://img.hdrelay.com/frames/fb469125-f1f3-459f-aeb4-98cb674e395f/default/last.jpg", "Snow stake"),
                          ("https://img.hdrelay.com/frames/671bcfb507697ecebbaffc13/default/last.jpg", "Aerie")]), "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-08", "enabled": True,
    },
    "arapahoe-basin": {
        "name": "Arapahoe Basin", "region": "Colorado", "pass": "Ikon",
        "site": "https://www.arapahoebasin.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://www.arapahoebasin.com/snow-report/", "order": "before"}, "grooming_pdf": None,
        "lat": 39.6350, "lon": -105.8730, "elevation_ft": 11500,
        "bands": _bands((39.6420, -105.8710, 10520, "base"), (39.6350, -105.8730, 11500, "mid-mountain"),
                        (39.6270, -105.8780, 12500, "summit")),
        "snotel": ['505:CO:SNTL', '602:CO:SNTL'],
        "snotel_label": "Grizzly Peak",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-10-28", "enabled": True,
    },
    "eldora": {
        "name": "Eldora", "region": "Colorado", "pass": "Ikon",
        "site": "https://www.eldora.com", "snow_report_path": None, "dor_api": "https://api.eldora.com", "grooming_pdf": None,
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
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-19", "enabled": True,
    },
    "brighton": {
        "name": "Brighton", "region": "Utah", "pass": "Ikon",
        "site": "https://www.brightonresort.com", "snow_report_path": None, "reportpal": "br", "grooming_pdf": None,
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
        "site": "https://www.snowbird.com", "snow_report_path": None, "dor_api": "https://api.snowbird.com", "grooming_pdf": None,
        "lat": 40.5700, "lon": -111.6600, "elevation_ft": 9600,
        "bands": _bands((40.5810, -111.6560, 7760, "base"), (40.5700, -111.6600, 9600, "mid-mountain"),
                        (40.5600, -111.6560, 11000, "summit")),
        "snotel": ['766:UT:SNTL', '1308:UT:SNTL'],
        "snotel_label": "Snowbird",
        "cams": _url_cams([("https://manage.hdrelay.com/snapshot/8611e276-7ee5-42c0-b8cd-d9e1890e1cd4", "Snow stake"),
                          ("https://manage.hdrelay.com/snapshot/544432bd-3910-4888-aa9f-14b6f51a7eb5", "Peruvian Gulch"),
                          ("https://manage.hdrelay.com/snapshot/5780754f-8da1-4223-ab8a-6755d84cbc10", "Mineral Basin"),
                          ("https://manage.hdrelay.com/snapshot/db2a69c5-66e9-4c48-a713-919eaf191fc1", "Little Cloud"),
                          ("https://manage.hdrelay.com/snapshot/61b2490be101c00b9c48374f", "Tram Bullpen"),
                          ("https://backend.roundshot.com/cams/44cfff4ff2a218a1178dbb105d95846a/medium", "Hidden Peak"),
                          ("https://backend.roundshot.com/cams/48fc223c0ed88474ecc2f884bf39de63/medium", "Powder Paradise")]), "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-27", "enabled": True,
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

    # ---------- Wave 1 (11/19/2026): shadow mode only ----------
    # "stage": "shadow" = the Render worker runs these in shadow mode (no sends, nothing shown in the app)
    # until their readers have matched the resorts' own pages for 3 days. Then set enabled True and drop stage.
    # Snow report path and Brown Rice cam ids were checked on each site 11/19/2026. None posts a Lumiplan
    # grooming map. Base/mid/peak points were snapped 11/19 to the nearest terrain at their stated elevation (Copernicus
    # 90 m DEM via the Open-Meteo elevation API); check them against the trail map when tuning.
    "whistler-blackcomb": {
        "name": "Whistler Blackcomb", "region": "British Columbia", "pass": "Epic",
        "site": "https://www.whistlerblackcomb.com", "grooming_pdf": None,
        "lat": 50.0682, "lon": -122.9575, "elevation_ft": 6069,
        "bands": _bands((50.1151, -122.9561, 2214, "Whistler Village"), (50.0682, -122.9575, 6069, "Roundhouse"),
                        (50.0583, -122.9561, 7160, "Whistler Peak")),
        "snotel": [], "snotel_label": None,  # no SNOTEL in Canada
        "cams": _cams([("whistlerroundhouse", "Roundhouse"), ("whistlerpeak", "Whistler Peak"),
                       ("whistlerblackcomb", "Blackcomb"), ("whistlersnowstack", "Snow stake"),
                       ("whistler7thheaven", "7th Heaven"), ("whistlervillage", "Village"),
                       ("whistlercreekside", "Creekside")]),
        "patrol": None, "tz": "America/Vancouver", "opening_day": "2026-11-20", "enabled": True,
    },
    "heavenly": {
        "name": "Heavenly", "region": "California", "pass": "Epic",
        "site": "https://www.skiheavenly.com", "grooming_pdf": None,
        "lat": 38.9254, "lon": -119.9215, "elevation_ft": 8500,
        "bands": _bands((38.9344, -119.9446, 6565, "California Lodge"), (38.9254, -119.9215, 8500, "mid-mountain"),
                        (38.9173, -119.9006, 10067, "Monument Peak")),
        "snotel": ["518:CA:SNTL", "508:CA:SNTL"], "snotel_label": "Heavenly Valley",
        "cams": _cams([("heavenlydipper", "Dipper"), ("heavenlymidstation", "Mid-station"), ("heavenlytram", "Tram"),
                       ("heavenlyeastpeak", "East Peak")]),
        "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-20", "enabled": True,
    },
    "northstar": {
        "name": "Northstar", "region": "California", "pass": "Epic",
        "site": "https://www.northstarcalifornia.com", "grooming_pdf": None,
        "lat": 39.2586, "lon": -120.1361, "elevation_ft": 7600,
        "bands": _bands((39.2757, -120.1199, 6330, "Village"), (39.2586, -120.1361, 7600, "mid-mountain"),
                        (39.2415, -120.1385, 8610, "Mt. Pluto")),
        "snotel": ["834:CA:SNTL", "809:CA:SNTL"], "snotel_label": "Truckee #2",
        "cams": _cams([("northstarsnowstake", "Snow stake"), ("northstarspluto", "Mt. Pluto"),
                       ("northstarmidmountain", "Mid-mountain"), ("northstarvillage", "Village")]),
        "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-20", "enabled": True,
    },
    "kirkwood": {
        "name": "Kirkwood", "region": "California", "pass": "Epic",
        "site": "https://www.kirkwood.com", "grooming_pdf": None,
        "lat": 38.6659, "lon": -120.0525, "elevation_ft": 8800,
        "bands": _bands((38.6848, -120.0664, 7800, "base"), (38.6659, -120.0525, 8800, "mid-mountain"),
                        (38.6623, -120.0606, 9876, "summit")),
        "snotel": ["1067:CA:SNTL", "1049:CA:SNTL"], "snotel_label": "Carson Pass",
        "cams": _cams([("kirkwoodcornice", "Cornice"), ("kirkwoodredcliffs", "Red Cliffs")]),
        "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-12-04", "enabled": True,
    },
    "stevens-pass": {
        "name": "Stevens Pass", "region": "Washington", "pass": "Epic",
        "site": "https://www.stevenspass.com", "snow_report_path": "/the-mountain/mountain-conditions/weather-report.aspx",
        "grooming_pdf": None,
        "lat": 47.7362, "lon": -121.0987, "elevation_ft": 4800,
        "bands": _bands((47.7443, -121.0893, 4061, "base"), (47.7362, -121.0987, 4800, "mid-mountain"),
                        (47.7317, -121.1027, 5845, "summit")),
        "snotel": ["791:WA:SNTL", "1338:WA:SNTL"], "snotel_label": "Stevens Pass",
        "cams": _cams([("stevenspasssnowstake", "Snow stake"), ("stevenspasscourtyard", "Courtyard"),
                       ("stevenspassschool", "Ski school"), ("stevenspassjupiter", "Jupiter"),
                       ("stevenspassskyline", "Skyline")]),
        "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-12-04", "enabled": True,
    },
    "stowe": {
        "name": "Stowe", "region": "Vermont", "pass": "Epic",
        "site": "https://www.stowe.com", "grooming_pdf": None,
        "lat": 44.5274, "lon": -72.8003, "elevation_ft": 2700,
        "bands": _bands((44.5310, -72.7801, 1559, "base"), (44.5274, -72.8003, 2700, "mid-mountain"),
                        (44.5229, -72.8104, 3625, "Cliff House")),
        "snotel": [], "snotel_label": None,  # no SNOTEL in the East
        "cams": _cams([("stowesnowstake", "Snow stake"), ("stowemidwaybasestation", "Midway"),
                       ("stowevillage", "Village")]),
        # Opening day not announced yet (11/19); last season's target was the Saturday before Thanksgiving.
        "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-21", "enabled": True,
    },
    "okemo": {
        "name": "Okemo", "region": "Vermont", "pass": "Epic",
        "site": "https://www.okemo.com", "grooming_pdf": None,
        "lat": 43.4033, "lon": -72.7343, "elevation_ft": 2300,
        "bands": _bands((43.3997, -72.7095, 1144, "base"), (43.4033, -72.7343, 2300, "mid-mountain"),
                        (43.4033, -72.7517, 3344, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": _cams([("okemosnowstake", "Snow stake"), ("okemosummit", "Summit"), ("okemosugarhouse", "Sugar House"),
                       ("okemoroundhouse", "Roundhouse")]),
        "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-21", "enabled": True,
    },
    "mount-snow": {
        "name": "Mount Snow", "region": "Vermont", "pass": "Epic",
        "site": "https://www.mountsnow.com", "snow_report_path": "/the-mountain/mountain-conditions/weather-report.aspx",
        "grooming_pdf": None,
        "lat": 42.9667, "lon": -72.9135, "elevation_ft": 2800,
        "bands": _bands((42.9658, -72.8913, 1900, "base"), (42.9667, -72.9135, 2800, "mid-mountain"),
                        (42.9595, -72.9245, 3600, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": _cams([("mountsnowsnowstake", "Snow stake"), ("mountsnowsummit", "Summit"), ("mountsnowcarinthia", "Carinthia"),
                       ("mountsnowbase", "Base")]),
        "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-21", "enabled": True,
    },
    "seven-springs": {
        "name": "Seven Springs", "region": "Pennsylvania", "pass": "Epic",
        "site": "https://www.7springs.com", "grooming_pdf": None,
        "lat": 40.0204, "lon": -79.2977, "elevation_ft": 2600,
        "bands": _bands((40.0159, -79.2871, 2240, "base"), (40.0204, -79.2977, 2600, "mid-mountain"),
                        (40.0240, -79.3106, 2994, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": _cams([("sevensprings", "Main"), ("sevenspringsnorthface", "North Face")]),
        # Opening day not announced yet (11/19).
        "patrol": None, "tz": "America/New_York", "opening_day": "2026-12-04", "enabled": True,
    },
    # Killington (locally owned since POWDR sold it in 2024) and POWDR's Mt. Bachelor: no open feed like Copper's
    # (checked 11/19), so for now these two
    # run on forecast and snow stations only, like Telluride.
    "killington": {
        "name": "Killington", "region": "Vermont", "pass": "Ikon",
        "site": "https://www.killington.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://killington.com/mountain-report", "start": "Snow Report Updated"}, "grooming_pdf": None,
        "lat": 43.6158, "lon": -72.8120, "elevation_ft": 3200,
        "bands": _bands((43.6284, -72.7958, 2200, "Snowshed base"), (43.6158, -72.8120, 3200, "mid-mountain"),
                        (43.6041, -72.8207, 4241, "Killington Peak")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York",
        "opening_day": "2026-11-01",  # already open per Ikon (11/19); Killington sets no date in advance
        "enabled": True,
    },
    "mt-bachelor": {
        "name": "Mt. Bachelor", "region": "Oregon", "pass": "Ikon",
        "site": "https://www.mtbachelor.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 43.9868, "lon": -121.6832, "elevation_ft": 7775,
        "bands": _bands((44.0012, -121.6694, 6300, "West Village"), (43.9868, -121.6832, 7775, "Pine Marten"),
                        (43.9787, -121.6882, 9065, "summit")),
        "snotel": ["815:OR:SNTL", "545:OR:SNTL"], "snotel_label": "Three Creeks Meadow",
        "cams": [], "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-12-04",
        "enabled": False, "stage": "shadow",
    },
    # ---------- Wave 2 (11/19/2026): shadow mode only ----------
    # Top independents and the Alterra group. Alterra's mountain report loads from a keyed feed (mtnpowder.com) that
    # we don't use without permission, and the independents' reports need the page reader that isn't built yet, so
    # these run like Steamboat and Winter Park today: our forecast, the nearest SNOTEL (US) and NOAA snow depths.
    # Points are approximate on-mountain spots; check them against the trail map when tuning. Opening days marked
    # "est." are typical-season estimates (not announced or not checked 11/19); confirm before launch.
    "jackson-hole": {
        "name": "Jackson Hole", "region": "Wyoming", "pass": "Ikon",
        "site": "https://www.jacksonhole.com", "snow_report_path": None,
        "report_feed": {"kind": "json", "url": "https://jacksonhole-prod.zaneray.com/api/snow.json", "stamp": "lastModified",
                        "fields": {"overnight_in": "snow.midMountain.newSnowSinceLiftsClosed",
                                   "last_24h_in": "snow.midMountain.newSnowLast24H",
                                   "last_48h_in": "snow.midMountain.newSnowLast48H",
                                   "last_7d_in": "snow.midMountain.newSnowLast7D",
                                   "base_in": "snow.midMountain.totalSnowDepth",
                                   "season_in": "snow.midMountain.seasonTotalSnow"}}, "grooming_pdf": None,
        "lat": 43.5873, "lon": -110.8511, "elevation_ft": 7835,
        "bands": _bands((43.5864, -110.8262, 6311, "Teton Village"), (43.5873, -110.8511, 7835, "mid-mountain"),
                        (43.5882, -110.8909, 10450, "Rendezvous summit")),
        "snotel": ["689:WY:SNTL", "1082:WY:SNTL"], "snotel_label": "Phillips Bench",
        "cams": _jpg_cams("https://cams.jacksonhole.com/webcam/", [
            ("raymersnowstake", "Snow stake"), ("codybowl", "Cody Bowl"), ("guncam", "Sublette Base"),
            ("teton_lift_summit", "Teton Lift summit"), ("casperchair", "Casper Chair"), ("teton_lift_base", "Teton Lift base"),
            ("solitudestation", "Solitude Station"), ("teewinot", "Teewinot / Sweetwater"), ("trambase", "Tram base"),
            ("SouthHoback", "Mountain view"), ("stilson", "Stilson")]), "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-27",  # announced
        "enabled": False, "stage": "shadow",
    },
    "big-sky": {
        "name": "Big Sky", "region": "Montana", "pass": "Ikon",
        "site": "https://www.bigskyresort.com", "snow_report_path": None, "reportpal": "bs", "grooming_pdf": None,
        "lat": 45.2889, "lon": -111.4292, "elevation_ft": 8800,
        "bands": _bands((45.2871, -111.3997, 7500, "Mountain Village"), (45.2889, -111.4292, 8800, "mid-mountain"),
                        (45.2772, -111.4509, 11166, "Lone Peak")),
        "snotel": ["590:MT:SNTL", "385:MT:SNTL"], "snotel_label": "Lone Mountain",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-25",  # announced
        "enabled": False, "stage": "shadow",
    },
    "banff-sunshine": {
        "name": "Banff Sunshine", "region": "Alberta", "pass": "Ikon",
        "site": "https://www.skibanff.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://www.skibanff.com/conditions"}, "grooming_pdf": None,
        "lat": 51.0899, "lon": -115.7645, "elevation_ft": 7082,
        "bands": _bands((51.1170, -115.7545, 5440, "Gondola base"), (51.0899, -115.7645, 7082, "Sunshine Village"),
                        (51.0647, -115.7688, 7595, "upper mountain")),
        "snotel": [], "snotel_label": None,  # no SNOTEL in Canada
        "cams": [], "patrol": None, "tz": "America/Edmonton", "opening_day": "2026-11-06",  # reported, not confirmed
        "enabled": False, "stage": "shadow",
    },
    "lake-louise": {
        "name": "Lake Louise", "region": "Alberta", "pass": "Ikon",
        "site": "https://www.skilouise.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 51.4530, "lon": -116.1400, "elevation_ft": 6800,
        "bands": _bands((51.4409, -116.1642, 5400, "base"), (51.4530, -116.1400, 6800, "Whitehorn"),
                        (51.4676, -116.1417, 8650, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/Edmonton", "opening_day": "2026-11-01",  # opened
        "enabled": False, "stage": "shadow",
    },
    "sun-valley": {
        "name": "Sun Valley", "region": "Idaho", "pass": "Ikon",
        "site": "https://www.sunvalley.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://www.sunvalley.com/the-mountain/mountain-report", "start": "Snowfall", "order": "before"}, "grooming_pdf": None,
        "lat": 43.6627, "lon": -114.3821, "elevation_ft": 7500,
        "bands": _bands((43.6753, -114.3697, 5750, "River Run"), (43.6627, -114.3821, 7500, "mid-mountain"),
                        (43.6546, -114.4095, 9150, "Bald Mountain summit")),
        "snotel": ["895:ID:SNTL", "537:ID:SNTL"], "snotel_label": "Chocolate Gulch",
        "cams": [], "patrol": None, "tz": "America/Boise", "opening_day": "2026-11-26",  # est.
        "enabled": False, "stage": "shadow",
    },
    # Alterra Mountain Company
    "mammoth": {
        "name": "Mammoth Mountain", "region": "California", "pass": "Ikon",
        "site": "https://www.mammothmountain.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 37.6402, "lon": -119.0262, "elevation_ft": 9600,
        "bands": _bands((37.6483, -119.0250, 8900, "Main Lodge"), (37.6402, -119.0262, 9600, "McCoy Station"),
                        (37.6303, -119.0330, 11053, "summit")),
        "snotel": [], "snotel_label": None,  # nearest SNOTEL (Virginia Lakes Ridge) is 51 km away: too far to count as truth
        "cams": [{"label": label, "image": f"https://media.mammothresorts.com/mmsa/mammoth/cams/{name}_1280x720.jpg",
                  "live": f"https://www.youtube.com/watch?v={yt}"}
                 for name, label, yt in (("Main_Broadway", "Main Lodge", "m4u2kGpkYD4"),
                                         ("Top_Of_Sierra_1", "The Summit", "awxz_oIlJE0"),
                                         ("McCoy_Chair_23_Top", "McCoy Station", "jFK8bVYad0M"),
                                         ("Unbound_Main_Park_1", "Unbound Main Park", "gelXqzE1Xi0"),
                                         ("Woolly_Woolly", "Woolly Cam", "AXyxIFY3JaA"),
                                         ("Village_Village", "The Village", "MwHWDokyUhw"),
                                         ("Outpost_Arriba", "The Outpost", "xaf6OzA-i6M"))], "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-05",  # opened early
        "enabled": False, "stage": "shadow",
    },
    "palisades-tahoe": {
        "name": "Palisades Tahoe", "region": "California", "pass": "Ikon",
        "site": "https://www.palisadestahoe.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 39.1938, "lon": -120.2681, "elevation_ft": 8200,
        "bands": _bands((39.1974, -120.2344, 6200, "Olympic Valley"), (39.1938, -120.2681, 8200, "High Camp"),
                        (39.1974, -120.2856, 9006, "Granite Chief")),
        "snotel": ["784:CA:SNTL", "848:CA:SNTL"], "snotel_label": "Palisades Tahoe",
        "cams": [], "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-25",  # announced
        "enabled": False, "stage": "shadow",
    },
    "big-bear": {
        "name": "Big Bear Mountain", "region": "California", "pass": "Ikon",
        "site": "https://www.bigbearmountainresort.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 34.2268, "lon": -116.8883, "elevation_ft": 7600,
        "bands": _bands((34.2349, -116.8883, 7000, "Snow Summit base"), (34.2268, -116.8883, 7600, "mid-mountain"),
                        (34.2205, -116.8927, 8200, "Snow Summit summit")),
        "snotel": [], "snotel_label": None,  # no SNOTEL in Southern California (nearest is 250 km away)
        "cams": [], "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-20",  # est.
        "enabled": False, "stage": "shadow",
    },
    "crystal-mountain": {
        "name": "Crystal Mountain", "region": "Washington", "pass": "Ikon",
        "site": "https://www.crystalmountainresort.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 46.9391, "lon": -121.4870, "elevation_ft": 5800,
        "bands": _bands((46.9346, -121.4752, 4400, "base"), (46.9391, -121.4870, 5800, "mid-mountain"),
                        (46.9391, -121.4989, 7012, "summit")),
        "snotel": ["642:WA:SNTL", "1085:WA:SNTL"], "snotel_label": "Morse Lake",
        "cams": [], "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-27",  # announced
        "enabled": False, "stage": "shadow",
    },
    "tremblant": {
        "name": "Tremblant", "region": "Quebec", "pass": "Ikon",
        "site": "https://www.tremblant.ca", "snow_report_path": None, "grooming_pdf": None,
        "lat": 46.2160, "lon": -74.5670, "elevation_ft": 2000,
        "bands": _bands((46.2090, -74.5850, 755, "Village"), (46.2160, -74.5670, 2000, "mid-mountain"),
                        (46.2200, -74.5525, 2871, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/Toronto", "opening_day": "2026-11-26",  # announced
        "enabled": False, "stage": "shadow",
    },
    "sugarbush": {
        "name": "Sugarbush", "region": "Vermont", "pass": "Ikon",
        "site": "https://www.sugarbush.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.1315, "lon": -72.9112, "elevation_ft": 2500,
        "bands": _bands((44.1360, -72.8940, 1483, "Lincoln Peak base"), (44.1315, -72.9112, 2500, "mid-mountain"),
                        (44.1269, -72.9281, 3975, "Lincoln Peak")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-21",  # est.
        "enabled": False, "stage": "shadow",
    },
    "stratton": {
        "name": "Stratton", "region": "Vermont", "pass": "Ikon",
        "site": "https://www.stratton.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 43.1041, "lon": -72.9200, "elevation_ft": 2900,
        "bands": _bands((43.1130, -72.9070, 1872, "base"), (43.1041, -72.9200, 2900, "mid-mountain"),
                        (43.1010, -72.9240, 3370, "upper mountain")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-18",  # announced
        "enabled": False, "stage": "shadow",
    },
    "snowshoe": {
        "name": "Snowshoe", "region": "West Virginia", "pass": "Ikon",
        "site": "https://www.snowshoemtn.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 38.4100, "lon": -80.0020, "elevation_ft": 4100,
        # Upside down: the village sits at the top and the runs drop below it.
        "bands": _bands((38.4059, -80.0210, 3348, "base"), (38.4100, -80.0020, 4100, "mid-mountain"),
                        (38.4110, -79.9940, 4848, "Village")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-25",  # announced
        "enabled": False, "stage": "shadow",
    },
    # ---------- Wave 3 (11/19/2026): shadow mode only ----------
    # Boyne (Sugarloaf, Sunday River, Loon), ORDA (Whiteface, Gore) and top independents. Pass = the main one (Revelstoke,
    # Taos, Sugarloaf and Sunday River are also on the Mountain Collective). Same as Wave 2: no resort
    # page is read yet (no open feed found; the page reader isn't built), so forecast + snow stations only.
    # Pass labels for the independents and every opening day (est.) get checked before launch.
    "sugarloaf": {
        "name": "Sugarloaf", "region": "Maine", "pass": "Ikon",
        "site": "https://www.sugarloaf.com", "snow_report_path": None, "reportpal": "sl", "grooming_pdf": None,
        "lat": 45.0400, "lon": -70.3100, "elevation_ft": 2800,
        "bands": _bands((45.0640, -70.3100, 1417, "base"), (45.0400, -70.3100, 2800, "mid-mountain"),
                        (45.0314, -70.3131, 4237, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-20",  # Ikon list
        "enabled": False, "stage": "shadow",
    },
    "sunday-river": {
        "name": "Sunday River", "region": "Maine", "pass": "Ikon",
        "site": "https://www.sundayriver.com", "snow_report_path": None, "reportpal": "sr", "grooming_pdf": None,
        "lat": 44.4650, "lon": -70.8750, "elevation_ft": 1800,
        "bands": _bands((44.4730, -70.8570, 800, "South Ridge"), (44.4650, -70.8750, 1800, "mid-mountain"),
                        (44.4580, -70.9000, 3140, "Oz")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-15",  # Ikon list, tentative
        "enabled": False, "stage": "shadow",
    },
    "loon": {
        "name": "Loon Mountain", "region": "New Hampshire", "pass": "Ikon",
        "site": "https://www.loonmtn.com", "snow_report_path": None, "reportpal": "lm", "grooming_pdf": None,
        "lat": 44.0445, "lon": -71.6288, "elevation_ft": 2000,
        "bands": _bands((44.0563, -71.6299, 950, "base"), (44.0445, -71.6288, 2000, "mid-mountain"),
                        (44.0360, -71.6210, 3050, "North Peak")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-21",  # est.
        "enabled": False, "stage": "shadow",
    },
    "whiteface": {
        "name": "Whiteface", "region": "New York", "pass": "Mountain Collective",
        "site": "https://whiteface.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.3600, "lon": -73.8800, "elevation_ft": 2400,
        "bands": _bands((44.3600, -73.8590, 1220, "base"), (44.3600, -73.8800, 2400, "Mid Station"),
                        (44.3634, -73.8995, 4386, "Lookout Mountain")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-26",  # est.
        "enabled": False, "stage": "shadow",
    },
    "gore": {
        "name": "Gore Mountain", "region": "New York", "pass": "Independent",
        "site": "https://goremountain.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 43.6740, "lon": -74.0280, "elevation_ft": 2500,
        "bands": _bands((43.6730, -74.0060, 1500, "base"), (43.6740, -74.0280, 2500, "mid-mountain"),
                        (43.6731, -74.0487, 3600, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-26",  # est.
        "enabled": False, "stage": "shadow",
    },
    "taos": {
        "name": "Taos Ski Valley", "region": "New Mexico", "pass": "Ikon",
        "site": "https://www.skitaos.com", "snow_report_path": None,
        "report_feed": {"kind": "json", "url": "https://www.skitaos.com/api/conditions",
                        "fields": {"overnight_in": "snowData.overnight", "last_24h_in": "snowData.last24Hours",
                                   "last_48h_in": "snowData.last48Hours", "last_7d_in": "snowData.last7Days",
                                   "base_in": "snowData.base", "season_in": "snowData.seasonTotal"}}, "grooming_pdf": None,
        "lat": 36.5850, "lon": -105.4500, "elevation_ft": 10500,
        "bands": _bands((36.5960, -105.4540, 9207, "base"), (36.5850, -105.4500, 10500, "mid-mountain"),
                        (36.5625, -105.4480, 12481, "Kachina Peak")),
        "snotel": ["1168:NM:SNTL", "1307:NM:SNTL"], "snotel_label": "Taos Powderhorn",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-26",  # announced
        "enabled": False, "stage": "shadow",
    },
    "whitefish": {
        "name": "Whitefish Mountain", "region": "Montana", "pass": "Independent",
        "site": "https://skiwhitefish.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://skiwhitefish.com/snowreport/", "start": "Summit"}, "grooming_pdf": None,
        "lat": 48.4930, "lon": -114.3620, "elevation_ft": 5800,
        "bands": _bands((48.4840, -114.3530, 4464, "base"), (48.4930, -114.3620, 5800, "mid-mountain"),
                        (48.5030, -114.3420, 6817, "summit")),
        "snotel": [], "snotel_label": None,  # nearest SNOTEL (Stryker Basin) is 31 km away: too far to count as truth
        "cams": [{"label": "Stumpy (snow stake)", "image": "https://skiwhitefish.com/inbound/cams/2425_StumpyCam.jpg", "live": None}], "patrol": None, "tz": "America/Denver", "opening_day": "2026-12-04",  # announced
        "enabled": False, "stage": "shadow",
    },
    "grand-targhee": {
        "name": "Grand Targhee", "region": "Wyoming", "pass": "Mountain Collective",
        "site": "https://www.grandtarghee.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 43.7883, "lon": -110.9448, "elevation_ft": 9000,
        "bands": _bands((43.7890, -110.9580, 7851, "base"), (43.7883, -110.9448, 9000, "mid-mountain"),
                        (43.7870, -110.9340, 9862, "Fred's Mountain")),
        "snotel": ["1082:WY:SNTL"], "snotel_label": "Grand Targhee",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-21",  # est.; the resort says it is delaying opening day, no date yet
        "enabled": False, "stage": "shadow",
    },
    "revelstoke": {
        "name": "Revelstoke", "region": "British Columbia", "pass": "Ikon",
        "site": "https://www.revelstokemountainresort.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://www.revelstokemountainresort.com/mountain/conditions/snow-report/", "start": "Snow Report"}, "grooming_pdf": None,
        "lat": 50.9571, "lon": -118.1161, "elevation_ft": 5600,
        "bands": _bands((50.9580, -118.1640, 1680, "base"), (50.9571, -118.1161, 5600, "Mackenzie Outpost"),
                        (50.9640, -118.1031, 7300, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [{"label": "Gnorm (snow stake)", "image": "https://www.revelstokemountainresort.com/uploads/gnorm/gnorm.jpg", "live": None}], "patrol": None, "tz": "America/Vancouver", "opening_day": "2026-12-05",  # announced
        "enabled": False, "stage": "shadow",
    },
    "jay-peak": {
        "name": "Jay Peak", "region": "Vermont", "pass": "Indy",
        "site": "https://jaypeakresort.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.9300, "lon": -72.5150, "elevation_ft": 2900,
        "bands": _bands((44.9370, -72.5040, 1815, "base"), (44.9300, -72.5150, 2900, "mid-mountain"),
                        (44.9244, -72.5252, 3968, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-26",  # est.
        "enabled": False, "stage": "shadow",
    },
    "loveland": {
        "name": "Loveland", "region": "Colorado", "pass": "Indy",
        "site": "https://skiloveland.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://skiloveland.com/snow-report/", "order": "before"}, "grooming_pdf": None,
        "lat": 39.6700, "lon": -105.9050, "elevation_ft": 11500,
        "bands": _bands((39.6800, -105.8980, 10800, "Loveland Basin"), (39.6700, -105.9050, 11500, "mid-mountain"),
                        (39.6622, -105.9098, 13010, "summit")),
        "snotel": ["602:CO:SNTL", "505:CO:SNTL"], "snotel_label": "Loveland Basin",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-07",  # opened
        "enabled": False, "stage": "shadow",
    },
    "wolf-creek": {
        "name": "Wolf Creek", "region": "Colorado", "pass": "Independent",
        "site": "https://wolfcreekski.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://wolfcreekski.com/snow-report/"}, "grooming_pdf": None,
        "lat": 37.4700, "lon": -106.8000, "elevation_ft": 11000,
        "bands": _bands((37.4734, -106.7861, 10300, "base"), (37.4700, -106.8000, 11000, "mid-mountain"),
                        (37.4560, -106.7951, 11904, "summit")),
        "snotel": ["874:CO:SNTL", "840:CO:SNTL"], "snotel_label": "Wolf Creek Summit",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-10-31",  # opened
        "enabled": False, "stage": "shadow",
    },
    "mt-hood-meadows": {
        "name": "Mt. Hood Meadows", "region": "Oregon", "pass": "Indy",
        "site": "https://www.skihood.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 45.3400, "lon": -121.6760, "elevation_ft": 6500,
        "bands": _bands((45.3310, -121.6650, 5250, "base"), (45.3400, -121.6760, 6500, "mid-mountain"),
                        (45.3500, -121.6850, 7300, "Cascade Express top")),
        "snotel": ["651:OR:SNTL", "1314:OR:SNTL"], "snotel_label": "Mt Hood Test Site",
        "cams": [], "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-12-04",  # announced
        "enabled": False, "stage": "shadow",
    },
    "big-white": {
        "name": "Big White", "region": "British Columbia", "pass": "Indy",
        "site": "https://www.bigwhite.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://www.bigwhite.com/mountain-conditions/daily-snow-report"}, "grooming_pdf": None,
        "lat": 49.7210, "lon": -118.9290, "elevation_ft": 5757,
        "bands": _bands((49.7450, -118.9820, 4950, "base"), (49.7210, -118.9290, 5757, "Village"),
                        (49.7444, -118.9354, 7606, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/Vancouver", "opening_day": "2026-11-26",  # est.
        "enabled": False, "stage": "shadow",
    },
    # ---------- Wave 4 (11/19/2026): shadow mode only ----------
    # Smaller independents. Forecast + snow stations until the page reader exists. Opening days (est.) and pass
    # labels get checked before launch.
    "powder-mountain": {
        "name": "Powder Mountain", "region": "Utah", "pass": "Independent",
        "site": "https://powdermountain.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://www.powdermountain.com/conditions", "start": "Updated"}, "grooming_pdf": None,
        "lat": 41.3775, "lon": -111.7826, "elevation_ft": 8000,
        "bands": _bands((41.3600, -111.8075, 6900, "base"), (41.3775, -111.7826, 8000, "mid-mountain"),
                        (41.3914, -111.7931, 9422, "James Peak")),
        "snotel": ["1300:UT:SNTL", "582:UT:SNTL"], "snotel_label": "Powder Mountain",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-12-11",  # announced
        "enabled": False, "stage": "shadow",
    },
    "saddleback": {
        "name": "Saddleback", "region": "Maine", "pass": "Indy",
        "site": "https://www.saddlebackmaine.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.9420, "lon": -70.5150, "elevation_ft": 3200,
        "bands": _bands((44.9520, -70.5300, 2120, "base"), (44.9420, -70.5150, 3200, "mid-mountain"),
                        (44.9360, -70.5050, 4120, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-27",  # est.
        "enabled": False, "stage": "shadow",
    },
    "holiday-valley": {
        "name": "Holiday Valley", "region": "New York", "pass": "Independent",
        "site": "https://www.holidayvalley.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 42.2605, "lon": -78.6770, "elevation_ft": 1900,
        "bands": _bands((42.2625, -78.6655, 1500, "base"), (42.2605, -78.6770, 1900, "mid-mountain"),
                        (42.2573, -78.6825, 2250, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-12-05",  # est.
        "enabled": False, "stage": "shadow",
    },
    "bretton-woods": {
        "name": "Bretton Woods", "region": "New Hampshire", "pass": "Independent",
        "site": "https://www.brettonwoods.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.2480, "lon": -71.4620, "elevation_ft": 2300,
        "bands": _bands((44.2575, -71.4425, 1500, "base"), (44.2480, -71.4620, 2300, "mid-mountain"),
                        (44.2400, -71.4600, 3100, "Mt. Rosebrook")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-21",  # est.
        "enabled": False, "stage": "shadow",
    },
    "smugglers-notch": {
        "name": "Smugglers' Notch", "region": "Vermont", "pass": "Indy",
        "site": "https://www.smuggs.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.5660, "lon": -72.7681, "elevation_ft": 2500,
        "bands": _bands((44.5880, -72.7890, 1030, "Morse base"), (44.5660, -72.7681, 2500, "mid-mountain"),
                        (44.5610, -72.7592, 3640, "Madonna summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-12-05",  # est.
        "enabled": False, "stage": "shadow",
    },
    "mad-river-glen": {
        "name": "Mad River Glen", "region": "Vermont", "pass": "Independent",
        "site": "https://www.madriverglen.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.1963, "lon": -72.9276, "elevation_ft": 2800,
        "bands": _bands((44.2030, -72.9170, 1600, "base"), (44.1963, -72.9276, 2800, "mid-mountain"),
                        (44.1940, -72.9340, 3637, "General Stark")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-12-12",  # est.
        "enabled": False, "stage": "shadow",
    },
    "cannon": {
        "name": "Cannon Mountain", "region": "New Hampshire", "pass": "Indy",
        "site": "https://www.cannonmt.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.1635, "lon": -71.6916, "elevation_ft": 3000,
        "bands": _bands((44.1695, -71.6870, 2000, "Tram base"), (44.1635, -71.6916, 3000, "mid-mountain"),
                        (44.1563, -71.6985, 4080, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-27",  # est.
        "enabled": False, "stage": "shadow",
    },
    "waterville-valley": {
        "name": "Waterville Valley", "region": "New Hampshire", "pass": "Indy",
        "site": "https://www.waterville.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 43.9661, "lon": -71.5474, "elevation_ft": 3000,
        "bands": _bands((43.9650, -71.5270, 1984, "base"), (43.9661, -71.5474, 3000, "mid-mountain"),
                        (43.9663, -71.5567, 4004, "Mt. Tecumseh")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-27",  # est.
        "enabled": False, "stage": "shadow",
    },
    "purgatory": {
        "name": "Purgatory", "region": "Colorado", "pass": "Independent",
        "site": "https://www.purgatory.ski", "snow_report_path": None, "grooming_pdf": None,
        "lat": 37.6250, "lon": -107.8300, "elevation_ft": 9800,
        "bands": _bands((37.6300, -107.8150, 8793, "base"), (37.6250, -107.8300, 9800, "mid-mountain"),
                        (37.6200, -107.8400, 10822, "summit")),
        "snotel": ["387:CO:SNTL", "780:CO:SNTL"], "snotel_label": "Cascade #2",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-20",  # announced
        "enabled": False, "stage": "shadow",
    },
    "tamarack": {
        "name": "Tamarack", "region": "Idaho", "pass": "Indy",
        "site": "https://tamarackidaho.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://www.tamarackidaho.com/snow-report", "order": "before"}, "grooming_pdf": None,
        "lat": 44.6750, "lon": -116.1450, "elevation_ft": 6500,
        "bands": _bands((44.6700, -116.1220, 4900, "base"), (44.6750, -116.1450, 6500, "mid-mountain"),
                        (44.6727, -116.1649, 7700, "summit")),
        "snotel": ["1016:ID:SNTL", "782:ID:SNTL"], "snotel_label": "Long Valley",
        "cams": [], "patrol": None, "tz": "America/Boise", "opening_day": "2026-12-12",  # est.
        "enabled": False, "stage": "shadow",
    },
    "sun-peaks": {
        "name": "Sun Peaks", "region": "British Columbia", "pass": "Mountain Collective",
        "site": "https://www.sunpeaksresort.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://www.sunpeaksresort.com/ski-ride/weather-conditions-cams/weather-snow-report", "start": "Updated"}, "grooming_pdf": None,
        "lat": 50.8970, "lon": -119.9040, "elevation_ft": 5800,
        "bands": _bands((50.8840, -119.8860, 4117, "Village"), (50.8970, -119.9040, 5800, "mid-mountain"),
                        (50.9089, -119.9266, 6824, "Tod Mountain")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/Vancouver", "opening_day": "2026-11-21",  # announced
        "enabled": False, "stage": "shadow",
    },
    "mt-baker": {
        "name": "Mt. Baker", "region": "Washington", "pass": "Independent",
        "site": "https://www.mtbaker.us", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://www.mtbaker.us/snow-report/"}, "grooming_pdf": None,
        "lat": 48.8600, "lon": -121.6800, "elevation_ft": 4200,
        "bands": _bands((48.8617, -121.6570, 3500, "White Salmon"), (48.8600, -121.6800, 4200, "mid-mountain"),
                        (48.8527, -121.6776, 5089, "Panorama Dome")),
        "snotel": ["909:WA:SNTL", "999:WA:SNTL"], "snotel_label": "Wells Creek",
        "cams": [], "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-27",  # est.
        "enabled": False, "stage": "shadow",
    },
    # ---------- 11/20/2026: Whitewater (BC) and Japan, shadow mode only ----------
    # Japan reports are in cm (the readers convert to inches) and most pages are English. Japanese-only:
    # Nozawa Onsen. No reader yet: Lotte Arai (page is built by script) and Zao Onsen (off-season page shows
    # no snow numbers). No SNOTEL or NWS outside the US. Points checked against Open-Meteo elevations.
    "whitewater": {
        "name": "Whitewater", "region": "British Columbia", "pass": "Independent",
        "site": "https://whitewatermountainresort.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://whitewatermountainresort.com/conditions", "start": "Snow report summary",
                        "labels": {"last_48h_in": None, "season_in": r"total snow(?:fall)?"},
                        "stamp": r"Updated on (?P<mon>[A-Za-z]{3,9})\.? (?P<d>\d{1,2}), (?P<y>20\d\d)(?: at (?P<t>\d{1,2}:\d\d))?"}, "grooming_pdf": None,
        "lat": 49.4380, "lon": -117.1530, "elevation_ft": 6280,
        "bands": _bands((49.4436, -117.1452, 5354, "base lodge"), (49.4380, -117.1530, 6280, "snow plot level"), (49.4300, -117.1578, 6722, "Summit Chair top")),
        "snotel": [], "snotel_label": None,
        "cams": _url_cams([("https://webcams.skiwhitewater.com/webcams/summit/current.jpg", "Summit"),
                          ("https://webcams.skiwhitewater.com/webcams/lodge/current.jpg", "Lodge")]), "patrol": None, "tz": "America/Vancouver", "opening_day": "2026-12-04",  # tentative, per the resort's hours page
        "enabled": False, "stage": "shadow",
    },
    "niseko": {
        "name": "Niseko United", "region": "Hokkaido", "pass": "Ikon",
        "site": "https://www.niseko.ne.jp/en/", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://en.grand-hirafu.jp/snow/", "start": "LIVE Weather",  # Grand Hirafu, the largest of the four
                        "stamp": r"Snow (?P<y>20\d\d)\.(?P<m>\d{1,2})\.(?P<d>\d{1,2}) (?P<t>\d{1,2}:\d\d\s*[AP]M)"}, "grooming_pdf": None,
        "lat": 42.8660, "lon": 140.6840, "elevation_ft": 2247,
        "bands": _bands((42.8600, 140.7020, 948, "Hirafu base"), (42.8660, 140.6840, 2247, "mid-mountain"), (42.8733, 140.6600, 4121, "below Annupuri summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "Asia/Tokyo", "opening_day": "2026-11-28",  # Grand Hirafu, scheduled
        "enabled": False, "stage": "shadow",
    },
    "rusutsu": {
        "name": "Rusutsu", "region": "Hokkaido", "pass": "Epic",
        "site": "https://rusutsu.com/en/", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://rusutsu.com/en/snow-and-weather-report/", "start": "West Mt.",
                        "labels": {"base_in": r"snow s?accumulation", "season_in": r"total snowfall"},
                        "stamp": r"Update Date\s*:\s*(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>20\d\d)\S*\s+(?P<t>\d{1,2}:\d\d)"}, "grooming_pdf": None,
        "lat": 42.7600, "lon": 140.9050, "elevation_ft": 2064,
        "bands": _bands((42.7484, 140.9034, 1368, "resort base"), (42.7600, 140.9050, 2064, "West Mountain mid"), (42.7700, 140.9067, 3255, "West Mountain summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "Asia/Tokyo", "opening_day": "2026-11-28",  # scheduled (early season 1)
        "enabled": False, "stage": "shadow",
    },
    "furano": {
        "name": "Furano", "region": "Hokkaido", "pass": "Ikon",
        "site": "https://www.princehotels.com/en/ski/furano/", "snow_report_path": None,
        "report_feed": {"kind": "json", "url": "https://furapuri.com/ski/data.json", "cm": True,  # the resort's own snow report app; no date in it
                        "fields": {"last_24h_in": "weathers.0.last_snowfall", "base_in": "weathers.0.snowbase"}}, "grooming_pdf": None,
        "lat": 43.3250, "lon": 142.3350, "elevation_ft": 2198,
        "bands": _bands((43.3285, 142.3582, 932, "Kitanomine base"), (43.3250, 142.3350, 2198, "mid-mountain"), (43.3195, 142.3110, 3494, "ropeway top")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "Asia/Tokyo", "opening_day": "2026-11-28",  # scheduled, per the resort's snow report
        "enabled": False, "stage": "shadow",
    },
    "kiroro": {
        "name": "Kiroro", "region": "Hokkaido", "pass": "Independent",
        "site": "https://www.kiroro.co.jp/en/", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://www.kiroro.co.jp/en/dashboard/", "start": "Course Data",
                        "labels": {"season_in": r"total snowfall"},
                        "stamp": r"WEATHER AND LIFT STATUS (?P<mon>[A-Za-z]{3,9}) (?P<d>\d{1,2}), (?P<y>20\d\d)"}, "grooming_pdf": None,
        "lat": 43.0700, "lon": 140.9780, "elevation_ft": 2188,
        "bands": _bands((43.0767, 140.9864, 1781, "base"), (43.0700, 140.9780, 2188, "mid-mountain"), (43.0511, 140.9789, 3455, "upper mountain")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "Asia/Tokyo", "opening_day": "2026-11-28",  # early season starts, per the operating hours page
        "enabled": False, "stage": "shadow",
    },
    "hakuba-happo-one": {
        "name": "Hakuba Happo-one", "region": "Nagano", "pass": "Epic",
        "site": "https://www.happo-one.jp/en/", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://www.happo-one.jp/en/", "start": "USAGIDAIRA",
                        "labels": {"base_in": r"snow ?depth", "last_24h_in": r"snow ?fall"},
                        "stamp": r"Update at (?P<y>20\d\d)\.(?P<m>\d{1,2})\.(?P<d>\d{1,2}) (?P<t>\d{1,2}:\d\d)"}, "grooming_pdf": None,
        "lat": 36.7020, "lon": 137.8140, "elevation_ft": 4705,
        "bands": _bands((36.6990, 137.8370, 2687, "Happo base"), (36.7020, 137.8140, 4705, "Usagidaira"), (36.6980, 137.8000, 5879, "upper Kurobishi")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "Asia/Tokyo", "opening_day": "2026-12-01",  # est.; early-season tickets start 12/1
        "enabled": False, "stage": "shadow",
    },
    "nozawa-onsen": {
        "name": "Nozawa Onsen", "region": "Nagano", "pass": "Independent",
        "site": "https://nozawaski.com", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://nozawaski.com/winter/course/", "start": "積雪情報",  # Japanese only; Yamabiko area comes first
                        "labels": {"overnight_in": "までの積雪量", "base_in": "積雪量", "last_24h_in": None, "last_48h_in": None,
                                   "last_7d_in": None, "season_in": None},
                        "stamp": r"(?P<m>\d{1,2})/(?P<d>\d{1,2}) (?P<t>\d{1,2}:\d\d) 更新"}, "grooming_pdf": None,
        "lat": 36.9100, "lon": 138.4760, "elevation_ft": 4327,
        "bands": _bands((36.9230, 138.4470, 1844, "village base"), (36.9100, 138.4760, 4327, "Yamabiko area"), (36.9000, 138.4900, 4951, "upper mountain")),
        "snotel": [], "snotel_label": None,
        "cams": _url_cams([("https://nozawaski.sakura.ne.jp/livecam/yamabiko.jpg", "Yamabiko"),
                          ("https://nozawaski.sakura.ne.jp/livecam/uenotaira.jpg", "Uenotaira"),
                          ("https://nozawaski.sakura.ne.jp/livecam/nagasaka.jpg", "Nagasaka")]), "patrol": None, "tz": "Asia/Tokyo", "opening_day": "2026-11-28",  # scheduled
        "enabled": False, "stage": "shadow",
    },
    "shiga-kogen": {
        "name": "Shiga Kogen", "region": "Nagano", "pass": "Ikon",
        "site": "https://www.shigakogen.gr.jp/english/index.html", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://www.shigakogen.gr.jp/english/index.html", "start": "Today's Shiga Kogen",  # Hasuike
                        "labels": {"last_24h_in": r"snowfall:", "base_in": r"snow accumulation:"},
                        "stamp": r"(?P<d>\d{1,2}) (?P<mon>[A-Za-z]{3,9}),? (?P<y>20\d\d) (?P<t>\d{1,2}:\d\d\s*[ap]m)"}, "grooming_pdf": None,
        "lat": 36.7150, "lon": 138.5150, "elevation_ft": 5682,
        "bands": _bands((36.7120, 138.4900, 5197, "Hasuike side"), (36.7150, 138.5150, 5682, "Ichinose"), (36.6720, 138.5240, 7356, "Yokoteyama")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "Asia/Tokyo", "opening_day": "2026-11-21",  # Yokoteyama first; the others open 11/27 to 12/12
        "enabled": False, "stage": "shadow",
    },
    "lotte-arai": {
        "name": "Lotte Arai", "region": "Niigata", "pass": "Ikon",
        "site": "https://www.lottehotel.com/arai-resort/en/snow-season", "snow_report_path": None, "grooming_pdf": None,
        "lat": 36.9700, "lon": 138.1350, "elevation_ft": 3510,
        "bands": _bands((36.9700, 138.1700, 1512, "base"), (36.9700, 138.1350, 3510, "mid-mountain"), (36.9700, 138.1000, 4206, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "Asia/Tokyo", "opening_day": "2026-12-12",  # tentative, per the slope map page
        "enabled": False, "stage": "shadow",
    },
    "zao-onsen": {
        "name": "Zao Onsen", "region": "Yamagata", "pass": "Ikon",
        "site": "https://www.zao-spa.or.jp/english/ski/", "snow_report_path": None, "grooming_pdf": None,
        "lat": 38.1560, "lon": 140.4100, "elevation_ft": 3806,
        "bands": _bands((38.1680, 140.3960, 2877, "Onsen base"), (38.1560, 140.4100, 3806, "Juhyo Kogen"), (38.1400, 140.4320, 5394, "Jizo summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "Asia/Tokyo", "opening_day": "2026-12-05",  # est.; not announced on the English site
        "enabled": False, "stage": "shadow",
    },
    "appi": {
        "name": "Appi Kogen", "region": "Iwate", "pass": "Ikon",
        "site": "https://www.appi.co.jp/en/", "snow_report_path": None,
        "report_feed": {"kind": "text", "url": "https://www.appi.co.jp/en/", "start": "Ski slope conditions",
                        "labels": {"last_24h_in": r"fresh snow"},
                        "stamp": r"Updated: (?P<m>\d{1,2})/(?P<d>\d{1,2}) (?P<t>\d{1,2}:\d\d)"}, "grooming_pdf": None,
        "lat": 39.9900, "lon": 140.9630, "elevation_ft": 2700,
        "bands": _bands((40.0060, 140.9680, 2051, "base"), (39.9900, 140.9630, 2700, "mid-mountain"), (39.9760, 140.9590, 4154, "Mt. Maemori")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "Asia/Tokyo", "opening_day": "2026-12-05",  # scheduled, per the resort's course guide
        "enabled": False, "stage": "shadow",
    },
}

SNOW_REPORT_PATH = "/the-mountain/mountain-conditions/snow-and-weather-report.aspx"
CAMS_PATH = "/the-mountain/mountain-conditions/mountain-cams.aspx"


# Provinces of the Canadian resorts. NWS (api.weather.gov) covers only the US, so these skip it.
CANADA_REGIONS = {"British Columbia", "Alberta", "Quebec", "Ontario", "Nova Scotia", "New Brunswick", "Newfoundland"}
# Prefectures of the Japanese resorts (the app groups them under Japan).
JAPAN_REGIONS = {"Hokkaido", "Aomori", "Iwate", "Akita", "Yamagata", "Miyagi", "Fukushima", "Niigata", "Nagano", "Gunma",
                 "Tochigi", "Gifu", "Toyama"}


def enabled():
    """Slugs the scheduler runs and the app offers, in display order."""
    env = [s.strip() for s in os.environ.get("RESORTS", "").split(",") if s.strip() in RESORTS]
    return env or [k for k, r in RESORTS.items() if r["enabled"]]


def shadow():
    """Slugs that run only on the Render worker in shadow mode (no sends, not in the app) while their readers
    are checked. See docs/RENDER.md."""
    return [k for k, r in RESORTS.items() if r.get("stage") == "shadow" and not r["enabled"]]


# By region, not by abbreviation: some zones have changed their offsets (British Columbia stays
# on daylight time year-round from 11/2026), but people there still say "Pacific time".
_ZONE_NAMES = {"America/Los_Angeles": ("PT", "Pacific time"), "America/Vancouver": ("PT", "Pacific time"),
               "America/Denver": ("MT", "Mountain time"), "America/Boise": ("MT", "Mountain time"),
               "America/Edmonton": ("MT", "Mountain time"), "America/Phoenix": ("MT", "Mountain time"),
               "America/Chicago": ("CT", "Central time"), "America/New_York": ("ET", "Eastern time"),
               "America/Toronto": ("ET", "Eastern time"), "America/Detroit": ("ET", "Eastern time"),
               "America/Montreal": ("ET", "Eastern time"), "America/Halifax": ("AT", "Atlantic time"),
               "Asia/Tokyo": ("JST", "Japan time")}


def zone_names(tz):
    """("MT", "Mountain time") for an IANA zone."""
    if tz in _ZONE_NAMES:
        return _ZONE_NAMES[tz]
    from datetime import datetime
    from zoneinfo import ZoneInfo
    abbr = datetime.now(ZoneInfo(tz)).tzname() or tz
    return abbr, f"{abbr} time"


def zone_label(slug):
    """Short zone label for a resort, e.g. "PT"."""
    return zone_names(get(slug)["tz"])[0]


def zone_name(slug):
    """Long zone name for a resort, e.g. "Pacific time"."""
    return zone_names(get(slug)["tz"])[1]


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
    r.setdefault("dor_api", None)
    r.setdefault("reportpal", None)
    r.setdefault("report_feed", None)
    r["country"] = "CA" if r["region"] in CANADA_REGIONS else "JP" if r["region"] in JAPAN_REGIONS else "US"
    if r["dor_api"]:  # POWDR's open JSON feed (sources/dor.py): snow report and groomed runs
        r["snow_report"] = r["dor_api"] + "/api/v1/dor/drupal/snow-reports"
    elif r["reportpal"]:  # Boyne's open JSON feed on the resort's own site (sources/reportpal.py)
        from .sources.reportpal import url as _rp_url
        r["snow_report"] = _rp_url(r["site"], r["reportpal"])
    elif r["report_feed"]:  # a small per-resort reader (sources/feeds.py)
        r["snow_report"] = r["report_feed"]["url"]
    elif "snow_report_path" in r and r["snow_report_path"] is None:
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
                    "grooming": bool(r["grooming_pdf"] or r["dor_api"] or r["reportpal"])})
    return {"default": DEFAULT, "resorts": out}


def is_static(slug):
    """Nothing to watch for between refreshes: no grooming map and no snow report that's read.
    The scheduler only needs to run these every half hour (refresh + the 7:00 send)."""
    r = get(slug)
    return not r["grooming_pdf"] and not r["snow_report"] and not r["dor_api"]


def coverage():
    """What each resort has and lacks: cams and where its snow report comes from (the admin "Cams and
    reports" table, so Young can see what's missing and send cam links in the thread)."""
    rows = []
    for slug in RESORTS:
        r = get(slug)
        if r["dor_api"]:
            report = "POWDR feed"
        elif r["reportpal"]:
            report = "Boyne feed"
        elif r["report_feed"]:
            report = "Resort feed" if r["report_feed"]["kind"] == "json" else "Report page"
        elif r["snow_report"]:
            report = "Vail page"
        else:
            report = ""
        rows.append({"resort": slug, "name": r["name"], "region": r["region"], "pass": r["pass"],
                     "stage": "live" if r["enabled"] else (r.get("stage") or "off"), "site": r["site"],
                     "cams": len(r["cams"]), "cam_labels": [c["label"] for c in r["cams"]],
                     "stake": any("stake" in c["label"].lower() for c in r["cams"]),
                     "report": report, "report_url": r["snow_report"] or "",
                     "grooming": bool(r["grooming_pdf"] or r["dor_api"] or r["reportpal"])})
    return rows

