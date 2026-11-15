# Beaver Creek Snow Desk

Every morning this bot sends the Beaver Creek grooming map with today's weather and a multi-model snow forecast. It sends to Telegram, to ntfy push notifications and by email, and keeps a mobile dashboard with the full history.

- Dashboard: https://ysgjay.github.io/beaver-creek-grooming-bot/
- Telegram: https://t.me/bcskireport
- Design, data sources and how the forecast works: [docs/SPEC.md](docs/SPEC.md)

## Run locally
```bash
pip install -r requirements.txt
python -m pytest -q tests
DRY_RUN=1 python -m bcbot run     # fetch everything and print the message; sends nothing
python -m bcbot site              # build the dashboard into _site/
python -m http.server -d _site    # then open http://localhost:8000
```

## One-time setup
1. **Reset the Facebook app secret** that was committed in the old `get_facebook_token.py` (it's still in git history).
2. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
3. Actions tab: turn the workflow back on (it was turned off by hand on Mar 30). It can stay on all year, because it only sends when the grooming map changes.
4. Secrets (Settings → Secrets and variables → Actions):
   - `BOT_TOKEN`: already set.
   - `NTFY_TOPIC`: a hard-to-guess topic name, e.g. `bc-groom-7h2k`.
   - `GMAIL_USER` and `GMAIL_APP_PASSWORD`: already set.
   - `EMAIL_TO` and/or `GOOGLE_SHEET_ID`: who gets the email.
5. Optional variables: `CAM_URLS` (comma-separated cam image URLs) and `SIGNUP_FORM_URL`.

The report goes out once per new grooming map. To send one on demand, open Actions → Daily grooming report → Run workflow and tick "force send".
