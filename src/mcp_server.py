"""
mcp_server.py — Model Context Protocol server exposing PermaDesign to
AI agents (Claude Code and any other MCP client).

Like the CLI, this is a thin shell over the Qt-free scripting facade
(:mod:`src.permadesign_api`). The actual tool logic lives in plain
module-level ``tool_*`` functions that take and return JSON-friendly
values — so they're unit-testable WITHOUT the MCP SDK installed. The
MCP plumbing (server construction + stdio run loop) is isolated in
:func:`build_server` / :func:`main`, guarded behind an import of the
``mcp`` package with a clear install message if it's missing.

Mutation tools are stateless and file-based: they take a
``project_path``, load it, apply one change, and save it back. That
matches MCP's request/response model — no session state to lose between
calls — and means an agent's edits are durable on disk immediately.

Run it (after ``pip install 'permadesign[mcp]'`` or ``pip install mcp``)::

    python -m src.mcp_server

then point an MCP client at that stdio command. See README.md →
"AI agent usage (MCP)".
"""

from __future__ import annotations

from typing import Any, Optional

from src.permadesign_api import (
    Project,
    query_plants,
    list_polycultures,
    list_structures,
    run_analysis,
    export_plant_catalogue_docx,
)


# ── Tool logic (plain, testable; no MCP dependency) ─────────────────────────

def tool_query_plants(
    text: str = "",
    *,
    plant_type: str = "",
    zone: Optional[int] = None,
    native_only: bool = False,
    pollinator_only: bool = False,
    host_plant_only: bool = False,
    keystone_only: bool = False,
    bird_food_only: bool = False,
    ab_ecoregion: str = "",
    limit: int = 50,
) -> list[dict]:
    """Search the plant catalogue. Returns matching plant dicts (each has
    ``id`` and ``common_name``), capped at ``limit``."""
    filters: dict[str, Any] = {}
    if text:
        filters["query"] = text
    if plant_type:
        filters["plant_type"] = plant_type
    if zone is not None:
        filters["zone"] = zone
    if native_only:
        filters["native_only"] = True
    if pollinator_only:
        filters["pollinator_only"] = True
    if host_plant_only:
        filters["host_plant_only"] = True
    if keystone_only:
        filters["keystone_only"] = True
    if bird_food_only:
        filters["bird_food_only"] = True
    if ab_ecoregion:
        filters["ab_ecoregion"] = ab_ecoregion
    results = query_plants(**filters)
    return results[:limit] if limit else results


def tool_list_communities() -> list[dict]:
    """List the seeded plant communities (polycultures). Each has an
    ``id`` to pass to ``place_community``."""
    return list_polycultures()


def tool_list_structures() -> list[dict]:
    """List the habitat-structure catalogue. Each has an ``id`` to pass
    to ``place_structure``."""
    return list_structures()


def tool_create_project(
    project_path: str,
    name: str = "Untitled Design",
    boundary: Optional[list[list[float]]] = None,
) -> dict:
    """Create a new project file at ``project_path``.

    ``boundary`` is an optional list of ``[lat, lng]`` pairs for the
    property outline. Returns a short summary of the created project.
    """
    coords = [(float(la), float(ln)) for la, ln in (boundary or [])]
    project = Project.create(name, boundary=coords or None)
    project.save(project_path)
    return _summary(project, project_path)


def tool_place_plant(
    project_path: str, plant_id: int, lat: float, lng: float,
) -> dict:
    """Load the project, place one plant at ``(lat, lng)``, save it back."""
    project = Project.load(project_path)
    project.place_plant(int(plant_id), float(lat), float(lng))
    project.save(project_path)
    return _summary(project, project_path)


def tool_place_community(
    project_path: str, polyculture_id: int,
    center_lat: float, center_lng: float,
) -> dict:
    """Load the project, place a full plant community centred at
    ``(center_lat, center_lng)``, save it back."""
    project = Project.load(project_path)
    project.place_polyculture(int(polyculture_id), float(center_lat), float(center_lng))
    project.save(project_path)
    return _summary(project, project_path)


