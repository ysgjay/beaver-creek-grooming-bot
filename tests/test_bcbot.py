import json
from datetime import date, datetime, timedelta

import pymupdf
import pytest

from bcbot import config, forecast, main, notify, report, verify
from bcbot.store import BlobStore, LocalStore
from bcbot.sources import grooming, nws, openmeteo, resort, snotel

TODAY = date(2026, 11, 15)


def _hours(days=10, start=TODAY):
    t0 = datetime(start.year, start.month, start.day)
    return [(t0 + timedelta(hours=h)).isoformat(timespec="minutes") for h in range(24 * days)]


def openmeteo_payload(models, precip=0.02, temp=20.0):
    times = _hours()
    hourly = {"time": times}
    for m in models:
        sfx = f"_{m}" if len(models) > 1 else ""
        n = 48 if m == "gfs_hrrr" else len(times)
        def col(v):
            return [v] * n + [None] * (len(times) - n)
        hourly |= {
            f"temperature_2m{sfx}": col(temp), f"apparent_temperature{sfx}": col(temp - 10),
            f"precipitation{sfx}": col(precip), f"snowfall{sfx}": col(precip * 7),
            f"wind_speed_10m{sfx}": col(12), f"wind_gusts_10m{sfx}": col(25),
            f"wind_direction_10m{sfx}": col(290), f"cloud_cover{sfx}": col(80),
        }
    return {"hourly": hourly}


# ---------- snow ratio ----------

def test_slr_curve():
    assert forecast.slr(40) == 8.0
    assert forecast.slr(12) == pytest.approx(17.0)
    assert 12 < forecast.slr(20) < 15.5
    assert forecast.snow_fraction(28) == 1.0
    assert forecast.snow_fraction(40) == 0.0
    assert forecast.hourly_snow(0.1, 40) == 0.0


def test_our_ratio_beats_openmeteo_7_to_1_for_cold_snow():
    # 0.5" liquid at 15°F: Open-Meteo would say 3.5"; Colorado reality is ~8".
    assert forecast.hourly_snow(0.5, 15) == pytest.approx(0.5 * forecast.slr(15))
    assert forecast.hourly_snow(0.5, 15) > 7


# ---------- open-meteo parsing ----------

def test_split_models_drops_missing_and_keeps_rows():
    models = ["ecmwf_ifs025", "gfs_hrrr"]
    out = openmeteo._split_models(openmeteo_payload(models), models + ["ukmo_seamless"])
    assert set(out) == set(models)
    assert out["ecmwf_ifs025"][0]["temperature_2m"] == 20.0
    assert out["gfs_hrrr"][100]["precipitation"] is None


def test_single_model_has_no_suffix():
    payload = {"hourly": {"time": _hours(1), "precipitation": [0.1] * 24, "temperature_2m": [10] * 24}}
    out = openmeteo._split_models(payload, ["gfs_seamless"])
    assert len(out["gfs_seamless"]) == 24


# ---------- blend ----------

def test_blend_daily_totals_and_buckets():
    models = ["ncep_nbm_conus", "ecmwf_ifs025", "gfs_hrrr"]
    rows = openmeteo._split_models(openmeteo_payload(models, precip=0.01, temp=20), models)
    fc = forecast.build(rows, today=TODAY)
    assert len(fc["days"]) == 10
    per_day = 24 * 0.01 * forecast.slr(20)
    assert fc["days"][0]["snow"] == pytest.approx(per_day, abs=0.1)
    assert fc["next_1_5"] == pytest.approx(5 * per_day, abs=0.5)
    # HRRR only covers 2 days, so it only appears in the first two
    assert "gfs_hrrr" in fc["days"][0]["models"] and "gfs_hrrr" not in fc["days"][3]["models"]


