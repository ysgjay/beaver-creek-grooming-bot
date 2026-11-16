import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pymupdf
import pytest

from bcbot import config, forecast, main, notify, report, resorts, verify
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


def test_nws_leaves_out_partly_covered_days():
    # The grid starts mid-afternoon: today has 8 hours left, tomorrow is complete.
    vals = [{"validTime": "2026-11-15T23:00:00+00:00/PT8H", "value": 25.4},   # 16:00-24:00 MST
            {"validTime": "2026-11-16T07:00:00+00:00/P1D", "value": 50.8}]    # all of 11/16 MST
    out = nws.daily_from_intervals(vals, min_hours=nws.MIN_HOURS)
    assert "2026-11-15" not in out
    assert out["2026-11-16"] == pytest.approx(2.0)


# ---------- elevation bands ----------

def bands_payload(temps=(38.0, 30.0, 24.0), precip=0.02):
    times = _hours()
    return [{"hourly": {"time": times, "temperature_2m": [t] * len(times),
                        "apparent_temperature": [t - 8] * len(times), "precipitation": [precip] * len(times),
                        "wind_speed_10m": [10] * len(times), "wind_gusts_10m": [20] * len(times)}}
            for t in temps]


def test_bands_are_on_the_mountain_and_ordered_by_elevation():
    fts = [b["elevation_ft"] for b in config.ELEVATION_BANDS]
    assert fts == sorted(fts) and fts[0] >= 8000        # Avon, the town below, is 7,430 ft
    assert [b["key"] for b in config.ELEVATION_BANDS] == ["base", "mid", "peak"]


def test_band_outlook_temps_and_rain_snow_split():
    rows = openmeteo.split_bands(bands_payload(), config.ELEVATION_BANDS)
    out = forecast.band_outlook(rows, now=datetime(2026, 11, 15, 6, 20, tzinfo=config.TZ))
    base, mid, peak = out
    assert (base["label"], base["elevation_ft"]) == ("Base", 8100)
    assert [b["now"]["temp"] for b in out] == [38, 30, 24]
    assert len(mid["hours"]) == 12 and mid["hours"][0]["time"] == "2026-11-15T06:00"
    assert peak["days"][0] == {"date": "2026-11-15", "high": 24, "low": 24, "snow_pct": 100}
    assert base["days"][0]["snow_pct"] == 0             # rain in the village, snow up top
    assert len(base["days"]) == 10


def test_band_outlook_skips_missing_band_and_dry_days():
    rows = openmeteo.split_bands(bands_payload(precip=0.0)[:2], config.ELEVATION_BANDS)
    out = forecast.band_outlook(rows, now=datetime(2026, 11, 15, 6, 0, tzinfo=config.TZ))
    assert [b["key"] for b in out] == ["base", "mid"]
    assert out[0]["days"][0]["snow_pct"] is None


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


def _archive(tmp_path, days=10, liquid=0.25, snow=5.0, snow_cal=None):
    """Forecasts issued the day before each of the last `days` days, plus matching SNOTEL."""
    fdir = tmp_path / "forecasts"
    fdir.mkdir(exist_ok=True)
    obs = {}
    for i in range(days):
        d = TODAY - timedelta(days=days - i)
        obs[d.isoformat()] = {"precip_in": 0.5, "depth_change_in": 6}
        doc = {"days": [{"date": d.isoformat(), "snow": snow, "low": 2, "high": 8}],
               "raw": {"dry": {d.isoformat(): {"liquid": liquid, "snow": 3}}}}
        if snow_cal:
            doc["snow_cal"] = snow_cal
        (fdir / f"{(d - timedelta(days=1)).isoformat()}.json").write_text(json.dumps(doc))

    def load(d):
        return json.loads((fdir / f"{d}.json").read_text()) if (fdir / f"{d}.json").exists() else None
    return obs, load


def test_terrain_prior_stands_until_recent_days_outweigh_it(tmp_path):
    # Nothing scored yet: the prior from last winter is the correction.
    v = verify.compute({}, lambda d: None, today=TODAY, priors={"gfs_seamless": 1.3})
    assert v["models"]["gfs_seamless"] == {"n": 0, "prior": 1.3, "bias_ratio": 1.3, "skill": 1.0}
    # One wet day (0.5" seen, 0.5" forecast) only nudges it: (0.5 + 1.3) / (0.5 + 1.0) = 1.2.
    obs, load = _archive(tmp_path, days=1, liquid=0.5)
    assert verify.compute(obs, load, today=TODAY, priors={"dry": 1.3})["models"]["dry"]["bias_ratio"] == 1.2
    # Ten such days: recent evidence wins, (5 + 1.3) / (5 + 1) = 1.05.
    obs, load = _archive(tmp_path, days=10, liquid=0.5)
    assert verify.compute(obs, load, today=TODAY, priors={"dry": 1.3})["models"]["dry"]["bias_ratio"] == 1.05


def test_terrain_priors_from_last_winter():
    days = [(date(2025, 12, 1) + timedelta(days=i)).isoformat() for i in range(40)]
    observed = {d: 0.2 for d in days}
    out = verify.terrain_priors({"coarse": {d: 0.1 for d in days},          # half of what fell
                                 "sharp": {d: 0.2 for d in days},
                                 "short": {d: 0.1 for d in days[:10]},      # too few days to trust
                                 "wild": {d: 0.01 for d in days}}, observed)
    assert out["coarse"]["bias_ratio"] == 1.6 and out["coarse"]["n"] == 40  # clamped from 2.0
    assert out["sharp"]["bias_ratio"] == 1.0
    assert "short" not in out and "wild" not in out
    assert verify.prior_season(date(2026, 11, 15)) == (date(2025, 11, 1), date(2026, 4, 30))
    assert verify.prior_season(date(2027, 2, 1)) == (date(2025, 11, 1), date(2026, 4, 30))