def tool_place_structure(
    project_path: str, structure_id: str, lat: float, lng: float,
) -> dict:
    """Load the project, place a habitat structure at ``(lat, lng)``,
    save it back."""
    project = Project.load(project_path)
    project.place_structure(str(structure_id), float(lat), float(lng))
    project.save(project_path)
    return _summary(project, project_path)


def tool_analyze_project(project_path: str) -> dict:
    """Load the project and return its habitat-score analysis."""
    project = Project.load(project_path)
    return run_analysis(project)


def tool_project_summary(project_path: str) -> dict:
    """Return a quick summary of a saved project (name, counts, warnings)."""
    project = Project.load(project_path)
    return _summary(project, project_path)


def tool_export_catalogue(out_path: str) -> dict:
    """Export the full plant catalogue to a .docx at ``out_path``."""
    written = export_plant_catalogue_docx(out_path)
    return {"path": written}


def tool_generate_design(
    project_path: str, prompt: str,
    lat: Optional[float] = None, lng: Optional[float] = None,
    endpoint: str = "", model: str = "",
) -> dict:
    """Generate a starting design from a natural-language ``prompt`` using a
    local OpenAI-compatible LLM (default: Ollama), save it to
    ``project_path``, and return a summary.

    ``lat``/``lng`` anchor the placed geometry. ``endpoint``/``model``
    override the LLM target (otherwise env vars / config / local default).
    Raises ``LLMError`` if the endpoint is unreachable or the response can't
    be turned into a valid design.
    """
    from src.llm_design import generate_design, LLMClient
    site_config = None
    if lat is not None and lng is not None:
        site_config = {"latitude": float(lat), "longitude": float(lng)}
    client = LLMClient(endpoint=endpoint or None, model=model or None)
    project = generate_design(str(prompt), site_config=site_config, client=client)
    project.save(project_path)
    return _summary(project, project_path)


def _summary(project: Project, path: str) -> dict:
    return {
        "path": path,
        "name": project.name,
        "n_plants": len(project.placed_plants),
        "n_structures": len(project.structures),
        "warnings": project.validate(),
    }


# Registry — single source of truth for the tool surface. build_server()
# registers each entry; tests assert against it without needing the SDK.
TOOL_SPECS: list[dict] = [
    {"name": "query_plants",     "func": tool_query_plants},
    {"name": "list_communities", "func": tool_list_communities},
    {"name": "list_structures",  "func": tool_list_structures},
    {"name": "create_project",   "func": tool_create_project},
    {"name": "place_plant",      "func": tool_place_plant},
    {"name": "place_community",  "func": tool_place_community},
    {"name": "place_structure",  "func": tool_place_structure},
    {"name": "analyze_project",  "func": tool_analyze_project},
    {"name": "project_summary",  "func": tool_project_summary},
    {"name": "export_catalogue", "func": tool_export_catalogue},
    {"name": "generate_design",  "func": tool_generate_design},
]


# ── MCP plumbing (requires the `mcp` SDK) ───────────────────────────────────

def build_server():
    """Construct the FastMCP server with every tool registered.

    Raises:
        RuntimeError: if the ``mcp`` SDK isn't installed, with an install
            hint. Kept out of module import so the tool logic above
            (and its tests) work without the SDK.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - needs SDK absent
        raise RuntimeError(
            "The MCP SDK isn't installed. Install it with "
            "`pip install mcp` (or `pip install 'permadesign[mcp]'`) "
            "to run the MCP server."
        ) from exc

    server = FastMCP("permadesign")
    for spec in TOOL_SPECS:
        # FastMCP.tool() reads the function's signature + docstring to
        # build the tool schema, so the testable tool_* functions become
        # the advertised tools verbatim.
        server.tool(name=spec["name"])(spec["func"])
    return server


def main() -> int:  # pragma: no cover - exercised by an MCP client
    """Run the MCP server over stdio."""
    server = build_server()
    server.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
