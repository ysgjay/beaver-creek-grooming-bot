"""Resort facts: seasonal re-check schedule, page watch and the info section."""
import re
from datetime import date, datetime

from bcbot import facts, pages
from bcbot.store import LocalStore


def test_closing_dates_checked_every_two_days_from_march():
    assert facts.interval_days("closing_day", date(2027, 2, 28)) == 30
    assert facts.interval_days("closing_day", date(2027, 3, 1)) == 2
    assert facts.interval_days("closing_day", date(2027, 5, 31)) == 2
    assert facts.interval_days("closing_day", date(2027, 6, 1)) == 30
    assert facts.interval_days("opening_day", date(2026, 10, 1)) == 2
    assert facts.interval_days("lift_hours", date(2027, 1, 15)) == 7  # crosses New Year
    assert facts.interval_days("lift_hours", date(2027, 7, 15)) == 30


def test_due_list_follows_the_season():
    f = {"x": {"closing_day": {"checked": "2027-02-20", "source": "s"}}}
    assert facts.due(date(2027, 2, 25), f) == []          # winter: monthly
    assert facts.due(date(2027, 3, 2), f) == [("x", "closing_day", 8)]  # March: every 2 days
    assert facts.stale(f["x"]["closing_day"], "closing_day", date(2027, 3, 2))


def test_every_fact_has_a_source_and_checked_date():
    for slug, kinds in facts.FACTS.items():
        for kind, f in kinds.items():
            assert f["source"].startswith("https://") and date.fromisoformat(f["checked"]), (slug, kind)
            assert kind in facts.LABELS


def test_fingerprint_ignores_menus_but_sees_dates():
    a = "<nav>Lessons Rentals</nav><p>Opening day: November 25</p><script>var t=1</script>"
    b = "<nav>Lessons Rentals Tubing</nav><p>Opening day: November 25</p><script>var t=2</script>"
    c = "<nav>Lessons</nav><p>Opening day: November 27</p>"
    assert facts.fingerprint(a) == facts.fingerprint(b) != facts.fingerprint(c)


def test_watch_flags_changed_pages_after_two_reads(tmp_path):
    store = LocalStore(tmp_path)
    pages_now = {u: "<p>Opens November 25</p>" for kinds in facts.FACTS.values() for u in [f["source"] for f in kinds.values()]}
    s1 = facts.watch(store, pages_now.get, now=datetime(2026, 11, 20, 7, 30))
    assert s1["changed_today"] == []
    url = next(iter(pages_now))
    pages_now[url] = "<p>Opens November 27</p>"
    s2 = facts.watch(store, pages_now.get, now=datetime(2026, 11, 21, 7, 30))
    assert s2["changed_today"] == [] and s2["pages"][url].get("pending_fp")  # one read could be a promo
    s3 = facts.watch(store, pages_now.get, now=datetime(2026, 11, 22, 7, 30))
    assert s3["changed_today"] == [url] and s3["pages"][url]["changed_at"] == "2026-11-22T07:30"
    assert store.get_json("data/facts/status.json")["changed_today"] == [url]
    item = next(q for q in s3["queue"] if q["source"] == url)
    assert item["reason"] == "changed" and item["added"] == ["Opens November 27"] and item["removed"] == ["Opens November 25"]
    assert s3["queue"][0]["reason"] == "changed"  # changes sort ahead of routine re-checks


def test_watch_one_off_change_is_not_flagged(tmp_path):
    store = LocalStore(tmp_path)
    pages_now = {u: "<p>Opens November 25</p>" for kinds in facts.FACTS.values() for u in [f["source"] for f in kinds.values()]}
    facts.watch(store, pages_now.get, now=datetime(2026, 11, 20, 7, 30))
    url = next(iter(pages_now))
    pages_now[url] = "<p>Opens November 25</p><p>Flash sale ends 11/21</p>"
    facts.watch(store, pages_now.get, now=datetime(2026, 11, 21, 7, 30))
    pages_now[url] = "<p>Opens November 25</p>"
    s3 = facts.watch(store, pages_now.get, now=datetime(2026, 11, 22, 7, 30))
    assert s3["changed_today"] == [] and "pending_fp" not in s3["pages"][url]


