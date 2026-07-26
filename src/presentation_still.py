"""
src/presentation_still.py — the render you can put in a proposal (V2.33, F69).

Design principle P13 (a native planting has to be loved to survive) — see
docs/DESIGN_PHILOSOPHY.md.

A landscape designer's deliverable is not an interactive viewer; it is an image
in a document. The app has had every piece of this for two releases and never
joined them:

* :mod:`src.docent` builds a data-driven script whose beats already carry
  ``year``, ``season_month`` and ``camera`` — and *nothing has ever read those
  three fields*. The docent widget shows the title and the narration; the 3D
  window runs a separate hard-coded twenty-frame flyover storyboard.
* ``window.permaSnapshot`` renders the real viewer offscreen at an arbitrary
  size and is wired to exactly one caller, the sprite-gallery contact sheet.
* :mod:`src.pdf_export` already lays out a full-page image (the map screenshot).

This module is the missing middle: it turns a project into a list of STILL
SPECS — a camera, a year, a month, a title and a caption — that the 3D window
can render and the PDF can lay out. It is Qt-free and renders nothing itself,
so the spec can be built, tested and reasoned about without a viewer.

Why P13 rather than P5. Making the design *legible* is P5 and this does that
too, but the reason it earns its place is Nassauer's: a planting nobody finds
beautiful gets removed, and the person who has to be convinced — a spouse, a
neighbour, a board, a client — is never going to open a 3D viewer. Handing them
an image is the mechanism by which the ecology survives contact with people.
"""

from __future__ import annotations

from typing import Optional

# Camera presets the viewer knows (html/scene3d/08-modes.js permaSetCameraPreset).
# The first three are the docent's own vocabulary, so a beat's `camera` field
# maps straight through. `sidewalk` is new here and is the roadmap's F77 — the
# neighbour's-eye view — which costs nothing once the preset machinery exists.
CAMERA_PRESETS = ("overview", "orbit", "walk", "sidewalk")
DEFAULT_CAMERA = "overview"

# Print sizing. A half-page image on Letter at 300 dpi is ~2,550 px wide; the
# viewer's snapshot hook clamps to 2048 per edge and inherits a device pixel
# ratio it does not control, so the still is rendered at an explicit ratio and
# the two multiply. See src/map3d_js.py:snapshot.
PRINT_WIDTH_PX = 1600
PRINT_PIXEL_RATIO = 2          # → 3200 px on the long edge, ~300 dpi at 10.5"
PRINT_ASPECT = 16 / 10


def _clamp_month(m) -> int:
    try:
        m = int(m)
    except (TypeError, ValueError):
        return 7
    return min(12, max(1, m))


def still_from_beat(beat: dict) -> dict:
    """One still spec from a docent beat.

    The three fields the beats have always carried and nothing has ever read.
    """
    camera = (beat or {}).get("camera") or DEFAULT_CAMERA
    if camera not in CAMERA_PRESETS:
        camera = DEFAULT_CAMERA
    try:
        year = max(0, int((beat or {}).get("year") or 0))
    except (TypeError, ValueError):
        year = 0
    return {
        "id": (beat or {}).get("id") or "still",
        "title": (beat or {}).get("title") or "",
        "caption": (beat or {}).get("narration") or "",
        "year": year,
        "month": _clamp_month((beat or {}).get("season_month")),
        "camera": camera,
    }


def presentation_stills(project: dict, *, script: Optional[dict] = None,
                        build_script=None) -> list:
    """Every still a project's docent script implies, in tour order.

    ``script`` (or ``build_script``) is injectable so this stays testable
    without the DB the real docent needs.
    """
    if script is None:
        if build_script is None:
            from src.docent import build_docent_script as build_script
        try:
            script = build_script(project)
        except Exception:                             # noqa: BLE001
            script = None
    beats = (script or {}).get("beats") or []
    return [still_from_beat(b) for b in beats]


def cover_still(project: dict, *, script: Optional[dict] = None,
                build_script=None) -> Optional[dict]:
    """The ONE image for the front of a proposal.

    The design at the year it has become itself, not on install day — which is
    P4's whole argument and the thing a photograph of a new planting can never
    show. So: the latest beat the script offers, in high summer, from the
    overview camera; failing that, a sensible default rather than nothing,
    because a document with no picture is the failure being avoided.
    """
    stills = presentation_stills(project, script=script,
                                 build_script=build_script)
    if not stills:
        return {"id": "cover", "title": "The design at year 8", "caption": "",
                "year": 8, "month": 7, "camera": DEFAULT_CAMERA}
    best = max(stills, key=lambda s: s["year"])
    return dict(best, id="cover", month=7, camera=DEFAULT_CAMERA)


def render_request(still: dict, *, width: int = PRINT_WIDTH_PX,
                   pixel_ratio: int = PRINT_PIXEL_RATIO) -> dict:
    """What the 3D window has to be told to produce this still."""
    w = max(320, min(2048, int(width)))
    return {
        "year": still.get("year", 0),
        "month": still.get("month", 7),
        "camera": still.get("camera", DEFAULT_CAMERA),
        "width": w,
        "height": int(round(w / PRINT_ASPECT)),
        # Multiplied by the renderer's own size, so this is the lever that gets
        # a print-resolution image out of a viewport-sized capture.
        "pixel_ratio": max(1, min(4, int(pixel_ratio))),
    }
