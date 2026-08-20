"""
tree_detect.py — Auto-detect existing tree crowns from satellite imagery (V2.26).

Design principle P8 (repair starts from an honest inventory of what's already
there) and P9 (estimates shipped as estimates, failure reported as failure) —
see docs/DESIGN_PHILOSOPHY.md.

OSM knows buildings well but almost never individual trees on rural or
residential land, so the V1.51 "Import building & tree outlines" flow leaves a
treed acreage's shade map empty and the user marking dozens of crowns by hand.
This module closes that gap from a source that exists *everywhere the app
works*: the same Esri World Imagery basemap the map already displays. It
fetches the handful of imagery tiles covering the property, finds tree crowns
as dark-green blobs, and emits them in the exact item shape the OSM import
produces — so boundary clipping, dedupe against hand-marked/OSM trees, project
insertion and map rendering all reuse the proven ``osm_features`` tail.

The detector is deliberately classical (no ML, no heavy deps — pure stdlib,
mirroring the optional-dependency policy of ``footprint_extract``):

  1. **Vegetation gate** — excess-green index (ExG = 2g − r − b) keeps living
     canopy/lawn pixels and drops roofs, gravel, asphalt, bare soil and water.
  2. **Canopy vs lawn split** — tree crowns image darker than mowed grass
     (self-shading); Otsu's threshold on the brightness histogram of the
     vegetation pixels finds the split adaptively per property, with guards
     for the all-forest and all-lawn degenerate cases. The split runs on
     3×3-smoothed brightness so a single textured surface's own noise can't
     fool Otsu into "splitting" it (a wooded lot must not speckle apart).
  3. **Texture gate** — darkness alone over-detects on unevenly lit grass
     (a shaded or lush park lawn is dark too), so canopy pixels must also be
     locally *rough*: crowns have big pixel-to-pixel brightness swings
     (sunlit tufts + self-shadow) where mowed lawn — even dark lawn — is
     smooth. A one-pixel dilation keeps small calm pockets inside real
     crowns.
  4. **Crown separation** — connected canopy blobs get a chamfer distance
     transform and greedy peak-picking (disk packing), so a shelterbelt row
     becomes a line of individual trees instead of one 100 m monster.
  5. **Physics verification** (second field pass) — colour, darkness and
     texture are all fakeable by real grass; these aren't: a sunlit crown
     mixes lit tufts with self-shadow (internal contrast — cast shadow on
     grass has no direct light and fails it), a crown is darker than the
     sunlit ground around it (ring contrast), and every tree in one photo
     casts its shadow the same compass way (shadow-bearing consensus, with
     a hemisphere prior; stand interiors inherit their blob's edge
     verdict). Shadow lengths then give *measured* heights — calibrated
     absolutely when an imported building of known height casts a legible
     shadow in the same photo — and crown colour tags obvious conifers/
     broadleafs for honest winter shade.

Honesty contract (P9): crown *positions and sizes* are measured from the photo;
*heights* are rough allometric estimates from crown size and are labelled as
such; foliage type is left **unknown** (the shade model already treats unknown
as year-round shade — it never invents a deciduous winter break); a failed tile
fetch is reported as a failure, never as "found 0 trees" (the V2.13 lesson).
Detection also only sees what the photo saw: leaf-off deciduous trees in
early-spring/fall imagery may be missed, and results are editable/deletable
exactly like OSM imports.

Public API:
  * ``detect_trees(bbox, *, _fetch_tile=…, _decode=…) -> dict | None``
  * ``import_detected_trees(res, project_dict, *, boundary=…, …) -> dict``

The tile *decoder* is injectable because JPEG decoding needs a codec: the GUI
passes a QImage-based one (``tree_detect_flow._qimage_decode``); tests pass a
synthetic decoder. This keeps the module import-safe with no Qt and no Pillow.
"""

from __future__ import annotations

import math
import urllib.request
from typing import Callable, Optional

# Same tiles the Leaflet basemap displays (html/map/01-core.js); fetched here
# once per import for analysis, at yard scale (a couple dozen 256 px tiles).
_TILE_URL = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
             "World_Imagery/MapServer/tile/{z}/{y}/{x}")
# Legacy product identifier, retained intentionally (see CLAUDE.md).
_USER_AGENT = "PermaDesign/1.0 (https://github.com/yarrowyarrowyarrow/permadesign)"
_TIMEOUT = 15.0

_TILE_PX = 256
_MAX_ZOOM = 19          # Esri's near-universal rural ceiling (~0.2 m/px)
_MIN_ZOOM = 16          # below ~1.2 m/px crowns stop being resolvable
_MAX_TILES = 28         # ≈1.8 Mpx mosaic ceiling — keeps pure-Python fast

# Detection tuning. These are heuristics, documented as such; results are
# always editable on the map, and the status message says so.
_EXG_MIN = 18           # vegetation gate: 2g − r − b at least this
_G_MIN = 30             # and not near-black
_OTSU_MIN_SEPARATION = 18   # dark/bright class means closer than this = no split
_ALL_FOREST_MEAN = 95   # uniformly dark vegetation ⇒ treat all of it as canopy
# Crown texture: min 3×3 brightness range for a canopy pixel. Mowed lawn at
# this scale (incl. JPEG noise) ranges ~2–8; crowns 15–40. Smooth dark lawn
# was the V2.26 over-detection failure — the park that hit the safety cap.
_MIN_CANOPY_TEXTURE = 10
# Physics gates (V2.26 second field run: mottled park grass beat both the
# darkness split AND the texture gate — but grass can't fake these two):
_RING_CONTRAST_MIN = 10     # a crown is darker than the sunlit ground *around*
#                             it; a "tree" inside a big grassy expanse isn't.
_CROWN_CONTRAST_MIN = 22    # p90 − p10 brightness inside a crown: sunlit
#                             tufts + self-shadow. Cast shadow ON grass gets
#                             no direct light at all, so however textured the
#                             grass is, it stays uniformly dark (the park
#                             mega-blob failure: tree shadows on lawn are
#                             dark AND green AND textured — this is the gate
#                             they cannot pass).
_SHADOW_LUM_FACTOR = 0.6    # shadow pixels: darker than 0.6 × scene median…
_SHADOW_LUM_CAP = 110       # …and dark in absolute terms.
_MIN_SHADOW_FRAC = 0.25     # aligned-shadow coverage that verifies a crown
_SHADOW_VOTE_FRAC = 0.30    # a candidate votes only with a clear best bearing
_SHADOW_BINS = 16           # compass resolution of the consensus vote
_SHADOW_SEARCH_MAX_M = 30.0
_SHADOW_SHORT_SPAN_PX = 6.0  # high-sun retry: near-noon captures leave only a
#                              2–6 px shadow fringe — sample a tight band just
#                              past the crown edge before giving up on shadows.
_CROWN_CONTRAST_STRICT = 30  # with NO legible shadows the physics evidence is
#                              thinner, so the internal-contrast bar rises —
#                              degrade toward caution, never permissiveness.
_MIN_CROWN_RADIUS_M = 0.9   # smaller blobs are shrubs/noise — skip
_MAX_CROWN_RADIUS_M = 12.0
_MAX_TREES = 400        # flood guard for a bad threshold day
# Open-grown height ≈ 2.6 × crown radius: between conifer (~5×) and broadleaf
# (~2×) allometry — a stated mid-range estimate, clamped to yard-tree reality.
_HEIGHT_PER_RADIUS = 2.6
_HEIGHT_MIN_M, _HEIGHT_MAX_M = 3.0, 18.0
# Foliage-aware allometry (fallback when the photo yields no usable shadows):
# open-grown conifers run tall-narrow, broadleaf wide-round. Stated rough
# estimates (P9) — the shadow-measured path replaces them when available.
_HEIGHT_PER_RADIUS_BY_FOLIAGE = {"evergreen": 4.0, "deciduous": 2.2,
                                 None: _HEIGHT_PER_RADIUS}
