"""Public report pages (bcbot/pages.py) and the archive index."""
import json
import re

from bcbot import pages
from bcbot.store import LocalStore, resort_store

DAY = {
    "date": "2026-11-18", "generated": "2026-11-18T06:50",
    "grooming": {"new_map": True, "image": "maps/vail/2026-11-18.jpg",
                 "runs": {"groomers_of_the_day": ["Born Free", "Riva Ridge"], "overnight": ["Born Free", "Riva Ridge", "Swingsville"],
                          "morning": ["Lodgepole"], "map_date": "November 18, 2026"}},
    "resort": {"last_24h_in": 3, "base_in": 18, "season_in": 31, "updated_time": "6:42 AM"},
    "forecast": {"days": [{"date": "2026-11-18", "snow": 2.0, "low": 1, "high": 4}], "next_1_5": 4, "next_1_5_range": [2, 7]},
    "hourly": {"hours": [{"time": f"2026-11-18T{h:02d}:00", "temp": 20 + h - 8, "feels": 10 + h - 8, "gust": 10 + h} for h in range(8, 17)]},
    "delivery": {"sent_at": "2026-11-18T06:55:00-07:00"},
}


def test_summary_uses_only_real_numbers():
    s = pages.summary(dict(DAY, resort_name="Vail"))
    assert s[0] == "Vail snow report for Wednesday 11/18: 4 runs groomed, including Born Free, Riva Ridge."
    assert 'The resort reports 3" of new snow in the last 24 hours, 18" base and 31" so far this season.' in s
    assert "The snow report posted at 6:42 AM." in s
    assert any(x.startswith("Expect 20°F at 8 AM") and "gusts to 26 mph" in x for x in s)
    assert 'The next 5 days look like 2 to 7" of snow, most likely 4".' in s
    bare = pages.summary({"date": "2026-11-18", "resort_name": "Alta"})
    assert bare == ["Alta snow report for Wednesday 11/18."]


def test_resort_page_is_crawlable_html_with_seo_tags():
    html = pages.resort_page("vail", DAY, ["2026-11-18", "2026-11-17", "2026-11-16"])
    assert "<title>Vail snow report today (11/18): grooming and forecast | 0xSnow</title>" in html
    assert "Vail trail map" in html and "Epic Pass blackout dates" in html and "Grooming map PDF" in html
    assert '<link rel="canonical" href="https://snow.0xm.studio/resorts/vail">' in html
    assert "4 runs groomed" in html and "Born Free" in html and "maps/vail/2026-11-18.jpg" in html
    assert 'href="/resorts/vail/2026-11-17"' in html and 'href="/resorts/vail/2026-11-18"' not in html
    assert "not affiliated" in html and "og:image" in html
    assert "&#847;" not in html  # no hidden email preheader on the web
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html):
        json.loads(block)


def test_dated_post_has_its_own_canonical_and_blogposting():
    html = pages.resort_page("vail", DAY, ["2026-11-18"], dated=True)
    assert '<link rel="canonical" href="https://snow.0xm.studio/resorts/vail/2026-11-18">' in html
    assert '"@type":"BlogPosting"' in html and "Vail snow report, Wed 11/18" in html


def test_archive_index_backfills_from_listing_then_appends(tmp_path):
    store = LocalStore(tmp_path)
    rs = resort_store("vail", store)
    for d in ["2026-11-16", "2026-11-17"]:
        rs.put_json(f"data/days/{d}.json", {"date": d})
    assert pages.post_dates(store, "vail") == ["2026-11-17", "2026-11-16"]
    assert pages.add_post(store, "vail", "2026-11-18") == ["2026-11-18", "2026-11-17", "2026-11-16"]
    assert rs.get_json("data/posts.json")["dates"][0] == "2026-11-18"
    # The default resort's folder is the unprefixed one; other resorts' folders don't leak in.
    assert pages.post_dates(store, "beaver-creek") == []


