"""
vector_tiles.py — the buildings off OpenStreetMap's map tiles, when its query
servers do not answer (V3.37).

The owner's third screenshot of a failed import read "OpenStreetMap didn't
answer: its servers are busy", over a street map that draws every building on
the block. The buildings are in OpenStreetMap; what failed was Overpass, the
query servers the import asks, which turn a busy or rate-limited caller away.
The same data is published as map tiles: OpenFreeMap serves OpenStreetMap in
the OpenMapTiles schema from a CDN, free, with no key and no limit per address,
and a zoom-14 tile (about 1.5 km across here) holds every building outline in
it, with a height its builders work out from the same height and storey tags
the Overpass import reads (``render_height``). One to four tiles cover a yard.

A tile is a protocol buffer (the Mapbox Vector Tile format, 2.1). The decoder
below reads only what a building needs, the ``building`` layer's polygons and
two of their values, in plain Python, so the app gains no dependency;
``tests/test_vector_tiles.py`` checks it against tiles a reference encoder
wrote.

Qt-free. Each building is the dict ``osm_features.parse_elements`` makes, so
everything after the fetch is the import it always was.
"""

from __future__ import annotations

import gzip
import json
import math
import struct
from typing import Optional

from src.log import get_logger

log = get_logger(__name__)

#: OpenFreeMap's TileJSON, which holds the address of the current tiles.
TILEJSON_URL = "https://tiles.openfreemap.org/planet"
#: The tiles' deepest zoom, where every building is drawn whole.
ZOOM = 14
#: More tiles than this is not a yard, and is asked of nobody.
MAX_TILES = 16
LAYER = "building"


# ── Reading a protocol buffer ────────────────────────────────────────────────

def _varint(buf, i: int):
    shift = result = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7


def _fields(buf):
    """``(field number, wire type, value)`` for each field of one message:
    an int for a varint, a slice for anything with a length or a fixed
    width."""
    i, n = 0, len(buf)
    while i < n:
        key, i = _varint(buf, i)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, i = _varint(buf, i)
        elif wire == 2:
            length, i = _varint(buf, i)
            value, i = buf[i:i + length], i + length
        elif wire == 1:
            value, i = buf[i:i + 8], i + 8
        elif wire == 5:
            value, i = buf[i:i + 4], i + 4
        else:
            raise ValueError(f"wire type {wire} at byte {i}")
        yield number, wire, value


def _packed(buf) -> list:
    out, i = [], 0
    while i < len(buf):
        value, i = _varint(buf, i)
        out.append(value)
    return out


def _zigzag(n: int) -> int:
    return (n >> 1) ^ -(n & 1)


def _value(buf):
    """A layer's ``Value``: a string, float, double, int, uint, sint or
    bool, whichever it holds."""
    for number, _wire, v in _fields(buf):
        if number == 1:
            return bytes(v).decode("utf-8", "replace")
        if number == 2:
            return struct.unpack("<f", v)[0]
        if number == 3:
            return struct.unpack("<d", v)[0]
        if number == 4:
            return v - (1 << 64) if v >= 1 << 63 else v
        if number == 5:
            return v
        if number == 6:
            return _zigzag(v)
        if number == 7:
            return bool(v)
    return None


def _rings(geometry: list) -> list:
    """A polygon's rings in tile units, ``[[(x, y), …], …]``: each a MoveTo,
    LineTos and a ClosePath, every coordinate a zigzagged step from the last."""
    rings: list = []
    x = y = i = 0
    while i < len(geometry):
        command, count = geometry[i] & 7, geometry[i] >> 3
        i += 1
        if command == 7:                     # ClosePath: the ring is done
            continue
        if command not in (1, 2):
            raise ValueError(f"geometry command {command}")
        for _ in range(count):
            x += _zigzag(geometry[i])
            y += _zigzag(geometry[i + 1])
            i += 2
            if command == 1:                 # MoveTo starts a ring
                rings.append([(x, y)])
            else:
                rings[-1].append((x, y))
    return rings


def _area(ring) -> float:
    """The surveyor's formula in tile units: positive for an outer ring,
    negative for a hole (the format's own rule; y points down)."""
    return sum(ring[i][0] * ring[(i + 1) % len(ring)][1]
               - ring[(i + 1) % len(ring)][0] * ring[i][1]
               for i in range(len(ring))) / 2.0


def layer_polygons(data, name: str = LAYER):
    """``(extent, [(properties, outer rings), …])`` for one layer's polygons,
    or ``None`` when the tile has no such layer. Holes are left out: a
    building's courtyard does not change the shade it casts much."""
    for number, wire, layer in _fields(memoryview(data)):
        if number != 3 or wire != 2:
            continue
        found, extent, keys, values, feats = None, 4096, [], [], []
        for n2, _w2, v2 in _fields(layer):
            if n2 == 1:
                found = bytes(v2).decode("utf-8", "replace")
                if found != name:
                    break
            elif n2 == 2:
                feats.append(v2)
            elif n2 == 3:
                keys.append(bytes(v2).decode("utf-8", "replace"))
            elif n2 == 4:
                values.append(v2)
            elif n2 == 5:
                extent = v2
        if found != name:
            continue
        values = [_value(v) for v in values]
        polygons = []
        for feat in feats:
            kind, tags, geometry = 0, [], []
            for n3, w3, v3 in _fields(feat):
                if n3 == 2:
                    tags = _packed(v3) if w3 == 2 else tags + [v3]
                elif n3 == 3:
                    kind = v3
                elif n3 == 4:
                    geometry = _packed(v3) if w3 == 2 else geometry + [v3]
            if kind != 3:                    # 3 = POLYGON
                continue
            props = {keys[tags[k]]: values[tags[k + 1]]
                     for k in range(0, len(tags) - 1, 2)}
            outers = [r for r in _rings(geometry)
                      if len(r) >= 3 and _area(r) > 0]
            polygons.append((props, outers))
        return extent, polygons
    return None


