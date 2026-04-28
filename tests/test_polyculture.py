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


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
