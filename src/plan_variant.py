"""
plan_variant.py — *Try another* (PY-6, V3.29; docs/homeowner/07 §4.4).

Design principle P1 — see docs/DESIGN_PHILOSOPHY.md.

The generator is deterministic, which the critic and the tests rely on: the
same answers give the same plan. *Try another* asks for a different plan of the
same quality, so a ``variant`` changes three things and nothing about how good
a plan is:

* **Which plants**, rotated only **within a band and a layer**
  (:func:`rotate_runs`): a variant swaps one top-pick shrub for another
  top-pick shrub, never for a worse plant (PR-1).
* **Where the anchors fall**: the grid the main pass lays its drifts on is
  shifted by a fraction of a cell (:func:`grid_phase`), by the golden ratio so
  no two variants share a phase.
* **How each drift is drawn**: the layouts' seeds move (:func:`seed_offset`).

Variant 0 changes none of them, so it is the plan the app made before V3.29.

Qt-free.
"""

from __future__ import annotations

from typing import Callable

#: How many places a variant moves each band's plants along within a layer.
STEP = 2
_GOLDEN = 0.6180339887498949


def rotate_runs(rows: list, key: Callable, variant: int) -> list:
    """``rows`` with each run of equal ``key`` rotated by ``variant * STEP``."""
    if not variant:
        return list(rows)
    out, run = [], []

    def flush():
        if run:
            k = (variant * STEP) % len(run)
            out.extend(run[k:] + run[:k])
            run.clear()

    last = object()
    for r in rows:
        k = key(r)
        if k != last:
            flush()
            last = k
        run.append(r)
    flush()
    return out


def grid_phase(variant: int) -> tuple:
    """Where in its cell the first grid point sits, as fractions of a cell:
    ``(0.5, 0.5)`` (the middle) for variant 0."""
    if not variant:
        return (0.5, 0.5)
    return ((0.5 + variant * _GOLDEN) % 1.0,
            (0.5 + variant * _GOLDEN * _GOLDEN) % 1.0)


def seed_offset(variant: int) -> int:
    """Added to every layout's seed: 0 for variant 0."""
    return int(variant) * 10007
