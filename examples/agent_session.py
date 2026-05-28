"""
agent_session.py — A worked end-to-end PermaDesign scripting session.

This is the canonical example an AI agent (or a new contributor) reads to
learn the headless API. Every step uses only ``src.permadesign_api`` —
no PyQt6, no QApplication, no GUI. Run it directly::

    python examples/agent_session.py

It builds a small pollinator garden for an Edmonton property, scores it,
saves the project, reloads it to prove round-trip fidelity, and writes a
plant-catalogue DOCX. Output files go to a temp directory whose path is
printed at the end.

The workflow:
    1. Query the plant catalogue (native pollinator plants).
    2. Create a project with a property boundary.
    3. Place individual plants.
    4. Place a seeded plant community (polyculture).
    5. Place a habitat structure.
    6. Run the habitat analysis and print the score breakdown.
    7. Save the project, then reload it and confirm it's identical.
    8. (Optional) Export the plant catalogue to DOCX.
"""

from __future__ import annotations

import os
import sys
import tempfile

# Make ``src`` importable when run from the repo root or elsewhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.permadesign_api import (
    Project,
    query_plants,
    list_polycultures,
    list_structures,
    run_analysis,
    export_plant_catalogue_docx,
)
from src.errors import PermaDesignError


# A small rectangular lot near central Edmonton, as (lat, lng) corners.
_BOUNDARY = [
    (53.5465, -113.4945),
    (53.5465, -113.4930),
    (53.5455, -113.4930),
    (53.5455, -113.4945),
]


def run(out_dir: str, *, with_docx: bool = True) -> dict:
    """Run the full scripting session, writing artefacts under ``out_dir``.

    Returns a dict of results (project path, score, etc.) so this doubles
    as an integration test. Raises PermaDesignError on any API failure.
    """
    log = print

    # ── 1. Query the catalogue ────────────────────────────────────────────
    natives = query_plants(native_only=True, pollinator_only=True)
    log(f"[1] {len(natives)} native pollinator plants in the catalogue.")
    if not natives:
        raise PermaDesignError("No native pollinator plants found — empty DB?")

    # ── 2. Create the project with a boundary ─────────────────────────────
    project = Project.create(
        "Edmonton Pollinator Garden",
        site_config={"latitude": 53.546, "longitude": -113.494,
                     "hardiness_zone": 3},
        boundary=_BOUNDARY,
    )
    log(f"[2] Created project {project.name!r} with a {len(_BOUNDARY)}-corner boundary.")

    # ── 3. Place a handful of individual plants ───────────────────────────
    base_lat, base_lng = 53.5460, -113.4938
    for i, plant in enumerate(natives[:6]):
        project.place_plant(
            plant["id"],
            base_lat + (i % 3) * 0.0002,
            base_lng + (i // 3) * 0.0002,
        )
    log(f"[3] Placed {len(project.placed_plants)} individual plants.")

    # ── 4. Place a seeded plant community ─────────────────────────────────
    communities = list_polycultures()
    if communities:
        community = communities[0]
        project.place_polyculture(community["id"], 53.5458, -113.4940)
        log(f"[4] Placed community {community['name']!r}; "
            f"design now has {len(project.placed_plants)} plants.")
    else:
        log("[4] No seeded communities available; skipping.")

    # ── 5. Place a habitat structure ──────────────────────────────────────
    structures = list_structures()
    struct_ids = {s["id"] for s in structures}
    if "bee_hotel" in struct_ids:
        project.place_structure("bee_hotel", 53.5462, -113.4935)
        log("[5] Placed a bee hotel.")
    elif structures:
        project.place_structure(structures[0]["id"], 53.5462, -113.4935)
        log(f"[5] Placed a {structures[0]['name']}.")

    # ── 6. Run the habitat analysis ───────────────────────────────────────
    analysis = run_analysis(project)
    score = analysis["habitat_score"]
    log(f"[6] Habitat Value Score: {score['total']}/100 ({score['grade']}).")
    for name, comp in score["components"].items():
        log(f"      {name:11s} {comp['score']:>5} / {comp['max']}")
    if analysis["warnings"]:
        log(f"    Warnings: {analysis['warnings']}")

    # ── 7. Save, then reload and confirm round-trip fidelity ──────────────
    project_path = os.path.join(out_dir, "pollinator_garden.perma.geojson")
    project.save(project_path)
    reloaded = Project.load(project_path)
    assert reloaded.as_dict() == project.as_dict(), "round-trip mismatch!"
    log(f"[7] Saved + reloaded {project_path} (round-trip identical).")

    # ── 8. Export the plant catalogue (optional) ──────────────────────────
    docx_path = None
    if with_docx:
        try:
            docx_path = export_plant_catalogue_docx(
                os.path.join(out_dir, "plant_catalogue.docx")
            )
            log(f"[8] Exported plant catalogue → {docx_path}")
        except PermaDesignError as exc:
            # python-docx may not be installed; that's fine for the demo.
            log(f"[8] DOCX export skipped: {exc}")

    return {
        "n_natives": len(natives),
        "n_placed": len(project.placed_plants),
        "score": score,
        "warnings": analysis["warnings"],
        "project_path": project_path,
        "docx_path": docx_path,
    }


def main() -> int:
    out_dir = tempfile.mkdtemp(prefix="permadesign_agent_session_")
    print(f"Writing artefacts to {out_dir}\n")
    try:
        run(out_dir)
    except PermaDesignError as exc:
        print(f"\nSession failed: {exc}", file=sys.stderr)
        return 1
    print("\nDone — headless session completed with no QApplication.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
