"""
osm_features.py — Import existing trees & buildings from OpenStreetMap (V1.51).

So the design generator's shade model and keep-out zones can account for what's
already on the property without the user marking everything by hand. Buildings
are well-mapped in towns; individual trees less so — hence this pairs with the
manual marking from V1.49 as a fallback for whatever OSM misses.

Mirrors the ``src/property_data.py`` fetchers exactly: stdlib ``urllib`` only,
short timeout, and **degrade gracefully** — every fetch returns ``[]`` / ``None``
on any failure so the UI shows "none found" rather than crashing. (This whole
module is therefore untestable against the live API in CI; tests parse captured
Overpass JSON fixtures, the same way ``test_property_data`` does.)

Data → project features:
  * building way  → ``existing_building`` (centroid, footprint radius, height
    from ``height`` or ``building:levels`` × 3 m).
  * ``natural=tree`` node → ``existing_tree`` (point, canopy radius from
    ``diameter_crown`` when present, else a default).

Public API:
  * ``fetch_buildings(bbox) -> list[dict]``
  * ``fetch_trees(bbox) -> list[dict]``
  * ``fetch_existing_features(bbox) -> dict`` (both, one Overpass call)
Each returned item: ``{"kind": "tree"|"building", "lat", "lng", "height_m",
"radius_m"}`` — ready for ``design_api.add_existing_tree/building``.

**Why a fetch failed is kept (V3.37).** Every failure used to come back as
``None`` with nothing recorded, so "busy", "offline", "the computer could not
check the server's certificate" and "blocked" all read "OpenStreetMap didn't
answer (busy or offline)", in the app and in its log. Each server's answer is
now an :class:`Unanswered` with its kind, logged, and :func:`failure_words`
turns the list into the one sentence the status line shows.
"""

from __future__ import annotations

import json
import logging
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import NamedTuple, Optional

# The server is told 25 s; the client waits a little longer, because a busy
# server queues a query before it runs it (V3.37: both were 25 s).
_TIMEOUT = 30.0
from src.http_utils import _USER_AGENT  # one identity (V3.31, FN-6)  # noqa: E402
from src.log import get_logger  # noqa: E402

log = get_logger(__name__)

# Public Overpass instances, asked in this order. The main one rate-limits per
# address hard (two imports within seconds routinely get a 429), and until
# V3.37 a failure asked it again after two seconds, which mostly got the same
# answer, before the one mirror. Now the others are asked first, and the main
# one again only when it said it was busy, after a longer pause.
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_OVERPASS_URLS = [
    _OVERPASS_URL,
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
_BUSY_PAUSE_S = 5.0

# What went wrong with one server (V3.37), worst news for the person first:
# the order :func:`failure_words` picks the sentence by.
BUSY = "busy"                 # 429, 502-504, or a query it cut short
SLOW = "slow"                 # no answer within _TIMEOUT
REFUSED = "refused"           # any other HTTP error: a 403 would be a block
CERTIFICATE = "certificate"   # its certificate could not be checked
GARBLED = "garbled"           # an answer that was not Overpass's JSON
UNREACHABLE = "unreachable"   # no connection: offline, no DNS, refused
_KINDS = (BUSY, SLOW, REFUSED, CERTIFICATE, GARBLED, UNREACHABLE)


class Unanswered(NamedTuple):
    """One server that did not answer: its host, the kind (above), and the
    detail the log keeps (an HTTP status, the exception's words)."""
    host: str
    kind: str
    detail: str

_DEFAULT_TREE_HEIGHT_M = 7.0
_DEFAULT_TREE_RADIUS_M = 3.0
_DEFAULT_BUILDING_HEIGHT_M = 5.0
_STOREY_HEIGHT_M = 3.0


def _bbox_str(bbox: dict) -> str:
    """Overpass wants ``south,west,north,east``."""
    return f"{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']}"


#: Which OSM ``highway`` values count as "a street this property fronts onto"
#: (V2.58). Footpaths, cycleways and driveways are excluded on purpose: the
#: question cues-to-care asks is which edge the *public* sees from the road, and
#: a back-lane cycle path is not that.
ROAD_HIGHWAYS = ("motorway", "trunk", "primary", "secondary", "tertiary",
                 "unclassified", "residential", "living_street", "service")


#: A yard's query declares this much memory (V3.37). Overpass admits a query
#: only while what it declares fits what the server has free, and the default
#: (512 MiB) is far more than a few hundred metres of buildings needs, so a
#: busy server turned a yard's query away for asking what a city's would.
_YARD_MAXSIZE = 64 * 1024 * 1024
_YARD_SPAN_DEG = 0.01           # a box under ~1 km a side counts as a yard


def _query(bbox: dict, include_trees: bool, include_buildings: bool,
           include_roads: bool = False) -> str:
    # Both ways AND relations: large complexes (apartment blocks with
    # courtyards) are often mapped as multipolygon relations, which a
    # way-only query never returns (V2.13).
    parts = []
    b = _bbox_str(bbox)
    if include_buildings:
        parts.append(f'way["building"]({b});')
        parts.append(f'relation["building"]({b});')
    if include_trees:
        parts.append(f'node["natural"="tree"]({b});')
    if include_roads:
        # One regex arm rather than nine, to keep the query short.
        parts.append(f'way["highway"~"^({"|".join(ROAD_HIGHWAYS)})$"]({b});')
    small = (bbox["north"] - bbox["south"] < _YARD_SPAN_DEG
             and bbox["east"] - bbox["west"] < _YARD_SPAN_DEG)
    maxsize = f"[maxsize:{_YARD_MAXSIZE}]" if small else ""
    return f"[out:json][timeout:25]{maxsize};({''.join(parts)});out geom;"


def _host(url: str) -> str:
    return urllib.parse.urlsplit(url).hostname or url


def _send(url: str, body: Optional[bytes] = None, context=None) -> bytes:
    """POST ``body`` to ``url``, or GET it when there is none."""
    headers = {"User-Agent": _USER_AGENT}
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=_TIMEOUT, context=context) as resp:
        return resp.read()


