-- Snow Audit tables (bcbot/audit.py SCHEMA; the app creates them on first run).
CREATE TABLE IF NOT EXISTS fc_calls (
  resort     text NOT NULL,
  source     text NOT NULL,          -- Open-Meteo model id, 'nws', 'blend' or 'mean'
  issued     date NOT NULL,          -- resort-local day the call was made
  valid      date NOT NULL,          -- the day it is about
  lead       smallint NOT NULL,      -- valid - issued, in days
  kind       text NOT NULL,          -- 'live' or 'replay'
  liquid     real,                   -- inches of water
  snow       real,                   -- inches of snow (our snow ratio, before any correction; blend: as sent)
  low        real,                   -- blend only: the range that went out
  high       real,
  issued_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (resort, source, issued, valid, kind)
);
CREATE INDEX IF NOT EXISTS fc_calls_valid ON fc_calls (resort, valid);
CREATE TABLE IF NOT EXISTS fc_truth (
  resort           text NOT NULL,
  valid            date NOT NULL,
  station          text,
  snotel_liquid    real,
  snotel_swe       real,             -- snow water equivalent change
  snotel_depth     real,             -- snow depth change
  resort_snow      real,             -- resort's 24 h report, posted the morning after `valid`
  resort_updated   text,
  updated_at       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (resort, valid)
);
CREATE TABLE IF NOT EXISTS fc_weights (   -- the blend's learned corrections, once a day
  resort  text NOT NULL,
  day     date NOT NULL,
  model   text NOT NULL,
  skill   real,
  short   real,
  mid     real,
  long    real,
  PRIMARY KEY (resort, day, model)
);
CREATE TABLE IF NOT EXISTS fc_backfill (  -- replay progress, one row per resort and month
  resort      text NOT NULL,
  month       text NOT NULL,              -- yyyy-mm
  covered_to  date,
  rows        integer,
  error       text,
  tried_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (resort, month)
);
CREATE TABLE IF NOT EXISTS fc_runs (      -- job log, so a missing model is logged, never silent
  id      bigserial PRIMARY KEY,
  at      timestamptz NOT NULL DEFAULT now(),
  resort  text,
  job     text NOT NULL,
  ok      boolean NOT NULL,
  detail  text
);
