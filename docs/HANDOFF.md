# 0xSnow (Colorado and Utah resorts): handoff

*Updated Nov 15, 2026. Deployment follows `main`; changes on a pull-request branch are previews until merged.*

## What it is
**Resorts:** 22 in Colorado and Utah on the Epic and Ikon passes (Beaver Creek, Vail, Breckenridge, Keystone, Crested Butte, Park City, Telluride, the four Aspen mountains, Steamboat, Winter Park, Copper, A-Basin, Eldora, Deer Valley, Solitude, Brighton, Alta, Snowbird, Snowbasin), picked from the title in the app and grouped by state. Sources, layouts and what differs per resort: `docs/RESORTS.md`. Database schema: `docs/schema.sql`.

A morning report for Beaver Creek skiers: the grooming map with the named runs, conditions, a multi-model snow forecast, and the snow stake cam.
- **Who gets it:** people who opt in. Delivery is by email and by notifications from the 0xSnow app itself.
- **The app:** a phone-first web app with Today, Calendar, Forecast and Help tabs, at **https://snow.0xm.studio**.
- **History:** every day is archived, and the Calendar shows the season's history.

## Owner preferences (keep these)
- **Layout:** simple and easy to navigate, with little white space and minimal scrolling.
  - **Phone (under 900px):** one column with custom alpine bottom tabs. Today shows source times and a compact snow outlook before grooming. Forecast leads with snowfall, using horizontally scrollable original stakes with 50 px day slots; hourly conditions follow. These mobile changes were approved Nov 15.
  - **900 to 1199px:** two columns of cards.
  - **1200px and wider:** full-width, map-led. The grooming map takes the left 62% of Today, tabs move into the top bar, and Today, Calendar and Forecast fit 1440 x 900 without scrolling. The rules are the two `@media` blocks at the end of `public/app.css`; each page's sections carry region classes (`a-groom`, `a-cond`, ...) set in `public/app.js`.