def _certificate_failed(exc: BaseException) -> bool:
    import ssl
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, ssl.SSLCertVerificationError) or isinstance(
        exc, ssl.SSLCertVerificationError)


#: Mozilla's certificates (certifi, shipped with the app), once they have
#: worked where the computer's own did not; None until then.
_mozilla: dict = {"context": None}


def _mozilla_context():
    """An SSL context over certifi's list, or None without certifi.

    Windows fills its store of root certificates on demand, as a browser or a
    Windows program first needs each one, and Python reads only what is in the
    store already; ``ssl_bootstrap`` steps in only when the store is empty. So
    a server whose root nothing on the computer has needed yet fails here while
    the browser opens it. A second opinion from Mozilla's list is still a
    checked certificate, and it is asked only after the computer's said no, so
    antivirus or a work network that installs its own root keeps working."""
    try:
        import ssl
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 — no certifi: the first answer stands
        return None


def _unanswered(url: str, exc: BaseException) -> Unanswered:
    """What kind of failure ``exc`` is, for one server."""
    import socket
    host = _host(url)
    if isinstance(exc, urllib.error.HTTPError):
        kind = BUSY if exc.code in (429, 502, 503, 504) else REFUSED
        return Unanswered(host, kind, f"HTTP {exc.code}")
    if _certificate_failed(exc):
        return Unanswered(host, CERTIFICATE, str(getattr(exc, "reason", exc)))
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return Unanswered(host, SLOW, f"no answer in {_TIMEOUT:.0f} s")
    # An SSLError's reason is a word ("UNEXPECTED_EOF_WHILE_READING"): name
    # the exception, not the str.
    named = exc if isinstance(reason, str) else reason
    return Unanswered(host, UNREACHABLE, f"{type(named).__name__}: {reason}")


def _read_answer(url: str, raw: bytes):
    """The parsed answer, or an :class:`Unanswered` for one that is not one."""
    host = _host(url)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return Unanswered(host, GARBLED, raw[:120].decode("utf-8", "replace"))
    if not isinstance(data, dict) or "elements" not in data:
        return Unanswered(host, GARBLED, "no elements in the answer")
    remark = str(data.get("remark") or "")
    if "runtime error" in remark.lower():
        # Out of time or memory: what came back is part of the answer, and a
        # part read as the whole is the "Found 0 buildings" lie again (V2.13).
        return Unanswered(host, BUSY, remark[:200])
    return data


def fetch_bytes(url: str, body: Optional[bytes] = None):
    """GET ``url`` (or POST ``body`` to it): the raw answer, or an
    :class:`Unanswered` saying what went wrong. A certificate the computer's
    store cannot check is checked against certifi's list before it counts as
    a failure (:func:`_mozilla_context`). Shared with ``vector_tiles``."""
    context = _mozilla["context"]
    try:
        return _send(url, body, context)
    except Exception as exc:  # noqa: BLE001 — classified, the caller moves on
        second = _mozilla_context() if (
            context is None and _certificate_failed(exc)) else None
        if second is None:
            return _unanswered(url, exc)
        try:
            raw = _send(url, body, second)
        except Exception as exc2:  # noqa: BLE001
            return _unanswered(url, exc2)
        _mozilla["context"] = second
        log.warning("%s's certificate checked against certifi's list; the "
                    "computer's own store could not (%s)",
                    _host(url), getattr(exc, "reason", exc))
        return raw


def _post_overpass(query: str, url: str = _OVERPASS_URL):
    """POST an Overpass QL query to one server: the parsed answer, or an
    :class:`Unanswered` saying what went wrong (V3.37; it was ``None`` for
    every failure, recorded nowhere)."""
    raw = fetch_bytes(url, b"data=" + urllib.parse.quote(query).encode("utf-8"))
    if isinstance(raw, Unanswered):
        return raw
    answer = _read_answer(url, raw)
    if (isinstance(answer, Unanswered) and "[maxsize:" in query
            and "out of memory" in answer.detail.lower()):
        # The memory a yard's query declares was not enough after all: ask
        # once more with the server's own default rather than fail on it.
        log.warning("Overpass %s: out of memory at the yard's maxsize; "
                    "asking again without it", answer.host)
        return _post_overpass(re.sub(r"\[maxsize:\d+\]", "", query), url)
    return answer


