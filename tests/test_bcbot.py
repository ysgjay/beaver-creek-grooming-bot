import json
from datetime import date, datetime, timedelta

import pymupdf
import pytest

from bcbot import config, forecast, main, notify, report, verify
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
    v = verify.compute(obs, forecasts_dir=fdir, today=TODAY)
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

@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "D", tmp_path / "data")
    monkeypatch.setattr(verify.config, "DATA_DIR", tmp_path / "data")
    models = list(config.MODELS)
    monkeypatch.setattr(openmeteo, "fetch_models",
                        lambda: openmeteo._split_models(openmeteo_payload(models), models))
    monkeypatch.setattr(openmeteo, "fetch_ensemble", lambda: {})
    monkeypatch.setattr(nws, "fetch_snowfall", lambda: {"2026-11-15": 1.0})
    monkeypatch.setattr(snotel, "fetch", lambda: {"station": "842:CO:SNTL", "daily": {}, "last_24h": {"snow_in": 0}})
    monkeypatch.setattr(resort, "fetch", lambda: {})
    pdf = {"bytes": make_pdf()}

    def fake_groom():
        jpeg, text = grooming.render(pdf["bytes"])
        import hashlib
        return {"hash": hashlib.sha256(pdf["bytes"]).hexdigest()[:16], "jpeg": jpeg,
                "text_lines": text.splitlines(), "last_modified": None}
    monkeypatch.setattr(grooming, "fetch", fake_groom)
    sent = []
    monkeypatch.setattr(notify, "send_all", lambda text, image=None, channels=None: sent.append((text, channels)) or {})
    return tmp_path / "data", pdf, sent


def test_pipeline_sends_once_per_new_map(sandbox):
    data, pdf, sent = sandbox
    assert main.run() == 0
    reports = [t for t, ch in sent if ch is None]
    alerts = [t for t, ch in sent if ch == ["ntfy"]]
    assert len(reports) == 1 and "Grooming" in reports[0]
    assert len(alerts) == 1 and "Powder alert" in alerts[0]  # ~7"/day in the fixture
    assert (data / "latest.json").exists() and (data / "index.json").exists()
    latest = json.loads((data / "latest.json").read_text())
    assert latest["grooming"]["new_map"] and latest["forecast"]["days"]
    assert any(data.glob("maps/*.jpg"))
    # second cron run, same map -> nothing sent
    assert main.run() == 0
    assert len(sent) == 2


def test_pipeline_dry_run_sends_nothing(sandbox):
    data, pdf, sent = sandbox
    assert main.run(dry_run=True) == 0
    assert sent == [] and not (data / "state.json").exists()


def test_pipeline_survives_source_outage(sandbox, monkeypatch):
    data, pdf, sent = sandbox
    def boom():
        raise RuntimeError("down")
    monkeypatch.setattr(nws, "fetch_snowfall", boom)
    monkeypatch.setattr(snotel, "fetch", boom)
    assert main.run() == 0
    latest = json.loads((data / "latest.json").read_text())
    assert any("nws" in e for e in latest["errors"])
    assert len([1 for _, ch in sent if ch is None]) == 1


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