# ── Tiles and the ground ─────────────────────────────────────────────────────

def tile_xy(lat: float, lng: float, z: int) -> tuple:
    """The ``(x, y)`` of the web-map tile at zoom ``z`` holding a point."""
    n = 2 ** z
    x = int((lng + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi)
            / 2.0 * n)
    return min(n - 1, max(0, x)), min(n - 1, max(0, y))


def tiles_for_bbox(bbox: dict, z: int) -> list:
    """Every tile at zoom ``z`` the box touches, ``[(x, y), …]``."""
    x0, y0 = tile_xy(bbox["north"], bbox["west"], z)
    x1, y1 = tile_xy(bbox["south"], bbox["east"], z)
    return [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]


def to_lnglat(z: int, x: int, y: int, px: float, py: float,
              extent: int = 4096) -> tuple:
    """``(lng, lat)`` of a point ``(px, py)`` in tile ``(x, y)``'s units."""
    n = 2 ** z
    lng = (x + px / extent) / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(
        math.pi * (1.0 - 2.0 * (y + py / extent) / n))))
    return lng, lat


def tile_buildings(data: bytes, z: int, x: int, y: int, *, keep=None) -> list:
    """The buildings in one tile, as ``osm_features.parse_elements`` makes
    them. A tile repeats a strip of its neighbours around its edge (its
    buffer), so a building counts in the tile its middle is in, once:
    ``keep(tx, ty)``, told that tile, says whether to count it here (by
    default only when it is this one)."""
    from src.osm_features import (_DEFAULT_BUILDING_HEIGHT_M, ring_centroid,
                                  ring_radius_m)
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    layer = layer_polygons(data)
    if layer is None:
        return []
    extent, polygons = layer
    out = []
    for props, outers in polygons:
        # An outline whose parts are drawn too: the parts carry the heights.
        if props.get("hide_3d"):
            continue
        height = props.get("render_height")
        for ring in outers:
            mx = sum(p[0] for p in ring) / len(ring)
            my = sum(p[1] for p in ring) / len(ring)
            home = (x + math.floor(mx / extent), y + math.floor(my / extent))
            if not (keep(*home) if keep is not None else home == (x, y)):
                continue
            footprint = [list(to_lnglat(z, x, y, px, py, extent))
                         for px, py in ring]
            footprint.append(list(footprint[0]))
            centre = ring_centroid(footprint)
            if centre is None:
                continue
            out.append({
                "kind": "building", "lat": centre[0], "lng": centre[1],
                "height_m": (max(0.5, float(height)) if height
                             else _DEFAULT_BUILDING_HEIGHT_M),
                "radius_m": max(1.0, ring_radius_m(footprint, centre)),
                "footprint": footprint})
    return out


def _touches(item: dict, bbox: dict) -> bool:
    """Overpass's rule for a way in a box: any corner inside it."""
    return any(bbox["south"] <= lat <= bbox["north"]
               and bbox["west"] <= lng <= bbox["east"]
               for lng, lat in item["footprint"])


def fetch_buildings(bbox: dict, *, why: Optional[list] = None,
                    _get=None) -> Optional[list]:
    """The buildings in ``bbox`` read off OpenFreeMap's tiles, or ``None``
    when the tiles could not be had, with what went wrong added to ``why``
    as for Overpass. ``_get(url)`` (bytes, or an ``Unanswered``) is
    injectable for tests."""
    from src.osm_features import GARBLED, Unanswered, _host, fetch_bytes
    get = _get or fetch_bytes
    misses = why if why is not None else []

    def miss(unanswered):
        misses.append(unanswered)
        log.info("Map tiles %s: %s (%s)", unanswered.host, unanswered.kind,
                 unanswered.detail)
        return None

    raw = get(TILEJSON_URL)
    if isinstance(raw, Unanswered):
        return miss(raw)
    try:
        tilejson = json.loads(bytes(raw).decode("utf-8"))
        template = str(tilejson["tiles"][0])
        zoom = min(ZOOM, int(tilejson.get("maxzoom", ZOOM)))
    except (ValueError, KeyError, IndexError, TypeError):
        return miss(Unanswered(_host(TILEJSON_URL), GARBLED,
                               "no tile address in its TileJSON"))
    tiles = tiles_for_bbox(bbox, zoom)
    if len(tiles) > MAX_TILES:
        log.info("Map tiles: %d tiles is not a yard; not asked", len(tiles))
        return None
    found: list = []
    fetched = set(tiles)
    for x, y in tiles:
        url = (template.replace("{z}", str(zoom)).replace("{x}", str(x))
               .replace("{y}", str(y)))
        raw = get(url)
        if isinstance(raw, Unanswered):
            return miss(raw)
        # Counted where its middle is, or here when that tile is not asked:
        # a building across the seam of the yard's tile is the neighbour
        # whose shade falls on the yard.
        here = (x, y)
        try:
            found += tile_buildings(
                bytes(raw), zoom, x, y,
                keep=lambda tx, ty, here=here: (tx, ty) == here
                or (tx, ty) not in fetched)
        except (ValueError, IndexError, KeyError, struct.error, OSError,
                EOFError) as exc:
            return miss(Unanswered(_host(url), GARBLED,
                                   f"unreadable tile ({exc})"))
    return [b for b in found if _touches(b, bbox)]
