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
# Hand-checked facts for one resort. Shared facts (passes, blackout dates, announced dates) are
# generated below from one source each and filled in for every resort that has no curated value.
CURATED = {
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


# ---------- shared facts: one official source, many resorts ----------
# Re-checking one of these pages updates every resort that uses it. See docs/RESORT_FACTS.md.

CHECKED_SHARED = "2026-11-19"
EPIC_PASS = ("https://www.epicpass.com/passes/epic-pass.aspx", "Epic Pass: Epic Pass resort access")
EPIC_LOCAL = ("https://www.epicpass.com/passes/epic-local-pass.aspx", "Epic Pass: Epic Local Pass")
EPIC_PEAK = ("https://www.epicpass.com/info/peak-restricted-dates.aspx", "Epic Pass: Restricted Peak Dates")
EPIC_PEAK_DATES = "11/27 to 11/28/2026, 12/26 to 12/31/2026, 1/16/2027 and 2/13 to 2/14/2027"
IKON_COMPARE = ("https://www.ikonpass.com/en/compare-passes", "Ikon Pass: Compare 26/27 Passes")
IKON_BASE_BLACKOUTS = ("https://www.ikonpass.com/en/help/blackout-dates/what-are-the-ikon-base-pass-blackout-dates",
                       "Ikon Pass: Ikon Base Pass blackout dates")
IKON_BASE_DATES = "12/26 to 12/30/2026, 1/16 to 1/17/2027 and 2/13 to 2/14/2027"
IKON_DATES = ("https://www.ikonpass.com/en/opening-closing-dates", "Ikon Pass: Opening and Closing Dates")
VR_DATES = ("https://news.vailresorts.com/2026-08-18-Is-Winter-About-to-Show-Off-Vail-Resorts-Announces-2026-27-Opening-Dates-as-Super-El-Nino-Builds-Anticipation-for-Great-Powder",
            "Vail Resorts: 2026/27 opening dates")

# Epic access per resort, word for word from the Epic Pass and Epic Local Pass pages: (Epic Pass, Epic Local Pass).
EPIC_ACCESS = {
    "vail": ("unlimited, no blackout dates", "10 days total, shared with Beaver Creek and Whistler Blackcomb, not valid on peak dates"),
    "beaver-creek": ("unlimited, no blackout dates", "10 days total, shared with Vail and Whistler Blackcomb, not valid on peak dates"),
    "breckenridge": ("unlimited, no blackout dates", "unlimited, including peak dates"),
    "keystone": ("unlimited, no blackout dates", "unlimited, including peak dates"),
    "crested-butte": ("unlimited, no blackout dates", "unlimited, including peak dates"),
    "park-city": ("unlimited, no blackout dates", "unlimited, not valid on peak dates"),
    "telluride": ("7 days total, then 50% off lift tickets", None),
}
# Ikon access per resort from the Compare Passes page: (Ikon Pass, Ikon Base Pass, Ikon Session Pass); None = not included.
IKON_ACCESS = {
    "arapahoe-basin": ("unlimited", "unlimited", "2, 3 or 4 days"),
    "snowmass": ("7 days, shared across Aspen Mountain, Snowmass, Aspen Highlands and Buttermilk", "Snowmass only", "5 days"),
    "aspen-mountain": ("7 days, shared across Aspen Mountain, Snowmass, Aspen Highlands and Buttermilk", None, "5 days"),
    "aspen-highlands": ("7 days, shared across Aspen Mountain, Snowmass, Aspen Highlands and Buttermilk", None, "5 days"),
    "buttermilk": ("7 days, shared across Aspen Mountain, Snowmass, Aspen Highlands and Buttermilk", None, "5 days"),
    "eldora": ("unlimited", "unlimited", "2, 3 or 4 days"),
    "steamboat": ("unlimited", "5 days", "2, 3 or 4 days"),
    "winter-park": ("unlimited", "unlimited", "2, 3 or 4 days"),
    "copper": ("unlimited", "unlimited", "2, 3 or 4 days"),
    "alta": ("7 days, shared with Snowbird", None, None),
    "snowbird": ("7 days, shared with Alta", "5 days, Snowbird only", None),
    "brighton": ("7 days", "5 days", "2, 3 or 4 days"),
    "solitude": ("unlimited", "unlimited", "2, 3 or 4 days"),
    "deer-valley": ("7 days, lift reservations required", "3 days, lift reservations required", None),
    "snowbasin": ("7 days", None, None),
}
# Announced opening (and closing) days: slug -> (opening, closing, source).
ANNOUNCED = {
    "vail": ("2026-11-13", None, VR_DATES), "breckenridge": ("2026-11-06", None, VR_DATES),
    "park-city": ("2026-11-20", None, VR_DATES), "crested-butte": ("2026-11-25", None, VR_DATES),
    "keystone": ("2026-10-30", None, ("https://news.vailresorts.com/keystone-opening-2026", "Keystone: 2026/27 Opening Day")),
    "telluride": ("2026-12-05", "2027-04-04", ("https://tellurideskiresort.com/?faqs=how-can-i-submit-a-photo-for-my-pass-prior-to-arrival",
                                              "Telluride: 2026-27 winter season dates")),
    "aspen-mountain": ("2026-11-26", None, IKON_DATES), "snowmass": ("2026-11-26", None, IKON_DATES),
    "aspen-highlands": ("2026-12-12", None, IKON_DATES), "buttermilk": ("2026-12-12", None, IKON_DATES),
    "steamboat": ("2026-11-21", None, IKON_DATES), "alta": ("2026-11-20", None, IKON_DATES),
    "snowbird": ("2026-11-27", None, IKON_DATES), "solitude": ("2026-11-20", None, IKON_DATES),
    "deer-valley": ("2026-12-05", None, IKON_DATES), "snowbasin": ("2026-11-27", None, IKON_DATES),
}
# Trail map pages checked by hand (we link, never copy the art).
TRAIL_MAPS = {
    "vail": ("https://www.vail.com/the-mountain/about-the-mountain/trail-map.aspx", "Winter 2026/27 trail maps: Front Side, Back Bowls, Blue Sky (on vail.com)"),
    "breckenridge": ("https://www.breckenridge.com/the-mountain/about-the-mountain/trail-map.aspx", "Winter 2026/27 trail map (on breckenridge.com)"),
    "keystone": ("https://www.keystoneresort.com/the-mountain/about-the-mountain/trail-map.aspx", "Trail maps (on keystoneresort.com)"),
}
TELLURIDE_HOURS = "Base lifts 9 AM to 4 PM. The free gondola runs 6:30 AM to midnight, 7 days a week."


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
    if slug in TRAIL_MAPS:
        url, label = TRAIL_MAPS[slug]
        out["trail_map"] = _fact(url, (url, f"{name}: Trail and Mountain Maps"), label=label)
    if slug in EPIC_ACCESS:
        full, local = EPIC_ACCESS[slug]
        text = f"Epic Pass: {full}. " + (f"Epic Local Pass: {local}. " if local else f"The Epic Local Pass doesn't include {name}. ")
        text += "Epic Day Pass: not valid on peak dates."
        out["passes"] = _fact(text, EPIC_LOCAL if local else EPIC_PASS)
        on_peak = [p for p, rule in (("Epic Local Pass", local),) if rule and "not valid on peak" in rule]
        out["blackout_dates"] = _fact(f"{EPIC_PEAK_DATES}. These apply to the " + " and ".join(on_peak + ["Epic Day Pass"])
                                      + (". The full Epic Pass has none." if "unlimited" in full else "."), EPIC_PEAK)
    if slug in IKON_ACCESS:
        full, base, session = IKON_ACCESS[slug]
        bits = [f"Ikon Pass: {full}" + (", no blackout dates" if full == "unlimited" else "")]
        bits.append(f"Ikon Base Pass: {base}" + (", with blackout dates" if base else "") if base else f"The Ikon Base Pass doesn't include {name}")
        if session:
            bits.append(f"Ikon Session Pass: {session}")
        out["passes"] = _fact(". ".join(bits) + ".", IKON_COMPARE)
        out["blackout_dates"] = (_fact(f"{IKON_BASE_DATES} on the Ikon Base Pass. The full Ikon Pass has none.", IKON_BASE_BLACKOUTS) if base
                                 else _fact(f"None. The Ikon Pass has no blackout dates, and the Ikon Base Pass doesn't include {name}.", IKON_COMPARE))
    return out


def _build():
    from . import resorts
    out = {}
    for slug in resorts.RESORTS:
        name = resorts.RESORTS[slug]["name"]
        merged = dict(_shared(slug, name), **CURATED.get(slug, {}))
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
OPERATOR = {s: "vail-resorts" for s in ("beaver-creek", "vail", "breckenridge", "keystone", "crested-butte", "park-city")}


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