def test_watch_treats_bot_walls_as_errors_and_flags_3_days(tmp_path):
    store = LocalStore(tmp_path)
    pages_now = {u: "<p>Opens November 25</p>" for kinds in facts.FACTS.values() for u in [f["source"] for f in kinds.values()]}
    facts.watch(store, pages_now.get, now=datetime(2026, 11, 20, 7, 30))
    url = next(iter(pages_now))
    pages_now[url] = "<title>Just a moment...</title><p>Checking your browser</p>"
    for day in (21, 22):
        s = facts.watch(store, pages_now.get, now=datetime(2026, 11, day, 7, 30))
        assert s["changed_today"] == [] and url not in s["failing"]
    s = facts.watch(store, pages_now.get, now=datetime(2026, 11, 23, 7, 30))
    assert url in s["failing"] and s["pages"][url]["errors"] == 3 and s["pages"][url]["fp"]
    assert facts.blocked("<div id=root></div>") and not facts.blocked("<p>Lifts 9 AM to 4 PM</p>")


def test_guide_shows_sourced_facts_and_faq():
    html = pages.guide_page("copper", {})
    assert "<title>Copper Mountain trail map, opening day, blackout dates, lift hours, ticket prices and lessons 2026/27 | 0xSnow</title>" in html
    assert "Base area lifts 9 AM to 4 PM" in html and "coppercolorado.com/the-mountain/trail-lift-info/lift-hours/" in html
    assert "checked 11/19" in html and '"@type":"FAQPage"' in html
    assert "Not announced yet" in html  # closing day
    assert "11/6" not in html  # the registry's old opening date is replaced by the sourced one
    bc = pages.guide_page("beaver-creek", {})
    assert "Winter 2026/27 trail map (PDF, on beavercreek.com)" in bc and "Wednesday 11/25/2026" in bc
    assert "When does the Vail grooming report come out?" in pages.guide_page("vail", {})  # kept in the FAQ


def test_passes_tickets_and_lessons_section():
    assert facts.interval_days("blackout_dates", date(2027, 3, 10)) == 2
    assert facts.interval_days("passes", date(2027, 1, 10)) == 30
    assert facts.interval_days("lift_tickets", date(2027, 1, 10)) == 7
    bc = pages.guide_page("beaver-creek", {})
    assert "Beaver Creek blackout dates and passes</h2>" in bc and "Beaver Creek lift tickets and lessons</h2>" in bc
    assert "Sat 12/26 to Thu 12/31" in bc and 'href="/passes/epic-blackout-dates"' in bc and "$211 online" in bc and "Epic Ascent" in bc
    assert "What are the Beaver Creek blackout dates for 2026/27?" in bc
    cu = pages.guide_page("copper", {})
    assert "No fixed price posted" in cu and "at least 1 day ahead" in cu and "Ikon Base Pass" in cu
    assert "How much is a lift ticket at Copper Mountain?" in cu


def test_shared_pass_facts_cover_every_resort():
    from bcbot import resorts
    assert set(resorts.enabled()) <= set(facts.FACTS)
    for slug in resorts.enabled():  # shadow-mode resorts get their pass facts before launch
        assert "passes" in facts.FACTS[slug] and "blackout_dates" in facts.FACTS[slug], slug
    assert "Ikon Pass: 7 days, shared with Snowbird" in facts.FACTS["alta"]["passes"]["value"]
    assert facts.FACTS["vail"]["opening_day"]["value"] == "2026-11-13"
    # hand-checked facts win over the shared tables
    assert facts.FACTS["copper"]["opening_day"]["value"] == "2026-11-08"


def test_guide_title_follows_the_facts_it_has():
    assert facts.topics("brighton") == ("opening day, closing day, lift hours, passes, blackout dates, "
                                        "lift ticket prices and lessons")  # no trail map posted
    html = pages.guide_page("alta", {})
    assert "<title>Alta trail map, opening day, blackout dates, lift hours, ticket prices and lessons 2026/27 | 0xSnow</title>" in html
    assert '<h1 class="page">Alta guide: trail map, opening day, blackout dates and more 2026/27</h1>' in html
    assert "doesn&#x27;t include Alta" in html and "Not included" in html


