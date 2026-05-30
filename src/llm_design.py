"""
llm_design.py — Prompt-driven design generation via a local LLM.

This is the "give it a sentence, get a starting design" path. It talks to
any OpenAI-compatible chat-completions endpoint — by default a local
`Ollama <https://ollama.com>`_ server at ``http://localhost:11434/v1`` —
so it runs fully offline with no API key and no extra dependencies (stdlib
``urllib`` only, matching :mod:`src.property_data` / :mod:`src.terrain`).

Division of labour: the LLM does the *ecological selection* it is good at
(which species, which communities, which habitat structures suit the
brief) and returns a compact JSON spec. Python does the *geometry* —
resolving names/queries to catalogue ids and laying everything out on the
map — so coordinates are always valid regardless of how good the model is
at arithmetic. The result is a normal :class:`~src.permadesign_api.Project`
the user can open in the GUI and refine by hand.

Nothing here imports Qt; it drives the headless facade in
:mod:`src.permadesign_api`.
"""

from __future__ import annotations

import json
import math
import os
import re
import urllib.error
import urllib.request
from typing import Any, Optional

from src.errors import LLMError

DEFAULT_ENDPOINT = "http://localhost:11434/v1"
DEFAULT_MODEL = "llama3.2"
_USER_AGENT = "PermaDesign/1.0 (https://github.com/yarrowyarrowyarrow/permadesign)"
_TIMEOUT = 120.0
# Grid cell size (metres) between placed items in the generated layout. Wide
# enough that adjacent communities don't overlap; the user fine-tunes after.
_SPACING_M = 6.0

# Plant search filters we forward to query_plants. Anything else the model
# emits is dropped so a hallucinated filter name can't crash search_plants.
_ALLOWED_FILTERS = {
    "query", "plant_type", "sun_req", "water_needs", "zone",
    "native_only", "edible_only", "perennial_only", "pollinator_only",
    "host_plant_only", "keystone_only", "bird_food_only", "ab_ecoregion",
    "max_unit_price", "common_only",
    "host_for_fauna_id", "supports_fauna_id", "supports_specialist",
    "soil_ph", "moisture",
}

_SYSTEM_PROMPT = """\
You are a landscape design assistant for PermaDesign, a tool for native-plant
habitat gardens in Alberta and the Canadian prairies. Given a design brief,
respond with ONLY a single JSON object (no prose, no markdown fences) of this
shape:

{
  "summary": "one sentence describing the design",
  "plants": [
    {"query": "wild bergamot", "quantity": 3},
    {"query": "native pollinator shrub", "quantity": 2}
  ],
  "communities": [
    {"query": "pollinator"}
  ],
  "structures": [
    {"structure_id": "bee_hotel"}
  ]
}

Rules:
- "plants[].query" is a free-text search run against the plant database;
  use plain plant names or descriptive terms. "quantity" is a positive
  integer (default 1). Prefer names from the PLANT PALETTE below — those are
  real, in-stock, site-appropriate species.
- "communities[].query" must loosely match one of the AVAILABLE COMMUNITIES
  listed below. Choose communities whose description suits the SITE
  CONDITIONS (e.g. a riparian/willow community for wet ground, a mixedgrass
  or aromatic community for a dry sunny site, a boreal/shade community for
  shade).
- "structures[].structure_id" must be one of the AVAILABLE STRUCTURE IDS
  listed below. Match structures to the site: pond / swale / rain_garden for
  low or wet ground, bee_hotel / native_bee_log in sun, brush_pile / snag for
  cover.
- MATCH PLANTS TO THE SITE CONDITIONS: shade-tolerant plants for shaded
  spots, moisture-loving / aquatic plants for wet or low ground, drought-
  tolerant plants for dry slopes, and species whose hardiness and ecoregion
  suit the site.
- Favour native, pollinator-supporting, prairie-hardy species.
- Include at least a few plants. Omit a section by giving an empty list.
"""


# ── HTTP (stdlib urllib, OpenAI-compatible POST) ─────────────────────────────

def _http_post_json(url: str, payload: dict, timeout: float) -> dict:
    """POST ``payload`` as JSON, return parsed JSON. Raises LLMError on any
    transport / decode failure (unlike the GET helpers elsewhere, generation
    must surface the failure rather than silently degrade)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": _USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise LLMError(
            f"could not reach LLM endpoint {url}: {getattr(exc, 'reason', exc)} "
            f"— is a local server (e.g. Ollama) running?"
        ) from exc
    except Exception as exc:  # noqa: BLE001 — any transport error is an LLMError
        raise LLMError(f"LLM request to {url} failed: {exc}") from exc
    try:
        return json.loads(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise LLMError(f"LLM endpoint returned non-JSON: {raw[:200]!r}") from exc


# ── Client ───────────────────────────────────────────────────────────────────

class LLMClient:
    """Thin OpenAI-compatible chat client.

    Resolution order for endpoint/model: explicit arg → ``PERMADESIGN_LLM_*``
    env var → ``~/.permadesign_config.json`` (``llm_endpoint`` / ``llm_model``)
    → built-in default (local Ollama).
    """

    def __init__(self, endpoint: Optional[str] = None,
                 model: Optional[str] = None, timeout: float = _TIMEOUT):
        cfg: dict = {}
        try:
            from src.settings import load_config
            cfg = load_config() or {}
        except Exception:  # noqa: BLE001 — config is best-effort
            cfg = {}
        self.endpoint = (
            endpoint or os.environ.get("PERMADESIGN_LLM_ENDPOINT")
            or cfg.get("llm_endpoint") or DEFAULT_ENDPOINT
        ).rstrip("/")
        self.model = (
            model or os.environ.get("PERMADESIGN_LLM_MODEL")
            or cfg.get("llm_model") or DEFAULT_MODEL
        )
        self.timeout = timeout

    def _completions_url(self) -> str:
        if self.endpoint.endswith("/chat/completions"):
            return self.endpoint
        return self.endpoint + "/chat/completions"

    def chat(self, messages: list[dict], *, temperature: float = 0.2) -> str:
        """Run one chat completion; return the assistant message text."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }
        data = _http_post_json(self._completions_url(), payload, self.timeout)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected LLM response shape: {data!r}") from exc

    def generate_spec(self, prompt: str, context: dict,
                      extra_hints: Optional[list] = None) -> dict:
        """Ask the model for a design spec and parse it into a dict.

        ``extra_hints`` (design-goal guidance) are appended to the brief."""
        content = self.chat(_build_messages(prompt, context, extra_hints))
        return _parse_spec_json(content)


