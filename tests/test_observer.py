from datetime import datetime, timezone

from bcbot import observer


def test_every_resort_has_a_probe_and_nothing_sends():
    probes = observer.probes()
    assert {p[0] for p in probes} == set(observer.resorts.enabled())
    imports = [ln for ln in open(observer.__file__) if ln.strip().startswith(("import", "from"))]
    assert not any(m in ln for ln in imports for m in ("mailer", "notify", "webpush", "main"))


def test_html_stamp_and_snow_fingerprint():
    html = "<script>var x=1</script><div>Last Updated: Nov 16, 2026 5:42 AM</div><p>Overnight 4\" 24 Hours 6\"</p>"
    stamp, fp, detail = observer.read_html(html)
    assert stamp.startswith("Nov 16, 2026 5:42")
    assert detail["snow_numbers"] == ["4", "6"]
    assert observer.read_html(html.replace('6"', '7"'))[1] != fp


def test_window_is_every_tick_3_to_10_local_otherwise_quarter_hours():
    mst_6am = datetime(2026, 11, 17, 13, 5, tzinfo=timezone.utc)
    mst_8pm_05 = datetime(2026, 11, 17, 3, 5, tzinfo=timezone.utc)
    mst_8pm_15 = datetime(2026, 11, 17, 3, 15, tzinfo=timezone.utc)
    assert observer.due("vail", mst_6am)
    assert not observer.due("vail", mst_8pm_05)
    assert observer.due("vail", mst_8pm_15)


def test_stops_after_the_week():
    assert observer.run(now=datetime(2026, 11, 25, 14, 0, tzinfo=timezone.utc))["status"] == "skipped"


def test_detail_is_always_valid_json():
    import json
    big = {"hints": ["x" * 5000] * 4, "text": "y" * 3000, "n": 3}
    assert json.loads(observer._cap(big))
