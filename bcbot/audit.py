"""Snow Audit: a permanent record of every forecast call and what actually fell, and the
report card built from it (the /audit page).

Spec: https://claude.ai/artifact/Sm6FFGCXht3qMBE7hbZbEg (decided by Young, 11/16/2026).

Two kinds of calls are kept, never mixed in a letter grade:
  live    frozen from the first full run of each resort's day (about 2 AM local), before any
          correction for the models (`raw`), plus our blend as it went out. Never overwritten.
  replay  rebuilt from Open-Meteo's Previous Runs archive (what each model said 1 to 7 days
          before the day) for past winters. A head start for the record, graded on water only
          (there is no archive of resort snow reports).

Truth, per resort and day (the day snow falls, keyed by its date):
  snotel_liquid   gauge precipitation increase, midnight to midnight (SNOTEL daily)
  resort_snow     the resort's own 24-hour report, posted the next morning (fresh reports only)

Neon tables (0xM database): fc_calls, fc_truth, fc_weights, fc_backfill, fc_runs.
Same SQL as docs/migrations/004_audit.sql (docs/ isn't deployed with the functions).

The page reads data/audit/<slug>.json (one per resort) and data/audit/all.json (pooled),
rebuilt by /api/audit's cron job. The raw log and CSV come from /api/audit?resort=...
"""
import logging
import time
from datetime import date, datetime, timedelta

from . import config, resorts

log = logging.getLogger(__name__)

SCHEMA = """
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
"""

BLEND, MEAN = "blend", "mean"
LEADS = range(10)
GROUPS = {"short": (0, 1), "mid": (2, 4), "long": (5, 9)}
# A day counts toward the average miss when the call or the truth reached this much.
COUNT_AT = {"snow": 1.0, "water": 0.05}
# Storm lines: snow 2" and 6" (the powder line); water about the same storms.
STORM = {"snow": (2.0, 6.0), "water": (0.15, 0.4)}
MIN_GRADE_DAYS = 8
# Replay: the winters to rebuild (Previous Runs holds most models from 01/2024).
REPLAY_FIRST = date(2024, 11, 1)
REPLAY_MONTHS = (11, 12, 1, 2, 3, 4)
REPLAY_LEADS = range(1, 8)
# The archive's "HRRR" is GFS stitched in, so it is not replayed.
NO_REPLAY = {"gfs_hrrr"}
# Before this local hour a missing source can still join the day's frozen call.
FREEZE_UNTIL_HOUR = 8
# A replay month that failed (or got no SNOTEL readings) is tried again after this long.
RETRY_HOURS = 2


def label(source):
    if source == BLEND:
        return "0xSnow blend"
    if source == MEAN:
        return "Plain average"
    if source == config.NWS_MODEL:
        return "NWS forecasters"
    return config.MODELS.get(source, {}).get("label", source)


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute(SCHEMA)


# ---------- live calls ----------

def live_rows(fc, issued):
    """[(source, valid, lead, liquid, snow, low, high)] from one forecast document.

    `raw` holds each source's own numbers before correction (NWS has snow only); `days` the
    blend as it went out. A plain average of every source is added as the yardstick a source
    has to beat."""
    out = []
    per_day = {}
    for m, daily in (fc.get("raw") or {}).items():
        for d, v in daily.items():
            lead = (date.fromisoformat(d) - issued).days
            if lead not in LEADS:
                continue
            out.append((m, d, lead, v.get("liquid"), v.get("snow"), None, None))
            per_day.setdefault(d, []).append(v)
    for d, vals in per_day.items():
        liq = [v["liquid"] for v in vals if v.get("liquid") is not None]
        snow = [v["snow"] for v in vals if v.get("snow") is not None]
        if len(snow) >= 3:
            out.append((MEAN, d, (date.fromisoformat(d) - issued).days,
                        round(sum(liq) / len(liq), 3) if len(liq) >= 3 else None,
                        round(sum(snow) / len(snow), 1), None, None))
    for x in fc.get("days") or []:
        lead = (date.fromisoformat(x["date"]) - issued).days
        if lead in LEADS:
            out.append((BLEND, x["date"], lead, None, x.get("snow"), x.get("low"), x.get("high")))
    return out


