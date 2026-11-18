# Posting-time study (11/16 to 11/23/2026)

One week of watching when each resort posts the day's grooming report and official snow totals,
to tune when 0xSnow sends.

- **Code:** `bcbot/observer.py`, called by `/api/observe` (Vercel cron, every 5 minutes, team 0xM Studio).
- **Cadence:** every 5 minutes from 3 to 10 a.m. resort time, every 15 minutes the rest of the day
  (Lumiplan maps are often posted the evening before). Turns itself off after `OBSERVE_UNTIL` (default 2026-11-23).
- **Sources:** Lumiplan PDFs (Beaver Creek, Vail, Park City), the Vail-platform snow report pages
  (`LastUpdatedText`), the POWDR JSON feeds (Copper, Eldora, Snowbird), and the most likely public
  report page for every other resort (`LIKELY` in the module; a wrong URL shows up as its HTTP status).
- **Stored:** one row per probe per poll in Neon `posting_polls` (0xM database). The table is created on first run;
  `docs/migrations/002_posting_polls.sql` is the same schema.
- **Summary:** `/data/observer/summary.json` (every change seen, in Mountain time, plus each probe's latest status).
- **Safe:** read-only. It doesn't import the mailer, push or send pipeline (a test checks), so it can't reach subscribers.

When the week is done: remove the `/api/observe` cron from `vercel.json`, then `DROP TABLE posting_polls;`.
