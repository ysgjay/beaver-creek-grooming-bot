"""Resort facts: seasonal re-check schedule, page watch and the info section."""
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


def test_watch_flags_changed_pages(tmp_path):
    store = LocalStore(tmp_path)
    pages_now = {u: "<p>Opens November 25</p>" for kinds in facts.FACTS.values() for u in [f["source"] for f in kinds.values()]}
    s1 = facts.watch(store, pages_now.get, now=datetime(2026, 11, 20, 7, 30))
    assert s1["changed_today"] == []
    url = next(iter(pages_now))
    pages_now[url] = "<p>Opens November 27</p>"
    s2 = facts.watch(store, pages_now.get, now=datetime(2026, 11, 21, 7, 30))
    assert s2["changed_today"] == [url] and s2["pages"][url]["changed_at"] == "2026-11-21T07:30"
    assert store.get_json("data/facts/status.json")["changed_today"] == [url]


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
    assert "<h2>Beaver Creek blackout dates and passes</h2>" in bc and "<h2>Beaver Creek lift tickets and lessons</h2>" in bc
    assert "Sat 12/26 to Thu 12/31" in bc and 'href="/passes/epic-blackout-dates"' in bc and "$211 online" in bc and "Epic Ascent" in bc
    assert "What are the Beaver Creek blackout dates for 2026/27?" in bc
    cu = pages.guide_page("copper", {})
    assert "No fixed price posted" in cu and "at least 1 day ahead" in cu and "Ikon Base Pass" in cu
    assert "How much is a lift ticket at Copper Mountain?" in cu


def test_shared_pass_facts_cover_every_resort():
    from bcbot import resorts
    assert set(facts.FACTS) == set(resorts.RESORTS)
    for slug in resorts.RESORTS:
        assert "passes" in facts.FACTS[slug] and "blackout_dates" in facts.FACTS[slug], slug
    assert "Ikon Pass: 7 days, shared with Snowbird" in facts.FACTS["alta"]["passes"]["value"]
    assert facts.FACTS["vail"]["opening_day"]["value"] == "2026-11-13"
    # hand-checked facts win over the shared tables
    assert facts.FACTS["copper"]["opening_day"]["value"] == "2026-11-08"


def test_guide_title_follows_the_facts_it_has():
    assert facts.topics("alta") == "opening day, closing day, passes and blackout dates"
    html = pages.guide_page("alta", {})
    assert "<title>Alta opening day and blackout dates 2026/27 | 0xSnow</title>" in html
    assert '<h1 class="page">Alta guide: opening day and blackout dates 2026/27</h1>' in html
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


def test_todo_points_at_operator_pages():
    rows = {(s, k): w for s, k, w in facts.todo()}
    assert rows[("park-city", "lift_hours")] == "https://www.parkcitymountain.com/explore-the-resort/about-the-resort/hours-of-operation.aspx"
    assert ("copper", "lessons") not in rows
    assert "find the official page" in rows[("alta", "lift_hours")]
