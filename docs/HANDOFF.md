# Chair 0: Snow Desk (Colorado Vail resorts): handoff

*Status as of Nov 15, 2026. Everything below is live, merged to `main`, and covered by 36 passing tests.*

## What it is
**Resorts:** Beaver Creek, Vail, Breckenridge, Keystone and Crested Butte, picked from the title in the app. Sources, layouts and what differs per resort: `docs/RESORTS.md`. Database schema: `docs/schema.sql`.

A morning report for Beaver Creek skiers: the grooming map with the named runs, conditions, a multi-model snow forecast, and the snow stake cam.
- **Who gets it:** people who opt in. Delivery is by email and by notifications from the Snow Desk app itself.
- **The app:** a phone-first web app with Today, Calendar, Forecast and Help tabs, at **https://snow.0xm.studio**.
- **History:** every day is archived, and the Calendar shows the season's history.

## Owner preferences (keep these)
- **Layout:** simple and easy to navigate, with little white space and minimal scrolling.
  - **Phone (under 900px):** one column of cards with the bottom tab bar. Desktop work must leave this unchanged.
  - **900 to 1199px:** two columns of cards.
  - **1200px and wider:** full-width, map-led. The grooming map takes the left 62% of Today, tabs move into the top bar, and Today, Calendar and Forecast fit 1440 x 900 without scrolling. The rules are the two `@media` blocks at the end of `public/app.css`; each page's sections carry region classes (`a-groom`, `a-cond`, ...) set in `public/app.js`.
- **Sign-up button (top bar):** `#signup-btn` in `public/index.html` opens the email and notification sign-up in a pop-up (`openSignup` in `public/app.js`, sharing `signupBlocks()` with the Help page). It shows until this browser has submitted the email form (`localStorage.emailSignup`), arrived from a confirmation link, or has a push subscription; `setSignedUp` controls it.
- **Forecast page order:** Next 12 hours runs as a strip across the top (`.hstrip`, one column per hour with snow, peak/mid/base temperature and wind), then 10-day snowfall beside Radar, then a row of detail sections (model votes for all 10 days, every model day by day, how the forecast is built, forecast vs. what fell). At 900px and wider each opens as a pop-up so the page never grows; on phones they expand in place. Selecting a day on the 10-day chart shows each model's call for that day (`dayVotes` in `public/app.js`): a pop-up beside the bar at 900px and wider, a bottom sheet on phones.
- **Radar (Forecast tab):** past hour of NEXRAD and the next 12 hours of HRRR simulated radar, as image tiles from Iowa State's Mesonet (`mesonet.agron.iastate.edu/cache/tile.py`). The map is MapLibre GL (vendored in `public/vendor/`, loaded only when the Forecast tab opens) with OpenFreeMap's keyless Positron style, repainted in the theme's colours. Radar tiles are repainted on a canvas into a one-colour Light to Heavy ramp (`echoStrength`, `recolorRadar` in `public/app.js`). If the style can't load it uses OpenStreetMap image tiles in the same map; if the library or WebGL can't load it falls back to a fixed image-tile grid with the standard radar colours. No API keys. CARTO basemaps were tried and need a key, so don't switch to them.
- **Look:** the Bluebird theme with the Frost finish is the default. Ten themes and five finishes are available from the snowflake button.
- **Charts:**

  | Where | Chart |
  |---|---|
  | Today | Heat strip |
  | Forecast page | Snow stakes (expected snow, plus a hatched "could reach" upper estimate) and model votes |
  | Calendar month | Accumulation |
  | Calendar day | Hourly snow + temperature |

- **Delivery:** opt-in only. Email goes through Resend from `report@snow.0xm.studio`, alongside app notifications. **No Telegram, no Instagram.**
- **Reliability:** reports must go out on time, every time. GitHub Actions cron was dropped because it ran late or skipped runs.
- **Design process:** the 0xM "ideas scout" skill is run before mockups. For this app the owner chose the standard card layout over the scout's alternatives.