def _fauna_digest(limit_per_taxon: int = 4) -> str:
    """A compact, prompt-friendly summary of native fauna the catalogue can
    support, grouped by taxon — grounds the model toward designing for real
    species (the plant_fauna junction, schema v20). Empty string on any error."""
    try:
        from src.db.fauna import list_fauna
        rows = list_fauna()
    except Exception:  # noqa: BLE001 — context enrichment is best-effort
        return ""
    by_taxon: dict[str, list] = {}
    for r in rows:
        nm = r.get("common_name") or r.get("scientific_name")
        if nm:
            by_taxon.setdefault(r.get("taxon", "other"), []).append(nm)
    label = {"lepidoptera": "butterflies/moths", "bird": "birds", "bee": "bees",
             "other_insect": "other beneficial insects", "mammal": "mammals"}
    parts = []
    for taxon, names in by_taxon.items():
        sample = ", ".join(names[:limit_per_taxon])
        if sample:
            parts.append(f"{label.get(taxon, taxon)}: {sample}")
    if not parts:
        return ""
    return ("NATIVE FAUNA the catalogue can support (favour plants that feed or "
            "host these): " + "; ".join(parts))


# ── Site-fit + catalogue context (V1.48) ─────────────────────────────────────

def _site_filters(site_config: Optional[dict]) -> dict:
    """Derive the baseline ``search_plants`` filters that bind a design to the
    measured site: hardiness zone, ecoregion, and soil pH. Empty dict when the
    site is unknown. These are applied *under* the model's own plant queries so
    even a vague request is constrained to site-fit species."""
    sc = site_config or {}
    out: dict = {}
    zone = sc.get("hardiness_zone")
    if isinstance(zone, (int, float)):
        out["zone"] = int(zone)
    eco = sc.get("ecoregion_key")
    if eco:
        out["ab_ecoregion"] = str(eco)
    ph = sc.get("soil_ph")
    if isinstance(ph, (int, float)):
        out["soil_ph"] = float(ph)
    return out


def _site_conditions_line(site_config: Optional[dict]) -> str:
    """A compact, human-readable SITE CONDITIONS summary for the prompt — every
    measured field we have, not just lat/lng/zone. Empty string when nothing
    beyond coordinates is known."""
    sc = site_config or {}
    bits: list[str] = []
    if sc.get("hardiness_zone") is not None:
        bits.append(f"hardiness zone {sc['hardiness_zone']}")
    if sc.get("ecoregion_label") or sc.get("ecoregion_key"):
        bits.append(f"ecoregion {sc.get('ecoregion_label') or sc['ecoregion_key']}")
    if isinstance(sc.get("gdd5_mean"), (int, float)):
        bits.append(f"GDD5 ~{sc['gdd5_mean']:.0f}")
    if isinstance(sc.get("frost_free_days"), (int, float)):
        bits.append(f"{sc['frost_free_days']:.0f} frost-free days")
    if isinstance(sc.get("annual_rainfall_mm"), (int, float)):
        bits.append(f"{sc['annual_rainfall_mm']:.0f} mm annual rain")
    if isinstance(sc.get("slope_pct"), (int, float)):
        asp = sc.get("aspect")
        bits.append(f"slope {sc['slope_pct']:.0f}%"
                    + (f" facing {asp}" if asp else ""))
    if isinstance(sc.get("soil_ph"), (int, float)):
        tex = sc.get("soil_texture")
        bits.append(f"soil pH {sc['soil_ph']:.1f}"
                    + (f" ({tex})" if tex else ""))
    return "SITE CONDITIONS: " + "; ".join(bits) + "." if bits else ""


def _plant_palette(query_plants, site_filters: dict,
                   limit_per_group: int = 8) -> str:
    """A compact, catalogue-real plant palette grouped by type, restricted to
    site-fit natives — grounds the model so it stops inventing names that get
    snapped to whatever search finds. Best-effort: empty string on any error."""
    try:
        rows = query_plants(native_only=True, **site_filters)
    except Exception:  # noqa: BLE001 — context enrichment is best-effort
        try:
            rows = query_plants(native_only=True)
        except Exception:  # noqa: BLE001
            return ""
    groups: dict[str, list[str]] = {}
    for r in rows:
        nm = r.get("common_name")
        if nm:
            groups.setdefault(r.get("plant_type", "other"), []).append(nm)
    order = ["tree", "shrub", "herb", "grass", "sedge", "rush",
             "groundcover", "vine", "root", "fern", "aquatic"]
    parts = []
    for ptype in order + [g for g in groups if g not in order]:
        names = groups.get(ptype)
        if names:
            parts.append(f"{ptype}: " + ", ".join(names[:limit_per_group]))
    if not parts:
        return ""
    return ("PLANT PALETTE (site-fit natives — prefer these):\n  "
            + "\n  ".join(parts))