def test_guide_leads_with_snow_report_and_quick_answers():
    day = {"date": "2026-11-19", "resort": {"last_24h_in": 4, "base_in": 22}}
    html = pages.guide_page("vail", {}, day, today=date(2026, 11, 19))
    assert html.index("Vail snow report today") < html.index("Quick answers") < html.index("Vail blackout dates and passes")
    assert "Open since Fri 11/13" in html and "Fri 11/27 to Sat 11/28" in html and 'class="next"' in html
    assert 'href="/resorts/vail"' in html and "Official map" in html and "5 cams" in html
    on = pages.guide_page("vail", {}, day, today=date(2026, 12, 27))
    assert "Today (12/27) is a blackout date at Vail" in on and 'class="on"' in on
    assert "The daily Alta report starts on opening day." in pages.guide_page("alta", {}, None, today=date(2026, 11, 19))


def test_todo_points_at_operator_pages(monkeypatch):
    monkeypatch.setitem(facts.FACTS, "park-city", {k: v for k, v in facts.FACTS["park-city"].items() if k != "lift_tickets"})
    monkeypatch.setitem(facts.FACTS, "alta", {k: v for k, v in facts.FACTS["alta"].items() if k != "lift_tickets"})
    rows = {(s, k): w for s, k, w in facts.todo()}
    assert rows[("park-city", "lift_tickets")] == "https://www.parkcitymountain.com/plan-your-trip/lift-access/tickets.aspx"
    assert ("copper", "lessons") not in rows
    assert "find the official page" in rows[("alta", "lift_tickets")]


def test_lift_hours_sit_in_the_top_row():
    html = pages.guide_page("alta", {}, None, today=date(2026, 11, 19))
    assert html.index('id="hours"') < html.index("Quick answers") and "Collins and Sunnyside run to 4:30 PM" in html
    assert '<nav class="chips" aria-label="On this page"><a href="#hours">Lift hours</a>' in html
    assert 'aria-current="page"><span class="full">Resort guide</span>' in html and "scroll-padding-top" in html
    assert 'href="/resorts/alta/guide" aria-current="page"><span class="full">Resort guide' in html
    assert "Snowbird hasn&#x27;t posted 2026/27 lift hours" in pages.guide_page("snowbird", {}, None, today=date(2026, 11, 19))


def test_multi_map_resorts_show_every_map_from_the_resorts_own_server():
    vail = facts.FACTS["vail"]["trail_map"]["maps"]
    assert [m["label"] for m in vail] == ["Front Side", "Back Bowls", "Blue Sky Basin"]
    assert all(m["image"].startswith("https://scene7.vailresorts.com/") for m in vail)
    html = pages.guide_page("vail", {}, None, today=date(2026, 11, 19))
    assert html.count('referrerpolicy="no-referrer"') == 3 and "Blue Sky Basin trail map" in html
    assert len(facts.FACTS["arapahoe-basin"]["trail_map"]["maps"]) == 4
    for kinds in facts.FACTS.values():  # every map has a label and an image or PDF on the resort's site
        for m in (kinds.get("trail_map") or {}).get("maps") or []:
            assert m["label"] and (m.get("image") or m.get("pdf")) and m.get("season")


def test_admin_grid_lists_every_resort_and_fact():
    g = facts.grid(date(2026, 11, 19))
    from bcbot import resorts
    assert len(g["rows"]) == len(resorts.RESORTS) * len(facts.LABELS)
    row = {(r["resort"], r["fact"]): r for r in g["rows"]}
    assert row[("brighton", "trail_map")]["status"] == "missing"
    assert row[("snowbird", "lift_hours")]["status"] == "not_posted"
    assert row[("vail", "trail_map")]["maps"] == 3 and row[("vail", "trail_map")]["map_images"] == 3
    assert row[("vail", "lift_tickets")]["fresh"] == "ok"
    assert facts.grid(date(2027, 3, 10))["rows"][0]["fresh"] in ("due", "stale")


def test_registry_opening_day_matches_the_checked_fact():
    """The registry date gates sends and the guide shows the fact: they must agree when the resort has set one."""
    from bcbot import resorts
    for slug in resorts.enabled():
        v = facts.FACTS.get(slug, {}).get("opening_day", {}).get("value")
        if v:
            assert resorts.RESORTS[slug]["opening_day"] == v, slug