def _insert_calls(cur, slug, issued_of, rows, kind):
    cur.executemany(
        "INSERT INTO fc_calls (resort, source, issued, valid, lead, kind, liquid, snow, low, high) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        [(slug, s, issued_of(v, lead), v, lead, kind, liq, snow, lo, hi) for s, v, lead, liq, snow, lo, hi in rows])


def freeze(conn, slug, fc, now):
    """Keep this morning's call. Only the first full run of the day counts; a source missing
    then may still join before FREEZE_UNTIL_HOUR. Returns the number of rows written."""
    issued = now.date()
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM fc_calls WHERE resort = %s AND issued = %s AND kind = 'live'", (slug, issued))
        if cur.fetchone()[0] and now.hour >= FREEZE_UNTIL_HOUR:
            return 0
        rows = live_rows(fc, issued)
        _insert_calls(cur, slug, lambda v, lead: issued, rows, "live")
        return len(rows)


def truth_rows(obs_daily, resort_report, today, fresh):
    """{valid: {column: value}} from SNOTEL's daily rows and this morning's resort report."""
    out = {}
    for d, row in (obs_daily or {}).items():
        vals = {"snotel_liquid": row.get("precip_in"), "snotel_swe": row.get("swe_change_in"),
                "snotel_depth": row.get("depth_change_in")}
        if any(v is not None for v in vals.values()):
            out[d] = vals
    rep = resort_report or {}
    if fresh and rep.get("last_24h_in") is not None:
        d = (today - timedelta(days=1)).isoformat()  # this morning's 24 h covers yesterday's snow day
        out.setdefault(d, {}).update(resort_snow=rep["last_24h_in"], resort_updated=rep.get("updated_time"))
    return out


def save_truth(cur, slug, rows, station=None):
    cols = ("snotel_liquid", "snotel_swe", "snotel_depth", "resort_snow", "resort_updated")
    for d, vals in rows.items():
        keep = {k: v for k, v in vals.items() if k in cols}
        if not keep:
            continue
        names = list(keep)
        cur.execute(
            f"INSERT INTO fc_truth (resort, valid, station, {', '.join(names)}) "
            f"VALUES (%s, %s, %s, {', '.join(['%s'] * len(names))}) ON CONFLICT (resort, valid) DO UPDATE SET "
            + ", ".join(f"{n} = coalesce(excluded.{n}, fc_truth.{n})" for n in names)
            + ", station = coalesce(excluded.station, fc_truth.station), updated_at = now()",
            (slug, d, station, *keep.values()))


def save_weights(cur, slug, day, verification):
    rows = []
    for m, st in ((verification or {}).get("models") or {}).items():
        b = st.get("bias_by_lead") or {}
        base = st.get("bias_ratio")
        rows.append((slug, day, m, st.get("skill"), b.get("short", base), b.get("mid", base), b.get("long", base)))
    if rows:
        cur.executemany("INSERT INTO fc_weights (resort, day, model, skill, short, mid, long) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", rows)


def record(slug, fc, obs, resort_report, verification, now, fresh):
    """Called by every full run. Never raises: the audit must not cost a morning report."""
    import os
    from . import db
    if not db.url() or os.environ.get("STORE_MODE") == "shadow":  # shadow runs never write to Neon
        return None
    try:
        with db.connect() as conn:
            ensure_schema(conn)
            n = freeze(conn, slug, fc, now) if fc else 0
            with conn.cursor() as cur:
                save_truth(cur, slug, truth_rows((obs or {}).get("daily"), resort_report, now.date(), fresh),
                           (obs or {}).get("station"))
                save_weights(cur, slug, now.date(), verification)
            return n
    except Exception as e:
        log.warning("audit record failed for %s: %s", slug, e)
        return None


# ---------- replay ----------

def replay_months(today):
    """Every winter month from REPLAY_FIRST up to the current one, as yyyy-mm."""
    out, d = [], REPLAY_FIRST
    while d <= today:
        if d.month in REPLAY_MONTHS:
            out.append(d.strftime("%Y-%m"))
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


def month_span(ym, today):
    start = date.fromisoformat(ym + "-01")
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return start, min(end, today - timedelta(days=1))


def replay_rows(by_lead):
    """{lead: {model: {date: liquid}}} -> [(source, valid, lead, liquid, None, None, None)], plus the plain average."""
    out = []
    for lead, models in by_lead.items():
        per_day = {}
        for m, days in models.items():
            for d, v in days.items():
                out.append((m, d, lead, v, None, None, None))
                per_day.setdefault(d, []).append(v)
        for d, vals in per_day.items():
            if len(vals) >= 3:
                out.append((MEAN, d, lead, round(sum(vals) / len(vals), 3), None, None, None))
    return out


def fetch_replay(start, end):
    """Each model's daily liquid as forecast 1 to 7 days ahead, from Open-Meteo Previous Runs."""
    from .sources import openmeteo
    from .util import get
    models = [m for m in config.MODELS if m not in NO_REPLAY]
    hourly = ",".join(f"precipitation_previous_day{n}" for n in REPLAY_LEADS)
    params = openmeteo._base_params() | {"hourly": hourly, "start_date": start.isoformat(), "end_date": end.isoformat()}
    params.pop("forecast_days")

    def split(payload, ms):
        h = payload.get("hourly", {})
        times = h.get("time", [])
        out = {}
        for n in REPLAY_LEADS:
            for m in ms:
                col = h.get(f"precipitation_previous_day{n}" + ("" if len(ms) == 1 else f"_{m}"))
                if not col:
                    continue
                sums, hours = {}, {}
                for t, v in zip(times, col):
                    if v is not None:
                        sums[t[:10]] = sums.get(t[:10], 0.0) + v
                        hours[t[:10]] = hours.get(t[:10], 0) + 1
                days = {d: round(v, 3) for d, v in sums.items() if hours[d] >= 20}
                if days:
                    out.setdefault(n, {})[m] = days
        return out

    t0 = time.monotonic()
    r = get(openmeteo.PREVIOUS_RUNS_URL, params=params | {"models": ",".join(models)}, timeout=20, retries=0)
    if r.ok:
        return split(r.json(), models)
    log.warning("previous runs failed (%s): %s", r.status_code, r.text[:200])
    out = {}
    for m in models:  # one model the archive lacks fails the whole request
        if time.monotonic() - t0 > 25:  # stay inside the function's time limit; the month is retried later
            raise TimeoutError("previous runs: out of time, models done: " + ",".join(sorted({k for v in out.values() for k in v})))
        rr = get(openmeteo.PREVIOUS_RUNS_URL, params=params | {"models": m}, timeout=10, retries=0)
        if rr.ok:
            for n, v in split(rr.json(), [m]).items():
                out.setdefault(n, {}).update(v)
    return out


def fetch_replay_truth(start, end):
    from .sources import snotel
    for triplet in config.SNOTEL_STATIONS:
        try:
            series = snotel._fetch(triplet, "DAILY", start.isoformat(), (end + timedelta(days=1)).isoformat(),
                                   elements="PREC,WTEQ,SNWD")
            obs = snotel.daily_observations(series)
            if obs:
                return triplet, {d: v for d, v in obs.items() if start.isoformat() <= d <= end.isoformat()}
        except Exception as e:
            log.warning("SNOTEL %s replay failed: %s", triplet, e)
    return None, {}


def pending_chunks(conn, today, slugs):
    """[(slug, yyyy-mm)] still to replay, oldest month first."""
    with conn.cursor() as cur:
        # A month that failed is retried after RETRY_HOURS, not on every tick.
        cur.execute("SELECT resort, month, covered_to, tried_at > now() - make_interval(hours => %s) FROM fc_backfill",
                    (RETRY_HOURS,))
        done = {(r, m): (c, recent) for r, m, c, recent in cur.fetchall()}
        # Months marked done before 11/16 fixes but holding no gauge readings (SNOTEL was down) run again.
        cur.execute("SELECT DISTINCT resort, to_char(valid, 'YYYY-MM') FROM fc_truth WHERE snotel_liquid IS NOT NULL")
        has_truth = set(cur.fetchall())
    out = []
    for ym in replay_months(today):
        _, end = month_span(ym, today)
        for s in slugs:
            covered, recent = done.get((s, ym), (None, False))
            if covered is not None and covered >= end and (s, ym) in has_truth:
                continue
            if recent and (covered is None or (s, ym) not in has_truth):
                continue  # tried lately and failed, or SNOTEL had nothing: wait before trying again
            out.append((s, ym))
    return out


def replay_chunk(conn, slug, ym, today):
    config.use(slug)
    start, end = month_span(ym, today)
    rows, err = [], None
    try:
        rows = replay_rows(fetch_replay(start, end))
        station, obs = fetch_replay_truth(start, end)
        with conn.cursor() as cur:
            _insert_calls(cur, slug, lambda v, lead: (date.fromisoformat(v) - timedelta(days=lead)).isoformat(),
                          rows, "replay")
            save_truth(cur, slug, truth_rows(obs, None, today, False), station)
        if not rows:
            err = "no model data"
        elif not obs:  # SNOTEL down: keep the calls, retry the month so it gets its truth
            err = "no SNOTEL data"
    except Exception as e:
        err = str(e)[:300]
    with conn.cursor() as cur:
        cur.execute("INSERT INTO fc_backfill (resort, month, covered_to, rows, error) VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (resort, month) DO UPDATE SET covered_to = excluded.covered_to, rows = excluded.rows, "
                    "error = excluded.error, tried_at = now()",
                    (slug, ym, end if not err else None, len(rows), err))
        cur.execute("INSERT INTO fc_runs (resort, job, ok, detail) VALUES (%s, 'replay', %s, %s)",
                    (slug, not err, f"{ym}: {len(rows)} rows" + (f", {err}" if err else "")))
    return len(rows), err


# ---------- grading ----------

def _pair(metric, liquid, snow, t_liquid, t_snow):
    """(forecast, truth) for one call, or None when it can't be graded on this metric."""
    if metric == "water":
        return (liquid, t_liquid) if liquid is not None and t_liquid is not None else None
    return (snow, t_snow) if snow is not None and t_snow is not None else None


def _empty():
    # n, sum |miss|, sum miss, sum call, sum truth, storms seen, storms caught, big seen, big caught,
    # storms called, false alarms
    return [0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0, 0, 0]


def add(acc, metric, f, o):
    s1, s2 = STORM[metric]
    if max(f, o) >= COUNT_AT[metric]:
        acc[0] += 1
        acc[1] += abs(f - o)
        acc[2] += f - o
        acc[3] += f
        acc[4] += o
    if o >= s1:
        acc[5] += 1
        acc[6] += f >= s1
    if o >= s2:
        acc[7] += 1
        acc[8] += f >= s2
    if f >= s1:
        acc[9] += 1
        acc[10] += o < s1 / 2


def aggregate(rows):
    """rows: (source, lead, kind, liquid, snow, truth_liquid, truth_snow).
    Returns {metric: {source: {lead: {kind: acc}}}}."""
    out = {"snow": {}, "water": {}}
    for source, lead, kind, liq, snow, t_liq, t_snow in rows:
        for metric in out:
            p = _pair(metric, liq, snow, t_liq, t_snow)
            if p is None:
                continue
            acc = out[metric].setdefault(source, {}).setdefault(str(lead), {}).setdefault(kind, _empty())
            add(acc, metric, *p)
    return out


def merge(into, other):
    for metric, sources in other.items():
        for s, leads in sources.items():
            for lead, kinds in leads.items():
                for k, acc in kinds.items():
                    tgt = into.setdefault(metric, {}).setdefault(s, {}).setdefault(lead, {}).setdefault(k, _empty())
                    for i, v in enumerate(acc):
                        tgt[i] += v
    return into


def _group(agg_source, group, kinds):
    lo, hi = GROUPS[group]
    acc = _empty()
    for lead in range(lo, hi + 1):
        for k in kinds:
            for i, v in enumerate((agg_source.get(str(lead)) or {}).get(k) or []):
                acc[i] += v
    return acc


def letter(skill):
    if skill >= 0.15:
        return "A"
    if skill >= 0:
        return "B"
    if skill >= -0.15:
        return "C"
    return "D"


def grades(agg):
    """{metric: {source: {group: {grade, mae, bias, n, n_replay, hint}}}}. Letters from live calls only;
    replay only offers a hint ("Replay suggests B") until a source has MIN_GRADE_DAYS live days."""
    out = {}
    for metric, sources in agg.items():
        ref = sources.get(MEAN) or {}
        res = out.setdefault(metric, {})
        for s, leads in sources.items():
            for g in GROUPS:
                live, rep = _group(leads, g, ("live",)), _group(leads, g, ("replay",))
                cell = {"n": live[0], "n_replay": rep[0]}
                for acc, key in ((live, "live"), (rep, "replay")):
                    r = _group(ref, g, (key,))
                    if acc[0]:
                        cell[f"{key}_mae"] = round(acc[1] / acc[0], 2)
                        cell[f"{key}_bias"] = round(acc[3] / acc[4], 2) if acc[4] else None
                    if acc[0] >= MIN_GRADE_DAYS and r[0] >= MIN_GRADE_DAYS and s != MEAN:
                        skill = 1 - (acc[1] / acc[0]) / max(r[1] / r[0], 1e-6)
                        cell[f"{key}_skill"] = round(skill, 2)
                        if key == "live":
                            cell["grade"] = letter(skill)
                        else:
                            cell["hint"] = letter(skill)
                if "grade" not in cell:
                    cell["grade"] = "New"
                res.setdefault(s, {})[g] = cell
    return out


def _flags(t):
    flags = []
    rs, sd = t.get("resort_snow"), t.get("snotel_depth")
    if rs is not None and sd is not None and abs(rs - max(sd, 0)) > 3 and abs(rs - max(sd, 0)) > 0.5 * max(rs, sd, 1):
        flags.append("disagree")
    if t.get("snotel_liquid") is None:
        flags.append("gauge-gap")
    if (t.get("snotel_swe") or 0) < -0.2:
        flags.append("melt")
    return flags


def summary(slug, calls, truth, weights, today):
    """The per-resort report card the page reads.

    calls: [(source, issued, valid, lead, kind, liquid, snow, low, high)] (dates as ISO strings)
    truth: {valid: {snotel_liquid, snotel_swe, snotel_depth, resort_snow, station}}
    weights: [(day, model, skill, short, mid, long)]"""
    today_s = today.isoformat()
    graded = []
    for s, issued, valid, lead, kind, liq, snow, lo, hi in calls:
        t = truth.get(valid)
        if valid >= today_s or not t:
            continue
        graded.append((s, lead, kind, liq, snow, t.get("snotel_liquid"), t.get("resort_snow")))
    agg = aggregate(graded)
    by_valid = {}
    for row in calls:
        by_valid.setdefault(row[2], []).append(row)

    # Storm ledger: the last 15 snow days, by the resort report when there is one, else the gauge.
    storms = []
    for d in sorted(truth, reverse=True):
        t = truth[d]
        big = (t.get("resort_snow") or 0) >= 2 or (t.get("resort_snow") is None and (t.get("snotel_liquid") or 0) >= 0.15)
        if not big or d >= today_s:
            continue
        rows = by_valid.get(d, [])
        metric = "snow" if t.get("resort_snow") is not None else "water"
        truth_v = t.get("resort_snow") if metric == "snow" else t.get("snotel_liquid")

        def call(source, lead):
            for s, _, _, ld, kind, liq, snow, *_ in rows:
                if s == source and ld == lead:
                    return (snow if metric == "snow" else liq), kind
            return None, None

        blend3, k3 = call(BLEND, 3)
        if blend3 is None:
            blend3, k3 = call(MEAN, 3)
        misses = []
        for s, _, _, ld, kind, liq, snow, *_ in rows:
            v = snow if metric == "snow" else liq
            if ld == 1 and v is not None and s not in (BLEND, MEAN):
                misses.append((abs(v - truth_v), s, v))
        misses.sort()
        storms.append({"date": d, "metric": metric, "resort": t.get("resort_snow"), "snotel": t.get("snotel_liquid"),
                       "call3": blend3, "call3_source": BLEND if k3 and call(BLEND, 3)[0] is not None else MEAN,
                       "kind": k3 or "replay", "flags": _flags(t),
                       "best": misses[0][1:] if misses else None, "worst": misses[-1][1:] if len(misses) > 1 else None})
        if len(storms) >= 15:
            break

    # Call trails: how each source's call for one day moved as it got closer.
    def trail(d):
        out = {}
        for s, _, _, ld, kind, liq, snow, *_ in by_valid.get(d, []):
            if kind != "live":
                continue
            if snow is not None:
                out.setdefault(s, []).append([ld, snow])
        for v in out.values():
            v.sort(reverse=True)
        return out

    trails = []
    latest = max((r[1] for r in calls if r[0] == BLEND and r[4] == "live"), default="")
    upcoming = [(snow or 0, valid) for s, issued, valid, lead, kind, liq, snow, *_ in calls
                if s == BLEND and kind == "live" and valid >= today_s and issued == latest]
    if upcoming:
        best = max(upcoming)
        if best[0] >= 2:
            trails.append({"date": best[1], "label": "Next storm", "truth": None, "sources": trail(best[1])})
    for st in storms:
        tr = trail(st["date"])
        if tr:
            trails.append({"date": st["date"], "label": "Last storm", "truth": st["resort"], "sources": tr})
            break

    # Range check: did what fell land inside the blend's range (live, days 1 to 5)?
    inside = n_range = 0
    for s, issued, valid, lead, kind, liq, snow, lo, hi in calls:
        t = truth.get(valid)
        if s != BLEND or kind != "live" or not 1 <= lead <= 5 or not t or t.get("resort_snow") is None or lo is None:
            continue
        if max(t["resort_snow"], snow or 0) < COUNT_AT["snow"]:
            continue
        n_range += 1
        inside += lo <= t["resort_snow"] <= hi

    # Headline: over the last 30 days of live calls (days 0 to 4), how many sources did the blend beat?
    since = (today - timedelta(days=30)).isoformat()
    recent = aggregate([(s, lead, kind, liq, snow, truth[v].get("snotel_liquid"), truth[v].get("resort_snow"))
                        for s, issued, v, lead, kind, liq, snow, *_ in calls
                        if kind == "live" and since <= v < today_s and v in truth and lead <= 4])
    headline = None
    sn = recent.get("snow", {})
    if BLEND in sn:
        def mae(src):
            acc = _empty()
            for lead in range(5):
                for i, x in enumerate((sn[src].get(str(lead)) or {}).get("live") or []):
                    acc[i] += x
            return acc[1] / acc[0] if acc[0] >= 5 else None
        b = mae(BLEND)
        others = [(s, mae(s)) for s in sn if s not in (BLEND, MEAN)]
        others = [(s, m) for s, m in others if m is not None]
        if b is not None and others:
            headline = {"beat": sum(m > b for _, m in others), "of": len(others), "days": 30, "blend_mae": round(b, 2)}

    # Yesterday's verdict.
    verdict = None
    y = (today - timedelta(days=1)).isoformat()
    ty = truth.get(y) or {}
    if ty.get("resort_snow") is not None:
        rows = [r for r in by_valid.get(y, []) if r[3] == 1 and r[4] == "live" and r[6] is not None]
        b = next((r[6] for r in rows if r[0] == BLEND), None)
        others = sorted((abs(r[6] - ty["resort_snow"]), r[0]) for r in rows if r[0] not in (BLEND, MEAN))
        if b is not None:
            verdict = {"date": y, "fell": ty["resort_snow"], "blend": b, "miss": round(abs(b - ty["resort_snow"]), 1),
                       "best": others[0][1] if others else None}

    w = {}
    for day, model, skill, short, mid, long_ in weights:
        w.setdefault(model, []).append([day, skill, short, mid, long_])

    kinds = {"live": set(), "replay": set()}
    for s, issued, valid, lead, kind, *_ in calls:
        if valid in truth and valid < today_s:
            kinds[kind].add(valid)
    stations = sorted({t.get("station") for t in truth.values() if t.get("station")})
    sources = sorted({r[0] for r in calls}, key=lambda s: (s != BLEND, s == MEAN, label(s)))
    return {
        "resort": slug, "name": resorts.get(slug)["name"] if slug in resorts.RESORTS else slug,
        "updated": datetime.now(config.TZ).isoformat(timespec="minutes"), "today": today_s,
        "stations": stations,
        "sources": [{"key": s, "label": label(s)} for s in sources],
        "days": {k: len(v) for k, v in kinds.items()},
        "first": {k: min(v) if v else None for k, v in kinds.items()},
        "agg": agg, "grades": grades(agg), "storms": storms, "trails": trails,
        "range": {"n": n_range, "inside": inside}, "headline": headline, "verdict": verdict, "weights": w,
    }


def pooled(summaries):
    """All resorts at once: sums of every resort's numbers, graded the same way."""
    agg = {}
    days = {"live": 0, "replay": 0}
    labels = {}
    for s in summaries:
        merge(agg, s.get("agg") or {})
        for k in days:
            days[k] += (s.get("days") or {}).get(k, 0)
        labels.update({x["key"]: x["label"] for x in s.get("sources", [])})
    keys = sorted(labels, key=lambda s: (s != BLEND, s == MEAN, labels[s]))
    return {"resort": "all", "name": "All resorts", "updated": datetime.now(config.TZ).isoformat(timespec="minutes"),
            "sources": [{"key": k, "label": labels[k]} for k in keys], "days": days, "agg": agg,
            "grades": grades(agg), "resorts": len(summaries)}


# ---------- database reads ----------

def load(conn, slug):
    with conn.cursor() as cur:
        cur.execute("SELECT source, issued::text, valid::text, lead, kind, liquid, snow, low, high FROM fc_calls "
                    "WHERE resort = %s", (slug,))
        calls = cur.fetchall()
        cur.execute("SELECT valid::text, snotel_liquid, snotel_swe, snotel_depth, resort_snow, station "
                    "FROM fc_truth WHERE resort = %s", (slug,))
        truth = {v: {"snotel_liquid": a, "snotel_swe": b, "snotel_depth": c, "resort_snow": d, "station": e}
                 for v, a, b, c, d, e in cur.fetchall()}
        cur.execute("SELECT day::text, model, skill, short, mid, long FROM fc_weights WHERE resort = %s ORDER BY day",
                    (slug,))
        weights = cur.fetchall()
    return calls, truth, weights


def log_days(conn, slug, start, end):
    """The raw log for the page's drawer: one entry per day, with every call for it."""
    with conn.cursor() as cur:
        cur.execute("SELECT valid::text, snotel_liquid, snotel_swe, snotel_depth, resort_snow, resort_updated, station "
                    "FROM fc_truth WHERE resort = %s AND valid BETWEEN %s AND %s ORDER BY valid DESC",
                    (slug, start, end))
        days = {}
        for v, a, b, c, d, upd, st in cur.fetchall():
            t = {"snotel_liquid": a, "snotel_swe": b, "snotel_depth": c, "resort_snow": d}
            days[v] = {"date": v, **t, "resort_updated": upd, "station": st, "flags": _flags(t), "calls": []}
        cur.execute("SELECT valid::text, source, lead, kind, liquid, snow, low, high FROM fc_calls "
                    "WHERE resort = %s AND valid BETWEEN %s AND %s ORDER BY source, lead", (slug, start, end))
        for v, s, lead, kind, liq, snow, lo, hi in cur.fetchall():
            days.setdefault(v, {"date": v, "flags": [], "calls": []})["calls"].append(
                [s, lead, kind, liq, snow] + ([lo, hi] if lo is not None else []))
    return sorted(days.values(), key=lambda x: x["date"], reverse=True)


CSV_HEAD = ["resort", "valid_date", "issued_date", "source", "lead_days", "kind", "forecast_snow_in",
            "forecast_water_in", "blend_low_in", "blend_high_in", "resort_snow_in", "snotel_water_in",
            "snotel_depth_change_in"]


def csv_rows(conn, slug, start, end, kind=None, source=None, lead=None):
    q = ("SELECT c.resort, c.valid::text, c.issued::text, c.source, c.lead, c.kind, c.snow, c.liquid, c.low, c.high, "
         "t.resort_snow, t.snotel_liquid, t.snotel_depth FROM fc_calls c LEFT JOIN fc_truth t "
         "ON t.resort = c.resort AND t.valid = c.valid WHERE c.resort = %s AND c.valid BETWEEN %s AND %s")
    args = [slug, start, end]
    if kind in ("live", "replay"):
        q += " AND c.kind = %s"
        args.append(kind)
    if source:
        q += " AND c.source = %s"
        args.append(source)
    if lead is not None:
        q += " AND c.lead = %s"
        args.append(lead)
    with conn.cursor() as cur:
        cur.execute(q + " ORDER BY c.valid, c.source, c.lead", args)
        return cur.fetchall()


# ---------- the cron job ----------

def job(store=None, budget_s=45, now=None, slugs=None):
    """/api/audit's cron: replay a few resort-months, then rebuild the report cards that are due."""
    from . import db
    from .store import get_store
    t0 = time.monotonic()
    store = store or get_store()
    slugs = slugs or resorts.enabled()
    today = (now or datetime.now(config.TZ)).date()
    done, summarized = [], []
    with db.connect() as conn:
        ensure_schema(conn)
        for slug, ym in pending_chunks(conn, today, slugs):
            if time.monotonic() - t0 > budget_s * 0.5:
                break
            n, err = replay_chunk(conn, slug, ym, today)
            done.append({"resort": slug, "month": ym, "rows": n, "error": err})
        state = store.get_json("data/audit/state.json", {}) or {}
        due = sorted(slugs, key=lambda s: state.get(s, ""))
        touched = {d["resort"] for d in done}
        for slug in due:
            if time.monotonic() - t0 > budget_s:
                break
            age_ok = state.get(slug, "") >= (datetime.now(config.TZ) - timedelta(hours=1)).isoformat()
            if age_ok and slug not in touched:
                continue
            config.use(slug)
            calls, truth, weights = load(conn, slug)
            store.put_json(f"data/audit/{slug}.json", summary(slug, calls, truth, weights, today))
            state[slug] = datetime.now(config.TZ).isoformat(timespec="minutes")
            summarized.append(slug)
        if summarized:
            cards = [store.get_json(f"data/audit/{s}.json") for s in slugs]
            store.put_json("data/audit/all.json", pooled([c for c in cards if c]))
            store.put_json("data/audit/state.json", state)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM fc_backfill WHERE covered_to IS NOT NULL")
            replayed = cur.fetchone()[0]
    return {"status": "ok", "replayed": done, "summarized": summarized,
            "replay_progress": f"{replayed}/{len(replay_months(today)) * len(slugs)}",
            "seconds": round(time.monotonic() - t0, 1)}
