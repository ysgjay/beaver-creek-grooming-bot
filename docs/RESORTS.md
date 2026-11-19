# Resorts

0xSnow covers the Colorado and Utah resorts on the Epic and Ikon passes (22). Everything per resort lives in
`bcbot/resorts.py`; after editing it, run `python -m bcbot resorts-json` to refresh the
app's list (`public/resorts.json`, checked by a test).

Sources were checked on 11/15/2026 from a browser on the owner's Mac.

| Resort | Grooming map (Lumiplan) | Snow report | Snow stake | Other cams | SNOTEL | Opening day |
|---|---|---|---|---|---|---|
| Beaver Creek | `beaver-creek-grooming-map.pdf` (sections layout) | `snow-and-weather-report.aspx` | Brown Rice `bcsnowstake2` | Brown Rice | Vail Mountain 842 | 11/25 |
| Vail | `vail-mountain-grooming-map.pdf` (area layout) | `snow-and-weather-report.aspx` | Brown Rice `vailsnowsummit` | Brown Rice | Vail Mountain 842 | 11/13 |
| Breckenridge | none found | `snow-and-weather-report.aspx` | `cache.snow.com/Mtncams/BreckSnowStake.jpg` | Brown Rice | Copper Mountain 415 | 11/6 |
| Keystone | none found | `snow-and-weather-report.aspx` | `cache.snow.com/Mtncams/KeySnowStake.jpg` | Brown Rice | Grizzly Peak 505 | Oct (set 11/1) |
| Crested Butte | none found | `weather-report.aspx` (different slug) | none | Brown Rice | Butte 380 | 11/25 |

### Added 11/15/2026 (free sources only)

| Resort | Pass | Grooming map | Snow report | Cams | SNOTEL | Opening day |
|---|---|---|---|---|---|---|
| Park City | Epic | `park-city-grooming-map.pdf` (two runs per line) | `weather-report.aspx` (Vail platform) | Brown Rice | Thaynes Canyon 814 | 11/20 |
| Telluride | Epic | none | not read | none yet | Alta Lakes 1344 | 11/26 |
| Snowmass | Ikon | none | not read | none yet | North Lost Trail 669 | 11/26 |
| Aspen Mountain | Ikon | none | not read | none yet | Castle Peak 1326 | 11/26 |
| Aspen Highlands | Ikon | none | not read | none yet | Castle Peak 1326 | 12/12 |
| Buttermilk | Ikon | none | not read | none yet | Castle Peak 1326 | 12/12 |
| Steamboat | Ikon | none | not read | none yet | Dry Lake 457 | 11/21 |
| Winter Park | Ikon | none | not read | none yet | Berthoud Summit 335 | 11/13 |
| Copper Mountain | Ikon | `api.coppercolorado.com` trails feed (groomed runs list) | `api.coppercolorado.com/api/v1/dor/drupal/snow-reports` | none yet | Copper Mountain 415 | 11/6 |
| Arapahoe Basin | Ikon | none | not read | none yet | Grizzly Peak 505 | 10/28 |
| Eldora | Ikon | `api.eldora.com` trails feed (groomed runs list) | `api.eldora.com/api/v1/dor/drupal/snow-reports` | none yet | Lake Eldora 564 | 11/13 |
| Deer Valley | Ikon | none | not read | none yet | Thaynes Canyon 814 | 12/5 |
| Solitude | Ikon | none | not read | none yet | Brighton 366 | 11/20 |
| Brighton | Ikon | none | not read | none yet | Brighton 366 | 11/27 |
| Alta | Ikon | none | not read | none yet | Atwater 1308 | 11/20 |
| Snowbird | Ikon | `api.snowbird.com` trails feed (groomed runs list) | `api.snowbird.com/api/v1/dor/drupal/snow-reports` | none yet | Snowbird 766 | 11/27 |
| Snowbasin | Ikon | none | not read | none yet | Ben Lomond Peak 332 (20 km away) | 11/27 |

