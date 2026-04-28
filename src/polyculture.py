"""
src/polyculture.py — interplanting helpers.

When the plant panel has a "mix" (≥1 secondary species in addition to the
selected primary), the geometry generator in html/map.html still produces
a single uniform list of [[lat, lng], ...] positions using one spacing.
This module provides the two pure-Python steps that wrap that geometry:

  1. resolve_spacing(species, strategy) — pick the centre-to-centre
     spacing for the mix. Default "max" guarantees no canopy overlap.
  2. assign_species(positions, species, strategy) — return a parallel
     list, one species dict per position, deciding which species lives
     at each spot.

Kept dependency-free so tests/test_polyculture.py can import without Qt.
"""

from __future__ import annotations

import random
from typing import Optional


def resolve_spacing(species: list[dict], strategy: str = "max") -> float:
    """Effective centre-to-centre spacing for a polyculture mix.

    Each species dict is expected to carry a 'spacing_m' float. Unknown
    or zero spacings are treated as 1m so the result is always positive.

    Strategies:
      "max"     — largest mature spacing in the mix (no canopy overlap)
      "min"     — smallest spacing (densest, expect overlap)
      "avg"     — arithmetic mean
      "primary" — first species' spacing (panel passes primary first)
    """
    spacings = [float(s.get("spacing_m") or 1.0) for s in species]
    if not spacings:
        return 1.0
    if strategy == "min":
        return min(spacings)
    if strategy == "avg":
        return sum(spacings) / len(spacings)
    if strategy == "primary":
        return spacings[0]
    # "max" is the safe default for any unknown strategy too.
    return max(spacings)


def assign_species(
    positions: list,
    species: list[dict],
    strategy: str = "weighted_random",
    *,
    rng: Optional[random.Random] = None,
) -> list[dict]:
    """Return a parallel list — one species dict per position.

    The strategy controls how species fill positions:

      "weighted_random" — independent samples with replacement, weighted
                          by each species' 'weight' field (default 1.0).
                          With equal weights this gives an even random
                          mix; uneven weights skew the distribution.

    `rng` is exposed so tests can pin a seed for reproducibility.
    """
    if not positions:
        return []
    if not species:
        return []
    if len(species) == 1:
        return [species[0]] * len(positions)

    rng = rng or random.Random()

    if strategy == "weighted_random":
        weights = [max(0.0, float(s.get("weight") or 1.0)) for s in species]
        if sum(weights) <= 0:
            weights = [1.0] * len(species)
        return rng.choices(species, weights=weights, k=len(positions))

    raise ValueError(f"Unknown polyculture strategy: {strategy!r}")