def _community_digest(limit: int = 14) -> str:
    """Per-community one-liner: name — first sentence of description
    [key members]. Replaces the names-only list so the model can choose a
    community by scenario. Best-effort: empty string on any error."""
    try:
        from src.permadesign_api import list_polycultures
        from src.db.polycultures import get_polyculture_by_id
        comms = list_polycultures()
    except Exception:  # noqa: BLE001
        return ""
    parts = []
    for c in comms[:limit]:
        name = c.get("name")
        if not name:
            continue
        desc = (c.get("description") or "").strip()
        first = desc.split(". ")[0].strip().rstrip(".") if desc else ""
        members = []
        try:
            full = get_polyculture_by_id(c["id"]) if c.get("id") else None
            members = [m.get("common_name") for m in (full or {}).get("members", [])
                       if m.get("common_name")][:4]
        except Exception:  # noqa: BLE001
            members = []
        line = f"- {name}"
        if first:
            line += f" — {first}"
        if members:
            line += f" [members: {', '.join(members)}]"
        parts.append(line)
    if not parts:
        return ""
    return "AVAILABLE COMMUNITIES:\n" + "\n".join(parts)


def _structure_digest() -> str:
    """Per-structure siting hint: ``id (Name): <first sentence of
    description>``. Best-effort: empty string on any error."""
    try:
        from src.permadesign_api import list_structures
        structs = list_structures()
    except Exception:  # noqa: BLE001
        return ""
    parts = []
    for s in structs:
        sid = s.get("id")
        if not sid:
            continue
        name = s.get("name") or sid
        desc = (s.get("description") or "").strip()
        first = desc.split(". ")[0].strip() if desc else ""
        parts.append(f"- {sid} ({name})" + (f": {first}" if first else ""))
    if not parts:
        return ""
    return "AVAILABLE STRUCTURE IDS:\n" + "\n".join(parts)


def _build_messages(prompt: str, context: dict,
                    extra_hints: Optional[list] = None) -> list[dict]:
    lines = [_SYSTEM_PROMPT, ""]

    # Rich digests when present (V1.48); fall back to the bare name/id lists.
    comm = context.get("community_digest")
    if comm:
        lines.append(comm)
    else:
        names = context.get("community_names") or []
        lines.append("AVAILABLE COMMUNITIES: " + ", ".join(names) if names
                     else "AVAILABLE COMMUNITIES: (none)")

    struct = context.get("structure_digest")
    if struct:
        lines.append(struct)
    else:
        sids = context.get("structure_ids") or []
        lines.append("AVAILABLE STRUCTURE IDS: " + ", ".join(str(s) for s in sids)
                     if sids else "AVAILABLE STRUCTURE IDS: (none)")

    site = context.get("site") or {}
    cond = context.get("site_conditions") or _site_conditions_line(site)
    if cond:
        lines.append(cond)
    if site.get("latitude") is not None and site.get("longitude") is not None:
        lines.append(f"SITE LOCATION: lat {site['latitude']}, "
                     f"lng {site['longitude']}")

    palette = context.get("plant_palette")
    if palette:
        lines.append(palette)

    if context.get("shade_note"):
        lines.append(context["shade_note"])
    if context.get("fauna_note"):
        lines.append(context["fauna_note"])
    if extra_hints:
        lines.append("DESIGN GOALS (honour these): " + " ".join(extra_hints))
    return [
        {"role": "system", "content": "\n".join(lines)},
        {"role": "user", "content": str(prompt)},
    ]


def _parse_spec_json(content: Any) -> dict:
    """Pull a JSON object out of an LLM message, tolerating ``` fences and
    surrounding prose."""
    if not isinstance(content, str) or not content.strip():
        raise LLMError("LLM returned empty content")
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except (ValueError, json.JSONDecodeError):
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except (ValueError, json.JSONDecodeError) as exc:
            raise LLMError(f"could not parse design spec JSON: {exc}") from exc
    raise LLMError("LLM response did not contain a JSON object")


# ── Spec → Project ───────────────────────────────────────────────────────────

def _validate_spec(spec: Any) -> None:
    if not isinstance(spec, dict):
        raise LLMError("design spec must be a JSON object")
    for key in ("plants", "communities", "structures"):
        if key in spec and not isinstance(spec[key], list):
            raise LLMError(f"design spec field '{key}' must be a list")
    if not (spec.get("plants") or spec.get("communities")):
        raise LLMError("design spec contains no plants or communities")


def _coerce_qty(value: Any) -> int:
    try:
        q = int(value)
    except (TypeError, ValueError):
        return 1
    return q if q >= 1 else 1


def _clean_filters(filters: dict) -> dict:
    return {k: v for k, v in filters.items() if k in _ALLOWED_FILTERS}


