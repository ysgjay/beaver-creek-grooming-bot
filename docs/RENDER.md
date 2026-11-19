# Render: resort worker and self-hosted forecast

Part of the US and Canada expansion plan (Young, 11/19/2026). Everything here lives in the
**0xM Studio** Render workspace. Never create anything in the Brassie workspace.

Blueprint: `render.yaml` at the repo root. Region oregon (close to Open-Meteo's data in AWS us-west-2).

| Service | Type | Plan | What it does |
|---|---|---|---|
| `snow-meteo` | Private service, Docker image `ghcr.io/open-meteo/open-meteo:1.8.0` | Standard (2 GB) + 40 GB disk | Our own Open-Meteo API. Reads model files on demand from Open-Meteo's open data on AWS (`REMOTE_DATA_DIRECTORY`) and caches them on the disk (`CACHE_SIZE=30GB`), so it only holds the models and places we ask for. No public URL; only other Render services reach it. |
| `snow-worker` | Background worker, Python | Starter | `python -m bcbot.worker`: the resort readers and daily pipeline with no 60 s limit. Same UTC ticks as the Cloudflare Worker. |

Rough cost: Standard $25 + disk 40 GB x $0.25 = $10 + Starter worker $7, about **$42/month**.

## How the app uses the forecast server
`bcbot/sources/openmeteo.py`: when `OPEN_METEO_URL` (or `OPEN_METEO_HOST`, which the blueprint
sets) is present, forecast and ensemble calls go to our server first and fall back to the public API
if it errors or refuses a model. History and previous-runs calls (priors once a season, Snow Audit
replay) stay on the public API. Vercel does not set these variables, so the app on Vercel is unchanged.

Licence notes: the weather data is CC-BY 4.0, so keep "Weather data by Open-Meteo.com" credit in the
app. The server code is AGPL; we run it unmodified.

## Worker modes (`WORKER_MODE`)
- **shadow** (default): reads the live Blob archive (`BLOB_PUBLIC_BASE`), writes only to a local
  folder (`store.ShadowStore`), never sends, never touches Neon. Safe beside Vercel. Check the logs
  for `tick (shadow): N resorts ... with problems [...]`.
- **live**: writes the real archive and sends. Before switching: copy `BLOB_READ_WRITE_TOKEN`,
  `SNOWDB_DATABASE_URL`, `RESEND_API_KEY`, `VAPID_PRIVATE_KEY` (and `ADMIN_NTFY_TOPIC`, `EMAIL_FROM`,
  `SEND_ENABLED=1`) from Vercel, then turn the Cloudflare trigger's crons off so only one scheduler
  drives the pipeline. Vercel's 14:05 UTC backup cron can stay: the `daily_sends` claim stops a double send.

Smoke test: `python -m bcbot.worker --once` (one forced tick of every enabled resort).

## Setup steps
1. Young creates the 0xM Studio workspace (billing card = 0xM) and reconnects the Render connector to it.
2. Claude applies the blueprint from `main` (Render → Blueprints → New, or the connector).
3. Set `BLOB_PUBLIC_BASE` on `snow-worker` (same value as Vercel).
4. Watch a few shadow ticks; compare `latest.json` from the shadow run with the live one.
5. Cut over to live (above) once the readers and forecast match.