Resorts whose own report isn't read (`snow_report_path: None`) send at 7:00 with the forecast,
SNOTEL totals and the elevation bands. They have nothing to watch between refreshes
(`resorts.is_static`), so `/api/run` only runs them on the ticks at :00 and :30 (`due` in
`api/run.py`). Opening days are the resorts' announced or projected dates as of 11/15/2026.
Coordinates and band elevations are approximate on-mountain points; check them against the
resort's trail map when tuning a resort. Next steps that stay free: Brown Rice or other cam IDs
for the Ikon resorts, and a snow report reader per resort site.

### Wave 1 (added 11/19/2026, shadow mode)

`"stage": "shadow"` resorts run only on the Render worker in shadow mode (`resorts.shadow()`): no sends, not in the
app, not in the sitemap. Turn one on (`enabled: True`, drop `stage`) after its numbers match the resort's own page for
3 days, and add its pass facts (`EPIC_ACCESS` / `IKON_ACCESS` in `bcbot/facts.py`). Plan:
https://claude.ai/artifact/5yrsn7gYFkyd5QZYqqwf3X

| Resort | Region | Snow report (checked 11/19) | Cams | Snow station | Opening day |
|---|---|---|---|---|---|
| Whistler Blackcomb | British Columbia | `snow-and-weather-report.aspx` | Brown Rice (7) | none (Canada) | 11/20 |
| Heavenly | California | `snow-and-weather-report.aspx` | Brown Rice (4) | Heavenly Valley 518 | 11/20 |
| Northstar | California | `snow-and-weather-report.aspx` | Brown Rice (4) | Truckee #2 834 | 11/20 |
| Kirkwood | California | `snow-and-weather-report.aspx` | Brown Rice (2) | Carson Pass 1067 | 12/4 |
| Stevens Pass | Washington | `weather-report.aspx` | Brown Rice (5) | Stevens Pass 791 | 12/4 |
| Stowe | Vermont | `snow-and-weather-report.aspx` | Brown Rice (3) | none (East) | not announced |
| Okemo | Vermont | `snow-and-weather-report.aspx` | Brown Rice (4) | none | not announced |
| Mount Snow | Vermont | `weather-report.aspx` | Brown Rice (4) | none | not announced |
| Seven Springs | Pennsylvania | `snow-and-weather-report.aspx` | Brown Rice (2) | none | not announced |
| Killington | Vermont | not read (no open feed; site is server-rendered) | none yet | none | open |
| Mt. Bachelor | Oregon | not read yet | none yet | Three Creeks Meadow 815 | 12/4 |

No Wave 1 resort posts a Lumiplan grooming PDF (all 404 on 11/19). Western US resorts use their nearest SNOTEL;
Vermont, Pennsylvania and BC have none, so the report falls back to NOAA snow-center depths (US) or forecast only (BC).
NWS and avalanche lookups are US/Colorado-centric and may log errors for Whistler; shadow mode is where we find out.

### Wave 2 (added 11/19/2026, shadow mode)

Top independents and the Alterra group. None of their own snow reports is read yet: Alterra's mountain report loads
from a keyed feed (mtnpowder.com) that we don't use without Alterra's permission, and the independents need the page
reader. Until then they run like Steamboat and Winter Park: our forecast, the nearest SNOTEL in the US, NOAA snow
depths in the East and forecast only in Canada. Opening days are typical-season estimates; confirm before launch.

| Resort | Region | Pass | Snow station | Opening day (est.) |
|---|---|---|---|---|
| Jackson Hole | Wyoming | Ikon | Phillips Bench 689 | 11/28 |
| Big Sky | Montana | Ikon | Lone Mountain 590 | 11/26 |
| Banff Sunshine | Alberta | Ikon | none (Canada) | 11/07 |
| Lake Louise | Alberta | Ikon | none (Canada) | 11/06 |
| Sun Valley | Idaho | Ikon | Chocolate Gulch 895 | 11/26 |
| Mammoth Mountain | California | Ikon | Virginia Lakes Ridge 846 (51 km) | 11/13 |
| Palisades Tahoe | California | Ikon | Palisades Tahoe 784 | 11/26 |
| Big Bear Mountain | California | Ikon | none (no SNOTEL in SoCal) | 11/20 |
| Crystal Mountain | Washington | Ikon | Morse Lake 642 | 12/04 |
| Tremblant | Quebec | Ikon | none (Canada) | 11/27 |
| Sugarbush | Vermont | Ikon | none | 11/21 |
| Stratton | Vermont | Ikon | none | 11/21 |
| Snowshoe | West Virginia | Ikon | none | 11/26 |