def _resolve_plants(entries: list, query_plants,
                    goal_filters: Optional[dict] = None) -> list[tuple[int, int]]:
    """Map each spec plant entry to ``(plant_id, quantity)`` via the catalogue.
    Entries that resolve to nothing are skipped.

    ``goal_filters`` (the hard filters for the user's selected design goals,
    e.g. ``{"native_only": True}``) are merged *under* any per-entry filters and
    the entry's text query, so a goal binds even when the model omits it. If the
    goal-narrowed search finds nothing for a named plant we retry the bare text
    query, so an explicitly requested species is never silently dropped — the
    goal-satisfaction check in :func:`_apply_goal_feedback` flags any shortfall."""
    goal_filters = goal_filters or {}
    out: list[tuple[int, int]] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        qty = _coerce_qty(e.get("quantity", 1))
        term = str(e.get("query") or e.get("common_name")
                   or e.get("name") or "").strip()
        raw_filters = e.get("filters")
        entry_filters = (_clean_filters(raw_filters)
                         if isinstance(raw_filters, dict) else {})
        base = {**goal_filters, **entry_filters}

        # Try most specific first, then progressively relax.
        attempts: list[dict] = []
        if term:
            attempts.append({**base, "query": term})
            if base:  # goals/entry-filters present — allow a bare-term retry
                attempts.append({"query": term})
        elif base:
            attempts.append(base)

        results: list[dict] = []
        for kw in attempts:
            try:
                results = query_plants(**kw)
            except Exception:  # noqa: BLE001 — try the next, less specific form
                results = []
            if results:
                break
        if results:
            out.append((results[0]["id"], qty))
    return out


def _resolve_communities(entries: list, communities: list[dict]) -> list[int]:
    by_name = {c["name"].lower(): c["id"]
               for c in communities if c.get("name") and c.get("id") is not None}
    out: list[int] = []
    for e in entries:
        term = ""
        if isinstance(e, dict):
            term = str(e.get("query") or e.get("name") or "").strip().lower()
        elif isinstance(e, str):
            term = e.strip().lower()
        if not term:
            continue
        cid = by_name.get(term)
        if cid is None:
            for nm, nid in by_name.items():
                if term in nm or nm in term:
                    cid = nid
                    break
        if cid is not None:
            out.append(cid)
    return out


def _resolve_structures(entries: list, structures: list[dict]) -> list[str]:
    valid = {s.get("id") for s in structures}
    out: list[str] = []
    for e in entries:
        sid = None
        if isinstance(e, dict):
            sid = e.get("structure_id") or e.get("id")
        elif isinstance(e, str):
            sid = e
        if sid in valid:
            out.append(sid)
    return out


def _design_center(boundary, site_config) -> Optional[tuple[float, float]]:
    if boundary:
        lats = [p[0] for p in boundary]
        lngs = [p[1] for p in boundary]
        return (sum(lats) / len(lats), sum(lngs) / len(lngs))
    sc = site_config or {}
    lat, lng = sc.get("latitude"), sc.get("longitude")
    if lat is not None and lng is not None:
        return (float(lat), float(lng))
    return None


def _grid_positions(center_lat: float, center_lng: float, n: int,
                    spacing_m: float = _SPACING_M) -> list[tuple[float, float]]:
    """Lay out ``n`` items on a square grid centred on the site, converting
    metre offsets to degrees with the local cos-lat projection."""
    if n <= 0:
        return []
    cols = max(1, int(math.ceil(math.sqrt(n))))
    cos_lat = math.cos(center_lat * math.pi / 180) or 1e-9
    positions = []
    for i in range(n):
        row, col = divmod(i, cols)
        dx = (col - (cols - 1) / 2.0) * spacing_m
        dy = (row - (cols - 1) / 2.0) * spacing_m
        positions.append((
            center_lat + dy / 111320.0,
            center_lng + dx / (111320.0 * cos_lat),
        ))
    return positions


# ── Boundary-aware placement (V1.48) ─────────────────────────────────────────

def _boundary_polygon(boundary) -> Optional[list]:
    """Convert a boundary given as a list of ``(lat, lng)`` tuples (the form
    ``controllers/generation.py:_current_boundary`` produces) into a GeoJSON
    polygon ``[[ [lng,lat], ... ]]`` for :func:`src.geometry.point_in_polygon`.
    Returns ``None`` for a degenerate boundary."""
    if not boundary or len(boundary) < 3:
        return None
    ring = [[float(p[1]), float(p[0])] for p in boundary]  # (lat,lng) → [lng,lat]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return [ring]


def grid_cells_in_boundary(boundary, spacing_m: float = _SPACING_M
                           ) -> list[tuple[float, float]]:
    """All grid-cell centres (at ``spacing_m``) that fall strictly inside the
    boundary polygon, row-major from the NW corner. The unit of "how many
    plants fit" for trim-to-fit, and the position pool for clipped placement.
    Empty list for a degenerate boundary."""
    poly = _boundary_polygon(boundary)
    if poly is None:
        return []
    from src.geometry import ring_bbox
    min_lat, min_lng, max_lat, max_lng = ring_bbox(poly[0])
    mid_lat = (min_lat + max_lat) / 2.0
    cos_lat = math.cos(mid_lat * math.pi / 180) or 1e-9
    dlat = spacing_m / 111320.0
    dlng = spacing_m / (111320.0 * cos_lat)
    if dlat <= 0 or dlng <= 0:
        return []
    from src.geometry import point_in_polygon
    cells: list[tuple[float, float]] = []
    # Start half a step in so cells sit inside rather than on the edge.
    lat = max_lat - dlat / 2.0
    while lat > min_lat:
        lng = min_lng + dlng / 2.0
        while lng < max_lng:
            if point_in_polygon(lat, lng, poly):
                cells.append((lat, lng))
            lng += dlng
        lat -= dlat
    return cells


def positions_in_boundary(boundary, n: int, center: tuple[float, float],
                          spacing_m: float = _SPACING_M
                          ) -> list[tuple[float, float]]:
    """Up to ``n`` placement positions that are guaranteed inside ``boundary``.
    Falls back to the unclipped centred grid around ``center`` when no usable
    boundary is supplied (pin-only designs keep today's behaviour)."""
    cells = grid_cells_in_boundary(boundary, spacing_m)
    if cells:
        return cells[:n]
    return _grid_positions(center[0], center[1], n, spacing_m)