def test_bias_and_skill_shift_blend():
    a = openmeteo._split_models(openmeteo_payload(["ecmwf_ifs025"], precip=0.01), ["ecmwf_ifs025"])
    b = openmeteo._split_models(openmeteo_payload(["gfs_seamless"], precip=0.03), ["gfs_seamless"])
    rows = a | b

    v = {"models": {"gfs_seamless": {"bias_ratio": 1.0, "skill": 0.5}, "ecmwf_ifs025": {"bias_ratio": 1.5, "skill": 2.0}}}
    tuned = forecast.build(rows, verification=v, today=TODAY)["days"][4]
    assert tuned["models"]["ecmwf_ifs025"] == pytest.approx(1.5 * 24 * 0.01 * forecast.slr(20), abs=0.1)
    e, g = tuned["models"]["ecmwf_ifs025"], tuned["models"]["gfs_seamless"]
    # day 5 base weights: ECMWF 2.5, GFS 1.0 -> scaled by skill 2.0 and 0.5
    assert tuned["snow"] == pytest.approx((5 * e + 0.5 * g) / 5.5, abs=0.1)


def test_ensemble_range_and_powder_odds():
    rows = openmeteo._split_models(openmeteo_payload(["ecmwf_ifs025"], precip=0.01), ["ecmwf_ifs025"])
    ens = {}
    for i in range(20):
        p = 0.04 if i < 5 else 0.0  # 5 of 20 members bring a big day
        ens[f"member{i:02d}"] = [{"time": t, "precipitation": p, "temperature_2m": 15} for t in _hours()]
    fc = forecast.build(rows, ensemble_rows=ens, today=TODAY)
    assert fc["powder_odds_pct"] == 25
    assert fc["days"][0]["low"] == 0.0 and fc["days"][0]["high"] > fc["days"][0]["snow"]


def test_nws_joins_blend():
    rows = openmeteo._split_models(openmeteo_payload(["ecmwf_ifs025"], precip=0.0), ["ecmwf_ifs025"])
    fc = forecast.build(rows, nws_daily={TODAY.isoformat(): 4.0}, today=TODAY)
    assert fc["days"][0]["models"]["nws"] == 4.0
    assert 0 < fc["days"][0]["snow"] < 4.0


def test_hourly_outlook_prefers_hrrr():
    models = ["ncep_nbm_conus", "gfs_hrrr"]
    rows = openmeteo._split_models(openmeteo_payload(models), models)
    out = forecast.hourly_outlook(rows, now=datetime(2026, 11, 15, 6, 20, tzinfo=config.TZ))
    assert out["model"] == "gfs_hrrr"
    assert out["hours"][0]["time"] == "2026-11-15T06:00"
    assert out["hours"][0]["dir"] == "WNW"


# ---------- NWS ----------

def test_nws_intervals_split_across_local_days():
    # 6h interval 04:00-10:00 UTC = 21:00-03:00 MST: half on each local date
    vals = [{"validTime": "2026-11-16T04:00:00+00:00/PT6H", "value": 50.8}]
    out = nws.daily_from_intervals(vals)
    assert out["2026-11-15"] == pytest.approx(1.0)
    assert out["2026-11-16"] == pytest.approx(1.0)


# ---------- SNOTEL ----------

def test_snotel_daily_differences():
    series = {"PREC": {"2026-11-10": 3.0, "2026-11-11": 3.4, "2026-11-12": 3.4},
              "SNWD": {"2026-11-10": 2, "2026-11-11": 7, "2026-11-12": 6}}
    obs = snotel.daily_observations(series)
    assert obs["2026-11-10"]["precip_in"] == 0.4
    assert obs["2026-11-10"]["depth_change_in"] == 5
    assert "precip_in" not in obs["2026-11-12"]


def test_snotel_last_24h_uses_peak():
    depth = {f"2026-11-14 {h:02d}:00": 5 for h in range(24)}
    depth |= {"2026-11-14 12:00": 9, "2026-11-15 00:00": 8}
    out = snotel.last_24h({"SNWD": depth})
    assert out["snow_in"] == 4


# ---------- verification ----------

