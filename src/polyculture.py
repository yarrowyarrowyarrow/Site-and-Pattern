"""
src/polyculture.py — interplanting helpers.

When the plant panel has a "mix" (≥1 secondary species in addition to the
selected primary), the geometry generator in html/map.html still produces
a single uniform list of [[lat, lng], ...] positions using one spacing.
This module provides the three pure-Python steps that wrap that geometry:

  1. resolve_spacing(species, strategy) — pick the centre-to-centre
     spacing for the mix. Default "max" guarantees no canopy overlap.
  2. assign_species(positions, species, strategy) — return a parallel
     list, one species dict per position, deciding *how many* of each
     species we need (this enforces the user's ratios).
  3. optimize_layout(positions, assignments) — permute that list so
     same-species plants are spread as far apart as the geometry
     allows, by minimising a 1/d² Coulomb-style repulsion energy via
     simulated annealing. The ratio counts from step (2) are
     preserved exactly because we only ever swap pairs.

Kept dependency-free so tests/test_polyculture.py can import without Qt.
"""

from __future__ import annotations

import math
import random
from typing import Optional, Callable


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


# ── Energy-minimisation layout optimiser ─────────────────────────────────────

def optimize_layout(
    positions: list,
    assignments: list[dict],
    *,
    iterations: Optional[int] = None,
    initial_temp: Optional[float] = None,
    rng: Optional[random.Random] = None,
    repulsion_exponent: float = 2.0,
) -> list[dict]:
    """Permute `assignments` to minimise same-species clumping.

    Treats every plant of the same species as an identically-charged
    particle. The total repulsion energy is

        E = Σ_{i<j, S(i)=S(j)} 1 / d(i, j)^p

    with p=2 by default (Coulomb-like). Different-species pairs don't
    contribute. Minimising E spreads same-species plants as far apart
    as the boundary geometry allows, regardless of mix ratio.

    Algorithm: Metropolis-Hastings / simulated annealing. Each step
    proposes a swap of two different-species positions and accepts it
    if it lowers E, or with probability exp(−ΔE/T) otherwise. T cools
    exponentially from `initial_temp` toward zero. Because we only ever
    swap, the per-species counts produced by `assign_species` are
    preserved exactly.

    Distance is Euclidean in local metres after a flat-earth projection
    around the centroid of `positions`. For ≤1km layouts this is
    monotonic with the per-geometry distance (chord vs arc on a circle,
    cube-coord vs Euclidean on a hex grid), so SA reaches the same
    minimum-energy permutation as a per-geometry metric would.

    Args:
        positions: list of [lat, lng] pairs (one per assignment).
        assignments: parallel list of species dicts (each must have an
            'id' so same-species pairs can be detected).
        iterations: number of swap proposals; default scales with N
            (max(500, 25·N), capped at 8000) to keep small layouts fast
            and large layouts well-mixed.
        initial_temp: starting temperature; default scales with the
            initial energy.
        rng: seedable Random for deterministic tests; new Random()
            otherwise.
        repulsion_exponent: 2 = Coulomb-like (default). Higher values
            penalise close pairs more aggressively; 1 gives gentler
            spreading.

    Returns the optimised list of assignments. The input is not
    mutated.
    """
    n = len(positions)
    if n != len(assignments):
        raise ValueError("positions and assignments must have the same length")
    if n < 2:
        return list(assignments)
    unique_ids = {a.get("id") for a in assignments}
    if len(unique_ids) < 2:
        return list(assignments)

    rng = rng or random.Random()
    pts_xy = _to_local_xy(positions)
    cur = list(assignments)

    # Pre-compute pairwise distances once — O(N²) memory but a single
    # pattern caps at a few hundred plants in practice.
    dists = _pairwise_distances(pts_xy)
    energies = _pair_energies(dists, repulsion_exponent)

    cur_E = _total_energy(cur, energies)
    if cur_E <= 0.0:
        return cur

    if iterations is None:
        # Floor of 3000 stops small grids (16 cells) getting trapped in
        # stripe-like local minima where the global checkerboard is
        # only a few coordinated swaps away. 100·N gives larger
        # patterns enough budget to mix; 30000 is the upper cap so
        # we don't spend more than a couple seconds on huge layouts.
        iterations = max(3000, min(30000, 100 * n))

    if initial_temp is None:
        # Heuristic: about 50% acceptance for moves that change E by
        # one same-species pair's worth on average.
        initial_temp = max(cur_E / max(1, n), 1e-9)
    # Slower cooling (T₀ → T₀/1000 over `iterations`) keeps SA
    # exploratory enough to escape stripe-like local minima before
    # freezing into the global pattern.
    cooling = (1e-3) ** (1.0 / max(1, iterations))

    T = initial_temp
    same_count = sum(1 for k in range(n) if cur[k].get("id") == cur[0].get("id"))
    # If the rarest species fills the whole list, nothing to do.
    if same_count == n:
        return cur

    for _ in range(iterations):
        i = rng.randrange(n)
        j = rng.randrange(n)
        if i == j:
            T *= cooling
            continue
        si = cur[i].get("id")
        sj = cur[j].get("id")
        if si == sj:
            T *= cooling
            continue
        dE = _swap_delta_e(cur, energies, i, j, si, sj)
        if dE < 0.0:
            cur[i], cur[j] = cur[j], cur[i]
            cur_E += dE
        elif T > 0.0:
            try:
                p = math.exp(-dE / T)
            except OverflowError:
                p = 0.0
            if rng.random() < p:
                cur[i], cur[j] = cur[j], cur[i]
                cur_E += dE
        T *= cooling
    return cur


