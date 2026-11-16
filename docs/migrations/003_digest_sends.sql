-- One combined morning email per subscriber with two or more resorts (bcbot/digest.py).
-- The app also creates this table on first use (CREATE TABLE IF NOT EXISTS), so running this by hand is optional.
CREATE TABLE IF NOT EXISTS digest_sends (
  day      date NOT NULL,
  token    text NOT NULL,
  resorts  text[] NOT NULL,
  pending  text[] NOT NULL DEFAULT '{}',
  sent_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (day, token)
);
