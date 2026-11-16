"""Posting-time observer (one week, Nov 16-23, 2026): when does each resort post its grooming
report and its official snow totals each morning?

Every tick polls each resort's grooming and snow-report sources and stores one row per probe in
Neon (`posting_polls`, docs/migrations/002_posting_polls.sql): HTTP status, the page's own
"Updated ..." stamp when it has one, and a fingerprint of the content. The first poll of a day
whose stamp or fingerprint differs from the previous one is when that day's report appeared.
Analysis queries: docs/POSTING_TIMES.md.

Read-only on purpose: it never imports the mailer, push or the send pipeline, so nothing here
can reach a subscriber. Its only other write is a summary of the changes it has seen, at
data/observer/summary.json in the Blob archive (public pages' posting times, nothing private).

Cadence: /api/observe is called every 5 minutes by Vercel cron. Between 3 and 10 a.m. resort time
every tick polls; the rest of the day only the :00/:15/:30/:45 ticks do (grooming maps are often
posted the evening before). After OBSERVE_UNTIL it does nothing.
"""
import hashlib
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import requests

from . import config, resorts

log = logging.getLogger(__name__)

OBSERVE_UNTIL = date.fromisoformat(os.environ.get("OBSERVE_UNTIL", "2026-11-23"))
WINDOW = (3, 10)  # local hours, [start, end)
TIMEOUT = 20

# Resorts whose own site isn't read by the app yet: the most likely public pages, checked by
# the observer itself (HTTP status and stamp are recorded, so a wrong guess shows up as 404/403).
LIKELY = {
    "telluride": {"snow": "https://tellurideskiresort.com/snow-report/"},
    "snowmass": {"snow": "https://www.aspensnowmass.com/four-mountains/snowmass/snow-and-grooming-report"},
    "aspen-mountain": {"snow": "https://www.aspensnowmass.com/four-mountains/aspen-mountain/snow-and-grooming-report"},
    "aspen-highlands": {"snow": "https://www.aspensnowmass.com/four-mountains/aspen-highlands/snow-and-grooming-report"},
    "buttermilk": {"snow": "https://www.aspensnowmass.com/four-mountains/buttermilk/snow-and-grooming-report"},
    "steamboat": {"snow": "https://www.steamboat.com/the-mountain/mountain-report"},
    "winter-park": {"snow": "https://www.winterparkresort.com/the-mountain/mountain-report"},
    "arapahoe-basin": {"snow": "https://www.arapahoebasin.com/snow-report/"},
    "deer-valley": {"snow": "https://www.deervalley.com/mountain-report"},
    "solitude": {"snow": "https://www.solitudemountain.com/mountain-and-village/mountain-report"},
    "brighton": {"snow": "https://www.brightonresort.com/conditions"},
    "alta": {"snow": "https://www.alta.com/conditions/daily-mountain-report/snow-report",
             "grooming": "https://www.alta.com/lift-terrain-status"},
    "snowbasin": {"snow": "https://www.snowbasin.com/the-mountain/mountain-report/"},
}


def probes():
    """(resort, source, kind, url) for every resort."""
    out = []
    for slug in resorts.enabled():
        r = resorts.get(slug)
        if r["grooming_pdf"]:
            out.append((slug, "grooming", "pdf", r["grooming_pdf"]))
        if r["dor_api"]:
            out.append((slug, "snow", "dor_snow", r["dor_api"] + "/api/v1/dor/drupal/snow-reports"))
            out.append((slug, "grooming", "dor_trails", r["dor_api"] + "/api/v1/dor/drupal/trails"))
        elif r["snow_report"]:
            out.append((slug, "snow", "vail", r["snow_report"]))
        for source, url in LIKELY.get(slug, {}).items():
            if not any(p[0] == slug and p[1] == source for p in out):
                out.append((slug, source, "html", url))
    return out


def _sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()[:16]


_TAGS = re.compile(r"<(script|style|noscript|svg)\b.*?</\1>", re.S | re.I)
_STAMP = re.compile(r"(?:last\s+)?updated?(?:\s+(?:at|on))?\s*:?\s*([A-Za-z]{3,9}\.?\s+\d{1,2},?\s+(?:20\d\d\s+)?(?:at\s+)?\d{1,2}:\d{2}\s?[AaPp]\.?[Mm]\.?"
                    r"|\d{1,2}/\d{1,2}(?:/\d{2,4})?,?\s+(?:at\s+)?\d{1,2}:\d{2}\s?[AaPp]\.?[Mm]\.?"
                    r"|\d{1,2}:\d{2}\s?[AaPp]\.?[Mm]\.?(?:\s+[A-Z]{2,4})?(?:\s+on)?(?:\s+[A-Za-z]{3,9}\.?\s+\d{1,2})?)", re.I)
