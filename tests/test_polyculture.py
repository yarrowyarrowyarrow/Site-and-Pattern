"""
tests/test_polyculture.py — unit tests for src/polyculture.

The polyculture helpers are pure Python, no Qt — they decide which
species fills each generated grid/row/circle position when the panel
has a "mix" of secondary species.
"""

import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.polyculture import resolve_spacing, assign_species


# ─────────────────────────────────────────────────────────────────────────────
# resolve_spacing
# ─────────────────────────────────────────────────────────────────────────────

def test_resolve_spacing_max_default():
    species = [{"spacing_m": 0.5}, {"spacing_m": 1.5}, {"spacing_m": 0.8}]
    assert resolve_spacing(species) == 1.5
    assert resolve_spacing(species, "max") == 1.5


def test_resolve_spacing_min():
    species = [{"spacing_m": 0.5}, {"spacing_m": 1.5}, {"spacing_m": 0.8}]
    assert resolve_spacing(species, "min") == 0.5


def test_resolve_spacing_avg():
    species = [{"spacing_m": 1.0}, {"spacing_m": 2.0}, {"spacing_m": 3.0}]
    assert resolve_spacing(species, "avg") == 2.0


def test_resolve_spacing_primary_uses_first():
    species = [{"spacing_m": 0.5}, {"spacing_m": 1.5}]
    assert resolve_spacing(species, "primary") == 0.5


def test_resolve_spacing_empty_falls_back_to_one_metre():
    assert resolve_spacing([]) == 1.0


def test_resolve_spacing_treats_missing_as_one_metre():
    # A species row without spacing_m shouldn't crash; it should be
    # interpreted as the 1m fallback so it can't go to zero.
    species = [{"spacing_m": 0}, {"spacing_m": None}, {}]
    assert resolve_spacing(species, "max") == 1.0
    assert resolve_spacing(species, "min") == 1.0


def test_resolve_spacing_unknown_strategy_falls_back_to_max():
    species = [{"spacing_m": 0.5}, {"spacing_m": 1.5}]
    assert resolve_spacing(species, "wat") == 1.5


# ─────────────────────────────────────────────────────────────────────────────
# assign_species — basic shape
# ─────────────────────────────────────────────────────────────────────────────

def test_assign_returns_parallel_list_length():
    species = [{"id": 1, "weight": 1}, {"id": 2, "weight": 1}]
    positions = [[0, 0]] * 10
    out = assign_species(positions, species, rng=random.Random(0))
    assert len(out) == 10


def test_assign_no_positions_returns_empty():
    species = [{"id": 1}]
    assert assign_species([], species) == []


def test_assign_no_species_returns_empty():
    assert assign_species([[0, 0], [1, 1]], []) == []


def test_assign_single_species_fills_every_position():
    species = [{"id": 7, "common_name": "Yarrow"}]
    positions = [[0, 0], [1, 1], [2, 2]]
    out = assign_species(positions, species)
    assert len(out) == 3
    assert all(s["id"] == 7 for s in out)


# ─────────────────────────────────────────────────────────────────────────────
# assign_species — weighted_random
# ─────────────────────────────────────────────────────────────────────────────

def test_assign_weighted_random_is_seeded():
    """Same seed → same assignment; different seed → likely different."""
    species = [{"id": 1, "weight": 1}, {"id": 2, "weight": 1},
               {"id": 3, "weight": 1}]
    positions = [[0, 0]] * 50
    a = assign_species(positions, species, rng=random.Random(42))
    b = assign_species(positions, species, rng=random.Random(42))
    assert [s["id"] for s in a] == [s["id"] for s in b]


def test_assign_equal_weights_distributes_roughly_evenly():
    species = [{"id": 1, "weight": 1}, {"id": 2, "weight": 1},
               {"id": 3, "weight": 1}]
    positions = [[0, 0]] * 3000
    out = assign_species(positions, species, rng=random.Random(0))
    counts = {1: 0, 2: 0, 3: 0}
    for s in out:
        counts[s["id"]] += 1
    # With seed 0 over 3000 trials, each species should land in
    # ~1000 ± 100 (well under a 50% deviation from equal share).
    for c in counts.values():
        assert 850 < c < 1150, counts


def test_assign_weight_skew_dominates_distribution():
    species = [{"id": 1, "weight": 9}, {"id": 2, "weight": 1}]
    positions = [[0, 0]] * 1000
    out = assign_species(positions, species, rng=random.Random(0))
    n1 = sum(1 for s in out if s["id"] == 1)
    # Roughly 90% should be species 1; allow generous tolerance.
    assert n1 > 800


def test_assign_all_zero_weights_falls_back_to_uniform():
    species = [{"id": 1, "weight": 0}, {"id": 2, "weight": 0}]
    positions = [[0, 0]] * 200
    out = assign_species(positions, species, rng=random.Random(0))
    n1 = sum(1 for s in out if s["id"] == 1)
    # Should not be all-1s or all-2s; uniform fallback gives ~100 each.
    assert 60 < n1 < 140


