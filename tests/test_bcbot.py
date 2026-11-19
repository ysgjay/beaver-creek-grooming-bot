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
    assert v["models"]["dry"]["bias_ratio"] == 1.25  # clamped from 2.0
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
    v = verify.compute({}, lambda d: None, today=TODAY, priors={"gfs_seamless": 1.2})
    assert v["models"]["gfs_seamless"] == {"n": 0, "prior": 1.2, "bias_ratio": 1.2, "skill": 1.0,
                                           "bias_by_lead": {"short": 1.2, "mid": 1.2, "long": 1.2}}
    # One wet day (0.5" seen, 0.5" forecast) only nudges it: (0.5 + 1.2) / (0.5 + 1.0) = 1.13.
    obs, load = _archive(tmp_path, days=1, liquid=0.5)
    assert verify.compute(obs, load, today=TODAY, priors={"dry": 1.2})["models"]["dry"]["bias_ratio"] == 1.13
    # Ten such days: recent evidence wins, (5 + 1.2) / (5 + 1) = 1.03.
    obs, load = _archive(tmp_path, days=10, liquid=0.5)
    assert verify.compute(obs, load, today=TODAY, priors={"dry": 1.2})["models"]["dry"]["bias_ratio"] == 1.03


def test_priors_by_lead_move_with_recent_short_range_evidence(tmp_path):
    # A model wet at short range but dry a week out keeps that shape as recent days arrive.
    priors = {"dry": {"short": 0.9, "mid": 1.0, "long": 1.2}}
    v = verify.compute({}, lambda d: None, today=TODAY, priors=priors)
    assert v["models"]["dry"]["bias_by_lead"] == {"short": 0.9, "mid": 1.0, "long": 1.2}
    obs, load = _archive(tmp_path, days=10, liquid=0.5)  # recent short range says 1.0 (0.9 -> 0.98)
    by = verify.compute(obs, load, today=TODAY, priors=priors)["models"]["dry"]["bias_by_lead"]
    assert by["short"] == 0.98 and by["mid"] == 1.09 and by["long"] == 1.25  # long clamped


def test_terrain_priors_from_last_winter():
    days = [(date(2025, 12, 1) + timedelta(days=i)).isoformat() for i in range(40)]
    observed = {d: 0.2 for d in days}
    out = verify.terrain_priors({"coarse": {d: 0.1 for d in days},          # half of what fell
                                 "sharp": {d: 0.2 for d in days},
                                 "short": {d: 0.1 for d in days[:10]},      # too few days to trust
                                 "wild": {d: 0.01 for d in days}}, observed)
    assert out["coarse"]["bias_ratio"] == 1.25 and out["coarse"]["n"] == 40  # clamped from 2.0
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
    rows = openmeteo._split_models(openmeteo_payload(["gfs_global"], precip=0.01), ["gfs_global"])
    ens = {f"member{i:02d}_gfs025": [{"time": t, "precipitation": 0.01, "temperature_2m": 20} for t in _hours()]
           for i in range(12)}
    plain = forecast.build(rows, ensemble_rows=ens, today=TODAY)
    fixed = forecast.build(rows, ensemble_rows=ens, today=TODAY, verification={
        "models": {"gfs_global": {"bias_ratio": 1.5, "skill": 1.0}}, "snow_cal": {"ratio": 1.2}})
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
    assert len(calls) == 2 and "gfs_global" in out and "ecmwf_ifs" not in out


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
    assert forecast._ensemble_parent("member01_gfs025") == "gfs_global"
    assert forecast._ensemble_parent("ecmwf_ifs025") == "ecmwf_ifs025"