- **Day labels:** every day axis shows the weekday over the MM/DD date (`dayTick` and `dayLabels` in `public/app.js`), in the resort's time zone. At 1200px and wider the sign-up link at the bottom of Today is hidden, because the top bar carries the button.
- **Top bar, left side:** the home button (`#home-btn`, the 0xSnow lift-terminal icon) goes to Today. The resort name (`#resort-btn`) opens a themed menu (`openResortMenu` in `public/app.js`) where a resort can be picked or starred. Starred resorts are kept on the device (`localStorage.favResorts`) and shown as tiles (`#favs`, `renderFavs`) with each one's new snow in the last 24 hours, read from that resort's `latest.json`. Favorites have their own slim row below the header, including at 1200px and wider.
- **Sign-up button (top bar):** `#signup-btn` in `public/index.html` opens the email and notification sign-up in a pop-up (`openSignup` in `public/app.js`, sharing `signupBlocks()` with the Help page). It shows until this browser has submitted the email form (`localStorage.emailSignup`), arrived from a confirmation link, or has a push subscription; `setSignedUp` controls it.
- **Forecast page order:** On desktop, upcoming hourly conditions run as a strip across the top (`.hs-wrap`: row labels beside the scrolling `.hstrip`, one column per hour with snow, peak/mid/base temperature and wind), then 10-day snowfall beside Radar, then a row of detail sections (model votes for all 10 days, every model day by day, how the forecast is built, forecast vs. what fell). At 900px and wider each opens as a pop-up so the page never grows; on phones they expand in place. Selecting a day on the 10-day chart shows each model's call for that day (`dayVotes` in `public/app.js`): a pop-up beside the bar at 900px and wider, a bottom sheet on phones. Expected snowfall and the likely range come first; model comparisons expand below. Native dialogs contain keyboard focus, close with Escape, and restore focus to the initiating control.
- **Radar (Forecast tab):** past hour of NEXRAD and the next 12 hours of HRRR simulated radar, as image tiles from Iowa State's Mesonet (`mesonet.agron.iastate.edu/cache/tile.py`). The map is MapLibre GL (vendored in `public/vendor/`, loaded only when the Forecast tab opens) with OpenFreeMap's keyless Positron style, repainted in the theme's colours. Radar tiles are repainted on a canvas into a one-colour Light to Heavy ramp (`echoStrength`, `recolorRadar` in `public/app.js`). If the style can't load it uses OpenStreetMap image tiles in the same map; if the library or WebGL can't load it falls back to a fixed image-tile grid with the standard radar colours. No API keys. CARTO basemaps were tried and need a key, so don't switch to them.
- **Look:** Frosted Snow in light mode and Midnight Ice in dark mode, with the iced lift-terminal logo in the top-left home link. Follow device appearance by default; Help → Appearance offers System, Light, and Dark with a saved per-device preference. The home-screen icon uses the dark navy iced tile via Apple touch icon and manifest PNGs. `public/appearance.js` applies appearance before first paint; `public/dark.css` holds the navy/ice palette and component overrides. Use ink and muted blue for routine controls. All snow/weather charts, calendar heat cells, model details, and radar use blue/ice shades; burgundy is reserved for the logo and small brand accents. `public/frost.css` loads after the base styles and is scoped by `data-brand="frosted-snow"`. `public/frost-surfaces.css` loads last on the app and Snow Audit, adding translucent ice-glass panes, fixed-scale etched detail, and soft highlights to the header, mobile bottom nav, and cards in both appearances. The texture stays behind content with no perimeter mask. Backdrop blur has an opaque fallback; chrome uses a 94% fill and strengthened secondary text. Open forecast popovers lift their containing card above siblings; no overflow clipping is added. Reduced transparency, forced colors, and print restore opaque, untextured panels. The selected tab has a flat ice-blue tint with no bottom edge or underline. Keep the original snowfall bars and their interactions. Logo usage, colors, and typography: `docs/BRAND.md`.
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
Naming (11/18/2026): the app is **0xSnow** everywhere (title, Home Screen label, manifest, emails, push, alerts). It was "Chair 0: Snow Desk" from 11/15 to 11/18. The email FROM name (`EMAIL_FROM`, default in `bcbot/mailer.py`) still says "Snow Desk" until the owner says to change it. The saved appearance key stays `chair0.appearance` so people keep their light/dark choice. The Vercel project, Blob store, Neon project and Cloudflare Worker all keep their `snow-desk` names, so nothing below moved. Brand sheet and style guide: see the project's brand artifact (made under the old Chair 0 name).

| Piece | Service / ID | Notes |
|---|---|---|
| Code | GitHub `ysgjay/beaver-creek-grooming-bot`, branch `main` | GitHub only stores code and runs tests (`.github/workflows/ci.yml`). Pushing to `main` deploys production. |
| App + functions | Vercel team **0xM Studio** (`team_uluFTokh4wR7JQqU9paCTLf2`), project **snow-desk** (`prj_qwxjIUmKixPpxhQOReFWhcrwICgl`) | Static app in `public/`, Python functions in `api/`. Domain `snow.0xm.studio`; the 0xm.studio DNS is on Vercel. Login protection is on for the vercel.app URLs, not the custom domain. |
| Scheduler | Cloudflare Worker **snow-desk-cron** (account `52b0eaa0…`, `jay-52b.workers.dev`) | Crons (UTC, never overlapping): `*/5 11-13 * * *`, `*/15 9-10,14-17 * * *`, `0 21 * * *`. Before Japan launches, replace `0 21` with `*/5 19-21 * * *` and add `*/15 18,22-23,0-1 * * *` and `0 5 * * *` (Japan's morning; 5 crons is the free plan's limit). `cron_window` in `api/run.py` keeps North American resorts to their old hours and Japanese ones to their local morning. Calls `POST https://snow.0xm.studio/api/run` with `Bearer CRON_SECRET`, retrying 3 times. Vercel's own daily cron (14:05 UTC) is the backup. |
| Public archive | Vercel Blob **snow-desk-archive** (`store_KpKAjFy5KoVso7GY`, public) | `data/latest.json`, `data/days/<date>.json`, `data/months/<yyyy-mm>.json`, `data/forecasts/<date>.json`, `data/verification.json`, `data/state.json`, `maps/<date>.jpg`, `cams/<date>.jpg`. The app reads these through rewrites in `vercel.json`. |
| Private data | Neon project **snow-desk** (`spring-heart-11973566`, us-east-1), created from Vercel Storage in team 0xM Studio, so it bills through 0xM's Vercel account (Launch plan). Moved Nov 15, 2026 from the old `square-hill-75040371` project, which billed elsewhere. | Tables: `subscribers` (double opt-in, token, status, resorts), `push_subscriptions` (resorts), `daily_sends` (once-a-day claim per resort). |
| Email | Resend, domain **snow.0xm.studio** (`8a410eb5-…`, verified) | DNS in Vercel: `resend._domainkey.snow` TXT, `send.snow` MX and TXT, `rsend.snow` CNAME. Free plan: 100 emails a day, about 90 subscribers. |