def test_history_payload_split_by_model():
    payload = {"daily": {"time": ["2025-12-01", "2025-12-02"], "precipitation_sum_gfs_seamless": [0.1, None],
                         "precipitation_sum_ecmwf_ifs": [None, None]}}
    assert openmeteo.split_history(payload, ["gfs_seamless", "ecmwf_ifs", "gem_seamless"]) == {
        "gfs_seamless": {"2025-12-01": 0.1}}


def test_snow_calibration_against_resort_report(tmp_path):
    # We forecast 5" a day for 10 days; the resort reported 7" each following morning.
    obs, load = _archive(tmp_path, days=10, snow=5.0)
    resort_daily = {(TODAY - timedelta(days=i)).isoformat(): 7.0 for i in range(10)}
    v = verify.compute(obs, load, today=TODAY, resort_daily=resort_daily)
    assert v["snow_cal"] == {"ratio": 1.36, "n": 10, "forecast_in": 50.0, "resort_in": 70.0}  # (70+6)/(50+6)
    assert v["history"][-1]["resort"] == 7.0
    # No resort reports: no calibration.
    assert verify.compute(obs, load, today=TODAY)["snow_cal"]["ratio"] == 1.0
    # Forecasts that were already calibrated are compared before calibration, so it can't compound.
    obs, load = _archive(tmp_path, days=10, snow=7.0, snow_cal=1.4)
    assert verify.compute(obs, load, today=TODAY, resort_daily=resort_daily)["snow_cal"]["forecast_in"] == 50.0


def test_calibration_and_bias_reach_the_range_too():
    rows = openmeteo._split_models(openmeteo_payload(["gfs_seamless"], precip=0.01), ["gfs_seamless"])
    ens = {f"member{i:02d}_gfs025": [{"time": t, "precipitation": 0.01, "temperature_2m": 20} for t in _hours()]
           for i in range(12)}
    plain = forecast.build(rows, ensemble_rows=ens, today=TODAY)
    fixed = forecast.build(rows, ensemble_rows=ens, today=TODAY, verification={
        "models": {"gfs_seamless": {"bias_ratio": 1.5, "skill": 1.0}}, "snow_cal": {"ratio": 1.2}})
    assert fixed["snow_cal"] == 1.2
    assert fixed["days"][0]["snow"] == pytest.approx(plain["days"][0]["snow"] * 1.8, abs=0.1)
    assert fixed["days"][0]["high"] == pytest.approx(plain["days"][0]["high"] * 1.8, abs=0.1)
    assert fixed["next_1_5_range"][0] == pytest.approx(plain["next_1_5_range"][0] * 1.8, abs=0.2)


def test_coarse_ecmwf_steps_aside_for_the_9km_run():
    coarse = openmeteo._split_models(openmeteo_payload(["ecmwf_ifs025"], precip=0.01), ["ecmwf_ifs025"])
    sharp = openmeteo._split_models(openmeteo_payload(["ecmwf_ifs"], precip=0.03), ["ecmwf_ifs"])
    alone = forecast.build(coarse, today=TODAY)
    both = forecast.build(coarse | sharp, today=TODAY)
    assert "ecmwf_ifs025" in alone["days"][0]["models"]
    assert list(both["days"][0]["models"]) == ["ecmwf_ifs"]
    assert both["days"][0]["snow"] == pytest.approx(3 * alone["days"][0]["snow"], abs=0.1)
    assert both["model_labels"]["ecmwf_ifs"] == "ECMWF 9 km"


def test_extra_models_never_cost_the_core_ones(monkeypatch):
    calls = []

    def fake(models, **opts):
        calls.append(models)
        if "ecmwf_ifs" in models:
            raise RuntimeError("unknown model")
        return {m: [] for m in models}
    monkeypatch.setattr(openmeteo, "_fetch_models", fake)
    out = openmeteo.fetch_models()
    assert len(calls) == 2 and "gfs_seamless" in out and "ecmwf_ifs" not in out


def test_humidity_sets_the_rain_snow_line():
    assert forecast.wet_bulb_f(36, 100) == pytest.approx(36, abs=0.6)
    assert forecast.wet_bulb_f(36, 30) < 30                      # dry air: far colder wet bulb
    assert forecast.snow_fraction(36, 30) == 1.0                 # dry Colorado air: snow at 36°F
    assert forecast.snow_fraction(36, 100) == 0.0                # soaked air: rain at 36°F
    assert 0.3 < forecast.snow_fraction(34, 95) < 0.8
    assert forecast.snow_fraction(20, 80) == 1.0
    assert forecast.snow_fraction(36) == 0.0 and forecast.snow_fraction(31) == 1.0   # no humidity: old rule
    assert forecast.hourly_snow(0.1, 36, 30) > 0 == forecast.hourly_snow(0.1, 36)


