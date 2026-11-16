from datetime import date, datetime, timedelta

from bcbot import audit, config, forecast
from tests.test_bcbot import TODAY, openmeteo_payload
from bcbot.sources import openmeteo


def _fc():
    models = ["ncep_nbm_conus", "gfs_seamless", "ecmwf_ifs025", "icon_seamless"]
    rows = openmeteo._split_models(openmeteo_payload(models, precip=0.02), models)
    return forecast.build(rows, {TODAY.isoformat(): 3.0}, today=TODAY)


def test_live_rows_keep_raw_models_blend_and_average():
    rows = audit.live_rows(_fc(), TODAY)
    sources = {r[0] for r in rows}
    assert {"ncep_nbm_conus", "nws", "blend", "mean"} <= sources
    assert all(0 <= r[2] <= 9 for r in rows)
    nws = [r for r in rows if r[0] == "nws"]
    assert nws == [("nws", TODAY.isoformat(), 0, None, 3.0, None, None)]
    blend0 = next(r for r in rows if r[0] == "blend" and r[2] == 0)
    assert blend0[5] is not None and blend0[6] is not None  # the range that went out
    mean0 = next(r for r in rows if r[0] == "mean" and r[2] == 0)
    assert mean0[3] is not None  # water average over the models (NWS has none)


def test_truth_rows_put_morning_report_on_yesterday():
    obs = {"2026-11-14": {"precip_in": 0.3, "depth_change_in": 4, "swe_change_in": 0.25}}
    t = audit.truth_rows(obs, {"last_24h_in": 5, "updated_time": "5:34 AM"}, TODAY, True)
    assert t["2026-11-14"]["snotel_liquid"] == 0.3
    assert t["2026-11-14"]["resort_snow"] == 5 and t["2026-11-14"]["resort_updated"] == "5:34 AM"
    assert "resort_snow" not in audit.truth_rows({}, {"last_24h_in": 5}, TODAY, False).get("2026-11-14", {})


def test_grades_are_live_only_with_replay_as_a_hint():
    rows = []
    for i in range(12):
        o = 4.0 + i % 3
        for lead in (0, 1):
            rows += [("good", lead, "live", None, o + 0.2, None, o), ("mean", lead, "live", None, o + 2, None, o),
                     ("bad", lead, "live", None, o + 5, None, o)]
        rows += [("rep", 1, "replay", 0.3, None, 0.31, None), ("mean", 1, "replay", 0.5, None, 0.31, None)]
    g = audit.grades(audit.aggregate(rows))
    assert g["snow"]["good"]["short"]["grade"] == "A"
    assert g["snow"]["bad"]["short"]["grade"] == "D"
    assert g["snow"]["good"]["mid"]["grade"] == "New"
    rep = g["water"]["rep"]["short"]
    assert rep["grade"] == "New" and rep["hint"] == "A" and rep["n_replay"] == 12


def test_dry_days_dont_count_but_false_alarms_do():
    acc = audit._empty()
    audit.add(acc, "snow", 0.0, 0.0)
    audit.add(acc, "snow", 3.0, 0.0)
    assert acc[0] == 1 and acc[9] == 1 and acc[10] == 1


def test_summary_builds_ledger_trail_range_and_verdict():
    today = TODAY
    y = (today - timedelta(days=1)).isoformat()
    calls, truth = [], {y: {"resort_snow": 6.0, "snotel_liquid": 0.5, "snotel_depth": 5, "station": "842:CO:SNTL"}}
    for lead in range(4):
        issued = (today - timedelta(days=1 + lead)).isoformat()
        calls += [("blend", issued, y, lead + 0, "live", None, 5.0 + lead, 3.0, 8.0),
                  ("gfs_seamless", issued, y, lead, "live", 0.4, 4.0, None, None),
                  ("ncep_nbm_conus", issued, y, lead, "live", 0.5, 6.5, None, None)]
    calls = [(s, i, v, (date.fromisoformat(v) - date.fromisoformat(i)).days, k, a, b, c, d) for s, i, v, _, k, a, b, c, d in calls]
    nxt = (today + timedelta(days=2)).isoformat()
    calls.append(("blend", today.isoformat(), nxt, 2, "live", None, 9.0, 5.0, 12.0))
    config.use("beaver-creek")
    s = audit.summary("beaver-creek", calls, truth, [("2026-11-15", "gfs_seamless", 1.1, 1.0, 1.0, 1.0)], today)
    assert s["storms"][0]["date"] == y and s["storms"][0]["call3"] == 8.0
    assert s["storms"][0]["best"][0] == "ncep_nbm_conus"
    assert s["verdict"]["fell"] == 6.0 and s["verdict"]["best"] == "ncep_nbm_conus"
    assert s["range"] == {"n": 3, "inside": 3}
    assert [t["label"] for t in s["trails"]] == ["Next storm", "Last storm"]
    assert s["days"]["live"] == 1 and s["stations"] == ["842:CO:SNTL"]
    pooled = audit.pooled([s, s])
    assert pooled["agg"]["snow"]["blend"]["1"]["live"][0] == 2 * s["agg"]["snow"]["blend"]["1"]["live"][0]