def test_verification_learns_dry_model(tmp_path):
    fdir = tmp_path / "forecasts"
    obs = {}
    for i in range(10):
        d = TODAY - timedelta(days=10 - i)
        obs[d.isoformat()] = {"precip_in": 0.5, "depth_change_in": 6}
        issue = (d - timedelta(days=1)).isoformat()
        (fdir).mkdir(exist_ok=True)
        (fdir / f"{issue}.json").write_text(json.dumps({
            "days": [{"date": d.isoformat(), "snow": 5.0, "low": 2, "high": 8}],
            "raw": {"dry": {d.isoformat(): {"liquid": 0.25, "snow": 3}},
                    "good": {d.isoformat(): {"liquid": 0.5, "snow": 6}}}}))
    v = verify.compute(obs, lambda d: json.loads((fdir / f"{d}.json").read_text()) if (fdir / f"{d}.json").exists() else None, today=TODAY)
    assert v["models"]["dry"]["bias_ratio"] == 1.6  # clamped from 2.0
    assert v["models"]["good"]["skill"] > v["models"]["dry"]["skill"]
    assert v["history"][-1]["observed"] == 6


# ---------- resort / grooming ----------

def test_resort_parse():
    html = 'x FR.snowReportData = {"TwentyFourHourSnowfall":{"Inches":"3"},"BaseDepth":{"Inches":"18"},"Other":1}; y'
    assert resort.parse(html) == {"last_24h_in": 3.0, "base_in": 18.0}
    assert resort.parse("<html></html>") == {}


def make_pdf(label="Golden Bear"):
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=400)
    page.insert_text((50, 50), label)
    data = doc.tobytes()
    doc.close()
    return data


def test_grooming_render():
    jpeg, text = grooming.render(make_pdf())
    assert jpeg[:2] == b"\xff\xd8"
    assert "Golden Bear" in text


# ---------- report ----------

def test_compose_message_fits_telegram_caption():
    day = {
        "date": "2026-11-15", "grooming": {"new_map": True},
        "observed": {"snow_in": 2}, "resort": {"last_24h_in": 3},
        "forecast": {"days": [{"date": "2026-11-21", "snow": 5.2}], "next_1_5": 3, "next_1_5_range": [1, 6],
                     "next_6_10": 11, "powder_odds_pct": 20},
        "hourly": {"hours": [{"time": f"2026-11-15T{h:02d}:00", "temp": 18, "feels": 6, "dir": "WNW",
                              "wind": 12, "gust": 25, "snow": 0} for h in range(6, 18)]},
    }
    text = report.compose(day)
    assert "Sun Nov 15th" in text and "Snowiest day: Sat 21" in text and "6a: 18°" in text
    assert len(text) <= notify.TELEGRAM_CAPTION_LIMIT


# ---------- full pipeline, all network mocked ----------

NOW = datetime(2026, 11, 15, 5, 45, tzinfo=config.TZ)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    store = LocalStore(tmp_path)
    models = list(config.MODELS)
    monkeypatch.setattr(openmeteo, "fetch_models",
                        lambda: openmeteo._split_models(openmeteo_payload(models), models))
    monkeypatch.setattr(openmeteo, "fetch_ensemble", lambda: {})
    monkeypatch.setattr(nws, "fetch_snowfall", lambda: {"2026-11-15": 1.0})
    monkeypatch.setattr(snotel, "fetch", lambda: {
        "station": "842:CO:SNTL", "last_24h": {"snow_in": 0},
        "daily": {"2026-11-13": {"precip_in": 0.4, "depth_change_in": 5, "depth_in": 8},
                  "2026-11-14": {"precip_in": 0.0, "depth_change_in": -1, "depth_in": 7}}})
    monkeypatch.setattr(resort, "fetch", lambda: {"last_24h_in": 0.0, "base_in": 4.0, "season_in": 10.0})
    monkeypatch.setattr(config, "STAKE_SNAPSHOT_URL", "")
    pdf = {"bytes": make_pdf()}

    def fake_groom():
        jpeg, text = grooming.render(pdf["bytes"])
        import hashlib
        return {"hash": hashlib.sha256(pdf["bytes"]).hexdigest()[:16], "jpeg": jpeg,
                "runs": {"groomers_of_the_day": [], "overnight": ["Flint"], "morning": ["Maverick"], "map_date": "November 14, 2026"},
                "text_lines": text.splitlines(), "last_modified": None}
    monkeypatch.setattr(grooming, "fetch", fake_groom)
    sent = []
    monkeypatch.setattr(notify, "send_all", lambda text, image=None, channels=None: sent.append((text, channels)) or {})
    return store, tmp_path, pdf, sent


