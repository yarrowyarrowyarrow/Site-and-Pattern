"""
permadesign_api.py — Public, Qt-free scripting facade for PermaDesign.

This is the single advertised entry point for driving PermaDesign without
the GUI: AI agents, automation scripts, the CLI (Chunk 7), and the MCP
server (Chunk 7) all build on what's here. Nothing in this module imports
PyQt6, so everything runs under a bare ``python`` interpreter — no
``QApplication`` required.

Quick start::

    from src.permadesign_api import Project, query_plants, run_analysis

    proj = Project.create("My Yard", boundary=[
        (53.55, -113.50), (53.55, -113.49),
        (53.54, -113.49), (53.54, -113.50),
    ])
    yarrow = query_plants(query="yarrow", native_only=True)[0]
    proj.place_plant(yarrow["id"], 53.545, 113.495 * -1)
    score = run_analysis(proj)
    print(score["habitat_score"]["total"])
    proj.save("my_yard.perma.geojson")

Design notes:
  • Failures raise typed exceptions from :mod:`src.errors` (never a Qt
    pop-up), so callers get structured, branchable errors.
  • A :class:`Project` wraps the same GeoJSON-ish project dict the GUI
    uses, so files written here open in the app and vice-versa.
  • The plant database is initialised lazily on first use via
    ``src.db.plants.init_db`` (idempotent), so a fresh checkout works
    without a GUI launch first.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from src.design_api import DesignGenerator
from src.project import load_project, save_project, project_to_map_data
from src.db.plants import get_plant, search_plants
from src.db.polycultures import get_polyculture_by_id, get_all_polycultures
from src.db.structures import get_structure, get_all_structures
from src.habitat_score import compute_habitat_score, HabitatScoreError
from src.errors import (
    ProjectError,
    PlantNotFoundError,
    PolycultureNotFoundError,
    AnalysisError,
    ExportError,
)

__all__ = [
    "Project",
    "query_plants",
    "list_polycultures",
    "list_structures",
    "run_analysis",
    "pull_plant_impact",
    "chickadee_provision",
    "export_plant_catalogue_docx",
]


_DB_READY = False


def _ensure_db() -> None:
    """Initialise the plant DB once (idempotent). Safe to call on every
    public entry point so a headless caller never hits an empty DB."""
    global _DB_READY
    if _DB_READY:
        return
    from src.db.plants import init_db
    init_db()
    _DB_READY = True


# ── Plant / community / structure catalogue queries ─────────────────────────

def query_plants(**filters: Any) -> list[dict]:
    """Search the plant catalogue.

    Accepts the same keyword filters as
    ``src.db.plants.search_plants`` — e.g. ``query``, ``plant_type``,
    ``sun_req``, ``water_needs``, ``zone``, ``native_only``,
    ``pollinator_only``, ``host_plant_only``, ``keystone_only``,
    ``bird_food_only``, ``ab_ecoregion``, … — and returns the matching
    plant dicts (each includes ``id`` and ``common_name``).

    Example::

        query_plants(query="milkweed", native_only=True)
        query_plants(plant_type="tree", zone=3)
    """
    _ensure_db()
    return search_plants(**filters)


def list_polycultures(top_level_only: bool = True) -> list[dict]:
    """Return the seeded plant communities (polycultures). Pass each
    one's ``id`` to :meth:`Project.place_polyculture`."""
    _ensure_db()
    return get_all_polycultures(top_level_only=top_level_only)


def list_structures() -> list[dict]:
    """Return the habitat-structure catalogue (bee hotels, ponds,
    brush piles, …). Pass each one's ``id`` to
    :meth:`Project.place_structure`."""
    return get_all_structures()


# ── Project ─────────────────────────────────────────────────────────────────

