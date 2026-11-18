-- 0xSnow: per-resort subscriptions and sends (resort switching).
-- Run once in Neon (snow-desk) BEFORE deploying the resort-switching code.
-- Safe to re-run. Existing subscribers and app subscriptions keep Beaver Creek only.
BEGIN;
ALTER TABLE subscribers        ADD COLUMN IF NOT EXISTS resorts text[] NOT NULL DEFAULT '{beaver-creek}';
ALTER TABLE push_subscriptions ADD COLUMN IF NOT EXISTS resorts text[] NOT NULL DEFAULT '{beaver-creek}';
ALTER TABLE daily_sends        ADD COLUMN IF NOT EXISTS resort  text   NOT NULL DEFAULT 'beaver-creek';
ALTER TABLE daily_sends DROP CONSTRAINT IF EXISTS daily_sends_pkey;
ALTER TABLE daily_sends ADD CONSTRAINT daily_sends_pkey PRIMARY KEY (day, resort);
COMMIT;

-- To undo (only if no other resort has sent yet):
-- BEGIN;
-- ALTER TABLE daily_sends DROP CONSTRAINT daily_sends_pkey;
-- DELETE FROM daily_sends WHERE resort <> 'beaver-creek';
-- ALTER TABLE daily_sends ADD CONSTRAINT daily_sends_pkey PRIMARY KEY (day);
-- ALTER TABLE daily_sends DROP COLUMN resort;
-- ALTER TABLE push_subscriptions DROP COLUMN resorts;
-- ALTER TABLE subscribers DROP COLUMN resorts;
-- COMMIT;
