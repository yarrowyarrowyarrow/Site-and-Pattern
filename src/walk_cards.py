"""
walk_cards.py — what a click in the walk opens (F255, V3.38).

Design principle P3 — see docs/DESIGN_PHILOSOPHY.md (relationships matter
more than components: the card is the plant's edges, made readable).

The owner, in Learn › Walk a wild landscape: *"I'd like to be able to click a
plant and read its drop down … this is this plant, here is what it does, here
are creatures it supports."* The walk's hint has said "left-click a plant to
learn about it" since V2.43, and the click went to ``html/scene3d/10-inspect.js``,
which looks the plant up in what ``permaSetDossier`` sent. Only the design's
3D preview ever sent it, so in the walk the lookup found nothing and the click
did nothing.

This module is the walk's side of that: the same
:func:`src.scene_dossier.build_dossier` the preview uses, so the two cards
cannot differ. V3.39 grows the cards themselves here (plant to animals to
plants, here and not here yet), away from ``reference_edit_flow``, which is
at its line ceiling.
"""

from __future__ import annotations


def push(win, scene: dict) -> None:
    """Send ``win.viewer`` the cards for everything in ``scene``.

    Called with every scene the walk pushes, so a card left open follows the
    year and the plants under it. An empty dossier on failure: no card is a
    smaller fault than a broken walk.
    """
    try:
        from src.scene_dossier import build_dossier
        dossier = build_dossier(scene)
    except Exception:      # noqa: BLE001
        dossier = {}
    win.viewer.set_dossier(dossier)
