"""Owner stats: a first-party visit counter and the numbers behind the private /admin page.

Visits are counted without cookies, IPs or user agents: the app makes a random id once per
browser (localStorage) and sends it with the tab and resort it shows. One row per local day,
visitor, resort and tab, with a view count, so a day's unique visitors are a count of ids.
Days are Mountain Time (America/Denver), like the combined email.

Nothing here is public. /api/hit only writes; /api/stats needs ADMIN_KEY.
"""
import hmac
import os
import re

TZ = "America/Denver"
VIEWS = ("today", "calendar", "forecast", "help", "audit")
VID_RE = re.compile(r"^[A-Za-z0-9_-]{8,40}$")
DAYS = 30

DDL = """
CREATE TABLE IF NOT EXISTS page_views (
  day        date    NOT NULL,
  vid        text    NOT NULL,
  resort     text    NOT NULL DEFAULT '',
  view       text    NOT NULL,
  n          integer NOT NULL DEFAULT 1,
  standalone boolean NOT NULL DEFAULT false,
  mobile     boolean NOT NULL DEFAULT false,
  first_at   timestamptz NOT NULL DEFAULT now(),
  last_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (day, vid, resort, view)
);
CREATE INDEX IF NOT EXISTS page_views_day ON page_views (day);
"""
_ready = False


def ensure(conn):
    global _ready
    if not _ready:
        with conn.cursor() as cur:
            cur.execute(DDL)
        _ready = True


def clean_hit(data, valid_resorts):
    """The fields to store from a POST body, or None if it isn't a hit from the app."""
    vid = str(data.get("v", ""))
    view = str(data.get("t", ""))
    resort = str(data.get("r", ""))
    if not VID_RE.match(vid) or view not in VIEWS:
        return None
    if resort not in valid_resorts:
        resort = ""
    return {"vid": vid, "view": view, "resort": resort,
            "standalone": data.get("s") is True, "mobile": data.get("m") is True}


def record_hit(conn, hit):
    ensure(conn)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO page_views (day, vid, resort, view, standalone, mobile) "
            f"VALUES ((now() AT TIME ZONE '{TZ}')::date, %(vid)s, %(resort)s, %(view)s, %(standalone)s, %(mobile)s) "
            "ON CONFLICT (day, vid, resort, view) DO UPDATE SET n = page_views.n + 1, last_at = now(), "
            "standalone = page_views.standalone OR excluded.standalone",
            hit)


def authorized(header):
    key = os.environ.get("ADMIN_KEY", "")
    if len(key) < 12:          # unset or too short: the page stays locked
        return False
    return hmac.compare_digest((header or "").encode(), f"Bearer {key}".encode())


def mask(email):
    user, _, domain = (email or "").partition("@")
    return (user[:1] + "•••" if user else "") + "@" + domain


def _rows(cur, sql, args=()):
    cur.execute(sql, args)
    return cur.fetchall()


def summary(conn):
    ensure(conn)
    local = f"(now() AT TIME ZONE '{TZ}')::date"
    d = lambda col: f"({col} AT TIME ZONE '{TZ}')::date"  # noqa: E731
    out = {"tz": TZ, "days": DAYS}
    with conn.cursor() as cur:
        out["today"] = str(_rows(cur, f"SELECT {local}")[0][0])
        out["email"] = dict(_rows(cur, "SELECT status, count(*) FROM subscribers GROUP BY 1"))
        out["push"] = _rows(cur, "SELECT count(*) FROM push_subscriptions WHERE failures < 3")[0][0]
        # Sign-ups by day: email forms sent, emails confirmed, app notifications turned on.
        since = f"{local} - {DAYS - 1}"
        sig = {}
        for key, sql in (
            ("requested", f"SELECT {d('created_at')} AS day, count(*) FROM subscribers WHERE {d('created_at')} >= {since} GROUP BY 1"),
            ("confirmed", f"SELECT {d('confirmed_at')} AS day, count(*) FROM subscribers WHERE confirmed_at IS NOT NULL AND {d('confirmed_at')} >= {since} GROUP BY 1"),
            ("unsubscribed", f"SELECT {d('unsubscribed_at')} AS day, count(*) FROM subscribers WHERE unsubscribed_at IS NOT NULL AND {d('unsubscribed_at')} >= {since} GROUP BY 1"),
            ("push", f"SELECT {d('created_at')} AS day, count(*) FROM push_subscriptions WHERE {d('created_at')} >= {since} GROUP BY 1"),
        ):
            for day, n in _rows(cur, sql):
                sig.setdefault(str(day), {})[key] = n
        out["signups"] = sig
        # Running totals at the start of the window, so the chart can draw a growth line.
        out["active_before"] = _rows(cur, f"SELECT count(*) FROM subscribers WHERE confirmed_at IS NOT NULL AND {d('confirmed_at')} < {since} "
                                          f"AND (unsubscribed_at IS NULL OR {d('unsubscribed_at')} >= {since})")[0][0]
        out["first_signup"] = str((_rows(cur, f"SELECT min({d('created_at')}) FROM subscribers")[0][0]) or "")
        # Per resort: active email subscribers and app notification subscriptions.
        per = {}
        for slug, n in _rows(cur, "SELECT unnest(resorts), count(*) FROM subscribers WHERE status = 'active' GROUP BY 1"):
            per.setdefault(slug, {})["email"] = n
        for slug, n in _rows(cur, "SELECT unnest(resorts), count(*) FROM push_subscriptions WHERE failures < 3 GROUP BY 1"):
            per.setdefault(slug, {})["push"] = n
        out["resorts"] = per
        out["multi"] = _rows(cur, "SELECT count(*) FROM subscribers WHERE status = 'active' AND cardinality(resorts) > 1")[0][0]
        out["recent"] = [{"email": mask(e), "status": s, "resorts": list(r or []), "at": a.isoformat()}
                         for e, s, r, a in _rows(cur, "SELECT email, status, resorts, created_at FROM subscribers ORDER BY created_at DESC LIMIT 12")]
        # Visits.
        out["visits"] = {str(day): {"visitors": v, "views": n} for day, v, n in _rows(
            cur, f"SELECT day, count(DISTINCT vid), sum(n) FROM page_views WHERE day >= {since} GROUP BY 1")}
        win = lambda k: _rows(cur, f"SELECT count(DISTINCT vid), coalesce(sum(n), 0) FROM page_views WHERE day > {local} - {k}")[0]  # noqa: E731
        out["window"] = {str(k): dict(zip(("visitors", "views"), win(k))) for k in (1, 7, 30)}
        out["by_view"] = dict(_rows(cur, f"SELECT view, sum(n) FROM page_views WHERE day >= {since} GROUP BY 1"))
        out["by_resort"] = dict(_rows(cur, f"SELECT resort, count(DISTINCT vid) FROM page_views WHERE day >= {since} AND resort <> '' GROUP BY 1"))
        dev = _rows(cur, f"SELECT count(DISTINCT vid) FILTER (WHERE standalone), count(DISTINCT vid) FILTER (WHERE mobile), "
                         f"count(DISTINCT vid) FROM page_views WHERE day >= {since}")[0]
        out["devices"] = {"home_screen": dev[0], "phone": dev[1], "all": dev[2]}
        out["returning"] = _rows(cur, f"SELECT count(*) FROM (SELECT vid FROM page_views WHERE day >= {since} "
                                      "GROUP BY vid HAVING count(DISTINCT day) > 1) x")[0][0]
        out["counting_since"] = str((_rows(cur, "SELECT min(day) FROM page_views")[0][0]) or "")
    return out
