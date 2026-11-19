"""Sourced resort facts for the public info pages: hours, opening and closing day, trail map, passes,
blackout dates, lift tickets and lessons.

Every fact carries the official page it came from and the date it was last checked. Facts are
re-checked on a seasonal schedule (Young, 11/19/2026): a fact is checked often in the weeks it
changes and gets searched, and monthly otherwise. Closing dates every 2 days from March 1,
opening dates every 2 days from mid-September, passes and blackout dates every 2 days
in March and April (when next season goes on sale), ticket prices weekly in season.

`watch()` runs once a day (/api/facts): it reads each source page, notes when the relevant
text changed, and writes data/facts/status.json listing what is due for a re-check. A changed
page or a due fact is a prompt to re-read the source and update FACTS here; nothing on the
public page changes until a person (or Claude) confirms the new value.
"""
import hashlib
import html
import re
from datetime import date, datetime, timedelta

# ---------- the data: bcbot/facts_data/*.json ----------
# The facts themselves live in JSON so a re-check (by a person or the scheduled Claude task) edits data,
# not code. curated.json: hand-checked facts per resort and kind, each
#   {"value", "checked", "source", "source_name", "note"?, "label"?, "maps"?, "rows"?, "evidence"?}.
#   value None = checked and not posted yet (the note says why). Dates are ISO; pages show MM/DD.
#   evidence (optional): the source sentence, quoted, that backs the value.
# shared.json: facts that come from one page for many resorts (pass access, announced dates, lift hours,
#   trail map pages). _shared() turns them into per-resort facts; a curated value wins.
import json
import os

_DATA = os.path.join(os.path.dirname(__file__), "facts_data")


