# Snow Desk: Beaver Creek

Every morning at 7:00 it sends the Beaver Creek grooming report, weather, a multi-model snow forecast and the snow stake cam to people who opted in, by email and app notification, and keeps the history.

- App: **https://snow.0xm.studio** (Today · Calendar · Forecast · Help)
- How it works and why: [docs/SPEC.md](docs/SPEC.md)

## Where it runs (all free tiers, no GitHub at runtime)
| Piece | Service | What it does |
|---|---|---|
| Scheduler | Cloudflare Worker `snow-desk-cron` | Cron every 15 min from 2 to 10 a.m. MT, plus 2 p.m. Each call retries 3 times, and failures can alert your phone (`ADMIN_NTFY_TOPIC`). |
| Pipeline | Vercel Python function `api/run.py` | Fetches sources, builds the forecast, saves the archive, sends notifications |
| Archive | Vercel Blob `snow-desk-archive` | JSON and images on a CDN; the app reads them same-origin via rewrites |
| Subscribers | Neon Postgres `snow-desk` (private) | Opted-in emails and app push subscriptions (the push signing key is a Vercel env var) |
| Email | Resend, from `report@snow.0xm.studio` | Its own subdomain (SPF, DKIM, bounce handling verified), so its reputation is separate from 0xm.studio mail |
| App | Vercel static (`public/`) on `snow.0xm.studio` | Phone-first app, 10 themes, works offline |
| Backup trigger | Vercel cron (daily 7:05 a.m. MST) | In case the Worker is down. Sending can never happen twice. |

GitHub only stores the code and runs the unit tests. Vercel deploys from it.

## When the report goes out
- **Before opening day** (`OPENING_DAY`, Nov 25): every morning at **7:00 a.m.** MT, with the forecast and stake cam, map or not.
- **In season:** **as soon as both are confirmed**, from 5:00 a.m.:
  1. a new grooming map since the last report (the Lumiplan PDF's fingerprint changed; it's usually posted the evening before), and
  2. the resort's snow report dated today (its `LastUpdatedText`, e.g. "Updated November 15, 2026 at 5:34 AM MST").

  The bot checks every 5 minutes from 4 to 7 a.m., so the report lands within about 5 minutes of both being published.
- **Fallbacks:** if the snow report ever carries no readable date, the new map alone triggers the send from 7:00. At 9:00, whatever is available goes out. After the season, once the map hasn't changed in 3 days, it goes quiet.
- **Exactly once a day:** the database records a claim on each day's send, so retries, the backup trigger, or two triggers at the same moment can't send twice.
- **Delivery stamp:** each report records when and why it was sent, and the app shows "Sent 5:41" and "Snow report 5:34 AM".

To send a labeled test now: `https://snow-desk-cron.jay-52b.workers.dev/?key=<CRON_SECRET>&test=1` (it refuses once there are more than 5 subscribers).

## Who gets it
- **Email:** people sign up on the app's Help page and must confirm with the link in their inbox (double opt-in). Every report is sent to each person individually, with a one-tap unsubscribe link and the standard one-click unsubscribe headers that Gmail and Apple Mail show as an Unsubscribe button. Resend's free plan allows 100 emails a day, roughly 90 subscribers.
- **App notifications:** "Turn on" on the Help page uses Web Push from the app itself, so nobody needs a separate app. It works on Android and desktop browsers, and on iPhone after Snow Desk is added to the Home Screen (iOS 16.4+). Powder alerts go only to app notifications.

## Settings (Vercel project `snow-desk` → Environment Variables)
| Variable | Status |
|---|---|
| `BLOB_READ_WRITE_TOKEN`, `BLOB_PUBLIC_BASE`, `CRON_SECRET`, `DATABASE_URL`, `EMAIL_FROM`, `SEND_ENABLED=1` | Set |
| `RESEND_API_KEY` | **Add this**: your Resend "Snow" key (sending access) |
| `NTFY_TOPIC` | Optional, for anyone who prefers the ntfy app |

To run it by hand: `https://snow-desk-cron.jay-52b.workers.dev/?key=<CRON_SECRET>&force=1`

## Local development
```bash
pip install -r requirements-dev.txt
python -m pytest -q tests
python -m bcbot run --force       # writes into public/data, public/maps (git-ignored)
python -m http.server -d public   # open http://localhost:8000
```