def _fetch_overpass(query: str, *, _post=None, _sleep=None,
                    why: Optional[list] = None,
                    on_miss=None) -> Optional[dict]:
    """Ask each server in turn until one answers: the main one, the others,
    then the main one again after a pause when it was only busy. Returns the
    parsed answer, or None when none did, which callers must report as a
    *failure*, never as an empty result (V2.13). ``why``, when given, collects
    an :class:`Unanswered` per failed attempt, and ``on_miss`` is told each
    one as it happens (the status line's "still asking"). ``_post``/``_sleep``
    are injectable for tests; a ``_post`` may return None for a failure."""
    import time
    post = _post or _post_overpass
    sleep = _sleep or time.sleep
    misses = why if why is not None else []

    def ask(url):
        got = post(query, url)
        if isinstance(got, dict):
            return got
        miss = (got if isinstance(got, Unanswered)
                else Unanswered(_host(url), UNREACHABLE, "no answer"))
        misses.append(miss)
        # Busy, slow and offline are routine; the rest is news (src/log.py).
        routine = miss.kind in (BUSY, SLOW, UNREACHABLE)
        log.log(logging.INFO if routine else logging.WARNING,
                "Overpass %s: %s (%s)", miss.host, miss.kind, miss.detail)
        if on_miss is not None:
            on_miss(miss)
        return None

    start = len(misses)
    for url in _OVERPASS_URLS:
        data = ask(url)
        if data is not None:
            return data
    if misses[start].kind == BUSY:
        sleep(_BUSY_PAUSE_S)    # etiquette: a pause before asking it again
        data = ask(_OVERPASS_URLS[0])
        if data is not None:
            return data
    log.warning("Overpass: no server answered (%s)", "; ".join(
        f"{m.host} {m.kind}" for m in misses[start:]))
    return None


#: The sentence for each kind: (what happened, what to do).
_SAID = {
    BUSY: ("its servers are busy", "Try again in a minute."),
    SLOW: ("it took too long", "Try again in a minute."),
    REFUSED: ("it refused the request ({detail})", ""),
    CERTIFICATE: ("its secure connection could not be checked (a wrong "
                  "clock, antivirus or a network that inspects connections "
                  "can do this)", ""),
    GARBLED: ("its answer could not be read", "Try again in a minute."),
    UNREACHABLE: ("it could not be reached", "Is the computer online?"),
}


#: One server's miss, said while the others are asked.
_SHORT = {BUSY: "is busy", SLOW: "is slow to answer",
          REFUSED: "refused the request",
          CERTIFICATE: "has a certificate that could not be checked",
          GARBLED: "sent an answer that could not be read",
          UNREACHABLE: "could not be reached"}


def trying_words(miss: Unanswered) -> str:
    """The status line while a fetch moves on: a slow server costs 30 s, and
    four of them two minutes, which reads as hung unless something says so."""
    return (f"Still asking OpenStreetMap: {miss.host} "
            f"{_SHORT.get(miss.kind, 'did not answer')}, so another server "
            "is being tried…")


#: What a server said, in a word or two, for :func:`server_words`.
_BRIEF = {SLOW: "too slow", CERTIFICATE: "certificate not checked",
          GARBLED: "unreadable answer", UNREACHABLE: "not reached"}


def server_words(why) -> str:
    """"overpass-api.de HTTP 429 · overpass.private.coffee not reached": each
    server's answer in the order asked. Shown at the end of a failure, so a
    screenshot of one says what each server said; the owner's two reports
    of V3.37 could not, and the log is a file nobody opens."""
    bits = []
    for m in why or []:
        if m.detail.startswith("HTTP "):
            said = m.detail
        elif m.kind == BUSY:
            said = ("out of memory" if "memory" in m.detail.lower()
                    else "cut its answer short")
        else:
            said = _BRIEF.get(m.kind, m.kind)
        bits.append(f"{m.host} {said}")
    return " · ".join(bits)


def failure_words(why, lost: str = "nothing was imported") -> str:
    """One sentence for a fetch that failed: the worst news among ``why``
    (the :class:`Unanswered` a fetch collected) in plain words, what was lost,
    and what to do, then what each server said. "didn't answer" stays its
    first words, whatever the kind: it is how a person tells a failure from an
    empty answer."""
    misses = list(why or [])
    kind = next((k for k in _KINDS if any(m.kind == k for m in misses)),
                UNREACHABLE if misses else None)
    if kind is None:
        return (f"OpenStreetMap didn't answer, so {lost}. "
                "Try again in a minute.")
    said, todo = _SAID[kind]
    detail = next((m.detail for m in misses if m.kind == kind), "")
    return " ".join(filter(None, (
        f"OpenStreetMap didn't answer: {said.format(detail=detail)}, "
        f"so {lost}.", todo, f"({server_words(misses)})")))