def test_ensemble_payload_carries_humidity():
    hourly = {"time": _hours(1), "precipitation_member01_gfs025": [0.01] * 24,
              "temperature_2m_member01_gfs025": [35.0] * 24, "relative_humidity_2m_member01_gfs025": [40] * 24,
              "precipitation_ecmwf_ifs025": [0.0] * 24, "temperature_2m_ecmwf_ifs025": [35.0] * 24}
    out = openmeteo.split_ensemble({"hourly": hourly})
    assert out["member01_gfs025"][0]["relative_humidity_2m"] == 40
    assert forecast._ensemble_parent("member01_gfs025") == "gfs_seamless"
    assert forecast._ensemble_parent("ecmwf_ifs025") == "ecmwf_ifs025"


def test_priors_are_worked_out_once_a_season(tmp_path, monkeypatch):
    store, calls = LocalStore(tmp_path), []
    days = [(date(2025, 12, 1) + timedelta(days=i)).isoformat() for i in range(40)]

    def history(start, end):
        calls.append((start, end))
        return {"gfs_seamless": {d: 0.1 for d in days}}
    monkeypatch.setattr(openmeteo, "fetch_history", history)
    monkeypatch.setattr(snotel, "fetch_daily_precip",
                        lambda b, e: {"station": "842:CO:SNTL", "daily": {d: 0.13 for d in days}})
    errors = []
    assert main._terrain_priors(store, TODAY, errors) == {"gfs_seamless": 1.3}
    assert main._terrain_priors(store, TODAY + timedelta(days=1), errors) == {"gfs_seamless": 1.3}
    assert len(calls) == 1 and not errors
    assert store.get_json("data/priors.json")["season"] == "2025-11-01"


def test_failed_priors_retry_the_next_day_not_every_run(tmp_path, monkeypatch):
    store, calls = LocalStore(tmp_path), []

    def down(b, e):
        calls.append(b)
        raise RuntimeError("offline")
    monkeypatch.setattr(snotel, "fetch_daily_precip", down)
    errors = []
    assert main._terrain_priors(store, TODAY, errors) == {}
    assert main._terrain_priors(store, TODAY, errors) == {}
    assert len(calls) == 1
    main._terrain_priors(store, TODAY + timedelta(days=1), errors)
    assert len(calls) == 2


# ---------- resort / grooming ----------

def test_resort_parse():
    html = 'x FR.snowReportData = {"TwentyFourHourSnowfall":{"Inches":"3"},"BaseDepth":{"Inches":"18"},"Other":1}; y'
    r = resort.parse(html)
    assert r["last_24h_in"] == 3.0 and r["base_in"] == 18.0
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

def test_compose_subject_and_push_payload():
    day = {
        "date": "2026-11-15", "grooming": {"new_map": True},
        "observed": {"snow_in": 2}, "resort": {"last_24h_in": 3},
        "forecast": {"days": [{"date": "2026-11-21", "snow": 5.2}], "next_1_5": 3, "next_1_5_range": [1, 6],
                     "next_6_10": 11, "powder_odds_pct": 20},
        "hourly": {"hours": [{"time": f"2026-11-15T{h:02d}:00", "temp": 18, "feels": 6, "dir": "WNW",
                              "wind": 12, "gust": 25, "snow": 0} for h in range(6, 18)]},
    }
    text = report.compose(day)
    assert "Sun 11/15" in text and "Snowiest day: 11/21" in text and "6a: 18°" in text
    assert len(text) < 1500
    assert report.subject(day) == 'Beaver Creek 11/15: Grooming map, 3" next 5 days'
    payload = report.push_payload(day, "https://snow.0xm.studio/maps/2026-11-15.jpg")
    assert payload["title"] == "Beaver Creek · 11/15" and "New snow 3\"" in payload["body"]
    assert payload["image"].endswith(".jpg") and payload["url"].startswith("https://")


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
    monkeypatch.setattr(openmeteo, "fetch_history", lambda start, end: {})
    monkeypatch.setattr(snotel, "fetch_daily_precip", lambda begin, end: {})
    monkeypatch.setattr(openmeteo, "fetch_bands",
                        lambda: openmeteo.split_bands(bands_payload(), config.ELEVATION_BANDS))
    monkeypatch.setattr(snotel, "fetch", lambda: {
        "station": "842:CO:SNTL", "last_24h": {"snow_in": 0},
        "daily": {"2026-11-13": {"precip_in": 0.4, "depth_change_in": 5, "depth_in": 8},
                  "2026-11-14": {"precip_in": 0.0, "depth_change_in": -1, "depth_in": 7}}})
    monkeypatch.setattr(resort, "fetch", lambda: {"last_24h_in": 0.0, "base_in": 4.0, "season_in": 10.0})
    monkeypatch.setitem(resorts.RESORTS["beaver-creek"], "cams", [])  # no stake snapshot fetch
    monkeypatch.setitem(resorts.RESORTS["beaver-creek"], "opening_day", date(2026, 11, 1).isoformat())   # these tests are in season
    pdf = {"bytes": make_pdf()}

    def fake_groom():
        jpeg, text = grooming.render(pdf["bytes"])
        import hashlib
        return {"hash": hashlib.sha256(pdf["bytes"]).hexdigest()[:16], "jpeg": jpeg,
                "runs": {"groomers_of_the_day": [], "overnight": ["Flint"], "morning": ["Maverick"], "map_date": "November 14, 2026"},
                "text_lines": text.splitlines(), "last_modified": None}
    monkeypatch.setattr(grooming, "fetch", fake_groom)
    sent = []
    monkeypatch.setattr(notify, "send_all", lambda day, map_url, channels=None, slug=None: sent.append((report.compose(day), channels)) or {"email": "ok"})
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
    assert d["reason"].startswith("ready") and d["new_map"] and d["sent_at"]
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
    g = store.get_json("data/latest.json")["grooming"]
    assert g["new_map"] is False and g["runs"]["overnight"] == ["Flint"]   # run names carried over
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


