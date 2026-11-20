import json
from datetime import datetime
from zoneinfo import ZoneInfo

from bcbot import groomwatch, resorts
from bcbot.store import LocalStore


def _now(day, hour=16):
    return datetime.fromisoformat(f"{day}T{hour:02d}:00+00:00")


def _latest(store, slug, day, grooming):
    path = "data/latest.json" if slug == resorts.DEFAULT else f"data/{slug}/latest.json"
    store.put_json(path, {"date": day, "grooming": grooming})


def test_had_grooming():
    assert groomwatch.had_grooming({"date": "2026-11-20", "grooming": {"image": "m.jpg", "new_map": True}}, "2026-11-20")
    assert not groomwatch.had_grooming({"date": "2026-11-20", "grooming": {"image": "m.jpg", "new_map": False}}, "2026-11-20")
    assert groomwatch.had_grooming({"date": "2026-11-20", "grooming": {"list": True, "runs": {"groomed": ["A"]}}}, "2026-11-20")
    assert not groomwatch.had_grooming({"date": "2026-11-20", "grooming": {"list": True, "runs": {"groomed": []}}}, "2026-11-20")
    assert not groomwatch.had_grooming({"date": "2026-11-19", "grooming": {"list": True, "runs": {"groomed": ["A"]}}}, "2026-11-20")
    assert not groomwatch.had_grooming({"date": "2026-11-20", "grooming": {"none": True}}, "2026-11-20")


def test_sources():
    assert groomwatch.source(resorts.get("vail")) == "Lumiplan map"
    assert groomwatch.source(resorts.get("copper")) == "POWDR feed"
    assert groomwatch.source(resorts.get("whistler-blackcomb")) == "Vail terrain page"
    assert groomwatch.source(resorts.get("killington")) == ""


def test_watch_alerts_once_for_no_source_and_for_an_empty_feed(tmp_path):
    store = LocalStore(tmp_path)
    slugs = ["killington", "whistler-blackcomb"]  # Whistler opened 11/20
    _latest(store, "whistler-blackcomb", "2026-11-20", {"list": True, "runs": {"groomed": ["Wishbone"]}})
    w = groomwatch.watch(store, _now("2026-11-20", 20), slugs)
    assert [a["resort"] for a in w["alerts"]] == ["killington"]
    assert {r["resort"]: r["last_grooming"] for r in w["rows"]}["whistler-blackcomb"] == "2026-11-20"
    # Next days: Killington isn't alerted again; Whistler's feed goes quiet.
    for day in ("2026-11-21", "2026-11-22"):
        _latest(store, "whistler-blackcomb", day, {"list": True, "runs": {"groomed": []}})
        assert groomwatch.watch(store, _now(day, 20), slugs)["alerts"] == []
    _latest(store, "whistler-blackcomb", "2026-11-23", {"list": True, "runs": {"groomed": []}})
    w = groomwatch.watch(store, _now("2026-11-23", 20), slugs)
    assert [(a["resort"], a["problem"]) for a in w["alerts"]] == [("whistler-blackcomb", "empty 3 days")]
    assert groomwatch.watch(store, _now("2026-11-23", 21), slugs)["alerts"] == []  # once per streak
    # Runs come back: problem clears.
    _latest(store, "whistler-blackcomb", "2026-11-24", {"list": True, "runs": {"groomed": ["Ego Bowl"]}})
    w = groomwatch.watch(store, _now("2026-11-24", 20), slugs)
    assert {r["resort"]: r["problem"] for r in w["rows"]}["whistler-blackcomb"] == ""


def test_watch_waits_for_opening_day(tmp_path):
    store = LocalStore(tmp_path)
    w = groomwatch.watch(store, _now("2026-11-20"), ["kirkwood"])  # opens 12/04
    assert w["alerts"] == [] and w["rows"][0]["in_season"] is False


def test_find_probes_formats_and_reports_new_candidates_once(tmp_path):
    store = LocalStore(tmp_path)
    terrain = '<script>FR.TerrainStatusFeed = {"GroomingAreas": [{"Name": "A", "Trails": [{"Name": "X", "IsGroomed": true}]}], "IsSuccessful": true};</script>'
    pages = {"https://www.killington.com": '<a href="/the-mountain/grooming-report">Grooming</a> <script src="https://mtnpowder.com/x.js"></script>',
             "https://www.alta.com" + "/the-mountain/mountain-conditions/terrain-and-lift-status.aspx": terrain,
             "https://api.alta.com/api/v1/dor/drupal/trails": json.dumps([{"name": "X", "groom_status": "groomed"}])}
    fetch = lambda u: pages.get(u)
    head = lambda u: 200 if u == "https://grooming.lumiplan.pro/killington-grooming-map.pdf" else 404
    f = groomwatch.find(store, fetch, head, _now("2026-11-23"), ["killington", "alta", "vail"])
    by = {x["resort"]: x for x in f["results"]}
    assert "vail" not in by  # has a source already
    assert [x["kind"] for x in by["killington"]["found"]] == ["lumiplan"]
    assert by["killington"]["links"] == ["https://www.killington.com/the-mountain/grooming-report"]
    assert by["killington"]["providers"] == ["Mountain Powder feed"]
    assert [x["kind"] for x in by["alta"]["found"]] == ["vail_terrain", "powdr"]
    assert len(f["new"]) == 3
    assert groomwatch.find(store, fetch, head, _now("2026-11-30"), ["killington", "alta"])["new"] == []
