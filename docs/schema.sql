-- Snow Desk private database (Neon project snow-desk), after migrations/001_resorts.sql.
CREATE TABLE subscribers (
  id              bigserial PRIMARY KEY,
  email           text NOT NULL,
  status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'unsubscribed')),
  token           text NOT NULL UNIQUE,
  resorts         text[] NOT NULL DEFAULT '{beaver-creek}',   -- slugs from bcbot/resorts.py
  created_at      timestamptz NOT NULL DEFAULT now(),
  confirm_sent_at timestamptz,
  confirmed_at    timestamptz,
  unsubscribed_at timestamptz
);
CREATE TABLE push_subscriptions (
  id           bigserial PRIMARY KEY,
  endpoint     text NOT NULL UNIQUE,
  p256dh       text NOT NULL,
  auth         text NOT NULL,
  resorts      text[] NOT NULL DEFAULT '{beaver-creek}',
  created_at   timestamptz NOT NULL DEFAULT now(),
  last_sent_at timestamptz,
  failures     integer NOT NULL DEFAULT 0
);
CREATE TABLE daily_sends (          -- once-a-day claim, per resort
  day        date NOT NULL,
  resort     text NOT NULL DEFAULT 'beaver-creek',
  reason     text NOT NULL,
  claimed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (day, resort)
);
CREATE TABLE app_secrets (
  name       text PRIMARY KEY,
  value      text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