def test_failed_send_and_missed_report_alert_the_owner(sandbox, monkeypatch):
    store, root, pdf, sent = sandbox
    from bcbot import alert
    alerts = []
    monkeypatch.setattr(alert, "admin", lambda title, body: alerts.append(title))
    monkeypatch.setattr(notify, "send_all", lambda day, map_url, channels=None, slug=None: {"email": "FAILED: Resend 429", "push": "1 delivered"})
    main.run(store=store, send=True, now=at(5, 45))
    r = main.run(store=store, send=True, now=at(7, 0))
    assert alerts == ["Snow Desk Beaver Creek: send failed"] and any("delivery" in e for e in r["errors"])
    for t in [at(9, 30), at(10, 0)]:      # it did go out (push), so no "missed" alert
        main.run(store=store, send=True, now=t)
    assert len(alerts) == 1


def test_missed_report_alerts_once(sandbox, monkeypatch):
    store, root, pdf, sent = sandbox
    from bcbot import alert
    alerts = []
    monkeypatch.setattr(alert, "admin", lambda title, body: alerts.append(title))
    monkeypatch.setattr(main, "_claim_send", lambda *a, **k: False)   # e.g. the send never happens
    monkeypatch.setattr(main, "send_decision", lambda *a, **k: None)
    for t in [at(7, 0), at(9, 15)]:
        main.run(store=store, send=True, now=t)
    assert alerts == []
    for t in [at(9, 30), at(9, 45), at(10, 30)]:
        main.run(store=store, send=True, now=t)
    assert alerts == ["Snow Desk Beaver Creek: no report yet"]


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


# ---------- web push (RFC 8291 / 8292) ----------

def test_webpush_matches_rfc8291_vector_and_roundtrips():
    from cryptography.hazmat.primitives.asymmetric import ec
    from bcbot import webpush as w
    ua = ec.derive_private_key(int.from_bytes(w.unb64u("q1dXpw3UpT5VOmu_cf_v6ih07Aems3njxI-JWgLcM94"), "big"), ec.SECP256R1())
    sender = ec.derive_private_key(int.from_bytes(w.unb64u("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"), "big"), ec.SECP256R1())
    ua_pub = "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
    body = w.encrypt(b"When I grow up, I want to be a watermelon", ua_pub, "BTBZMqHH6r4Tts7J_aSIgg",
                     salt=w.unb64u("DGv6ra1nlYgDCS1FRnbzlw"), sender_private=sender)
    assert w.b64u(body) == ("DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6Tlz"
                            "AC8wEqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN")
    fresh = w.encrypt(b'{"title":"x"}', ua_pub, "BTBZMqHH6r4Tts7J_aSIgg")
    assert w.decrypt(fresh, ua, "BTBZMqHH6r4Tts7J_aSIgg") == b'{"title":"x"}'


def test_vapid_header_is_a_valid_es256_jwt():
    import json as _json
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    from bcbot import webpush as w
    priv, pub = w.generate_vapid_keys()
    key = w.load_vapid_key(priv)
    assert w.vapid_public_b64(key) == pub
    h = w.vapid_header("https://fcm.googleapis.com/fcm/send/abc", key, "https://snow.0xm.studio")
    jwt = h.split("t=")[1].split(",")[0]
    head, claims, sig = jwt.split(".")
    c = _json.loads(w.unb64u(claims))
    assert c["aud"] == "https://fcm.googleapis.com" and c["sub"] == "https://snow.0xm.studio"
    raw = w.unb64u(sig)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    pubkey = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), w.unb64u(pub))
    pubkey.verify(der, f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))  # raises if invalid
    assert h.endswith("k=" + pub)


# ---------- email ----------

