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

Beaver Creek, the first resort, keeps these paths. Every other resort gets the same
layout one folder down: data/<slug>/latest.json, maps/<slug>/<date>.jpg, cams/<slug>/...
(see ResortStore). The existing /data, /maps and /cams rewrites cover both.
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

    def list(self, prefix, limit=2000):
        base = self.root / prefix
        if not base.is_dir():
            return []
        return sorted(f"{prefix}{p.name}" for p in base.iterdir() if p.is_file())[:limit]

    def get_bytes(self, path):
        try:
            return (self.root / path).read_bytes()
        except FileNotFoundError:
            return None


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

    def get_bytes(self, path):
        r = http().get(self._url(path), timeout=30)
        return r.content if r.ok else None

    def list(self, prefix, limit=2000):
        """Pathnames under a prefix (Blob list API, paged)."""
        out, cursor = [], None
        while len(out) < limit:
            params = {"prefix": prefix, "limit": 1000, **({"cursor": cursor} if cursor else {})}
            r = http().get(self.API, params=params, timeout=20,
                           headers={"authorization": f"Bearer {self.token}", "x-api-version": self.API_VERSION})
            r.raise_for_status()
            body = r.json()
            out += [b["pathname"] for b in body.get("blobs", [])]
            cursor = body.get("cursor")
            if not body.get("hasMore") or not cursor:
                break
        return out

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


class ResortStore:
    """One resort's view of a store: data/x -> data/<slug>/x (identity for the default resort)."""
    TOP = ("data/", "maps/", "cams/")

    def __init__(self, inner, slug):
        from .resorts import DEFAULT
        self.inner, self.slug = inner, slug
        self.prefixed = slug != DEFAULT

    def path(self, path):
        if self.prefixed:
            for top in self.TOP:
                if path.startswith(top):
                    return f"{top}{self.slug}/{path[len(top):]}"
        return path

    def get_json(self, path, default=None):
        return self.inner.get_json(self.path(path), default)

    def put_json(self, path, obj):
        return self.inner.put_json(self.path(path), obj)

    def put_bytes(self, path, data, content_type, max_age=None):
        return self.inner.put_bytes(self.path(path), data, content_type, max_age)

    def exists(self, path):
        return self.inner.exists(self.path(path))

    def get_bytes(self, path):
        return self.inner.get_bytes(self.path(path))


def resort_store(slug, store=None):
    store = store or get_store()
    return store if isinstance(store, ResortStore) and store.slug == slug else ResortStore(
        store.inner if isinstance(store, ResortStore) else store, slug)


class ShadowStore:
    """Reads the live archive, writes only to a local folder. The Render worker runs in this
    mode first (WORKER_MODE=shadow), so the full pipeline can be checked off Vercel without
    touching what the app and emails read. Reads see the shadow's own writes first."""

    def __init__(self, live, root):
        self.live = live
        self.local = LocalStore(root)

    def get_json(self, path, default=None):
        hit = self.local.get_json(path)
        return hit if hit is not None else self.live.get_json(path, default)

    def get_bytes(self, path):
        hit = self.local.get_bytes(path)
        return hit if hit is not None else self.live.get_bytes(path)

    def exists(self, path):
        return self.local.exists(path) or self.live.exists(path)

    def list(self, prefix, limit=2000):
        try:
            live = self.live.list(prefix, limit)
        except Exception:  # Blob listing needs the token; a read-only shadow may not have it
            live = []
        return sorted(set(live) | set(self.local.list(prefix, limit)))[:limit]

    def put_json(self, path, obj):
        self.local.put_json(path, obj)

    def put_bytes(self, path, data, content_type, max_age=None):
        if content_type.startswith("image/"):
            return  # maps, cams and radar frames aren't kept in shadow: only the report data is compared
        self.local.put_bytes(path, data, content_type, max_age)


def get_store():
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    base = os.environ.get("BLOB_PUBLIC_BASE")
    if os.environ.get("STORE_MODE") == "shadow":
        live = BlobStore(token or "", base) if base else LocalStore(config.ROOT / "public")
        return ShadowStore(live, os.environ.get("SHADOW_DIR") or "/tmp/0xsnow-shadow")
    if token and base:
        return BlobStore(token, base)
    if os.environ.get("VERCEL_ENV") == "production" or os.environ.get("WORKER_MODE", "").strip().lower() == "live":
        # On a server, a local folder is thrown away on restart: refuse instead of silently
        # writing (and sending) from a store nobody reads.
        raise RuntimeError("BLOB_READ_WRITE_TOKEN and BLOB_PUBLIC_BASE are required in live mode")
    return LocalStore(config.ROOT / "public")
