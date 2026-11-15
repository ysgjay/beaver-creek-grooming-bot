"""Build the static dashboard: web/ (app shell) + data/ (archive) -> _site/."""
import shutil

from . import config
from .util import write_json


def build(out=None):
    out = out or config.SITE_DIR
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(config.WEB_DIR, out)
    shutil.copytree(config.DATA_DIR, out / "data",
                    ignore=shutil.ignore_patterns("state.json"))
    (out / ".nojekyll").write_text("")
    # Public, non-secret settings the page needs (subscribe links).
    write_json(out / "config.json", {
        "telegram": "https://t.me/" + config.TELEGRAM_CHAT_ID.lstrip("@") if config.TELEGRAM_CHAT_ID.startswith("@") else None,
        "ntfy_topic": config.NTFY_TOPIC or None,
        "ntfy_server": config.NTFY_SERVER,
        "signup_form": config.SIGNUP_FORM_URL or None,
        "cams": config.CAMS,
    })
    return out