def test_daily_email_is_personal_with_one_click_unsubscribe(monkeypatch):
    from bcbot import mailer
    calls = []

    class R:
        ok = True
        def json(self):
            return {"data": []}
    monkeypatch.setattr("bcbot.mailer.http", lambda: type("H", (), {"post": lambda self, url, json=None, timeout=None, headers=None: calls.append((url, json)) or R()})())
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    recipients = [(f"skier{i}@example.com", f"tok{i}") for i in range(150)]
    day = {"date": "2026-11-15", "grooming": {"new_map": True, "runs": {"overnight": ["Flint"], "morning": []}},
           "forecast": {"days": [{"date": "2026-11-15", "snow": 3.0, "low": 1, "high": 6}], "next_1_5": 3, "next_6_10": 1}}
    html = mailer.daily_html(day, "https://snow.0xm.studio/maps/2026-11-15.jpg")
    assert "Flint" in html and "maps/2026-11-15.jpg" in html and "Beaver Creek · Sun 11/15" in html
    assert mailer.send_daily(recipients, "Subject", html, "text") == 150
    assert [len(b) for _, b in calls] == [100, 50] and all(u.endswith("/emails/batch") for u, _ in calls)
    first = calls[0][1][0]
    assert first["to"] == ["skier0@example.com"] and first["from"].endswith("@snow.0xm.studio>")
    assert first["headers"]["List-Unsubscribe"] == "<https://snow.0xm.studio/api/unsubscribe?t=tok0>"
    assert first["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "api/unsubscribe?t=tok0" in first["html"] and "tok1" not in first["html"]


def test_notify_skips_unconfigured_channels(monkeypatch):
    for k in ["RESEND_API_KEY", "DATABASE_URL", "SNOWDB_DATABASE_URL", "NTFY_TOPIC"]:
        monkeypatch.delenv(k, raising=False)
    r = notify.send_all({"date": "2026-11-15"}, None)
    assert r == {"email": "skipped (email not configured)", "push": "skipped (push not configured)", "ntfy": "skipped"}


def test_send_test_labels_and_leaves_schedule_alone(sandbox, monkeypatch):
    store, root, pdf, sent = sandbox
    main.run(store=store, send=False, now=at(5, 45))
    state_before = store.get_json("data/state.json")
    monkeypatch.setattr("bcbot.db.connect", lambda: __import__("contextlib").nullcontext(None))
    monkeypatch.setattr("bcbot.db.active_subscribers", lambda conn, resort=None: [("a@example.com", "t")])
    monkeypatch.setattr("bcbot.db.push_subscriptions", lambda conn, resort=None: [{"endpoint": "https://push.example/1"}])
    captured = []
    monkeypatch.setattr(notify, "send_all", lambda day, map_url, channels=None, slug=None: captured.append(day) or {"email": "sent to 1"})
    r = main.send_test(store)
    assert r["status"] == "ok" and captured[0]["test"] is True
    assert report.subject(captured[0]).startswith("Test · Beaver Creek")
    assert store.get_json("data/state.json") == state_before          # schedule untouched
    monkeypatch.setattr("bcbot.db.active_subscribers", lambda conn, resort=None: [("x@example.com", "t")] * 6)
    assert main.send_test(store)["status"] == "refused"
    monkeypatch.setattr("bcbot.db.active_subscribers", lambda conn, resort=None: [("a@example.com", "t")])
    monkeypatch.setattr("bcbot.db.push_subscriptions", lambda conn, resort=None: [{"endpoint": "https://push.example/1"}] * 6)
    assert main.send_test(store)["status"] == "refused"                 # app subscribers are protected too
    assert len(captured) == 1


# ---------- app notifications end to end (fake push service, fake database) ----------

def test_push_needs_the_vercel_key(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://test")
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    assert notify.push({"date": "2026-11-15"}, None, "beaver-creek") == "skipped (push not configured)"


def test_public_key_is_derived_from_the_private_key(monkeypatch):
    from bcbot import webpush as w
    priv, pub = w.generate_vapid_keys()
    monkeypatch.setenv("VAPID_PRIVATE_KEY", priv)
    assert w.vapid_public_b64(w.app_key()) == pub
    monkeypatch.delenv("VAPID_PRIVATE_KEY")
    assert w.app_key() is None


def test_daily_push_is_one_encrypted_notification_with_the_powder_alert(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import ec
    from bcbot import webpush as w
    priv, pub = w.generate_vapid_keys()
    monkeypatch.setenv("VAPID_PRIVATE_KEY", priv)
    monkeypatch.setenv("DATABASE_URL", "postgres://test")
    browsers = [ec.generate_private_key(ec.SECP256R1()) for _ in range(2)]
    subs = [{"endpoint": f"https://push.example/{i}", "p256dh": w.b64u(w._public_bytes(b)), "auth": w.b64u(bytes([i]) * 16)}
            for i, b in enumerate(browsers)]
    results, posts = [], []

    class R:
        def __init__(self, code): self.status_code = code

    class FakeHTTP:
        def post(self, url, data=None, timeout=None, headers=None):
            posts.append((url, data, headers))
            return R(201 if url.endswith("/0") else 410)
    monkeypatch.setattr(notify, "http", lambda: FakeHTTP())
    monkeypatch.setattr("bcbot.db.connect", lambda: __import__("contextlib").nullcontext(None))
    monkeypatch.setattr("bcbot.db.push_subscriptions", lambda conn, resort=None: subs)
    monkeypatch.setattr("bcbot.db.record_push_result", lambda conn, endpoint, status: results.append((endpoint, status)))

    day = {"date": "2026-11-15", "grooming": {"runs": {"overnight": ["Flint"]}}, "forecast": {"next_1_5": 8},
           "powder": report.powder_alert({"days": [{"snow": 5}, {"snow": 4}]})}
    assert notify.push(day, None, "beaver-creek") == "1 delivered, 1 expired, 0 failed"
    assert len(posts) == 2 and results == [("https://push.example/0", 201), ("https://push.example/1", 410)]
    url, body, headers = posts[0]
    assert headers["Content-Encoding"] == "aes128gcm" and headers["Authorization"].endswith("k=" + pub)
    payload = json.loads(w.decrypt(body, browsers[0], subs[0]["auth"]))
    assert payload["body"].startswith("❄️ Powder alert: 9\"") and "Flint" in payload["body"]


def test_powder_alert_never_adds_a_second_notification(sandbox, monkeypatch):
    store, root, pdf, sent = sandbox
    days = []
    monkeypatch.setattr(notify, "send_all", lambda day, map_url, channels=None, slug=None: days.append(day) or {"push": "ok"})
    monkeypatch.setattr(report, "powder_alert", lambda fc, name=None: "❄️ Powder alert")
    main.run(store=store, send=True, now=at(7))
    main.run(store=store, send=True, now=at(8))
    assert len(days) == 1 and days[0]["powder"] == "❄️ Powder alert"



# ---------- pre-season and "send as soon as confirmed" ----------

def test_preseason_sends_daily_at_seven_without_a_new_map(sandbox, monkeypatch):
    store, root, pdf, sent = sandbox
    monkeypatch.setitem(resorts.RESORTS["beaver-creek"], "opening_day", date(2026, 11, 25).isoformat())
    main.run(store=store, send=True, now=at(6, 0, day=14))
    main.run(store=store, send=True, now=at(7, 0, day=14))
    assert len(reports(sent)) == 1                               # Nov 14 at 7:00
    main.run(store=store, send=True, now=at(6, 50))
    assert len(reports(sent)) == 1                               # not before 7:00
    main.run(store=store, send=True, now=at(7, 0))
    main.run(store=store, send=True, now=at(7, 15))
    assert len(reports(sent)) == 2                               # Nov 15 at 7:00, once
    assert report.subject({"date": "2026-11-15", "preseason": True, "grooming": {}}).startswith("Beaver Creek 11/15: Opens 11/25")


def test_sends_as_soon_as_map_and_todays_snow_report_are_confirmed(sandbox, monkeypatch):
    store, root, pdf, sent = sandbox
    main.run(store=store, send=True, now=at(7, 0, day=14))           # yesterday's report
    sent.clear()
    stale = {"last_24h_in": 0.0, "stamps": {"LastUpdated": "November 14, 2026 5:10 AM"}}
    fresh = {"last_24h_in": 4.0, "stamps": {"LastUpdated": "November 15, 2026 5:20 AM"}}
    pdf["bytes"] = make_pdf("Tonight's map")
    monkeypatch.setattr(resort, "fetch", lambda: stale)
    main.run(store=store, send=True, now=at(4, 50))                  # before SEND_EARLIEST
    main.run(store=store, send=True, now=at(5, 5))                   # new map, old snow report
    assert reports(sent) == []
    monkeypatch.setattr(resort, "fetch", lambda: fresh)
    r = main.run(store=store, send=True, now=at(5, 25))              # both confirmed -> send now
    assert r["decision"] == "ready" and len(reports(sent)) == 1
    d = store.get_json("data/latest.json")["delivery"]
    assert d["snow_report_fresh"] is True and d["new_map"] is True
    main.run(store=store, send=True, now=at(5, 30))
    assert len(reports(sent)) == 1


def test_resort_stamp_dates():
    from datetime import date as D
    assert resort.is_fresh({"stamps": {"a": "2026-11-15T05:20:00"}}, D(2026, 11, 15)) is True
    assert resort.is_fresh({"stamps": {"a": "11/14/2026 5:10"}}, D(2026, 11, 15)) is False
    assert resort.is_fresh({"stamps": {"a": "Nov. 15, 2026"}}, D(2026, 11, 15)) is True
    assert resort.is_fresh({"stamps": {"a": "/Date(1794749400000)/"}}, D(2026, 11, 15)) is True
    assert resort.is_fresh({"stamps": {"Report": "Daily"}}, D(2026, 11, 15)) is None
    assert resort.is_fresh({}, D(2026, 11, 15)) is None


def test_real_beaver_creek_report_timestamp():
    from datetime import date as D
    html = 'FR.snowReportData = {"TwentyFourHourSnowfall":{"Inches":"1"},"LastUpdatedText":"Updated November 15, 2026 at 5:34 AM MST"};'
    r = resort.parse(html)
    assert r["updated_time"] == "5:34 AM"
    assert resort.is_fresh(r, D(2026, 11, 15)) is True and resort.is_fresh(r, D(2026, 11, 16)) is False


# ---------- several resorts ----------

def test_resort_store_keeps_beaver_creek_paths_and_nests_the_others(tmp_path):
    from bcbot.store import resort_store
    base = LocalStore(tmp_path)
    assert resort_store("beaver-creek", base).path("data/latest.json") == "data/latest.json"
    vail = resort_store("vail", base)
    assert vail.path("data/latest.json") == "data/vail/latest.json"
    assert vail.path("maps/2026-11-15.jpg") == "maps/vail/2026-11-15.jpg"
    vail.put_json("data/state.json", {"x": 1})
    assert (tmp_path / "data/vail/state.json").exists() and not (tmp_path / "data/state.json").exists()


def test_use_switches_every_per_resort_setting():
    try:
        r = config.use("vail")
        assert config.RESORT_NAME == "Vail" and config.GROOMING_PDF_URL.endswith("vail-mountain-grooming-map.pdf")
        assert config.RESORT_SNOW_REPORT_URL.startswith("https://www.vail.com/") and config.LAT == r["lat"]
        assert config.TZ.key == "America/Denver"
    finally:
        config.use("beaver-creek")
    assert config.RESORT_NAME == "Beaver Creek" and "beaver-creek" in config.GROOMING_PDF_URL


def test_each_resort_has_its_own_archive_state_and_send(sandbox, monkeypatch):
    store, root, pdf, sent = sandbox
    monkeypatch.setitem(resorts.RESORTS["vail"], "opening_day", "2026-11-01")
    slugs = []
    monkeypatch.setattr(notify, "send_all", lambda day, map_url, channels=None, slug=None:
                        slugs.append((slug, report.subject(day), map_url)) or {"email": "ok"})
    main.run(store=store, send=True, now=at(7), slug="beaver-creek")
    main.run(store=store, send=True, now=at(7), slug="vail")
    main.run(store=store, send=True, now=at(8), slug="vail")          # once a day per resort
    assert [s for s, _, _ in slugs] == ["beaver-creek", "vail"]
    assert slugs[1][1].startswith("Vail 11/15") and "/maps/vail/2026-11-15.jpg" in slugs[1][2]
    vail_day = json.loads((root / "data/vail/latest.json").read_text())
    assert vail_day["resort_slug"] == "vail" and vail_day["grooming"]["image"] == "maps/vail/2026-11-15.jpg"
    assert (root / "maps/vail/2026-11-15.jpg").exists() and (root / "maps/2026-11-15.jpg").exists()
    assert json.loads((root / "data/state.json").read_text())["last_sent_date"] == "2026-11-15"
    assert json.loads((root / "data/vail/state.json").read_text())["last_sent_date"] == "2026-11-15"


def test_resort_opening_days_are_independent(sandbox, monkeypatch):
    store, root, pdf, sent = sandbox
    monkeypatch.setitem(resorts.RESORTS["vail"], "opening_day", "2026-11-25")   # Vail pre-season, BC open
    main.run(store=store, send=True, now=at(7), slug="vail")
    main.run(store=store, send=True, now=at(7), slug="beaver-creek")
    assert json.loads((root / "data/vail/latest.json").read_text())["delivery"]["reason"] == "preseason"
    assert json.loads((root / "data/latest.json").read_text())["delivery"]["reason"] == "ready (map; report has no date)"


def test_run_all_covers_enabled_resorts(sandbox, monkeypatch):
    store, root, pdf, sent = sandbox
    monkeypatch.setenv("RESORTS", "beaver-creek,vail,nope")
    assert resorts.enabled() == ["beaver-creek", "vail"]
    out = main.run_all(store=store, send=False, now=at(6))
    assert set(out) == {"beaver-creek", "vail"} and all(r["status"] == "ok" for r in out.values())


def test_signup_input_only_keeps_enabled_resorts(monkeypatch):
    monkeypatch.setenv("RESORTS", "beaver-creek,vail")
    assert resorts.valid(["vail", "vail", "keystone", "x", "beaver-creek"]) == ["vail", "beaver-creek"]
    assert resorts.valid(None) == []


def test_resort_link_and_names_in_messages():
    day = {"date": "2026-11-15", "resort_slug": "vail", "resort_name": "Vail", "grooming": {"new_map": True}}
    assert report.app_url(day).endswith("/?resort=vail")
    assert report.push_payload(day, None)["url"].endswith("?resort=vail")
    assert report.push_payload(day, None)["tag"] == "report-vail-2026-11-15"
    assert report.app_url({"date": "2026-11-15", "resort_slug": "beaver-creek"}) == config.DASHBOARD_URL


def test_daily_email_has_a_choose_resorts_link(monkeypatch):
    from bcbot import mailer
    posted = []
    monkeypatch.setattr(mailer, "_post", lambda path, payload: posted.append(payload))
    mailer.send_daily([("a@example.com", "tok")], "s", "<p>x</p>", "x")
    assert "/api/resorts?t=tok" in posted[0][0]["html"] and "/api/resorts?t=tok" in posted[0][0]["text"]


def test_public_resorts_json_matches_resorts_py(monkeypatch):
    monkeypatch.delenv("RESORTS", raising=False)
    assert json.loads((config.ROOT / "public/resorts.json").read_text()) == resorts.public_list()


def test_claim_is_per_day_and_resort():
    from bcbot import db
    calls = []

    class Cur:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def execute(self, sql, args): calls.append((sql, args))
        def fetchone(self): return ("2026-11-15",)

    class Conn:
        def cursor(self): return Cur()
    assert db.claim_send(Conn(), "2026-11-15", "ready", "vail")
    assert "ON CONFLICT (day, resort)" in calls[0][0] and calls[0][1] == ("2026-11-15", "vail", "ready")


def test_every_resort_is_complete():
    for slug in resorts.RESORTS:
        r = resorts.get(slug)
        fts = [b["elevation_ft"] for b in r["bands"]]
        assert [b["key"] for b in r["bands"]] == ["base", "mid", "peak"] and fts == sorted(fts), slug
        assert fts[0] < r["elevation_ft"] <= fts[2], slug          # forecast point is on the mountain
        assert r["snotel"] and r["tz"] == "America/Denver" and r["opening_day"], slug
        assert r["region"] in ("Colorado", "Utah") and r["pass"] in ("Epic", "Ikon"), slug
        if r["dor_api"]:  # POWDR open feed
            assert r["snow_report"] == r["dor_api"] + "/api/v1/dor/drupal/snow-reports", slug
        elif r["snow_report"]:  # Vail-platform resorts; the others' reports aren't read yet
            assert r["snow_report"].startswith(r["site"] + "/the-mountain/mountain-conditions/"), slug


def test_resorts_running_at_once_never_share_settings():
    """Vercel runs concurrent requests in one process: each must keep its own resort's config."""
    import threading
    barrier, seen = threading.Barrier(len(resorts.RESORTS)), {}

    def work(slug):
        config.use(slug)
        barrier.wait()                      # every thread has switched before anyone reads
        seen[slug] = (config.RESORT, config.GROOMING_PDF_URL, config.LAT, tuple(config.SNOTEL_STATIONS))

    threads = [threading.Thread(target=work, args=(s,)) for s in resorts.RESORTS]
    [t.start() for t in threads]
    [t.join() for t in threads]
    for slug, (got, pdf, lat, snotel) in seen.items():
        r = resorts.get(slug)
        assert got == slug and pdf == r["grooming_pdf"] and lat == r["lat"] and list(snotel) == r["snotel"]


def test_colorado_and_utah_are_covered():
    names = {resorts.get(s)["name"] for s in resorts.enabled()}
    for n in ("Park City", "Telluride", "Snowmass", "Steamboat", "Winter Park", "Copper Mountain",
              "Arapahoe Basin", "Deer Valley", "Alta", "Snowbird", "Snowbasin", "Brighton", "Solitude"):
        assert n in names
    assert resorts.get("park-city")["snow_report"].endswith("/weather-report.aspx")
    assert resorts.get("alta")["snow_report"] is None and resorts.is_static("alta")
    assert not resorts.is_static("park-city") and not resorts.is_static("breckenridge")


def test_unread_snow_report_is_skipped(monkeypatch):
    config.use("alta")
    monkeypatch.setattr(resort, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("fetched")))
    assert resort.fetch() == {}


def test_static_resorts_only_run_on_the_half_hour():
    import importlib.util
    spec = importlib.util.spec_from_file_location("api_run", Path(__file__).resolve().parent.parent / "api" / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    slugs = ["beaver-creek", "alta", "park-city"]
    at = lambda m: datetime(2026, 11, 20, 12, m, tzinfo=timezone.utc)
    assert mod.due(slugs, now=at(5)) == ["beaver-creek", "park-city"]
    assert mod.due(slugs, now=at(30)) == slugs and mod.due(slugs, now=at(0)) == slugs
    assert mod.due(slugs, force=True, now=at(5)) == slugs
    assert mod.due(slugs, user_agent="vercel-cron/1.0", now=at(5)) == slugs


def test_park_city_two_runs_per_line():
    out = grooming.parse_runs(["November 3, 2026 06:24 AM", "1 Snow Dancer 2 Mellow Moose", "3 Sweet Pea", "4 Kokopelli", "2", "41"])
    assert out["groomed"] == ["Snow Dancer", "Mellow Moose", "Sweet Pea", "Kokopelli"]
    assert out["map_date"] == "November 3, 2026 06:24 AM"
    assert grooming.parse_runs(["MID-VAIL", "9 Highline 10 Lane 2", "11 Run 7 Up"])["groomed"] == ["Highline", "Lane 2", "Run 7 Up"]


# --- POWDR open feeds (Copper, Snowbird, Eldora) ---

def test_dor_snow_report_takes_newest_and_converts_cm():
    from bcbot.sources import dor
    reports = [
        {"date": "2026-11-14 05:00:00", "overnight_amount": 1, "base_depth": 10, "unit_of_measurement": "in",
         "computed": {"24_hour": 1, "total": 12}},
        {"date": "2026-11-15 05:30:00", "overnight_amount": 5.08, "base_depth": 50.8, "unit_of_measurement": "cm",
         "computed": {"24_hour": 5.08, "48_hour": 10.16, "7_day": "", "total": 76.2}},
    ]
    r = dor.parse_snow_report(reports)
    assert r["overnight_in"] == 2.0 and r["last_24h_in"] == 2.0 and r["last_48h_in"] == 4.0
    assert r["base_in"] == 20.0 and r["season_in"] == 30.0 and "last_7d_in" not in r
    assert r["updated_time"] == "5:30 AM"
    assert resort.is_fresh(r, TODAY) is True
    assert dor.parse_snow_report([]) == {} and dor.parse_snow_report({"x": 1}) == {}


def test_dor_trails_lists_groomed_winter_runs_by_sector():
    from bcbot.sources import dor
    trails = [
        {"name": "Main Vein", "sector": {"name": "Center Village"}, "type": "alpine_trail", "season": "winter", "groom_status": "groomed"},
        {"name": "Andy's Encore", "sector": {"name": "Center Village"}, "type": "alpine_trail", "season": "winter", "groom_status": "not_groomed"},
        {"name": "Bouncer", "sector": {"name": "East Village"}, "type": "alpine_trail", "season": "winter", "groom_status": "groomed"},
        {"name": "Bike Path", "sector": {"name": "East Village"}, "type": "bike_trail", "season": "summer", "groom_status": "groomed"},
        {"name": "Woodward", "sector": None, "type": "terrain_park_trail", "season": "winter", "groom_status": "groomed"},
    ]
    g = dor.parse_trails(trails)
    assert g["areas"] == {"Center Village": ["Main Vein"], "East Village": ["Bouncer"], "Groomed": ["Woodward"]}
    assert g["groomed"] == ["Main Vein", "Bouncer", "Woodward"]
    assert dor.parse_trails(None)["groomed"] == []


def test_dor_resorts_read_the_feed():
    for slug in ("copper", "snowbird", "eldora"):
        r = resorts.get(slug)
        assert r["dor_api"].startswith("https://api.") and r["snow_report"].endswith("/snow-reports")
        assert not resorts.is_static(slug)
        config.use(slug)
        assert config.DOR_API == r["dor_api"]
    config.use("beaver-creek")
    assert not config.DOR_API


def test_resort_fetch_routes_to_dor(monkeypatch):
    from bcbot.sources import dor
    monkeypatch.setattr(dor, "fetch_snow_report", lambda: {"overnight_in": 3.0})
    config.use("copper")
    try:
        assert resort.fetch() == {"overnight_in": 3.0}
    finally:
        config.use("beaver-creek")
