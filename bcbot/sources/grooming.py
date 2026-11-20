"""Lumiplan grooming map PDF -> one JPEG per page + content hash + the run names on the pages.

Some sheets have more than one page (Vail posts two), so every page is rendered and shown.

Two layouts are in use:
  Beaver Creek: section headings ("LAST NIGHT'S GROOMING"...) with number and name on
    alternating lines.
  Vail: area headings ("MID-VAIL") with number and name on one line, separated by
    non-breaking spaces; runs go in `groomed`, by area in `areas`.
"""
import hashlib
import io
import logging
import re

import pymupdf
from PIL import Image

from .. import config
from ..util import get

log = logging.getLogger(__name__)


MAX_PAGES = 6  # a safety cap: Lumiplan sheets are one or two pages


def _jpeg(page, max_width):
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    pix = None
    if img.width > max_width:
        img = img.resize((max_width, round(img.height * max_width / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    return buf.getvalue()


def render(pdf_bytes, max_width=2000):
    """Every page as a JPEG (in order) and the text of all pages. Pages render one at a time
    so only one bitmap is in memory at once."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages = [doc[i] for i in range(min(doc.page_count, MAX_PAGES))]
        text = "\n".join(p.get_text() for p in pages)
        jpegs = [_jpeg(p, max_width) for p in pages]
    finally:
        doc.close()
        pymupdf.TOOLS.store_shrink(100)  # empty MuPDF's cache: it otherwise grows across renders
    return jpegs, text


_SECTIONS = {
    "GROOMERS OF THE DAY": "groomers_of_the_day",
    "LAST NIGHT'S GROOMING": "overnight",
    "MORNING GROOMING": "morning",
}
_DATE = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}"
                   r"(?: \d{1,2}:\d{2} ?[AP]M)?$")


_NUM_NAME = re.compile(r"^(\d{1,3})[\s\u00a0]+(\S.*)$")


def _split_pairs(ln):
    """Park City's sheet can put two runs on one line: "1 Snow Dancer 2 Mellow Moose".
    A number only starts a new run when it is the next pin number, so names with digits stay whole."""
    tokens, runs, num = ln.split(), [], None
    for t in tokens:
        if t.isdigit() and (num is None or int(t) == num + 1) and (not runs or runs[-1][1]):
            num = int(t)
            runs.append([num, []])
        elif runs:
            runs[-1][1].append(t)
    return [" ".join(words) for _n, words in runs if words]


def _parse_area_layout(lines):
    """Vail-style sheet: 'MID-VAIL', '1\u00a0\u00a0 Ramshorn - Lower', ... (lone numbers are map pins)."""
    areas, area = {}, None
    for ln in lines:
        ln = ln.replace("\u00a0", " ").strip()
        m = _NUM_NAME.match(ln)
        if m:
            areas.setdefault(area or "Groomed", []).extend(_split_pairs(ln))
        elif _DATE.match(ln) or ln.isdigit():
            continue
        elif ln.isupper() and len(ln) <= 40:
            area = ln.title()
    return {"groomed": [r for runs in areas.values() for r in runs], "areas": areas}


def parse_runs(lines):
    """Pull the run lists out of the PDF's text layer.

    The Lumiplan sheet lists each section as alternating number / run-name lines,
    e.g. "LAST NIGHT'S GROOMING", "1", "Little Brave Lower", "2", "Flint". Map labels
    follow the lists and break the number/name pattern, which ends the section.
    """
    out = {v: [] for v in _SECTIONS.values()}
    out["map_date"] = next((ln for ln in lines if _DATE.match(ln)), None)
    if not any(ln.upper().replace("\u2019", "'") in _SECTIONS for ln in lines):
        return out | _parse_area_layout(lines)
    section, expect_name = None, False
    for ln in lines:
        key = _SECTIONS.get(ln.upper().replace("\u2019", "'"))
        if key:
            section, expect_name = key, False
            continue
        if section is None:
            continue
        if expect_name:
            out[section].append(ln)
            expect_name = False
        elif ln.isdigit():
            expect_name = True
        elif section == "groomers_of_the_day" and not out[section] and ln.lower().startswith(("hand-picked", "no trails")):
            continue
        else:
            section = None  # pattern broken: we're into the map labels
    return out


def page_text(pdf_bytes):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return "\n".join(doc[i].get_text() for i in range(min(doc.page_count, MAX_PAGES)))
    finally:
        doc.close()


def fetch(known_hash=None):
    """The map PDF's hash, run names and (only when the PDF changed) its page JPEGs. The cheap check runs
    every few minutes, and rendering an unchanged map each time used up the Render worker's memory."""
    r = get(config.GROOMING_PDF_URL, timeout=60)
    r.raise_for_status()
    pdf = r.content
    digest = hashlib.sha256(pdf).hexdigest()[:16]
    jpegs, text = ([], page_text(pdf)) if known_hash and digest == known_hash else render(pdf)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return {
        # Hash the PDF, not the render, so re-rendering never fakes a "new" map.
        "hash": digest,
        "jpeg": jpegs[0] if jpegs else None,  # page 1
        "extra_jpegs": jpegs[1:],  # pages 2+
        "text_lines": lines,
        "runs": parse_runs(lines),
        "last_modified": r.headers.get("Last-Modified"),
    }