def community_fits(boundary, center: tuple[float, float], radius_m: float
                   ) -> bool:
    """True when a community of the given natural radius, placed at ``center``,
    fits inside the boundary — tested by sampling the radius circle's compass
    points (so the expanded members don't spill outside). Always True when there
    is no boundary to respect."""
    poly = _boundary_polygon(boundary)
    if poly is None:
        return True
    from src.geometry import point_in_polygon
    if not point_in_polygon(center[0], center[1], poly):
        return False
    cos_lat = math.cos(center[0] * math.pi / 180) or 1e-9
    for ang in range(0, 360, 45):
        rad = math.radians(ang)
        dlat = (radius_m * math.cos(rad)) / 111320.0
        dlng = (radius_m * math.sin(rad)) / (111320.0 * cos_lat)
        if not point_in_polygon(center[0] + dlat, center[1] + dlng, poly):
            return False
    return True


def generate_design(prompt: str, *, site_config: Optional[dict] = None,
                    boundary: Optional[list] = None,
                    name: str = "Generated Design",
                    client: Optional[LLMClient] = None,
                    endpoint: Optional[str] = None,
                    model: Optional[str] = None,
                    goals: Optional[list] = None,
                    budget: Optional[float] = None,
                    fauna_ids: Optional[list] = None,
                    match_site: bool = True):
    """Generate a :class:`~src.permadesign_api.Project` from a prompt.

    The site location comes from ``boundary`` (centroid) or
    ``site_config['latitude'/'longitude']`` — one is required, since placed
    geometry needs an anchor. ``client`` can be injected (tests pass a fake);
    otherwise an :class:`LLMClient` is built from ``endpoint``/``model``/env/
    config.

    ``goals`` is a list of design-goal keys from :mod:`src.design_goals`
    (e.g. ``["native_only", "food_producing"]``): each goal's hard filters
    narrow plant selection and its hint is appended to the LLM brief (the
    hybrid path). Unbacked goals, and hard goals nothing placed satisfies, are
    reported in the returned project's ``properties.generation_warnings``.

    Raises:
        LLMError: endpoint unreachable, response unparseable, the spec is
            malformed/empty, or no site location was supplied.
    """
    from src.permadesign_api import (
        Project, query_plants, list_polycultures, list_structures,
    )

    if not prompt or not str(prompt).strip():
        raise LLMError("prompt is empty")

    center = _design_center(boundary, site_config)
    if center is None:
        raise LLMError(
            "no site location: pass a boundary or site_config with "
            "'latitude' and 'longitude'"
        )

    if client is None:
        client = LLMClient(endpoint=endpoint, model=model)

    communities = list_polycultures()
    structures = list_structures()
    site_filters = _site_filters(site_config)
    context = {
        "community_names": [c.get("name") for c in communities if c.get("name")],
        "structure_ids": [s.get("id") for s in structures if s.get("id")],
        "community_digest": _community_digest(),
        "structure_digest": _structure_digest(),
        "site": dict(site_config or {}),
        "site_conditions": _site_conditions_line(site_config),
        "plant_palette": _plant_palette(query_plants, site_filters),
        "fauna_note": _fauna_digest(),
    }

    from src.design_goals import filters_for_goals, hints_for_goals
    # Bind plant selection to the measured site (zone/ecoregion/soil pH) on top
    # of the goal filters, so even a vague LLM query stays site-appropriate.
    goal_filters = {**site_filters, **(filters_for_goals(goals) or {})}

    hints = hints_for_goals(goals)
    if budget and budget > 0:
        hints = hints + [
            f"The total plant budget is about ${budget:.0f} CAD — favour "
            "common, lower-cost native species and avoid large specimen trees."
        ]
    fauna_names = _fauna_names(fauna_ids)
    if fauna_names:
        hints = hints + [
            "Prioritise plants that feed or host these species: "
            + ", ".join(fauna_names) + "."
        ]

    spec = client.generate_spec(prompt, context, extra_hints=hints)
    _validate_spec(spec)

    plant_items = _resolve_plants(spec.get("plants") or [], query_plants,
                                  goal_filters)
    community_items = _resolve_communities(spec.get("communities") or [], communities)
    structure_items = _resolve_structures(spec.get("structures") or [], structures)

    # Keep the design within budget *before* placement (no project-removal API
    # needed): count the atomic community cost first, drop a community that alone
    # blows the budget (only if individual plants remain to carry the design),
    # then trim individual plants to the remainder.
    budget_dropped = 0
    if budget and budget > 0:
        from src.sourcing import trim_to_budget, polyculture_cost
        clow, chigh = polyculture_cost(community_items)
        cmid = (clow + chigh) / 2.0
        if cmid > budget and plant_items:
            community_items = []
            cmid = 0.0
        plant_items, budget_dropped = trim_to_budget(
            plant_items, max(budget - cmid, 0.0))

    if not plant_items and not community_items:
        raise LLMError(
            "generated design had no plants or communities that matched the "
            "catalogue"
        )

    project = Project.create(name, site_config=site_config, boundary=boundary)
    elev, zones, pzone, szone = _zone_context(
        boundary, site_config, project.as_dict() if match_site else None)
    _place_within_boundary(project, plant_items, community_items,
                           structure_items, boundary, center,
                           elev=elev, zones=zones,
                           plant_zone_for=pzone, structure_zone_for=szone)

    _apply_goal_feedback(project, goals, query_plants, center, boundary)
    _apply_fauna_feedback(project, fauna_ids, query_plants, center, boundary)
    _record_budget_note(project, project.placed_plants, budget, budget_dropped)
    return project