def test_priors_are_worked_out_once_a_season(tmp_path, monkeypatch):
    store, calls = LocalStore(tmp_path), []
    days = [(date(2025, 12, 1) + timedelta(days=i)).isoformat() for i in range(40)]

    def history(start, end):
        calls.append((start, end))
        return {"short": {"gfs_seamless": {d: 0.1 for d in days}},
                "mid": {"gfs_seamless": {d: 0.11 for d in days}}, "long": {}}
    monkeypatch.setattr(openmeteo, "fetch_history_by_lead", history)
    monkeypatch.setattr(snotel, "fetch_daily_precip",
                        lambda b, e: {"station": "842:CO:SNTL", "daily": {d: 0.12 for d in days}})
    errors = []
    want = {"gfs_seamless": {"short": 1.2, "mid": 1.09}}
    assert main._terrain_priors(store, TODAY, errors) == want
    assert main._terrain_priors(store, TODAY + timedelta(days=1), errors) == want
    assert len(calls) == 1 and not errors
    assert store.get_json("data/priors.json")["season"] == "2025-11-01"
    # Priors saved by the old single-range method are worked out again.
    store.put_json("data/priors.json", {"season": "2025-11-01", "models": {"gfs_seamless": {"bias_ratio": 1.6}}})
    assert main._terrain_priors(store, TODAY + timedelta(days=2), errors) == want and len(calls) == 2


def test_history_by_lead_sums_full_days_only():
    times = [f"2026-01-01T{h:02d}:00" for h in range(24)] + [f"2026-01-02T{h:02d}:00" for h in range(10)]
    payload = {"hourly": {"time": times,
                          "precipitation_previous_day1_gfs_seamless": [0.01] * 34,
                          "precipitation_previous_day3_gfs_seamless": [None] * 34,
                          "precipitation_previous_day5_gfs_seamless": [0.02] * 34,
                          "precipitation_previous_day1_ukmo_seamless": [0.0] * 34}}
    out = openmeteo.split_history_by_lead(payload, ["gfs_seamless", "ukmo_seamless"])
    assert out["short"]["gfs_seamless"] == {"2026-01-01": 0.24}  # 01-02 has only 10 hours
    assert out["long"]["gfs_seamless"] == {"2026-01-01": 0.48}
    assert "gfs_seamless" not in out["mid"]
    assert "gfs_hrrr" in openmeteo.NO_PRIOR_MODELS


def test_blend_uses_range_correction_and_is_anchored_to_nws_and_nbm():
    rows = [{"time": f"{(TODAY + timedelta(days=d)).isoformat()}T{h:02d}:00", "precipitation": 0.05,
             "temperature_2m": 20, "relative_humidity_2m": 90} for d in range(10) for h in range(24)]
    raw = forecast.daily_totals(rows)[TODAY.isoformat()]["snow"]
    ver = {"models": {"gfs_seamless": {"bias_ratio": 1.2, "bias_by_lead": {"short": 1.2, "mid": 1.0, "long": 0.8}}}}
    fc = forecast.build({"gfs_seamless": rows}, verification=ver, today=TODAY)
    assert fc["days"][0]["snow"] == round(raw * 1.2, 1)
    assert fc["days"][3]["snow"] == round(raw * 1.0, 1)
    assert fc["days"][7]["snow"] == round(raw * 0.8, 1)
    # A blend far above both the NWS forecasters and NOAA's blend is held to 1.5x the larger.
    nbm = [dict(r, precipitation=0.001) for r in rows]
    nws = {TODAY.isoformat(): 2.0}
    fc = forecast.build({"gfs_seamless": rows, "ncep_nbm_conus": nbm}, nws_daily=nws, today=TODAY)
    d0 = fc["days"][0]
    assert d0["capped"] and d0["snow"] == 3.0 and d0["high"] >= 3.0


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
    assert report.subject(day) == 'Beaver Creek: 3" new, 3" next 5 days'
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
    monkeypatch.setattr(openmeteo, "fetch_history_by_lead", lambda start, end: {})
    from bcbot.sources import mountain
    monkeypatch.setattr(mountain, "fetch_avalanche", lambda: None)
    monkeypatch.setattr(mountain, "fetch_discussion", lambda: None)
    monkeypatch.setattr(mountain, "fetch_stations", lambda: None)
    monkeypatch.setattr(mountain, "fetch_nohrsc", lambda: None)
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

    def fake_groom(known_hash=None):
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
    assert alerts == ["0xSnow Beaver Creek: send failed"] and any("delivery" in e for e in r["errors"])
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
    assert alerts == ["0xSnow Beaver Creek: no report yet"]


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
    assert "1 groomed" in html and "maps/2026-11-15.jpg" in html and "Beaver Creek</h1>" in html and "11/15" in html
    assert "Open Snow Desk" not in html and "Open 0xSnow" not in html and "See the full report" in html and "frosted-logo-email.png" in html
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
    assert report.subject({"date": "2026-11-15", "preseason": True, "grooming": {}}).startswith("Beaver Creek: Opens 11/25")


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
    assert slugs[1][1].startswith("Vail: ") and "/maps/vail/2026-11-15.jpg" in slugs[1][2]
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