def test_sitemap_and_hub_list_every_resort(tmp_path):
    store = LocalStore(tmp_path)
    pages.add_post(store, "vail", "2026-11-18")
    xml = pages.sitemap(store)
    assert "<loc>https://snow.0xm.studio/resorts/vail/2026-11-18</loc><lastmod>2026-11-18</lastmod>" in xml
    assert "<loc>https://snow.0xm.studio/resorts/alta</loc>" in xml
    hub = pages.hub_page()
    assert 'href="/resorts/snowbird"' in hub and "<h2>Utah</h2>" in hub and "<h2>Colorado</h2>" in hub


def test_valid_date_rejects_junk():
    assert pages.valid_date("2026-11-18") and not pages.valid_date("2026-11-8") and not pages.valid_date("../x")


def test_post_is_frozen_at_send_and_resort_page_uses_it(tmp_path):
    store = LocalStore(tmp_path)
    rs = resort_store("vail", store)
    pages.add_post(store, "vail", "2026-11-18", dict(DAY, note="sent"), ping=False)
    rs.put_json("data/days/2026-11-18.json", dict(DAY, note="afternoon"))
    rs.put_json("data/latest.json", dict(DAY, note="afternoon"))
    assert pages.post_day(store, "vail", "2026-11-18")["note"] == "sent"
    assert pages.latest_day(store, "vail")["note"] == "sent"
    rs.put_json("data/latest.json", dict(DAY, date="2026-11-19", note="next morning, not sent yet"))
    assert pages.latest_day(store, "vail")["note"] == "next morning, not sent yet"


def test_indexnow_only_from_production(monkeypatch):
    calls = []
    monkeypatch.setattr("bcbot.util.http", lambda: type("H", (), {"post": lambda self, url, **k: calls.append((url, k)) or type("R", (), {"status_code": 200})()})())
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    assert pages.indexnow(["https://snow.0xm.studio/resorts/vail"]) is None and not calls
    monkeypatch.setenv("VERCEL_ENV", "production")
    assert pages.indexnow(["https://snow.0xm.studio/resorts/vail"]) == 200
    body = calls[0][1]["json"]
    assert calls[0][0] == "https://api.indexnow.org/indexnow" and body["host"] == "snow.0xm.studio"
    assert body["keyLocation"].endswith(pages.INDEXNOW_KEY + ".txt")


def test_indexnow_key_file_is_served():
    from pathlib import Path
    assert (Path(__file__).parent.parent / "public" / f"{pages.INDEXNOW_KEY}.txt").read_text().strip() == pages.INDEXNOW_KEY


def test_region_page_sorts_by_new_snow(tmp_path):
    store = LocalStore(tmp_path)
    resort_store("vail", store).put_json("data/latest.json", dict(DAY, resort={"last_24h_in": 3, "base_in": 18}))
    resort_store("copper", store).put_json("data/latest.json", dict(DAY, resort={"last_24h_in": 7, "base_in": 20}))
    html = pages.region_page(store, "colorado")
    assert "<h1 class=\"page\">Colorado snow report today</h1>" in html
    assert "Most new snow: Copper Mountain 7&quot;, Vail 3&quot;." in html
    assert html.index("/resorts/copper") < html.index("/resorts/vail\">")
    assert "/resorts/alta\"" not in html  # Utah resorts stay on the Utah page


def test_feeds_are_valid_rss(tmp_path):
    import xml.etree.ElementTree as ET
    store = LocalStore(tmp_path)
    pages.add_post(store, "vail", "2026-11-17", ping=False)
    pages.add_post(store, "vail", "2026-11-18", ping=False)
    one = ET.fromstring(pages.feed_xml(store, "vail"))
    items = one.findall("./channel/item")
    assert [i.findtext("link") for i in items] == ["https://snow.0xm.studio/resorts/vail/2026-11-18",
                                                   "https://snow.0xm.studio/resorts/vail/2026-11-17"]
    assert items[0].findtext("pubDate").endswith("-0700")
    everything = ET.fromstring(pages.feed_xml(store))
    assert len(everything.findall("./channel/item")) == 1