def _zone_context(boundary, site_config, project_dict):
    """Build the Tier-2 micro-zoning context for placement, or all-``None`` when
    zoning is disabled (``project_dict is None``) or unavailable (no grid,
    offline). Returns ``(elev, zones, plant_zone_for, structure_zone_for)``.

    Best-effort and side-effect-free: any failure degrades to property-wide
    placement (the Tier-1 path), which already keeps everything in-boundary."""
    if project_dict is None:
        return (None, None, None, None)
    try:
        from src import zoning, shade
        elev = zoning.site_elevation_grid(boundary, site_config)
        if not elev:
            return (None, None, None, None)
        shade_g = shade.shade_grid_for_design(project_dict, elev)
        zones = zoning.classify_zones(elev, shade_g)
        if not zones:
            return (None, None, None, None)

        def plant_zone_for(plant_id):
            try:
                from src.db.plants import get_plant
                return zoning.preferred_zone_for_plant(get_plant(plant_id) or {})
            except Exception:  # noqa: BLE001
                return None

        return (elev, zones, plant_zone_for,
                zoning.preferred_zone_for_structure)
    except Exception:  # noqa: BLE001 — zoning is best-effort
        return (None, None, None, None)


def _add_warning(project, message: str) -> None:
    """Append a one-off message to ``properties.generation_warnings``."""
    props = project.as_dict().setdefault("properties", {})
    props.setdefault("generation_warnings", []).append(message)


class _Positioner:
    """Hands out placement positions, preferring a requested micro-zone.

    Built from either a zone→positions map (Tier-2 zoning available) or a flat
    in-boundary position list (Tier-1). ``take(zone)`` returns the next free
    position whose zone matches, else spills to NEUTRAL, else any remaining
    cell — so zoning *guides* placement without ever dropping a plant for lack
    of a perfect cell. ``remaining`` tracks capacity for trim-to-fit."""

    def __init__(self, zone_positions: Optional[dict], flat: list):
        self._by_zone: dict = {}
        if zone_positions:
            for z, pts in zone_positions.items():
                self._by_zone[z] = list(pts)
        # A flat fallback pool (used when no zoning, and as the final spill).
        self._flat = list(flat)
        self._used: set = set()

    @property
    def remaining(self) -> int:
        if self._by_zone:
            return sum(len(v) for v in self._by_zone.values())
        return len(self._flat)

    def _pop_unused(self, lst: list):
        while lst:
            p = lst.pop(0)
            if p not in self._used:
                self._used.add(p)
                return p
        return None

    def take(self, zone: Optional[str] = None):
        from src import zoning
        if self._by_zone:
            order = []
            if zone:
                order.append(zone)
            if zoning.NEUTRAL not in order:
                order.append(zoning.NEUTRAL)
            for z in (zone, zoning.NEUTRAL, zoning.WET, zoning.DRY,
                      zoning.SHADED):
                if z and z not in order:
                    order.append(z)
            for z in order:
                p = self._pop_unused(self._by_zone.get(z, []))
                if p is not None:
                    return p
            return None
        return self._pop_unused(self._flat)


def _place_within_boundary(project, plant_items, community_items,
                           structure_items, boundary,
                           center: tuple[float, float],
                           elev: Optional[dict] = None,
                           zones: Optional[dict] = None,
                           plant_zone_for=None,
                           structure_zone_for=None) -> None:
    """Place plants, communities and structures so every element lands inside
    the drawn boundary, trimming to fit at healthy spacing (V1.48).

    Positions come from :func:`positions_in_boundary`; when the boundary is too
    small to hold everything at ``_SPACING_M`` spacing we place what fits and
    record a "trimmed N" warning. Communities are only placed where their whole
    expanded footprint (``community_natural_radius``) fits — otherwise they are
    skipped with a note, closing the member-offset spill path.

    When an elevation grid + ``zones`` are supplied (Tier-2), plants/structures
    are routed to their preferred micro-zone via ``plant_zone_for`` /
    ``structure_zone_for`` (callables returning a zone label); otherwise a flat
    in-boundary grid is used."""
    from src.db.polycultures import (
        get_polyculture_by_id, community_natural_radius,
    )

    # Build the position source: zoned (clipped to boundary) or flat.
    zpos = None
    if elev and zones:
        try:
            from src import zoning
            zpos = zoning.zone_positions(elev, zones, boundary)
        except Exception:  # noqa: BLE001
            zpos = None
    flat = positions_in_boundary(
        boundary,
        len(plant_items) + len(community_items) + len(structure_items),
        center)
    positioner = _Positioner(zpos, flat)

    # Filter communities down to those whose footprint fits somewhere sensible.
    placeable_comms: list[tuple[int, float]] = []
    skipped_comms = 0
    for cid in community_items:
        try:
            full = get_polyculture_by_id(cid)
            radius = community_natural_radius(full)
        except Exception:  # noqa: BLE001
            radius = 1.0
        placeable_comms.append((cid, radius))

    total = len(plant_items) + len(placeable_comms) + len(structure_items)
    capacity = positioner.remaining

    # Trim-to-fit: when capacity can't hold everything at healthy spacing, drop
    # the overflow (individual plants first — communities/structures are higher-
    # value, larger commitments).
    trimmed = 0
    if capacity < total:
        drop = min(total - capacity, len(plant_items))
        if drop:
            plant_items = plant_items[:len(plant_items) - drop]
            trimmed += drop

    for plant_id, qty in plant_items:
        zone = None
        if plant_zone_for is not None:
            try:
                zone = plant_zone_for(plant_id)
            except Exception:  # noqa: BLE001
                zone = None
        pos = positioner.take(zone)
        if pos is None:
            break
        project.place_plant(plant_id, pos[0], pos[1], quantity=qty)
    for cid, radius in placeable_comms:
        pos = positioner.take(None)
        if pos is None:
            break
        if community_fits(boundary, pos, radius):
            project.place_polyculture(cid, pos[0], pos[1])
        else:
            skipped_comms += 1
    for struct_id in structure_items:
        zone = None
        if structure_zone_for is not None:
            try:
                zone = structure_zone_for(struct_id)
            except Exception:  # noqa: BLE001
                zone = None
        pos = positioner.take(zone)
        if pos is None:
            break
        project.place_structure(struct_id, pos[0], pos[1])

    if trimmed:
        _add_warning(project,
                     f"Trimmed {trimmed} plant" + ("s" if trimmed != 1 else "")
                     + " to fit the area at healthy spacing.")
    if skipped_comms:
        _add_warning(project,
                     f"Skipped {skipped_comms} plant communit"
                     + ("ies" if skipped_comms != 1 else "y")
                     + " that did not fit inside the boundary.")


