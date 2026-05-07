"""
tests/test_pattern_placement.py — Python ports of the JS pattern-placement
geometry helpers in html/map.html.

The JS implementations (_rowPositions, _gridPositions, _circlePositions,
_effectiveSpacing) are the canonical reference. These ports must remain
behaviourally equivalent so the Python tests catch regressions in the JS
math without firing up a browser.

Run with:
    python -m pytest tests/test_pattern_placement.py -v
"""

import math


# ─────────────────────────────────────────────────────────────────────────────
# Mirror of the JS helpers (kept dependency-free on purpose)
# ─────────────────────────────────────────────────────────────────────────────

def haversine_m(a, b):
    R = 6_371_000
    d_lat = math.radians(b[0] - a[0])
    d_lng = math.radians(b[1] - a[1])
    lat1 = math.radians(a[0])
    lat2 = math.radians(b[0])
    x = (math.sin(d_lat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x))


def effective_spacing(spacing_m: float, overlap: float) -> float:
    s = (spacing_m or 1.0) * (1.0 - (overlap or 0))
    return max(s, 0.01)


def row_positions(latA, lngA, latB, lngB, spacing_m, overlap, count=None):
    length = haversine_m([latA, lngA], [latB, lngB])
    s = effective_spacing(spacing_m, overlap)
    if count and count > 0:
        n = max(2, int(count))
    else:
        n = max(2, int(length // s) + 1)
    positions = []
    if n == 1:
        return [[latA, lngA]]
    for i in range(n):
        t = i / (n - 1)
        positions.append([latA + (latB - latA) * t,
                          lngA + (lngB - lngA) * t])
    return positions


def grid_positions(latA, lngA, latB, lngB, spacing_m, overlap,
                    rows=None, cols=None, stagger=False):
    s = effective_spacing(spacing_m, overlap)
    min_lat = min(latA, latB); max_lat = max(latA, latB)
    min_lng = min(lngA, lngB); max_lng = max(lngA, lngB)
    mid_lat = (min_lat + max_lat) / 2
    width_m  = haversine_m([mid_lat, min_lng], [mid_lat, max_lng])
    height_m = haversine_m([min_lat, min_lng], [max_lat, min_lng])
    n_cols = max(1, int(cols)) if cols and cols > 0 else max(1, int(width_m // s) + 1)
    n_rows = max(1, int(rows)) if rows and rows > 0 else max(1, int(height_m // s) + 1)
    d_lat = (max_lat - min_lat) / (n_rows - 1) if n_rows > 1 else 0
    d_lng = (max_lng - min_lng) / (n_cols - 1) if n_cols > 1 else 0
    positions = []
    for r in range(n_rows):
        row_lat = min_lat + d_lat * r
        offset = (d_lng / 2) if (stagger and r % 2 == 1) else 0
        for c in range(n_cols):
            col_lng = min_lng + d_lng * c + offset
            if col_lng > max_lng + 1e-9:
                continue
            positions.append([row_lat, col_lng])
    return positions


def circle_positions(center_lat, center_lng, radius_m, spacing_m, overlap,
                      count=None, fill=False):
    """Mirror of _circlePositions in html/map.html.

    fill=False → perimeter ring of `count` (or spacing-derived) plants.
    fill=True  → honeycomb hex pack inside the disc; centre plant is
                 first, then every plant has six equidistant neighbours
                 at exactly `s` metres.
    """
    s = effective_spacing(spacing_m, overlap)
    cos_lat = math.cos(math.radians(center_lat))
    if fill:
        disc = _hex_packed_disc(center_lat, center_lng, radius_m, s, cos_lat)
        if count and count > 0 and len(disc) > count:
            n = max(1, int(count))
            disc.sort(key=lambda p: (
                ((p[1] - center_lng) * 111320 * cos_lat) ** 2
                + ((p[0] - center_lat) * 111320) ** 2
            ))
            return disc[:n]
        return disc
    # Perimeter only.
    positions = []
    circumference = 2 * math.pi * radius_m
    n = max(3, int(count)) if count and count > 0 else max(3, int(circumference // s))
    for k in range(n):
        theta = (2 * math.pi * k) / n
        d_lat = (radius_m * math.cos(theta)) / 111320
        d_lng = (radius_m * math.sin(theta)) / (111320 * cos_lat)
        positions.append([center_lat + d_lat, center_lng + d_lng])
    return positions


def _hex_packed_disc(center_lat, center_lng, radius_m, s, cos_lat):
    row_spacing = s * math.sqrt(3) / 2
    max_row = int(math.ceil(radius_m / row_spacing)) + 1
    max_col = int(math.ceil(radius_m / s)) + 1
    r2 = radius_m * radius_m + 1e-3
    positions = [[center_lat, center_lng]]
    for r_idx in range(-max_row, max_row + 1):
        y = r_idx * row_spacing
        row_offset = (s / 2) if (r_idx & 1) else 0.0
        for c_idx in range(-max_col, max_col + 1):
            x = c_idx * s + row_offset
            if x * x + y * y <= r2:
                if abs(x) < 1e-6 and abs(y) < 1e-6:
                    continue
                positions.append([
                    center_lat + y / 111320,
                    center_lng + x / (111320 * cos_lat),
                ])
    return positions


# ─────────────────────────────────────────────────────────────────────────────
# Test fixtures — Edmonton-area centre, easy reasoning about ~1m precision
# ─────────────────────────────────────────────────────────────────────────────

LAT0, LNG0 = 53.5461, -113.4938


# ─────────────────────────────────────────────────────────────────────────────
# Effective spacing
# ─────────────────────────────────────────────────────────────────────────────

def test_effective_spacing_no_overlap():
    assert effective_spacing(2.0, 0.0) == 2.0


def test_effective_spacing_half_overlap():
    assert abs(effective_spacing(2.0, 0.5) - 1.0) < 1e-9


def test_effective_spacing_full_overlap_floors_at_1cm():
    # 100% overlap would mean centres coincide; the impl floors at 1cm
    # to avoid div-by-zero downstream.
    assert effective_spacing(2.0, 1.0) == 0.01


def test_effective_spacing_falls_back_to_1m_when_unset():
    # Mirrors the JS default: no spacing data → 1m default, then overlap.
    assert effective_spacing(0, 0) == 1.0
    assert effective_spacing(None, 0) == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Row mode
# ─────────────────────────────────────────────────────────────────────────────

def test_row_positions_endpoints_match_anchors():
    a = [LAT0, LNG0]
    b = [LAT0, LNG0 + 0.001]   # ~67m east
    pts = row_positions(a[0], a[1], b[0], b[1], spacing_m=10, overlap=0)
    assert pts[0] == a
    assert pts[-1] == b


def test_row_positions_count_override_wins():
    a = [LAT0, LNG0]
    b = [LAT0, LNG0 + 0.001]
    pts = row_positions(a[0], a[1], b[0], b[1], 1.0, 0, count=5)
    assert len(pts) == 5


def test_row_positions_spacing_drives_count():
    a = [LAT0, LNG0]
    b = [LAT0, LNG0 + 0.001]
    length = haversine_m(a, b)
    pts = row_positions(a[0], a[1], b[0], b[1], spacing_m=10, overlap=0)
    expected = max(2, int(length // 10) + 1)
    assert len(pts) == expected


def test_row_positions_overlap_increases_density():
    a = [LAT0, LNG0]
    b = [LAT0, LNG0 + 0.001]
    sparse = row_positions(a[0], a[1], b[0], b[1], 5.0, 0.0)
    dense  = row_positions(a[0], a[1], b[0], b[1], 5.0, 0.5)
    assert len(dense) >= len(sparse)


# ─────────────────────────────────────────────────────────────────────────────
# Grid mode
# ─────────────────────────────────────────────────────────────────────────────

def test_grid_explicit_rows_cols_count():
    a = [LAT0, LNG0]
    b = [LAT0 + 0.001, LNG0 + 0.001]
    pts = grid_positions(a[0], a[1], b[0], b[1], 5.0, 0,
                          rows=4, cols=3, stagger=False)
    assert len(pts) == 12


def test_grid_stagger_row_offset_is_half_dlng():
    a = [LAT0, LNG0]
    b = [LAT0 + 0.001, LNG0 + 0.001]
    pts = grid_positions(a[0], a[1], b[0], b[1], 5.0, 0,
                          rows=2, cols=3, stagger=True)
    # First row should have lng aligned with min_lng; second offset.
    row0_lngs = sorted({p[1] for p in pts if abs(p[0] - a[0]) < 1e-9})
    row1_lngs = sorted({p[1] for p in pts if abs(p[0] - b[0]) < 1e-9})
    d_lng = (b[1] - a[1]) / 2
    expected_offset = d_lng / 2
    # row1 starts ~half-step right of row0
    assert abs(row1_lngs[0] - (row0_lngs[0] + expected_offset)) < 1e-9


def test_grid_corner_order_independent():
    """Corner click order shouldn't matter."""
    a, b = [LAT0, LNG0], [LAT0 + 0.001, LNG0 + 0.001]
    pts1 = grid_positions(a[0], a[1], b[0], b[1], 5.0, 0, rows=3, cols=3)
    pts2 = grid_positions(b[0], b[1], a[0], a[1], 5.0, 0, rows=3, cols=3)
    s = lambda L: sorted((round(p[0], 9), round(p[1], 9)) for p in L)
    assert s(pts1) == s(pts2)


# ─────────────────────────────────────────────────────────────────────────────
# Circle mode
# ─────────────────────────────────────────────────────────────────────────────

def test_circle_count_override():
    pts = circle_positions(LAT0, LNG0, 20.0, 2.0, 0, count=8)
    assert len(pts) == 8


def test_circle_points_lie_on_circumference():
    R = 25.0
    pts = circle_positions(LAT0, LNG0, R, 2.0, 0, count=12)
    cos_lat = math.cos(math.radians(LAT0))
    for p in pts:
        d_lat_m = (p[0] - LAT0) * 111320
        d_lng_m = (p[1] - LNG0) * 111320 * cos_lat
        d = math.sqrt(d_lat_m ** 2 + d_lng_m ** 2)
        # Allow ~0.5% tolerance for the lat/lng ↔ metres approximation.
        assert abs(d - R) < 0.5, f"point {p} at distance {d:.2f} ≠ {R}"


def test_circle_fill_includes_centre_and_rings():
    pts = circle_positions(LAT0, LNG0, 30.0, 5.0, 0, fill=True)
    # First point should be the centre when fill=True
    assert pts[0] == [LAT0, LNG0]
    # And total points should exceed a single-ring placement
    single_ring = circle_positions(LAT0, LNG0, 30.0, 5.0, 0, fill=False)
    assert len(pts) > len(single_ring)


def test_circle_no_fill_does_not_place_centre():
    pts = circle_positions(LAT0, LNG0, 30.0, 5.0, 0, count=6, fill=False)
    # No centre point — every plant should be on the circumference
    assert [LAT0, LNG0] not in pts


def test_hex_fill_centre_is_first():
    """The hex-pack disc must emit the centre plant first so callers
    that rely on positions[0] (e.g. existing tests, the live preview)
    keep working."""
    pts = circle_positions(LAT0, LNG0, 25.0, 2.0, 0, fill=True)
    assert pts[0] == [LAT0, LNG0]


def test_hex_fill_each_plant_has_six_equidistant_neighbours():
    """Sanity check the honeycomb topology: pick the centre plant and
    confirm exactly six other plants sit at distance ≈ s. The hex
    invariant — six equidistant neighbours — is what makes this denser
    than a square grid (~91% packing vs ~78%)."""
    R = 30.0
    s = 4.0
    pts = circle_positions(LAT0, LNG0, R, s, 0, fill=True)
    cos_lat = math.cos(math.radians(LAT0))
    centre = pts[0]

    def metres(p, q):
        dx = (q[1] - p[1]) * 111320 * cos_lat
        dy = (q[0] - p[0]) * 111320
        return math.sqrt(dx * dx + dy * dy)

    near = [metres(centre, p) for p in pts[1:]]
    near.sort()
    # Tolerate ~0.1m for the lat/lng ↔ metres approximation.
    six = near[:6]
    for d in six:
        assert abs(d - s) < 0.1, six
    # 7th neighbour should be appreciably further (≥ s·sqrt(3)).
    assert near[6] > s * (math.sqrt(3) - 0.1)


def test_hex_fill_packs_more_densely_than_square_grid():
    """For the same radius and spacing, hex packing should fit more
    plants into the disc than a naive square grid (concentric rings
    layout)."""
    R = 20.0
    s = 2.0
    hex_pts = circle_positions(LAT0, LNG0, R, s, 0, fill=True)
    # Square-grid count inside the same disc (same R, s).
    cos_lat = math.cos(math.radians(LAT0))
    square_count = 0
    rng = int(R / s) + 1
    for c in range(-rng, rng + 1):
        for r in range(-rng, rng + 1):
            x = c * s
            y = r * s
            if x * x + y * y <= R * R:
                square_count += 1
    assert len(hex_pts) > square_count, (len(hex_pts), square_count)


def test_hex_fill_count_caps_total_plants():
    """Explicit count truncates the disc — closest-to-centre wins —
    so users can ask for `Total: N` without blowing up the renderer
    on large radii."""
    pts = circle_positions(LAT0, LNG0, 50.0, 1.0, 0, count=20, fill=True)
    assert len(pts) == 20
    # Centre stays in the cap (it's the closest point to itself).
    assert pts[0] == [LAT0, LNG0]
    # Every cap entry must be inside the disc and nearer to centre
    # than any rejected entry — verify by re-running uncapped and
    # confirming our 20 are all in the closest-20.
    uncapped = circle_positions(LAT0, LNG0, 50.0, 1.0, 0, fill=True)
    assert len(uncapped) > len(pts)
    cos_lat = math.cos(math.radians(LAT0))

    def d2(p):
        dx = (p[1] - LNG0) * 111320 * cos_lat
        dy = (p[0] - LAT0) * 111320
        return dx * dx + dy * dy

    uncapped_sorted = sorted(uncapped, key=d2)
    expected_set = {(round(p[0], 9), round(p[1], 9)) for p in uncapped_sorted[:20]}
    actual_set = {(round(p[0], 9), round(p[1], 9)) for p in pts}
    assert actual_set == expected_set


def test_hex_fill_count_zero_means_no_cap():
    """count=0 (or omitted) should leave the radius-derived count alone."""
    pts_unset = circle_positions(LAT0, LNG0, 12.0, 2.0, 0, fill=True)
    pts_zero  = circle_positions(LAT0, LNG0, 12.0, 2.0, 0, count=0, fill=True)
    assert len(pts_unset) == len(pts_zero)


def test_hex_fill_no_plants_outside_disc():
    R = 15.0
    s = 1.5
    pts = circle_positions(LAT0, LNG0, R, s, 0, fill=True)
    cos_lat = math.cos(math.radians(LAT0))
    for p in pts:
        dx = (p[1] - LNG0) * 111320 * cos_lat
        dy = (p[0] - LAT0) * 111320
        d = math.sqrt(dx * dx + dy * dy)
        # Allow ~1 cm tolerance for the boundary cells.
        assert d <= R + 0.05, (p, d)


# ─────────────────────────────────────────────────────────────────────────────
# Project round-trip with placement_group_id
# ─────────────────────────────────────────────────────────────────────────────

def test_placement_group_id_roundtrips():
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import src.project as project_io

    proj = project_io.new_project("Group test")
    gid = project_io.new_placement_group_id()
    for lng, lat in [(-113.50, 53.55), (-113.51, 53.55), (-113.52, 53.55)]:
        proj["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": "plant",
                "plant_id": 7,
                "common_name": "Test",
                "placement_group_id": gid,
                "pattern_kind": "row",
                "quantity": 1,
            }
        })

    data = project_io.project_to_map_data(proj)
    assert len(data["plants"]) == 3
    assert all(p["placement_group_id"] == gid for p in data["plants"])


def test_legacy_plant_features_get_unique_singleton_groups():
    """Legacy projects without placement_group_id load with one fresh id each."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import src.project as project_io

    proj = project_io.new_project("Legacy")
    for lng, lat in [(-113.50, 53.55), (-113.51, 53.55)]:
        proj["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": "plant",
                "plant_id": 1,
                "common_name": "Legacy plant",
            }
        })

    data = project_io.project_to_map_data(proj)
    ids = [p["placement_group_id"] for p in data["plants"]]
    assert all(i.startswith("pg_") for i in ids)
    # Each legacy plant gets its own singleton group.
    assert len(set(ids)) == 2


def test_new_placement_group_id_is_unique():
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import src.project as project_io
    seen = {project_io.new_placement_group_id() for _ in range(200)}
    assert len(seen) == 200


# ─────────────────────────────────────────────────────────────────────────────
# Marquee hit-test logic — pure Python mirror of the JS implementation
# ─────────────────────────────────────────────────────────────────────────────

def _bounds_contains(bounds, pt):
    (south, west), (north, east) = bounds
    return south <= pt[0] <= north and west <= pt[1] <= east


def marquee_hit_test(bounds, plants, boundaries=(), sectors=(), sun_path=None):
    """Mirror of the JS _marqueeHitTest: returns (hit_kinds, hit_ids)."""
    hits = []
    for p in plants:
        if _bounds_contains(bounds, (p["lat"], p["lng"])):
            hits.append(("plant", p["marker_id"]))
    for b in boundaries:
        if any(_bounds_contains(bounds, pt) for pt in b["points"]):
            hits.append(("boundary", b["id"]))
    for s in sectors:
        if _bounds_contains(bounds, (s["lat"], s["lng"])):
            hits.append(("sector", s["id"]))
    if sun_path is not None and _bounds_contains(bounds, sun_path):
        hits.append(("sunpath", None))
    return hits


def test_marquee_hits_only_inside_bounds():
    bounds = ((53.500, -113.500), (53.510, -113.490))
    plants = [
        {"marker_id": "a", "lat": 53.505, "lng": -113.495},   # inside
        {"marker_id": "b", "lat": 53.520, "lng": -113.495},   # outside (north)
        {"marker_id": "c", "lat": 53.505, "lng": -113.480},   # outside (east)
    ]
    hits = marquee_hit_test(bounds, plants)
    assert hits == [("plant", "a")]


def test_marquee_picks_boundaries_via_any_vertex():
    bounds = ((53.500, -113.500), (53.510, -113.490))
    boundaries = [
        # one vertex inside the rect → hit
        {"id": "b1", "points": [
            (53.450, -113.510), (53.505, -113.495), (53.450, -113.480),
        ]},
        # all vertices outside → miss
        {"id": "b2", "points": [
            (53.450, -113.510), (53.450, -113.480),
        ]},
    ]
    hits = marquee_hit_test(bounds, [], boundaries=boundaries)
    assert ("boundary", "b1") in hits
    assert ("boundary", "b2") not in hits


def test_marquee_sectors_and_sunpath():
    bounds = ((53.500, -113.500), (53.510, -113.490))
    sectors = [
        {"id": "s1", "lat": 53.505, "lng": -113.495},  # in
        {"id": "s2", "lat": 53.530, "lng": -113.495},  # out
    ]
    hits = marquee_hit_test(bounds, [], sectors=sectors,
                             sun_path=(53.506, -113.493))
    assert ("sector", "s1") in hits
    assert ("sector", "s2") not in hits
    assert ("sunpath", None) in hits


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed of {passed + failed}.")
    sys.exit(0 if failed == 0 else 1)
