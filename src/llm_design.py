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
You are a landscape design assistant for Site & Pattern, a tool for native-plant
habitat gardens in Alberta and the Canadian prairies. Given a design brief,
respond with ONLY a single JSON object (no prose, no markdown fences) of this
shape:

{
  "summary": "one sentence describing the design",
  "plants": [
    {"query": "wild bergamot", "quantity": 7, "layout": "scatter"},
    {"query": "saskatoon", "quantity": 5, "layout": "row"}
  ],
  "plant_mixes": [
    {"plants": [{"query": "blue grama grass", "weight": 3},
                {"query": "gaillardia", "weight": 1}],
     "quantity": 24, "layout": "drift"}
  ],
  "communities": [
    {"query": "pollinator", "count": 2, "layout": "scatter"}
  ],
  "community_mixes": [
    {"communities": [{"query": "meadow", "weight": 2},
                     {"query": "aromatic", "weight": 1}],
     "count": 3}
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
- "plants[].layout" (optional) is how that GROUP is arranged on the ground:
  "row" for hedges, screens and bed edges; "grid" for evenly-spaced trees or a
  formal block; "circle" for a feature specimen or herb circle; "drift" for a
  flowing, naturalistic sweep of grasses/forbs (the preferred look for a meadow);
  "scatter" for loosely-spread accents. Choose the layout that suits the plant's
  role; omit it to let the app pick by growth habit.
- "plant_mixes" (optional) interleaves 2–4 species through ONE stand — a
  seed-mix look (matrix grass + flowering forbs is the classic meadow).
  "weight" sets the ratio (3:1 = three of the first per one of the second);
  "quantity" is the TOTAL plants in the stand. Use a mix when species should
  mingle; use separate "plants" entries when each species should hold its
  own ground.
- Use generous quantities and several groups so the planting FILLS the
  available space (see the planting target below) rather than leaving the lot
  mostly bare.
- "communities[].query" must loosely match one of the AVAILABLE COMMUNITIES
  listed below. Choose communities whose description suits the SITE
  CONDITIONS (e.g. a riparian/willow community for wet ground, a mixedgrass
  or aromatic community for a dry sunny site, a boreal/shade community for
  shade). "count" (optional, 1–6) repeats the community that many times —
  e.g. three willow pockets along a wet edge; "layout" (optional) arranges
  the repeats ("row" / "grid" / "circle" / "scatter").
- "community_mixes" (optional) scatters SEVERAL community types across the
  site in one gesture — "count" total pockets, each pocket one community
  chosen by "weight" ratio. Use it for a mosaic (meadow + shrub island +
  herb circle) instead of listing each community separately.
- "structures[].structure_id" must be one of the AVAILABLE STRUCTURE IDS
  listed below. Match structures to the site: pond / swale / rain_garden for
  low or wet ground, bee_hotel / native_bee_log in sun, brush_pile / snag for
  cover.
- MATCH PLANTS TO THE SITE CONDITIONS: shade-tolerant plants for shaded
  spots, moisture-loving / aquatic plants for wet or low ground, drought-
  tolerant plants for dry slopes, and species whose hardiness and ecoregion
  suit the site.
- Favour native, pollinator-supporting, prairie-hardy species.
- USE THE FULL VOCABULARY: for any meadow / naturalistic / lawn-conversion
  brief include at least one "plant_mixes" stand (matrix grass + forbs);
  when two or more communities suit the site, prefer one "community_mixes"
  mosaic over separate single communities; give hedges/screens a "row" and
  repeated feature pockets a "count".
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

    def revise_spec(self, prompt: str, context: dict, first_spec: dict,
                    critique: list,
                    extra_hints: Optional[list] = None) -> dict:
        """One evaluate→revise round (V1.62): show the model the spec it
        produced plus the habitat-score critique of the placed result, and
        ask for an improved complete spec in the same format. The caller
        re-validates, re-places, and only adopts the revision when the
        habitat score actually improves."""
        messages = _build_messages(prompt, context, extra_hints)
        messages.append({"role": "assistant",
                         "content": json.dumps(first_spec)})
        messages.append({"role": "user", "content": (
            "Your design was placed on the site and evaluated with the "
            "Habitat Value Score. Issues found:\n- "
            + "\n- ".join(str(c) for c in critique)
            + "\n\nReturn an improved COMPLETE design spec in the exact "
              "same JSON format (not a diff). Keep what already works; "
              "fix the issues by adding species or communities that close "
              "the gaps, and drop anything that doesn't serve the goals."
        )})
        return _parse_spec_json(self.chat(messages))


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
            groups.setdefault(r.get("plant_type", "other"),
                              []).append(_palette_entry(r))
    order = ["tree", "shrub", "herb", "grass", "sedge", "rush",
             "groundcover", "vine", "root", "fern", "aquatic"]
    parts = []
    for ptype in order + [g for g in groups if g not in order]:
        names = groups.get(ptype)
        if names:
            parts.append(f"{ptype}: " + "; ".join(names[:limit_per_group]))
    if not parts:
        return ""
    return ("PLANT PALETTE (site-fit natives — prefer these; "
            "H=height W=spread cm, sun/water/bloom/pH):\n  "
            + "\n  ".join(parts))


def _palette_entry(r: dict) -> str:
    """Compact per-plant detail line: ``Name (H120×W90, full_sun, low, Jun–Aug,
    pH6–8)`` — only the fields present, so the model can match plants to the
    site without a second lookup. Values are abbreviated to bound prompt size."""
    nm = r.get("common_name", "?")
    bits = []

    def _cm(v):
        try:
            return f"{int(round(float(v) * 100))}"
        except (TypeError, ValueError):
            return ""
    h = _cm(r.get("mature_height_meters") or r.get("mature_height_m"))
    w = _cm(r.get("mature_canopy_m") or r.get("spacing_meters")
            or r.get("spacing_m"))
    if h or w:
        bits.append(f"H{h or '?'}×W{w or '?'}")
    if r.get("sun_requirement"):
        bits.append(str(r["sun_requirement"]))
    if r.get("water_needs"):
        bits.append(str(r["water_needs"]))
    if r.get("bloom_period"):
        bits.append(str(r["bloom_period"]))
    lo, hi = r.get("soil_ph_min"), r.get("soil_ph_max")
    if lo or hi:
        bits.append(f"pH{lo or '?'}-{hi or '?'}")
    return f"{nm} ({', '.join(bits)})" if bits else nm


def _existing_features_note(project_dict: dict) -> str:
    """One-line summary of marked/imported existing trees & buildings so the
    model knows to design around them (they're also enforced as keep-out).
    Empty when there are none."""
    n_tree = n_bldg = 0
    for f in (project_dict or {}).get("features", []) or []:
        props = f.get("properties") or {}
        et = props.get("element_type")
        if et == "existing_tree":
            n_tree += 1
        elif et == "existing_building":
            n_bldg += 1
        elif et == "canopy_footprint" and props.get("cast_shade"):
            # V1.58: OSM buildings + hand-drawn building/canopy perimeters import
            # as shade-casting canopy_footprint polygons rather than points.
            n_bldg += 1
    if not (n_tree or n_bldg):
        return ""
    bits = []
    if n_tree:
        bits.append(f"{n_tree} existing tree" + ("s" if n_tree != 1 else ""))
    if n_bldg:
        bits.append(f"{n_bldg} building" + ("s" if n_bldg != 1 else ""))
    return ("EXISTING ON SITE (avoid planting on top of these): "
            + ", ".join(bits) + ".")


def _zones_note(elev, zones) -> str:
    """One-line wet/dry/shaded cell tally from the micro-zoning, so the model
    knows the site has distinct sub-areas to design into. Empty when zoning is
    unavailable."""
    if not zones:
        return ""
    from collections import Counter
    counts = Counter(zones.values())
    from src import zoning
    parts = []
    for key, label in ((zoning.WET, "wet/low"), (zoning.DRY, "dry/high"),
                       (zoning.SHADED, "shaded")):
        if counts.get(key):
            parts.append(f"{label}: {counts[key]} cells")
    if not parts:
        return ""
    return "SITE ZONES (place matching plants in each): " + "; ".join(parts) + "."


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
    if context.get("zones_note"):
        lines.append(context["zones_note"])
    if context.get("existing_note"):
        lines.append(context["existing_note"])
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
    for key in ("plants", "plant_mixes", "communities", "community_mixes",
                "structures"):
        if key in spec and not isinstance(spec[key], list):
            raise LLMError(f"design spec field '{key}' must be a list")
    if not (spec.get("plants") or spec.get("communities")
            or spec.get("plant_mixes") or spec.get("community_mixes")):
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
    out: list[tuple[int, int, str]] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        qty = _coerce_qty(e.get("quantity", 1))
        layout = str(e.get("layout") or "").strip().lower()
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
            # (plant_id, quantity, layout) — layout is "" when the model didn't
            # request one; _place_within_boundary fills a habit-based default.
            out.append((results[0]["id"], qty, layout))
    return out


def _one_community_id(entry, by_name: dict) -> Optional[int]:
    """Resolve one spec entry (dict or bare string) to a community id —
    exact name match first, then loose substring either way."""
    term = ""
    if isinstance(entry, dict):
        term = str(entry.get("query") or entry.get("name") or "").strip().lower()
    elif isinstance(entry, str):
        term = entry.strip().lower()
    if not term:
        return None
    cid = by_name.get(term)
    if cid is None:
        for nm, nid in by_name.items():
            if term in nm or nm in term:
                cid = nid
                break
    return cid


def _community_index(communities: list[dict]) -> dict:
    return {c["name"].lower(): c["id"]
            for c in communities if c.get("name") and c.get("id") is not None}


def _clean_layout(value) -> str:
    """Validate a spec layout name against the canonical pattern set —
    anything unrecognized becomes '' (let placement pick)."""
    from src import layout as _layout
    name = str(value or "").strip().lower()
    return name if name in _layout.LAYOUTS else ""


def _coerce_weight(value) -> int:
    try:
        return max(1, min(99, int(value)))
    except (TypeError, ValueError):
        return 1


# How many repeats of one community / pockets in one mix the spec may ask
# for. Communities are big multi-plant footprints — the cap keeps a
# hallucinated "count": 400 from carpeting the lot.
_MAX_COMMUNITY_COUNT = 6
_MAX_MIX_POCKETS = 12


def _resolve_communities(entries: list, communities: list[dict]) -> list[dict]:
    """Spec ``communities`` entries → placement groups
    ``{"id", "count", "layout"}``. Unmatched entries drop (same contract as
    plant resolution); a bare string or count-less dict is one instance."""
    by_name = _community_index(communities)
    out: list[dict] = []
    for e in entries:
        cid = _one_community_id(e, by_name)
        if cid is None:
            continue
        count, layout = 1, ""
        if isinstance(e, dict):
            try:
                count = max(1, min(_MAX_COMMUNITY_COUNT,
                                   int(e.get("count") or 1)))
            except (TypeError, ValueError):
                count = 1
            layout = _clean_layout(e.get("layout"))
        out.append({"id": cid, "count": count, "layout": layout})
    return out


def _resolve_community_mixes(entries: list,
                             communities: list[dict]) -> list[dict]:
    """Spec ``community_mixes`` → ``{"members": [(cid, weight)], "count",
    "layout"}``. A mix needs ≥2 resolved member types — a one-community
    "mix" folds down to a plain community group at the caller. Mixes whose
    members all fail to resolve drop entirely."""
    by_name = _community_index(communities)
    out: list[dict] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        members: list[tuple[int, int]] = []
        seen: set[int] = set()
        for m in (e.get("communities") or e.get("members") or []):
            cid = _one_community_id(m, by_name)
            if cid is None or cid in seen:
                continue
            seen.add(cid)
            weight = _coerce_weight(m.get("weight") if isinstance(m, dict)
                                    else 1)
            members.append((cid, weight))
        if not members:
            continue
        try:
            count = max(1, min(_MAX_MIX_POCKETS, int(e.get("count") or 0)))
        except (TypeError, ValueError):
            count = 0
        if count < 1:
            count = max(2, len(members))   # sensible default: one per type
        out.append({"members": members, "count": count,
                    "layout": _clean_layout(e.get("layout"))})
    return out


def _resolve_plant_mixes(entries: list, query_plants,
                         goal_filters: Optional[dict]) -> list[dict]:
    """Spec ``plant_mixes`` → ``{"members": [(plant_id, weight)],
    "quantity", "layout"}``. Members resolve through the same catalogue
    search as ``plants`` entries (so goal filters and the bare-term retry
    apply); a mix keeps only resolved members and drops entirely when
    fewer than one survives."""
    out: list[dict] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        raw_members = e.get("plants") or e.get("members") or []
        resolved: list[tuple[int, int]] = []
        seen: set[int] = set()
        for m in raw_members:
            if isinstance(m, str):
                m = {"query": m}
            if not isinstance(m, dict):
                continue
            # Reuse the single-entry plant resolution (goal filters + the
            # bare-term retry apply); read the plant id back off the item.
            items = _resolve_plants([m], query_plants, goal_filters)
            if not items:
                continue
            pid = items[0][0]
            if pid in seen:
                continue
            seen.add(pid)
            resolved.append((pid, _coerce_weight(m.get("weight"))))
        if not resolved:
            continue
        # Cap the stand: mixes bypass the density expansion, so a
        # hallucinated quantity must not carpet the lot on its own.
        qty = min(_coerce_qty(e.get("quantity") or e.get("qty")
                              or (4 * len(resolved))), 60)
        out.append({"members": resolved, "quantity": qty,
                    "layout": _clean_layout(e.get("layout"))})
    return out


def _expected_mix_counts(members: list[tuple[int, int]],
                         total: int) -> dict[int, int]:
    """Deterministic per-member instance counts for ``total`` placements —
    the exact split ``assign_species`` will produce (largest-deficit over
    weights), used for budget math before placement."""
    from src.polyculture import assign_species
    items = [{"id": mid, "weight": w} for mid, w in members]
    assignments = assign_species([(0.0, 0.0)] * max(0, int(total)), items,
                                 "even_split")
    counts: dict[int, int] = {}
    for a in assignments:
        counts[a["id"]] = counts.get(a["id"], 0) + 1
    return counts


def _trim_spec_to_budget(p_items, p_mixes, c_groups, c_mixes, budget):
    """One money rule for BOTH generation paths (LLM and offline).

    Keeps the design within budget *before* placement (no project-removal
    API needed): cost the atomic communities first (every repeat and every
    expected mix pocket), dropping community groups/mixes lowest-ranked-
    first when they alone blow the budget (only while plants remain to
    carry the design); then trim individual plants; then drop whole plant
    mixes (never trim inside one — that would skew its ratios) until the
    remainder fits. Returns ``(p_items, p_mixes, c_groups, c_mixes,
    n_dropped)``."""
    if not budget or budget <= 0:
        return p_items, p_mixes, c_groups, c_mixes, 0
    from src.sourcing import estimate_cost, polyculture_cost, trim_to_budget

    def _communities_mid_cost() -> float:
        expanded = [g["id"] for g in c_groups for _ in range(g["count"])]
        for mix in c_mixes:
            for cid, n in _expected_mix_counts(
                    mix["members"], mix["count"]).items():
                expanded.extend([cid] * n)
        lo, hi = polyculture_cost(expanded)
        return (lo + hi) / 2.0

    dropped = 0
    cmid = _communities_mid_cost()
    while cmid > budget and (p_items or p_mixes) and (c_groups or c_mixes):
        if c_mixes:
            c_mixes = c_mixes[:-1]      # drop lowest-priority first
        else:
            c_groups = c_groups[:-1]
        dropped += 1
        cmid = _communities_mid_cost()
    if cmid > budget and (p_items or p_mixes):
        c_groups, c_mixes = [], []
        cmid = 0.0

    p_items, n = trim_to_budget(p_items, max(budget - cmid, 0.0))
    dropped += n
    plo, phi = estimate_cost([(pid, q) for pid, q, *_ in p_items])
    remaining = max(budget - cmid - (plo + phi) / 2.0, 0.0)
    while p_mixes:
        pairs = [(pid, n) for mix in p_mixes
                 for pid, n in _expected_mix_counts(
                     mix["members"], mix["quantity"]).items()]
        mlo, mhi = estimate_cost(pairs)
        if (mlo + mhi) / 2.0 <= remaining:
            break
        p_mixes = p_mixes[:-1]          # drop whole mixes, newest first
        dropped += 1
    return p_items, p_mixes, c_groups, c_mixes, dropped


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


def _inside_boundary(boundary, lat: float, lng: float) -> bool:
    """True when ``(lat, lng)`` is inside the boundary polygon (or there is no
    usable boundary). Thin wrapper over :func:`src.geometry.point_in_polygon`."""
    poly = _boundary_polygon(boundary)
    if poly is None:
        return True
    from src.geometry import point_in_polygon
    return point_in_polygon(lat, lng, poly)


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
                    match_site: bool = True,
                    density: str = "balanced",
                    existing_features: Optional[list] = None,
                    revise: bool = True):
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

    ``revise=True`` (default) runs one evaluate→revise round: the placed
    design is scored with the Habitat Value Score, the concrete issues are
    fed back to the model, and its revised spec is re-placed — adopted only
    when the score improves (see :mod:`src.design_critic`). The
    deterministic critic repairs (keystone / host / bloom-gap fills) run
    either way.

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

    # Micro-zoning + keep-out are computed up front so they inform BOTH the
    # prompt (the model designs into the wet/dry/shaded zones and around
    # existing features) and placement. project_for_ctx carries any marked
    # existing trees/buildings the user/site already has.
    project_ctx = Project.create(name, site_config=site_config, boundary=boundary)
    from src.exclusion import keepout_circles, fill_regions
    elev, zones, pzone, szone, cell_env_map = _zone_context(
        boundary, site_config, project_ctx.as_dict() if match_site else None)
    # F5: fold the user's existing drawn layer (existing trees/buildings,
    # existing-remnant + hardscape zones, restoration fill zones) into the
    # context so it both informs the prompt and steers placement.
    _ctx_dict = {"features": (project_ctx.as_dict().get("features") or [])
                 + (existing_features or [])}
    keepout = keepout_circles(_ctx_dict)
    fills = fill_regions(_ctx_dict)

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
        "zones_note": _zones_note(elev, zones),
        "existing_note": _existing_features_note(_ctx_dict),
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
    # Density target — tell the model roughly how many plantings fill the space
    # (placement also expands deterministically, so this is guidance not a hard
    # contract).
    cap = _boundary_capacity(boundary, keepout)
    frac = _DENSITY_FRACTION.get((density or "").lower())
    if cap and frac:
        hints = hints + [
            f"Aim for roughly {int(cap * frac)} total plantings to fill the "
            f"space at a {density} density."
        ]

    def _realize(spec_dict, into_project=None):
        """Resolve a spec against the catalogue and place it. Returns
        ``(project, budget_dropped)``; raises LLMError when nothing in the
        spec matched. Placement is deterministic, so realizing a revised
        spec is cheap — only the LLM round costs anything."""
        p_items = _resolve_plants(spec_dict.get("plants") or [],
                                  query_plants, goal_filters)
        p_mixes = _resolve_plant_mixes(spec_dict.get("plant_mixes") or [],
                                       query_plants, goal_filters)
        c_groups = _resolve_communities(spec_dict.get("communities") or [],
                                        communities)
        c_mixes = _resolve_community_mixes(
            spec_dict.get("community_mixes") or [], communities)
        s_items = _resolve_structures(spec_dict.get("structures") or [],
                                      structures)
        # A "mix" with one surviving member type is just a repeated
        # community / a plain plant group — fold it down so placement has
        # one code path per real concept.
        for mix in list(c_mixes):
            if len(mix["members"]) == 1:
                c_mixes.remove(mix)
                c_groups.append({
                    "id": mix["members"][0][0],
                    "count": min(mix["count"], _MAX_COMMUNITY_COUNT),
                    "layout": mix["layout"],
                })
        for mix in list(p_mixes):
            if len(mix["members"]) == 1:
                p_mixes.remove(mix)
                p_items.append((mix["members"][0][0], mix["quantity"],
                                mix["layout"]))

        p_items, p_mixes, c_groups, c_mixes, dropped = _trim_spec_to_budget(
            p_items, p_mixes, c_groups, c_mixes, budget)

        if not p_items and not c_groups and not p_mixes and not c_mixes:
            raise LLMError(
                "generated design had no plants or communities that "
                "matched the catalogue"
            )

        proj = into_project if into_project is not None else Project.create(
            name, site_config=site_config, boundary=boundary)
        p_items = _apply_density(p_items, boundary, density, keepout)
        _place_within_boundary(proj, p_items, c_groups, s_items,
                               boundary, center,
                               elev=elev, zones=zones,
                               plant_zone_for=pzone,
                               structure_zone_for=szone,
                               keepout=keepout,
                               cell_env_map=cell_env_map,
                               fill_regions=fills,
                               community_mixes=c_mixes,
                               plant_mixes=p_mixes)
        return proj, dropped

    spec = client.generate_spec(prompt, context, extra_hints=hints)
    _validate_spec(spec)
    # Round 1 reuses the project built up front (zoning + keep-out were
    # already computed for the prompt).
    project, budget_dropped = _realize(spec, into_project=project_ctx)

    # ── Evaluate → revise → re-place (V1.62) ────────────────────────────
    # Score the placed design with the same Habitat Value Score the
    # Analysis panel shows, hand the model its own spec + the concrete
    # issues, and re-place its revision. The revision is adopted ONLY if
    # the score actually improves, so the loop can never make a design
    # worse by our own metric.
    from src.design_critic import (
        apply_repairs, critique_lines, evaluate_design,
    )
    revise_fn = getattr(client, "revise_spec", None)
    if revise and revise_fn is not None:
        eval1 = evaluate_design(project)
        issues = critique_lines(eval1) if eval1 else []
        if issues:
            try:
                spec2 = revise_fn(prompt, context, spec, issues,
                                  extra_hints=hints)
                _validate_spec(spec2)
                project2, dropped2 = _realize(spec2)
                eval2 = evaluate_design(project2)
                if (eval2 and eval1
                        and eval2.get("total", 0) > eval1.get("total", 0)):
                    project, budget_dropped = project2, dropped2
                    _add_warning(project,
                                 "Design revised after evaluation — "
                                 f"Habitat Score {eval1['total']} → "
                                 f"{eval2['total']}.")
            except Exception:  # noqa: BLE001 — revision is opportunistic;
                pass           # any failure keeps the valid round-1 design

    # Deterministic backstop for whichever round won: mend the most
    # impactful remaining gaps straight from the catalogue.
    for msg in apply_repairs(
            project, query_plants,
            lambda: _one_position_in_boundary(boundary, center)):
        _add_warning(project, msg)

    _apply_goal_feedback(project, goals, query_plants, center, boundary)
    _apply_fauna_feedback(project, fauna_ids, query_plants, center, boundary)
    _record_budget_note(project, project.placed_plants, budget, budget_dropped)
    return project


def _zone_context(boundary, site_config, project_dict):
    """Build the Tier-2 micro-zoning context for placement, or all-``None`` when
    zoning is disabled (``project_dict is None``) or unavailable (no grid,
    offline). Returns ``(elev, zones, plant_zone_for, structure_zone_for,
    cell_env_map)`` where ``cell_env_map`` is a ``{(lat,lng): CellEnv}`` dict
    for scored placement (``None`` on any failure).

    Best-effort and side-effect-free: any failure degrades to property-wide
    placement (the Tier-1 path), which already keeps everything in-boundary."""
    if project_dict is None:
        return (None, None, None, None, None)
    try:
        from src import zoning, shade
        from src import terrain as _terrain
        from src.placement_score import build_cell_env_map

        elev = zoning.site_elevation_grid(boundary, site_config)
        if not elev:
            return (None, None, None, None, None)
        shade_g = shade.shade_grid_for_design(project_dict, elev)
        zones = zoning.classify_zones(elev, shade_g)
        if not zones:
            return (None, None, None, None, None)

        def plant_zone_for(plant_id):
            try:
                from src.db.plants import get_plant
                return zoning.preferred_zone_for_plant(get_plant(plant_id) or {})
            except Exception:  # noqa: BLE001
                return None

        # Build scored cell map: slope + aspect extend the coarse zone routing
        # with continuous microsite signals (S-facing drier, steep = poor for
        # trees, etc.).  Best-effort — falls back to None on any failure.
        cell_env_map = None
        try:
            slope_g = _terrain.compute_slope_grid(elev)
            aspect_g = _terrain.compute_aspect_grid(elev)
            cells = grid_cells_in_boundary(boundary)
            if cells:
                cell_env_map = build_cell_env_map(
                    cells, shade_g, elev, slope_g, aspect_g)
        except Exception:  # noqa: BLE001
            cell_env_map = None

        return (elev, zones, plant_zone_for,
                zoning.preferred_zone_for_structure, cell_env_map)
    except Exception:  # noqa: BLE001 — zoning is best-effort
        return (None, None, None, None, None)


def _add_warning(project, message: str) -> None:
    """Append a one-off message to ``properties.generation_warnings``."""
    props = project.as_dict().setdefault("properties", {})
    props.setdefault("generation_warnings", []).append(message)


def _cell_dist_m(a: tuple, b: tuple) -> float:
    """Metres between two ``(lat, lng)`` points — local cos-lat model (matches
    the inline math in ``reserve_near`` / ``placement_score``)."""
    cos_lat = math.cos(a[0] * math.pi / 180) or 1e-9
    dx = (b[1] - a[1]) * 111320.0 * cos_lat
    dy = (b[0] - a[0]) * 111320.0
    return math.hypot(dx, dy)


class _Positioner:
    """Hands out placement positions, preferring a requested micro-zone.

    Built from either a zone→positions map (Tier-2 zoning available) or a flat
    in-boundary position list (Tier-1). ``take(zone)`` returns the next free
    position whose zone matches, else spills to NEUTRAL, else any remaining
    cell — so zoning *guides* placement without ever dropping a plant for lack
    of a perfect cell. ``remaining`` tracks capacity for trim-to-fit.

    Within a pool, ``take`` farthest-point-samples (V2.20): the first anchor
    is the most central free cell and each later anchor is the free cell
    farthest from everything already handed out — so groups distribute across
    the whole space. Before this, cells were consumed in the pool's row-major
    order and every design crammed along its north edge."""

    def __init__(self, zone_positions: Optional[dict], flat: list):
        self._by_zone: dict = {}
        if zone_positions:
            for z, pts in zone_positions.items():
                self._by_zone[z] = list(pts)
        # A flat fallback pool (used when no zoning, and as the final spill).
        self._flat = list(flat)
        self._used: set = set()
        # Farthest-point state: anchors handed out so far, each free cell's
        # distance to the nearest of them, and the pool centroid (the first
        # anchor grows the design from the middle of the space outward).
        self._taken_pts: list = []
        self._mindist: dict = {}
        pool = [p for pts in (self._pools()) for p in pts]
        if pool:
            self._centroid: Optional[tuple] = (
                sum(p[0] for p in pool) / len(pool),
                sum(p[1] for p in pool) / len(pool),
            )
        else:
            self._centroid = None

    def _pools(self) -> list:
        return list(self._by_zone.values()) if self._by_zone else [self._flat]

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

    def _pop_spread(self, lst: list):
        """Remove and return the best free cell in ``lst``: the most central
        cell for the first anchor, then the cell farthest from every anchor
        handed out so far (farthest-point sampling). Returns ``None`` when the
        list holds no free cell. Ties break toward the pool's row-major order,
        keeping selection deterministic."""
        lst[:] = [p for p in lst if p not in self._used]
        if not lst:
            return None
        if not self._taken_pts:
            c = self._centroid
            best = (min(lst, key=lambda p: _cell_dist_m(p, c))
                    if c is not None else lst[0])
        else:
            best = max(lst, key=lambda p: self._mindist.get(p, float("inf")))
        lst.remove(best)
        self._used.add(best)
        self._note_taken(best)
        return best

    def _note_taken(self, pt: tuple) -> None:
        """Fold a newly handed-out anchor into every free cell's running
        min-distance (one incremental pass keeps ``_pop_spread`` O(cells))."""
        self._taken_pts.append(pt)
        for pool in self._pools():
            for cell in pool:
                if cell in self._used:
                    continue
                d = _cell_dist_m(cell, pt)
                prev = self._mindist.get(cell)
                if prev is None or d < prev:
                    self._mindist[cell] = d

    def reserve_near(self, positions, radius_m: float) -> None:
        """Mark every still-free cell within ``radius_m`` of any of
        ``positions`` as used, so the next group's anchor lands elsewhere —
        this is what makes groups spread across the boundary instead of
        clumping. Cheap O(cells·positions) scan over the remaining pools."""
        if not positions or radius_m <= 0:
            return
        import math as _m
        pools = list(self._by_zone.values()) if self._by_zone else [self._flat]
        for pool in pools:
            for cell in pool:
                if cell in self._used:
                    continue
                cl = _m.cos(cell[0] * _m.pi / 180) or 1e-9
                for (la, ln) in positions:
                    dx = (cell[1] - ln) * 111320.0 * cl
                    dy = (cell[0] - la) * 111320.0
                    if dx * dx + dy * dy < radius_m * radius_m:
                        self._used.add(cell)
                        break

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
                p = self._pop_spread(self._by_zone.get(z, []))
                if p is not None:
                    return p
            return None
        return self._pop_spread(self._flat)


class ScoredPositioner:
    """Placement cell pool that picks ecologically optimal positions (V1.51).

    Scores every available cell for the requesting plant using
    :func:`src.placement_score.score_cell_for_plant` and returns the
    highest-scoring unoccupied one.  Falls back transparently to
    ``_Positioner`` zone-routing when ``cell_env_map`` is absent — so
    offline / terrain-unavailable cases keep working exactly as before.

    ``_bonus_cells`` carries temporary drip-line bonuses for the cells
    adjacent to a newly placed canopy tree; cleared after each non-tree
    group so the bonus doesn't bleed across unrelated placements."""

    def __init__(self, cell_env_map: Optional[dict],
                 zone_positions: Optional[dict],
                 flat: list,
                 elev: Optional[dict] = None):
        self._env_map = cell_env_map  # {(lat,lng): CellEnv} or None
        self._fallback = _Positioner(zone_positions, flat)
        # All available cells as a list so we can iterate and score.
        if zone_positions:
            all_pts: list = []
            for pts in zone_positions.values():
                all_pts.extend(pts)
            # Also include flat-only cells not in any zone bucket.
            zone_set = set(all_pts)
            for p in flat:
                if p not in zone_set:
                    all_pts.append(p)
            self._all = all_pts
        else:
            self._all = list(flat)
        self._used: set = set()
        self._bonus_cells: dict = {}   # {(lat,lng): float bonus addend}
        # Aesthetic context (V1.62): the pool's latitude span for the
        # tall-north/low-south gradient, and the groups anchored so far
        # for bed cohesion + repetition rhythm.
        if self._all:
            lats = [c[0] for c in self._all]
            self._lat_range: Optional[tuple] = (min(lats), max(lats))
        else:
            self._lat_range = None
        self._anchors: list = []   # [(lat, lng, plant_id, height_m), ...]
        # Spread state (V2.20): every cell handed out so far, each free
        # cell's distance to the nearest of them, and a saturation scale of
        # a quarter of the pool's diagonal. On a flat/uniform site the eco
        # scores tie and strict-> selection used to degenerate to "first
        # cell in row-major order" — every group along the north edge, with
        # bed cohesion then pulling the rest toward it. The spread term
        # breaks those ties toward unused ground so anchors distribute
        # across the whole space.
        self._spread_pts: list = []
        self._spread_mindist: dict = {}
        if self._all:
            lngs = [c[1] for c in self._all]
            diag = _cell_dist_m((min(lats), min(lngs)), (max(lats), max(lngs)))
            self._spread_scale_m = max(12.0, 0.25 * diag)
            self._pool_centroid: Optional[tuple] = (
                sum(lats) / len(lats), sum(lngs) / len(lngs))
        else:
            self._spread_scale_m = 12.0
            self._pool_centroid = None

    @property
    def remaining(self) -> int:
        return self._fallback.remaining

    def _pop_unused(self, lst: list):
        return self._fallback._pop_unused(lst)

    def note_anchor(self, cell: Optional[tuple], plant: dict) -> None:
        """Record an anchored group so later ``take_best`` calls can score
        bed cohesion and same-species rhythm against it."""
        if cell is None:
            return
        self._anchors.append((
            cell[0], cell[1], plant.get("id"),
            float(plant.get("mature_height_meters") or 0.0),
        ))

    def _spread_score(self, cell: tuple) -> float:
        """0–1 "uses new ground" term: the distance to the nearest
        already-taken cell, saturating at ``_spread_scale_m`` —
        farthest-point sampling expressed as a score term. Neutral (0.5)
        before anything is anchored: the FIRST anchor is decided by
        ecology + composition (e.g. the tall-north gradient sends a canopy
        tree to the north edge), with only an epsilon centrality tie-break
        in ``take_best`` so a flat, uniform site starts from the middle of
        the space instead of the pool's first row-major cell."""
        if not self._spread_pts:
            return 0.5
        d = self._spread_mindist.get(cell)
        if d is None:
            return 1.0
        return min(1.0, d / self._spread_scale_m)

    def _note_spread(self, cell: tuple) -> None:
        """Fold a newly taken cell into every free cell's running
        min-distance (one incremental pass keeps ``take_best`` O(cells))."""
        self._spread_pts.append(cell)
        for c in self._all:
            if c in self._used:
                continue
            d = _cell_dist_m(c, cell)
            prev = self._spread_mindist.get(c)
            if prev is None or d < prev:
                self._spread_mindist[c] = d

    def take_best(self, plant: dict,
                  zone: Optional[str] = None) -> Optional[tuple]:
        """Return the highest-scoring available cell for this plant.

        If ``cell_env_map`` is None, delegates to ``_Positioner.take(zone)``
        (which farthest-point-samples its pool).  Otherwise iterates all
        available cells, scoring each 65% on ecological fit
        (:func:`score_cell_for_plant`), 15% on composition
        (:func:`aesthetic_score` — tall-north gradient, bed cohesion,
        repetition rhythm) and 20% on spread (:meth:`_spread_score` — prefer
        unused ground), and picks the best; still returns something (the best
        of what remains) rather than None when capacity exists, matching
        ``_Positioner``'s never-drop-a-plant guarantee. Ecological fit stays
        dominant: a wet-obligate still beats the spread pull to a dry corner,
        because eco spans the full 0–1 while spread contributes at most 0.2."""
        if self._env_map is None:
            return self._fallback.take(zone)

        from src.placement_score import aesthetic_score, score_cell_for_plant
        best_cell: Optional[tuple] = None
        best_score = -1.0

        for cell in self._all:
            if cell in self._used:
                continue
            env = self._env_map.get(cell)
            if env is None:
                # Cell not in env map (e.g. added from flat fallback);
                # give it a neutral score so it can still be selected.
                eco = 0.5
            else:
                eco = score_cell_for_plant(plant, env)
            beauty = aesthetic_score(plant, cell,
                                     lat_range=self._lat_range,
                                     anchors=self._anchors)
            score = (0.65 * eco + 0.15 * beauty
                     + 0.20 * self._spread_score(cell))
            score += self._bonus_cells.get(cell, 0.0)
            if not self._spread_pts and self._pool_centroid is not None:
                # Epsilon-weight centrality: breaks exact ties toward the
                # middle of the pool for the first anchor without ever
                # outvoting a real ecological or compositional signal.
                d0 = _cell_dist_m(cell, self._pool_centroid)
                score += 1e-6 * max(0.0, 1.0 - d0 / self._spread_scale_m)
            if score > best_score:
                best_score = score
                best_cell = cell

        if best_cell is not None:
            self._used.add(best_cell)
            # Keep fallback in sync so remaining count stays accurate.
            self._fallback._used.add(best_cell)
            self._note_spread(best_cell)
            return best_cell
        return None

    def reserve_near(self, positions, radius_m: float) -> None:
        """Delegate to ``_Positioner.reserve_near``; also marks cells in our
        own ``_used`` set so ``take_best`` skips them."""
        self._fallback.reserve_near(positions, radius_m)
        self._used |= self._fallback._used

    def clear_bonus(self) -> None:
        """Clear temporary drip-line bonuses."""
        self._bonus_cells.clear()


def _apply_dripline_bonus(positioner: ScoredPositioner,
                          positions: list,
                          canopy_radius_m: float,
                          spacing_m: float) -> None:
    """Mark cells in the 0.5×–1.5× canopy-radius ring around each placed
    tree position with a +0.2 score bonus.  Subsequent understory plants
    are attracted to the drip-line — ecologically the most productive zone
    under a canopy tree."""
    if not positions or canopy_radius_m <= 0:
        return
    import math as _m
    cos_lat = _m.cos(positions[0][0] * _m.pi / 180) or 1e-9
    inner = 0.5 * canopy_radius_m
    outer = 1.5 * canopy_radius_m
    for cell in positioner._all:
        if cell in positioner._used:
            continue
        for (la, ln) in positions:
            dx = (cell[1] - ln) * 111320.0 * cos_lat
            dy = (cell[0] - la) * 111320.0
            dist = _m.hypot(dx, dy)
            if inner <= dist <= outer:
                positioner._bonus_cells[cell] = (
                    positioner._bonus_cells.get(cell, 0.0) + 0.2)
                break


# Ecological layer order — canopy trees anchor first so later groups
# get to fill the spaces around them (understory, groundcover last).
_LAYER_ORDER: dict = {
    "tree": 0, "shrub": 1, "vine": 2,
    "grass": 3, "herb": 4, "root": 5, "groundcover": 6,
}


# Density → fraction of the boundary's plantable capacity to fill (V1.50).
_DENSITY_FRACTION = {"sparse": 0.30, "balanced": 0.60, "full": 0.90}

# Absolute ceiling on auto-generated plants regardless of how large the boundary
# is — a generated starting design should be a workable seed the user refines,
# not thousands of markers that stall the map. (A 1 km² lot at balanced density
# would otherwise want ~thousands.)
_MAX_GENERATED_PLANTS = 300


def _boundary_capacity(boundary, keepout=None) -> int:
    """How many plants the boundary holds at the default healthy spacing, minus
    cells blocked by keep-out. The fill target is a fraction of this."""
    cells = grid_cells_in_boundary(boundary)
    if keepout:
        from src.exclusion import is_clear
        cells = [c for c in cells if is_clear(c[0], c[1], keepout)]
    return len(cells)


def _apply_density(plant_items, boundary, density: str, keepout=None):
    """Scale per-group quantities up so the design fills ``density`` × capacity,
    instead of placing one plant per group on a near-empty lot. Returns the
    (possibly expanded) plant_items. No-op without a boundary or for an unknown
    density. The extra is distributed round-robin **weighted by habit**
    (V2.20): herbaceous species expand 4× as fast as trees and 2× as fast as
    shrubs, so density fills the lot with the matrix/drift ground layer that
    carries a naturalistic design — equal expansion used to hand a 3,000 m²
    lot as many willows as wildflowers."""
    frac = _DENSITY_FRACTION.get((density or "").lower())
    if not frac or not plant_items or not boundary:
        return plant_items
    capacity = _boundary_capacity(boundary, keepout)
    target = max(len(plant_items), int(capacity * frac))
    target = min(target, _MAX_GENERATED_PLANTS)   # don't carpet a huge lot
    current = sum(it[1] for it in plant_items)
    if current >= target:
        return plant_items
    items = [list(it) if not isinstance(it, list) else it[:]
             for it in plant_items]
    # Normalise to 3 elements (plant_id, qty, layout).
    items = [[it[0], it[1], (it[2] if len(it) > 2 else "")] for it in items]
    weights = []
    for it in items:
        try:
            from src.db.plants import get_plant
            ptype = (get_plant(it[0]) or {}).get("plant_type", "")
        except Exception:  # noqa: BLE001
            ptype = ""
        weights.append(1 if ptype == "tree" else 2 if ptype == "shrub" else 4)
    sequence = [i for i, w in enumerate(weights) for _ in range(w)]
    i = 0
    while sum(it[1] for it in items) < target:
        items[sequence[i % len(sequence)]][1] += 1
        i += 1
        if i > target * 2:   # safety valve
            break
    return [tuple(it) for it in items]


def _plant_spacing_m(plant_id: int, default: float = _SPACING_M) -> float:
    """Healthy centre-to-centre spacing for a species — its mature canopy (or
    spacing) from the catalogue, floored so groups never pack absurdly tight."""
    try:
        from src.db.plants import get_plant
        row = get_plant(plant_id) or {}
        s = (row.get("mature_canopy_m") or row.get("spacing_meters")
             or row.get("spacing_m"))
        if s:
            return max(0.5, float(s))
    except Exception:  # noqa: BLE001
        pass
    return default


# Ecological massing (V2.20): a species repeats as several modest drifts
# distributed through the design — the Rainer/West "masses repeated in
# rhythm" pattern (P2, grown-not-designed) — rather than pooling its whole
# quantity in one blob at a single anchor. Per-drift member caps by habit:
# trees read as individuals or small groves, shrubs as clumps, herbaceous
# plants as drifts.
_DRIFT_MAX: dict = {"tree": 3, "shrub": 6}
_DRIFT_MAX_DEFAULT = 9


def _split_into_drifts(plant_items) -> list:
    """Split each ``(plant_id, qty, layout?)`` item into repeated groups of at
    most the habit's per-drift cap, so a species distributes across the space
    (farthest-point anchoring then pushes the repeats apart, and the rhythm
    aesthetic term rewards the recurrence). Item order is preserved — the
    stable layer sort in ``_place_within_boundary`` runs after this."""
    from src.db.plants import get_plant
    out: list = []
    for item in plant_items:
        pid, qty = item[0], max(1, int(item[1] or 1))
        group_layout = item[2] if len(item) > 2 else ""
        try:
            ptype = (get_plant(pid) or {}).get("plant_type", "")
        except Exception:  # noqa: BLE001
            ptype = ""
        cap = _DRIFT_MAX.get(ptype, _DRIFT_MAX_DEFAULT)
        while qty > 0:
            take = min(qty, cap)
            out.append((pid, take, group_layout))
            qty -= take
    return out


def _place_within_boundary(project, plant_items, community_groups,
                           structure_items, boundary,
                           center: tuple[float, float],
                           elev: Optional[dict] = None,
                           zones: Optional[dict] = None,
                           plant_zone_for=None,
                           structure_zone_for=None,
                           keepout=None,
                           cell_env_map: Optional[dict] = None,
                           fill_regions=None,
                           community_mixes: Optional[list] = None,
                           plant_mixes: Optional[list] = None) -> None:
    """Place plants (in their requested LAYOUT pattern), communities and
    structures so everything lands inside the boundary, avoids keep-out zones
    (existing trees/buildings/water structures), and spreads to use the space.

    V1.51: Plants are placed in ecological layer order (trees first,
    groundcover last) using scored cell selection when terrain data is
    available — continuous shade, moisture, slope, and edge-preference scores
    replace the coarse four-bucket zone system for anchor selection.  A
    drip-line bonus attracts understory plants to the productive zone around
    newly placed canopy trees.  Companion proximity warnings are appended to
    ``generation_warnings`` after placement.  Falls back to the V1.50
    zone-routing positioner when terrain data is absent."""
    from src.db.polycultures import (
        get_polyculture_by_id, community_natural_radius,
    )
    from src import layout as _layout
    from src.exclusion import is_clear
    from src.db.plants import get_plant, get_plant_uses

    keepout = keepout or []

    # Build the anchor pool: zoned (clipped to boundary) or flat — and drop any
    # anchor that sits inside a keep-out circle so we never seed a group there.
    zpos = None
    if elev and zones:
        try:
            from src import zoning
            zpos = zoning.zone_positions(elev, zones, boundary)
        except Exception:  # noqa: BLE001
            zpos = None
    flat = positions_in_boundary(boundary, 10_000, center)  # full cell pool
    if keepout:
        flat = [p for p in flat if is_clear(p[0], p[1], keepout)]
        if zpos:
            zpos = {z: [p for p in pts if is_clear(p[0], p[1], keepout)]
                    for z, pts in zpos.items()}
    # Steer planting INTO drawn restoration / lawn-conversion zones when any are
    # present (F5): restrict the anchor pool to cells inside those rings. Guarded
    # so a tiny/empty zone set never starves placement — fall back to the whole
    # boundary if the restriction leaves nothing.
    if fill_regions:
        from src.geometry import point_in_ring

        def _in_fill(la, ln):
            return any(point_in_ring(la, ln, r) for r in fill_regions)

        ff = [p for p in flat if _in_fill(p[0], p[1])]
        if ff:
            flat = ff
            if zpos:
                zpos = {z: [p for p in pts if _in_fill(p[0], p[1])]
                        for z, pts in zpos.items()}

    positioner = ScoredPositioner(cell_env_map, zpos, flat, elev=elev)

    def _clip_keepout(positions, half_canopy_m=0.0):
        """Keep only positions inside the boundary AND clear of keep-out."""
        out = []
        for la, ln in positions:
            if boundary and not _inside_boundary(boundary, la, ln):
                continue
            if not is_clear(la, ln, keepout, half_canopy_m):
                continue
            out.append((la, ln))
        return out

    # ── Plant groups: layer-ordered, ecologically scored ───────────────────
    # Sort by ecological layer so canopy trees anchor first and subsequent
    # groups fill around them (stable sort preserves LLM order within layers).
    def _layer_rank(item):
        try:
            row = get_plant(item[0]) or {}
            return _LAYER_ORDER.get(row.get("plant_type", ""), 7)
        except Exception:  # noqa: BLE001
            return 7

    plant_items_sorted = sorted(_split_into_drifts(plant_items),
                                key=_layer_rank)

    for group_i, item in enumerate(plant_items_sorted):
        plant_id, qty = item[0], item[1]
        group_layout = item[2] if len(item) > 2 else ""
        zone = None
        if plant_zone_for is not None:
            try:
                zone = plant_zone_for(plant_id)
            except Exception:  # noqa: BLE001
                zone = None

        # Fetch plant row once; embed use tags so scorer can read them without
        # an extra DB call per cell.
        plant_row = get_plant(plant_id) or {}
        try:
            plant_row["_uses"] = set(get_plant_uses(plant_id))
        except Exception:  # noqa: BLE001
            plant_row["_uses"] = set()

        anchor = positioner.take_best(plant_row, zone)
        if anchor is None:
            break
        positioner.note_anchor(anchor, plant_row)
        if not group_layout:
            group_layout = _layout.default_layout_for(
                plant_row.get("plant_type", ""))
        spacing = _plant_spacing_m(plant_id)
        # Per-group seed: repeated drifts of one species get different
        # jitter/bearings instead of identical stamps (still deterministic).
        positions = _layout.positions_for_layout(
            group_layout, anchor[0], anchor[1], qty, spacing, seed=group_i)
        positions = _clip_keepout(positions, half_canopy_m=spacing / 2.0)
        if not positions:
            # The pattern fell outside / onto keep-out — fall back to the anchor.
            positions = [anchor]
        for la, ln in positions:
            project.place_plant(plant_id, la, ln, quantity=1)
        # Reserve the group's footprint so later groups don't reuse those cells.
        positioner.reserve_near(positions, spacing)

        # After placing a canopy tree, attract understory plants to the
        # drip-line ring; clear the bonus once a non-tree group has used it.
        plant_type = plant_row.get("plant_type", "")
        height = plant_row.get("mature_height_meters") or 0
        is_canopy = plant_type == "tree" and (height or 0) >= 4.0
        if is_canopy:
            canopy_r = plant_row.get("mature_canopy_m") or spacing
            _apply_dripline_bonus(positioner, positions,
                                  float(canopy_r), spacing)
        elif positioner._bonus_cells:
            positioner.clear_bonus()

    # ── Plant mixes: several species interleaved through ONE stand ─────────
    # The generator's equivalent of the panel's "Place Mix": one pattern of
    # positions, one species per position by weight ratio — the same
    # assign_species("even_split") the manual pattern handler uses, so the
    # generated stand rotates species exactly like a hand-placed one.
    from src.polyculture import assign_species, resolve_spacing
    for mix_i, mix in enumerate(plant_mixes or []):
        members = mix.get("members") or []
        if not members:
            continue
        species_items = [{
            "id": pid,
            "weight": w,
            "spacing_m": _plant_spacing_m(pid),
        } for pid, w in members]
        # "max" mirrors the manual mix default: centre-to-centre spacing wide
        # enough that no member's canopy overlaps its neighbour.
        spacing = resolve_spacing(species_items, "max")
        first_row = get_plant(members[0][0]) or {}
        zone = None
        if plant_zone_for is not None:
            try:
                zone = plant_zone_for(members[0][0])
            except Exception:  # noqa: BLE001
                zone = None
        anchor = positioner.take_best(first_row, zone)
        if anchor is None:
            break
        positioner.note_anchor(anchor, first_row)
        layout_name = mix.get("layout") or _layout.DRIFT
        positions = _layout.positions_for_layout(
            layout_name, anchor[0], anchor[1], int(mix.get("quantity") or 1),
            spacing, seed=1000 + mix_i)
        positions = _clip_keepout(positions, half_canopy_m=spacing / 2.0)
        if not positions:
            positions = [anchor]
        for (la, ln), pick in zip(positions,
                                  assign_species(positions, species_items,
                                                 "even_split")):
            project.place_plant(pick["id"], la, ln, quantity=1)
        positioner.reserve_near(positions, spacing)

    # ── Communities: only where the whole footprint fits + clears keep-out ──
    skipped_comms = 0

    def _community_radius(cid: int) -> float:
        try:
            return community_natural_radius(get_polyculture_by_id(cid))
        except Exception:  # noqa: BLE001
            return 1.0

    def _place_community_at(cid: int, anchor, radius: float) -> bool:
        """One community instance at ``anchor`` if its footprint fits the
        boundary and clears keep-out; reserves the footprint on success."""
        if (community_fits(boundary, anchor, radius)
                and is_clear(anchor[0], anchor[1], keepout, radius)):
            project.place_polyculture(cid, anchor[0], anchor[1])
            positioner.note_anchor(anchor, {})
            positioner.reserve_near([anchor], radius * 2)
            return True
        return False

    def _community_anchors(count: int, layout_name: str, spacing: float,
                           seed: int) -> list:
        """``count`` candidate anchors: a pattern around the best free cell
        when a layout was requested, else independently spread best cells.
        Always at least one take_best anchor; pattern positions that fall
        outside/onto keep-out are topped up with spread anchors."""
        first = positioner.take_best({}, None)
        if first is None:
            return []
        anchors: list = []
        if layout_name and count > 1:
            candidates = _layout.positions_for_layout(
                layout_name, first[0], first[1], count, spacing, seed=seed)
            anchors = _clip_keepout(candidates)[:count]
        if not anchors:
            anchors = [first]
        while len(anchors) < count:
            extra = positioner.take_best({}, None)
            if extra is None:
                break
            anchors.append(extra)
        return anchors

    for group_i, group in enumerate(community_groups or []):
        cid = group["id"] if isinstance(group, dict) else group
        count = int(group.get("count") or 1) if isinstance(group, dict) else 1
        layout_name = (group.get("layout") or "") if isinstance(group, dict) \
            else ""
        radius = _community_radius(cid)
        anchors = _community_anchors(count, layout_name,
                                     spacing=max(radius * 2.0, 4.0),
                                     seed=2000 + group_i)
        if not anchors:
            break
        placed = sum(1 for a in anchors if _place_community_at(cid, a, radius))
        skipped_comms += count - placed

    # ── Community mixes: N pockets, each one community picked by ratio ─────
    # Mirrors the Communities tab's "mix as pattern": the same
    # assign_species("even_split") the manual handler uses decides which
    # community each pocket becomes, so a 2:1 mix over six pockets is
    # exactly four of one and two of the other.
    for mix_i, mix in enumerate(community_mixes or []):
        members = mix.get("members") or []
        if not members:
            continue
        radii = {cid: _community_radius(cid) for cid, _ in members}
        spacing = max(max(radii.values()) * 2.0, 4.0)
        anchors = _community_anchors(int(mix.get("count") or len(members)),
                                     mix.get("layout") or "",
                                     spacing, seed=3000 + mix_i)
        if not anchors:
            break
        items = [{"id": cid, "weight": w} for cid, w in members]
        for anchor, pick in zip(anchors,
                                assign_species(anchors, items, "even_split")):
            cid = int(pick["id"])
            if not _place_community_at(cid, anchor, radii[cid]):
                skipped_comms += 1

    # ── Structures: route to preferred zone (water → wet/low) ──────────────
    for struct_id in structure_items:
        zone = None
        if structure_zone_for is not None:
            try:
                zone = structure_zone_for(struct_id)
            except Exception:  # noqa: BLE001
                zone = None
        anchor = positioner.take_best({}, zone)
        if anchor is None:
            break
        project.place_structure(struct_id, anchor[0], anchor[1])

    if skipped_comms:
        _add_warning(project,
                     f"Skipped {skipped_comms} plant communit"
                     + ("ies" if skipped_comms != 1 else "y")
                     + " that did not fit inside the boundary or clear an "
                     "existing feature.")

    # ── Companion proximity check (post-placement warnings only) ───────────
    try:
        from src.placement_score import build_companion_graph, check_companion_spacing
        placed = project.placed_plants
        unique_ids = list({p.get("plant_id") for p in placed
                           if p.get("plant_id") is not None})
        if len(unique_ids) > 1:
            graph = build_companion_graph(unique_ids)
            for w in check_companion_spacing(placed, graph):
                _add_warning(project, w)
    except Exception:  # noqa: BLE001 — companion checking is best-effort
        pass


# ── Goal feedback + offline fallback ─────────────────────────────────────────

_OFFLINE_PLANT_CAP = 7  # how many individual plants the no-LLM path places

# Habit buckets for the offline pick, in round-robin priority order: the
# herbaceous matrix carries a naturalistic design, but one pass across all
# buckets first guarantees vertical layers (a habitat-score component and
# basic ecological structure) before forbs/grasses fill the remaining slots.
_OFFLINE_BUCKETS: tuple = (
    ("wildflower", "herb"),
    ("grass", "sedge", "rush"),
    ("shrub",),
    ("tree",),
    ("groundcover", "vine", "fern"),
)


def _rank_offline_plants(plants: list) -> list:
    """Order offline candidates by ecological value for a site whose moisture
    is unknown: keystone / larval-host / pollinator / bird-food species first,
    wetland and aquatic specialists last (P9 — with no site moisture data,
    don't gamble the design on a bog), then round-robin across habit buckets
    so the capped pick spans vertical layers instead of taking the first N
    alphabetical catalogue rows. Deterministic: ties keep catalogue order."""
    def value(p: dict) -> int:
        uses = p.get("permaculture_uses") or ""
        v = 0
        if "keystone_species" in uses:
            v += 3
        if "host_plant" in uses:
            v += 2
        if "pollinator" in uses:
            v += 1
        if "bird_food" in uses:
            v += 1
        water = (p.get("water_needs") or "").lower()
        if (p.get("plant_type") or "").lower() == "aquatic" or "high" in water:
            v -= 6
        return v

    buckets: dict = {b: [] for b in _OFFLINE_BUCKETS}
    other: list = []   # aquatic / unknown habits — no guaranteed slot
    for p in plants:
        pt = (p.get("plant_type") or "").lower()
        for b in _OFFLINE_BUCKETS:
            if pt in b:
                buckets[b].append(p)
                break
        else:
            other.append(p)

    # Two tiers per bucket: sound generalist picks first, moisture-extreme
    # specialists (negative value) only after every bucket's good candidates —
    # so a bog plant reaches a generic design only when the pool is truly thin.
    good_pools: list = []
    bad_pools: list = []
    for b in _OFFLINE_BUCKETS:
        pool = sorted(buckets[b], key=value, reverse=True)  # stable sort
        good_pools.append([p for p in pool if value(p) >= 0])
        bad_pools.append([p for p in pool if value(p) < 0])
    other.sort(key=value, reverse=True)

    ordered: list = []

    def _robin(pools: list) -> None:
        while True:
            took = False
            for pool in pools:
                if pool:
                    ordered.append(pool.pop(0))
                    took = True
            if not took:
                return

    _robin(good_pools)
    _robin(bad_pools)
    ordered.extend(other)
    return ordered


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


# Ecoregion key → the human words seeded community names use, so an
# ecoregion-tagged site prefers its matching community (aspen_parkland →
# "Aspen Parkland Edge", riparian → "Riparian Willow Thicket", …).
_ECOREGION_WORDS = {
    "aspen_parkland":     "aspen parkland",
    "mixedgrass_prairie": "mixedgrass",
    "fescue_foothills":   "foothills",
    "boreal_mixedwood":   "boreal",
    "riparian":           "riparian",
    "wet_meadow":         "wet meadow",
    "subalpine_montane":  "subalpine",
}


def _select_offline_communities(communities: list[dict], goals, site_config,
                                budget, max_n: int = 3) -> list[int]:
    """Pick up to ``max_n`` seeded communities that fit the goals + site for the
    no-LLM path, scored by goal-name match (+2 each) and ecoregion-name match
    (+3). This is the D2 upgrade: the offline design lays down a couple of
    grounded plant communities instead of a single default. Falls back to one
    sensible default when nothing scores and there's no budget pressure."""
    if not communities:
        return []
    from src.design_goals import community_name_hints
    hints = [h.lower() for h in (community_name_hints(goals) or []) if h]
    eco_word = _ECOREGION_WORDS.get((site_config or {}).get("ecoregion_key"))

    def _score(c: dict) -> int:
        text = ((c.get("name") or "") + " " + (c.get("description") or "")).lower()
        s = sum(2 for h in hints if h in text)
        if eco_word and eco_word in text:
            s += 3
        return s

    scored = [(_score(c), c) for c in communities]
    # stable sort keeps catalogue order among equal scores
    scored.sort(key=lambda t: t[0], reverse=True)
    picks = [c for sc, c in scored if sc > 0][:max_n]
    if not picks and not budget:
        picks = [communities[0]]
    return [c["id"] for c in picks if c.get("id") is not None]


_MEADOW_MATRIX_TYPES = ("grass", "sedge", "rush")
_MEADOW_FORB_TYPES = ("wildflower", "herb")


def _offline_plant_mix(ranked_pool: list, capacity: int,
                       frac: float) -> Optional[dict]:
    """The offline path's signature meadow gesture: ONE interleaved stand of
    matrix grass + flowering forbs (the Rainer/West ground layer), built
    deterministically from the ranked site/goal-fit pool. Returns a
    plant-mix dict (same shape the LLM spec resolves to) or None when the
    pool can't support one (no grass and fewer than three forbs).

    The stand is sized from the site's plantable capacity so a small yard
    gets a pocket meadow and an acreage gets a real sweep — clamped to
    [8, 48] plants (the mix supplements the individual drifts, it doesn't
    replace the whole design)."""
    matrix = next((p for p in ranked_pool
                   if p.get("plant_type") in _MEADOW_MATRIX_TYPES), None)
    forbs = [p for p in ranked_pool
             if p.get("plant_type") in _MEADOW_FORB_TYPES
             and (matrix is None or p["id"] != matrix["id"])][:3]
    if matrix is not None and forbs:
        # Matrix-dominant: 3 parts grass to 1 part each forb.
        members = [(matrix["id"], 3)] + [(f["id"], 1) for f in forbs[:2]]
    elif matrix is None and len(forbs) >= 3:
        members = [(f["id"], 1) for f in forbs]   # wildflower blend
    else:
        return None
    quantity = max(8, min(48, int((capacity or 20) * (frac or 0.6) * 0.35)))
    return {"members": members, "quantity": quantity, "layout": "drift"}


def _offline_community_plan(community_ids: list[int],
                            capacity: int) -> tuple[list, list]:
    """Turn the ranked offline community picks into placement structures:
    one pick → a repeated group (two pockets when the site has room),
    several picks → a weighted mosaic (top pick dominant 2:1), pockets
    scaled by plantable capacity. Returns ``(community_groups,
    community_mixes)`` — the same shapes the LLM spec resolves to."""
    ids = [cid for cid in (community_ids or []) if cid is not None]
    if not ids:
        return [], []
    roomy = (capacity or 0) >= 24     # ~4+ of the 6 m anchor cells per pocket
    if len(ids) == 1:
        return [{"id": ids[0], "count": 2 if roomy else 1,
                 "layout": ""}], []
    pockets = min(_MAX_MIX_POCKETS,
                  len(ids) + (2 if (capacity or 0) >= 48 else 1 if roomy
                              else 0))
    members = [(ids[0], 2)] + [(cid, 1) for cid in ids[1:]]
    return [], [{"members": members, "count": pockets, "layout": ""}]


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
                            match_site: bool = True,
                            density: str = "balanced",
                            existing_features: Optional[list] = None):
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

    # Rank the pool ecologically before capping — pre-V2.20 the cap took the
    # first N rows in catalogue (alphabetical) order, which led generic yards
    # with "B..." wetland specialists (Bog Cranberry, Buckbean, ...).
    plants = _rank_offline_plants(plants)

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
            for pl in _rank_offline_plants(hits):
                if pl["id"] not in seen:
                    seen.add(pl["id"]); chosen.append(pl)
        for pl in plants:
            if pl["id"] not in seen:
                seen.add(pl["id"]); chosen.append(pl)
        plants = chosen

    # (plant_id, qty, layout) with a habit-based default layout; the offline
    # path has no LLM to choose a pattern. Quantities/fill are sized later by
    # the density-aware space-fill in _place_within_boundary.
    from src.layout import default_layout_for
    plant_items = [(p["id"], 1, default_layout_for(p.get("plant_type", "")))
                   for p in plants[:_OFFLINE_PLANT_CAP]]

    communities = list_polycultures()
    # D2: place a couple of site/goal-fit communities as grouped units, not a
    # single default — scored by goal + ecoregion name match.
    community_ids = _select_offline_communities(
        communities, goals, site_config, budget)

    project = Project.create(name, site_config=site_config, boundary=boundary)
    elev, zones, pzone, szone, cell_env_map = _zone_context(
        boundary, site_config, project.as_dict() if match_site else None)
    # F5: the user's existing drawn layer steers placement — keep out of
    # existing-remnant zones / hardscape / existing trees & buildings, and fill
    # into drawn restoration / lawn-conversion zones.
    from src.exclusion import keepout_circles, fill_regions
    _ctx = {"features": existing_features or []}
    keepout = keepout_circles(project.as_dict()) + keepout_circles(_ctx)
    fills = fill_regions(_ctx)

    # V2.23: the offline path speaks the full placement vocabulary too.
    # A matrix-grass + forbs meadow mix replaces those species' stand-alone
    # drifts (sized by the site's plantable capacity), and the selected
    # communities become repeated pockets / a weighted mosaic instead of
    # one instance each — the same structures the LLM spec produces, placed
    # by the same engine.
    capacity = _boundary_capacity(boundary, keepout)
    frac = _DENSITY_FRACTION.get((density or "balanced").lower()) or 0.6
    p_mixes: list[dict] = []
    meadow = _offline_plant_mix(plants[:_OFFLINE_PLANT_CAP * 2],
                                capacity, frac)
    if meadow:
        p_mixes.append(meadow)
        in_mix = {pid for pid, _ in meadow["members"]}
        plant_items = [it for it in plant_items if it[0] not in in_mix]
    c_groups, c_mixes = _offline_community_plan(community_ids, capacity)

    plant_items, p_mixes, c_groups, c_mixes, budget_dropped = \
        _trim_spec_to_budget(plant_items, p_mixes, c_groups, c_mixes, budget)

    if not plant_items and not c_groups and not p_mixes and not c_mixes:
        raise LLMError(
            "offline generation found no plants or communities to place"
        )

    plant_items = _apply_density(plant_items, boundary, density, keepout)
    _place_within_boundary(project, plant_items, c_groups, [],
                           boundary, center, elev=elev, zones=zones,
                           plant_zone_for=pzone, structure_zone_for=szone,
                           keepout=keepout,
                           cell_env_map=cell_env_map, fill_regions=fills,
                           community_mixes=c_mixes, plant_mixes=p_mixes)

    # The deterministic critic runs offline too (V1.62): score the placed
    # design and mend the most impactful gaps straight from the catalogue.
    from src.design_critic import apply_repairs
    for msg in apply_repairs(
            project, query_plants,
            lambda: _one_position_in_boundary(boundary, center)):
        _add_warning(project, msg)

    _apply_goal_feedback(project, goals, query_plants, center, boundary)
    _apply_fauna_feedback(project, fauna_ids, query_plants, center, boundary)
    _record_budget_note(project, project.placed_plants, budget, budget_dropped)
    return project