def _parse_height(tags: dict, default: float) -> float:
    """Building/tree height from OSM tags: explicit ``height`` (metres) wins,
    else ``building:levels`` × storey height, else the default."""
    h = tags.get("height")
    if h:
        try:
            return max(0.5, float(str(h).split()[0]))   # "12 m" → 12
        except (ValueError, IndexError):
            pass
    levels = tags.get("building:levels")
    if levels:
        try:
            return max(0.5, float(levels) * _STOREY_HEIGHT_M)
        except ValueError:
            pass
    return default


def _ring_lnglat(geometry: list) -> Optional[list]:
    """Cleaned, **closed** ring of ``[lng, lat]`` pairs (GeoJSON order) from an
    Overpass ``geom`` way (a list of ``{"lat","lon"}``). ``None`` for a
    degenerate ring (fewer than 3 distinct vertices). The ring is what lets the
    shapely shadow path cast the building's true footprint."""
    pts = [[float(g["lon"]), float(g["lat"])] for g in geometry
           if "lat" in g and "lon" in g]
    # Distinct vertices, ignoring a closing duplicate.
    core = pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts
    if len(core) < 3:
        return None
    ring = list(core)
    ring.append(ring[0])            # close the ring
    return ring


def _line_lnglat(geometry: list) -> list:
    """Open polyline of ``[lng, lat]`` pairs from an Overpass ``geom`` way.

    Separate from :func:`_ring_lnglat` because that one is built for building
    footprints: it demands three distinct vertices and **closes** the ring. Both
    are wrong for a street — a two-node way is a perfectly good road segment and
    would be dropped, and closing the line invents a segment back to the start
    that the frontage would then measure a distance to.
    """
    return [[float(g["lon"]), float(g["lat"])] for g in geometry or []
            if "lat" in g and "lon" in g]


def ring_centroid(ring_lnglat: list) -> Optional[tuple]:
    """``(lat, lng)`` centroid of a ring of ``[lng, lat]`` pairs, or ``None``
    for a degenerate ring (<3 distinct vertices)."""
    pts = [(p[1], p[0]) for p in (ring_lnglat or []) if len(p) >= 2]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]              # drop closing duplicate
    if len(pts) < 3:
        return None
    clat = sum(p[0] for p in pts) / len(pts)
    clng = sum(p[1] for p in pts) / len(pts)
    return (clat, clng)


def ring_radius_m(ring_lnglat: list, center: Optional[tuple] = None) -> float:
    """Enclosing radius in metres: the max distance from ``center`` (``(lat,
    lng)``; defaults to the ring centroid) to any vertex of ``ring_lnglat`` (a
    ring of ``[lng, lat]`` pairs). ``0.0`` for an empty ring.

    Shared by the OSM import, the drawn-shape, and the footprint-edit paths so
    they all size a footprint's ``canopy_radius_m`` identically — covering the
    structure for keep-out and the circle fallback."""
    pts = [(p[1], p[0]) for p in (ring_lnglat or []) if len(p) >= 2]
    if not pts:
        return 0.0
    if center is None:
        # Drop a closing-duplicate vertex so it doesn't skew the centroid
        # (mirrors ring_centroid); the max scan below still covers every vertex.
        core = pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts
        clat = sum(p[0] for p in core) / len(core)
        clng = sum(p[1] for p in core) / len(core)
    else:
        clat, clng = center
    cos_lat = math.cos(clat * math.pi / 180) or 1e-9
    radius = 0.0
    for la, ln in pts:
        dx = (ln - clng) * 111320.0 * cos_lat
        dy = (la - clat) * 111320.0
        radius = max(radius, math.hypot(dx, dy))
    return radius


