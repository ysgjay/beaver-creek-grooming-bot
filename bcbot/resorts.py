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
        "site": "https://tellurideskiresort.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 37.9160, "lon": -107.8360, "elevation_ft": 10800,
        "bands": _bands((37.9360, -107.8460, 8725, "base"), (37.9160, -107.8360, 10800, "mid-mountain"),
                        (37.9070, -107.8400, 12570, "summit")),
        "snotel": ['1344:CO:SNTL', '713:CO:SNTL'],
        "snotel_label": "Alta Lakes",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-12-05", "enabled": True,
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
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-08", "enabled": True,
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
        "site": "https://www.snowbird.com", "snow_report_path": None, "dor_api": "https://api.snowbird.com", "grooming_pdf": None,
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

    # ---------- Wave 1 (11/19/2026): shadow mode only ----------
    # "stage": "shadow" = the Render worker runs these in shadow mode (no sends, nothing shown in the app)
    # until their readers have matched the resorts' own pages for 3 days. Then set enabled True and drop stage.
    # Snow report path and Brown Rice cam ids were checked on each site 11/19/2026. None posts a Lumiplan
    # grooming map. Points are approximate on-mountain spots; check them against the trail map when tuning.
    "whistler-blackcomb": {
        "name": "Whistler Blackcomb", "region": "British Columbia", "pass": "Epic",
        "site": "https://www.whistlerblackcomb.com", "grooming_pdf": None,
        "lat": 50.0670, "lon": -122.9480, "elevation_ft": 6069,
        "bands": _bands((50.1145, -122.9540, 2214, "Whistler Village"), (50.0670, -122.9480, 6069, "Roundhouse"),
                        (50.0610, -122.9580, 7160, "Whistler Peak")),
        "snotel": [], "snotel_label": None,  # no SNOTEL in Canada
        "cams": _cams([("whistlerroundhouse", "Roundhouse"), ("whistlerpeak", "Whistler Peak"),
                       ("whistlerblackcomb", "Blackcomb"), ("whistlersnowstack", "Snow stake"),
                       ("whistler7thheaven", "7th Heaven"), ("whistlervillage", "Village"),
                       ("whistlercreekside", "Creekside")]),
        "patrol": None, "tz": "America/Vancouver", "opening_day": "2026-11-20", "enabled": False, "stage": "shadow",
    },
    "heavenly": {
        "name": "Heavenly", "region": "California", "pass": "Epic",
        "site": "https://www.skiheavenly.com", "grooming_pdf": None,
        "lat": 38.9200, "lon": -119.9150, "elevation_ft": 8500,
        "bands": _bands((38.9350, -119.9400, 6565, "California Lodge"), (38.9200, -119.9150, 8500, "mid-mountain"),
                        (38.9050, -119.8920, 10067, "Monument Peak")),
        "snotel": ["518:CA:SNTL", "508:CA:SNTL"], "snotel_label": "Heavenly Valley",
        "cams": _cams([("heavenlydipper", "Dipper"), ("heavenlymidstation", "Mid-station"), ("heavenlytram", "Tram"),
                       ("heavenlyeastpeak", "East Peak")]),
        "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-20", "enabled": False, "stage": "shadow",
    },
    "northstar": {
        "name": "Northstar", "region": "California", "pass": "Epic",
        "site": "https://www.northstarcalifornia.com", "grooming_pdf": None,
        "lat": 39.2640, "lon": -120.1290, "elevation_ft": 7600,
        "bands": _bands((39.2740, -120.1210, 6330, "Village"), (39.2640, -120.1290, 7600, "mid-mountain"),
                        (39.2540, -120.1340, 8610, "Mt. Pluto")),
        "snotel": ["834:CA:SNTL", "809:CA:SNTL"], "snotel_label": "Truckee #2",
        "cams": _cams([("northstarsnowstake", "Snow stake"), ("northstarspluto", "Mt. Pluto"),
                       ("northstarmidmountain", "Mid-mountain"), ("northstarvillage", "Village")]),
        "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-20", "enabled": False, "stage": "shadow",
    },
    "kirkwood": {
        "name": "Kirkwood", "region": "California", "pass": "Epic",
        "site": "https://www.kirkwood.com", "grooming_pdf": None,
        "lat": 38.6720, "lon": -120.0700, "elevation_ft": 8800,
        "bands": _bands((38.6850, -120.0650, 7800, "base"), (38.6720, -120.0700, 8800, "mid-mountain"),
                        (38.6650, -120.0780, 9876, "summit")),
        "snotel": ["1067:CA:SNTL", "1049:CA:SNTL"], "snotel_label": "Carson Pass",
        "cams": _cams([("kirkwoodcornice", "Cornice"), ("kirkwoodredcliffs", "Red Cliffs")]),
        "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-12-04", "enabled": False, "stage": "shadow",
    },
    "stevens-pass": {
        "name": "Stevens Pass", "region": "Washington", "pass": "Epic",
        "site": "https://www.stevenspass.com", "snow_report_path": "/the-mountain/mountain-conditions/weather-report.aspx",
        "grooming_pdf": None,
        "lat": 47.7380, "lon": -121.0960, "elevation_ft": 4800,
        "bands": _bands((47.7450, -121.0890, 4061, "base"), (47.7380, -121.0960, 4800, "mid-mountain"),
                        (47.7310, -121.0990, 5845, "summit")),
        "snotel": ["791:WA:SNTL", "1338:WA:SNTL"], "snotel_label": "Stevens Pass",
        "cams": _cams([("stevenspasssnowstake", "Snow stake"), ("stevenspasscourtyard", "Courtyard"),
                       ("stevenspassschool", "Ski school"), ("stevenspassjupiter", "Jupiter"),
                       ("stevenspassskyline", "Skyline")]),
        "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-12-04", "enabled": False, "stage": "shadow",
    },
    "stowe": {
        "name": "Stowe", "region": "Vermont", "pass": "Epic",
        "site": "https://www.stowe.com", "grooming_pdf": None,
        "lat": 44.5320, "lon": -72.7950, "elevation_ft": 2700,
        "bands": _bands((44.5300, -72.7810, 1559, "base"), (44.5320, -72.7950, 2700, "mid-mountain"),
                        (44.5310, -72.8060, 3625, "Cliff House")),
        "snotel": [], "snotel_label": None,  # no SNOTEL in the East
        "cams": _cams([("stowesnowstake", "Snow stake"), ("stowemidwaybasestation", "Midway"),
                       ("stowevillage", "Village")]),
        # Opening day not announced yet (11/19); last season's target was the Saturday before Thanksgiving.
        "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-21", "enabled": False, "stage": "shadow",
    },
    "okemo": {
        "name": "Okemo", "region": "Vermont", "pass": "Epic",
        "site": "https://www.okemo.com", "grooming_pdf": None,
        "lat": 43.4010, "lon": -72.7330, "elevation_ft": 2300,
        "bands": _bands((43.4020, -72.7180, 1144, "base"), (43.4010, -72.7330, 2300, "mid-mountain"),
                        (43.4015, -72.7520, 3344, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": _cams([("okemosnowstake", "Snow stake"), ("okemosummit", "Summit"), ("okemosugarhouse", "Sugar House"),
                       ("okemoroundhouse", "Roundhouse")]),
        "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-21", "enabled": False, "stage": "shadow",
    },
    "mount-snow": {
        "name": "Mount Snow", "region": "Vermont", "pass": "Epic",
        "site": "https://www.mountsnow.com", "snow_report_path": "/the-mountain/mountain-conditions/weather-report.aspx",
        "grooming_pdf": None,
        "lat": 42.9640, "lon": -72.9280, "elevation_ft": 2800,
        "bands": _bands((42.9600, -72.9200, 1900, "base"), (42.9640, -72.9280, 2800, "mid-mountain"),
                        (42.9680, -72.9330, 3600, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": _cams([("mountsnowsnowstake", "Snow stake"), ("mountsnowsummit", "Summit"), ("mountsnowcarinthia", "Carinthia"),
                       ("mountsnowbase", "Base")]),
        "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-21", "enabled": False, "stage": "shadow",
    },
    "seven-springs": {
        "name": "Seven Springs", "region": "Pennsylvania", "pass": "Epic",
        "site": "https://www.7springs.com", "grooming_pdf": None,
        "lat": 40.0240, "lon": -79.2950, "elevation_ft": 2600,
        "bands": _bands((40.0200, -79.2990, 2240, "base"), (40.0240, -79.2950, 2600, "mid-mountain"),
                        (40.0280, -79.2920, 2994, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": _cams([("sevensprings", "Main"), ("sevenspringsnorthface", "North Face")]),
        # Opening day not announced yet (11/19).
        "patrol": None, "tz": "America/New_York", "opening_day": "2026-12-04", "enabled": False, "stage": "shadow",
    },
    # Killington (locally owned since POWDR sold it in 2024) and POWDR's Mt. Bachelor: no open feed like Copper's
    # (checked 11/19), so for now these two
    # run on forecast and snow stations only, like Telluride.
    "killington": {
        "name": "Killington", "region": "Vermont", "pass": "Ikon",
        "site": "https://www.killington.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 43.6220, "lon": -72.8060, "elevation_ft": 3200,
        "bands": _bands((43.6290, -72.7950, 2200, "Snowshed base"), (43.6220, -72.8060, 3200, "mid-mountain"),
                        (43.6045, -72.8200, 4241, "Killington Peak")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York",
        "opening_day": "2026-11-01",  # already open per Ikon (11/19); Killington sets no date in advance
        "enabled": False, "stage": "shadow",
    },
    "mt-bachelor": {
        "name": "Mt. Bachelor", "region": "Oregon", "pass": "Ikon",
        "site": "https://www.mtbachelor.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 43.9850, "lon": -121.6830, "elevation_ft": 7775,
        "bands": _bands((43.9910, -121.6780, 6300, "West Village"), (43.9850, -121.6830, 7775, "Pine Marten"),
                        (43.9790, -121.6886, 9065, "summit")),
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
        "site": "https://www.jacksonhole.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 43.5925, "lon": -110.8480, "elevation_ft": 7835,
        "bands": _bands((43.5875, -110.8279, 6311, "Teton Village"), (43.5925, -110.8480, 7835, "mid-mountain"),
                        (43.5980, -110.8700, 10450, "Rendezvous summit")),
        "snotel": ["689:WY:SNTL", "1082:WY:SNTL"], "snotel_label": "Phillips Bench",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-27",  # announced
        "enabled": False, "stage": "shadow",
    },
    "big-sky": {
        "name": "Big Sky", "region": "Montana", "pass": "Ikon",
        "site": "https://www.bigskyresort.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 45.2780, "lon": -111.4250, "elevation_ft": 8800,
        "bands": _bands((45.2860, -111.4010, 7500, "Mountain Village"), (45.2780, -111.4250, 8800, "mid-mountain"),
                        (45.2785, -111.4500, 11166, "Lone Peak")),
        "snotel": ["590:MT:SNTL", "385:MT:SNTL"], "snotel_label": "Lone Mountain",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-25",  # announced
        "enabled": False, "stage": "shadow",
    },
    "banff-sunshine": {
        "name": "Banff Sunshine", "region": "Alberta", "pass": "Ikon",
        "site": "https://www.skibanff.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 51.0790, "lon": -115.7820, "elevation_ft": 7082,
        "bands": _bands((51.1150, -115.7630, 5440, "Gondola base"), (51.0790, -115.7820, 7082, "Sunshine Village"),
                        (51.0650, -115.7700, 7595, "upper mountain")),
        "snotel": [], "snotel_label": None,  # no SNOTEL in Canada
        "cams": [], "patrol": None, "tz": "America/Edmonton", "opening_day": "2026-11-06",  # reported, not confirmed
        "enabled": False, "stage": "shadow",
    },
    "lake-louise": {
        "name": "Lake Louise", "region": "Alberta", "pass": "Ikon",
        "site": "https://www.skilouise.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 51.4500, "lon": -116.1500, "elevation_ft": 6800,
        "bands": _bands((51.4420, -116.1620, 5400, "base"), (51.4500, -116.1500, 6800, "Whitehorn"),
                        (51.4630, -116.1330, 8650, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/Edmonton", "opening_day": "2026-11-01",  # opened
        "enabled": False, "stage": "shadow",
    },
    "sun-valley": {
        "name": "Sun Valley", "region": "Idaho", "pass": "Ikon",
        "site": "https://www.sunvalley.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 43.6670, "lon": -114.3880, "elevation_ft": 7500,
        "bands": _bands((43.6750, -114.3700, 5750, "River Run"), (43.6670, -114.3880, 7500, "mid-mountain"),
                        (43.6597, -114.4033, 9150, "Bald Mountain summit")),
        "snotel": ["895:ID:SNTL", "537:ID:SNTL"], "snotel_label": "Chocolate Gulch",
        "cams": [], "patrol": None, "tz": "America/Boise", "opening_day": "2026-11-26",  # est.
        "enabled": False, "stage": "shadow",
    },
    # Alterra Mountain Company
    "mammoth": {
        "name": "Mammoth Mountain", "region": "California", "pass": "Ikon",
        "site": "https://www.mammothmountain.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 37.6440, "lon": -119.0390, "elevation_ft": 9600,
        "bands": _bands((37.6510, -119.0270, 8900, "Main Lodge"), (37.6440, -119.0390, 9600, "McCoy Station"),
                        (37.6310, -119.0330, 11053, "summit")),
        "snotel": [], "snotel_label": None,  # nearest SNOTEL (Virginia Lakes Ridge) is 51 km away: too far to count as truth
        "cams": [], "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-05",  # opened early
        "enabled": False, "stage": "shadow",
    },
    "palisades-tahoe": {
        "name": "Palisades Tahoe", "region": "California", "pass": "Ikon",
        "site": "https://www.palisadestahoe.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 39.1880, "lon": -120.2620, "elevation_ft": 8200,
        "bands": _bands((39.1970, -120.2350, 6200, "Olympic Valley"), (39.1880, -120.2620, 8200, "High Camp"),
                        (39.1965, -120.2830, 9006, "Granite Chief")),
        "snotel": ["784:CA:SNTL", "848:CA:SNTL"], "snotel_label": "Palisades Tahoe",
        "cams": [], "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-25",  # announced
        "enabled": False, "stage": "shadow",
    },
    "big-bear": {
        "name": "Big Bear Mountain", "region": "California", "pass": "Ikon",
        "site": "https://www.bigbearmountainresort.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 34.2260, "lon": -116.8900, "elevation_ft": 7600,
        "bands": _bands((34.2365, -116.8895, 7000, "Snow Summit base"), (34.2260, -116.8900, 7600, "mid-mountain"),
                        (34.2180, -116.8920, 8200, "Snow Summit summit")),
        "snotel": [], "snotel_label": None,  # no SNOTEL in Southern California (nearest is 250 km away)
        "cams": [], "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-20",  # est.
        "enabled": False, "stage": "shadow",
    },
    "crystal-mountain": {
        "name": "Crystal Mountain", "region": "Washington", "pass": "Ikon",
        "site": "https://www.crystalmountainresort.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 46.9300, "lon": -121.4900, "elevation_ft": 5800,
        "bands": _bands((46.9350, -121.4750, 4400, "base"), (46.9300, -121.4900, 5800, "mid-mountain"),
                        (46.9280, -121.5040, 7012, "summit")),
        "snotel": ["642:WA:SNTL", "1085:WA:SNTL"], "snotel_label": "Morse Lake",
        "cams": [], "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-27",  # announced
        "enabled": False, "stage": "shadow",
    },
    "tremblant": {
        "name": "Tremblant", "region": "Quebec", "pass": "Ikon",
        "site": "https://www.tremblant.ca", "snow_report_path": None, "grooming_pdf": None,
        "lat": 46.2180, "lon": -74.5700, "elevation_ft": 2000,
        "bands": _bands((46.2090, -74.5850, 755, "Village"), (46.2180, -74.5700, 2000, "mid-mountain"),
                        (46.2265, -74.5560, 2871, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/Toronto", "opening_day": "2026-11-26",  # announced
        "enabled": False, "stage": "shadow",
    },
    "sugarbush": {
        "name": "Sugarbush", "region": "Vermont", "pass": "Ikon",
        "site": "https://www.sugarbush.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.1400, "lon": -72.9100, "elevation_ft": 2500,
        "bands": _bands((44.1360, -72.8940, 1483, "Lincoln Peak base"), (44.1400, -72.9100, 2500, "mid-mountain"),
                        (44.1440, -72.9300, 3975, "Lincoln Peak")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-21",  # est.
        "enabled": False, "stage": "shadow",
    },
    "stratton": {
        "name": "Stratton", "region": "Vermont", "pass": "Ikon",
        "site": "https://www.stratton.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 43.1080, "lon": -72.9150, "elevation_ft": 2900,
        "bands": _bands((43.1130, -72.9070, 1872, "base"), (43.1080, -72.9150, 2900, "mid-mountain"),
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
        "bands": _bands((38.4080, -80.0080, 3348, "base"), (38.4100, -80.0020, 4100, "mid-mountain"),
                        (38.4110, -79.9940, 4848, "Village")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-25",  # announced
        "enabled": False, "stage": "shadow",
    },
    # ---------- Wave 3 (11/19/2026): shadow mode only ----------
    # Boyne (Sugarloaf, Sunday River, Loon), ORDA (Whiteface, Gore) and top independents. Same as Wave 2: no resort
    # page is read yet (no open feed found; the page reader isn't built), so forecast + snow stations only.
    # Pass labels for the independents and every opening day (est.) get checked before launch.
    "sugarloaf": {
        "name": "Sugarloaf", "region": "Maine", "pass": "Ikon",
        "site": "https://www.sugarloaf.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 45.0400, "lon": -70.3100, "elevation_ft": 2800,
        "bands": _bands((45.0540, -70.3090, 1417, "base"), (45.0400, -70.3100, 2800, "mid-mountain"),
                        (45.0314, -70.3131, 4237, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-21",  # est.
        "enabled": False, "stage": "shadow",
    },
    "sunday-river": {
        "name": "Sunday River", "region": "Maine", "pass": "Ikon",
        "site": "https://www.sundayriver.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.4650, "lon": -70.8750, "elevation_ft": 1800,
        "bands": _bands((44.4730, -70.8570, 800, "South Ridge"), (44.4650, -70.8750, 1800, "mid-mountain"),
                        (44.4580, -70.9000, 3140, "Oz")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-14",  # est.
        "enabled": False, "stage": "shadow",
    },
    "loon": {
        "name": "Loon Mountain", "region": "New Hampshire", "pass": "Ikon",
        "site": "https://www.loonmtn.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.0450, "lon": -71.6380, "elevation_ft": 2000,
        "bands": _bands((44.0360, -71.6210, 950, "base"), (44.0450, -71.6380, 2000, "mid-mountain"),
                        (44.0530, -71.6510, 3050, "North Peak")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-21",  # est.
        "enabled": False, "stage": "shadow",
    },
    "whiteface": {
        "name": "Whiteface", "region": "New York", "pass": "Ikon",
        "site": "https://whiteface.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.3600, "lon": -73.8800, "elevation_ft": 2400,
        "bands": _bands((44.3600, -73.8590, 1220, "base"), (44.3600, -73.8800, 2400, "Mid Station"),
                        (44.3660, -73.9030, 4386, "Lookout Mountain")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-26",  # est.
        "enabled": False, "stage": "shadow",
    },
    "gore": {
        "name": "Gore Mountain", "region": "New York", "pass": "Ikon",
        "site": "https://goremountain.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 43.6650, "lon": -74.0300, "elevation_ft": 2500,
        "bands": _bands((43.6730, -74.0060, 1500, "base"), (43.6650, -74.0300, 2500, "mid-mountain"),
                        (43.6580, -74.0520, 3600, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-26",  # est.
        "enabled": False, "stage": "shadow",
    },
    "taos": {
        "name": "Taos Ski Valley", "region": "New Mexico", "pass": "Ikon",
        "site": "https://www.skitaos.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 36.5850, "lon": -105.4500, "elevation_ft": 10500,
        "bands": _bands((36.5960, -105.4540, 9207, "base"), (36.5850, -105.4500, 10500, "mid-mountain"),
                        (36.5720, -105.4460, 12481, "Kachina Peak")),
        "snotel": ["1168:NM:SNTL", "1307:NM:SNTL"], "snotel_label": "Taos Powderhorn",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-26",  # est.
        "enabled": False, "stage": "shadow",
    },
    "whitefish": {
        "name": "Whitefish Mountain", "region": "Montana", "pass": "Independent",
        "site": "https://skiwhitefish.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 48.4930, "lon": -114.3620, "elevation_ft": 5800,
        "bands": _bands((48.4840, -114.3530, 4464, "base"), (48.4930, -114.3620, 5800, "mid-mountain"),
                        (48.5040, -114.3700, 6817, "summit")),
        "snotel": ["1311:MT:SNTL"], "snotel_label": "Stryker Basin",  # nearest SNOTEL is 30 km away
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-12-05",  # est.
        "enabled": False, "stage": "shadow",
    },
    "grand-targhee": {
        "name": "Grand Targhee", "region": "Wyoming", "pass": "Mountain Collective",
        "site": "https://www.grandtarghee.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 43.7800, "lon": -110.9420, "elevation_ft": 9000,
        "bands": _bands((43.7890, -110.9580, 7851, "base"), (43.7800, -110.9420, 9000, "mid-mountain"),
                        (43.7720, -110.9350, 9862, "Fred's Mountain")),
        "snotel": ["1082:WY:SNTL", "689:WY:SNTL"], "snotel_label": "Grand Targhee",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-21",  # est.
        "enabled": False, "stage": "shadow",
    },
    "revelstoke": {
        "name": "Revelstoke", "region": "British Columbia", "pass": "Mountain Collective",
        "site": "https://www.revelstokemountainresort.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 50.9620, "lon": -118.1920, "elevation_ft": 5600,
        "bands": _bands((50.9580, -118.1640, 1680, "base"), (50.9620, -118.1920, 5600, "Mackenzie Outpost"),
                        (50.9530, -118.2300, 7300, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/Vancouver", "opening_day": "2026-12-05",  # est.
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
        "name": "Loveland", "region": "Colorado", "pass": "Independent",
        "site": "https://skiloveland.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 39.6700, "lon": -105.9050, "elevation_ft": 11500,
        "bands": _bands((39.6800, -105.8980, 10800, "Loveland Basin"), (39.6700, -105.9050, 11500, "mid-mountain"),
                        (39.6600, -105.9100, 13010, "summit")),
        "snotel": ["602:CO:SNTL", "505:CO:SNTL"], "snotel_label": "Loveland Basin",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-06",  # est.
        "enabled": False, "stage": "shadow",
    },
    "wolf-creek": {
        "name": "Wolf Creek", "region": "Colorado", "pass": "Independent",
        "site": "https://wolfcreekski.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 37.4700, "lon": -106.8000, "elevation_ft": 11000,
        "bands": _bands((37.4740, -106.7930, 10300, "base"), (37.4700, -106.8000, 11000, "mid-mountain"),
                        (37.4650, -106.8100, 11904, "summit")),
        "snotel": ["874:CO:SNTL", "840:CO:SNTL"], "snotel_label": "Wolf Creek Summit",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-07",  # est.
        "enabled": False, "stage": "shadow",
    },
    "mt-hood-meadows": {
        "name": "Mt. Hood Meadows", "region": "Oregon", "pass": "Independent",
        "site": "https://www.skihood.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 45.3350, "lon": -121.6680, "elevation_ft": 6500,
        "bands": _bands((45.3310, -121.6650, 5250, "base"), (45.3350, -121.6680, 6500, "mid-mountain"),
                        (45.3420, -121.6720, 7300, "Cascade Express top")),
        "snotel": ["651:OR:SNTL", "1314:OR:SNTL"], "snotel_label": "Mt Hood Test Site",
        "cams": [], "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-12-05",  # est.
        "enabled": False, "stage": "shadow",
    },
    "big-white": {
        "name": "Big White", "region": "British Columbia", "pass": "Independent",
        "site": "https://www.bigwhite.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 49.7210, "lon": -118.9290, "elevation_ft": 5757,
        "bands": _bands((49.7180, -118.9250, 4950, "base"), (49.7210, -118.9290, 5757, "Village"),
                        (49.7330, -118.9440, 7606, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/Vancouver", "opening_day": "2026-11-26",  # est.
        "enabled": False, "stage": "shadow",
    },
    # ---------- Wave 4 (11/19/2026): shadow mode only ----------
    # Smaller independents. Forecast + snow stations until the page reader exists. Opening days (est.) and pass
    # labels get checked before launch.
    "powder-mountain": {
        "name": "Powder Mountain", "region": "Utah", "pass": "Independent",
        "site": "https://powdermountain.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 41.3700, "lon": -111.7700, "elevation_ft": 8000,
        "bands": _bands((41.3790, -111.7800, 6900, "Timberline"), (41.3700, -111.7700, 8000, "mid-mountain"),
                        (41.3600, -111.7600, 9422, "Lightning Ridge")),
        "snotel": ["1300:UT:SNTL", "582:UT:SNTL"], "snotel_label": "Powder Mountain",
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-12-05",  # est.
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
        "lat": 42.2600, "lon": -78.6650, "elevation_ft": 1900,
        "bands": _bands((42.2650, -78.6700, 1500, "base"), (42.2600, -78.6650, 1900, "mid-mountain"),
                        (42.2560, -78.6580, 2250, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-12-05",  # est.
        "enabled": False, "stage": "shadow",
    },
    "bretton-woods": {
        "name": "Bretton Woods", "region": "New Hampshire", "pass": "Independent",
        "site": "https://www.brettonwoods.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.2480, "lon": -71.4620, "elevation_ft": 2300,
        "bands": _bands((44.2570, -71.4660, 1500, "base"), (44.2480, -71.4620, 2300, "mid-mountain"),
                        (44.2400, -71.4600, 3100, "Mt. Rosebrook")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-21",  # est.
        "enabled": False, "stage": "shadow",
    },
    "smugglers-notch": {
        "name": "Smugglers' Notch", "region": "Vermont", "pass": "Independent",
        "site": "https://www.smuggs.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.5700, "lon": -72.7950, "elevation_ft": 2500,
        "bands": _bands((44.5880, -72.7890, 1030, "Morse base"), (44.5700, -72.7950, 2500, "mid-mountain"),
                        (44.5640, -72.8010, 3640, "Madonna summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-12-05",  # est.
        "enabled": False, "stage": "shadow",
    },
    "mad-river-glen": {
        "name": "Mad River Glen", "region": "Vermont", "pass": "Independent",
        "site": "https://www.madriverglen.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.1990, "lon": -72.9250, "elevation_ft": 2800,
        "bands": _bands((44.2030, -72.9170, 1600, "base"), (44.1990, -72.9250, 2800, "mid-mountain"),
                        (44.1940, -72.9340, 3637, "General Stark")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-12-12",  # est.
        "enabled": False, "stage": "shadow",
    },
    "cannon": {
        "name": "Cannon Mountain", "region": "New Hampshire", "pass": "Independent",
        "site": "https://www.cannonmt.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.1580, "lon": -71.6930, "elevation_ft": 3000,
        "bands": _bands((44.1590, -71.6990, 2000, "Tram base"), (44.1580, -71.6930, 3000, "mid-mountain"),
                        (44.1563, -71.6985, 4080, "summit")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/New_York", "opening_day": "2026-11-27",  # est.
        "enabled": False, "stage": "shadow",
    },
    "waterville-valley": {
        "name": "Waterville Valley", "region": "New Hampshire", "pass": "Independent",
        "site": "https://www.waterville.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 43.9600, "lon": -71.5180, "elevation_ft": 3000,
        "bands": _bands((43.9650, -71.5270, 1984, "base"), (43.9600, -71.5180, 3000, "mid-mountain"),
                        (43.9550, -71.5070, 4004, "Mt. Tecumseh")),
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
        "cams": [], "patrol": None, "tz": "America/Denver", "opening_day": "2026-11-21",  # est.
        "enabled": False, "stage": "shadow",
    },
    "tamarack": {
        "name": "Tamarack", "region": "Idaho", "pass": "Independent",
        "site": "https://tamarackidaho.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 44.6750, "lon": -116.1450, "elevation_ft": 6500,
        "bands": _bands((44.6700, -116.1220, 4900, "base"), (44.6750, -116.1450, 6500, "mid-mountain"),
                        (44.6780, -116.1550, 7700, "summit")),
        "snotel": ["1016:ID:SNTL", "782:ID:SNTL"], "snotel_label": "Long Valley",
        "cams": [], "patrol": None, "tz": "America/Boise", "opening_day": "2026-12-12",  # est.
        "enabled": False, "stage": "shadow",
    },
    "sun-peaks": {
        "name": "Sun Peaks", "region": "British Columbia", "pass": "Independent",
        "site": "https://www.sunpeaksresort.com", "snow_report_path": None, "grooming_pdf": None,
        "lat": 50.8900, "lon": -119.9000, "elevation_ft": 5800,
        "bands": _bands((50.8840, -119.8860, 4117, "Village"), (50.8900, -119.9000, 5800, "mid-mountain"),
                        (50.9040, -119.9150, 6824, "Tod Mountain")),
        "snotel": [], "snotel_label": None,
        "cams": [], "patrol": None, "tz": "America/Vancouver", "opening_day": "2026-11-21",  # est.
        "enabled": False, "stage": "shadow",
    },
    "mt-baker": {
        "name": "Mt. Baker", "region": "Washington", "pass": "Independent",
        "site": "https://www.mtbaker.us", "snow_report_path": None, "grooming_pdf": None,
        "lat": 48.8600, "lon": -121.6800, "elevation_ft": 4200,
        "bands": _bands((48.8570, -121.6710, 3500, "Heather Meadows"), (48.8600, -121.6800, 4200, "mid-mountain"),
                        (48.8630, -121.6870, 5089, "Panorama Dome")),
        "snotel": ["909:WA:SNTL", "999:WA:SNTL"], "snotel_label": "Wells Creek",
        "cams": [], "patrol": None, "tz": "America/Los_Angeles", "opening_day": "2026-11-27",  # est.
        "enabled": False, "stage": "shadow",
    },
}

SNOW_REPORT_PATH = "/the-mountain/mountain-conditions/snow-and-weather-report.aspx"
CAMS_PATH = "/the-mountain/mountain-conditions/mountain-cams.aspx"


def enabled():
    """Slugs the scheduler runs and the app offers, in display order."""
    env = [s.strip() for s in os.environ.get("RESORTS", "").split(",") if s.strip() in RESORTS]
    return env or [k for k, r in RESORTS.items() if r["enabled"]]


def shadow():
    """Slugs that run only on the Render worker in shadow mode (no sends, not in the app) while their readers
    are checked. See docs/RENDER.md."""
    return [k for k, r in RESORTS.items() if r.get("stage") == "shadow" and not r["enabled"]]


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
    if r["dor_api"]:  # POWDR's open JSON feed (sources/dor.py): snow report and groomed runs
        r["snow_report"] = r["dor_api"] + "/api/v1/dor/drupal/snow-reports"
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
                    "grooming": bool(r["grooming_pdf"] or r["dor_api"])})
    return {"default": DEFAULT, "resorts": out}


def is_static(slug):
    """Nothing to watch for between refreshes: no grooming map and no snow report that's read.
    The scheduler only needs to run these every half hour (refresh + the 7:00 send)."""
    r = get(slug)
    return not r["grooming_pdf"] and not r["snow_report"] and not r["dor_api"]
