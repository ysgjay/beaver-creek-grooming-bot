# Snow Desk: Beaver Creek

Every morning it gets the Beaver Creek grooming report, weather, a multi-model snow forecast and the snow stake cam, then sends it out and keeps the history.

- App: **https://snow.0xm.studio** (Today · Calendar · Forecast · Help)
- Telegram: https://t.me/bcskireport
- How it works and why: [docs/SPEC.md](docs/SPEC.md)

## Where it runs (all free tiers, no GitHub at runtime)
| Piece | Service | What it does |
|---|---|---|
| Scheduler | Cloudflare Worker `snow-desk-cron` | Cron every 30 min, 3:00–9:30 a.m. MT, plus 2 p.m.; calls `/api/run` |
| Pipeline | Vercel Python function `api/run.py` | Fetches sources, builds the forecast, saves the archive, sends notifications |
| Archive | Vercel Blob `snow-desk-archive` | JSON and images on a CDN; the app reads them same-origin via rewrites |
| App | Vercel static (`public/`) on `snow.0xm.studio` | Phone-first app, 10 themes, works offline |
| Backup trigger | Vercel cron (daily 5:35 a.m. MT) | In case the Worker is down |

GitHub only stores the code and runs the unit tests. Vercel deploys from it.

## Settings (Vercel project `snow-desk` → Environment Variables)
| Variable | Status |
|---|---|
| `BLOB_READ_WRITE_TOKEN`, `BLOB_PUBLIC_BASE`, `CRON_SECRET` | Set |
| `SEND_ENABLED` | Set to `1` to start sending notifications. Off until then, so the bot can't double-post. |
| `BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram (copy `BOT_TOKEN` from the old GitHub secret) |
| `NTFY_TOPIC` | Free push notifications through the ntfy app. Also add the topic to `public/config.json` so it shows in Help. |
| `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `EMAIL_TO`, `GOOGLE_SHEET_ID` | Email |

To run it by hand: `https://snow-desk-cron.jay-52b.workers.dev/?key=<CRON_SECRET>&force=1`

## Local development
```bash
pip install -r requirements-dev.txt
python -m pytest -q tests
python -m bcbot run --force       # writes into public/data, public/maps (git-ignored)
python -m http.server -d public   # open http://localhost:8000
```
