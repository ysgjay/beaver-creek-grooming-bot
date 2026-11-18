"""Public report pages for search engines and sharing (bcbot/pages.py).

GET /api/page                         -> /resorts hub
GET /api/page?resort=vail             -> today's Vail report
GET /api/page?resort=vail&date=...    -> that day's archived report
GET /api/page?sitemap=1               -> sitemap.xml
(vercel.json rewrites the clean URLs /resorts, /resorts/<slug>[/<date>] and /sitemap.xml here.)
"""
import logging

from bcbot.web import Handler
from bcbot import pages, resorts
from bcbot.store import get_store, resort_store

LATEST = "public, max-age=300, s-maxage=600, stale-while-revalidate=3600"
ARCHIVE = "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800"


class handler(Handler):
    def send(self, code, body, content_type="text/html", cache=LATEST):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Cache-Control", cache if code == 200 else "public, s-maxage=300")
        self.end_headers()
        self.wfile.write(data)

    def not_found(self, msg="Not found"):
        body = pages.shell(page_title="Not found | 0xSnow", desc=msg, canonical=pages.site("resorts"), noindex=True,
                           body=f'<h1 class="page">{msg}</h1><p><a href="/resorts">See all resorts</a></p>')
        self.send(404, body)

    def do_GET(self):
        try:
            store = get_store()
            if self.query("sitemap"):
                return self.send(200, pages.sitemap(store), "application/xml", "public, s-maxage=3600")
            slug, day_str = self.query("resort"), self.query("date")
            if not slug:
                return self.send(200, pages.hub_page(), cache="public, max-age=3600, s-maxage=86400")
            if slug not in resorts.enabled():
                return self.not_found("We don't cover that resort yet")
            rs = resort_store(slug, store)
            dates = pages.post_dates(store, slug)
            if day_str:
                if not pages.valid_date(day_str):
                    return self.not_found()
                day = rs.get_json(f"data/days/{day_str}.json")
                if not day or not day.get("date"):
                    return self.not_found("No report for that day")
                return self.send(200, pages.resort_page(slug, day, dates, dated=True), cache=ARCHIVE)
            day = rs.get_json("data/latest.json")
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