**Render (expansion, 11/19/2026):** a self-hosted Open-Meteo server and a resort worker, set up from `render.yaml`. Details, modes and cut-over steps: `docs/RENDER.md`.

**DNS gotcha:** `snow.0xm.studio` needs its own ALIAS record (`snow` → `cname.vercel-dns-016.com.`), which now exists. The email records under `snow.*` stop 0xm.studio's catch-all `*` record from covering it. Never delete that ALIAS.

## Vercel environment variables (names only; values live in Vercel)
- **Storage and data:** `BLOB_READ_WRITE_TOKEN`, `BLOB_PUBLIC_BASE`, and `SNOWDB_DATABASE_URL` (plus the other `SNOWDB_*` variables), which the Vercel Neon integration manages. The code prefers it over the old `DATABASE_URL`, which can be removed once the old project is deleted.
- **Security:** `CRON_SECRET`, which the Cloudflare Worker also holds
- **Email:** `RESEND_API_KEY`, the owner's "Snow" send-only key; `EMAIL_FROM`
- **Sending:** `SEND_ENABLED=1`
- **App notifications:** `VAPID_PRIVATE_KEY` (sensitive; the Web Push signing key, kept only in Vercel). Generate one with `npx web-push generate-vapid-keys` and paste only the private key. The public key is derived from it and served by `GET /api/push`, so the two can't drift. If you rotate it, the app moves existing subscribers to the new key the next time they open it.
- **Owner alerts:** `ADMIN_NTFY_TOPIC` (optional). When set, `bcbot/alert.py` sends a phone notification through ntfy if a channel fails during the daily send, or if a resort still has no report 30 minutes after `SEND_LATEST`. Without it, the same alerts are logged at error level and appear in Vercel's runtime errors. Set the same topic on the Cloudflare Worker to also hear about failed triggers.
- **Owner stats:** `ADMIN_KEY` (sensitive), the password for the private `/admin` page. Unset or under 12 characters keeps the page locked.
- **Optional, with defaults:** `RESORTS` (which resorts run; default all five), `OPENING_DAY` (Beaver Creek, 2026-11-25) and `OPENING_DAY_<SLUG>` for the others, `SEND_TIME` (07:00), `SEND_EARLIEST` (05:00), `SEND_LATEST` (09:00), `REFRESH_HOURS`, `NTFY_TOPIC`, `VAPID_SUBJECT`, `CAM_IDS`, `STAKE_SNAPSHOT_URL`

