"""Public report pages for search engines and sharing (bcbot/pages.py).

GET /api/page                         -> /resorts hub
GET /api/page?resort=vail             -> today's Vail report
GET /api/page?resort=vail&date=...    -> that day's archived report
GET /api/page?resort=colorado         -> every Colorado resort in one table (also utah)
GET /api/page?resort=vail&date=guide  -> how Vail's report works (evergreen)
GET /api/page?feed=1[&resort=vail]    -> RSS: newest post per resort, or one resort's posts
GET /api/page?pass=epic-blackout-dates -> Epic (or Ikon) blackout dates, with "is today blacked out?"
GET /api/page?sitemap=1               -> sitemap.xml
(vercel.json rewrites the clean URLs /resorts, /resorts/<slug>[/<date>] and /sitemap.xml here.)
"""
import logging

from bcbot.web import Handler
from bcbot import llm, pages, resorts
from bcbot.store import get_store

LATEST = "public, max-age=300, s-maxage=600, stale-while-revalidate=3600"
ARCHIVE = "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800"


class handler(Handler):
    def send(self, code, body, content_type="text/html", cache=LATEST, canonical=None):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Cache-Control", cache if code == 200 else "public, s-maxage=300")
        if canonical:
            self.send_header("Link", f'<{canonical}>; rel="canonical"')
        if content_type != "text/html":
            self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def not_found(self, msg="Not found"):
        body = pages.shell(page_title="Not found | 0xSnow", desc=msg, canonical=pages.site("resorts"), noindex=True,
                           body=f'<h1 class="page">{msg}</h1><p><a href="/resorts">See all resorts</a></p>')
        self.send(404, body)

    def machine(self, store, slug, day_str, fmt):
        """Markdown and JSON twins of the HTML pages (bcbot/llm.py)."""
        import json
        md, js = "text/markdown", "application/json"
        if slug in pages.REGIONS and not day_str and fmt == "md":
            return self.send(200, llm.region_md(store, slug), md, canonical=pages.site("resorts/" + slug))
        if slug not in resorts.enabled():
            return self.send(404, "Not found\n", "text/plain")
        if day_str == "guide" and fmt == "md":
            return self.send(200, llm.guide_md(slug), md, "public, max-age=3600, s-maxage=21600",
                             canonical=pages.site(f"resorts/{slug}/guide"))
        dated = bool(day_str)
        if dated:
            day = pages.post_day(store, slug, day_str) if pages.valid_date(day_str) else None
        else:
            day = pages.latest_day(store, slug, pages.post_dates(store, slug))
        if not day or not day.get("date"):
            return self.send(404, "No report for that day\n", "text/plain")
        canonical = pages.site(pages.resort_path(slug, day_str if dated else None))
        cache = ARCHIVE if dated else LATEST
        if fmt == "json":
            return self.send(200, json.dumps(llm.report_json(slug, day, dated), indent=1), js, cache, canonical)
        return self.send(200, llm.report_md(slug, day, dated), md, cache, canonical)

    def do_GET(self):
        try:
            store = get_store()
            if self.query("sitemap"):
                return self.send(200, pages.sitemap(store), "application/xml", "public, s-maxage=3600")
            if self.query("llms"):
                return self.send(200, llm.llms_txt(), "text/plain", "public, max-age=3600, s-maxage=86400")
            pass_key = self.query("pass")
            if pass_key:
                if pass_key not in pages.PASSES:
                    return self.not_found()
                return self.send(200, pages.pass_page(pass_key), cache="public, max-age=600, s-maxage=3600")
            slug, day_str = self.query("resort"), self.query("date")
            fmt = None
            for ext in ("md", "json"):
                if slug and slug.endswith("." + ext):
                    slug, fmt = slug[:-len(ext) - 1], ext
                if day_str and day_str.endswith("." + ext):
                    day_str, fmt = day_str[:-len(ext) - 1], ext
            if fmt:
                return self.machine(store, slug, day_str, fmt)
            if self.query("feed"):
                if slug and slug not in resorts.enabled():
                    return self.not_found()
                return self.send(200, pages.feed_xml(store, slug or None), "application/rss+xml", "public, s-maxage=1800")
            if not slug:
                return self.send(200, pages.hub_page(), cache="public, max-age=3600, s-maxage=86400")
            if slug in pages.REGIONS and not day_str:
                return self.send(200, pages.region_page(store, slug))
            if slug not in resorts.enabled():
                return self.not_found("We don't cover that resort yet")
            if day_str == "guide":
                summary = store.get_json("data/observer/summary.json")
                return self.send(200, pages.guide_page(slug, summary), cache="public, max-age=3600, s-maxage=21600")
            dates = pages.post_dates(store, slug)
            if day_str:
                if not pages.valid_date(day_str):
                    return self.not_found()
                day = pages.post_day(store, slug, day_str)
                if not day or not day.get("date"):
                    return self.not_found("No report for that day")
                return self.send(200, pages.resort_page(slug, day, dates, dated=True), cache=ARCHIVE)
            day = pages.latest_day(store, slug, dates)
            if not day or not day.get("date"):
                return self.send(200, pages.empty_resort_page(slug))
            return self.send(200, pages.resort_page(slug, day, dates))
        except Exception:
            logging.exception("page failed")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b"Something went wrong. Try again in a minute.")
