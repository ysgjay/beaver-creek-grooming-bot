import json

from bcbot import config, resorts
from bcbot.sources import vrterrain

FEED = {"Date": "2026-11-20T16:30:52-07:00", "ResortId": 19, "GroomingAreas": [
    {"Id": 289, "Name": "Blackcomb Lifts", "Trails": [], "Lifts": []},
    {"Id": 1, "Name": "Jersey Cream", "Trails": [
        {"Name": "Wishbone", "IsGroomed": True, "IsOpen": True, "Difficulty": "Blue"},
        {"Name": "Blackcomb Race Centre", "IsGroomed": False, "IsOpen": False, "Difficulty": "Blue"}]},
    {"Id": 2, "Name": "Peak 8", "Trails": [
        {"Name": "Freeway Terrain Park", "IsGroomed": True, "IsOpen": True, "Difficulty": "TerrainPark"},
        {"Name": " ", "IsGroomed": True}]}],
    "ErrorDetails": None, "IsSuccessful": True}


def _page(feed):
    # The live page carries the object twice: an old "/Date(...)/" copy and an ISO-dated one.
    old = dict(feed, Date="\\/Date(1795217452252)\\/")
    return (f'<script type="module">\r\n    FR.TerrainStatusFeed = {json.dumps(old)};\r\n    FR.LiftStatusFilters = [];</script>'
            f'<script type="module">\r\n    FR.TerrainStatusFeed = {json.dumps(feed)};\r\n    FR.RunFilters = [];</script>')


def test_parses_groomed_runs_by_area():
    g = vrterrain.parse(_page(FEED))
    assert g["areas"] == {"Jersey Cream": ["Wishbone"], "Peak 8": ["Freeway Terrain Park"]}
    assert g["groomed"] == ["Wishbone", "Freeway Terrain Park"]


def test_no_feed_or_failed_feed_is_none():
    assert vrterrain.parse("<html>no feed</html>") is None
    assert vrterrain.parse(_page(dict(FEED, IsSuccessful=False))) is None


def test_nothing_groomed_is_an_empty_list_not_none():
    feed = dict(FEED, GroomingAreas=[{"Name": "A", "Trails": [{"Name": "X", "IsGroomed": False}]}])
    assert vrterrain.parse(_page(feed))["groomed"] == []


def test_vail_resorts_without_a_map_get_the_terrain_page():
    w = resorts.get("whistler-blackcomb")
    assert w["terrain_status"] == "https://www.whistlerblackcomb.com" + vrterrain.PATH
    assert resorts.get("copper")["terrain_status"] is None  # POWDR feed, not Vail's platform
    with_url = [r for r in resorts.public_list()["resorts"] if r["slug"] == "whistler-blackcomb"]
    assert with_url[0]["grooming"] is True
    config.use("whistler-blackcomb")
    try:
        assert config.TERRAIN_STATUS_URL == w["terrain_status"]
    finally:
        config.use(resorts.DEFAULT)
