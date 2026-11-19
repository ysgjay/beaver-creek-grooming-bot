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

# value: what the page shows. None = not announced yet (the page says so, with the source).
# Dates are ISO strings; the page renders them as weekday + MM/DD.
FACTS = {
    "beaver-creek": {
        "opening_day": {"value": "2026-11-25", "checked": "2026-11-19",
                        "source": "https://www.beavercreek.com/explore-the-resort/about-the-resort/hours-of-operation.aspx",
                        "source_name": "Beaver Creek: Hours of Operation"},
        "closing_day": {"value": None, "checked": "2026-11-19",
                        "source": "https://www.beavercreek.com/explore-the-resort/about-the-resort/hours-of-operation.aspx",
                        "source_name": "Beaver Creek: Hours of Operation"},
        "lift_hours": {"value": None, "checked": "2026-11-19",
                       "note": "Lift hours for 2026/27 aren't posted yet. The resort says operations begin 11/25.",
                       "source": "https://www.beavercreek.com/explore-the-resort/about-the-resort/hours-of-operation.aspx",
                       "source_name": "Beaver Creek: Hours of Operation"},
        "trail_map": {"value": "https://www.beavercreek.com/-/aemasset/digital-experience-assets-library/destination-resorts/"
                               "beaver-creek/mountain-operations/winter-2026-2027/20261110_BC_winter-trail_map_001.pdf",
                      "label": "Winter 2026/27 trail map (PDF, on beavercreek.com)", "checked": "2026-11-19",
                      "source": "https://www.beavercreek.com/the-mountain/about-the-mountain/trail-map.aspx",
                      "source_name": "Beaver Creek: Trail and Mountain Maps"},
        "passes": {"value": "Epic Pass: unlimited, no blackout dates. Epic Local Pass: 10 days total, shared with Vail "
                            "and Whistler Blackcomb, not valid on peak dates. Epic Day Pass: not valid on peak dates.",
                   "checked": "2026-11-19", "source": "https://www.epicpass.com/passes/epic-local-pass.aspx",
                   "source_name": "Epic Pass: Epic Local Pass"},
        "blackout_dates": {"value": "11/27 to 11/28/2026, 12/26 to 12/31/2026, 1/16/2027 and 2/13 to 2/14/2027. "
                                    "These apply to the Epic Local Pass and Epic Day Pass. The full Epic Pass has none.",
                           "checked": "2026-11-19", "source": "https://www.epicpass.com/info/peak-restricted-dates.aspx",
                           "source_name": "Epic Pass: Restricted Peak Dates"},
        "lift_tickets": {"value": "$211 online for a 1-day adult ticket (ages 13 to 64) on opening day, 11/25, against $250 "
                                  "full price. Child (5 to 12): $146. Prices change by date, and buying 4+ weeks ahead saves the most.",
                         "checked": "2026-11-19", "source": "https://www.beavercreek.com/plan-your-trip/lift-access/tickets.aspx",
                         "source_name": "Beaver Creek: Lift Tickets"},
        "lessons": {"value": "Child group lessons, adult group lessons (including first-time lessons) and Epic Ascent "
                             "private lessons. Kids save 20% on the third straight day of group lessons and every day after, "
                             "and Epic pass holders get 20% off group lessons.",
                    "checked": "2026-11-19", "source": "https://www.beavercreek.com/plan-your-trip/ski-and-ride-lessons.aspx",
                    "source_name": "Beaver Creek: Ski & Snowboard Lessons"},
    },
    "copper": {
        "opening_day": {"value": "2026-11-08", "checked": "2026-11-19",
                        "source": "https://www.coppercolorado.com/events-activities/events-calendar/opening-day-2627/",
                        "source_name": "Copper Mountain: 26/27 Opening Day"},
        "closing_day": {"value": None, "checked": "2026-11-19",
                        "source": "https://www.coppercolorado.com/events-activities/events-calendar/closing-weekend/",
                        "source_name": "Copper Mountain: Closing Weekend",
                        "note": "Copper's closing weekend page still shows last season's dates."},
        "lift_hours": {"value": "Base area lifts 9 AM to 4 PM. Storm King, Resolution, Blackjack and Mountain Chief "
                                "close at 3 PM; Timberline Express, Excelerator, Sierra, Lumberjack and Rendezvous at "
                                "3:30 PM; Three Bears at 2:30 PM. Fast Tracks gets 30 minutes early on American Eagle.",
                       "checked": "2026-11-19",
                       "source": "https://www.coppercolorado.com/the-mountain/trail-lift-info/lift-hours/",
                       "source_name": "Copper Mountain: Lift Hours"},
        "trail_map": {"value": "https://www.coppercolorado.com/the-mountain/trail-area-maps/winter-trail-map/",
                      "label": "2026/27 winter trail maps: Frontside, Copper Bowl, Spaulding Bowl (on coppercolorado.com)",
                      "checked": "2026-11-19",
                      "source": "https://www.coppercolorado.com/the-mountain/trail-area-maps/winter-trail-map/",
                      "source_name": "Copper Mountain: Winter Trail Map"},
        "passes": {"value": "Ikon Pass: unlimited, no blackout dates. Ikon Base Pass: unlimited, with blackout dates. "
                            "Ikon Session Pass: 2, 3 or 4 days total. Copper also sells its own Copper Season Pass.",
                   "checked": "2026-11-19", "source": "https://www.ikonpass.com/en/compare-passes",
                   "source_name": "Ikon Pass: Compare 26/27 Passes"},
        "blackout_dates": {"value": "12/26 to 12/30/2026, 1/16 to 1/17/2027 and 2/13 to 2/14/2027 on the Ikon Base Pass. "
                                    "The full Ikon Pass has none.",
                           "checked": "2026-11-19",
                           "source": "https://www.ikonpass.com/en/help/blackout-dates/what-are-the-ikon-base-pass-blackout-dates",
                           "source_name": "Ikon Pass: Ikon Base Pass blackout dates"},
        "lift_tickets": {"value": None, "note": "Copper prices tickets by date and doesn't list a fixed price. Buy online at "
                                                "least 1 day ahead for the online price; walk-up window rates may be higher.",
                         "checked": "2026-11-19", "source": "https://www.coppercolorado.com/tickets-passes/lift-tickets/tickets/",
                         "source_name": "Copper Mountain: Lift Tickets"},
        "lessons": {"value": "Adult group lessons (18+), youth group lessons (3 to 17), private and family private lessons, "
                             "adult and youth seasonal programs, Copper Guides, Woodward park privates, adult clinics and "
                             "adaptive lessons.",
                    "checked": "2026-11-19", "source": "https://www.coppercolorado.com/lessons-rentals/lessons/",
                    "source_name": "Copper Mountain: Lessons & Programs"},
    },
}

