"""Beaver Creek grooming map (Lumiplan PDF) -> JPEG + content hash + any text on the page."""
import hashlib
import io
import logging

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
        "last_modified": r.headers.get("Last-Modified"),
    }
