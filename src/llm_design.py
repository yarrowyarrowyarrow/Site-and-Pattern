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
    "native_only", "pollinator_only", "host_plant_only",
    "keystone_only", "bird_food_only", "ab_ecoregion",
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

    def generate_spec(self, prompt: str, context: dict) -> dict:
        """Ask the model for a design spec and parse it into a dict."""
        content = self.chat(_build_messages(prompt, context))
        return _parse_spec_json(content)


def _build_messages(prompt: str, context: dict) -> list[dict]:
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


def _resolve_plants(entries: list, query_plants) -> list[tuple[int, int]]:
    """Map each spec plant entry to ``(plant_id, quantity)`` via the catalogue.
    Entries that resolve to nothing are skipped."""
    out: list[tuple[int, int]] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        qty = _coerce_qty(e.get("quantity", 1))
        results: list[dict] = []
        filters = e.get("filters")
        if isinstance(filters, dict) and filters:
            try:
                results = query_plants(**_clean_filters(filters))
            except Exception:  # noqa: BLE001 — fall back to text search
                results = []
        if not results:
            term = e.get("query") or e.get("common_name") or e.get("name") or ""
            if str(term).strip():
                try:
                    results = query_plants(query=str(term).strip())
                except Exception:  # noqa: BLE001
                    results = []
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
                    model: Optional[str] = None):
    """Generate a :class:`~src.permadesign_api.Project` from a prompt.

    The site location comes from ``boundary`` (centroid) or
    ``site_config['latitude'/'longitude']`` — one is required, since placed
    geometry needs an anchor. ``client`` can be injected (tests pass a fake);
    otherwise an :class:`LLMClient` is built from ``endpoint``/``model``/env/
    config.

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
    }

    spec = client.generate_spec(prompt, context)
    _validate_spec(spec)

    plant_items = _resolve_plants(spec.get("plants") or [], query_plants)
    community_items = _resolve_communities(spec.get("communities") or [], communities)
    structure_items = _resolve_structures(spec.get("structures") or [], structures)

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

    return project