NO_SNOTEL = ("British Columbia", "Alberta", "Quebec", "Vermont", "New Hampshire", "Maine", "New York", "Pennsylvania",
             "West Virginia")


REGION_TZ = {
    "Colorado": "America/Denver", "Utah": "America/Denver", "Wyoming": "America/Denver", "Montana": "America/Denver",
    "New Mexico": "America/Denver", "Idaho": "America/Boise", "California": "America/Los_Angeles",
    "Washington": "America/Los_Angeles", "Oregon": "America/Los_Angeles", "British Columbia": "America/Vancouver",
    "Alberta": "America/Edmonton", "Quebec": "America/Toronto", "Vermont": "America/New_York",
    "New Hampshire": "America/New_York", "Maine": "America/New_York", "New York": "America/New_York",
    "Pennsylvania": "America/New_York", "West Virginia": "America/New_York",
}


def test_every_resort_is_complete():
    for slug in resorts.RESORTS:
        r = resorts.get(slug)
        fts = [b["elevation_ft"] for b in r["bands"]]
        assert [b["key"] for b in r["bands"]] == ["base", "mid", "peak"] and fts == sorted(fts), slug
        assert fts[0] < r["elevation_ft"] <= fts[2], slug          # forecast point is on the mountain
        # SNOTEL covers the western US only; Big Bear and Mammoth have none close enough
        no_snotel = r["region"] in NO_SNOTEL or slug in ("big-bear", "mammoth", "whitefish")
        assert (r["snotel"] or no_snotel) and r["opening_day"], slug
        from zoneinfo import ZoneInfo
        assert ZoneInfo(r["tz"]) and r["tz"] == REGION_TZ[r["region"]], slug
        assert r["pass"] in ("Epic", "Ikon", "Mountain Collective", "Indy", "Independent"), slug
        assert r["enabled"] or r.get("stage") == "shadow", slug  # new resorts start in shadow mode
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


def test_no_send_in_the_evening():
    """A resort added (or a run forced) at night refreshes its data but doesn't email until morning."""
    tz = config.TZ
    evening = datetime(2026, 11, 15, 19, 0, tzinfo=tz)
    assert main.send_decision({}, evening, map_new=True, resort_fresh=True, has_map=False) is None
    morning = datetime(2026, 11, 16, 9, 5, tzinfo=tz)
    assert main.send_decision({}, morning, map_new=True, resort_fresh=None, has_map=False) is not None


def test_day_ticket_email_without_map_lists_runs_and_subject_carries_numbers():
    from bcbot import mailer
    hours = [{"time": f"2026-11-16T{h:02d}:00", "temp": 20 + h - 6, "feels": 10 + h - 6, "dir": "NW", "wind": 9,
              "gust": 14 + 2 * (h - 6), "snow": 0} for h in range(6, 18)]
    day = {"date": "2026-11-16", "resort_name": "Keystone", "resort_slug": "keystone",
           "resort": {"last_24h_in": 2, "base_in": 18, "updated_time": "6:42 AM"},
           "grooming": {"new_map": True, "runs": {"groomers_of_the_day": ["Schoolmarm"], "groomed": ["Schoolmarm", "Flying Dutchman"]}},
           "hourly": {"hours": hours},
           "forecast": {"days": [{"date": "2026-11-16", "snow": 3.0, "low": 1, "high": 6}], "next_1_5": 3, "next_1_5_range": [1, 6]}}
    html = mailer.daily_html(day, None)
    assert "Flying Dutchman" in html and "Schoolmarm" in html and "<img src=\"https://snow" in html  # logo only
    assert "8a" in html and "4p" in html and "6a" not in html          # first chair to last
    assert "Mon<br>11/16" in html and "1–6" in html
    assert "Groomers of the day: Schoolmarm" in mailer.preheader(day)
    assert report.subject(day) == 'Keystone: 2" new, 2 groomed, gusts to 34 mph'