## Data sources
- **Grooming map:** the Lumiplan PDF `https://grooming.lumiplan.pro/beaver-creek-grooming-map.pdf`, usually posted the evening before. The bot spots a new map because the file's fingerprint changes. Run names ("Groomers of the day", "Last night's grooming", "Morning grooming") and the map's date are read from the PDF's text (`bcbot/sources/grooming.py`).
- **Official snow report:** the beavercreek.com snow report page, embedded `FR.snowReportData` block. Fields read: overnight, 24h, 48h, 7-day, base and season totals, and `LastUpdatedText`, e.g. "Updated November 15, 2026 at 5:34 AM MST".
- **Snow stake and cams:** Brown Rice cams. `https://player.brownrice.com/snapshot/<id>` gives a still image and `/embed/<id>` the live stream. IDs: `bcsnowstake2` (stake), `bcspruce`, `bctalons`, `bcmccoy`, `bcredbuffalo`, `bcvillage`. The stake snapshot is archived each day.
- **Forecast:** Open-Meteo, with temperatures corrected to the 10,476 ft forecast point.
  - Models: GFS, HRRR, NBM, ECMWF (9 km, with the 25 km run as fallback), ICON, GEM and UKMO, plus 82 ensemble runs (variations of the models used for ranges and odds). The NWS gridded forecast joins the blend.
  - Ground truth: the Vail Mountain SNOTEL station (842:CO:SNTL).
  - Method, the open-data version of OpenSnow's PEAKS approach:
    1. A temperature-based snow-to-liquid ratio, about 15:1 in the teens, instead of a flat 7:1. Rain or snow is decided by wet-bulb temperature (temperature plus humidity).
    2. Each model's bias and skill learned against SNOTEL over 45 days. The bias starts from the model's record over last winter (`data/priors.json`, worked out once a season from Open-Meteo's historical forecast archive), because coarse models run dry on the upper mountain and early season has too few wet days to learn from.
    3. A weighted blend, then a calibration against Beaver Creek's own reported snowfall (`snow_cal` in `data/verification.json`, between 0.7 and 1.4), plus ensemble ranges and the odds of a 6"+ day. Ensemble runs get the same corrections as the main number.

  - Elevation bands: `config.ELEVATION_BANDS` lists base (8,100 ft), mid (10,200 ft) and peak (11,440 ft), all on the mountain. `data/latest.json` carries `bands`: for each one the label, elevation, `now`, the next 12 `hours` (temp, feels, wind, gust) and 10 `days` (high, low, and `snow_pct`, the share of precipitation falling as snow there). The snow totals stay tied to the 10,476 ft forecast point.
  - The NWS grid only counts for days it covers in full (20+ hours), like the models.

  Details are in `docs/SPEC.md`.

## Public report pages and SEO (`/resorts`, `bcbot/pages.py`, `api/page.py`)

- `/resorts` lists every resort; `/resorts/<slug>` is today's report and `/resorts/<slug>/<YYYY-MM-DD>` is an archive post. Each is plain HTML: a short summary from the day's numbers, then the Day Ticket laid out for the web (`bcbot/webreport.py`: section headings, groomed runs as lists, full-width map, two columns on desktop). The email (`mailer.daily_html`) is separate and unchanged.
- Pages read the stored day JSON in Blob. The archive index is `data/<slug>/posts.json`, appended on each daily send; if missing it is rebuilt from the Blob listing of `data/<slug>/days/`.
- `/sitemap.xml` (dynamic) and `public/robots.txt`. Google Search Console and Bing Webmaster Tools are verified with a DNS TXT record on 0xm.studio.
- Each sent report is frozen at `data/<slug>/posts/<date>.json`, so a post (and the resort page once today's report is out) stays the morning report while the day's data keeps refreshing.
- `/resorts/colorado` and `/resorts/utah`: every resort in one table, sorted by new snow. `/resorts/<slug>/guide`: evergreen "how this resort's report works", with posting times from the posting-time study (`data/observer/summary.json`).
- RSS: `/feed.xml` (newest post per resort) and `/resorts/<slug>/feed.xml`.
- IndexNow: each new post pings api.indexnow.org (production only). Key file `public/a156955085e0f01a4754e933d5369d7f.txt` (public by design).
- The service worker skips `/resorts`, `/sitemap.xml`, `/feed.xml` `/robots.txt` and `/llms.txt`.
- Theme: public pages use the app's Frosted Snow / Midnight Ice colors as CSS variables (`pages.THEME`) and load `/appearance.js`, so they follow the app's light/dark choice. Header links back to the app on the same resort; the app's Today and Calendar views link to `/resorts/<slug>/guide` and `/resorts/<slug>`.
- For AI assistants (`bcbot/llm.py`): `/llms.txt`, and a Markdown or JSON twin of each page by adding `.md` / `.json` (`/resorts/vail.md`, `/resorts/vail.json`, `/resorts/vail/2026-11-18.md`, `/resorts/vail/guide.md`, `/resorts/colorado.md`). Each HTML page links its twin with `rel="alternate" type="text/markdown"`; each twin sends a `Link: rel="canonical"` header to the HTML page. robots.txt explicitly welcomes the main AI crawlers.
- Resort facts (`bcbot/facts.py`): opening day, closing day, lift hours, trail map link, passes, pass blackout dates, lift ticket price and lesson types, each with its official source URL and checked date, shown on `/resorts/<slug>/guide` with FAQ JSON-LD. All 22 resorts have passes and blackout dates (shared Epic/Ikon tables) and most have opening and closing days; Beaver Creek and Copper have all 8. How to add or re-check a resort: `docs/RESORT_FACTS.md`; `python -m bcbot.facts` lists what's missing and where to read it. Never rehost resort trail map art; link to it.
- Re-check schedule: closing day every 2 days from 3/1 to 5/31, opening day every 2 days from 9/15 to 11/30, otherwise weekly or monthly (`interval_days`). The `/api/facts` cron (daily 14:30 UTC) fingerprints each source page, writes `data/facts/status.json` and sends an admin alert when a page changed or a fact is overdue. A person (or Claude) then re-reads the source and updates `CURATED` or the shared tables; nothing changes on the page automatically. Facts older than twice their interval show "re-checking".

## Snow Audit (forecast grading, `/audit/<resort>`)
Spec: https://claude.ai/artifact/Sm6FFGCXht3qMBE7hbZbEg (Young's decisions, 11/16/2026). Linked only from Help → About the numbers, on purpose: it is historical data.
- **Live calls:** every full run calls `audit.record` (`bcbot/audit.py`). The first full run of the resort's day (about 2 AM local) freezes each source's raw call (before corrections), the plain average and our blend with its range into Neon `fc_calls`, kind `live`. Later runs never overwrite it (a source missing at 2 AM may still join until 8 AM). It also upserts SNOTEL daily truth and the morning's fresh resort 24-hour report (stored on the day the snow fell, the day before the report) into `fc_truth`, and the blend's learned corrections into `fc_weights`. It never fails a run.
- **Replay:** `/api/audit` runs every 10 minutes (Vercel cron, `CRON_SECRET`). Each tick rebuilds a few resort-months of past winters (Nov to Apr from 11/2024) from Open-Meteo Previous Runs (`precipitation_previous_day1..7`, HRRR skipped) plus SNOTEL, kind `replay`; progress is in `fc_backfill`. About 300 resort-months, so roughly two days for all 22 resorts. Then it rebuilds `data/audit/<slug>.json` (hourly) and `data/audit/all.json`.
- **Grading:** snow against the resort report, water against the SNOTEL gauge, days 0 to 9, live and replay kept apart. Letter grades (A to D vs the plain average, 8+ days) come from live calls only; replay only gives a hint. Grades don't change the blend yet (shadow mode is the next step in the accuracy spec).
- **Public reads:** `/api/audit?resort=<slug>&log=1` (the Log drawer) and `&format=csv` (filters: `kind`, `source`, `lead`, `from`, `to`).
- **Tables:** `docs/migrations/004_audit.sql`, created automatically on first use. A local Postgres test runs when `AUDIT_TEST_DB` is set.

## Owner stats (`/admin`, also `/stats`)
Private page for the owner: email and app sign-ups by day, per-resort subscribers, visitors per day, tabs used, phone and Home Screen share, latest sign-ups (addresses shortened). It asks for `ADMIN_KEY` once and keeps it on that device; Lock forgets it. Not linked anywhere, `noindex`.
- **Visits:** Vercel Web Analytics is off (it can bill on the Pro team), so the app counts its own views: `countView` in `public/app.js` posts `{random browser id, tab, resort}` to `/api/hit` once per tab and resort per page load, only on snow.0xm.studio. No cookies, IPs or user agents are stored. Table `page_views` in Neon (created on first use, `bcbot/stats.py`), one row per Mountain Time day, visitor, resort and tab. Opening `/admin` turns counting off on that device ("Don't count my visits").
- **API:** `GET /api/stats` with `Authorization: Bearer <ADMIN_KEY>`.

## When the report goes out (`bcbot/main.py`, `send_decision`)
- **Each resort runs on its own** (own state, opening day and once-a-day send), in the resort's time zone. Resorts with no grooming map send as soon as today's snow report is posted (see `docs/RESORTS.md`).
- **Before the resort's opening day:** daily at 7:00 MT, map or not. The subject reads "Opens 11/25".
- **In season:** as soon as both a new grooming map since the last report **and** a resort snow report dated today are confirmed, from 5:00. Checks run every 5 minutes from 4 to 7 a.m., so a report lands within about 5 minutes. If the report date can't be read, the new map alone triggers the send from 7:00. At 9:00, whatever is available goes out. Once the map hasn't changed in 3 days, the season is over and the bot stays quiet.
- **App notifications follow the same rule:** one notification per send. A powder alert (6"+ in 48 hours) is the first line of that notification, never a separate one.
- **Exactly once a day per resort:** the `daily_sends` (day, resort) primary key makes the claim atomic. Nov 15 was marked as covered by a test.
- **Recorded:** each send stores when it went out, why, whether the map was new, and whether the snow report was fresh, in `delivery` on the day record. The app labels the saved report time separately from the resort snow and forecast source times. Delivery metadata remains in the archive.

## Code map
- `public/report-ui.js`: tested presentation helpers for resort-local timestamps, map age, current forecast hours, source labels, and complete five-day outlooks. Never infer a map date from its download filename or treat missing forecast days as zero.
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
- `api/hit.py`, `api/stats.py`, `bcbot/stats.py`, `public/admin.*`: visit counter and the owner stats page
- `public/`: `index.html`, `app.js` (views and charts), `app.css`, `themes.css`, `frost.css` (brand layer), `dark.css` (Midnight Ice palette), `frost-surfaces.css` (shared ice-glass material for header, bottom nav, and cards; loads last on the app and Snow Audit), `brand/` (logos, cached frost texture, and licensed local fonts), `sw.js` (loads fresh when online, cached copy offline; handles push), `config.json` (cams)
- `cloudflare/worker.js`: scheduler
- `tests/test_bcbot.py`: run with `pip install -r requirements-dev.txt && python -m pytest tests`

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
3. **Alerts:** set `ADMIN_NTFY_TOPIC` in Vercel and on the Worker (same topic), then subscribe to it in the ntfy app.
4. **Next season:** set each resort's opening day for 2027 (`opening_day` in `bcbot/resorts.py`, or the `OPENING_DAY*` env vars). Any date before it gets daily pre-season reports, so set it close to when you want those to begin. Also note that the crons are in UTC, so in daylight time the windows shift an hour later in local time.
5. **Ideas parked as GitHub issues #1–3** (label `idea`): a one-sentence verdict at the top of Today, grouping groomed runs by mountain area, and the season shown as a snow pit.
6. **Reference artifacts:**
   - Theme gallery: https://claude.ai/artifact/JKiXvakBJAFPDMGPLnjcTN
   - Bluebird studies (finishes and chart designs): https://claude.ai/artifact/37NRmiA9Ksjsa5oS6afgYN
