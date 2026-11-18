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
    assert s[0] == "Vail grooming and snow report for Wednesday 11/18: 4 runs groomed, including Born Free, Riva Ridge."
    assert 'The resort reports 3" of new snow in the last 24 hours, 18" base and 31" so far this season.' in s
    assert "The snow report posted at 6:42 AM." in s
    assert any(x.startswith("Expect 20°F at 8 AM") and "gusts to 26 mph" in x for x in s)
    assert 'The next 5 days look like 2 to 7" of snow, most likely 4".' in s
    bare = pages.summary({"date": "2026-11-18", "resort_name": "Alta"})
    assert bare == ["Alta grooming and snow report for Wednesday 11/18."]


def test_resort_page_is_crawlable_html_with_seo_tags():
    html = pages.resort_page("vail", DAY, ["2026-11-18", "2026-11-17", "2026-11-16"])
    assert "<title>Vail grooming report today and snow forecast | 0xSnow</title>" in html
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
    assert '"@type":"BlogPosting"' in html and "Vail grooming report, Wed 11/18" in html


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