## Where everything runs (all free tiers)
Naming (11/15/2026): Chair 0 is the brand (maroon lift-terminal logo); Snow Desk is the product, shown as "Chair 0: Snow Desk" in full and "Snow Desk" where space is short. The email sender stays "Snow Desk". the Vercel project, Blob store, Neon project and Cloudflare Worker all keep their `snow-desk` names, so nothing below moved. Brand sheet and style guide: see the project's Chair 0 brand artifact.

| Piece | Service / ID | Notes |
|---|---|---|
| Code | GitHub `ysgjay/beaver-creek-grooming-bot`, branch `main` | GitHub only stores code and runs tests (`.github/workflows/ci.yml`). Pushing to `main` deploys production. |
| App + functions | Vercel team **0xM Studio** (`team_uluFTokh4wR7JQqU9paCTLf2`), project **snow-desk** (`prj_qwxjIUmKixPpxhQOReFWhcrwICgl`) | Static app in `public/`, Python functions in `api/`. Domain `snow.0xm.studio`; the 0xm.studio DNS is on Vercel. Login protection is on for the vercel.app URLs, not the custom domain. |
| Scheduler | Cloudflare Worker **snow-desk-cron** (account `52b0eaa0…`, `jay-52b.workers.dev`) | Crons (UTC, never overlapping): `*/5 11-13 * * *`, `*/15 9-10,14-17 * * *`, `0 21 * * *`. Calls `POST https://snow.0xm.studio/api/run` with `Bearer CRON_SECRET`, retrying 3 times. Vercel's own daily cron (14:05 UTC) is the backup. |
| Public archive | Vercel Blob **snow-desk-archive** (`store_KpKAjFy5KoVso7GY`, public) | `data/latest.json`, `data/days/<date>.json`, `data/months/<yyyy-mm>.json`, `data/forecasts/<date>.json`, `data/verification.json`, `data/state.json`, `maps/<date>.jpg`, `cams/<date>.jpg`. The app reads these through rewrites in `vercel.json`. |
| Private data | Neon project **snow-desk** (`square-hill-75040371`, us-east-1) | Tables: `subscribers` (double opt-in, token, status, resorts), `push_subscriptions` (resorts), `daily_sends` (once-a-day claim per resort). |
| Email | Resend, domain **snow.0xm.studio** (`8a410eb5-…`, verified) | DNS in Vercel: `resend._domainkey.snow` TXT, `send.snow` MX and TXT, `rsend.snow` CNAME. Free plan: 100 emails a day, about 90 subscribers. |

**DNS gotcha:** `snow.0xm.studio` needs its own ALIAS record (`snow` → `cname.vercel-dns-016.com.`), which now exists. The email records under `snow.*` stop 0xm.studio's catch-all `*` record from covering it. Never delete that ALIAS.

## Vercel environment variables (names only; values live in Vercel)
- **Storage and data:** `BLOB_READ_WRITE_TOKEN`, `BLOB_PUBLIC_BASE`, `DATABASE_URL`
- **Security:** `CRON_SECRET`, which the Cloudflare Worker also holds
- **Email:** `RESEND_API_KEY`, the owner's "Snow" send-only key; `EMAIL_FROM`
- **Sending:** `SEND_ENABLED=1`
- **App notifications:** `VAPID_PRIVATE_KEY` (sensitive; the Web Push signing key, kept only in Vercel). Generate one with `npx web-push generate-vapid-keys` and paste only the private key. The public key is derived from it and served by `GET /api/push`, so the two can't drift. If you rotate it, the app moves existing subscribers to the new key the next time they open it.
- **Optional, with defaults:** `RESORTS` (which resorts run; default all five), `OPENING_DAY` (Beaver Creek, 2026-11-25) and `OPENING_DAY_<SLUG>` for the others, `SEND_TIME` (07:00), `SEND_EARLIEST` (05:00), `SEND_LATEST` (09:00), `REFRESH_HOURS`, `NTFY_TOPIC`, `VAPID_SUBJECT`, `CAM_IDS`, `STAKE_SNAPSHOT_URL`

