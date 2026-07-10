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
_MIN_CROWN_RADIUS_M = 0.9   # smaller blobs are shrubs/noise — skip
_MAX_CROWN_RADIUS_M = 12.0
_MAX_TREES = 400        # flood guard for a bad threshold day
# Open-grown height ≈ 2.6 × crown radius: between conifer (~5×) and broadleaf
# (~2×) allometry — a stated mid-range estimate, clamped to yard-tree reality.
_HEIGHT_PER_RADIUS = 2.6
_HEIGHT_MIN_M, _HEIGHT_MAX_M = 3.0, 18.0


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
    idx = 0
    for i in range(w * h):
        r = rgb[idx]
        g = rgb[idx + 1]
        b = rgb[idx + 2]
        idx += 3
        bright[i] = (r + 2 * g + b) >> 2
        if g >= _G_MIN and (2 * g - r - b) >= _EXG_MIN and g > b:
            veg[i] = 1
    return veg, bright


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


# ── Detection pipeline ───────────────────────────────────────────────────────

def detect_trees(bbox: dict, *,
                 _fetch_tile: Optional[Callable] = None,
                 _decode: Optional[Callable] = None,
                 max_tiles: int = _MAX_TILES) -> Optional[dict]:
    """Detect tree crowns in the satellite imagery covering ``bbox``.

    ``_fetch_tile(zoom, x, y) -> bytes | None`` and ``_decode(data) ->
    (w, h, rgb_bytes) | None`` are injectable (GUI: HTTP + QImage; tests:
    synthetic). Returns ``None`` when the imagery could not be fetched or
    decoded at all — callers must report that as *failure*, never as "found
    0 trees". Otherwise::

        {"trees": [{"kind": "tree", "lat", "lng", "radius_m", "height_m",
                    "label": "Tree (detected)", "source": "imagery",
                    "dedupe_m": …}, …],
         "zoom": int, "m_per_px": float,
         "tiles_ok": int, "tiles_failed": int, "capped": bool}
    """
    if _decode is None:
        return None                  # no codec available — honest failure
    fetch = _fetch_tile or _fetch_tile_bytes
    zoom = _pick_zoom(bbox, max_tiles)
    tx0, ty0, tx1, ty1 = _tile_range(bbox, zoom)
    # A boundary far beyond yard scale can outrun the mosaic budget even at
    # the minimum useful zoom — scan the central block that fits and say so,
    # rather than fetching hundreds of tiles or silently lying about coverage.
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
            decoded = _decode(data) if data else None
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
        return None                  # mostly holes — report failure, not "0"

    clat = (bbox["north"] + bbox["south"]) / 2.0
    mpp = _m_per_px(clat, zoom)
    min_r_px = _MIN_CROWN_RADIUS_M / mpp
    min_area_px = max(4, int(math.pi * min_r_px * min_r_px))

    veg, bright = _vegetation_and_brightness(bytes(mosaic), w, h)
    smooth, hist = _smooth_brightness(veg, bright, w, h)
    mask = _canopy_mask(veg, smooth, hist, w, h)
    base = {"zoom": zoom, "m_per_px": mpp, "tiles_ok": tiles_ok,
            "tiles_failed": tiles_failed, "capped": False,
            "partial": partial}
    if mask is None:
        return {**base, "trees": []}
    mask = _texture_mask(mask, bright, w, h)

    origin_x = tx0 * _TILE_PX       # mosaic (0,0) in global pixel coords
    origin_y = ty0 * _TILE_PX
    trees = []
    capped = False
    for comp in _components(mask, w, h, min_area_px):
        dist = _chamfer(comp, w)
        for (px, py, r_px) in _pack_crowns(comp, dist, w, min_r_px):
            lat, lng = _global_px_to_latlng(origin_x + px + 0.5,
                                            origin_y + py + 0.5, zoom)
            # Keep only crowns whose centre falls in the requested bbox —
            # whole-tile overflow shouldn't leak trees the user never asked
            # about (precise boundary clipping happens downstream).
            if not (bbox["south"] <= lat <= bbox["north"]
                    and bbox["west"] <= lng <= bbox["east"]):
                continue
            radius_m = max(_MIN_CROWN_RADIUS_M,
                           min(_MAX_CROWN_RADIUS_M, r_px * mpp))
            height_m = max(_HEIGHT_MIN_M,
                           min(_HEIGHT_MAX_M, _HEIGHT_PER_RADIUS * radius_m))
            trees.append({
                "kind": "tree",
                "lat": lat, "lng": lng,
                "radius_m": round(radius_m, 1),
                "height_m": round(height_m, 1),
                "label": "Tree (detected)",
                "source": "imagery",
                # A detection landing inside an already-known crown is the
                # same tree — scale the dedupe distance with crown size.
                "dedupe_m": max(2.0, 0.8 * radius_m),
            })
            if len(trees) >= _MAX_TREES:
                capped = True
                break
        if capped:
            break
    return {**base, "trees": trees, "capped": capped}


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
        msg += (" Detection stopped at the safety cap — the photo may be "
                "too busy for a clean read here.")
    if added:
        msg += (" Positions and crown sizes are measured from the photo; "
                "heights are rough estimates from crown size. Click a tree "
                "and press Delete to drop any false hits (shrub beds, "
                "shadows).")
    elif not items:
        msg += (" Crowns need to read as darker, textured green blobs "
                "against the ground — leaf-off deciduous trees may be "
                "invisible in the photo. Mark or draw missed trees by "
                "hand below.")
    return {"added": added, "kept": len(kept), "found": len(items),
            "message": msg}