def hex_pack_disc_local(radius_m: float, spacing_m: float) -> list[tuple[float, float]]:
    """Return hex-packed (x, y) positions in metres that fit inside a disc
    of the given radius. Mirrors the JS `_hexPackedDisc` in html/map.html
    so the polyculture builder can preview the same packing the map uses.

    Always starts with (0, 0) (the centre) and walks rows outward; honey-
    comb spacing keeps each plant equidistant from its six nearest
    neighbours. Returns an empty list if spacing is wider than the disc.
    """
    if radius_m <= 0 or spacing_m <= 0:
        return []
    row_spacing = spacing_m * math.sqrt(3.0) / 2.0
    if row_spacing > radius_m:
        # Even a single ring won't fit — just return the centre point.
        return [(0.0, 0.0)] if spacing_m <= radius_m * 2 else []
    positions: list[tuple[float, float]] = [(0.0, 0.0)]
    n_rows = int(math.floor(radius_m / row_spacing))
    for r in range(1, n_rows + 1):
        y = r * row_spacing
        x_shift = (spacing_m / 2.0) if (r % 2 == 1) else 0.0
        # Walk x outward from the shifted start, stopping when outside
        # the disc.
        k = 0
        while True:
            x = x_shift + k * spacing_m
            if math.sqrt(x * x + y * y) > radius_m:
                break
            positions.append((x, y))
            positions.append((-x if x > 0 else x, y))
            positions.append((x, -y))
            positions.append((-x if x > 0 else x, -y))
            k += 1
        # The k=0, x_shift=0 case duplicates (0, y), (0, -y) — dedupe.
    # Dedupe while preserving order.
    seen = set()
    unique: list[tuple[float, float]] = []
    for p in positions:
        key = (round(p[0], 6), round(p[1], 6))
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return unique