Canadian resorts still show inches and °F; the cm/°C choice is open (see the plan).

### Wave 3 (added 11/19/2026, shadow mode)

Boyne (Sugarloaf, Sunday River, Loon), ORDA (Whiteface, Gore) and the top independents: Taos, Whitefish (SNOTEL
Stryker Basin 1311, 30 km), Grand Targhee (Grand Targhee 1082), Revelstoke, Jay Peak, Loveland (Loveland Basin 602),
Wolf Creek (Wolf Creek Summit 874), Mt. Hood Meadows (Mt Hood Test Site 651) and Big White. Same setup as Wave 2: no
resort page read yet, opening days and independent pass labels are estimates to confirm before launch.

### Wave 4 (added 11/19/2026, shadow mode)

Smaller independents: Powder Mountain (SNOTEL Powder Mountain 1300), Saddleback, Holiday Valley, Bretton Woods,
Smugglers' Notch, Mad River Glen, Cannon, Waterville Valley, Purgatory (Cascade #2 387), Tamarack (Long Valley 1016),
Sun Peaks and Mt. Baker (Wells Creek 909). Same setup as Waves 2 and 3. With Wave 4 all 50 resorts in the plan are
registered: 22 live, 50 in shadow.

## What differs between resorts
- **Grooming map layouts.** Beaver Creek's PDF has "Groomers of the day", "Last night's grooming" and
  "Morning grooming" sections with number and name on alternating lines. Vail's lists runs under area
  headings ("MID-VAIL") with number and name on one line. `sources/grooming.py` reads both.
- **No grooming map** (Breckenridge, Keystone, Crested Butte): the report is snow report, cams and
  forecast. In season it goes out as soon as today's snow report is posted (from 5:00), or at 7:00 if
  the report can't be dated, and at 9:00 at the latest. There's no "season over" detection for these,
  so set their opening day each year and turn them off in spring (`RESORTS` env var).
- **Resort websites block scripts.** vail.com and the other resort sites sit behind Akamai and can
  refuse server requests. The snow report is best-effort: if it can't be read, the report still goes
  out (at 7:00 for map-less resorts). Lumiplan, Brown Rice and cache.snow.com don't block.

## Storage
Beaver Creek keeps its original paths (`data/latest.json`, `maps/<date>.jpg`). Every other resort is
one folder down: `data/vail/latest.json`, `maps/vail/<date>.jpg`, `cams/vail/<date>.jpg`.

## Subscribers
`subscribers.resorts` and `push_subscriptions.resorts` hold each person's picks (existing ones are
Beaver Creek). Each resort's report is its own email or notification, once a day per resort
(`daily_sends` is keyed by day and resort). Every email has a "Choose resorts" link (`/api/resorts`).
The Resend free plan is 100 emails a day across all resorts, so every extra resort a
subscriber picks costs one more email a day. Watch the total as people pick more resorts.

## Turning a resort on or off
Set `enabled` in `resorts.py`, or set the `RESORTS` env var in Vercel (for example
`beaver-creek,vail`), which overrides it without a deploy of new code. Opening days can be overridden
with `OPENING_DAY_<SLUG>` (for example `OPENING_DAY_CRESTED_BUTTE=2027-11-24`).


## POWDR feeds (Copper, Eldora, Snowbird)

These three publish open JSON at `https://api.<resort>.com/api/v1/dor/drupal/snow-reports` and `/trails`. `bcbot/sources/dor.py` reads both: the newest snow report (its `date` is the Updated time) and every winter trail whose `groom_status` isn't `not_groomed`, grouped by sector. They have no map, so the email lists groomed runs and sends once today's snow report is in, like other map-less resorts (9:00 deadline), listing whatever runs are groomed by then.
