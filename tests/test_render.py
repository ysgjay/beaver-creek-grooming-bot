"""Render pieces: our own Open-Meteo server with public fallback, the worker schedule, and the
shadow store that never touches the live archive."""
from datetime import datetime, timezone

import requests

from bcbot import store, worker
from bcbot.sources import openmeteo


class Resp:
    def __init__(self, status=200, text="{}"):
        self.status_code, self.text, self.ok = status, text, status < 400


def test_forecast_uses_our_server_first(monkeypatch):
    calls = []
    monkeypatch.setenv("OPEN_METEO_HOST", "snow-meteo")
    monkeypatch.setattr(openmeteo, "_http_get", lambda url, **o: calls.append(url) or Resp())
    openmeteo.get(openmeteo.FORECAST_URL, params={})
    openmeteo.get(openmeteo.ENSEMBLE_URL, params={})
    assert calls == ["http://snow-meteo:8080/v1/forecast", "http://snow-meteo:8080/v1/ensemble"]


def test_falls_back_to_public_api(monkeypatch):
    calls = []
    monkeypatch.setenv("OPEN_METEO_URL", "http://snow-meteo:8080/")

    def fake(url, **o):
        calls.append(url)
        if "snow-meteo" in url and len(calls) == 1:
            raise requests.ConnectionError("down")
        if "snow-meteo" in url:
            return Resp(400, "unknown model")
        return Resp()

    monkeypatch.setattr(openmeteo, "_http_get", fake)
    assert openmeteo.get(openmeteo.FORECAST_URL, params={}).ok
    assert openmeteo.get(openmeteo.FORECAST_URL, params={}).ok
    assert calls[1] == calls[3] == openmeteo.FORECAST_URL


def test_history_and_unset_server_stay_public(monkeypatch):
    calls = []
    monkeypatch.delenv("OPEN_METEO_URL", raising=False)
    monkeypatch.delenv("OPEN_METEO_HOST", raising=False)
    monkeypatch.setattr(openmeteo, "_http_get", lambda url, **o: calls.append(url) or Resp())
    openmeteo.get(openmeteo.FORECAST_URL, params={})
    monkeypatch.setenv("OPEN_METEO_URL", "http://snow-meteo:8080")
    openmeteo.get(openmeteo.HISTORY_URL, params={})
    assert calls == [openmeteo.FORECAST_URL, openmeteo.HISTORY_URL]


def test_worker_ticks_match_cloudflare_crons():
    at = lambda h, m: worker.is_tick(datetime(2026, 12, 1, h, m, tzinfo=timezone.utc))
    assert at(11, 5) and at(13, 55) and at(9, 15) and at(17, 45) and at(21, 0)
    assert not at(11, 7) and not at(9, 5) and not at(18, 0) and not at(21, 15) and not at(3, 0)


def test_worker_defaults_to_shadow(monkeypatch):
    monkeypatch.delenv("WORKER_MODE", raising=False)
    assert worker.mode() == "shadow"
    monkeypatch.setenv("WORKER_MODE", "LIVE")
    assert worker.mode() == "live"


def test_shadow_store_reads_live_writes_local(tmp_path):
    live = store.LocalStore(tmp_path / "live")
    live.put_json("data/latest.json", {"day": "live"})
    s = store.ShadowStore(live, tmp_path / "shadow")
    assert s.get_json("data/latest.json") == {"day": "live"}
    s.put_json("data/latest.json", {"day": "shadow"})
    s.put_bytes("maps/x.jpg", b"img", "image/jpeg")
    assert s.get_json("data/latest.json") == {"day": "shadow"}
    assert live.get_json("data/latest.json") == {"day": "live"}
    assert not live.exists("maps/x.jpg") and not s.exists("maps/x.jpg")  # images aren't kept in shadow
    assert s.list("data/") == ["data/latest.json"]


def test_get_store_shadow_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("STORE_MODE", "shadow")
    monkeypatch.setenv("SHADOW_DIR", str(tmp_path))
    monkeypatch.setenv("BLOB_PUBLIC_BASE", "https://example.public.blob.vercel-storage.com")
    s = store.get_store()
    assert isinstance(s, store.ShadowStore) and isinstance(s.live, store.BlobStore)


def test_start_tick_once_per_deploy(monkeypatch, tmp_path):
    monkeypatch.setenv("SHADOW_DIR", str(tmp_path))
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc")
    assert worker._start_tick_due() is True
    assert worker._start_tick_due() is False   # a restart of the same deploy skips it
    monkeypatch.setenv("RENDER_GIT_COMMIT", "def")
    assert worker._start_tick_due() is True    # a new deploy runs it again


def test_release_memory_reports_mb():
    mb = worker._release_memory()
    assert mb is None or mb > 0


def test_canadian_resorts_skip_nws(monkeypatch):
    from bcbot import config, resorts
    from bcbot.sources import mountain, nws
    called = []
    monkeypatch.setattr(nws, "get", lambda *a, **k: called.append(a) or (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(mountain, "get", lambda *a, **k: called.append(a) or (_ for _ in ()).throw(AssertionError))
    assert resorts.get("whistler-blackcomb")["country"] == "CA"
    assert resorts.get("beaver-creek")["country"] == "US"
    config.use("whistler-blackcomb")
    try:
        assert nws.fetch_snowfall() == {}
        assert mountain.fetch_discussion() is None
        assert called == []
    finally:
        config.use("beaver-creek")


def test_unchanged_map_is_not_rendered(monkeypatch):
    import hashlib
    from bcbot.sources import grooming
    from tests.test_bcbot import make_pdf
    pdf = make_pdf()

    class R:
        content, headers = pdf, {}
        def raise_for_status(self):
            pass
    monkeypatch.setattr(grooming, "get", lambda *a, **k: R())
    monkeypatch.setattr(grooming.config, "GROOMING_PDF_URL", "https://example.com/map.pdf", raising=False)
    digest = hashlib.sha256(pdf).hexdigest()[:16]
    rendered = []
    real = grooming.render
    monkeypatch.setattr(grooming, "render", lambda b: rendered.append(1) or real(b))
    same = grooming.fetch(digest)
    assert same["hash"] == digest and same["jpeg"] is None and same["text_lines"] and rendered == []
    new = grooming.fetch("something-else")
    assert new["jpeg"] and rendered == [1]


def test_compare_forecasts_flags_big_gaps(monkeypatch, tmp_path):
    live = store.LocalStore(tmp_path / "live")
    shadow = store.ShadowStore(live, tmp_path / "shadow")
    day = lambda *snow: {"forecast": {"days": [{"snow": s} for s in snow]}}
    store.ResortStore(live, "vail").put_json("data/latest.json", day(2, 3, 1))
    store.ResortStore(shadow, "vail").put_json("data/latest.json", day(2, 3, 2))
    store.ResortStore(live, "keystone").put_json("data/latest.json", day(1, 0, 0))
    store.ResortStore(shadow, "keystone").put_json("data/latest.json", day(6, 2, 0))
    monkeypatch.setattr(store, "get_store", lambda: shadow)
    out = worker.compare_forecasts(["vail", "keystone"])
    assert out["rows"] == ["vail 7/6", "keystone 8/1"]
    assert out["differ"] == ["keystone"]