_SNOW_BITS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\"|”|in\b|inches|cm)", re.I)


def read_html(text):
    """Generic page: its 'Updated ...' stamp (if any) and a fingerprint of the snow numbers on it."""
    stamp = None
    for m in _STAMP.finditer(text):
        stamp = re.sub(r"\s+", " ", m.group(1)).strip()
        break
    visible = re.sub(r"<[^>]+>", " ", _TAGS.sub(" ", text))
    visible = re.sub(r"\s+", " ", visible)
    if not stamp:
        m = _STAMP.search(visible)
        stamp = re.sub(r"\s+", " ", m.group(1)).strip() if m else None
    nums = _SNOW_BITS.findall(visible)
    return stamp, _sha(" ".join(nums)) if nums else _sha(visible), {"snow_numbers": nums[:24]}


def read(kind, resp):
    """-> (stamp, fingerprint, detail)."""
    if kind == "pdf":
        detail = {"last_modified": resp.headers.get("Last-Modified"), "etag": resp.headers.get("ETag")}
        try:
            import pymupdf
            doc = pymupdf.open(stream=resp.content, filetype="pdf")
            lines = [ln.strip() for ln in doc[0].get_text().splitlines() if ln.strip()]
            doc.close()
            from .sources.grooming import parse_runs
            runs = parse_runs(lines)
            detail["map_date"] = runs.get("map_date")
            detail["runs"] = sum(len(v) for k, v in runs.items() if isinstance(v, list) and k != "groomed") or len(runs.get("groomed") or [])
        except Exception as e:
            detail["parse_error"] = str(e)[:200]
        return detail.get("map_date") or detail["last_modified"], _sha(resp.content), detail
    if kind == "vail":
        from .sources.resort import parse
        rep = parse(resp.text)
        if not rep:
            stamp, fp, detail = read_html(resp.text)
            return stamp, fp, dict(detail, note="no snowReportData")
        stamps = rep.get("stamps") or {}
        stamp = next((str(v) for k, v in stamps.items() if "updated" in k.lower()), None) or json.dumps(stamps)[:200]
        totals = {k: v for k, v in rep.items() if k.endswith("_in")}
        return stamp, _sha(json.dumps(totals, sort_keys=True)), {"totals": totals}
    if kind == "dor_snow":
        from .sources.dor import parse_snow_report
        rep = parse_snow_report(resp.json())
        totals = {k: v for k, v in rep.items() if k.endswith("_in")}
        return (rep.get("stamps") or {}).get("date"), _sha(json.dumps(totals, sort_keys=True)), {"totals": totals}
    if kind == "dor_trails":
        trails = resp.json()
        groomed = sorted(t.get("name") or "" for t in trails if isinstance(t, dict)
                         and (t.get("groom_status") or "not_groomed") != "not_groomed")
        stamps = [str(t.get(k)) for t in trails if isinstance(t, dict) for k in ("updated", "updated_at", "changed", "groom_date") if t.get(k)]
        return (max(stamps) if stamps else None), _sha("|".join(groomed)), {"groomed": len(groomed)}
    return read_html(resp.text)


def poll_one(probe, session):
    slug, source, kind, url = probe
    t0 = time.monotonic()
    row = {"resort": slug, "source": source, "kind": kind, "url": url, "http": None, "ms": None, "bytes": None,
           "stamp": None, "fp": None, "detail": None, "error": None}
    try:
        resp = session.get(url, timeout=TIMEOUT, headers={"Accept": "application/json" if kind.startswith("dor") else "*/*",
                                                          "Cache-Control": "no-cache"})
        row.update(http=resp.status_code, bytes=len(resp.content))
        if resp.ok:
            stamp, fp, detail = read(kind, resp)
            row.update(stamp=(stamp or None) and str(stamp)[:200], fp=fp, detail=json.dumps(detail, default=str)[:2000])
    except Exception as e:
        row["error"] = f"{type(e).__name__}: {e}"[:300]
    row["ms"] = int((time.monotonic() - t0) * 1000)
    return row