def test_guide_uses_posting_study_medians():
    summary = {"changes": [
        {"resort": "vail", "source": "grooming", "day": "2026-11-16", "at": "05:10"},
        {"resort": "vail", "source": "grooming", "day": "2026-11-16", "at": "06:40"},
        {"resort": "vail", "source": "grooming", "day": "2026-11-17", "at": "05:20"},
        {"resort": "vail", "source": "grooming", "day": "2026-11-18", "at": "05:30"},
        {"resort": "vail", "source": "snow", "day": "2026-11-17", "at": "05:35"},
        {"resort": "vail", "source": "snow", "day": "2026-11-17", "at": "21:00"},
        {"resort": "alta", "source": "snow", "day": "2026-11-17", "at": "04:00"}]}
    assert pages.posting_times(summary, "vail") == {"grooming": {"time": "5:20 AM", "days": 3}, "snow": {"time": "5:35 AM", "days": 1}}
    html = pages.guide_page("vail", summary)
    assert "When does the Vail grooming report come out?" in html
    assert "usually lands around 5:20 AM" in html and "grooming map each night as a PDF" in html
    assert "still measuring" in pages.guide_page("alta", {})


def test_report_page_is_laid_out_for_the_web():
    day = dict(DAY, grooming=dict(DAY["grooming"], runs=dict(DAY["grooming"]["runs"], areas=None)))
    html = pages.resort_page("vail", day, ["2026-11-18"])
    assert 'class="wrap wide"' in html and '<article class="rp">' in html
    for h in ("<h2>Grooming</h2>", "<h2>First chair to last</h2>", "<h2>Snow forecast</h2>"):
        assert h in html
    assert '<ul class="gotd"><li>Born Free</li><li>Riva Ridge</li></ul>' in html
    assert "<h3>Groomed overnight</h3><ul><li>Born Free</li><li>Riva Ridge</li><li>Swingsville</li></ul>" in html
    assert "<h3>Groomed this morning</h3><ul><li>Lodgepole</li></ul>" in html
    assert 'Open full size</a>' in html and 'alt="Grooming map for Vail, 11/18"' in html
    assert '<th scope="row">Gust</th>' in html and "<dt>Base</dt><dd>18&quot;</dd>" not in html and "<dt>Base</dt><dd>18\"</dd>" in html
    assert "role=\"presentation\"" not in html  # no email layout tables on the web


def test_report_page_without_map_or_grooming():
    day = {"date": "2026-11-18", "resort": {"last_24h_in": 0}}
    html = pages.resort_page("alta", day, ["2026-11-18"])
    assert "hasn't posted grooming for this day" in html and "First chair to last" not in html


def test_pass_pages_answer_is_today_blacked_out():
    from datetime import date
    assert pages.pass_status("epic-blackout-dates", date(2026, 11, 27))[0] is True
    on, nxt = pages.pass_status("epic-blackout-dates", date(2026, 11, 19))
    assert on is False and nxt[0] == "2026-11-27"
    assert pages.pass_status("ikon-blackout-dates", date(2027, 3, 1)) == (False, None)
    html = pages.pass_page("epic-blackout-dates", date(2026, 11, 19))
    assert "<h1 class=\"page\">Epic Pass blackout dates 2026/27</h1>" in html
    assert "The next one is Fri 11/27 to Sat 11/28 (Thanksgiving), 8 days away." in html
    assert "restricted peak dates" in html and 'href="/resorts/vail"' in html
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html):
        json.loads(block)
    html = pages.pass_page("ikon-blackout-dates", date(2026, 12, 27))
    assert "Yes. Today (12/27) is a blackout date for the Ikon Base Pass." in html
    assert 'href="/resorts/copper"' in html


def test_pass_calendar_marks_blackout_days_and_ics_has_one_event_per_range():
    from datetime import date
    html = pages.pass_page("epic-blackout-dates", date(2026, 11, 19))
    assert html.count('class="m"') == 4 and "November 2026" in html and "February 2027" in html
    assert 'aria-label="Fri 11/27, blackout date"' in html and 'class="t p"' not in html
    assert '<td class="t"><span>19</span></td>' in html
    assert 'href="/passes/epic-blackout-dates.ics"' in html
    ics = pages.pass_ics("ikon-blackout-dates")
    assert ics.count("BEGIN:VEVENT") == 3
    assert "DTSTART;VALUE=DATE:20261226\r\nDTEND;VALUE=DATE:20261231" in ics
