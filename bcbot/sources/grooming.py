"""Beaver Creek grooming map (Lumiplan PDF) -> JPEG + content hash + any text on the page."""
import hashlib
import io
import logging
import re

import pymupdf
from PIL import Image

from .. import config
from ..util import get

log = logging.getLogger(__name__)


def render(pdf_bytes, max_width=2000):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    text = page.get_text()
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    doc.close()
    if img.width > max_width:
        img = img.resize((max_width, round(img.height * max_width / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    return buf.getvalue(), text


_SECTIONS = {
    "GROOMERS OF THE DAY": "groomers_of_the_day",
    "LAST NIGHT'S GROOMING": "overnight",
    "MORNING GROOMING": "morning",
}
_DATE = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}$")


def parse_runs(lines):
    """Pull the run lists out of the PDF's text layer.

    The Lumiplan sheet lists each section as alternating number / run-name lines,
    e.g. "LAST NIGHT'S GROOMING", "1", "Little Brave Lower", "2", "Flint". Map labels
    follow the lists and break the number/name pattern, which ends the section.
    """
    out = {v: [] for v in _SECTIONS.values()}
    out["map_date"] = next((ln for ln in lines if _DATE.match(ln)), None)
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


def fetch():
    r = get(config.GROOMING_PDF_URL, timeout=60)
    r.raise_for_status()
    pdf = r.content
    jpeg, text = render(pdf)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return {
        # Hash the PDF, not the render, so re-rendering never fakes a "new" map.
        "hash": hashlib.sha256(pdf).hexdigest()[:16],
        "jpeg": jpeg,
        "text_lines": lines,
        "runs": parse_runs(lines),
        "last_modified": r.headers.get("Last-Modified"),
    }
