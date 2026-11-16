import json
import time
from datetime import datetime

import requests

from . import config

_session = None


def http():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers["User-Agent"] = config.USER_AGENT
    return _session


def get(url, *, params=None, headers=None, timeout=30, retries=2):
    """GET with a timeout and a couple of retries on network/5xx errors."""
    last = None
    for attempt in range(retries + 1):
        try:
            r = http().get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code < 500:
                return r
            last = requests.HTTPError(f"{r.status_code} from {url}")
        except requests.RequestException as e:
            last = e
        if attempt < retries:  # no pointless wait after the last try
            time.sleep(2 * (attempt + 1))
    raise last


def now_local():
    return datetime.now(config.TZ)


def today_str():
    return now_local().date().isoformat()


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=False) + "\n")


def r1(x):
    return None if x is None else round(float(x), 1)