def test_resubmitting_signup_as_active_subscriber_emails_a_resort_update_link(monkeypatch):
    from bcbot import mailer
    posted = []
    monkeypatch.setattr(mailer, "_post", lambda path, payload: posted.append(payload))
    mailer.send_resort_update("a@example.com", "tok", ["beaver-creek", "vail"])
    p = posted[0]
    assert p["to"] == ["a@example.com"] and "Update" in p["subject"]
    assert "/api/resorts?t=tok&pick=beaver-creek%2Cvail" in p["html"] and "Beaver Creek and Vail" in p["html"]
    assert "Nothing changes until you tap Save" in p["text"]


# ---------- combined email ----------

def _digest_day(slug, name, snow, gotd, image=None):
    return {"date": "2026-11-16", "resort_slug": slug, "resort_name": name,
            "resort": {"last_24h_in": snow, "base_in": 20, "updated_time": "6:40 AM"},
            "grooming": {"image": image, "runs": {"groomers_of_the_day": gotd, "groomed": gotd + ["Extra"]}},
            "hourly": {"hours": [{"time": f"2026-11-16T{h:02d}:00", "temp": 20, "feels": 10, "dir": "W", "wind": 5,
                                  "gust": 12, "snow": 0} for h in range(6, 18)]},
            "forecast": {"next_1_5": 4, "days": []}}


def test_digest_waits_for_every_resort_until_the_cutoff():
    from datetime import datetime
    from bcbot import digest
    subs = [("a@x.com", "ta", ["vail", "copper"]), ("b@x.com", "tb", ["vail", "alta"])]
    days = {"vail": _digest_day("vail", "Vail", 2, ["Born Free"]), "copper": _digest_day("copper", "Copper Mountain", 1, [])}
    early = datetime(2026, 11, 16, 6, 10, tzinfo=digest.TZ)
    late = datetime(2026, 11, 16, 6, 30, tzinfo=digest.TZ)
    assert digest.plan(subs, {"vail", "copper"}, days, early) == [("a@x.com", "ta", ["vail", "copper"], [])]
    assert digest.plan(subs, {"vail"}, days, early) == []                 # before 6:30: waits for every resort
    assert digest.plan(subs, {"vail"}, days, late)[0] == ("a@x.com", "ta", ["vail", "copper"], [])  # 6:30: all info in
    assert digest.plan(subs, {"vail"}, days, late)[1] == ("b@x.com", "tb", ["vail"], ["alta"])
    assert digest.plan(subs, set(), {}, late) == []                       # nothing in: nothing sent


def test_digest_email_summarizes_each_resort_with_links():
    from datetime import datetime
    from bcbot import digest, mailer
    picked = [("vail", _digest_day("vail", "Vail", 2, ["Born Free", "Riva Ridge"], "maps/vail/2026-11-16.jpg")),
              ("copper", _digest_day("copper", "Copper Mountain", 0, ["Main Vein"]))]
    html = mailer.digest_html(picked, ["alta"], datetime(2026, 11, 16, 6, 30, tzinfo=digest.TZ))
    assert "Your mountains" in html and "Mon 11/16" in html and "2 of 3 reports in" in html
    assert "Born Free" in html and "Main Vein" in html and "Report pending" in html and "Alta" in html
    assert "?resort=vail" in html and "maps/vail/2026-11-16.jpg" in html and "Open Snow Desk" not in html
    assert mailer.digest_subject(picked, ["alta"]) == 'Vail 2" new, Copper Mountain 2 groomed, Alta pending'
    assert "Full report:" in mailer.digest_text(picked, ["alta"])


def test_resort_email_skips_multi_resort_subscribers(monkeypatch):
    seen = {}
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setattr(notify, "_db_url", lambda: "postgres://x")
    monkeypatch.setattr("bcbot.db.connect", lambda: __import__("contextlib").nullcontext(None))
    monkeypatch.setattr("bcbot.db.active_subscribers", lambda conn, resort=None, single_only=False: seen.setdefault("single", single_only) and [])
    assert notify.email({"date": "2026-11-16"}, None, "vail") == "no subscribers" and seen["single"] is True


