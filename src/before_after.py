"""
src/before_after.py — before / after / in five years (F76, V2.56).

Design principle P13 (a native planting has to be loved to survive), P4 (time is
the most undervalued design variable) and P5 (make the invisible visible) — see
docs/DESIGN_PHILOSOPHY.md.

The one image that makes people act, and every ingredient has existed for three
releases without ever being assembled:

* :mod:`src.site_photo` holds the user's own photograph of their yard (F24);
* :mod:`src.snapshot_timeline` already knows which years are worth showing (F2);
* :mod:`src.presentation_still` already turns a moment into a print-resolution
  render request (F69), including the ``sidewalk`` camera (F77);
* :mod:`src.pdf_export` already lays a captured pixmap onto a page.

This is the missing middle: three panel specs — *your lawn now*, *year 1*,
*year 5* — that the 3D window renders and the PDF lays out side by side. Qt-free
and renders nothing itself, exactly like ``presentation_still``, so the whole
composition can be built and tested without a viewer.

**Why one page rather than a slider.** P4's argument is that a planting has to be
judged on its trajectory, not on install day, and the app has always been able to
*show* that — by asking someone to drag a year slider. Nobody drags the slider for
a person they are trying to convince. Three panels on one page make the same
argument in a form that can be handed to a spouse, a board or a client, which is
the form the argument actually has to survive in.

**The two 'before' cases are different arguments and are captioned differently.**
With the user's own photograph, panel one is *your lawn as it is now* — the
comparison that converts somebody. Without it, the honest fallback is the
planting in its first summer: still true, still useful, and a materially weaker
claim. Silently letting one stand in for the other is the small dishonesty this
codebase keeps finding in itself, so the caption always says which one you are
looking at.

**Year 0 is not planting day (V3.43).** The fallback rendered "the design at
year 0" under the title *On planting day*, and year 0 is the growth model's
design fully grown (``scene3d.growth_scale_factor`` returns 1.0 there, on
purpose). So the page showed a mature yard as the day it went in, and a smaller
one beside it as year 1: the planting shrinking. Without a photograph the page
is now three summers, the first, one between and the last, and no panel is
year 0.
"""

from __future__ import annotations

from typing import Callable, Optional

#: Panel identities, in reading order.
BEFORE = "before"
NEAR = "near"
FAR = "far"

#: Panel content kinds. A photo panel is a stored image; a render panel is a
#: request the 3D window has to satisfy.
KIND_PHOTO = "photo"
KIND_RENDER = "render"

#: One camera for every rendered panel, or the panels do not compare — a
#: viewpoint change between two images reads as a difference in the design.
#: ``sidewalk`` (F77) because the neighbour's-eye view is the entire argument
#: this page exists to make (P13).
DEFAULT_CAMERA = "sidewalk"

#: High summer, so the planting is shown doing what it does.
DEFAULT_MONTH = 7

#: The first year the growth model draws, the summer after planting: what the
#: fallback before-panel shows. Never 0, which is the design fully grown.
FIRST_SUMMER = 1


def panel_years(project: dict, *,
                get_plant: Optional[Callable] = None) -> tuple:
    """``(near, far)`` — the two years to render, from the app's own vocabulary.

    Read off :func:`src.snapshot_timeline.snapshot_years` rather than hard-coding
    1 and 5, so the timeline and this page can never disagree about which years
    are worth showing.

    In practice that is always ``(1, 5)`` today: ``snapshot_years`` caps its
    years at ``succession.timeline_max_years``, whose **floor is 20**, so no
    design can be short enough to cap year 5 away. The fallback below is
    therefore defensive rather than load-bearing — but it costs a line, and the
    alternative is a page that silently shows the same year twice if that floor
    ever moves.
    """
    from src.snapshot_timeline import placed_records, snapshot_years
    years = snapshot_years(placed_records(project or {}), get_plant=get_plant)
    if len(years) >= 2:
        return (years[0], years[1])
    if len(years) == 1:
        return (years[0], years[0])
    return (1, 5)


