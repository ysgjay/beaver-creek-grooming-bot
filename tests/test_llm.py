"""Machine-readable twins of the public pages (bcbot/llm.py) and the page shell's links to them."""
import json

from bcbot import llm, pages
from tests.test_pages import DAY


def test_llms_txt_lists_every_resort_with_md_and_json():
    t = llm.llms_txt()
    assert t.startswith("# 0xSnow\n\n> ")
    assert "https://snow.0xm.studio/resorts/vail.md" in t and "https://snow.0xm.studio/resorts/vail.json" in t
    assert "https://snow.0xm.studio/resorts/copper/guide.md" in t and "## Utah resorts" in t


def test_report_markdown_has_only_real_numbers():
    md = llm.report_md("vail", DAY)
    assert md.startswith("# Vail grooming and snow report, Wednesday 11/18/2026")
    assert "| New snow, 24 hours | 3\" |" in md and "Last 7 days" not in md
    assert "### Groomed overnight\n\n- Born Free" in md and "| 8 AM | 20 | 10 | 18 |" in md
    assert "Source page: https://snow.0xm.studio/resorts/vail" in md


def test_report_json_and_guide_markdown(monkeypatch):
    j = llm.report_json("beaver-creek", DAY)
    json.dumps(j)
    assert j["snow_in"]["base"] == 18 and j["grooming"]["all"][0] == "Born Free"
    assert j["facts"]["blackout_dates"]["source"].startswith("https://www.epicpass.com")
    g = llm.guide_md("copper")
    assert "## Lift hours" in g and "checked 11/19/2026" in g and "## Blackout dates" in g
    v = llm.guide_md("vail")
    assert "## Blackout dates" in v and "Epic Local Pass: 10 days total" in v
    from bcbot import facts as F
    monkeypatch.setattr(F, "FACTS", {})
    assert "hasn't collected sourced facts" in llm.guide_md("vail")


def test_pages_link_markdown_twin_and_follow_app_theme():
    html = pages.resort_page("vail", DAY, ["2026-11-18"])
    assert '<link rel="alternate" type="text/markdown" title="Markdown version" href="/resorts/vail.md">' in html
    assert '<script src="/appearance.js"></script>' in html and 'html[data-appearance="dark"]' in html
    assert 'href="/?resort=vail">Open in the app' in html and "/ Vail</span>" in html
    dated = pages.resort_page("vail", DAY, ["2026-11-18"], dated=True)
    assert 'href="/resorts/vail/2026-11-18.md"' in dated
    assert 'href="/resorts/copper/guide.md"' in pages.guide_page("copper", {})