def test_digest_radar_and_opt_in_grooming_maps():
    from datetime import datetime
    from bcbot import digest, mailer
    picked = [("vail", _digest_day("vail", "Vail", 2, ["Born Free"], "maps/vail/2026-11-16.jpg"))]
    now = datetime(2026, 11, 16, 6, 30, tzinfo=digest.TZ)
    off = mailer.digest_html(picked, [], now, radar_url="https://snow.0xm.studio/radar/email/x.png", maps=False, token="tok")
    assert "radar/email/x.png" in off and "Radar · Colorado and Utah · 6:30 AM MT" in off
    assert '<img src="https://snow.0xm.studio/maps/vail' not in off and "Turn them on" in off and "api/resorts?t=tok" in off
    on = mailer.digest_html(picked, [], now, maps=True, token="tok")
    assert '<img src="https://snow.0xm.studio/maps/vail/2026-11-16.jpg"' in on and "Turn them on" not in on and "Radar" not in on


def test_radar_snapshot_renders_frost_and_blue_only():
    import io
    from PIL import Image
    from bcbot import radar

    def fetch(url):
        color = (0, 200, 0, 255) if "nexrad" in url else (242, 239, 233, 255)
        b = io.BytesIO()
        Image.new("RGBA", (256, 256), color).save(b, "PNG")
        return b.getvalue()
    img = Image.open(io.BytesIO(radar.render(fetch))).convert("RGB")
    assert img.width == radar.OUT_W
    r, g, b = img.getpixel((5, 5))
    assert b > r and b >= g                                  # blue echo over frost, never burgundy


def test_saved_verification_takes_current_limits_when_snotel_is_down():
    stored = {"models": {"gfs_hrrr": {"n": 0, "prior": 1.6, "bias_ratio": 1.6, "skill": 1.0},
                         "gfs_seamless": {"n": 0, "prior": 1.6, "bias_ratio": 1.6, "skill": 1.0},
                         "icon_seamless": {"n": 6, "prior": 1.1, "bias_ratio": 1.5, "skill": 1.2},
                         "nws": {"n": 0, "bias_ratio": 1.0, "skill": 1.0}}, "snow_cal": {"ratio": 1.1}}
    # No new-style priors saved yet: old ones are held to the current limit, HRRR goes to 1.0.
    v = verify.refresh(stored, {}, no_prior={"gfs_hrrr"})
    assert v["models"]["gfs_hrrr"]["bias_by_lead"] == {"short": 1.0, "mid": 1.0, "long": 1.0}
    assert v["models"]["gfs_seamless"]["bias_ratio"] == 1.25
    assert v["models"]["icon_seamless"]["bias_ratio"] == 1.25 and v["models"]["icon_seamless"]["skill"] == 1.2
    assert v["models"]["nws"]["bias_ratio"] == 1.0 and v["snow_cal"] == {"ratio": 1.1}
    # With range priors saved, unscored models take them.
    v = verify.refresh(stored, {"gfs_seamless": {"short": 1.1, "mid": 1.2, "long": 0.9}}, no_prior={"gfs_hrrr"})
    assert v["models"]["gfs_seamless"]["bias_by_lead"] == {"short": 1.1, "mid": 1.2, "long": 0.9}


def test_ceiling_is_never_below_a_models_own_call():
    rows = lambda p: [{"time": f"{(TODAY + timedelta(days=d)).isoformat()}T{h:02d}:00", "precipitation": p,
                       "temperature_2m": 20, "relative_humidity_2m": 90} for d in range(10) for h in range(24)]
    ens = {f"member{i:02d}_gfs025": rows(0.001) for i in range(20)}  # every run nearly dry
    fc = forecast.build({"gfs_seamless": rows(0.02), "ukmo_seamless": rows(0.001)}, ensemble_rows=ens, today=TODAY)
    d0 = fc["days"][0]
    assert d0["high"] == fc["days"][0]["models"]["gfs_seamless"] > d0["snow"]
    gfs5 = sum(x["models"]["gfs_seamless"] for x in fc["days"][:5])
    assert fc["next_1_5_range"][1] == round(gfs5, 1)