class Project:
    """A PermaDesign project: a property boundary plus placed plants,
    communities, and structures.

    Construct with :meth:`create` (new) or :meth:`load` (from a saved
    ``.perma.geojson`` file), mutate with the ``place_*`` / ``set_boundary``
    methods, inspect via :attr:`placed_plants` / :attr:`structures` /
    :meth:`as_dict`, then :meth:`save` or :meth:`analyze`.

    The wrapped dict is the exact format the GUI reads and writes, so a
    project built here opens in the app unchanged.
    """

    def __init__(self, generator: DesignGenerator):
        # Internal — use Project.create() / Project.load().
        self._gen = generator

    # ── Construction ─────────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        name: str = "Untitled Design",
        *,
        site_config: Optional[dict] = None,
        boundary: Optional[list[tuple[float, float]]] = None,
    ) -> "Project":
        """Create a fresh project.

        Args:
            name: project name (stored in properties.project_name).
            site_config: optional dict of site fields (latitude,
                longitude, hardiness_zone, soil_type, …).
            boundary: optional list of ``(lat, lng)`` tuples for the
                property outline.
        """
        _ensure_db()
        sc = dict(site_config or {})
        sc.setdefault("name", name)
        proj = cls(DesignGenerator(sc))
        if boundary:
            proj.set_boundary(boundary)
        return proj

    @classmethod
    def load(cls, path: str) -> "Project":
        """Load a project from a ``.perma.geojson`` file.

        Raises:
            ProjectError: if the file is missing, unreadable, or not
                valid project JSON.
        """
        _ensure_db()
        try:
            data = load_project(path)
        except FileNotFoundError as exc:
            raise ProjectError(f"Project file not found: {path}") from exc
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            raise ProjectError(f"Couldn't read project {path}: {exc}") from exc
        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            raise ProjectError(
                f"{path} is not a Site & Pattern project (missing FeatureCollection)."
            )
        gen = DesignGenerator()
        gen.project = data
        return cls(gen)

    # ── Persistence ──────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        """Write the project to ``path``. Raises ProjectError on I/O error."""
        try:
            save_project(self._gen.project, path)
        except OSError as exc:
            raise ProjectError(f"Couldn't save project to {path}: {exc}") from exc

    # ── Mutation ─────────────────────────────────────────────────────────

    def set_boundary(self, coords: list[tuple[float, float]],
                     color: str = "green") -> None:
        """Set the property boundary from a list of ``(lat, lng)`` tuples."""
        self._gen.set_boundary(coords, color)

    def place_plant(self, plant_id: int, lat: float, lng: float,
                    *, polyculture_name: str = "", quantity: int = 1) -> None:
        """Place a single plant at ``(lat, lng)``.

        Raises:
            PlantNotFoundError: if ``plant_id`` isn't in the catalogue.
        """
        _ensure_db()
        if get_plant(plant_id) is None:
            raise PlantNotFoundError(f"No plant with id {plant_id}")
        self._gen.add_plant(plant_id, lat, lng,
                            polyculture_name=polyculture_name, quantity=quantity)

    def place_polyculture(self, polyculture_id: int,
                          center_lat: float, center_lng: float) -> None:
        """Place an entire plant community centred at ``(center_lat,
        center_lng)``; each member lands at its stored offset.

        Raises:
            PolycultureNotFoundError: if ``polyculture_id`` doesn't exist.
        """
        _ensure_db()
        if get_polyculture_by_id(polyculture_id) is None:
            raise PolycultureNotFoundError(
                f"No polyculture with id {polyculture_id}"
            )
        self._gen.add_polyculture(polyculture_id, center_lat, center_lng)

    def place_structure(self, struct_id: str, lat: float, lng: float) -> None:
        """Place a habitat structure (by catalogue id) at ``(lat, lng)``."""
        struct_def = get_structure(struct_id)
        # Unknown ids still place (mirrors DesignGenerator), but we attach
        # the real definition when we have one so habitat scoring counts it.
        self._gen.add_structure(struct_id, lat, lng,
                                struct_def=struct_def or {"id": struct_id})

    # ── Inspection ───────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._gen.project["properties"].get("project_name", "")

    @property
    def placed_plants(self) -> list[dict]:
        """Placed plants as ``{plant_id, common_name, lat, lng, …}`` dicts."""
        return project_to_map_data(self._gen.project)["plants"]

    @property
    def structures(self) -> list[dict]:
        """Placed structures as their ``struct_def`` dicts (each has ``id``)
        — the same shape the GUI feeds the habitat scorer."""
        out = []
        for f in self._gen.project.get("features", []):
            props = f.get("properties", {})
            if props.get("element_type") == "structure":
                out.append(props.get("struct_def", {}))
        return out

    def as_dict(self) -> dict:
        """Return the underlying project dict (GUI-compatible GeoJSON)."""
        return self._gen.project

    def validate(self) -> list[str]:
        """Return human-readable warnings about the design (missing
        boundary, no plants, no site coords, …). Empty list = clean."""
        return self._gen.validate()

    def analyze(self) -> dict:
        """Convenience wrapper for :func:`run_analysis(self) <run_analysis>`."""
        return run_analysis(self)