def parse_elements(data: Optional[dict]) -> list[dict]:
    """Turn an Overpass JSON response into existing-feature dicts. Pure and
    fixture-testable (no network)."""
    out: list[dict] = []
    for el in (data or {}).get("elements", []) or []:
        tags = el.get("tags", {}) or {}
        etype = el.get("type")
        if etype == "node" and tags.get("natural") == "tree":
            lat, lng = el.get("lat"), el.get("lon")
            if lat is None or lng is None:
                continue
            crown = tags.get("diameter_crown")
            radius = _DEFAULT_TREE_RADIUS_M
            if crown:
                try:
                    radius = max(0.5, float(str(crown).split()[0]) / 2.0)
                except (ValueError, IndexError):
                    pass
            out.append({"kind": "tree", "lat": float(lat), "lng": float(lng),
                        "height_m": _parse_height(tags, _DEFAULT_TREE_HEIGHT_M),
                        "radius_m": radius})
        elif etype == "way" and tags.get("highway") in ROAD_HIGHWAYS:
            line = _line_lnglat(el.get("geometry", []) or [])
            if len(line) < 2:
                continue
            out.append({"kind": "road", "line": line,
                        "name": tags.get("name") or "",
                        "highway": tags.get("highway") or ""})
        elif etype == "way" and tags.get("building"):
            ring = _ring_lnglat(el.get("geometry", []) or [])
            if ring is None:
                continue
            c = ring_centroid(ring)
            if c is None:
                continue
            clat, clng = c
            out.append({"kind": "building", "lat": clat, "lng": clng,
                        "height_m": _parse_height(
                            tags, _DEFAULT_BUILDING_HEIGHT_M),
                        "radius_m": max(1.0, ring_radius_m(ring, (clat, clng))),
                        "footprint": ring})
        elif etype == "relation" and tags.get("building"):
            # Multipolygon building (V2.13): each *closed* outer-role member
            # ring becomes a footprint (tags/height come from the relation).
            # Outers split across several unclosed way fragments would need
            # arc-stitching — skipped rather than force-closed into garbage.
            for m in el.get("members", []) or []:
                if m.get("type") != "way" or m.get("role") not in ("outer", ""):
                    continue
                geometry = m.get("geometry", []) or []
                if (len(geometry) < 4
                        or geometry[0].get("lat") != geometry[-1].get("lat")
                        or geometry[0].get("lon") != geometry[-1].get("lon")):
                    continue                     # unclosed fragment — skip
                ring = _ring_lnglat(geometry)
                if ring is None:
                    continue
                c = ring_centroid(ring)
                if c is None:
                    continue
                clat, clng = c
                out.append({"kind": "building", "lat": clat, "lng": clng,
                            "height_m": _parse_height(
                                tags, _DEFAULT_BUILDING_HEIGHT_M),
                            "radius_m": max(1.0, ring_radius_m(
                                ring, (clat, clng))),
                            "footprint": ring})
    return out


def fetch_roads(bbox: dict) -> Optional[list]:
    """Street centrelines in ``bbox``, or ``None`` when the fetch failed.

    Added V2.58 so the frontage can be *measured* rather than assumed. Same
    None-on-failure contract as :func:`fetch_existing_features`, and for the
    same reason: a failed request rendered as "no roads" would silently send
    the caller back to the south-edge guess while looking like an answer.
    """
    data = _fetch_overpass(_query(bbox, False, False, include_roads=True))
    if data is None:
        return None
    return [f for f in parse_elements(data) if f["kind"] == "road"]


def fetch_existing_features(bbox: dict, *, trees: bool = True,
                            buildings: bool = True,
                            roads: bool = True,
                            why: Optional[list] = None,
                            on_miss=None) -> Optional[dict]:
    """Fetch existing trees and/or buildings in ``bbox`` from OSM. Returns
    ``{"trees": [...], "buildings": [...]}``, or **None when the network
    fetch failed** (timeout / rate-limit / server busy, on every server).
    A None must be reported as a failure — for years a failed request was
    silently rendered as "Found 0 buildings", which is a lie (V2.13).
    ``why`` collects what each server said (:func:`failure_words`) and
    ``on_miss`` hears each as it happens."""
    if not (trees or buildings or roads):
        return {"trees": [], "buildings": [], "roads": []}
    data = _fetch_overpass(_query(bbox, trees, buildings, roads), why=why,
                           on_miss=on_miss)
    if data is None:
        return None
    feats = parse_elements(data)
    return {
        "trees": [f for f in feats if f["kind"] == "tree"],
        "buildings": [f for f in feats if f["kind"] == "building"],
        "roads": [f for f in feats if f["kind"] == "road"],
    }


#: The status line while the tiles are read instead.
TILES_WORDS = ("OpenStreetMap's query servers didn't answer: reading the "
               "buildings off its map tiles instead…")
#: Said after buildings that came off the tiles.
TILES_NOTE = ("The buildings came off OpenStreetMap's map tiles, as its query "
              "servers didn't answer; mapped trees and streets need those.")


def fetch_with_fallback(bbox: dict, *, why: Optional[list] = None,
                        on_miss=None, on_tiles=None) -> Optional[dict]:
    """Buildings, trees and streets from Overpass; when no Overpass server
    answers, the buildings alone off OpenStreetMap's map tiles
    (``vector_tiles``, V3.37), marked ``"from_tiles": True``. ``None`` when
    neither answered. ``on_tiles`` is told before the tiles are asked."""
    misses = why if why is not None else []
    res = fetch_existing_features(bbox, why=misses, on_miss=on_miss)
    if res is not None:
        return res
    if on_tiles is not None:
        on_tiles()
    from src import vector_tiles
    buildings = vector_tiles.fetch_buildings(bbox, why=misses)
    if buildings is None:
        return None
    return {"buildings": buildings, "trees": [], "roads": [],
            "from_tiles": True}


def fetch_buildings_or_none(bbox: dict,
                            why: Optional[list] = None) -> Optional[list]:
    """Buildings only, or None when no server answered: for the bulk
    downloader, which must not store a part that failed as an empty one
    (V3.37). No roads: until V3.37 every part of a bulk download also fetched
    every street in it, a heavier query for a busy server to turn away."""
    res = fetch_existing_features(bbox, trees=False, buildings=True,
                                  roads=False, why=why)
    return None if res is None else res["buildings"]


def fetch_buildings(bbox: dict) -> list[dict]:
    """Buildings only, with the legacy []-on-failure contract."""
    return fetch_buildings_or_none(bbox) or []