def _load(name):
    with open(os.path.join(_DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


CURATED = _load("curated.json")
_SHARED = _load("shared.json")
CHECKED_SHARED = _SHARED["checked_shared"]
_S = _SHARED["sources"]
EPIC_PASS, EPIC_LOCAL, EPIC_PEAK = _S["EPIC_PASS"], _S["EPIC_LOCAL"], _S["EPIC_PEAK"]
IKON_COMPARE, IKON_BASE_BLACKOUTS, IKON_DATES, VR_DATES = (_S["IKON_COMPARE"], _S["IKON_BASE_BLACKOUTS"],
                                                           _S["IKON_DATES"], _S["VR_DATES"])
EPIC_PEAK_DATES = _SHARED["epic_peak_dates"]
IKON_BASE_DATES = _SHARED["ikon_base_dates"]
TELLURIDE_HOURS = _SHARED["telluride_hours"]
EPIC_ACCESS = _SHARED["epic_access"]    # slug -> [Epic Pass, Epic Local Pass or null]
IKON_ACCESS = _SHARED["ikon_access"]    # slug -> [Ikon Pass, Ikon Base Pass or null, Ikon Session Pass or null]
ANNOUNCED = _SHARED["announced"]        # slug -> [opening, closing or null, [source url, page name]]
TRAIL_MAPS = _SHARED["trail_maps"]      # slug -> [page url, label]
LIFT_HOURS = _SHARED["lift_hours"]      # slug -> [text, [source url, page name]]


def _fact(value, src, **extra):
    return dict({"value": value, "checked": CHECKED_SHARED, "source": src[0], "source_name": src[1]}, **extra)


def _shared(slug, name):
    out = {}
    if slug in ANNOUNCED:
        o, c, src = ANNOUNCED[slug]
        out["opening_day"] = _fact(o, src)
        out["closing_day"] = _fact(c, src)
    if slug == "telluride":
        out["lift_hours"] = _fact(TELLURIDE_HOURS, ANNOUNCED["telluride"][2])
    if slug in LIFT_HOURS:
        value, src = LIFT_HOURS[slug]
        out["lift_hours"] = _fact(value, src)
    if slug in TRAIL_MAPS:
        url, label = TRAIL_MAPS[slug]
        out["trail_map"] = _fact(url, (url, f"{name}: Trail and Mountain Maps"), label=label)
    if slug in EPIC_ACCESS:
        full, local = EPIC_ACCESS[slug]
        text = f"Epic Pass: {full}. " + (f"Epic Local Pass: {local}. " if local else f"The Epic Local Pass doesn't include {name}. ")
        text += "Epic Day Pass: not valid on peak dates."
        rows = [("Epic Pass", full), ("Epic Local Pass", local or "Not included"), ("Epic Day Pass", "Not valid on peak dates")]
        out["passes"] = _fact(text, EPIC_LOCAL if local else EPIC_PASS, rows=rows)
        on_peak = [p for p, rule in (("Epic Local Pass", local),) if rule and "not valid on peak" in rule]
        applies = " and ".join(on_peak + ["Epic Day Pass"])
        out["blackout_dates"] = _fact(f"{EPIC_PEAK_DATES}. These apply to the {applies}"
                                      + (". The full Epic Pass has none." if "unlimited" in full else "."), EPIC_PEAK,
                                      pass_key="epic-blackout-dates", applies=applies)
    if slug in IKON_ACCESS:
        full, base, session = IKON_ACCESS[slug]
        bits = [f"Ikon Pass: {full}" + (", no blackout dates" if full == "unlimited" else "")]
        bits.append(f"Ikon Base Pass: {base}" + (", with blackout dates" if base else "") if base else f"The Ikon Base Pass doesn't include {name}")
        if session:
            bits.append(f"Ikon Session Pass: {session}")
        rows = [("Ikon Pass", full + (", no blackout dates" if full == "unlimited" else "")),
                ("Ikon Base Pass", (base + ", with blackout dates") if base else "Not included")]
        if session:
            rows.append(("Ikon Session Pass", session))
        out["passes"] = _fact(". ".join(bits) + ".", IKON_COMPARE, rows=rows)
        out["blackout_dates"] = (_fact(f"{IKON_BASE_DATES} on the Ikon Base Pass. The full Ikon Pass has none.", IKON_BASE_BLACKOUTS,
                                       pass_key="ikon-blackout-dates", applies="Ikon Base Pass") if base
                                 else _fact(f"None. The Ikon Pass has no blackout dates, and the Ikon Base Pass doesn't include {name}.",
                                            IKON_COMPARE, pass_key=None, applies=None))
    return out


def _build():
    from . import resorts
    out = {}
    for slug in resorts.RESORTS:
        name = resorts.RESORTS[slug]["name"]
        shared = _shared(slug, name)
        merged = dict(shared, **CURATED.get(slug, {}))
        # Hand-checked pass facts keep the structured rows and blackout ranges from the shared tables.
        for kind, keys in (("passes", ("rows",)), ("blackout_dates", ("pass_key", "applies"))):
            if kind in CURATED.get(slug, {}) and kind in shared and shared[kind]["source"] == merged[kind]["source"]:
                merged[kind] = dict({k: shared[kind][k] for k in keys if k in shared[kind]}, **merged[kind])
        if merged:
            out[slug] = merged
    return out


FACTS = _build()

LABELS = {"opening_day": "Opening day", "closing_day": "Closing day", "lift_hours": "Lift hours", "trail_map": "Trail map",
          "passes": "Passes", "blackout_dates": "Blackout dates", "lift_tickets": "Lift tickets", "lessons": "Lessons"}


SHORT = {"opening_day": "opening day", "closing_day": "closing day", "lift_hours": "lift hours", "trail_map": "trail map",
         "passes": "passes", "blackout_dates": "blackout dates", "lift_tickets": "lift ticket prices", "lessons": "lessons"}


def topics(slug):
    """What a resort's guide covers, in page order, e.g. "opening day, closing day, passes and blackout dates"."""
    have = [SHORT[k] for k in LABELS if k in (FACTS.get(slug) or {})]
    return ", ".join(have[:-1]) + (" and " if len(have) > 1 else "") + (have[-1] if have else "")


# ---------- adding a resort: where to look ----------
# Each operator lays its sites out the same way, so one checked path pattern covers all its resorts.
# Paths were confirmed on beavercreek.com (Vail Resorts). Read the page before trusting a fact: the
# path only says where to look. See docs/RESORT_FACTS.md.
OPERATOR_PAGES = {
    "vail-resorts": {
        "lift_hours": "/explore-the-resort/about-the-resort/hours-of-operation.aspx",
        "trail_map": "/the-mountain/about-the-mountain/trail-map.aspx",
        "lift_tickets": "/plan-your-trip/lift-access/tickets.aspx",
        "lessons": "/plan-your-trip/ski-and-ride-lessons.aspx",
    },
}
OPERATOR = {s: "vail-resorts" for s in ("beaver-creek", "vail", "breckenridge", "keystone", "crested-butte", "park-city",
                                        "whistler-blackcomb", "heavenly", "northstar", "kirkwood", "stevens-pass", "stowe",
                                        "okemo", "mount-snow", "seven-springs")}


def missing(slug):
    """Fact kinds a resort's guide doesn't have yet."""
    have = FACTS.get(slug) or {}
    return [k for k in LABELS if k not in have]


def todo():
    """[(slug, kind, where to read it)] for every missing fact, so the next person knows what to check."""
    from . import resorts
    out = []
    for slug, r in resorts.RESORTS.items():
        pages = OPERATOR_PAGES.get(OPERATOR.get(slug), {})
        for kind in missing(slug):
            where = r["site"] + pages[kind] if kind in pages else f'{r["site"]} (find the official page)'
            out.append((slug, kind, where))
    return out


def _in(today, start, end):
    """Is today between two (month, day) points, inclusive? Handles ranges that cross New Year."""
    t = (today.month, today.day)
    return start <= t <= end if start <= end else (t >= start or t <= end)


def interval_days(kind, today):
    """How often a fact is re-checked, by season. Busy weeks get checked every 2 days."""
    if kind == "closing_day":
        return 2 if _in(today, (3, 1), (5, 31)) else 30
    if kind == "opening_day":
        return 2 if _in(today, (9, 15), (11, 30)) else 30
    if kind == "lift_hours":
        return 7 if _in(today, (11, 1), (4, 30)) else 30
    if kind == "trail_map":
        return 7 if _in(today, (10, 15), (12, 15)) else 30
    if kind in ("passes", "blackout_dates"):
        # Next season's passes and their blackout dates are announced and go on sale in March.
        return 2 if _in(today, (3, 1), (4, 30)) else 30
    if kind == "lift_tickets":
        return 7 if _in(today, (11, 1), (4, 30)) else 30
    if kind == "lessons":
        return 14 if _in(today, (10, 1), (12, 31)) else 30
    return 30


def due(today=None, facts=None):
    """Facts whose next check date has come: [(slug, kind, days overdue)], most overdue first."""
    today = today or date.today()
    out = []
    for slug, kinds in (facts or FACTS).items():
        for kind, f in kinds.items():
            nxt = date.fromisoformat(f["checked"]) + timedelta(days=interval_days(kind, today))
            if today >= nxt:
                out.append((slug, kind, (today - nxt).days))
    return sorted(out, key=lambda x: -x[2])


def last_checked(slug, kind, f, confirmed=None):
    """The fact's checked date, or a later date the daily watch confirmed its source page unchanged."""
    c = (confirmed or {}).get(f"{slug}|{kind}")
    return max(f["checked"], c) if c else f["checked"]


# Kinds that go wrong fast. Past 4x their check interval we stop showing the value at all.
VOLATILE = ("opening_day", "closing_day", "lift_hours", "lift_tickets")
_CONFIRMED = {"at": None, "data": {}}


def confirmed_dates():
    """Dates the daily watch confirmed facts unchanged (Blob data/facts/status.json), cached 15 minutes.
    Never raises: with no store we fall back to the checked dates in this file."""
    now = datetime.now()
    if _CONFIRMED["at"] and (now - _CONFIRMED["at"]).total_seconds() < 900:
        return _CONFIRMED["data"]
    try:
        from .store import get_store
        data = (get_store().get_json("data/facts/status.json", {}) or {}).get("confirmed") or {}
    except Exception:
        data = {}
    _CONFIRMED.update(at=now, data=data)
    return data


def expired(f, kind, today=None):
    """Too old to show: a volatile fact past 4x its check interval, or a date from a past season."""
    today = today or date.today()
    if kind in VOLATILE and (today - date.fromisoformat(f["checked"])).days > 4 * interval_days(kind, today):
        return True
    v = f.get("value")
    if kind in ("opening_day", "closing_day") and v and re.fullmatch(r"\d{4}-\d\d-\d\d", v):
        return (today - date.fromisoformat(v)).days > 240  # last season's date
    return False


def public(slug, today=None, confirmed=None):
    """A resort's facts as the public pages, llms.txt and JSON should show them: checked dates include
    the watch's confirmations, and an expired value is replaced by a pointer to the source page, so we
    never show an old value as current."""
    today = today or date.today()
    confirmed = confirmed_dates() if confirmed is None else confirmed
    out = {}
    for kind, f in (FACTS.get(slug) or {}).items():
        f = dict(f, checked=last_checked(slug, kind, f, confirmed))
        if f.get("value") is not None and expired(f, kind, today):
            name = f.get("source_name") or "the resort's page"
            f = dict(f, value=None, expired=True, maps=None,
                     note=f"Last confirmed {int(f['checked'][5:7])}/{int(f['checked'][8:10])}. Check {name} for the current {SHORT[kind]}.")
            f = {k: v for k, v in f.items() if v is not None or k == "value"}
        out[kind] = f
    return out


def stale(f, kind, today=None):
    """Shown on the page when a fact is more than twice its check interval old."""
    today = today or date.today()
    return (today - date.fromisoformat(f["checked"])).days > 2 * interval_days(kind, today)


# ---------- page watch ----------

KEY_LINE = re.compile(r"(open|clos|hours|season|\b\d{1,2}(:\d\d)?\s?(am|pm)\b|\b\d{1,2}/\d{1,2}\b|"
                      r"january|february|march|april|may|june|november|december)", re.I)


# Bot walls and empty JavaScript shells come back as a 200 but carry none of the page: treat them as a failed read.
BLOCKED = re.compile(r"(just a moment\.\.\.|cf-chl|challenge-platform|captcha|access denied|attention required|"
                     r"enable javascript to|request unsuccessful|incapsula|are you a robot)", re.I)
MAX_LINES = 60  # key lines kept per page for the re-check diff


def key_lines(page_html):
    """The page's lines that carry dates and hours, sorted, without menus, scripts or promos."""
    text = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", page_html or "")
    text = html.unescape(re.sub(r"(?s)<[^>]+>", "\n", text))
    return sorted({ln.strip() for ln in text.splitlines() if ln.strip() and len(ln.strip()) < 300 and KEY_LINE.search(ln)})


def fingerprint(page_html):
    """Hash only the lines that carry dates and hours, so menus and promos don't trip it."""
    return hashlib.sha256("\n".join(key_lines(page_html)).encode()).hexdigest()[:16]


def blocked(page_html):
    """A read that didn't get the real page: a bot wall, a challenge, or a shell with no dates or hours at all."""
    return not key_lines(page_html) or bool(BLOCKED.search((page_html or "")[:20000]))


def watch(store, fetch, now=None):
    """Read every source page once and write data/facts/status.json. `fetch(url) -> html or None`.

    A page counts as changed only when the new text is still there on the next read (one-off promos,
    countdowns and A/B tests don't flag it). Bot walls and empty shells count as errors, not changes.
    The status carries a work queue for the re-check task: every fact that is due, plus every fact
    whose source changed, with the lines that were added and removed. Returns the status written."""
    now = now or datetime.now()
    stamp = now.isoformat(timespec="minutes")
    prev = store.get_json("data/facts/status.json", {}) or {}
    seen = dict(prev.get("pages") or {})
    changed, failing = [], []
    urls = sorted({f["source"] for kinds in FACTS.values() for f in kinds.values()})
    # 170+ pages won't fit a 60 s function one at a time: read them in parallel.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=32) as pool:
        pages = dict(zip(urls, pool.map(fetch, urls)))
    for url in urls:
        page = pages[url]
        entry = dict(seen.get(url) or {})
        if page is None or blocked(page):
            entry["error_at"] = stamp
            entry["errors"] = entry.get("errors", 0) + 1
            entry["error"] = "no response" if page is None else "blocked or empty page"
            if entry["errors"] >= 3:
                failing.append(url)
            seen[url] = entry
            continue
        lines = key_lines(page)[:MAX_LINES]
        fp = fingerprint(page)
        entry.update(read_at=stamp, errors=0)
        entry.pop("error", None)
        if not entry.get("fp"):
            entry.update(fp=fp, lines=lines)
        elif fp == entry["fp"]:
            entry.pop("pending_fp", None)
            entry["lines"] = lines
        elif entry.get("pending_fp") == fp:  # second read in a row with the new text: a real change
            entry.update(prev_lines=entry.get("lines") or [], lines=lines, fp=fp, changed_at=stamp)
            entry.pop("pending_fp", None)
            changed.append(url)
        else:
            entry["pending_fp"] = fp
        seen[url] = entry
    # A page read cleanly today, with no change since the fact was checked, confirms the fact: no
    # person or PR needed (Young, 11/19/2026: re-checks that change nothing skip the PR). Kept in Blob.
    confirmed = dict(prev.get("confirmed") or {})
    for slug, kinds in FACTS.items():
        for kind, f in kinds.items():
            page = seen.get(f["source"]) or {}
            clean = page.get("read_at", "")[:16] == stamp and not page.get("pending_fp")
            if clean and not (page.get("changed_at") and page["changed_at"][:10] > f["checked"]) and f.get("value") is not None:
                confirmed[f"{slug}|{kind}"] = now.date().isoformat()
    # A change stays in the queue until the facts on that page are re-checked after it.
    queue = []
    eff = {s: {k: dict(f, checked=last_checked(s, k, f, confirmed)) for k, f in kinds.items()} for s, kinds in FACTS.items()}
    due_now = {(s, k): d for s, k, d in due(now.date(), eff)}
    for slug, kinds in FACTS.items():
        for kind, f in kinds.items():
            page = seen.get(f["source"]) or {}
            moved = page.get("changed_at") and page["changed_at"][:10] > f["checked"]
            if not moved and (slug, kind) not in due_now:
                continue
            item = {"resort": slug, "fact": kind, "source": f["source"], "value": f.get("value"),
                    "checked": f["checked"], "reason": "changed" if moved else "due",
                    "overdue_days": due_now.get((slug, kind), 0)}
            if moved:
                old, new = set(page.get("prev_lines") or []), set(page.get("lines") or [])
                item.update(changed_at=page["changed_at"], added=sorted(new - old)[:10], removed=sorted(old - new)[:10])
            queue.append(item)
    queue.sort(key=lambda q: (q["reason"] != "changed", -q["overdue_days"], q["resort"], q["fact"]))
    status = {"generated": stamp, "pages": seen, "changed_today": changed, "failing": failing,
              "due": [{"resort": s, "fact": k, "overdue_days": d} for (s, k), d in due_now.items()], "queue": queue,
              "confirmed": confirmed}
    store.put_json("data/facts/status.json", status)
    return status


if __name__ == "__main__":  # python -m bcbot.facts [todo|due]
    import sys
    if (sys.argv[1:] or ["todo"])[0] == "due":
        for slug, kind, late in due():
            print(f"{slug:16} {kind:15} {late} days overdue")
    else:
        rows = todo()
        for slug, kind, where in rows:
            print(f"{slug:16} {kind:15} {where}")
        print(f"\n{len(rows)} missing facts across {len({r[0] for r in rows})} resorts")


# ---------- owner view: what we have, what's missing, how fresh (/admin "Resort facts") ----------

def grid(today=None, confirmed=None):
    """One row per resort and fact kind for the private admin table and its CSV export.
    status: "filled" (a value), "not_posted" (we checked and the resort hasn't posted it), "missing" (never checked).
    fresh: "ok", "due" (next check date has come) or "stale" (more than twice the check interval old)."""
    from . import resorts
    today = today or date.today()
    rows = []
    for slug, r in resorts.RESORTS.items():
        have = FACTS.get(slug) or {}
        for kind in LABELS:
            f = have.get(kind)
            row = {"resort": slug, "name": r["name"], "fact": kind, "label": LABELS[kind],
                   "stage": "live" if r["enabled"] else r.get("stage", "off")}
            if not f:
                rows.append(dict(row, status="missing", fresh="", value="", checked="", next_check="",
                                 source="", source_name="", maps=0, map_images=0))
                continue
            every = interval_days(kind, today)
            f = dict(f, checked=last_checked(slug, kind, f, confirmed))
            nxt = date.fromisoformat(f["checked"]) + timedelta(days=every)
            value = f.get("value")
            if kind == "trail_map":
                value = f.get("label") or value
            rows.append(dict(
                row, status="filled" if f.get("value") else "not_posted",
                fresh="stale" if stale(f, kind, today) else "due" if today >= nxt else "ok",
                value=value or f.get("note") or "", checked=f["checked"], next_check=nxt.isoformat(), every_days=every,
                source=f["source"], source_name=f.get("source_name", ""),
                maps=len(f.get("maps") or []), map_images=sum(1 for m in f.get("maps") or [] if m.get("image"))))
    return {"today": today.isoformat(), "kinds": list(LABELS), "labels": LABELS, "rows": rows}