# ── Analysis ─────────────────────────────────────────────────────────────────

def run_analysis(project: Project) -> dict:
    """Run the design analyses on a project and return a JSON-friendly dict.

    Currently computes the Habitat Value Score (the same 0–100 score the
    GUI's Analysis tab shows). Returns::

        {
            "habitat_score": { ... } | None,   # None if nothing placed
            "warnings": [ ... ],               # from Project.validate()
        }

    Raises:
        AnalysisError: if the plant database can't be read.
    """
    _ensure_db()
    try:
        score = compute_habitat_score(project.placed_plants, project.structures)
    except HabitatScoreError as exc:
        raise AnalysisError(f"Habitat score unavailable: {exc}") from exc
    return {
        "habitat_score": score.as_dict() if score is not None else None,
        "warnings": project.validate(),
    }


def pull_plant_impact(project: Project, plant_id: int) -> Optional[dict]:
    """Preview the cost of removing one placed ``plant_id`` from ``project`` —
    the "pull-a-plant" impact simulator (F46). Returns the JSON-friendly dict
    from :func:`src.plant_impact.pull_plant_impact` (supported species lost,
    whether the food-web chain snaps, Habitat Score delta), or ``None`` if the
    plant isn't placed.

    Raises:
        AnalysisError: if the plant database can't be read.
    """
    _ensure_db()
    from src.plant_impact import pull_plant_impact as _impact
    try:
        return _impact(project.placed_plants, project.structures, int(plant_id))
    except HabitatScoreError as exc:
        raise AnalysisError(f"Impact unavailable: {exc}") from exc


def chickadee_provision(project: Project) -> dict:
    """Estimate whether ``project`` could provision a chickadee brood — the
    "feed a chickadee" scenario (F47). Returns the JSON-friendly dict from
    :func:`src.chickadee_scenario.chickadee_provision`: the design's estimated
    caterpillar capacity (an honest range) against the 6,000–9,000 a brood
    needs, a pass/partway/short ``status`` + ``verdict``, and the keystone host
    plants doing the work.

    Raises:
        AnalysisError: if the plant/fauna database can't be read.
    """
    _ensure_db()
    from src.chickadee_scenario import chickadee_provision as _provision
    try:
        return _provision(project.placed_plants)
    except Exception as exc:      # noqa: BLE001
        raise AnalysisError(f"Chickadee scenario unavailable: {exc}") from exc


# ── Exports ────────────────────────────────────────────────────────────────

def export_plant_catalogue_docx(out_path: str) -> str:
    """Export the full plant catalogue to a Word ``.docx`` at ``out_path``.

    This is the headless export path (no Qt). It writes the shipped plant
    catalogue — field reference, plant table, planting calendar — not a
    specific design.

    PDF design export is intentionally NOT exposed here: ``src.pdf_export``
    needs a live Qt ``QPrinter`` + a rendered map screenshot, so it can't
    run headlessly. Call it from the GUI instead.

    Returns the path written. Raises ExportError on failure.
    """
    try:
        import sys
        import os
        scripts_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
        )
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import export_plant_docx
        return export_plant_docx.main(out_path)
    except ImportError as exc:
        raise ExportError(
            f"DOCX export needs the python-docx package: {exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - surface anything as ExportError
        raise ExportError(f"DOCX export failed: {exc}") from exc