def first_summer_panel(camera: str = DEFAULT_CAMERA) -> dict:
    """The fallback first panel: the planting in its first summer.

    Used when there is no site photograph — and also when there is one that
    cannot be decoded, which the renderer discovers and this module cannot.
    Either way the caption says plainly that this is *not* a photograph of the
    existing yard: see the module docstring, they are two different arguments.

    ``camera`` is a parameter and not a default lookup because a panel built
    here has to match the camera the rest of the page is using. Left to
    ``render_request``'s own fallback it would come out as ``overview`` beside
    two ``sidewalk`` panels, and the page would silently stop comparing like
    with like.
    """
    return {
        "id": BEFORE,
        "kind": KIND_RENDER,
        "title": "The first summer",
        "caption": ("The planting in its first summer. No photograph of the "
                    "yard as it is now has been added, so this is not the "
                    "lawn it replaces."),
        "year": FIRST_SUMMER,
        "month": DEFAULT_MONTH,
        "camera": camera,
    }


def before_panel(project: dict) -> dict:
    """The first panel: the user's photograph if there is one, else the
    planting's first summer."""
    from src import site_photo

    feature = site_photo.feature_from_project(project or {})
    if feature is None:
        return first_summer_panel()
    props = feature.get("properties") or {}
    return {
        "id": BEFORE,
        "kind": KIND_PHOTO,
        "title": "Now",
        "caption": "Your yard as it is today.",
        "image": props.get("image") or "",
    }


def panel_specs(project: dict, *, camera: str = DEFAULT_CAMERA,
                get_plant: Optional[Callable] = None) -> list:
    """The three panels, in reading order.

    Every rendered panel carries the same camera and month, so the only thing
    that changes across the page is the thing being argued about: time.
    """
    from src.presentation_still import CAMERA_PRESETS, DEFAULT_CAMERA as _FALLBACK

    cam = camera if camera in CAMERA_PRESETS else _FALLBACK
    near, far = panel_years(project, get_plant=get_plant)

    panels = [before_panel(project), _year_panel(NEAR, near),
              _year_panel(FAR, far)]
    if panels[0]["kind"] == KIND_RENDER:
        without_photo(panels, cam)
    for p in panels:
        if p["kind"] == KIND_RENDER:
            p["camera"] = cam
    return panels


def _year_panel(panel_id: str, year: int) -> dict:
    what = ("filling in, still open between the plants" if panel_id == NEAR
            else "closed up, and what the design was actually for")
    return {
        "id": panel_id,
        "kind": KIND_RENDER,
        "title": f"Year {year}",
        "caption": f"After {_season_count(year)} — {what}.",
        "year": year,
        "month": DEFAULT_MONTH,
    }


def _between(first: int, last: int) -> Optional[int]:
    """A year strictly between two others, nearest their middle, or ``None``
    when they leave no room for one."""
    mid = max(first + 1, (first + last) // 2)
    return mid if mid < last else None


def without_photo(panels: list, camera: str = DEFAULT_CAMERA) -> list:
    """Make ``panels`` the page with no photograph, in place: the first summer
    as the first panel, and the middle panel moved to a year between it and the
    last, so the first summer is not shown twice. Also what the renderer does
    with a photograph it cannot decode."""
    far = next((p for p in panels if p.get("id") == FAR), None)
    for i, p in enumerate(panels):
        if p.get("id") == BEFORE:
            panels[i] = first_summer_panel(camera)
        elif p.get("id") == NEAR and far is not None:
            year = _between(FIRST_SUMMER, int(far.get("year") or 0))
            if year is not None and p.get("year") == FIRST_SUMMER:
                panels[i] = dict(_year_panel(NEAR, year),
                                 camera=p.get("camera") or camera)
    return panels


def _season_count(years: int) -> str:
    n = int(years or 0)
    if n <= 0:
        return "no growing seasons"
    return "one growing season" if n == 1 else f"{n} growing seasons"


def render_requests(panels: list, **kwargs) -> list:
    """``(panel_id, request)`` for every panel the viewer has to render.

    Photo panels are skipped — they are already an image. Sizing comes from
    :func:`src.presentation_still.render_request` rather than being restated, so
    a print-resolution change lands on both features at once.
    """
    from src.presentation_still import render_request

    out = []
    for p in panels or []:
        if p.get("kind") != KIND_RENDER:
            continue
        out.append((p.get("id"), render_request(p, **kwargs)))
    return out


def page_caption(panels: list) -> str:
    """One line under the three panels, naming the argument being made."""
    far = next((p for p in panels or [] if p.get("id") == FAR), None)
    year = (far or {}).get("year") or 5
    first = (panels or [{}])[0]
    span = (f"The same view over {year} summers." if first.get("kind") == KIND_RENDER
            else f"The same view, {year} years apart.")
    return (f"{span} A native planting is judged on what it becomes, not on "
            f"the day it goes in.")
