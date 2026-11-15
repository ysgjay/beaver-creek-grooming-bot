# Beaver Creek Snow Desk: build spec

## Goal
Each morning, send one report with three things in it: the Beaver Creek grooming map, today's weather, and a snow forecast we build ourselves from public data. Send it through channels that don't depend on carrier SMS gateways or Instagram, and keep a public dashboard with the full history.

## What changed from v1
| v1 | now |
|---|---|
| Scraped OpenSnow's page with Playwright for 2 numbers | Our own multi-model forecast from public data (no scraping, no browser) |
| Telegram + Instagram (instagrapi, private API, session expiry) | Opt-in email (Resend) and app notifications (Web Push); Telegram and Instagram removed |
| Posted the map daily even when it hadn't changed (off-season spam) | Sends once per *new* map (PDF hash), up to 3 checks each morning |
| One channel's failure stopped the others | Every source and channel is isolated; failures are listed in the data and the job fails only if the core is missing |
| No history | Every day archived in Vercel Blob and browsable in the app's calendar and feed |
| Map image only | Groomed run names parsed from the PDF and included in the message |
| GitHub Actions cron, turned off by hand at season end (Mar 30) | A Cloudflare Worker cron that can stay on all year: off-season, the map doesn't change, so nothing is sent |
| Facebook app secret committed in `get_facebook_token.py` | File removed. **The secret is still in git history, so reset it in the Meta developer console.** |

## How OpenSnow makes its forecasts, and what we copy
OpenSnow's forecasts come from **PEAKS**, its machine-learning model. PEAKS 2.0 (Oct 2026) takes a low-resolution forecast from the public global models and does two things to it:
1. **Downscaling**: it re-creates the forecast at high resolution, so values change with terrain instead of every ~15 miles.
2. **Bias correction**: it was trained on historical station observations, so it learns where each model is usually too wet, too dry, too warm or too windy.