def fetch_trees(bbox: dict) -> list[dict]:
    res = fetch_existing_features(bbox, trees=True, buildings=False,
                                  roads=False)
    return res["trees"] if res else []


def _too_close(lat, lng, existing, min_m=2.0) -> bool:
    """True when an (lat,lng) is within ``min_m`` of an already-present feature
    point — used to dedupe OSM imports against hand-marked features."""
    cos_lat = math.cos(lat * math.pi / 180) or 1e-9
    for elat, elng in existing:
        dx = (lng - elng) * 111320.0 * cos_lat
        dy = (lat - elat) * 111320.0
        if dx * dx + dy * dy < min_m * min_m:
            return True
    return False


def _osm_building_feature(item: dict) -> Optional[dict]:
    """Build a shade-casting ``canopy_footprint`` Polygon feature from an OSM
    building dict carrying a ``footprint`` ring. Mirrors
    ``footprint_extract.add_extracted_footprints`` so the building renders as a
    true outline AND casts a true-shape shadow, while ``canopy_radius_m`` + a
    stored centroid keep the keep-out (``src/exclusion.py``) and circle fallback
    working. ``None`` when the footprint is missing/degenerate (caller then
    falls back to a Point ``existing_building``).

    The ``shape_id`` is a fresh uuid so it can never collide with an existing or
    re-imported footprint (a count/time-based scheme could repeat after a
    building is deleted, or for two imports in the same millisecond)."""
    import uuid
    footprint = item.get("footprint")
    if not footprint or len(footprint) < 4:
        return None
    coords = [[float(p[0]), float(p[1])] for p in footprint]
    if coords[0] != coords[-1]:
        coords.append(coords[0])            # close the ring
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [coords]},
        "properties": {
            "element_type": "canopy_footprint",
            "shape_id": f"shape_osm_{uuid.uuid4().hex[:12]}",
            "label": "Building (OSM)",
            "shape_type": "Building (OSM)",
            "fill_color": "#8d6e63",
            "stroke_color": "#5d4037",
            "fill_opacity": 0.3,
            "dash_array": "",
            "height_m": float(item.get("height_m") or _DEFAULT_BUILDING_HEIGHT_M),
            "cast_shade": True,
            # Centroid + radius let keepout_circles / the circle fallback treat
            # the polygon like the old point building without re-deriving them.
            "canopy_radius_m": float(item.get("radius_m") or 4.0),
            "lat": float(item["lat"]), "lng": float(item["lng"]),
            "source": "osm",
        },
    }


def add_features_to_project(features: list[dict], project_dict: dict) -> int:
    """Append OSM-derived existing trees/buildings to a project's feature list,
    skipping any that duplicate a feature already present. Returns the number
    added. Pure (mutates the dict in place); the GUI calls this on the main
    thread after the off-thread fetch.

    Trees become ``existing_tree`` Points (canopy circle). Buildings with a true
    footprint become shade-casting ``canopy_footprint`` Polygons (V1.58) so they
    render as real outlines and cast true-shape shadows; a building without a
    usable ring falls back to the legacy ``existing_building`` Point."""
    feats = project_dict.setdefault("features", [])
    existing_pts = []
    for f in feats:
        props = f.get("properties") or {}
        et = props.get("element_type")
        geom = f.get("geometry") or {}
        if et in ("existing_tree", "existing_building"):
            c = geom.get("coordinates") or []
            if len(c) >= 2:
                existing_pts.append((c[1], c[0]))
        elif et == "canopy_footprint" and props.get("source") == "osm":
            la, ln = props.get("lat"), props.get("lng")
            if la is None or ln is None:
                ring = (geom.get("coordinates") or [None])[0]
                cc = ring_centroid(ring) if ring else None
                la, ln = cc if cc else (None, None)
            if la is not None and ln is not None:
                existing_pts.append((la, ln))
    added = 0
    for item in features or []:
        lat, lng = item.get("lat"), item.get("lng")
        # ``dedupe_m`` lets a source scale the duplicate radius with the
        # feature it detected (tree_detect: a crown centred inside an
        # already-known crown is the same tree). Default stays 2 m.
        if lat is None or lng is None or _too_close(
                lat, lng, existing_pts,
                min_m=float(item.get("dedupe_m") or 2.0)):
            continue
        if item.get("kind") == "building":
            feat = _osm_building_feature(item)
            if feat is not None:
                feats.append(feat)
                existing_pts.append((lat, lng))
                added += 1
                continue
        # Tree, or a building with no usable footprint → legacy Point feature.
        # Items may override label/source (e.g. tree_detect's imagery-derived
        # trees, V2.26) and declare foliage; absent keys keep OSM semantics.
        etype = ("existing_tree" if item.get("kind") == "tree"
                 else "existing_building")
        props = {
            "element_type": etype,
            "height_m": float(item.get("height_m") or (
                _DEFAULT_TREE_HEIGHT_M if etype == "existing_tree"
                else _DEFAULT_BUILDING_HEIGHT_M)),
            "canopy_radius_m": float(item.get("radius_m") or (
                _DEFAULT_TREE_RADIUS_M if etype == "existing_tree"
                else 4.0)),
            "label": item.get("label") or (
                "Tree (OSM)" if etype == "existing_tree"
                else "Building (OSM)"),
            "struct_id": etype,
            "source": item.get("source") or "osm",
        }
        if etype == "existing_tree" and item.get("foliage"):
            props["tree_foliage"] = item["foliage"]
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": props,
        })
        existing_pts.append((lat, lng))
        added += 1
    return added