# ── Goal feedback + offline fallback ─────────────────────────────────────────

_OFFLINE_PLANT_CAP = 7  # how many individual plants the no-LLM path places


def _match_communities_by_name(communities: list[dict],
                               hints: list) -> list[int]:
    """Return ids of seeded communities whose name contains any of ``hints``
    (case-insensitive substring), preserving catalogue order."""
    lowered = [h.lower() for h in (hints or []) if h]
    out: list[int] = []
    for c in communities:
        name = (c.get("name") or "").lower()
        cid = c.get("id")
        if cid is None or not name:
            continue
        if any(h in name for h in lowered):
            out.append(cid)
    return out


def _fauna_names(fauna_ids) -> list:
    """Resolve fauna ids to common names (for prompt hints / warnings). Skips
    unknown ids; returns [] on any error."""
    out: list = []
    try:
        from src.db.fauna import get_fauna
    except Exception:  # noqa: BLE001
        return out
    for fid in fauna_ids or []:
        try:
            rec = get_fauna(int(fid))
        except Exception:  # noqa: BLE001
            rec = None
        if rec and rec.get("common_name"):
            out.append(rec["common_name"])
    return out


def _one_position_in_boundary(boundary, center: tuple[float, float]
                              ) -> tuple[float, float]:
    """A single placement spot inside the boundary (its first free grid cell),
    falling back to the design centre when there is no usable boundary. Keeps
    the goal/fauna repair additions from landing outside the drawn area."""
    cells = grid_cells_in_boundary(boundary)
    if cells:
        return cells[0]
    return _grid_positions(center[0], center[1], 1)[0]


def _apply_fauna_feedback(project, fauna_ids, query_plants,
                          center: tuple[float, float], boundary=None) -> None:
    """Ensure the design actually serves each chosen wildlife species: for any
    selected fauna with no supporting plant among those placed, drop in one
    plant that supports it. Mirrors :func:`_apply_goal_feedback`; warnings live
    under ``properties.generation_warnings``."""
    if not fauna_ids:
        return
    placed_ids = {p.get("plant_id") for p in project.placed_plants}
    added_any = False
    for fid in fauna_ids:
        try:
            supporters = query_plants(supports_fauna_id=int(fid))
        except Exception:  # noqa: BLE001
            supporters = []
        if not supporters:
            continue
        if placed_ids.isdisjoint({p["id"] for p in supporters}):
            lat, lng = _one_position_in_boundary(boundary, center)
            project.place_plant(supporters[0]["id"], lat, lng, quantity=1)
            placed_ids.add(supporters[0]["id"])
            added_any = True
    if added_any:
        names = _fauna_names(fauna_ids)
        msg = ("Added plants so the design supports your chosen wildlife"
               + (f" ({', '.join(names)})." if names else "."))
        props = project.as_dict().setdefault("properties", {})
        props.setdefault("generation_warnings", []).append(msg)


def _apply_goal_feedback(project, goals, query_plants,
                         center: tuple[float, float], boundary=None) -> None:
    """Record goal-related warnings on the project and, if a *backed* goal ends
    up with no representation among the placed plants, drop in one satisfying
    plant so the result never silently violates a hard goal.

    Warnings live under ``properties.generation_warnings`` (a plain list on the
    project dict — no schema concept) for the GUI/CLI to surface. The key is
    only written when there is something to say. Deeper repair (e.g. filling
    bloom gaps) waits on the data described in ``docs/data_gaps_v1.44.md``."""
    from src.design_goals import (
        filters_for_goals, unbacked_goals, get_goal, caveats_for_goals,
    )

    warnings: list = []
    unbacked = unbacked_goals(goals)
    if unbacked:
        labels = [g.label for g in (get_goal(k) for k in unbacked) if g]
        warnings.append(
            "Applied as guidance to the AI only (no plant data backs these "
            "yet, so they can't be guaranteed): " + ", ".join(labels) + "."
        )
    # Advisories for goals honoured by a denylist (e.g. the safety goals).
    warnings.extend(caveats_for_goals(goals))

    goal_filters = filters_for_goals(goals)
    if goal_filters:
        try:
            satisfying = query_plants(**goal_filters)
        except Exception:  # noqa: BLE001
            satisfying = []
        if not satisfying:
            warnings.append(
                "No catalogue plant satisfies all selected goals at once — the "
                "design may not meet every goal."
            )
        else:
            sat_ids = {p["id"] for p in satisfying}
            placed_ids = {p.get("plant_id") for p in project.placed_plants}
            if placed_ids.isdisjoint(sat_ids):
                lat, lng = _one_position_in_boundary(boundary, center)
                project.place_plant(satisfying[0]["id"], lat, lng, quantity=1)
                warnings.append(
                    "Added one plant to honour the selected goals "
                    f"({satisfying[0].get('common_name', 'plant')})."
                )

    if warnings:
        props = project.as_dict().setdefault("properties", {})
        props.setdefault("generation_warnings", []).extend(warnings)


