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
    strategy: str = "even_split",
    *,
    rng: Optional[random.Random] = None,
) -> list[dict]:
    """Return a parallel list — one species dict per position.

    Strategies:

      "even_split" (default) — deterministic. Distributes species across
                               positions as evenly as the per-species
                               'weight' ratio allows, using a largest-
                               deficit pass. With equal weights and N
                               positions divisible by len(species), each
                               species gets exactly N/k plants. Result
                               is a stable rotating pattern (s0, s1, s2,
                               s0, s1, s2, …) so neighbouring positions
                               are different species.

      "weighted_random" — independent samples with replacement, weighted
                          by 'weight' (default 1.0). Each placement is
                          a fresh draw, so two adjacent cells may land
                          on the same species. `rng` is exposed so
                          tests can pin a seed for reproducibility.
    """
    if not positions:
        return []
    if not species:
        return []
    if len(species) == 1:
        return [species[0]] * len(positions)

    if strategy == "even_split":
        return _assign_even_split(positions, species)

    if strategy == "weighted_random":
        rng = rng or random.Random()
        weights = [max(0.0, float(s.get("weight") or 1.0)) for s in species]
        if sum(weights) <= 0:
            weights = [1.0] * len(species)
        return rng.choices(species, weights=weights, k=len(positions))

    raise ValueError(f"Unknown polyculture strategy: {strategy!r}")


def _assign_even_split(positions: list, species: list[dict]) -> list[dict]:
    """Largest-deficit ratio assignment.

    For each position i, compute the "ideal" share for each species
    (`(i+1) * weight[s] / total_weight`) minus what they've actually
    received so far, then pick the species with the largest deficit.
    This produces an integer count per species that's always
    floor(target) or ceil(target), and an interleaved spatial pattern.

    Equivalent in effect to Bresenham's line algorithm generalised to
    k species. Deterministic given (positions, species, weights) — no
    rng needed.
    """
    weights = [max(0.0, float(s.get("weight") or 1.0)) for s in species]
    total = sum(weights)
    if total <= 0:
        weights = [1.0] * len(species)
        total = float(len(species))

    counts = [0.0] * len(species)
    out: list[dict] = []
    for i in range(len(positions)):
        # Pick the species whose "should have had by now − got" is largest.
        # Tie-break by species index (lowest first) for deterministic output.
        best_s = 0
        best_def = ((i + 1) * weights[0] / total) - counts[0]
        for s in range(1, len(species)):
            d = ((i + 1) * weights[s] / total) - counts[s]
            if d > best_def:
                best_def = d
                best_s = s
        counts[best_s] += 1.0
        out.append(species[best_s])
    return out