# ── Qt worker thread (optional; mirrors shade.ShadeWorker) ───────────────────
# Defined only when PyQt6 is importable so the pure fetch above stays usable
# headless. The GUI runs fetch_existing_features off the UI thread because it
# does a network Overpass query.
try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _HAVE_QT = True
except ImportError:
    _HAVE_QT = False

if _HAVE_QT:
    class OSMWorker(QObject):
        """Fetch existing OSM features for a bbox off the UI thread.

            worker = OSMWorker(bbox)
            worker.ready.connect(on_ready)   # the fetch result, or a failure
        """

        ready = pyqtSignal(object)
        finished = pyqtSignal()
        #: "Still asking…" while it moves between servers (V3.37).
        progress = pyqtSignal(str)

        def __init__(self, bbox, parent=None):
            super().__init__(parent)
            self._bbox = bbox

        def run(self):
            why: list = []
            try:
                res = fetch_with_fallback(
                    self._bbox, why=why,
                    on_miss=lambda m: self.progress.emit(trying_words(m)),
                    on_tiles=lambda: self.progress.emit(TILES_WORDS))
            except Exception:  # noqa: BLE001 — never crash the worker thread
                log.exception("Overpass fetch raised")
                res = None
            # A failure carries what each server said (V3.37), for
            # import_osm_result to put into words.
            self.ready.emit(res if res is not None else {"failed": why})
            self.finished.emit()


def pad_bbox(bbox: dict, metres: float) -> dict:
    """Grow a bbox by ``metres`` on every side. Load-bearing for the import
    (V2.13): Overpass returns a building way only when at least one of its
    *corner nodes* falls inside the box, so a boundary drawn tight over a big
    building can contain the building but none of its corners — the margin
    catches them (the full footprint comes back via ``out geom`` regardless)."""
    clat = (bbox["south"] + bbox["north"]) / 2.0
    dlat = metres / 111320.0
    dlng = metres / (111320.0 * max(1e-9, math.cos(clat * math.pi / 180)))
    return {"south": bbox["south"] - dlat, "north": bbox["north"] + dlat,
            "west": bbox["west"] - dlng, "east": bbox["east"] + dlng}


def bbox_with_area_note(boundary, site_config: dict,
                        radius_m: float = 60.0, pad_m: float = 30.0):
    """``(bbox, note)``: the search bbox plus a human description of what area
    it covers, so the import status can say exactly what was searched.
    Boundary path = the polygon's bounding box grown by ``pad_m``; fallback =
    a square of half-extent ``radius_m`` around the property pin. ``(None,
    "")`` when neither exists. Pure geometry, shared by the OSM + footprint
    import flows."""
    if boundary and len(boundary) >= 3:
        lats = [p[0] for p in boundary]
        lngs = [p[1] for p in boundary]
        raw = {"north": max(lats), "south": min(lats),
               "east": max(lngs), "west": min(lngs)}
        return (pad_bbox(raw, pad_m) if pad_m > 0 else raw,
                f"your boundary + {pad_m:.0f} m margin")
    lat, lng = site_config.get("latitude"), site_config.get("longitude")
    if lat is None or lng is None:
        return None, ""
    cos_lat = math.cos(lat * math.pi / 180) or 1e-9
    dlat = radius_m / 111320.0
    dlng = radius_m / (111320.0 * cos_lat)
    return ({"north": lat + dlat, "south": lat - dlat,
             "east": lng + dlng, "west": lng - dlng},
            f"≈{radius_m:.0f} m around the pin — draw a property boundary "
            "to control the area")


def bbox_from_boundary_or_pin(boundary, site_config: dict,
                              radius_m: float = 60.0):
    """Back-compat wrapper over :func:`bbox_with_area_note` (bbox only)."""
    return bbox_with_area_note(boundary, site_config, radius_m=radius_m)[0]


# ── Boundary-precise filtering (V2.13) ───────────────────────────────────────
# The Overpass query has to be a bbox, but the user drew a *polygon* — and a
# padded bbox happily scoops up the neighbours' whole block corner. These
# pure-Python helpers (no shapely; it's an optional dependency) clip the
# results back to the drawn boundary plus a user-controlled neighbour margin.

def _point_in_polygon(lat: float, lng: float, poly: list) -> bool:
    """Ray-cast point-in-polygon; ``poly`` = [(lat, lng), …] (open or closed)."""
    n = len(poly)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        yi, xi = poly[i][0], poly[i][1]
        yj, xj = poly[j][0], poly[j][1]
        if (yi > lat) != (yj > lat):
            x_cross = xj + (lat - yj) / (yi - yj) * (xi - xj)
            if lng < x_cross:
                inside = not inside
        j = i
    return inside