def _record_budget_note(project, placed, budget,
                        dropped: int = 0) -> None:
    """Append an estimated-cost note (and any budget-trim message) to the
    project's ``generation_warnings``. ``placed`` is the project's placed-plant
    list, so the estimate covers the whole design (individual plants plus any
    community-expanded ones). No-op unless a budget was given."""
    if not budget or budget <= 0:
        return
    from src.sourcing import estimate_cost, format_cost
    low, high = estimate_cost(placed)
    mid = (low + high) / 2.0
    status = (f"within your ${budget:.0f} budget" if mid <= budget
              else f"above your ${budget:.0f} budget")
    msg = (f"Estimated plant cost {format_cost(low, high)} CAD "
           f"(Alberta retail estimate) — {status}")
    if dropped:
        msg += (f"; trimmed {dropped} plant" + ("s" if dropped != 1 else "")
                + " to reduce cost")
    props = project.as_dict().setdefault("properties", {})
    props.setdefault("generation_warnings", []).append(msg)


def generate_design_offline(*, site_config: Optional[dict] = None,
                            boundary: Optional[list] = None,
                            name: str = "Generated Design",
                            goals: Optional[list] = None,
                            budget: Optional[float] = None,
                            fauna_ids: Optional[list] = None,
                            match_site: bool = True):
    """Generate a :class:`~src.permadesign_api.Project` WITHOUT an LLM.

    Selects plants by the hard filters for ``goals`` (defaulting to Alberta
    natives) and pulls in seeded plant communities whose names match the goals,
    then lays everything out exactly like :func:`generate_design`. This is the
    fallback the GUI/CLI use when no local model is reachable, so the one-click
    button always produces a usable starting design.

    Raises:
        LLMError: if no site location (``boundary`` or ``site_config`` lat/lng)
            is supplied — placed geometry needs an anchor.
    """
    from src.permadesign_api import Project, query_plants, list_polycultures
    from src.design_goals import filters_for_goals, community_name_hints

    center = _design_center(boundary, site_config)
    if center is None:
        raise LLMError(
            "no site location: pass a boundary or site_config with "
            "'latitude' and 'longitude'"
        )

    # Bind selection to the measured site (zone/ecoregion/soil pH) on top of the
    # goal filters so the offline design is site-appropriate too (V1.48).
    site_filters = _site_filters(site_config)
    goal_filters = {**site_filters,
                    **(filters_for_goals(goals) or {"native_only": True})}
    try:
        plants = query_plants(**goal_filters)
    except Exception:  # noqa: BLE001
        plants = []
    if not plants:  # site+goals too restrictive — widen so we still produce one
        try:
            plants = query_plants(native_only=True, **site_filters)
        except Exception:  # noqa: BLE001
            plants = []
    if not plants:
        try:
            plants = query_plants(native_only=True)
        except Exception:  # noqa: BLE001
            plants = []

    # If the user picked target wildlife, lead with plants that support it
    # (intersected with the goals where possible), then fill with the rest so
    # the capped selection still serves the chosen species.
    if fauna_ids:
        chosen: list = []
        seen: set = set()
        for fid in fauna_ids:
            try:
                hits = (query_plants(supports_fauna_id=int(fid), **goal_filters)
                        or query_plants(supports_fauna_id=int(fid)))
            except Exception:  # noqa: BLE001
                hits = []
            for pl in hits:
                if pl["id"] not in seen:
                    seen.add(pl["id"]); chosen.append(pl)
        for pl in plants:
            if pl["id"] not in seen:
                seen.add(pl["id"]); chosen.append(pl)
        plants = chosen

    plant_items = [(p["id"], 1) for p in plants[:_OFFLINE_PLANT_CAP]]

    communities = list_polycultures()
    community_items = _match_communities_by_name(
        communities, community_name_hints(goals))
    # Don't force an arbitrary default community in budget mode — it would blow
    # an individual-plant budget; a goal-matched community still applies.
    if not community_items and communities and not budget:
        community_items = [communities[0]["id"]]  # a sensible default

    # Budget: count the (atomic) community cost first, drop a matched community
    # that alone blows the budget (when individuals remain to carry the design),
    # then trim individual plants to the remainder so the whole design fits.
    budget_dropped = 0
    if budget and budget > 0:
        from src.sourcing import trim_to_budget, polyculture_cost
        clow, chigh = polyculture_cost(community_items)
        cmid = (clow + chigh) / 2.0
        if cmid > budget and plant_items:
            community_items = []
            cmid = 0.0
        plant_items, budget_dropped = trim_to_budget(
            plant_items, max(budget - cmid, 0.0))

    if not plant_items and not community_items:
        raise LLMError(
            "offline generation found no plants or communities to place"
        )

    project = Project.create(name, site_config=site_config, boundary=boundary)
    elev, zones, pzone, szone = _zone_context(
        boundary, site_config, project.as_dict() if match_site else None)
    _place_within_boundary(project, plant_items, community_items, [],
                           boundary, center, elev=elev, zones=zones,
                           plant_zone_for=pzone, structure_zone_for=szone)

    _apply_goal_feedback(project, goals, query_plants, center, boundary)
    _apply_fauna_feedback(project, fauna_ids, query_plants, center, boundary)
    _record_budget_note(project, project.placed_plants, budget, budget_dropped)
    return project
