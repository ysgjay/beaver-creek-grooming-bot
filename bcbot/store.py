"""Where the archive lives.

Production uses Vercel Blob (public CDN URLs, served same-origin to the app through a
rewrite in vercel.json). Tests and local runs use a folder. Both expose the same API.

Layout (same paths in both):
  data/latest.json              today's full record (what the Today page loads)
  data/days/<date>.json         each day's full record
  data/months/<yyyy-mm>.json    per-day summaries for the calendar, week/month stats and feed
  data/forecasts/<date>.json    raw per-model forecast issued that day (for verification)
  data/verification.json        model scores
  data/state.json               bot bookkeeping (last map hash, last send)
  maps/<date>.jpg, cams/<date>.jpg
"""
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode

from . import config
from .util import http

JSON_MAX_AGE = 60       # seconds; Blob's minimum. JSON changes a few times a day.
IMAGE_MAX_AGE = 31536000  # images for a date never change


class LocalStore:
    def __init__(self, root):
        self.root = Path(root)

    def get_json(self, path, default=None):
        try:
            return json.loads((self.root / path).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    def put_json(self, path, obj):
        self.put_bytes(path, (json.dumps(obj, indent=1) + "\n").encode(), "application/json")

    def put_bytes(self, path, data, content_type, max_age=None):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def exists(self, path):
        return (self.root / path).exists()


class BlobStore:
    API = "https://vercel.com/api/blob/"
    API_VERSION = "11"

    def __init__(self, token, public_base):
        self.token = token
        self.base = public_base.rstrip("/")

    def _url(self, path):
        return f"{self.base}/{path}"

    def get_json(self, path, default=None):
        # Cache-buster: the pipeline must see its own writes from 30 minutes ago.
        r = http().get(self._url(path), params={"t": int(time.time())}, timeout=20)
        if r.status_code == 404:
            return default
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return default

    def exists(self, path):
        return http().head(self._url(path), timeout=20).status_code == 200

    def put_json(self, path, obj):
        self.put_bytes(path, json.dumps(obj, separators=(",", ":")).encode(), "application/json", JSON_MAX_AGE)

    def put_bytes(self, path, data, content_type, max_age=None):
        max_age = max_age or (IMAGE_MAX_AGE if content_type.startswith("image/") else JSON_MAX_AGE)
        r = http().put(
            self.API + "?" + urlencode({"pathname": path}),
            data=data,
            headers={
                "authorization": f"Bearer {self.token}",
                "x-api-version": self.API_VERSION,
                "x-add-random-suffix": "0",
                "x-allow-overwrite": "1",
                "x-content-type": content_type,
                "x-cache-control-max-age": str(max_age),
            },
            timeout=60,
        )
        if not r.ok:
            raise RuntimeError(f"Blob put {path} failed: {r.status_code} {r.text[:200]}")
        return r.json().get("url")


def get_store():
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    base = os.environ.get("BLOB_PUBLIC_BASE")
    if token and base:
        return BlobStore(token, base)
    return LocalStore(config.ROOT / "public")