def reports(sent):
    return [t for t, ch in sent if ch is None]


def at(h, m=0, day=15):
    return datetime(2026, 11, day, h, m, tzinfo=config.TZ)


def test_early_run_archives_but_waits_for_send_time(sandbox):
    store, root, pdf, sent = sandbox
    r = main.run(store=store, send=True, now=at(5, 45))
    assert r["status"] == "ok" and r["map_changed"] and reports(sent) == []
    latest = store.get_json("data/latest.json")
    assert latest["grooming"]["new_map"] and latest["forecast"]["days"]
    assert (root / "maps/2026-11-15.jpg").exists()
    month = store.get_json("data/months/2026-11.json")
    assert month["days"]["2026-11-15"]["overnight"] == ["Flint"]
    assert month["days"]["2026-11-13"]["snotel_new_in"] == 5      # SNOTEL fills past days
    assert month["days"]["2026-11-14"]["snotel_new_in"] == 0.0    # settling is not negative snow
    # 6:15: nothing changed and not yet in the pre-send window -> cheap skip
    assert main.run(store=store, send=True, now=at(6, 15))["status"] == "skipped"


def test_sends_at_seven_exactly_once(sandbox):
    store, root, pdf, sent = sandbox
    main.run(store=store, send=True, now=at(5, 45))
    r = main.run(store=store, send=True, now=at(7, 0))
    assert r["sent"] is not None and len(reports(sent)) == 1
    assert "Groomed overnight: Flint" in reports(sent)[0]
    d = store.get_json("data/latest.json")["delivery"]
    assert d["scheduled"].endswith("07:00") and d["new_map"]
    # retries, the backup cron, and later triggers never send twice
    for t in [at(7, 0), at(7, 15), at(9, 0), at(14, 0)]:
        main.run(store=store, send=True, now=t)
    pdf["bytes"] = make_pdf("Updated map")   # even a new map later that day
    main.run(store=store, send=True, now=at(8, 30))
    assert len(reports(sent)) == 1


def test_pre_send_window_refreshes_stale_data(sandbox):
    store, root, pdf, sent = sandbox
    main.run(store=store, send=True, now=at(5, 0))
    r = main.run(store=store, send=True, now=at(6, 45))   # 1h45 old, inside the 30-min window
    assert r["status"] == "ok" and r["full_run"] and reports(sent) == []


def test_late_map_sends_the_moment_it_appears(sandbox):
    store, root, pdf, sent = sandbox
    main.run(store=store, send=True, now=at(6, 0, day=14))         # yesterday's map
    sent.clear()
    main.run(store=store, send=True, now=at(5, 45))                # same map today -> not new
    assert store.get_json("data/latest.json")["grooming"]["new_map"] is False
    main.run(store=store, send=True, now=at(7, 0))
    main.run(store=store, send=True, now=at(7, 15))
    assert reports(sent) == []                                     # waiting for today's map
    pdf["bytes"] = make_pdf("Today's map")
    main.run(store=store, send=True, now=at(7, 30))
    assert len(reports(sent)) == 1


def test_fallback_sends_without_new_map_in_season(sandbox):
    store, root, pdf, sent = sandbox
    main.run(store=store, send=True, now=at(6, 0, day=14))
    sent.clear()
    for t in [at(5, 45), at(7, 0), at(8, 45)]:
        main.run(store=store, send=True, now=t)
    assert reports(sent) == []
    main.run(store=store, send=True, now=at(9, 0))
    assert len(reports(sent)) == 1 and "No new grooming map" in reports(sent)[0]