def due(slug, now):
    local = now.astimezone(ZoneInfo(resorts.get(slug)["tz"]))
    return WINDOW[0] <= local.hour < WINDOW[1] or now.minute % 15 < 2


def run(now=None, force=False):
    now = now or datetime.now(timezone.utc)
    if now.astimezone(ZoneInfo("America/Denver")).date() > OBSERVE_UNTIL and not force:
        return {"status": "skipped", "reason": f"observation ended {OBSERVE_UNTIL}"}
    todo = [p for p in probes() if force or due(p[0], now)]
    if not todo:
        return {"status": "skipped", "reason": "outside window"}
    session = requests.Session()
    session.headers["User-Agent"] = config.USER_AGENT
    with ThreadPoolExecutor(max_workers=24) as pool:
        rows = list(pool.map(lambda p: poll_one(p, session), todo))
    from . import db
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA)
        cur.executemany(
            "INSERT INTO posting_polls (polled_at, resort, source, kind, url, http, ms, bytes, stamp, fp, detail, error)"
            " VALUES (%(polled_at)s, %(resort)s, %(source)s, %(kind)s, %(url)s, %(http)s, %(ms)s, %(bytes)s,"
            " %(stamp)s, %(fp)s, %(detail)s::jsonb, %(error)s)",
            [dict(r, polled_at=now) for r in rows])
        summary_ok = True
        try:
            write_summary(cur, now)
        except Exception:
            log.exception("observer summary failed")
            summary_ok = False
    ok = sum(1 for r in rows if r["fp"])
    return {"status": "ok", "polled": len(rows), "ok": ok, "summary": summary_ok,
            "failed": [f"{r['resort']}/{r['source']}: {r['http'] or r['error']}" for r in rows if not r["fp"]]}


# Same as docs/migrations/002_posting_polls.sql (docs/ isn't deployed with the functions).
SCHEMA = """CREATE TABLE IF NOT EXISTS posting_polls (
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
"""

# Every poll whose stamp or fingerprint differs from the previous successful poll of the same
# probe, in resort-local time (all 22 resorts are on Mountain time).
CHANGES_SQL = """
WITH ok AS (
  SELECT resort, source, kind, polled_at, stamp, fp, detail,
         lag(fp) OVER w AS prev_fp, lag(stamp) OVER w AS prev_stamp
  FROM posting_polls WHERE fp IS NOT NULL
  WINDOW w AS (PARTITION BY resort, source, url ORDER BY polled_at)
)
SELECT resort, source, kind,
       to_char(polled_at AT TIME ZONE 'America/Denver', 'YYYY-MM-DD') AS day,
       to_char(polled_at AT TIME ZONE 'America/Denver', 'HH24:MI') AS at,
       stamp, prev_stamp, fp IS DISTINCT FROM prev_fp AS content_changed,
       stamp IS DISTINCT FROM prev_stamp AS stamp_changed, detail
FROM ok
WHERE prev_fp IS NOT NULL AND (fp IS DISTINCT FROM prev_fp OR stamp IS DISTINCT FROM prev_stamp)
ORDER BY resort, source, polled_at
"""

LATEST_SQL = """
SELECT DISTINCT ON (resort, source, url) resort, source, kind, url, http, stamp, error,
       to_char(polled_at AT TIME ZONE 'America/Denver', 'YYYY-MM-DD HH24:MI') AS at,
       (SELECT count(*) FROM posting_polls p2 WHERE p2.resort = p.resort AND p2.url = p.url) AS polls,
       (SELECT count(*) FROM posting_polls p2 WHERE p2.resort = p.resort AND p2.url = p.url AND p2.fp IS NOT NULL) AS ok_polls
FROM posting_polls p ORDER BY resort, source, url, polled_at DESC
"""


def write_summary(cur, now):
    cols = lambda: [c.name for c in cur.description]  # noqa: E731
    cur.execute(CHANGES_SQL)
    names = cols()
    changes = [dict(zip(names, row)) for row in cur.fetchall()]
    cur.execute(LATEST_SQL)
    names = cols()
    latest = [dict(zip(names, row)) for row in cur.fetchall()]
    from .store import get_store
    get_store().put_json("data/observer/summary.json", {
        "generated": now.astimezone(ZoneInfo("America/Denver")).strftime("%Y-%m-%d %H:%M %Z"),
        "until": OBSERVE_UNTIL.isoformat(), "probes": latest, "changes": changes})