def test_avalanche_zone_and_station_parsing():
    from bcbot.sources import mountain
    square = [[-107, 39], [-106, 39], [-106, 40], [-107, 40], [-107, 39]]
    payload = {"features": [
        {"geometry": {"type": "Polygon", "coordinates": [[[-112, 40], [-111, 40], [-111, 41], [-112, 41], [-112, 40]]]},
         "properties": {"name": "Salt Lake", "center_id": "UAC", "danger_level": "-1"}},
        {"geometry": {"type": "MultiPolygon", "coordinates": [[square]]},
         "properties": {"name": "Vail", "center": "CAIC", "center_id": "CAIC", "danger_level": "2",
                        "link": "https://avalanche.state.co.us/"}}]}
    z = mountain.avalanche_zone(payload, 39.59, -106.52)
    assert z["zone"] == "Vail" and z["danger"] == "Moderate" and z["level"] == 2
    assert mountain.avalanche_zone(payload, 40.58, -111.64)["danger"] is None
    assert mountain.avalanche_zone(payload, 35.0, -100.0) is None
    stations = {"STATION": [
        {"NAME": "Town", "STID": "T", "ELEVATION": "7400", "DISTANCE": 1,
         "OBSERVATIONS": {"air_temp_value_1": {"value": 40}}},
        {"NAME": "Summit", "STID": "S", "ELEVATION": "11200", "DISTANCE": 3,
         "OBSERVATIONS": {"air_temp_value_1": {"value": 18.4, "date_time": "t"}, "snow_depth_value_1": {"value": 12.2}}},
        {"NAME": "Dead", "STID": "D", "ELEVATION": "10000", "DISTANCE": 2, "OBSERVATIONS": {}}]}
    out = mountain.parse_stations(stations, 7800)
    assert [s["id"] for s in out] == ["S"] and out[0]["temp_f"] == 18 and out[0]["depth_in"] == 12


def test_new_ensembles_inherit_their_parents_correction():
    assert forecast._ensemble_parent("member03_ecmwf_aifs025_ensemble") is None
    assert forecast._ensemble_parent("member03_ecmwf_ifs025_ensemble") == "ecmwf_ifs025"
    assert forecast._ensemble_parent("member03_ncep_gefs025") == "gfs_global"
    assert forecast._ensemble_parent("member03_icon_seamless_eps") == "icon_seamless"
    assert forecast._ensemble_parent("member03_gem_global_ensemble") == "gem_seamless"
    assert forecast._ensemble_parent("member03_ukmo_global_ensemble_20km") == "ukmo_seamless"


NOHRSC_PAGE = """
<table class="gray_data_table" cellspacing="2" summary="x"><caption><strong>Raw Snowfall Observations</strong></caption>
<tbody><tr><td class="desc"><a href="#">ATAU1</a></td><td class="desc">ALTA</td><td>8684</td><td>2.50</td><td>24</td><td>2026-11-17 01</td><td>0.7 mi NNE</td></tr></tbody></table>
<table class="gray_data_table" cellspacing="2" summary="x"><caption><strong>Snow Depth Observations</strong></caption>
<thead><tr><th scope="col">Station ID</th></tr></thead><tbody>
<tr><td class="desc"><a href="#">CLN</a></td><td class="desc">ALTA - COLLINS</td><td>9629</td><td>19.00</td><td>2026-11-16 23</td><td>0.3 mi SSE</td></tr>
<tr><td class="desc"><a href="#">X</a></td><td class="desc">TOWN</td><td>5100</td><td>0.00</td><td>2026-11-16 23</td><td>9 mi W</td></tr>
<tr><td class="desc"><a href="#">AGD</a></td><td class="desc">ALTA - GUARD HOUSE</td><td>8714</td><td>3.00</td><td>2026-11-17 00</td><td>0.7 mi N</td></tr>
</tbody></table>"""


def test_nohrsc_nearest_observations_give_on_mountain_depth():
    from bcbot.sources import mountain
    out = mountain.parse_nohrsc(NOHRSC_PAGE)
    assert out["snowfall"][0] == {"id": "ATAU1", "name": "Alta", "elevation_ft": 8684.0, "value_in": 2.5,
                                  "hours": 24.0, "time_utc": "2026-11-17 01", "distance_mi": 0.7}
    rows = mountain.mountain_depth(out, 8500)
    assert [r["id"] for r in rows] == ["CLN", "AGD"]
    assert rows[0]["name"] == "Alta - Collins" and rows[0]["depth_in"] == 19 and rows[0]["temp_f"] is None
    # Another ski area 7.7 mi away is not "on this mountain" (Beaver Creek showed Vail Mid-Mtn).
    far = {"depth": [{"id": "CAVMM_MADIS", "name": "Vail Ski Area Mid-Mtn", "elevation_ft": 10328.0,
                      "value_in": 4.0, "time_utc": "x", "distance_mi": 7.7}]}
    assert mountain.mountain_depth(far, 7800) == []