def test_off_season_sends_nothing(sandbox):
    store, root, pdf, sent = sandbox
    main.run(store=store, send=True, now=at(6, 0, day=10))         # map last changed 5 days ago
    sent.clear()
    for t in [at(5, 45), at(7, 0), at(9, 0), at(9, 15)]:
        main.run(store=store, send=True, now=t)
    assert reports(sent) == []


def test_sending_disabled_never_sends(sandbox):
    store, root, pdf, sent = sandbox
    for t in [at(5, 45), at(7, 0), at(9, 0)]:
        main.run(store=store, send=False, now=t)
    assert sent == []


def test_pipeline_survives_source_outage(sandbox, monkeypatch):
    store, root, pdf, sent = sandbox

    def boom():
        raise RuntimeError("down")
    monkeypatch.setattr(nws, "fetch_snowfall", boom)
    monkeypatch.setattr(snotel, "fetch", boom)
    r = main.run(store=store, send=True, now=at(7, 0))
    assert r["ok"] and len(reports(sent)) == 1
    assert any("nws" in e for e in store.get_json("data/latest.json")["errors"])


def test_blob_store_put_uses_vercel_blob_protocol(monkeypatch):
    calls = []

    class Resp:
        ok = True
        status_code = 200
        def json(self):
            return {"url": "https://x.public.blob.vercel-storage.com/data/latest.json"}

    class FakeHttp:
        def put(self, url, data=None, headers=None, timeout=None):
            calls.append((url, headers, data))
            return Resp()
    monkeypatch.setattr("bcbot.store.http", lambda: FakeHttp())
    b = BlobStore("vercel_blob_rw_store123_secret", "https://x.public.blob.vercel-storage.com")
    b.put_json("data/latest.json", {"a": 1})
    url, h, data = calls[0]
    assert url == "https://vercel.com/api/blob/?pathname=data%2Flatest.json"
    assert h["authorization"] == "Bearer vercel_blob_rw_store123_secret"
    assert h["x-add-random-suffix"] == "0" and h["x-allow-overwrite"] == "1"
    assert h["x-content-type"] == "application/json" and h["x-cache-control-max-age"] == "60"
    b.put_bytes("maps/2026-11-15.jpg", b"jpg", "image/jpeg")
    assert calls[1][1]["x-cache-control-max-age"] == "31536000"


def test_parse_runs_from_real_lumiplan_text():
    # Text layer of the live PDF fetched by CI on 2026-11-14
    lines = ['OFFICIAL PARTNERS OF BEAVER CREEK RESORT', 'November 13, 2026', 'GROOMERS OF THE DAY',
             'Hand-picked by our snow surface experts.', 'No trails reported.', "LAST NIGHT'S GROOMING",
             '1', 'Little Brave Lower', '2', 'Flint', 'MORNING GROOMING', '3', 'Intertwine - Upper', '4',
             'Maverick', 'DA', 'KOTA S', 'K', 'I', 'W', 'A', 'Y', 'LITTLE', 'BR']
    runs = grooming.parse_runs(lines)
    assert runs["map_date"] == "November 13, 2026"
    assert runs["groomers_of_the_day"] == []
    assert runs["overnight"] == ["Little Brave Lower", "Flint"]
    assert runs["morning"] == ["Intertwine - Upper", "Maverick"]


def test_bucket_range_uses_member_totals():
    rows = openmeteo._split_models(openmeteo_payload(["ecmwf_ifs025"], precip=0.0), ["ecmwf_ifs025"])
    ens = {}
    for i in range(20):
        # each member puts its one storm on a different day: daily p90 is 0 but every 5-day total is big
        day = i % 5
        ens[f"m{i}"] = [{"time": t, "precipitation": 0.03 if int(t[8:10]) - 15 == day else 0.0,
                         "temperature_2m": 15} for t in _hours()]
    fc = forecast.build(rows, ensemble_rows=ens, today=TODAY)
    lo, hi = fc["next_1_5_range"]
    storm = 24 * 0.03 * forecast.slr(15)
    assert hi == pytest.approx(storm, abs=0.2)  # every member's 5-day total is one storm
    assert lo == 0.0  # range always includes the blend (dry deterministic model here)