## Data sources
- **Grooming map:** the Lumiplan PDF `https://grooming.lumiplan.pro/beaver-creek-grooming-map.pdf`, usually posted the evening before. The bot spots a new map because the file's fingerprint changes. Run names ("Groomers of the day", "Last night's grooming", "Morning grooming") and the map's date are read from the PDF's text (`bcbot/sources/grooming.py`).
- **Official snow report:** the beavercreek.com snow report page, embedded `FR.snowReportData` block. Fields read: overnight, 24h, 48h, 7-day, base and season totals, and `LastUpdatedText`, e.g. "Updated November 15, 2026 at 5:34 AM MST".
- **Snow stake and cams:** Brown Rice cams. `https://player.brownrice.com/snapshot/<id>` gives a still image and `/embed/<id>` the live stream. IDs: `bcsnowstake2` (stake), `bcspruce`, `bctalons`, `bcmccoy`, `bcredbuffalo`, `bcvillage`. The stake snapshot is archived each day.
- **Forecast:** Open-Meteo, with temperatures corrected to the 10,476 ft forecast point.
  - Models: GFS, HRRR, NBM, ECMWF (9 km, with the 25 km run as fallback), NAM 3 km, ICON, GEM and UKMO, plus 82 ensemble runs (variations of the models used for ranges and odds). The NWS gridded forecast joins the blend.
  - Ground truth: the Vail Mountain SNOTEL station (842:CO:SNTL).
  - Method, the open-data version of OpenSnow's PEAKS approach:
    1. A temperature-based snow-to-liquid ratio, about 15:1 in the teens, instead of a flat 7:1. Rain or snow is decided by wet-bulb temperature (temperature plus humidity).
    2. Each model's bias and skill learned against SNOTEL over 45 days. The bias starts from the model's record over last winter (`data/priors.json`, worked out once a season from Open-Meteo's historical forecast archive), because coarse models run dry on the upper mountain and early season has too few wet days to learn from.
    3. A weighted blend, then a calibration against Beaver Creek's own reported snowfall (`snow_cal` in `data/verification.json`, between 0.7 and 1.4), plus ensemble ranges and the odds of a 6"+ day. Ensemble runs get the same corrections as the main number.

  - Elevation bands: `config.ELEVATION_BANDS` lists base (8,100 ft), mid (10,200 ft) and peak (11,440 ft), all on the mountain. `data/latest.json` carries `bands`: for each one the label, elevation, `now`, the next 12 `hours` (temp, feels, wind, gust) and 10 `days` (high, low, and `snow_pct`, the share of precipitation falling as snow there). The snow totals stay tied to the 10,476 ft forecast point.
  - The NWS grid only counts for days it covers in full (20+ hours), like the models.

  Details are in `docs/SPEC.md`.

## When the report goes out (`bcbot/main.py`, `send_decision`)
- **Each resort runs on its own** (own state, opening day and once-a-day send), in the resort's time zone. Resorts with no grooming map send as soon as today's snow report is posted (see `docs/RESORTS.md`).
- **Before the resort's opening day:** daily at 7:00 MT, map or not. The subject reads "Opens 11/25".
- **In season:** as soon as both a new grooming map since the last report **and** a resort snow report dated today are confirmed, from 5:00. Checks run every 5 minutes from 4 to 7 a.m., so a report lands within about 5 minutes. If the report date can't be read, the new map alone triggers the send from 7:00. At 9:00, whatever is available goes out. Once the map hasn't changed in 3 days, the season is over and the bot stays quiet.
- **App notifications follow the same rule:** one notification per send. A powder alert (6"+ in 48 hours) is the first line of that notification, never a separate one.
- **Exactly once a day per resort:** the `daily_sends` (day, resort) primary key makes the claim atomic. Nov 15 was marked as covered by a test.
- **Recorded:** each send stores when it went out, why, whether the map was new, and whether the snow report was fresh, in `delivery` on the day record. The app shows "Sent …" and "Snow report 5:34 AM".

## Code map
- `bcbot/main.py`: pipeline and send rules, `run`, `send_test`, CLI
- `bcbot/forecast.py`: snow ratio and blend
- `bcbot/verify.py`: model scoring
- `bcbot/sources/*`: data sources
- `bcbot/store.py`: Blob or local storage
- `bcbot/db.py`: Neon access
- `bcbot/mailer.py`: Resend, with the email HTML
- `bcbot/webpush.py`: RFC 8291/8292 push, checked against the RFC test vector
- `bcbot/notify.py`: email, push and ntfy channels
- `bcbot/report.py`: subject, text and push payload
- `api/run.py`: cron entry, plus `?force=1` and `?test=1`
- `api/subscribe.py`, `api/confirm.py`, `api/unsubscribe.py`: email sign-up, with a confirmation page and RFC 8058 one-click unsubscribe
- `api/push.py`: app notification sign-up; GET returns the public key
- `public/`: `index.html`, `app.js` (views and charts), `app.css`, `themes.css`, `sw.js` (loads fresh when online, cached copy offline; handles push), `config.json` (cams)
- `cloudflare/worker.js`: scheduler
- `tests/test_bcbot.py`: 36 tests, run with `pip install -r requirements-dev.txt && python -m pytest tests`

## Operating it
- **Send a labeled test now:** `https://snow-desk-cron.jay-52b.workers.dev/?key=<CRON_SECRET>&test=1`. It refuses if there are more than 5 email subscribers or more than 5 app subscriptions, and doesn't touch the schedule.
- **Force a refresh:** same URL with `&force=1`.
- **Deploy:** push to `main`. Vercel builds automatically in about 30 seconds.
- **Update only the Worker's code**, which keeps its secret: `PUT /accounts/<id>/workers/scripts/snow-desk-cron/content`.
- **See who's subscribed:** in Neon, `SELECT status, count(*) FROM subscribers GROUP BY 1`.
- **Logs:** Vercel → snow-desk → Logs, and the Cloudflare Worker logs.

## Open items / to do
1. **Old services retired (Nov 15, 2026):**
   - Resend: the "Snow" key the app uses is now send-only, and no key on the team has full access. A copy of that key is still saved as a network secret in the Claude Code cloud "Default" environment; the app doesn't need it.
   - GitHub Actions secrets: `BOT_TOKEN`, `GMAIL_*` and `INSTAGRAM_*` deleted. The only workflow is `ci.yml`, which uses no secrets.
   - The personal cloud environment "beaver-creek-grooming-bot" is archived.
   - Facebook: no longer used, so the old app secret in git history was left as is.
2. **Still to do by hand:** delete the old Telegram bot in @BotFather (`/deletebot`) and the old Telegram channel. Optionally delete the leftover GitHub secrets `GOOGLE_SHEET_ID`, `SMS_RECIPIENTS` and `TWILIO_*`, which nothing uses.
3. **Optional:** add `ADMIN_NTFY_TOPIC` to the Worker to get a phone alert if a trigger fails.
4. **Next season:** set each resort's opening day for 2027 (`opening_day` in `bcbot/resorts.py`, or the `OPENING_DAY*` env vars). Any date before it gets daily pre-season reports, so set it close to when you want those to begin. Also note that the crons are in UTC, so in daylight time the windows shift an hour later in local time.
5. **Ideas parked as GitHub issues #1–3** (label `idea`): a one-sentence verdict at the top of Today, grouping groomed runs by mountain area, and the season shown as a snow pit.
6. **Reference artifacts:**
   - Theme gallery: https://claude.ai/artifact/JKiXvakBJAFPDMGPLnjcTN
   - Bluebird studies (finishes and chart designs): https://claude.ai/artifact/37NRmiA9Ksjsa5oS6afgYN
