# Resorts

Chair 0 covers Vail Resorts' five Colorado mountains. Everything per resort lives in
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
The Resend free plan is 100 emails a day across all resorts.

## Turning a resort on or off
Set `enabled` in `resorts.py`, or set the `RESORTS` env var in Vercel (for example
`beaver-creek,vail`), which overrides it without a deploy of new code. Opening days can be overridden
with `OPENING_DAY_<SLUG>` (for example `OPENING_DAY_CRESTED_BUTTE=2027-11-24`).
