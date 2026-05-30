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
  integer (default 1).
- "communities[].query" must loosely match one of the AVAILABLE COMMUNITIES
  listed below.
- "structures[].structure_id" must be one of the AVAILABLE STRUCTURE IDS
  listed below.
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


def _build_messages(prompt: str, context: dict,
                    extra_hints: Optional[list] = None) -> list[dict]:
    names = context.get("community_names") or []
    sids = context.get("structure_ids") or []
    site = context.get("site") or {}
    lines = [_SYSTEM_PROMPT, ""]
    lines.append("AVAILABLE COMMUNITIES: " + ", ".join(names) if names
                 else "AVAILABLE COMMUNITIES: (none)")
    lines.append("AVAILABLE STRUCTURE IDS: " + ", ".join(str(s) for s in sids)
                 if sids else "AVAILABLE STRUCTURE IDS: (none)")
    if site.get("latitude") is not None and site.get("longitude") is not None:
        lines.append(f"SITE: lat {site['latitude']}, lng {site['longitude']}"
                     + (f", hardiness zone {site['hardiness_zone']}"
                        if site.get("hardiness_zone") else ""))
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


def generate_design(prompt: str, *, site_config: Optional[dict] = None,
                    boundary: Optional[list] = None,
                    name: str = "Generated Design",
                    client: Optional[LLMClient] = None,
                    endpoint: Optional[str] = None,
                    model: Optional[str] = None,
                    goals: Optional[list] = None,
                    budget: Optional[float] = None,
                    fauna_ids: Optional[list] = None):
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
    context = {
        "community_names": [c.get("name") for c in communities if c.get("name")],
        "structure_ids": [s.get("id") for s in structures if s.get("id")],
        "site": dict(site_config or {}),
        "fauna_note": _fauna_digest(),
    }

    from src.design_goals import filters_for_goals, hints_for_goals
    goal_filters = filters_for_goals(goals)

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
    positions = _grid_positions(
        center[0], center[1],
        len(plant_items) + len(community_items) + len(structure_items),
    )
    idx = 0
    for plant_id, qty in plant_items:
        lat, lng = positions[idx]; idx += 1
        project.place_plant(plant_id, lat, lng, quantity=qty)
    for poly_id in community_items:
        lat, lng = positions[idx]; idx += 1
        project.place_polyculture(poly_id, lat, lng)
    for struct_id in structure_items:
        lat, lng = positions[idx]; idx += 1
        project.place_structure(struct_id, lat, lng)

    _apply_goal_feedback(project, goals, query_plants, center)
    _apply_fauna_feedback(project, fauna_ids, query_plants, center)
    _record_budget_note(project, project.placed_plants, budget, budget_dropped)
    return project


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


def _apply_fauna_feedback(project, fauna_ids, query_plants,
                          center: tuple[float, float]) -> None:
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
            lat, lng = _grid_positions(center[0], center[1], 1)[0]
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
                         center: tuple[float, float]) -> None:
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
                lat, lng = _grid_positions(center[0], center[1], 1)[0]
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
                            fauna_ids: Optional[list] = None):
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

    goal_filters = filters_for_goals(goals) or {"native_only": True}
    try:
        plants = query_plants(**goal_filters)
    except Exception:  # noqa: BLE001
        plants = []
    if not plants:  # goals too restrictive — widen so we still produce a design
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
    positions = _grid_positions(
        center[0], center[1], len(plant_items) + len(community_items))
    idx = 0
    for plant_id, qty in plant_items:
        lat, lng = positions[idx]; idx += 1
        project.place_plant(plant_id, lat, lng, quantity=qty)
    for poly_id in community_items:
        lat, lng = positions[idx]; idx += 1
        project.place_polyculture(poly_id, lat, lng)

    _apply_goal_feedback(project, goals, query_plants, center)
    _apply_fauna_feedback(project, fauna_ids, query_plants, center)
    _record_budget_note(project, project.placed_plants, budget, budget_dropped)
    return project
