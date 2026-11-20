"""Reader for resorts whose snow report is server-rendered HTML with no feed (Killington and independents).

It strips the page to text and looks for the usual labels next to a number: "24 Hour 0"", "48 Hr 2 in",
"7 Day 5"", "Base 30"", "Season 5"", "Overnight 1"", plus "Updated November 15, 2026 10:44 AM".
Pages that render the numbers with JavaScript give nothing here; those resorts stay on forecast + SNOTEL.
Use it with a resort's "report_feed": {"kind": "text", "url": <page>, "start": <heading>} (sources/feeds.py).
"""
import html as _html
import re
from datetime import date


_NUM = r"(\d{1,3}(?:\.\d)?)\s*(\"|”|″|''|in\b|inches\b|cm\b)"
_LABELS = (  # first match wins, so the specific labels come before the broad ones
    ("overnight_in", r"overnight|new snow|since (?:lifts? close|close|last report)|12[\s-]*(?:hours?|hrs?|h)\b"),
    ("last_24h_in", r"24[\s-]*(?:hours?|hrs?|h)\b|past 24|last 24"),
    ("last_48h_in", r"48[\s-]*(?:hours?|hrs?|h)\b|past 48|last 48"),
    ("last_7d_in", r"7[\s-]*days?\b|past 7 days|last 7 days|this week"),
    ("base_in", r"base(?: depth)?|snow depth|mid[\s-]*mountain depth|summit depth"),
    ("season_in", r"season(?:al)?(?: total| to date| snowfall)?|year to date|ytd|cumulative"),
)
_MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
_UPDATED = re.compile(r"(?:updated|as of|reported|last update)[:\s]*(?:on\s+)?(?:[A-Za-z]+day,?\s+)?"
                      r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d\d)(?:\s*(?:at|@|,)?\s*(\d{1,2}:\d{2}\s*[AP]\.?M\.?))?",
                      re.I)
_UPDATED_NOYEAR = re.compile(r"(?:updated|as of|reported)[:\s]*(?:on\s+)?([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*"
                             r"(?:at|@)?\s*(\d{1,2}:\d{2}\s*[AP]\.?M\.?)?", re.I)
_UPDATED_US = re.compile(r"(?:updated|as of|reported)[:\s]*(\d{1,2})/(\d{1,2})/((?:20)?\d\d)\b(?:\s*(?:at|@)?\s*"
                         r"(\d{1,2}:\d{2}\s*[AP]\.?M\.?))?", re.I)


def page_text(html):
    s = re.sub(r"(?is)<(script|style|noscript|svg|head)\b.*?</\1>", " ", html or "")
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


def _value(text, label, order="after"):
    if not label:
        return None
    """order "after": label then number ("24 Hour 0\""); "before": number then label ("0\" 24 hours")."""
    after = r"(?:%s)[^\d\n]{0,16}?%s" % (label, _NUM)  # allows a short word between ("Overnight Fresh 4\"")
    before = r"%s\s*(?:of\s+)?(?:%s)\b" % (_NUM, label)
    m = re.search(after if order == "after" else before, text, re.I)
    if not m:
        return None
    v = float(m.group(1))
    return round(v / 2.54, 1) if m.group(2).lower().startswith("cm") else v


def _stamp(text, today=None):
    m = _UPDATED.search(text)
    if m and m.group(1)[:3].lower() in _MONTHS:
        d = date(int(m.group(3)), _MONTHS.index(m.group(1)[:3].lower()) + 1, int(m.group(2)))
        return d, m.group(4)
    m = _UPDATED_US.search(text)
    if m:
        y = int(m.group(3))
        return date(y + 2000 if y < 100 else y, int(m.group(1)), int(m.group(2))), m.group(4)
    m = _UPDATED_NOYEAR.search(text)  # "Last Updated: Nov 15, 5:00 AM MT": this year, or last year in early Jan
    if m and m.group(1)[:3].lower() in _MONTHS:
        today = today or date.today()
        d = date(today.year, _MONTHS.index(m.group(1)[:3].lower()) + 1, int(m.group(2)))
        if d > today:
            d = d.replace(year=today.year - 1)
        return d, m.group(3)
    return None, None


def _hm(t):
    """ "8:44AM" / "11:39" / "8:17am" -> "8:44 AM" (24-hour times are turned into AM/PM)."""
    t = (t or "").strip()
    m = re.match(r"(\d{1,2})[:：](\d{2})\s*([AaPp])?\.?[Mm]?", t)
    if not m:
        return None
    hh, mm, ap = int(m.group(1)), m.group(2), m.group(3)
    if ap:
        return f"{(hh % 12) or 12}:{mm} {ap.upper()}M"
    return f"{(hh % 12) or 12}:{mm} {'AM' if hh < 12 else 'PM'}"


def _stamp_re(text, pattern, today=None):
    """A resort-specific date pattern with named groups: y (optional), m or mon (month number or name), d,
    t (optional time, 24-hour or AM/PM). Used for pages that write dates as 23/10/2026, 2026.11.03 or 11/20."""
    m = re.search(pattern, text, re.I)
    if not m:
        return None, None
    g = m.groupdict()
    try:
        month = int(g["m"]) if g.get("m") else _MONTHS.index(g["mon"][:3].lower()) + 1
        today = today or date.today()
        if g.get("y"):
            d = date(int(g["y"]), month, int(g["d"]))
        else:  # no year on the page: this year, or last year in early January
            d = date(today.year, month, int(g["d"]))
            if d > today:
                d = d.replace(year=today.year - 1)
    except (KeyError, ValueError, TypeError):
        return None, None
    return d, _hm(g.get("t"))


def parse(html, start=None, order="after", today=None, labels=None, stamp=None):
    """Snow numbers (inches) and the report's date, in the same shape as resort.parse.
    `start` limits the search to the text after a heading such as "Snow Report". `labels` replaces the
    label pattern for some keys (None turns a key off), for pages worded differently ("Snow Accumulation",
    "積雪量"). `stamp` is a date pattern for pages without an "Updated <Month> <day>, <year>" line."""
    text = full = page_text(html)
    if start:
        i = text.lower().find(start.lower())
        if i >= 0:
            text = text[i:i + 3000]
    out = {}
    for key, label in _LABELS:
        if labels and key in labels:
            label = labels[key]
        v = _value(text, label, order)
        if v is not None:
            out[key] = v
    if not out:
        return {}
    if stamp:
        d, t = _stamp_re(text, stamp, today)
        if not d and text is not full:
            d, t = _stamp_re(full, stamp, today)
    else:
        d, t = _stamp(text, today)
        if not d and text is not full:
            d, t = _stamp(full, today)  # the "Updated" line can sit above the start heading
    if d:
        out["stamps"] = {"updated": d.isoformat()}
        if t:
            out["updated_time"] = t if stamp else re.sub(r"\s*([AP])\.?M\.?", r" \1M", t.upper()).strip().lstrip("0")
    return out