OpenSnow then blends PEAKS with the other models, weighted heavily toward PEAKS. Its training data comes from NOAA, NCAR and ECMWF. Sources: [opensnow.com/peaks](https://opensnow.com/peaks), [PEAKS 2.0 announcement](https://opensnow.com/news/post/new-peaks-20), [support: PEAKS model](https://support.opensnow.com/feature-guides/peaks-model).

We can't copy the trained neural net. What we can copy is the recipe, built from the same open inputs:

| OpenSnow step | Our version |
|---|---|
| Public global and regional models | Open-Meteo point data for GFS, HRRR (3 km), NOAA NBM, ECMWF, ICON, GEM and UKMO, plus the NWS forecasters' 2.5 km gridded snowfall |
| Downscale to the terrain | Open-Meteo's `elevation=3193` lapse-rate correction to the 10,476 ft forecast point (the same point OpenSnow uses for Beaver Creek). NWS and HRRR are already high-resolution. |
| Snow amount | Our own temperature-dependent snow-to-liquid ratio (8:1 near freezing, ~17:1 at 12°F). Open-Meteo's `snowfall` field assumes ~7:1, which under-forecasts Colorado powder by about half. |
| Bias correction from stations | Every forecast is archived. Each day, each model's liquid precip is scored against the **Vail Mountain SNOTEL** gauge (10,300 ft, ~6 mi away; Copper Mountain as fallback). Over a 45-day window: `bias_ratio = observed / forecast` (clamped 0.6–1.6), and `skill = median MAE / model MAE` (clamped 0.5–2). |
| Weighted blend | Prior weights by lead time (HRRR/NBM/NWS lead for days 1–2, ECMWF/NBM after that) × learned skill, applied to the bias-corrected values |
| Forecast range | 10th–90th percentile of 82 ensemble members (GFS 31 + ECMWF 51), plus "chance of a 6"+ day" as the share of members with one |

Possible upgrades once a season of archive exists:
- Fit the snow ratio to observations (SNOTEL depth change ÷ precip).
- Learn the weights by lead time.
- Add CAIC stations and the resort's reported 24-hour totals as extra truth.

## Architecture (v3: Vercel + Cloudflare)
```
Cloudflare Worker cron (free)  every 30 min 3:00-9:30 a.m. MT, and 2 p.m.
  └─ POST https://snow.0xm.studio/api/run   (Bearer CRON_SECRET)
       Vercel Python function (bcbot)
         1. cheap check: grooming PDF hash vs last run. If the map is unchanged, the forecast
            is under 6 h old and it's the same day, exit with no writes.
         2. sources: open-meteo, ensemble, NWS, SNOTEL, resort report, stake snapshot
         3. verify -> forecast -> archive to Vercel Blob -> notify (if SEND_ENABLED=1)
Vercel static app (public/) on snow.0xm.studio
  /data/*, /maps/*, /cams/*  rewritten to the Blob CDN (same origin, cached)
Vercel cron: daily backup trigger at 5:35 a.m. MT
```
Why this shape:
- **It scales.** Every page view is static files and CDN-cached JSON. No database or function runs per visitor, so 10 or 10,000 skiers cost the same.
- **It stays inside free tiers.** About 2 full runs a day, roughly 15 Blob writes, and around 25 tiny Worker invocations.
- **It doesn't depend on GitHub at runtime.** GitHub only holds the code. Vercel builds from it.
- **No database.** Month files (`data/months/YYYY-MM.json`) hold one compact row per day, which is everything the calendar, week/month stats and grooming feed need. SNOTEL back-fills snowfall for days the bot never ran.

## Blob layout
`data/latest.json`, `data/days/<date>.json`, `data/months/<yyyy-mm>.json`, `data/forecasts/<date>.json`, `data/verification.json`, `data/state.json`, `maps/<date>.jpg`, `cams/<date>.jpg`

## App (public/)
- **Today** (the default): status, snow (24h, base, season), the grooming report (map with zoom, plus the named runs), weather now and the next 12 hours, a 5-day forecast chart with a Full forecast button, and the snow stake with the other resort cams.
- **Calendar**: Day, Week and Month views. Month is a heat-map calendar of new snow each morning with grooming-report dots, and tiles for snowfall in the month, snowiest day, report count and season to date. Week shows daily bars, the weekly total and the week's reports. Day shows that day's map, runs and stake photo. Below all three is a feed of every grooming report, newest first, with "Show earlier reports".
- **Forecast**: a 10-day chart with ensemble ranges, day-by-day range bars, hourly table, a table of every model, how the forecast is built, and forecast vs. what fell.
- **Help**: Ski Patrol emergency (970) 754-6911 as text with Call and Copy buttons, what to tell patrol, the non-emergency line (970) 754-6610, Security, 911, and how to subscribe. Numbers are from Beaver Creek's Safety on the Mountain page.
- **Charts**: Today has a heat strip (ten days in one row). The Forecast page has snow stakes: solid snow is expected, the hatched zone up to a dashed cap is how much more it could reach, and a notch marks the low end. Below that, model votes show one dot per model with the blend as a bar. Calendar month shows snowfall accumulated so far, with the forecast continuing as a dashed line. Calendar day shows hourly snow bars under a temperature line.
- **Look**: Bluebird colors with the Frost finish by default.
- **Themes**: 10 (Corduroy, Trail Sign, Patrol, Alpenglow, Beacon, Lift Ticket, Night Cat, Amber Lens, Bluebird, Glade), each passing WCAG AA. Until someone picks one, the app follows the phone's light or dark setting.
- **Offline**: a service worker keeps the app and the last report, so it opens on a chairlift with no signal.

## Delivery channels
| Channel | Cost | How people join | Notes |
|---|---|---|---|
| Email (Resend) | free up to 100 emails a day | Sign up in Help, then confirm by email | From `report@snow.0xm.studio`, a verified subdomain with its own reputation. Each person gets their own copy with one-click unsubscribe (RFC 8058 headers plus a link). The subscriber list is in a private Neon database. |
| App notifications (Web Push) | free | "Turn on" in Help | Built on RFC 8291 encryption and VAPID (RFC 8292), checked against the RFC test vector. The signing keys are created on the server and kept in the database. Expired subscriptions are removed automatically. Powder alerts use this channel only. |
| ntfy | free | Optional `NTFY_TOPIC` | Kept for anyone who prefers it |

Telegram and Instagram were removed: email plus app notifications reach everyone without a third-party account.

## Configuration and testing
See README.md for environment variables. `python -m pytest tests`: 23 tests cover the forecast math, parsers, verification, Blob protocol headers, and the pipeline's skip, refresh, send-once and outage behavior.