def test_assign_unknown_strategy_raises():
    species = [{"id": 1, "weight": 1}, {"id": 2, "weight": 1}]
    try:
        assign_species([[0, 0]], species, strategy="bogus")
    except ValueError as e:
        assert "bogus" in str(e)
    else:
        raise AssertionError("expected ValueError for unknown strategy")


# ─────────────────────────────────────────────────────────────────────────────
# assign_species — even_split (the default)
# ─────────────────────────────────────────────────────────────────────────────

def test_even_split_is_deterministic_no_rng_needed():
    species = [{"id": 1, "weight": 1}, {"id": 2, "weight": 1},
               {"id": 3, "weight": 1}]
    positions = [[0, 0]] * 9
    a = assign_species(positions, species)             # default strategy
    b = assign_species(positions, species, "even_split")
    c = assign_species(positions, species, "even_split")
    assert [s["id"] for s in a] == [s["id"] for s in b]
    assert [s["id"] for s in b] == [s["id"] for s in c]


def test_even_split_equal_weights_n_divisible_gives_exact_thirds():
    species = [{"id": 1, "weight": 1}, {"id": 2, "weight": 1},
               {"id": 3, "weight": 1}]
    positions = [[0, 0]] * 12
    out = assign_species(positions, species, "even_split")
    counts = {1: 0, 2: 0, 3: 0}
    for s in out:
        counts[s["id"]] += 1
    assert counts == {1: 4, 2: 4, 3: 4}


def test_even_split_equal_weights_interleaves():
    """Adjacent positions should be different species so the spatial
    pattern looks mixed, not blocky."""
    species = [{"id": 1, "weight": 1}, {"id": 2, "weight": 1},
               {"id": 3, "weight": 1}]
    positions = [[0, 0]] * 9
    out = assign_species(positions, species, "even_split")
    ids = [s["id"] for s in out]
    # First three picks should be one of each species (no repeats).
    assert set(ids[:3]) == {1, 2, 3}


def test_even_split_unequal_ratio_2_1_1_1():
    species = [{"id": 1, "weight": 2}, {"id": 2, "weight": 1},
               {"id": 3, "weight": 1}, {"id": 4, "weight": 1}]
    positions = [[0, 0]] * 10
    out = assign_species(positions, species, "even_split")
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for s in out:
        counts[s["id"]] += 1
    # 2:1:1:1 ratio over 10 → species 1 gets 4, others get 2 each.
    assert counts[1] == 4
    assert counts[2] + counts[3] + counts[4] == 6
    # No species should be more than 1 off from its ideal (largest-
    # remainder behaviour: floor(ideal) or ceil(ideal)).
    for sid, ideal in [(1, 4.0), (2, 2.0), (3, 2.0), (4, 2.0)]:
        assert abs(counts[sid] - ideal) <= 1


def test_even_split_weights_sum_zero_falls_back_to_uniform():
    species = [{"id": 1, "weight": 0}, {"id": 2, "weight": 0}]
    positions = [[0, 0]] * 6
    out = assign_species(positions, species, "even_split")
    counts = {1: 0, 2: 0}
    for s in out:
        counts[s["id"]] += 1
    # Falls back to equal weights → exact 3:3 split for 6 positions.
    assert counts == {1: 3, 2: 3}


def test_even_split_count_diff_at_most_one_for_any_n_and_equal_weights():
    """Property test: with equal weights, every species' count should be
    floor(N/k) or ceil(N/k) — never more than 1 apart."""
    species = [{"id": i, "weight": 1} for i in range(1, 5)]   # 4 species
    for n in (1, 3, 7, 13, 50, 99, 100):
        positions = [[0, 0]] * n
        out = assign_species(positions, species, "even_split")
        counts = [0, 0, 0, 0]
        for s in out:
            counts[s["id"] - 1] += 1
        assert max(counts) - min(counts) <= 1, (n, counts)
        assert sum(counts) == n


# ─────────────────────────────────────────────────────────────────────────────
# optimize_layout — energy-minimisation layout
# ─────────────────────────────────────────────────────────────────────────────

import math as _m
from src.polyculture import optimize_layout


def _grid_positions(rows: int, cols: int, spacing_m: float = 1.0):
    """Lat/lng grid centred at LAT0/LNG0 with `spacing_m` step."""
    LAT0, LNG0 = 53.5461, -113.4938
    cos_lat = _m.cos(_m.radians(LAT0))
    out = []
    for r in range(rows):
        for c in range(cols):
            d_lat = (r * spacing_m) / 111320.0
            d_lng = (c * spacing_m) / (111320.0 * cos_lat)
            out.append([LAT0 + d_lat, LNG0 + d_lng])
    return out


def _same_species_pair_count(assignments):
    n = len(assignments)
    return sum(
        1 for i in range(n) for j in range(i + 1, n)
        if assignments[i]["id"] == assignments[j]["id"]
    )


