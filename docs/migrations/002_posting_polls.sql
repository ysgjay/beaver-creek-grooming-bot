-- Snow Desk: one-week posting-time observer (bcbot/observer.py). Safe to re-run.
-- Drop when the study is done: DROP TABLE posting_polls;
CREATE TABLE IF NOT EXISTS posting_polls (
  id        bigserial PRIMARY KEY,
  polled_at timestamptz NOT NULL,
  resort    text NOT NULL,
  source    text NOT NULL,          -- 'grooming' or 'snow'
  kind      text NOT NULL,          -- pdf, vail, dor_snow, dor_trails, html
  url       text NOT NULL,
  http      integer,
  ms        integer,
  bytes     integer,
  stamp     text,                   -- the source's own "Updated ..." / map date, when it has one
  fp        text,                   -- fingerprint of the content (PDF bytes, totals, groomed runs)
  detail    jsonb,
  error     text
);
CREATE INDEX IF NOT EXISTS posting_polls_probe ON posting_polls (resort, source, polled_at);