def stack_to_community_members(stack: list[dict]) -> list[dict]:
    """Hex-pack a ratio-weighted stack of species into a disc at the
    widest member's planting spacing. Returns member dicts ready to feed
    into ``polycultures.replace_polyculture_members``.

    Each input species dict carries at least ``id``, ``common_name``,
    ``spacing_m`` (or ``spacing_meters``), and an optional ``_weight``
    ratio integer. The total disc capacity is sized to fit
    ``sum(weights)`` positions at the max member spacing; species are
    distributed across positions in their ratios, then permuted to
    spread same-species members apart.
    """
    if not stack:
        return []
    species = []
    total_weight = 0
    for s in stack:
        pid = s.get("id") or s.get("plant_id")
        if not pid:
            continue
        weight = max(1, int(s.get("_weight") or s.get("weight") or 1))
        spacing = float(s.get("spacing_m") or s.get("spacing_meters") or 1.0)
        species.append({
            "id": int(pid),
            "common_name": s.get("common_name") or "",
            "spacing_m": spacing,
            "plant_type": s.get("plant_type") or "herb",
            "color": s.get("color") or s.get("marker_color") or "",
            "weight": weight,
        })
        total_weight += weight
    if not species:
        return []

    spacing_m = resolve_spacing(species, "max")
    # Pick a radius big enough to fit at least `total_weight` positions
    # plus a little slack so optimize_layout has somewhere to swap.
    n_target = max(total_weight, 1)
    # Hex disc capacity ≈ (π r² · 2) / (s²·√3). Solve for r:
    radius_m = math.sqrt(n_target * spacing_m * spacing_m * math.sqrt(3.0) / (2.0 * math.pi))
    radius_m = max(spacing_m, radius_m)
    positions = hex_pack_disc_local(radius_m, spacing_m)
    # Grow until we have enough positions (rare — only when packing wastes
    # the budget at small radii).
    grow_guard = 0
    while len(positions) < n_target and grow_guard < 10:
        radius_m *= 1.25
        positions = hex_pack_disc_local(radius_m, spacing_m)
        grow_guard += 1
    if len(positions) > n_target:
        positions = positions[:n_target]

    pseudo_latlng = [[y, x] for (x, y) in positions]
    assignments = assign_species(pseudo_latlng, species)
    try:
        assignments = optimize_layout(pseudo_latlng, assignments)
    except Exception:
        pass

    members: list[dict] = []
    for (x_m, y_m), sp in zip(positions, assignments):
        members.append({
            "plant_id":    int(sp["id"]),
            "common_name": sp.get("common_name") or "",
            "role":        "other",
            "layer":       None,
            "functions":   [],
            "color":       sp.get("color") or "",
            "spacing_m":   float(sp.get("spacing_m") or 1.0),
            "offset_x":    round(float(x_m), 2),
            "offset_y":    round(float(y_m), 2),
        })
    return members


def _to_local_xy(positions: list) -> list[tuple[float, float]]:
    """Project [lat, lng] into local metres (flat-earth, centroid origin)."""
    if not positions:
        return []
    mean_lat = sum(p[0] for p in positions) / len(positions)
    cos_lat = math.cos(math.radians(mean_lat))
    out = []
    for lat, lng in positions:
        x = lng * 111320.0 * cos_lat
        y = lat * 111320.0
        out.append((x, y))
    return out


def _pairwise_distances(pts_xy: list[tuple[float, float]]) -> list[list[float]]:
    n = len(pts_xy)
    d = [[0.0] * n for _ in range(n)]
    for i in range(n):
        xi, yi = pts_xy[i]
        for j in range(i + 1, n):
            dx = pts_xy[j][0] - xi
            dy = pts_xy[j][1] - yi
            dij = math.sqrt(dx * dx + dy * dy)
            d[i][j] = dij
            d[j][i] = dij
    return d


def _pair_energies(dists: list[list[float]], p: float) -> list[list[float]]:
    """Lookup of 1/d^p for each pair; coincident points get a huge
    finite penalty so the optimiser strongly avoids leaving them
    same-species but never blows up to inf."""
    n = len(dists)
    big = 1e12
    e = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = dists[i][j]
            v = big if d <= 1e-9 else 1.0 / (d ** p)
            e[i][j] = v
            e[j][i] = v
    return e


def _total_energy(assignments: list[dict],
                  energies: list[list[float]]) -> float:
    n = len(assignments)
    E = 0.0
    for i in range(n):
        si = assignments[i].get("id")
        for j in range(i + 1, n):
            if assignments[j].get("id") == si:
                E += energies[i][j]
    return E


def _swap_delta_e(assignments: list[dict],
                   energies: list[list[float]],
                   i: int, j: int, si, sj) -> float:
    """ΔE for swapping the species at positions i and j.

    Pre-computed per-pair energies make this O(N). The pair (i, j)
    itself contributes zero before and after the swap (it changes
    from si≠sj to sj≠si — still different species).
    """
    n = len(assignments)
    dE = 0.0
    for k in range(n):
        if k == i or k == j:
            continue
        sk = assignments[k].get("id")
        if sk == si:
            # Lose pair (i,k); gain pair (j,k).
            dE -= energies[i][k]
            dE += energies[j][k]
        elif sk == sj:
            # Lose pair (j,k); gain pair (i,k).
            dE -= energies[j][k]
            dE += energies[i][k]
    return dE
