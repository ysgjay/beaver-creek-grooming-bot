from bcbot import stats

RESORTS = {"vail": {}, "beaver-creek": {}}


def test_clean_hit_accepts_app_payload():
    h = stats.clean_hit({"v": "abc123DEF456", "t": "forecast", "r": "vail", "s": True, "m": False}, RESORTS)
    assert h == {"vid": "abc123DEF456", "view": "forecast", "resort": "vail", "standalone": True, "mobile": False}


def test_clean_hit_rejects_junk():
    assert stats.clean_hit({"v": "short", "t": "today"}, RESORTS) is None
    assert stats.clean_hit({"v": "abc123DEF456", "t": "admin"}, RESORTS) is None
    assert stats.clean_hit({"v": "abc123DEF456'; drop", "t": "today"}, RESORTS) is None
    assert stats.clean_hit({"v": "abc123DEF456", "t": "today", "r": "nowhere", "s": "yes"}, RESORTS)["resort"] == ""


def test_authorized(monkeypatch):
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    assert not stats.authorized("Bearer ")
    monkeypatch.setenv("ADMIN_KEY", "short")
    assert not stats.authorized("Bearer short")
    monkeypatch.setenv("ADMIN_KEY", "a-long-enough-key")
    assert stats.authorized("Bearer a-long-enough-key")
    assert not stats.authorized("Bearer a-long-enough-kez")
    assert not stats.authorized(None)


def test_mask():
    assert stats.mask("young@example.com") == "y•••@example.com"
