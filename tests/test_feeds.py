from datetime import date

from bcbot import resorts
from bcbot.sources import feeds, textpage

# Page text as each resort's report page renders it without JavaScript (checked 11/19/2026).
KILLINGTON = ('<div>Snow Report</div><div><div>Updated November 15, 2026 10:44 AM</div><a><div>24 Hour</div>'
              '<div><i></i></div><div>0&quot;</div></a><a><div>48 Hour</div><div>0"</div></a><a><div>7 Day</div>'
              '<div>5"</div></a><a><div>Season</div><div>5"</div></a>')
SUN_VALLEY = ('November 19, 2026 High 27°F Snowfall 0” Overnight 0” 24 hours 5” 7 days 0” Base 15” Season '
              'Last Updated: Nov 15, 5:00 AM MT')
REVELSTOKE = 'Snow Report New Snow 1 cm Last Hour 0 cm 24 hours 1 cm 48 hours 5 cm 7 days 29 cm Base Depth 37 cm Season Total 147 cm'
TELLURIDE = ('Last Updated: November 19, 2026 at 4:42am 0" last 24 hr Snow depth 12" Season total 12" '
             'Snow overnight 6" Last 24 hours 0" Last 48 hours 0" Last 7 days 0"')
POWDER = ('Updated: 11/18/26 03:02 PM MST 12HR Snowfall 0" 24HR Snowfall 0" 48HR Snowfall 12" 7 Day Snowfall 15" '
          'Base Depth 16" Current Season 15"')


def test_label_then_number_with_stamp():
    out = textpage.parse(KILLINGTON, "Snow Report Updated")
    assert out == {"last_24h_in": 0, "last_48h_in": 0, "last_7d_in": 5, "season_in": 5,
                   "stamps": {"updated": "2026-11-15"}, "updated_time": "10:44 AM"}


def test_number_then_label_and_date_without_year():
    out = textpage.parse(SUN_VALLEY, "Snowfall", "before", today=date(2026, 11, 19))
    assert (out["overnight_in"], out["last_24h_in"], out["last_7d_in"], out["base_in"], out["season_in"]) == (0, 0, 5, 0, 15)
    assert out["stamps"] == {"updated": "2026-11-15"} and out["updated_time"] == "5:00 AM"
    assert textpage.parse("Last Updated: Dec 30, 6:00 AM 2\" 24 hours", order="before",
                          today=date(2027, 1, 2))["stamps"] == {"updated": "2026-12-30"}


def test_centimeters_become_inches():
    out = textpage.parse(REVELSTOKE, "Snow Report")
    assert out["last_24h_in"] == 0.4 and out["last_7d_in"] == 11.4 and out["base_in"] == 14.6 and out["season_in"] == 57.9


def test_start_skips_a_summary_tile_but_keeps_the_stamp():
    out = textpage.parse(TELLURIDE, "Snow depth")
    assert out["last_24h_in"] == 0 and out["base_in"] == 12 and out["overnight_in"] == 6
    assert out["stamps"] == {"updated": "2026-11-19"} and out["updated_time"] == "4:42 AM"


def test_two_digit_year_and_12_hour_overnight():
    out = textpage.parse(POWDER, "Updated")
    assert out["overnight_in"] == 0 and out["last_48h_in"] == 12 and out["base_in"] == 16
    assert out["stamps"] == {"updated": "2026-11-18"} and out["updated_time"] == "3:02 PM"


def test_page_without_numbers_is_empty():
    assert textpage.parse("<p>Loading...</p>") == {} and textpage.parse(None) == {}


def test_json_feed_paths_and_value_objects():
    jackson = {"lastModified": "2026-11-18T08:30:00.000-07:00", "snow": {"midMountain": {
        "newSnowLast24H": {"unit": "INCH", "value": "0"}, "newSnowLast48H": {"value": "2"}, "newSnowLast7D": {},
        "totalSnowDepth": {"value": "1"}, "seasonTotalSnow": {"value": "6"},
        "newSnowSinceLiftsClosed": {"value": "0"}}}}
    out = feeds.parse_json(jackson, resorts.get("jackson-hole")["report_feed"])
    assert out == {"overnight_in": 0, "last_24h_in": 0, "last_48h_in": 2, "base_in": 1, "season_in": 6,
                   "stamps": {"updated": "2026-11-18"}, "updated_time": "8:30 AM"}
    taos = {"snowData": {"last7Days": 8, "last48Hours": 7, "last24Hours": 0, "overnight": None, "base": 8,
                         "seasonTotal": 19.75}}
    out = feeds.parse_json(taos, resorts.get("taos")["report_feed"])
    assert out == {"last_24h_in": 0, "last_48h_in": 7, "last_7d_in": 8, "base_in": 8, "season_in": 19.75}


def test_every_report_feed_is_wired():
    for slug, r in resorts.RESORTS.items():
        f = r.get("report_feed")
        if f:
            assert f["kind"] in feeds.KINDS and f["url"].startswith("https://"), slug
            assert f.get("order", "after") in ("after", "before"), slug
            assert resorts.get(slug)["snow_report"] == f["url"] and not resorts.is_static(slug), slug
