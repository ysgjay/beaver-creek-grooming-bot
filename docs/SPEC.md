# Beaver Creek Snow Desk: build spec

## Goal
Each morning, send one report with three things in it: the Beaver Creek grooming map, today's weather, and a snow forecast we build ourselves from public data. Send it through channels that don't depend on carrier SMS gateways or Instagram, and keep a public dashboard with the full history.

## What changed from v1
| v1 | v2 |
|---|---|
| Scraped OpenSnow's page with Playwright for 2 numbers | Our own multi-model forecast from public data (no scraping, no browser) |
| Telegram + Instagram (instagrapi, private API, session expiry) | Telegram + ntfy push + email; Instagram removed |
| Posted the map daily even when it hadn't changed (off-season spam) | Sends once per *new* map (PDF hash), up to 3 checks each morning |
| One channel's failure stopped the others | Every source and channel is isolated; failures are listed in the data and the job fails only if the core is missing |
| No history | Every day archived in `data/` and browsable on the dashboard |
| Cron turned off by hand at season end (Mar 30) and must be turned back on each season | Can stay enabled all year: off-season, the map doesn't change, so nothing is sent. The daily data commits also keep GitHub's 60-day inactivity shut-off from triggering. |
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

## Architecture
```
GitHub Actions (cron 5:40 / 6:40 / 7:40 MST, plus manual runs)
  └─ python -m bcbot run
       sources/  openmeteo · nws · snotel · grooming (Lumiplan PDF) · resort (best effort)
       verify    score archived forecasts vs SNOTEL → data/verification.json
       forecast  ratio → bias → blend → range → data/forecasts/<date>.json
       archive   data/days/<date>.json, data/maps/<date>.jpg, data/index.json, data/latest.json
       notify    Telegram · ntfy · email   (only when the map hash is new; DRY_RUN on branches)
  └─ commit data/ → build _site/ (web/ + data/) → deploy to GitHub Pages
```
Data files are plain JSON in the repo, so the history is versioned and needs no database. A map is about 0.5 MB per day, roughly 70 MB per season.

## Delivery channels
| Channel | Cost | Setup | Notes |
|---|---|---|---|
| Telegram `@bcskireport` | free | existing `BOT_TOKEN` | Photo plus caption (≤1024 characters, enforced) |
| **ntfy** push | free | secret `NTFY_TOPIC` (pick a hard-to-guess name) | Replaces SMS. People install the ntfy app and subscribe to the topic. The map comes as an attachment, and tapping opens the dashboard. Powder alerts go here too. |
| Email | free | existing `GMAIL_USER` / `GMAIL_APP_PASSWORD`, plus `EMAIL_TO` and/or `GOOGLE_SHEET_ID` | HTML email with the map inline, recipients in BCC. Any email address found in the sign-up sheet is added. |
| Dashboard | free | Settings → Pages → Source: **GitHub Actions** | `https://ysgjay.github.io/beaver-creek-grooming-bot/`, mobile-first, installable to the home screen |

Real SMS was left out on purpose. Email-to-SMS gateways are shutting down, and Twilio now requires toll-free or 10DLC registration. If SMS is ever needed, a Twilio toll-free number would be one more function in `notify.py`.

## Dashboard
- **Summary**: last 24 hours (resort report, else SNOTEL), next 1–5 days, days 6–10 (each with a range), and the odds of a 6"+ day.
- **10-day bar chart** of the blend, with range whiskers and a tooltip listing each model's number. An expandable table shows every model, day by day, with its learned weight and bias.
- **Grooming map** with tap-to-zoom. **Next 12 hours**: temperature, feels-like, wind, gust, snow, cloud.
- **Forecast vs. what fell**: the day-before forecast against SNOTEL for the last 14 days.
- **Archive** of every day. `#day-YYYY-MM-DD` deep links open that day's map and forecast.
- **Cams**: set repo variable `CAM_URLS` (comma-separated image URLs; the first is the stake cam, which is also archived daily). Branch runs print candidate URLs from the resort site (`python -m bcbot discover`).

## Configuration
Secrets: `BOT_TOKEN`, `NTFY_TOPIC`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `EMAIL_TO`, `GOOGLE_SHEET_ID`.
Variables: `CAM_URLS`, `SIGNUP_FORM_URL`. Tunables are in `bcbot/config.py` (forecast point, models and weights, SNOTEL stations, powder threshold).

## Testing
- `python -m pytest tests`: 19 tests with API-shaped fixtures. They cover the snow ratio, model parsing, the blend, bias and skill, ensemble odds, NWS interval splitting, SNOTEL differencing, verification, resort parsing, PDF rendering, message length, and the full pipeline (sends once per map, dry run, a source outage).
- `ci.yml`: pushing to any non-`main` branch runs the tests and the real pipeline against the live APIs in dry-run mode, then commits the resulting data. Nothing is sent.