def test_emails_show_next_7_day_snow_total():
    from datetime import datetime
    from bcbot import digest, mailer
    days7 = [{"date": f"2026-11-{16 + i}", "snow": 2.0} for i in range(10)]
    vail = _digest_day("vail", "Vail", 2, ["Born Free"])
    vail["forecast"] = {"next_1_5": 10, "next_1_7": 14, "days": days7}
    alta = _digest_day("alta", "Alta", 15, [])
    alta["forecast"] = {"next_1_5": 10, "days": days7}           # older forecast without next_1_7: summed from days
    html = mailer.digest_html([("vail", vail), ("alta", alta)], [], datetime(2026, 11, 16, 6, 30, tzinfo=digest.TZ))
    assert 'next 7 days 14"' in html and "7 DAY" in html
    assert mailer.next_7(alta["forecast"]) == 14
    assert "next 7 days" in mailer.digest_text([("vail", vail)], [])
    assert mailer.next_7({"days": days7[:3]}) is None


def test_combined_email_has_7_daily_snow_tiles_per_resort():
    from datetime import datetime
    from bcbot import digest, mailer
    vail = _digest_day("vail", "Vail", 2, [])
    vail["forecast"] = {"next_1_5": 5, "days": [{"date": f"2026-11-{16 + i}", "snow": float(i)} for i in range(10)]}
    html = mailer.digest_html([("vail", vail)], [], datetime(2026, 11, 16, 6, 30, tzinfo=digest.TZ))
    assert "Sun<br>11/22" in html and "Mon<br>11/23" not in html     # 7 days: 11/16 to 11/22


def test_wave_1_resorts_run_only_in_shadow_mode(monkeypatch):
    shadow = resorts.shadow()
    assert {"whistler-blackcomb", "heavenly", "stowe", "killington"} <= set(shadow)
    assert not set(shadow) & set(resorts.enabled())                    # not in the app or the sends
    assert not set(shadow) & {r["slug"] for r in resorts.public_list()["resorts"]}
    from bcbot import worker
    seen = {}
    monkeypatch.setattr("bcbot.main.run", lambda force=False, slug=None: seen.setdefault(slug, {"status": "skipped"}))
    monkeypatch.setenv("WORKER_MODE", "shadow")
    worker.tick(force=True)
    assert set(shadow) <= set(seen)
    seen.clear()
    monkeypatch.setenv("WORKER_MODE", "live")
    monkeypatch.setattr("api.run._digest", lambda: None)
    worker.tick(force=True)
    assert not set(shadow) & set(seen)


def test_wave_2_resorts_are_in_shadow_and_read_no_resort_page_yet():
    wave2 = ["jackson-hole", "big-sky", "banff-sunshine", "lake-louise", "sun-valley", "mammoth", "palisades-tahoe",
             "big-bear", "crystal-mountain", "tremblant", "sugarbush", "stratton", "snowshoe"]
    assert set(wave2) <= set(resorts.shadow())
    for slug in wave2:
        r = resorts.get(slug)
        assert r["snow_report"] is None and resorts.is_static(slug), slug  # no keyed feeds, no page reader yet


def test_wave_3_and_4_resorts_are_in_shadow():
    wave3 = ["sugarloaf", "sunday-river", "loon", "whiteface", "gore", "taos", "whitefish", "grand-targhee", "revelstoke",
             "jay-peak", "loveland", "wolf-creek", "mt-hood-meadows", "big-white"]
    wave4 = ["powder-mountain", "saddleback", "holiday-valley", "bretton-woods", "smugglers-notch", "mad-river-glen",
             "cannon", "waterville-valley", "purgatory", "tamarack", "sun-peaks", "mt-baker"]
    for slug in wave3 + wave4:
        assert slug in resorts.shadow() and slug not in resorts.enabled(), slug
        assert resorts.get(slug)["snow_report"] is None and resorts.is_static(slug), slug


def test_the_next_50_are_all_registered():
    assert len(resorts.RESORTS) == 72 and len(resorts.shadow()) == 50
