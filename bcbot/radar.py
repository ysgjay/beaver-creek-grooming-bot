"""A zoomed-out radar snapshot for the morning email (Colorado and Utah, Monochrome frost).

Email apps can't run the app's live radar map, so this stitches a still image server-side:
OpenStreetMap tiles recolored to the frost palette, the latest NEXRAD composite from Iowa
State Mesonet (the same tiles the app uses) recolored to the blue snow ramp, and a dot per
resort. Saved to the Blob store at radar/email/<date>-<HHMM>.png (served as /radar/...).
Any failure returns None and the email simply goes without it.
"""
import io
import logging
import math

from PIL import Image, ImageDraw, ImageFilter

from . import config, resorts
from .util import http

log = logging.getLogger(__name__)

RADAR_SRC = "https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q"   # max zoom 6
BASE_SRC = "https://tile.openstreetmap.org"
BBOX = (-114.4, 36.6, -101.8, 42.3)      # west, south, east, north: Utah + Colorado
BASE_Z, RADAR_Z = 7, 6
OUT_W = 1200

LAND, LINE = (238, 244, 249), (122, 144, 164)            # frost land, control-border ink for roads/borders
RAMP = [(197, 223, 242), (136, 178, 213), (55, 111, 155), (12, 42, 74)]   # light to heavy (blue only)
INK = (12, 42, 74)


def _px(lon, lat, z):
    n = 256 * 2 ** z
    s = math.sin(math.radians(lat))
    return (lon + 180) / 360 * n, (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n


def _stitch(src, z, fetch):
    """Mosaic of the tiles covering BBOX at zoom z, cropped to it."""
    x0, y0 = _px(BBOX[0], BBOX[3], z)
    x1, y1 = _px(BBOX[2], BBOX[1], z)
    tx0, ty0, tx1, ty1 = int(x0 // 256), int(y0 // 256), int(x1 // 256), int(y1 // 256)
    img = Image.new("RGBA", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256), (0, 0, 0, 0))
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            data = fetch(f"{src}/{z}/{tx}/{ty}.png")
            if data:
                img.paste(Image.open(io.BytesIO(data)).convert("RGBA"), ((tx - tx0) * 256, (ty - ty0) * 256))
    return img.crop((round(x0 - tx0 * 256), round(y0 - ty0 * 256), round(x1 - tx0 * 256), round(y1 - ty0 * 256)))


def _frost(base):
    """OSM colors to the frost monochrome: land, parks and forests to frost; roads, borders
    and labels (the darker strokes) to slate."""
    g = base.convert("L")

    def lut(i):
        return [round(LINE[i] + (LAND[i] - LINE[i]) * min(1, max(0, (v - 120) / 105)) ** 0.8) for v in range(256)]
    return Image.merge("RGB", (g.point(lut(0)), g.point(lut(1)), g.point(lut(2)))).convert("RGBA")


def echo_strength(r, g, b):
    """0..1 from NEXRAD's rainbow palette (same mapping as the app's recolorRadar)."""
    mx, mn = max(r, g, b), min(r, g, b)
    d, val = mx - mn, mx / 255
    if mx == 0 or d / mx < 0.2:
        return 0.05
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    h = (h * 60 + 360) % 360

    def dim(span):
        return min(1, max(0, (1 - val) / span))
    if 165 <= h < 255:
        return 0.05 + 0.30 * (h - 165) / 90
    if 75 <= h < 165:
        return 0.35 + 0.22 * dim(0.45)
    if 45 <= h < 75:
        return 0.57 + 0.13 * dim(0.3)
    if h < 45 or h >= 330:
        return 0.70 + 0.20 * dim(0.4)
    return 0.92


def _recolor(radar):
    px = radar.load()
    w, h = radar.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if not a:
                continue
            e = echo_strength(r, g, b)
            mx = max(r, g, b)
            if not mx or (mx - min(r, g, b)) / mx < 0.2:
                px[x, y] = (0, 0, 0, 0)          # gray clear-air returns and clutter: speckle at email size
                continue
            t = e * (len(RAMP) - 1)
            k = min(len(RAMP) - 2, int(t))
            f = t - k
            c = [round(RAMP[k][i] + (RAMP[k + 1][i] - RAMP[k][i]) * f) for i in range(3)]
            px[x, y] = (*c, round(90 + 150 * min(1, e / 0.6)))   # light echoes stay sheer
    return radar.filter(ImageFilter.GaussianBlur(1.2))      # soft, cloud-like


def render(fetch=None):
    """PNG bytes of the snapshot."""
    def default_fetch(url):
        r = http().get(url, timeout=20)
        return r.content if r.ok else None
    fetch = fetch or default_fetch
    base = _frost(_stitch(BASE_SRC, BASE_Z, fetch))
    radar = _recolor(_stitch(RADAR_SRC, RADAR_Z, fetch)).resize(base.size, Image.BILINEAR)
    img = Image.alpha_composite(base, radar)
    scale = OUT_W / img.width
    img = img.resize((OUT_W, round(img.height * scale)), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    x0, y0 = _px(BBOX[0], BBOX[3], BASE_Z)
    for slug in resorts.enabled():
        r = resorts.get(slug)
        x, y = _px(r["lon"], r["lat"], BASE_Z)
        cx, cy = (x - x0) * scale, (y - y0) * scale
        d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=(255, 255, 255))
        d.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=INK)
    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


def snapshot(store, now):
    """URL of today's email radar image, rendering it once per 10 minutes. None on failure."""
    stamp = now.strftime("%Y-%m-%d-%H") + f"{now.minute // 10 * 10:02d}"
    path = f"radar/email/{stamp}.png"
    url = f"{config.DASHBOARD_URL.rstrip('/')}/{path}"
    try:
        if store.get_bytes(path):
            return url
        store.put_bytes(path, render(), "image/png")
        return url
    except Exception:
        log.exception("radar snapshot failed")
        return None
