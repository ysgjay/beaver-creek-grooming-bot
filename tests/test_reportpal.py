from zoneinfo import ZoneInfo

from bcbot import resorts
from bcbot.sources import reportpal

MT = ZoneInfo("America/Denver")
FEED = {  # trimmed from bigskyresort.com/api/reportpal?resortName=bs on 11/19/2026
    "name": "Big Sky", "units": "USC", "updated": "2026-11-19T13:05:00Z",
    "currentConditions": {"resortLocations": {"location": [{
        "name": "Big Sky Resort", "snowOverNight": {"inches": "1", "centimeters": "3"},
        "snow24Hours": {"inches": "2", "centimeters": "5"}, "snow48Hours": {"inches": "10", "centimeters": "25"},
        "snow7Days": {"inches": "10", "centimeters": "25"}, "snowSeasonTotal": None,
        "base": {"inches": "16", "centimeters": "41"}}]}},
    "facilities": {"areas": {"area": [
        {"name": "Cascade Area", "trails": {"trail": [{"name": "Middle River", "groomed": True},
                                                      {"name": "Lower Morningstar", "groomed": False}]}},
        {"name": "Swift Current", "trails": {"trail": {"name": "Calamity Jane", "groomed": True}}},
        {"name": "Lone Peak", "trails": None}]}},
}


def test_snow_numbers_in_inches_with_local_stamp():
    out = reportpal.parse_snow_report(FEED, MT)
    assert out["overnight_in"] == 1 and out["last_24h_in"] == 2 and out["last_48h_in"] == 10
    assert out["last_7d_in"] == 10 and out["base_in"] == 16 and "season_in" not in out
    assert out["stamps"] == {"updated": "2026-11-19"} and out["updated_time"] == "6:05 AM"


def test_groomed_runs_by_area_single_trail_objects_ok():
    g = reportpal.parse_trails(FEED)
    assert g["areas"] == {"Cascade Area": ["Middle River"], "Swift Current": ["Calamity Jane"]}
    assert g["groomed"] == ["Middle River", "Calamity Jane"]


def test_bad_input_is_empty():
    assert reportpal.parse_snow_report(None) == {} and reportpal.parse_snow_report({"x": 1}) == {}
    assert reportpal.parse_trails({})["groomed"] == []


def test_boyne_resorts_read_the_feed():
    for slug, code in (("big-sky", "bs"), ("brighton", "br"), ("sugarloaf", "sl"), ("sunday-river", "sr"),
                       ("loon", "lm")):
        r = resorts.get(slug)
        assert r["snow_report"] == f"{r['site']}/api/reportpal?resortName={code}&useReportPal=true"
        assert not resorts.is_static(slug)