def test_replay_rows_and_months():
    rows = audit.replay_rows({1: {"a": {"2025-01-02": 0.2}, "b": {"2025-01-02": 0.4}, "c": {"2025-01-02": 0.6}}})
    assert ("mean", "2025-01-02", 1, 0.4, None, None, None) in rows
    months = audit.replay_months(date(2026, 11, 16))
    assert months[0] == "2024-11" and "2025-06" not in months and months[-1] == "2026-11"
    assert audit.month_span("2026-11", date(2026, 11, 16)) == (date(2026, 11, 1), date(2026, 11, 15))
    assert audit.month_span("2025-02", date(2026, 11, 16))[1] == date(2025, 2, 28)


def test_migration_matches_schema():
    from pathlib import Path
    sql = (Path(__file__).resolve().parent.parent / "docs/migrations/004_audit.sql").read_text()
    assert audit.SCHEMA.strip() in sql


def test_record_is_a_no_op_without_a_database(monkeypatch):
    monkeypatch.delenv("SNOWDB_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert audit.record("beaver-creek", _fc(), {}, {}, {}, datetime(2026, 11, 15, 2, tzinfo=config.TZ), True) is None


# Runs against a real Postgres when AUDIT_TEST_DB is set (CI skips it).
import os
import pytest


@pytest.mark.skipif(not os.environ.get("AUDIT_TEST_DB"), reason="needs AUDIT_TEST_DB")
def test_database_round_trip(monkeypatch, tmp_path):
    import psycopg
    from bcbot import db
    from bcbot.store import LocalStore
    url = os.environ["AUDIT_TEST_DB"]
    monkeypatch.setenv("SNOWDB_DATABASE_URL", url)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS fc_calls, fc_truth, fc_weights, fc_backfill, fc_runs")
    fc = _fc()
    early = datetime(2026, 11, 15, 2, 10, tzinfo=config.TZ)
    obs = {"station": "842:CO:SNTL", "daily": {"2026-11-14": {"precip_in": 0.3, "depth_change_in": 4}}}
    verification = {"models": {"gfs_seamless": {"skill": 1.2, "bias_ratio": 1.1, "bias_by_lead": {"short": 1.05}}}}
    n = audit.record("beaver-creek", fc, obs, {"last_24h_in": 5}, verification, early, True)
    assert n > 30
    # A later run the same day doesn't overwrite the morning call.
    fc2 = dict(fc, days=[dict(d, snow=99.0) for d in fc["days"]])
    assert audit.record("beaver-creek", fc2, obs, {"last_24h_in": 6}, verification,
                        datetime(2026, 11, 15, 14, tzinfo=config.TZ), True) == 0
    with db.connect() as conn:
        calls, truth, weights = audit.load(conn, "beaver-creek")
        assert max(c[6] for c in calls if c[0] == "blend") < 99
        assert truth["2026-11-14"]["resort_snow"] == 6 and truth["2026-11-14"]["snotel_liquid"] == 0.3
        assert weights == [("2026-11-15", "gfs_seamless", 1.2, 1.05, 1.1, 1.1)]
        log_ = audit.log_days(conn, "beaver-creek", date(2026, 11, 10), date(2026, 11, 30))
        assert log_[0]["calls"] and any(d["date"] == "2026-11-14" for d in log_)
        assert audit.csv_rows(conn, "beaver-creek", date(2026, 11, 1), date(2026, 12, 1), "live", "blend", 0)

    # Replay: one month, with the network faked.
    monkeypatch.setattr(audit, "fetch_replay", lambda s, e: {1: {"gfs_seamless": {"2025-01-05": 0.4}, "icon_seamless": {"2025-01-05": 0.2},
                                                                 "ecmwf_ifs": {"2025-01-05": 0.3}}})
    monkeypatch.setattr(audit, "fetch_replay_truth", lambda s, e: ("842:CO:SNTL", {"2025-01-05": {"precip_in": 0.35}}))
    monkeypatch.setattr(audit, "replay_months", lambda today: ["2025-01"])
    store = LocalStore(tmp_path)
    out = audit.job(store=store, now=datetime(2026, 11, 16, 9, tzinfo=config.TZ), slugs=["beaver-creek"])
    assert out["replayed"][0]["rows"] == 4 and out["summarized"] == ["beaver-creek"]
    card = store.get_json("data/audit/beaver-creek.json")
    assert card["agg"]["water"]["gfs_seamless"]["1"]["replay"][0] == 1
    assert store.get_json("data/audit/all.json")["resorts"] == 1
    # Done months aren't fetched again.
    assert audit.job(store=store, now=datetime(2026, 11, 16, 9, tzinfo=config.TZ), slugs=["beaver-creek"])["replayed"] == []