def test_shadow_resorts_stay_off_public_endpoints(monkeypatch):
    from bcbot import resorts, stats
    shadow = resorts.shadow()[0]
    hit = stats.clean_hit({"v": "a" * 16, "t": "report", "r": shadow}, resorts.enabled())
    assert hit is None or hit["resort"] == ""                          # never counted as a shadow resort
    from bcbot import audit
    monkeypatch.setenv("STORE_MODE", "shadow")
    monkeypatch.setattr("bcbot.db.url", lambda: "postgres://x")
    assert audit.record(shadow, {}, {}, {}, {}, None, False) is None   # never touches Neon in shadow mode


def test_scene7_tiles_load_small_and_link_the_full_image():
    from bcbot import guide
    html = guide.map_gallery(facts.FACTS["vail"]["trail_map"])
    assert "wid=800" in html and "wid=4000" in html


def test_coverage_lists_every_resort_with_cams_and_report_source():
    from bcbot import resorts
    cv = {r["resort"]: r for r in resorts.coverage()}
    assert set(cv) == set(resorts.RESORTS)
    assert cv["jackson-hole"]["cams"] == 11 and cv["jackson-hole"]["stake"] and cv["jackson-hole"]["report"] == "Resort feed"
    assert cv["big-sky"]["report"] == "Boyne feed" and cv["big-sky"]["grooming"]
    assert cv["copper"]["report"] == "POWDR feed" and cv["killington"]["report"] == "Report page"
    assert cv["beaver-creek"]["report"] == "Vail page" and cv["mammoth"]["report"] == ""
    assert cv["mammoth"]["stage"] == "shadow" and cv["vail"]["stage"] == "live"


def test_watch_confirms_unchanged_facts_without_a_pr(tmp_path):
    store = LocalStore(tmp_path)
    pages_now = {u: "<p>Opens November 25</p>" for kinds in facts.FACTS.values() for u in [f["source"] for f in kinds.values()]}
    later = datetime(2026, 12, 30, 7, 30)  # every fact is due by now
    facts.watch(store, pages_now.get, now=datetime(2026, 11, 20, 7, 30))
    url = next(iter(pages_now))
    pages_now[url] = None  # this page fails today, so its facts can't be confirmed
    s = facts.watch(store, pages_now.get, now=later)
    slug, kind, f = next((s_, k, f) for s_, ks in facts.FACTS.items() for k, f in ks.items() if f.get("value") is not None and f["source"] != url)
    assert s["confirmed"][f"{slug}|{kind}"] == "2026-12-30"
    assert not any(q["resort"] == slug and q["fact"] == kind for q in s["queue"])
    blocked = [(s_, k) for s_, ks in facts.FACTS.items() for k, f in ks.items() if f["source"] == url]
    assert all(any(q["resort"] == b[0] and q["fact"] == b[1] for q in s["queue"]) for b in blocked)
    row = next(r for r in facts.grid(today=later.date(), confirmed=s["confirmed"])["rows"]
               if r["resort"] == slug and r["fact"] == kind)
    assert row["checked"] == "2026-12-30" and row["fresh"] == "ok"


def _season_ok(iso, months):
    return date.fromisoformat(iso).month in months


def test_fact_values_pass_sanity_checks():
    """Guards automated re-check PRs: a bad value fails here before it can reach the site."""
    for slug, kinds in facts.FACTS.items():
        o, c = (kinds.get("opening_day") or {}).get("value"), (kinds.get("closing_day") or {}).get("value")
        if o:
            assert _season_ok(o, {9, 10, 11, 12, 1}), (slug, o)
        if c:
            assert _season_ok(c, {3, 4, 5, 6, 7}), (slug, c)
        if o and c:
            assert o < c, slug
        for kind, f in kinds.items():
            v = f.get("value")
            if v is None:
                assert f.get("note") or kind in ("closing_day", "opening_day"), (slug, kind)  # blank needs a reason
                continue
            if kind == "lift_hours":
                assert re.search(r"\d{1,2}(:\d\d)?\s?(AM|PM|am|pm|noon|midnight)|\d{1,2} to \d", v), (slug, v)
            if kind == "lift_tickets":
                assert "$" in v, (slug, v)
            if kind == "trail_map":
                assert v.startswith("https://"), (slug, v)