def _dist_to_polygon_m(lat: float, lng: float, poly: list) -> float:
    """Min distance (metres, equirectangular) from a point to the polygon's
    edges. Zero-ish for points on the boundary; combine with
    :func:`_point_in_polygon` for interior points."""
    if not poly:
        return float("inf")
    cos_lat = math.cos(lat * math.pi / 180) or 1e-9

    def _xy(p):
        return ((p[1] - lng) * 111320.0 * cos_lat, (p[0] - lat) * 111320.0)

    best = float("inf")
    n = len(poly)
    for i in range(n):
        ax, ay = _xy(poly[i])
        bx, by = _xy(poly[(i + 1) % n])
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        t = 0.0 if seg2 <= 1e-12 else max(
            0.0, min(1.0, -(ax * dx + ay * dy) / seg2))
        px, py = ax + t * dx, ay + t * dy
        best = min(best, math.hypot(px, py))
    return best


def _feature_near_boundary(item: dict, boundary: list, margin_m: float) -> bool:
    """True when the feature touches the boundary polygon or comes within
    ``margin_m`` of it: centroid or any footprint vertex inside / near."""
    pts = [(item.get("lat"), item.get("lng"))]
    for p in item.get("footprint") or []:
        pts.append((p[1], p[0]))                 # footprint is [lng, lat]
    for la, ln in pts:
        if la is None or ln is None:
            continue
        if _point_in_polygon(la, ln, boundary):
            return True
        if margin_m > 0 and _dist_to_polygon_m(la, ln, boundary) <= margin_m:
            return True
    return False


def filter_to_boundary(feats: list, boundary, margin_m: float = 30.0):
    """Split fetched features into (kept, n_inside, n_neighbours) against the
    drawn boundary polygon: inside = centroid inside; neighbour = within
    ``margin_m`` of the edge (their shade still falls on the site). With no
    usable boundary everything is kept (bbox semantics, the pin fallback)."""
    if not boundary or len(boundary) < 3:
        return list(feats or []), len(feats or []), 0
    kept, n_inside, n_neigh = [], 0, 0
    for item in feats or []:
        la, ln = item.get("lat"), item.get("lng")
        centroid_inside = (la is not None and ln is not None
                           and _point_in_polygon(la, ln, boundary))
        if centroid_inside:
            kept.append(item)
            n_inside += 1
        elif _feature_near_boundary(item, boundary, margin_m):
            kept.append(item)
            n_neigh += 1
    return kept, n_inside, n_neigh


def import_osm_result(res: Optional[dict], project_dict: dict, *,
                      boundary=None, margin_m: float = 30.0,
                      area_note: str = "") -> dict:
    """Filter a fetch result to the boundary, add to the project, and compose
    the status message — the whole import tail in one pure, testable call
    (the map controller sits at its line ceiling). Returns
    ``{"added": int, "kept": int, "found": int, "message": str}``;
    a failed fetch (``None``, or the worker's ``{"failed": [Unanswered]}``)
    produces added=0, ``"failed"`` (what each server said) and the honest
    message, which says why since V3.37."""
    if res is None or "failed" in res:
        why = list((res or {}).get("failed") or [])
        return {"added": 0, "kept": 0, "found": 0, "failed": why,
                "message": failure_words(why)}
    feats = list(res.get("buildings", [])) + list(res.get("trees", []))
    kept, n_inside, n_neigh = filter_to_boundary(feats, boundary, margin_m)
    added = add_features_to_project(kept, project_dict)
    from_tiles = bool(res.get("from_tiles"))
    # Streets (V2.58). NOT boundary-filtered and NOT counted in `added`: a road
    # is useful precisely because it is *outside* the property, and counting it
    # as an imported feature would inflate "found 12 buildings" with things the
    # user never asked to place. Stored so src.frontage can measure which edge
    # faces the street instead of assuming south. The map tiles' fallback
    # brings none, which must not wipe the ones an earlier import stored.
    try:
        from src.frontage import store_roads
        if not from_tiles:
            store_roads(project_dict, res.get("roads") or [])
    except Exception:      # noqa: BLE001 — never fail an import over this
        pass
    msg = f"Found {len(feats)} nearby; "
    if boundary and len(boundary) >= 3:
        msg += (f"kept {len(kept)} ({n_inside} inside your boundary + "
                f"{n_neigh} neighbour{'s' if n_neigh != 1 else ''} within "
                f"{margin_m:.0f} m); ")
    elif area_note:
        msg += f"searched {area_note}; "
    msg += f"added {added} new."
    if added or len(kept):
        msg += (" Click an imported outline and press Delete to drop any "
                "you don't want.")
    elif not feats:
        msg += (" OSM knows no buildings/trees here — anything missing can "
                "be drawn by hand below.")
    if from_tiles:
        msg += (" " + TILES_NOTE)
    return {"added": added, "kept": len(kept), "found": len(feats),
            "from_tiles": from_tiles, "message": msg}
