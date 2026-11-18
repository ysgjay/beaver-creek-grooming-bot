-- Snow Desk private database (Neon project snow-desk, spring-heart-11973566, in 0xM's Vercel-managed Neon org), after migrations/001_resorts.sql.
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
CREATE UNIQUE INDEX subscribers_email_lower ON subscribers (lower(email));
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
CREATE TABLE digest_sends (         -- once-a-day claim, per multi-resort subscriber (migrations/003)
  day      date NOT NULL,
  token    text NOT NULL,
  resorts  text[] NOT NULL,
  pending  text[] NOT NULL DEFAULT '{}',
  sent_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (day, token)
);
CREATE TABLE page_views (           -- first-party visit counter (bcbot/stats.py, created on first use)
  day        date    NOT NULL,      -- America/Denver
  vid        text    NOT NULL,      -- random id per browser, no personal data
  resort     text    NOT NULL DEFAULT '',
  view       text    NOT NULL,
  n          integer NOT NULL DEFAULT 1,
  standalone boolean NOT NULL DEFAULT false,
  mobile     boolean NOT NULL DEFAULT false,
  first_at   timestamptz NOT NULL DEFAULT now(),
  last_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (day, vid, resort, view)
);