_HEIGHT_MAX_MEASURED_M = 25.0   # shadow-measured heights may exceed the
#                                 allometric clamp — a real 22 m spruce is real
# Confident-only foliage tells from crown colour (leaf-on imagery): conifers
# image dark, muted blue-green; broadleaf bright saturated green. Anything in
# between stays None = unknown = year-round shade (the app's honest default).
_EVERGREEN_LUM_MAX = 75
_EVERGREEN_GB_MAX = 35          # g − b stays muted on conifers
_DECIDUOUS_LUM_MIN = 80
_DECIDUOUS_EXG_MIN = 90


# ── Web-Mercator tile / pixel math ───────────────────────────────────────────

def _latlng_to_global_px(lat: float, lng: float, zoom: int) -> tuple:
    """(x, y) in global pixel coordinates at ``zoom`` (256 px tiles)."""
    n = _TILE_PX * (1 << zoom)
    x = (lng + 180.0) / 360.0 * n
    # Clamp sin(lat) away from ±1 so the log never blows up at the poles.
    s = max(-0.9999, min(0.9999, math.sin(math.radians(lat))))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def _global_px_to_latlng(x: float, y: float, zoom: int) -> tuple:
    """Inverse of :func:`_latlng_to_global_px` → (lat, lng)."""
    n = _TILE_PX * (1 << zoom)
    lng = x / n * 360.0 - 180.0
    t = math.pi * (1 - 2 * y / n)
    lat = math.degrees(math.atan(math.sinh(t)))
    return lat, lng


def _m_per_px(lat: float, zoom: int) -> float:
    """Ground metres per pixel at ``lat`` for 256 px Web-Mercator tiles."""
    return 156543.03392 * math.cos(math.radians(lat)) / (1 << zoom)