LABELS = {"opening_day": "Opening day", "closing_day": "Closing day", "lift_hours": "Lift hours", "trail_map": "Trail map",
          "passes": "Passes", "blackout_dates": "Blackout dates", "lift_tickets": "Lift tickets", "lessons": "Lessons"}


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


def stale(f, kind, today=None):
    """Shown on the page when a fact is more than twice its check interval old."""
    today = today or date.today()
    return (today - date.fromisoformat(f["checked"])).days > 2 * interval_days(kind, today)


# ---------- page watch ----------

KEY_LINE = re.compile(r"(open|clos|hours|season|\b\d{1,2}(:\d\d)?\s?(am|pm)\b|\b\d{1,2}/\d{1,2}\b|"
                      r"january|february|march|april|may|june|november|december)", re.I)


def fingerprint(page_html):
    """Hash only the lines that carry dates and hours, so menus and promos don't trip it."""
    text = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", page_html or "")
    text = html.unescape(re.sub(r"(?s)<[^>]+>", "\n", text))
    lines = sorted({ln.strip() for ln in text.splitlines() if ln.strip() and len(ln.strip()) < 300 and KEY_LINE.search(ln)})
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16]


def watch(store, fetch, now=None):
    """Read every source page once, compare with the last fingerprint, and write the status file.
    `fetch(url) -> html or None`. Returns the status written."""
    now = now or datetime.now()
    prev = store.get_json("data/facts/status.json", {}) or {}
    seen = dict(prev.get("pages") or {})
    changed = []
    for url in sorted({f["source"] for kinds in FACTS.values() for f in kinds.values()}):
        page = fetch(url)
        if page is None:
            seen.setdefault(url, {})["error_at"] = now.isoformat(timespec="minutes")
            continue
        fp = fingerprint(page)
        old = (seen.get(url) or {}).get("fp")
        entry = {"fp": fp, "read_at": now.isoformat(timespec="minutes"),
                 "changed_at": (seen.get(url) or {}).get("changed_at")}
        if old and old != fp:
            entry["changed_at"] = now.isoformat(timespec="minutes")
            changed.append(url)
        seen[url] = entry
    status = {"generated": now.isoformat(timespec="minutes"), "pages": seen, "changed_today": changed,
              "due": [{"resort": s, "fact": k, "overdue_days": d} for s, k, d in due(now.date())]}
    store.put_json("data/facts/status.json", status)
    return status