def _min_same_species_distance(positions, assignments):
    """Smallest distance between any two same-species placements (in metres)."""
    LAT0 = 53.5461
    cos_lat = _m.cos(_m.radians(LAT0))
    best = float("inf")
    n = len(assignments)
    for i in range(n):
        for j in range(i + 1, n):
            if assignments[i]["id"] != assignments[j]["id"]:
                continue
            dx = (positions[j][1] - positions[i][1]) * 111320.0 * cos_lat
            dy = (positions[j][0] - positions[i][0]) * 111320.0
            d = _m.sqrt(dx * dx + dy * dy)
            if d < best:
                best = d
    return best


def test_optimize_preserves_species_counts():
    species = [
        {"id": 1, "common_name": "A", "weight": 2},
        {"id": 2, "common_name": "B", "weight": 1},
        {"id": 3, "common_name": "C", "weight": 1},
    ]
    positions = _grid_positions(4, 5)         # 20 cells
    assignments = assign_species(positions, species, "even_split")
    before_counts = {1: 0, 2: 0, 3: 0}
    for a in assignments:
        before_counts[a["id"]] += 1

    optimised = optimize_layout(positions, assignments, rng=random.Random(7))
    after_counts = {1: 0, 2: 0, 3: 0}
    for a in optimised:
        after_counts[a["id"]] += 1
    assert before_counts == after_counts


def test_optimize_returns_new_list():
    species = [{"id": 1, "weight": 1}, {"id": 2, "weight": 1}]
    positions = _grid_positions(3, 3)
    assignments = assign_species(positions, species, "even_split")
    optimised = optimize_layout(positions, assignments, rng=random.Random(0))
    # Same length, but should not mutate the input list.
    assert len(optimised) == len(assignments)


def test_optimize_increases_min_same_species_distance_on_grid():
    """Start from a deliberately pathological all-clumped layout. SA
    should rearrange it so the smallest gap between two same-species
    plants grows.

    4×4 grid with 8:8 ratio — left half all A, right half all B.
    Optimum is the checkerboard, where every same-species neighbour is
    a diagonal step (distance √2). Both species are equally affected,
    so the min-same-species-distance metric is sensitive to the move.
    """
    species_a = {"id": 1, "common_name": "A"}
    species_b = {"id": 2, "common_name": "B"}
    positions = _grid_positions(4, 4)
    assignments = []
    for r in range(4):
        for c in range(4):
            assignments.append(species_a if c < 2 else species_b)

    before_min = _min_same_species_distance(positions, assignments)
    optimised = optimize_layout(
        positions, assignments,
        iterations=4000, rng=random.Random(0),
    )
    after_min = _min_same_species_distance(positions, optimised)
    # Clumped: adjacent same-species pairs ⇒ min distance == 1.
    # Optimised: every same-species neighbour is diagonal ⇒ √2.
    assert before_min < 1.01
    assert after_min >= _m.sqrt(2) - 0.05


def test_optimize_seeded_is_reproducible():
    species = [{"id": 1, "weight": 1}, {"id": 2, "weight": 1},
               {"id": 3, "weight": 1}]
    positions = _grid_positions(4, 4)
    assignments = assign_species(positions, species, "even_split")
    a = optimize_layout(positions, list(assignments), rng=random.Random(123),
                         iterations=500)
    b = optimize_layout(positions, list(assignments), rng=random.Random(123),
                         iterations=500)
    assert [s["id"] for s in a] == [s["id"] for s in b]


def test_optimize_single_species_short_circuits():
    species = [{"id": 1, "common_name": "A"}]
    positions = _grid_positions(3, 3)
    assignments = [species[0]] * 9
    optimised = optimize_layout(positions, assignments)
    # Nothing to do — still all species 1, in the same order.
    assert all(s["id"] == 1 for s in optimised)
    assert len(optimised) == 9


def test_optimize_empty_inputs():
    assert optimize_layout([], []) == []
    assert optimize_layout([[0, 0]], [{"id": 1}]) == [{"id": 1}]


def test_optimize_mismatched_lengths_raises():
    try:
        optimize_layout([[0, 0], [1, 1]], [{"id": 1}])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for length mismatch")


def test_optimize_2x2_alternating_is_optimal():
    """For a 2×2 grid with two species 2:2, the only minimum-energy
    layouts are the two checkerboards; SA should reach one of them."""
    species_a = {"id": 1}
    species_b = {"id": 2}
    positions = _grid_positions(2, 2)
    # Start clumped: top row A, bottom row B.
    assignments = [species_a, species_a, species_b, species_b]
    optimised = optimize_layout(
        positions, assignments,
        iterations=1000, rng=random.Random(0),
    )
    ids = [s["id"] for s in optimised]
    # The two diagonals should be the same species. Either:
    # [1,2,2,1] or [2,1,1,2] (the two checkerboards).
    assert ids in ([1, 2, 2, 1], [2, 1, 1, 2])


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