def _tile_range(bbox: dict, zoom: int) -> tuple:
    """Inclusive (tx0, ty0, tx1, ty1) tile range covering ``bbox``."""
    x0, y0 = _latlng_to_global_px(bbox["north"], bbox["west"], zoom)
    x1, y1 = _latlng_to_global_px(bbox["south"], bbox["east"], zoom)
    return (int(x0 // _TILE_PX), int(y0 // _TILE_PX),
            int(x1 // _TILE_PX), int(y1 // _TILE_PX))


def _pick_zoom(bbox: dict, max_tiles: int = _MAX_TILES) -> int:
    """Highest zoom (≤ ``_MAX_ZOOM``) whose tile count fits the mosaic budget.
    Never below ``_MIN_ZOOM`` — a huge boundary just gets coarser pixels."""
    for zoom in range(_MAX_ZOOM, _MIN_ZOOM - 1, -1):
        tx0, ty0, tx1, ty1 = _tile_range(bbox, zoom)
        if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) <= max_tiles:
            return zoom
    return _MIN_ZOOM


def _fetch_tile_bytes(zoom: int, x: int, y: int) -> Optional[bytes]:
    """GET one imagery tile; ``None`` on any failure (offline-graceful)."""
    url = _TILE_URL.format(z=zoom, x=x, y=y)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.read()
    except Exception:  # noqa: BLE001 — caller counts failures honestly
        return None


# ── Mask building ────────────────────────────────────────────────────────────

def _vegetation_and_brightness(rgb: bytes, w: int, h: int) -> tuple:
    """One pass over the mosaic: a vegetation mask (bytearray of 0/1) and the
    per-pixel brightness of EVERY pixel (the texture gate reads neighbours,
    which may be background). The split histogram comes later, from the
    smoothed values (:func:`_smooth_brightness`)."""
    veg = bytearray(w * h)
    bright = bytearray(w * h)
    hist_all = [0] * 256
    idx = 0
    for i in range(w * h):
        r = rgb[idx]
        g = rgb[idx + 1]
        b = rgb[idx + 2]
        idx += 3
        lum = (r + 2 * g + b) >> 2
        bright[i] = lum
        hist_all[lum] += 1
        if g >= _G_MIN and (2 * g - r - b) >= _EXG_MIN and g > b:
            veg[i] = 1
    return veg, bright, hist_all


def _smooth_brightness(veg: bytearray, bright: bytearray,
                       w: int, h: int) -> tuple:
    """3×3 box-smoothed brightness for the vegetation pixels, plus its
    histogram. The canopy/lawn *split* runs on these values: within one
    surface, smoothing collapses crown texture (±20 pixel-to-pixel) to a
    tight cluster, so Otsu can't mistake a single textured canopy's noise
    for two brightness classes — while genuine lawn-vs-crown contrast
    survives smoothing untouched. The texture gate keeps reading the RAW
    ``bright`` values; only the split uses these."""
    smooth = bytearray(w * h)
    hist = [0] * 256
    for i in range(w * h):
        if not veg[i]:
            continue
        x, y = i % w, i // w
        acc = n = 0
        for yy in (y - 1, y, y + 1):
            if yy < 0 or yy >= h:
                continue
            base = yy * w
            for xx in (x - 1, x, x + 1):
                if 0 <= xx < w:
                    acc += bright[base + xx]
                    n += 1
        v = acc // n
        smooth[i] = v
        hist[v] += 1
    return smooth, hist


def _otsu_two_thresholds(hist: list) -> Optional[tuple]:
    """Two-threshold (3-class) Otsu via prefix sums. Returns ``(t1, t2)``
    maximizing between-class variance, or ``None`` on a thin histogram.
    Needed because a real yard often has THREE brightness modes — dry grass,
    green grass, tree canopy — and a 2-class split happily puts the line
    between the grasses, labelling every green lawn pixel 'canopy' (the
    second park failure)."""
    total = sum(hist)
    if total < 192:
        return None
    cw = [0] * 257
    cm = [0.0] * 257
    for i in range(256):
        cw[i + 1] = cw[i] + hist[i]
        cm[i + 1] = cm[i] + i * hist[i]
    m_all = cm[256] / total
    best, best_var = None, -1.0
    for t1 in range(255):
        w0 = cw[t1 + 1]
        if w0 == 0:
            continue
        m0 = cm[t1 + 1] / w0
        for t2 in range(t1 + 1, 255):
            w1 = cw[t2 + 1] - cw[t1 + 1]
            w2 = total - cw[t2 + 1]
            if w1 == 0:
                continue
            if w2 == 0:
                break
            m1 = (cm[t2 + 1] - cm[t1 + 1]) / w1
            m2 = (cm[256] - cm[t2 + 1]) / w2
            var = (w0 * (m0 - m_all) ** 2 + w1 * (m1 - m_all) ** 2
                   + w2 * (m2 - m_all) ** 2)
            if var > best_var:
                best_var, best = var, (t1, t2)
    return best


def _otsu_threshold(hist: list) -> Optional[int]:
    """Otsu's between-class-variance threshold over a 256-bin histogram.
    ``None`` when the histogram is (near-)empty."""
    total = sum(hist)
    if total < 64:
        return None
    sum_all = sum(i * hist[i] for i in range(256))
    sum_b = 0.0
    w_b = 0
    best_t, best_var = None, -1.0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > best_var:
            best_var, best_t = var, t
    return best_t


def _canopy_mask(veg: bytearray, bright: bytearray, hist: list,
                 w: int, h: int) -> Optional[bytearray]:
    """Split vegetation into canopy-vs-lawn by brightness. Returns the canopy
    mask, or ``None`` when there's no tree-like vegetation to work with.

    Degenerate-case guards: when Otsu can't find two *meaningfully* separated
    brightness classes, uniformly dark vegetation is treated as all-canopy
    (a wooded lot with no lawn) and uniformly bright vegetation as all-lawn
    (nothing to detect) — never a coin-flip split of noise."""
    total = sum(hist)
    if total == 0:
        return None
    # Tri-modal first (dry grass / green grass / canopy): when the darkest
    # of three classes separates cleanly from BOTH grasses, it is the canopy.
    tt = _otsu_two_thresholds(hist)
    if tt is not None:
        t1, t2 = tt
        n0 = sum(hist[:t1 + 1])
        n1 = sum(hist[t1 + 1:t2 + 1])
        n2 = total - n0 - n1
        if n0 >= 64 and n1 and n2:
            m0 = sum(i * hist[i] for i in range(t1 + 1)) / n0
            m1 = sum(i * hist[i] for i in range(t1 + 1, t2 + 1)) / n1
            m2 = sum(i * hist[i] for i in range(t2 + 1, 256)) / n2
            if (m1 - m0) >= _OTSU_MIN_SEPARATION and (m2 - m1) >= 12:
                mask = bytearray(w * h)
                for i in range(w * h):
                    if veg[i] and bright[i] <= t1:
                        mask[i] = 1
                return mask
    t = _otsu_threshold(hist)
    if t is not None:
        n_dark = sum(hist[:t + 1])
        n_lite = total - n_dark
        if n_dark and n_lite:
            m_dark = sum(i * hist[i] for i in range(t + 1)) / n_dark
            m_lite = sum(i * hist[i] for i in range(t + 1, 256)) / n_lite
            if (m_lite - m_dark) >= _OTSU_MIN_SEPARATION:
                mask = bytearray(w * h)
                for i in range(w * h):
                    if veg[i] and bright[i] <= t:
                        mask[i] = 1
                return mask
    mean = sum(i * hist[i] for i in range(256)) / total
    if mean < _ALL_FOREST_MEAN:
        return bytearray(veg)       # uniformly dark ⇒ wooded, keep it all
    return None                     # uniformly bright ⇒ lawn, nothing to find


def _texture_mask(mask: bytearray, bright: bytearray, w: int, h: int,
                  min_range: int = _MIN_CANOPY_TEXTURE) -> bytearray:
    """Drop canopy-mask pixels that sit in *smooth* imagery. Crowns at yard
    scale are rough (3×3 brightness range ≥ ``min_range``); mowed lawn is
    smooth even where it images dark — the V2.26 park failure that blanketed
    a lawn in detections. A one-pixel dilation of the rough set (within the
    mask) keeps small calm pockets inside real crowns; the thin smooth-patch
    *rims* that survive dilation are too narrow to pack a crown and die in
    the min-size / min-radius filters downstream."""
    rough = bytearray(w * h)
    for i in range(w * h):
        if not mask[i]:
            continue
        x, y = i % w, i // w
        lo = hi = bright[i]
        for yy in (y - 1, y, y + 1):
            if yy < 0 or yy >= h:
                continue
            base = yy * w
            for xx in (x - 1, x, x + 1):
                if xx < 0 or xx >= w:
                    continue
                v = bright[base + xx]
                if v < lo:
                    lo = v
                elif v > hi:
                    hi = v
        if hi - lo >= min_range:
            rough[i] = 1
    out = bytearray(w * h)
    for i in range(w * h):
        if not mask[i]:
            continue
        if rough[i]:
            out[i] = 1
            continue
        x, y = i % w, i // w
        for yy in (y - 1, y, y + 1):        # 1-px dilation of the rough set
            if yy < 0 or yy >= h:
                continue
            base = yy * w
            if any(rough[base + xx] for xx in (x - 1, x, x + 1)
                   if 0 <= xx < w):
                out[i] = 1
                break
    return out


# ── Shadow + contrast physics (V2.26 second pass) ───────────────────────────
# Grass can mimic canopy in colour, darkness and even texture (mottled park
# lawn), but it cannot fake two physical facts: a crown is darker than the
# sunlit ground AROUND it, and a real tree casts a shadow in the SAME compass
# direction as every other tree in the photo.

def _hist_median(hist: list) -> int:
    total = sum(hist)
    acc = 0
    for i in range(256):
        acc += hist[i]
        if acc * 2 >= total:
            return i
    return 255


def _shadow_mask_for(mask: bytearray, bright: bytearray, hist_all: list,
                     w: int, h: int) -> bytearray:
    """Pixels dark enough to be cast shadow (well below the scene's median
    brightness), excluding canopy-mask pixels — a crown is dark but is not
    its own shadow."""
    thr = min(int(_SHADOW_LUM_FACTOR * _hist_median(hist_all)),
              _SHADOW_LUM_CAP)
    shadow = bytearray(w * h)
    for i in range(w * h):
        if bright[i] <= thr and not mask[i]:
            shadow[i] = 1
    return shadow


def _bearing_vec(bin_idx: int) -> tuple:
    """Unit pixel-space vector for compass bearing bin (0 = north = −y)."""
    b = math.radians(bin_idx * (360.0 / _SHADOW_BINS))
    return math.sin(b), -math.cos(b)


def _bearing_allowed(bin_idx: int, lat: float) -> bool:
    """Hemisphere prior: away from the tropics the sun is on the equator
    side, so shadows point poleward — a 'shadow' pointing the wrong way is
    dark grass, not a shadow."""
    b = math.radians(bin_idx * (360.0 / _SHADOW_BINS))
    if lat > 30.0:
        return math.cos(b) >= -1e-9          # northern half-plane
    if lat < -30.0:
        return math.cos(b) <= 1e-9           # southern half-plane
    return True


def _shadow_frac(shadow: bytearray, w: int, h: int,
                 px: float, py: float, r_px: float, bin_idx: int,
                 span: Optional[float] = None) -> float:
    """Fraction of sample points just beyond the crown edge, along one
    bearing, that land on shadow. ``span`` (px) narrows the sampled band for
    the high-sun retry; default scales with the crown."""
    dx, dy = _bearing_vec(bin_idx)
    if span is None:
        span = max(8.0, 2.0 * r_px)
    hits = n = 0
    for k in range(8):
        d = r_px + 1.0 + span * k / 7.0
        x = int(px + dx * d)
        y = int(py + dy * d)
        if x < 0 or x >= w or y < 0 or y >= h:
            continue
        n += 1
        if shadow[y * w + x]:
            hits += 1
    return hits / n if n else 0.0


def _shadow_run_m(shadow: bytearray, w: int, h: int, px: float, py: float,
                  start_d: float, bin_idx: int, mpp: float) -> float:
    """Length (metres) of the contiguous shadow run along a bearing, starting
    ``start_d`` px from ``(px, py)``. Tolerates 2-px gaps (crown-edge
    scatter); ends after 3 consecutive misses or the search cap."""
    dx, dy = _bearing_vec(bin_idx)
    max_d = start_d + _SHADOW_SEARCH_MAX_M / mpp
    misses = 0
    last_hit = None
    d = start_d
    while d <= max_d:
        x = int(px + dx * d)
        y = int(py + dy * d)
        if 0 <= x < w and 0 <= y < h and shadow[y * w + x]:
            last_hit = d
            misses = 0
        elif last_hit is not None:
            misses += 1
            if misses >= 3:
                break
        elif d - start_d > 6.0:
            break               # never reached shadow near the edge — none
        # Leading misses are tolerated: JPEG smears the crown/shadow
        # boundary into a collar of pixels the canopy mask claims, so the
        # run may only start a few px past the geometric edge.
        d += 1.0
    if last_hit is None:
        return 0.0
    return max(0.0, (last_hit - start_d + 1.0)) * mpp


def _ring_contrast(mask: bytearray, shadow: bytearray, bright: bytearray,
                   w: int, h: int, px: int, py: int, r_px: float) -> str:
    """'pass' when the crown is darker than the sunlit ground around it,
    'fail' when its surroundings look just like it (a patch inside a big
    grassy expanse), 'interior' when there's no visible ground around to
    compare against (a crown inside a closed stand — can't judge here)."""
    r_in = max(1, int(r_px))
    crown_sum = crown_n = 0
    ring_sum = ring_n = 0
    r_out = r_in + 4
    for y in range(max(0, py - r_out), min(h, py + r_out + 1)):
        for x in range(max(0, px - r_out), min(w, px + r_out + 1)):
            d2 = (x - px) ** 2 + (y - py) ** 2
            i = y * w + x
            if d2 <= r_in * r_in:
                if mask[i]:
                    crown_sum += bright[i]
                    crown_n += 1
            elif d2 >= (r_in + 2) ** 2 and d2 <= r_out * r_out:
                # Sunlit surroundings only: other canopy and cast shadow
                # tell us nothing about ground contrast.
                if not mask[i] and not shadow[i]:
                    ring_sum += bright[i]
                    ring_n += 1
    if crown_n == 0:
        return "fail"
    if ring_n < 8:
        return "interior"
    if (ring_sum / ring_n) - (crown_sum / crown_n) >= _RING_CONTRAST_MIN:
        return "pass"
    return "fail"


def _disk_contrast(bright: bytearray, mask: bytearray, w: int, h: int,
                   px: int, py: int, r_px: float) -> int:
    """Internal brightness spread (p90 − p10) across a candidate crown's
    masked pixels. Sunlit crowns mix lit tufts with self-shadow → high
    spread; cast shadow lying on grass receives no direct light → uniformly
    dark, whatever the grass texture. Tiny disks return 255 (pass — too
    small to judge, the size filters own that call)."""
    r_i = max(1, int(r_px))
    vals = []
    for y in range(max(0, py - r_i), min(h, py + r_i + 1)):
        for x in range(max(0, px - r_i), min(w, px + r_i + 1)):
            if (x - px) ** 2 + (y - py) ** 2 > r_i * r_i:
                continue
            i = y * w + x
            if mask[i]:
                vals.append(bright[i])
    if len(vals) < 8:
        return 255
    vals.sort()
    return (vals[int(0.9 * (len(vals) - 1))]
            - vals[int(0.1 * (len(vals) - 1))])


def _classify_foliage(mosaic: bytes, mask: bytearray, w: int, h: int,
                      px: int, py: int, r_px: float) -> Optional[str]:
    """Confident-only conifer/broadleaf tell from crown colour: conifers
    image dark, muted blue-green; leafed-out broadleaf bright saturated
    green. Anything ambiguous stays None (= unknown = year-round shade,
    the app's honest convention — never invent a winter sun break)."""
    r_in = max(1, int(r_px))
    rs = gs = bs = n = 0
    for y in range(max(0, py - r_in), min(h, py + r_in + 1)):
        for x in range(max(0, px - r_in), min(w, px + r_in + 1)):
            if (x - px) ** 2 + (y - py) ** 2 > r_in * r_in:
                continue
            i = y * w + x
            if not mask[i]:
                continue
            rs += mosaic[i * 3]
            gs += mosaic[i * 3 + 1]
            bs += mosaic[i * 3 + 2]
            n += 1
    if n < 4:
        return None
    r_m, g_m, b_m = rs / n, gs / n, bs / n
    lum = (r_m + 2 * g_m + b_m) / 4.0
    if lum < _EVERGREEN_LUM_MAX and (g_m - b_m) < _EVERGREEN_GB_MAX:
        return "evergreen"
    if lum >= _DECIDUOUS_LUM_MIN and (2 * g_m - r_m - b_m) >= _DECIDUOUS_EXG_MIN:
        return "deciduous"
    return None


_COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def _bearing_name(bin_idx: int) -> str:
    return _COMPASS[bin_idx % _SHADOW_BINS]


# ── Blob analysis ────────────────────────────────────────────────────────────

def _components(mask: bytearray, w: int, h: int, min_area_px: int) -> list:
    """4-connected components of the mask as lists of pixel indices, dropping
    specks below ``min_area_px``. Iterative flood fill (no recursion)."""
    seen = bytearray(w * h)
    out = []
    for start in range(w * h):
        if not mask[start] or seen[start]:
            continue
        stack = [start]
        seen[start] = 1
        comp = []
        while stack:
            i = stack.pop()
            comp.append(i)
            x = i % w
            if x + 1 < w and mask[i + 1] and not seen[i + 1]:
                seen[i + 1] = 1
                stack.append(i + 1)
            if x > 0 and mask[i - 1] and not seen[i - 1]:
                seen[i - 1] = 1
                stack.append(i - 1)
            if i + w < w * h and mask[i + w] and not seen[i + w]:
                seen[i + w] = 1
                stack.append(i + w)
            if i - w >= 0 and mask[i - w] and not seen[i - w]:
                seen[i - w] = 1
                stack.append(i - w)
        if len(comp) >= min_area_px:
            out.append(comp)
    return out


def _chamfer(comp: list, w: int) -> dict:
    """Chamfer (3-4) distance-to-edge transform over one component. Returns
    ``{pixel_index: distance_in_thirds_of_px}`` — the inscribed radius at each
    canopy pixel, which for a round crown peaks at the crown centre."""
    inside = set(comp)
    big = 1 << 30
    dist = {i: big for i in comp}
    xs = [i % w for i in comp]
    ys = [i // w for i in comp]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)

    def _d(x, y):
        # Any pixel not in this component (other blobs, background, off the
        # mosaic) counts as background: distance 0.
        if x < 0 or x >= w or y < 0:
            return 0
        i = y * w + x
        return dist[i] if i in inside else 0

    # Forward pass (top-left → bottom-right)…
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            i = y * w + x
            if i not in inside:
                continue
            dist[i] = min(dist[i],
                          _d(x - 1, y) + 3, _d(x, y - 1) + 3,
                          _d(x - 1, y - 1) + 4, _d(x + 1, y - 1) + 4)
    # …then the backward pass (bottom-right → top-left).
    for y in range(y1, y0 - 1, -1):
        for x in range(x1, x0 - 1, -1):
            i = y * w + x
            if i not in inside:
                continue
            dist[i] = min(dist[i],
                          _d(x + 1, y) + 3, _d(x, y + 1) + 3,
                          _d(x + 1, y + 1) + 4, _d(x - 1, y + 1) + 4)
    return dist


def _pack_crowns(comp: list, dist: dict, w: int, min_r_px: float) -> list:
    """Greedy disk packing over one canopy blob: repeatedly take the deepest
    remaining pixel as a crown centre (radius = its inscribed distance),
    suppressing later peaks that fall inside an accepted crown. A shelterbelt
    row of touching crowns resolves into a line of individual trees; an
    isolated round crown yields exactly one. Returns [(px, py, r_px), …]."""
    peaks = sorted(comp, key=lambda i: dist.get(i, 0), reverse=True)
    accepted = []
    for i in peaks:
        r = dist.get(i, 0) / 3.0
        if r < min_r_px:
            break
        x, y = i % w, i // w
        ok = True
        for (ax, ay, ar) in accepted:
            if (x - ax) ** 2 + (y - ay) ** 2 < (0.9 * (r + ar)) ** 2:
                ok = False
                break
        if ok:
            accepted.append((x, y, r))
    return accepted


# ── Imagery mosaic (shared by detection + foliage sampling) ──────────────────

def _build_mosaic(bbox: dict, fetch: Callable, decode: Callable,
                  max_tiles: int) -> Optional[dict]:
    """Fetch + assemble the Esri imagery mosaic covering ``bbox``. Returns
    ``{mosaic(bytes), w, h, origin_x, origin_y, zoom, mpp, tiles_ok,
    tiles_failed, partial}`` or ``None`` when too few tiles decoded (mostly
    holes — a failure, never silently "0"). Shared by ``detect_trees`` (RGB
    fallback) and ``classify_foliage_at_points`` (colour tags for CHM trees)."""
    zoom = _pick_zoom(bbox, max_tiles)
    tx0, ty0, tx1, ty1 = _tile_range(bbox, zoom)
    # A boundary far beyond yard scale can outrun the mosaic budget even at
    # the minimum useful zoom — scan the central block that fits and say so.
    partial = False
    while (tx1 - tx0 + 1) * (ty1 - ty0 + 1) > max_tiles:
        partial = True
        if (tx1 - tx0) >= (ty1 - ty0):
            tx0 += 1
            tx1 -= 1
        else:
            ty0 += 1
            ty1 -= 1
    ntx, nty = tx1 - tx0 + 1, ty1 - ty0 + 1
    w, h = ntx * _TILE_PX, nty * _TILE_PX
    mosaic = bytearray(w * h * 3)
    tiles_ok = tiles_failed = 0
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            data = fetch(zoom, tx, ty)
            decoded = decode(data) if data else None
            if not decoded:
                tiles_failed += 1
                continue
            tw, th, rgb = decoded
            if tw != _TILE_PX or th != _TILE_PX:
                tiles_failed += 1
                continue
            tiles_ok += 1
            ox = (tx - tx0) * _TILE_PX
            oy = (ty - ty0) * _TILE_PX
            for row in range(_TILE_PX):
                src = row * _TILE_PX * 3
                dst = ((oy + row) * w + ox) * 3
                mosaic[dst:dst + _TILE_PX * 3] = rgb[src:src + _TILE_PX * 3]
    if tiles_ok == 0 or tiles_failed > tiles_ok:
        return None
    clat = (bbox["north"] + bbox["south"]) / 2.0
    return {"mosaic": bytes(mosaic), "w": w, "h": h,
            "origin_x": tx0 * _TILE_PX, "origin_y": ty0 * _TILE_PX,
            "zoom": zoom, "mpp": _m_per_px(clat, zoom),
            "tiles_ok": tiles_ok, "tiles_failed": tiles_failed,
            "partial": partial}


# ── Detection pipeline ───────────────────────────────────────────────────────

def detect_trees(bbox: dict, *,
                 buildings: Optional[list] = None,
                 _fetch_tile: Optional[Callable] = None,
                 _decode: Optional[Callable] = None,
                 max_tiles: int = _MAX_TILES) -> Optional[dict]:
    """Detect tree crowns in the satellite imagery covering ``bbox``.

    ``buildings`` (optional) are already-known structures — dicts with
    ``lat``/``lng``/``height_m`` and ideally a ``ring`` of [lng, lat] pairs
    and/or ``radius_m`` — used as photogrammetric scale anchors: a building
    of known height with a legible shadow calibrates the sun's elevation,
    turning every tree's shadow length into a *measured* height.

    ``_fetch_tile(zoom, x, y) -> bytes | None`` and ``_decode(data) ->
    (w, h, rgb_bytes) | None`` are injectable (GUI: HTTP + QImage; tests:
    synthetic). Returns ``None`` when the imagery could not be fetched or
    decoded at all — callers must report that as *failure*, never as "found
    0 trees". Otherwise::

        {"trees": [{"kind": "tree", "lat", "lng", "radius_m", "height_m",
                    "foliage": "evergreen"|"deciduous"|None,
                    "detect_confidence": str, "label": "Tree (detected)",
                    "source": "imagery", "dedupe_m": …}, …],
         "zoom": int, "m_per_px": float,
         "tiles_ok": int, "tiles_failed": int, "capped": bool,
         "partial": bool, "shadow_bearing": "NNE"|None,
         "anchor": {"type": "building"|"allometry", …}|None,
         "dropped": {"ring": int, "shadow": int, "stand": int}}
    """
    if _decode is None:
        return None                  # no codec available — honest failure
    fetch = _fetch_tile or _fetch_tile_bytes
    mos = _build_mosaic(bbox, fetch, _decode, max_tiles)
    if mos is None:
        return None                  # mostly holes — report failure, not "0"
    w, h = mos["w"], mos["h"]
    mosaic = mos["mosaic"]           # bytes
    zoom, mpp = mos["zoom"], mos["mpp"]
    tiles_ok, tiles_failed = mos["tiles_ok"], mos["tiles_failed"]
    partial = mos["partial"]
    origin_x, origin_y = mos["origin_x"], mos["origin_y"]
    clat = (bbox["north"] + bbox["south"]) / 2.0     # for the hemisphere prior
    min_r_px = _MIN_CROWN_RADIUS_M / mpp
    min_area_px = max(4, int(math.pi * min_r_px * min_r_px))

    veg, bright, hist_all = _vegetation_and_brightness(mosaic, w, h)
    smooth, hist = _smooth_brightness(veg, bright, w, h)
    mask = _canopy_mask(veg, smooth, hist, w, h)
    base = {"zoom": zoom, "m_per_px": mpp, "tiles_ok": tiles_ok,
            "tiles_failed": tiles_failed, "capped": False, "partial": partial,
            "shadow_bearing": None, "anchor": None,
            "dropped": {"flat": 0, "ring": 0, "shadow": 0, "stand": 0,
                        "weak": 0}}
    if mask is None:
        return {**base, "trees": []}
    mask = _texture_mask(mask, bright, w, h)

    # Candidate crowns (colour + darkness + texture say "tree-ish"); the
    # physics gates below decide which ones actually are.
    cands = []
    blob_pixels = {}
    for blob_idx, comp in enumerate(_components(mask, w, h, min_area_px)):
        blob_pixels[blob_idx] = comp
        dist = _chamfer(comp, w)
        for (px, py, r_px) in _pack_crowns(comp, dist, w, min_r_px):
            cands.append({"blob": blob_idx, "x": px, "y": py, "r": r_px})

    # Gate 0 — direct light: a sunlit crown mixes lit tufts with
    # self-shadow (high internal brightness spread); cast shadow lying on
    # grass gets no direct light and stays uniformly dark however textured
    # the grass is (the park mega-blob: tree shadows on lawn welded crowns
    # and grass into one giant blob).
    dropped = {"flat": 0, "ring": 0, "shadow": 0, "stand": 0, "weak": 0}
    lit_cands = []
    blob_flat = {}
    for c in cands:
        stats = blob_flat.setdefault(c["blob"], [0, 0])
        stats[1] += 1
        c["contrast"] = _disk_contrast(bright, mask, w, h,
                                       c["x"], c["y"], c["r"])
        if c["contrast"] >= _CROWN_CONTRAST_MIN:
            lit_cands.append(c)
        else:
            stats[0] += 1
            dropped["flat"] += 1
    cands = lit_cands
    # A blob whose candidates are mostly flat is a misread (shadow swath /
    # shaded grass), not a stand — clear its whole footprint back to the
    # scene and re-stamp only its lit crowns, so the survivors get a clean
    # ring, and the freed dark pixels feed the shadow stages instead of
    # starving them. Mostly-lit blobs (real woodlots) are left intact.
    for blob_idx, (n_flat, n_total) in blob_flat.items():
        if n_total >= 3 and n_flat / n_total >= 0.6:
            for i in blob_pixels[blob_idx]:
                mask[i] = 0
            for c in cands:
                if c["blob"] != blob_idx:
                    continue
                r_i = max(1, int(c["r"]))
                for y in range(max(0, c["y"] - r_i),
                               min(h, c["y"] + r_i + 1)):
                    for x in range(max(0, c["x"] - r_i),
                                   min(w, c["x"] + r_i + 1)):
                        if (x - c["x"]) ** 2 + (y - c["y"]) ** 2 \
                                <= r_i * r_i:
                            mask[y * w + x] = 1
    shadow = _shadow_mask_for(mask, bright, hist_all, w, h)

    # Gate 1 — ring contrast: darker than the visible sunlit ground around
    # it, or 'interior' when a closed stand leaves no ground to compare.
    for c in cands:
        c["ring"] = _ring_contrast(mask, shadow, bright, w, h,
                                   c["x"], c["y"], c["r"])

    # Gate 2 — shadow consensus. Ring-passing candidates vote on a shadow
    # bearing (hemisphere prior applied); a coherent peak means the photo
    # has legible shadows, and every kept crown must then agree with it.
    edge_cands = [c for c in cands if c["ring"] == "pass"]

    def _vote(span):
        votes = [0.0] * _SHADOW_BINS
        n_voters = 0
        for c in edge_cands:
            best_bin, best_frac = None, 0.0
            for k in range(_SHADOW_BINS):
                if not _bearing_allowed(k, clat):
                    continue
                f = _shadow_frac(shadow, w, h, c["x"], c["y"], c["r"], k,
                                 span)
                if f > best_frac:
                    best_frac, best_bin = f, k
            if best_bin is not None and best_frac >= _SHADOW_VOTE_FRAC:
                votes[best_bin] += best_frac
                n_voters += 1
        total = sum(votes)
        if n_voters >= 3 and n_voters >= 0.1 * max(1, len(cands)) \
                and total > 0:
            peak = max(range(_SHADOW_BINS),
                       key=lambda k: (votes[(k - 1) % _SHADOW_BINS]
                                      + votes[k]
                                      + votes[(k + 1) % _SHADOW_BINS]))
            cluster = (votes[(peak - 1) % _SHADOW_BINS] + votes[peak]
                       + votes[(peak + 1) % _SHADOW_BINS])
            if cluster >= 0.5 * total:
                return peak
        return None

    # Standard band first; a near-noon capture leaves only a thin shadow
    # fringe, so retry with a tight band before declaring "no shadows".
    vote_span = None
    bearing = _vote(None)
    if bearing is None:
        bearing = _vote(_SHADOW_SHORT_SPAN_PX)
        if bearing is not None:
            vote_span = _SHADOW_SHORT_SPAN_PX

    # Verdicts. Stand interiors can't be judged individually (their shadow
    # falls on the neighbouring crown, their ring is more canopy) — they
    # inherit their blob's edge verdict: a real stand has verified edges,
    # a mis-masked grass expanse doesn't. With NO legible shadows the
    # remaining evidence is thinner, so the bar rises everywhere: stronger
    # internal contrast required, and interiors need a much stronger edge
    # verdict to inherit (degrade toward caution, never permissiveness).
    blob_edge: dict = {}
    for c in cands:
        if c["ring"] == "interior":
            continue
        stats = blob_edge.setdefault(c["blob"], [0, 0])
        stats[1] += 1
        keep = c["ring"] == "pass"
        if not keep:
            dropped["ring"] += 1
        elif bearing is not None:
            f = max(_shadow_frac(shadow, w, h, c["x"], c["y"], c["r"], k,
                                 vote_span)
                    for k in ((bearing - 1) % _SHADOW_BINS, bearing,
                              (bearing + 1) % _SHADOW_BINS))
            if f < _MIN_SHADOW_FRAC:
                keep = False
                dropped["shadow"] += 1
            else:
                c["verified"] = True
        elif c["contrast"] < _CROWN_CONTRAST_STRICT:
            keep = False
            dropped["weak"] += 1
        c["keep"] = keep
        if keep:
            stats[0] += 1
    inherit_ratio = 0.3 if bearing is not None else 0.6
    for c in cands:
        if c["ring"] != "interior":
            continue
        kept_e, total_e = blob_edge.get(c["blob"], (0, 0))
        if total_e == 0 or kept_e / total_e >= inherit_ratio:
            c["keep"] = True
            c["inherited"] = True
        else:
            c["keep"] = False
            dropped["stand"] += 1

    # Sun-elevation anchor for shadow→height: prefer a building of known
    # height (its shadow in the same photo calibrates tan(elevation)
    # absolutely); else the median allometric ratio over verified crowns.
    # origin_x/origin_y (mosaic (0,0) in global pixel coords) come from
    # _build_mosaic above.
    tan_elev = None
    anchor = None
    if bearing is not None:
        dxb, dyb = _bearing_vec(bearing)
        best = None
        for bld in buildings or []:
            b_lat, b_lng = bld.get("lat"), bld.get("lng")
            h_b = bld.get("height_m")
            if b_lat is None or b_lng is None or not h_b:
                continue
            gx, gy = _latlng_to_global_px(b_lat, b_lng, zoom)
            bx, by = gx - origin_x, gy - origin_y
            if not (0 <= bx < w and 0 <= by < h):
                continue
            # Start the march at the building's far edge along the bearing.
            extent = (float(bld.get("radius_m") or 4.0)) / mpp
            ring = bld.get("ring") or []
            proj = 0.0
            for p in ring:                     # ring is [lng, lat] pairs
                vgx, vgy = _latlng_to_global_px(p[1], p[0], zoom)
                proj = max(proj, (vgx - gx) * dxb + (vgy - gy) * dyb)
            if proj > 0:
                extent = proj
            length = _shadow_run_m(shadow, w, h, bx, by, extent + 1.0,
                                   bearing, mpp)
            if length >= 1.0 and (best is None or length > best[1]):
                best = (float(h_b), length)
        if best is not None:
            tan_elev = best[0] / best[1]
            anchor = {"type": "building", "height_m": round(best[0], 1),
                      "shadow_m": round(best[1], 1)}
        else:
            ratios = []
            for c in cands:
                if not c.get("verified"):
                    continue
                c["shadow_m"] = _shadow_run_m(shadow, w, h, c["x"], c["y"],
                                              c["r"] + 1.0, bearing, mpp)
                if c["shadow_m"] >= 1.0:
                    r_m = min(_MAX_CROWN_RADIUS_M, c["r"] * mpp)
                    ratios.append((_HEIGHT_PER_RADIUS * r_m) / c["shadow_m"])
            if len(ratios) >= 3:
                ratios.sort()
                tan_elev = ratios[len(ratios) // 2]
                anchor = {"type": "allometry"}

    # Emit, strongest first: with the physics gates in front, hitting the
    # cap means a genuinely tree-dense area (or a hard photo) — keep the
    # best-evidenced crowns rather than refusing wholesale.
    final = [c for c in cands if c.get("keep")]
    final.sort(key=lambda c: (not c.get("verified"),
                              -c.get("contrast", 0)))
    capped = len(final) > _MAX_TREES
    final = final[:_MAX_TREES]
    trees = []
    for c in final:
        lat, lng = _global_px_to_latlng(origin_x + c["x"] + 0.5,
                                        origin_y + c["y"] + 0.5, zoom)
        # Keep only crowns whose centre falls in the requested bbox —
        # whole-tile overflow shouldn't leak trees the user never asked
        # about (precise boundary clipping happens downstream).
        if not (bbox["south"] <= lat <= bbox["north"]
                and bbox["west"] <= lng <= bbox["east"]):
            continue
        radius_m = max(_MIN_CROWN_RADIUS_M,
                       min(_MAX_CROWN_RADIUS_M, c["r"] * mpp))
        foliage = _classify_foliage(mosaic, mask, w, h,
                                    c["x"], c["y"], c["r"])
        # Height: measured from the crown's own shadow when the photo gives
        # us one and a calibration exists; else foliage-aware allometry.
        height_m = None
        if c.get("verified") and tan_elev is not None:
            if "shadow_m" not in c:
                c["shadow_m"] = _shadow_run_m(shadow, w, h, c["x"], c["y"],
                                              c["r"] + 1.0, bearing, mpp)
            if c["shadow_m"] >= 1.0:
                height_m = max(_HEIGHT_MIN_M,
                               min(_HEIGHT_MAX_MEASURED_M,
                                   c["shadow_m"] * tan_elev))
        if height_m is None:
            per_r = _HEIGHT_PER_RADIUS_BY_FOLIAGE.get(
                foliage, _HEIGHT_PER_RADIUS)
            height_m = max(_HEIGHT_MIN_M,
                           min(_HEIGHT_MAX_M, per_r * radius_m))
        if c.get("verified"):
            confidence = "high (shadow-verified)"
        elif c.get("inherited"):
            confidence = "medium (stand interior)"
        else:
            confidence = "medium (no shadow consensus in photo)"
        trees.append({
            "kind": "tree",
            "lat": lat, "lng": lng,
            "radius_m": round(radius_m, 1),
            "height_m": round(height_m, 1),
            "label": "Tree (detected)",
            "source": "imagery",
            "foliage": foliage,
            "detect_confidence": confidence,
            # A detection landing inside an already-known crown is the
            # same tree — scale the dedupe distance with crown size.
            "dedupe_m": max(2.0, 0.8 * radius_m),
        })
    return {**base, "trees": trees, "capped": capped, "dropped": dropped,
            "shadow_bearing": (_bearing_name(bearing)
                               if bearing is not None else None),
            "anchor": anchor}


# ── Import tail (mirrors osm_features.import_osm_result) ─────────────────────

def _shift_latlng(lat: float, lng: float,
                  east_m: float, north_m: float) -> tuple:
    """Move a point by metres east/north (cosLat metric — see src/projection.py;
    centimetre-accurate at the ≤30 m alignment nudges involved here)."""
    if not east_m and not north_m:
        return lat, lng
    cos_lat = math.cos(math.radians(lat)) or 1e-9
    return (lat + north_m / 111320.0,
            lng + east_m / (111320.0 * cos_lat))


def import_detected_trees(res: Optional[dict], project_dict: dict, *,
                          boundary=None, margin_m: float = 30.0,
                          offset_east_m: float = 0.0,
                          offset_north_m: float = 0.0,
                          area_note: str = "") -> dict:
    """Filter a detection result to the boundary, add trees to the project and
    compose the honest status message — the whole import tail in one pure,
    testable call (mirrors ``osm_features.import_osm_result``).

    ``offset_east_m``/``offset_north_m`` are the user's satellite-alignment
    nudge: the basemap is *displayed* shifted by that much, so a position read
    from raw imagery must be shifted the same way to land where the user sees
    the tree — and where their drawn boundary/data actually is.

    Returns ``{"added": int, "kept": int, "found": int, "message": str}``;
    ``res=None`` (fetch/decoding failure) produces added=0 and says so."""
    from src.osm_features import add_features_to_project, filter_to_boundary
    if res is None:
        return {"added": 0, "kept": 0, "found": 0,
                "message": ("Couldn't read the satellite imagery (offline or "
                            "the tile server refused) — nothing was imported. "
                            "Try again in a minute, or mark trees by hand "
                            "below.")}
    items = []
    for t in res.get("trees", []):
        lat, lng = _shift_latlng(t["lat"], t["lng"],
                                 offset_east_m, offset_north_m)
        items.append({**t, "lat": lat, "lng": lng})
    kept, n_inside, n_neigh = filter_to_boundary(items, boundary, margin_m)
    added = add_features_to_project(kept, project_dict)
    msg = (f"Scanned the satellite photo at {res.get('m_per_px', 0):.2f} m/px; "
           f"spotted {len(items)} tree crown{'s' if len(items) != 1 else ''}")
    if boundary and len(boundary) >= 3:
        msg += (f"; kept {len(kept)} ({n_inside} inside your boundary + "
                f"{n_neigh} neighbour{'s' if n_neigh != 1 else ''} within "
                f"{margin_m:.0f} m)")
    elif area_note:
        msg += f" ({area_note})"
    msg += f"; added {added} new."
    if res.get("tiles_failed"):
        msg += (f" ({res['tiles_failed']} imagery tile(s) didn't load — "
                "part of the area wasn't scanned.)")
    if res.get("partial"):
        msg += (" (The boundary is larger than one scan covers — only the "
                "central area was scanned.)")
    if res.get("capped"):
        msg += (" (Very busy photo — kept only the strongest reads at the "
                "safety cap.)")
    d = res.get("dropped") or {}
    n_dropped = sum(d.values())
    bearing = res.get("shadow_bearing")
    if bearing:
        msg += (f" Crowns were cross-checked against their cast shadows "
                f"(pointing ≈{bearing})")
        if n_dropped:
            msg += (f"; {n_dropped} look-alike patch"
                    f"{'es' if n_dropped != 1 else ''} (grass/shrub — no "
                    "matching shadow or ground contrast) dropped")
        msg += "."
    elif n_dropped:
        msg += (f" {n_dropped} look-alike patch"
                f"{'es' if n_dropped != 1 else ''} without ground contrast "
                "dropped.")
    if added:
        anchor = res.get("anchor") or {}
        if anchor.get("type") == "building":
            msg += (f" Heights are measured from each tree's shadow, scaled "
                    f"by your {anchor['height_m']:g} m building's "
                    f"{anchor['shadow_m']:g} m shadow.")
        elif anchor.get("type") == "allometry":
            msg += (" Heights are estimated from shadow lengths (scale from "
                    "typical crown proportions — import a building for a "
                    "true reference).")
        elif bearing:
            msg += (" Shadow lengths weren't readable enough to measure "
                    "heights, so they're rough estimates from crown size.")
        else:
            msg += (" No legible shadows in this photo (even after a "
                    "high-sun retry) — only the strongest reads were kept; "
                    "heights are rough estimates from crown size.")
        n_ev = sum(1 for t in kept if t.get("foliage") == "evergreen")
        n_de = sum(1 for t in kept if t.get("foliage") == "deciduous")
        n_un = len(kept) - n_ev - n_de
        msg += (f" Foliage: {n_ev} conifer-like (year-round shade), "
                f"{n_de} broadleaf-like (bare in winter), {n_un} unknown "
                "(treated as year-round shade). Click a tree and press "
                "Delete to drop any false hits.")
    elif not items:
        msg += (" Crowns need to read as darker, textured green blobs "
                "against the ground — leaf-off deciduous trees may be "
                "invisible in the photo. Mark or draw missed trees by "
                "hand below.")
    return {"added": added, "kept": len(kept), "found": len(items),
            "message": msg}


# ── Foliage tagging for height-detected trees (colour ⊗ height, P7) ──────────

def classify_foliage_at_points(trees: list, bbox: dict, *,
                               _fetch_tile: Optional[Callable] = None,
                               _decode: Optional[Callable] = None,
                               max_tiles: int = _MAX_TILES) -> list:
    """Best-effort: tag each tree's foliage (conifer/broadleaf) from the
    satellite photo's colour at its location. The canopy-height map gives
    position + height but no colour, so this crosses the two data domains
    (P7) to add the conifer/deciduous distinction the height map can't —
    feeding leaf-off winter shade and the 3D crown shape.

    Mutates ``trees`` in place (sets ``foliage`` where the colour is
    confident) and returns them. Any fetch failure or ambiguous colour
    leaves ``foliage`` unchanged (unknown = year-round shade — never
    invents a winter sun break). ``_fetch_tile``/``_decode`` injectable."""
    if _decode is None or not trees:
        return trees
    fetch = _fetch_tile or _fetch_tile_bytes
    mos = _build_mosaic(bbox, fetch, _decode, max_tiles)
    if mos is None:
        return trees
    w, h, mosaic = mos["w"], mos["h"], mos["mosaic"]
    zoom, mpp = mos["zoom"], mos["mpp"]
    ox, oy = mos["origin_x"], mos["origin_y"]
    veg, _bright, _hist = _vegetation_and_brightness(mosaic, w, h)
    for t in trees:
        gx, gy = _latlng_to_global_px(t["lat"], t["lng"], zoom)
        px, py = int(gx - ox), int(gy - oy)
        if not (0 <= px < w and 0 <= py < h):
            continue
        r_px = max(2, int((t.get("radius_m") or 2.0) / mpp))
        fol = _classify_foliage(mosaic, veg, w, h, px, py, r_px)
        if fol:
            t["foliage"] = fol
    return trees
