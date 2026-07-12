"""
Tests for src/tree_detect.py — satellite tree-crown detection (V2.26).

No network and no Qt: the tile fetcher returns (z, x, y) keys and the
injectable decoder renders a synthetic scene in global pixel coordinates, so
the whole pipeline (mosaic → vegetation gate → Otsu split → components →
chamfer → disk packing → import tail) runs against ground truth.
"""

import math
import unittest

from src import tree_detect
from src.osm_features import add_features_to_project

_Z = 19
_LAT, _LNG = 53.5, -113.3       # Sherwood Park-ish; math must work anywhere

# Scene palette (r, g, b) — chosen against the detector's documented gates:
TAN = (185, 160, 130)       # dry ground: ExG = 5  → not vegetation
LAWN = (110, 170, 90)       # bright lawn: ExG = 140, brightness 135
CROWN = (40, 70, 40)        # dark crown:  ExG = 60,  brightness 55
DARK_LAWN = CROWN           # dark but *smooth* — lawn in shade / lush park
ROOF = (120, 120, 125)      # building:    ExG = −5 → not vegetation


SHADOW = (55, 62, 52)       # cast shadow: dark (lum 57), ExG 17 → not veg


def crown_texture(gx, gy):
    """A real crown at yard scale: dark green with strong pixel-to-pixel
    brightness swings (sunlit tufts + self-shadow). Equal-channel jitter
    keeps ExG and hue identical to CROWN while the internal-contrast gate
    sees ±24 — a lit crown even under the strict no-shadow bar."""
    j = ((gx * 31 + gy * 17) % 49) - 24
    return (CROWN[0] + j, CROWN[1] + j, CROWN[2] + j)


def dim_crown_texture(gx, gy):
    """Marginal internal contrast (±17): passes the normal direct-light gate
    but NOT the strict bar that applies when a photo has no legible shadows."""
    j = ((gx * 31 + gy * 17) % 35) - 17
    return (CROWN[0] + j, CROWN[1] + j, CROWN[2] + j)


def deciduous_texture(gx, gy):
    """A leafed-out broadleaf crown: brighter, saturated green (lum ≈ 91,
    ExG ≈ 115, g−b ≈ 65), still rough — wide jitter so the internal-contrast
    (sunlit-tuft) gate reads it as a lit crown."""
    j = ((gx * 31 + gy * 17) % 41) - 20
    return (70 + j, 120 + j, 55 + j)


def shadow_on_grass_texture(gx, gy):
    """Tree shadow cast ON grass: dark (lum ≈ 64), green enough to pass the
    vegetation gate (ExG ≈ 31), textured enough to pass the 3×3 texture gate
    (±8 jitter) — but with NO direct light, so its internal contrast stays
    far below a sunlit crown's. The park mega-blob poison."""
    j = ((gx * 13 + gy * 7) % 17) - 8
    return (58 + j, 72 + j, 55 + j)


def _shadow_band(cx, cy, r, length, disk_r=None):
    """Disks painting a northward cast shadow for a crown/building at
    (cx, cy) of radius r: a contiguous dark band from just past the edge to
    ``length`` px beyond it (screen north = −y; bearing bin 0)."""
    rr = disk_r if disk_r is not None else max(3, int(0.7 * r))
    return [(cx, cy - (r + k), rr, SHADOW) for k in range(2, length + 1, 2)]


def _shadowed_crown(cx, cy, r, shadow_len):
    """A textured crown plus its northward shadow. Shadow disks first would
    overpaint the crown, so crown goes first in the disk list (first match
    wins in _disk_scene)."""
    return [(cx, cy, r, crown_texture)] + _shadow_band(cx, cy, r, shadow_len)


def _center_px():
    x, y = tree_detect._latlng_to_global_px(_LAT, _LNG, _Z)
    return int(x), int(y)


def _bbox_around(lat, lng, half_m):
    dlat = half_m / 111320.0
    dlng = half_m / (111320.0 * math.cos(math.radians(lat)))
    return {"north": lat + dlat, "south": lat - dlat,
            "east": lng + dlng, "west": lng - dlng}


def _fetch_key(z, x, y):
    return (z, x, y)


def _scene_decoder(scene):
    """Render one 256×256 tile of ``scene(gx, gy) -> (r, g, b)``."""
    def decode(key):
        _z, tx, ty = key
        buf = bytearray(256 * 256 * 3)
        i = 0
        base_y = ty * 256
        base_x = tx * 256
        for row in range(256):
            gy = base_y + row
            for col in range(256):
                r, g, b = scene(base_x + col, gy)
                buf[i] = r
                buf[i + 1] = g
                buf[i + 2] = b
                i += 3
        return (256, 256, bytes(buf))
    return decode


def _disk_scene(disks, background=TAN, extras=()):
    """Scene of coloured disks [(cx, cy, r, colour), …] over ``background``,
    plus rectangles [(x0, y0, x1, y1, colour), …] painted first. A ``colour``
    may be a callable ``(gx, gy) -> (r, g, b)`` for textured surfaces."""
    def scene(gx, gy):
        for (cx, cy, r, colour) in disks:
            if (gx - cx) ** 2 + (gy - cy) ** 2 <= r * r:
                return colour(gx, gy) if callable(colour) else colour
        for (x0, y0, x1, y1, colour) in extras:
            if x0 <= gx <= x1 and y0 <= gy <= y1:
                return colour(gx, gy) if callable(colour) else colour
        return background
    return scene


def _dist_m(lat1, lng1, lat2, lng2):
    cos_lat = math.cos(math.radians(lat1))
    dx = (lng2 - lng1) * 111320.0 * cos_lat
    dy = (lat2 - lat1) * 111320.0
    return math.hypot(dx, dy)


class TestTileMath(unittest.TestCase):
    def test_roundtrip(self):
        x, y = tree_detect._latlng_to_global_px(_LAT, _LNG, _Z)
        lat, lng = tree_detect._global_px_to_latlng(x, y, _Z)
        self.assertAlmostEqual(lat, _LAT, places=6)
        self.assertAlmostEqual(lng, _LNG, places=6)

    def test_axes_orientation(self):
        x0, y0 = tree_detect._latlng_to_global_px(_LAT, _LNG, _Z)
        x_e, _ = tree_detect._latlng_to_global_px(_LAT, _LNG + 0.001, _Z)
        _, y_n = tree_detect._latlng_to_global_px(_LAT + 0.001, _LNG, _Z)
        self.assertGreater(x_e, x0)     # east → larger x
        self.assertLess(y_n, y0)        # north → smaller y

    def test_m_per_px_matches_ground_scale(self):
        # One pixel step east should measure ~m_per_px metres on the ground.
        mpp = tree_detect._m_per_px(_LAT, _Z)
        x, y = tree_detect._latlng_to_global_px(_LAT, _LNG, _Z)
        lat2, lng2 = tree_detect._global_px_to_latlng(x + 1, y, _Z)
        self.assertAlmostEqual(_dist_m(_LAT, _LNG, lat2, lng2), mpp,
                               delta=mpp * 0.02)

    def test_pick_zoom_respects_tile_budget(self):
        # A moderately large boundary steps the zoom down to fit the budget…
        big = _bbox_around(_LAT, _LNG, 600.0)       # a 1.2 km square
        z = tree_detect._pick_zoom(big, max_tiles=28)
        self.assertLess(z, 19)
        tx0, ty0, tx1, ty1 = tree_detect._tile_range(big, z)
        self.assertLessEqual((tx1 - tx0 + 1) * (ty1 - ty0 + 1), 28)
        # …but never below the floor where crowns stop being resolvable.
        huge = _bbox_around(_LAT, _LNG, 5000.0)
        self.assertEqual(tree_detect._pick_zoom(huge, max_tiles=28), 16)
        small = _bbox_around(_LAT, _LNG, 30.0)
        self.assertEqual(tree_detect._pick_zoom(small), 19)

    def test_over_budget_scan_is_cropped_and_flagged(self):
        # Past the zoom floor the scan crops to the central block that fits
        # the tile budget — never hundreds of fetches — and flags coverage.
        fetched = []

        def counting_fetch(z, x, y):
            fetched.append((z, x, y))
            return (z, x, y)

        res = tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 1500.0), max_tiles=4,
            _fetch_tile=counting_fetch,
            _decode=_scene_decoder(_disk_scene([])))
        self.assertIsNotNone(res)
        self.assertLessEqual(len(fetched), 4)
        self.assertTrue(res["partial"])


class TestDetection(unittest.TestCase):
    def test_detects_crowns_not_lawn_or_roof(self):
        cx, cy = _center_px()
        crowns = [(cx - 60, cy - 20, 20), (cx + 55, cy + 45, 12)]
        scene = _disk_scene(
            [(x, y, r, crown_texture) for (x, y, r) in crowns],
            extras=[(cx - 30, cy + 30, cx + 20, cy + 70, LAWN),
                    (cx - 100, cy + 60, cx - 40, cy + 100, ROOF)])
        res = tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 30.0),
            _fetch_tile=_fetch_key, _decode=_scene_decoder(scene))
        self.assertIsNotNone(res)
        trees = res["trees"]
        self.assertEqual(len(trees), len(crowns))
        mpp = res["m_per_px"]
        for (gx, gy, r_px) in crowns:
            tlat, tlng = tree_detect._global_px_to_latlng(gx + 0.5, gy + 0.5,
                                                          _Z)
            best = min(trees, key=lambda t: _dist_m(tlat, tlng,
                                                    t["lat"], t["lng"]))
            self.assertLess(_dist_m(tlat, tlng, best["lat"], best["lng"]),
                            3.5 * mpp)
            truth_r = r_px * mpp
            self.assertGreater(best["radius_m"], truth_r * 0.6)
            self.assertLess(best["radius_m"], truth_r * 1.4)
            self.assertGreaterEqual(best["height_m"], 3.0)
            self.assertLessEqual(best["height_m"], 18.0)
            self.assertEqual(best["label"], "Tree (detected)")
            self.assertEqual(best["source"], "imagery")
            self.assertEqual(best["kind"], "tree")

    def test_shelterbelt_row_splits_into_trees(self):
        cx, cy = _center_px()
        r, spacing = 12, 22          # overlapping row → one connected blob
        row = [(cx - spacing, cy, r), (cx, cy, r), (cx + spacing, cy, r)]
        scene = _disk_scene([(x, y, rr, crown_texture) for (x, y, rr) in row])
        res = tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 30.0),
            _fetch_tile=_fetch_key, _decode=_scene_decoder(scene))
        self.assertIsNotNone(res)
        self.assertEqual(len(res["trees"]), 3)

    def test_all_lawn_finds_nothing(self):
        scene = _disk_scene([], background=LAWN)
        res = tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 30.0),
            _fetch_tile=_fetch_key, _decode=_scene_decoder(scene))
        self.assertIsNotNone(res)       # imagery read fine — an honest zero
        self.assertEqual(res["trees"], [])

    def test_dark_smooth_lawn_is_not_trees(self):
        # The V2.26 park regression: a big *dark but smooth* patch of grass
        # (shaded / lush lawn) passes the darkness split but must fail the
        # texture gate — only the genuinely rough crown is a tree.
        cx, cy = _center_px()
        scene = _disk_scene(
            [(cx + 60, cy - 30, 16, crown_texture)],
            background=LAWN,
            extras=[(cx - 110, cy - 20, cx - 10, cy + 60, DARK_LAWN)])
        res = tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 30.0),
            _fetch_tile=_fetch_key, _decode=_scene_decoder(scene))
        self.assertIsNotNone(res)
        self.assertEqual(len(res["trees"]), 1)
        tlat, tlng = tree_detect._global_px_to_latlng(cx + 60.5, cy - 29.5,
                                                      _Z)
        t = res["trees"][0]
        self.assertLess(_dist_m(tlat, tlng, t["lat"], t["lng"]),
                        3.5 * res["m_per_px"])

    def test_fetch_failure_is_failure_not_zero(self):
        res = tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 30.0),
            _fetch_tile=lambda z, x, y: None,
            _decode=_scene_decoder(_disk_scene([])))
        self.assertIsNone(res)
        # And with no decoder at all (no codec) — same honest failure.
        self.assertIsNone(tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 30.0),
            _fetch_tile=_fetch_key, _decode=None))


class TestShadowPhysics(unittest.TestCase):
    """The V2.26 second-pass gates: grass can mimic canopy colour, darkness
    and texture, but it can't cast a consistent shadow or be darker than
    its own surroundings."""

    def test_shadowless_dark_patches_culled_by_consensus(self):
        # Park regression v2: textured dark patches (mottled grass) pass the
        # colour/darkness/texture gates — but four real crowns agree on a
        # northward shadow bearing, and the patches have no such shadow.
        cx, cy = _center_px()
        disks = []
        crowns = [(cx - 80, cy - 40, 11), (cx - 30, cy - 55, 12),
                  (cx + 40, cy - 35, 11), (cx + 85, cy + 10, 12)]
        for (x, y, r) in crowns:
            disks += _shadowed_crown(x, y, r, 2 * r)
        fakes = [(cx - 70, cy + 55, 12), (cx + 5, cy + 65, 11),
                 (cx + 70, cy + 60, 12)]
        disks += [(x, y, r, crown_texture) for (x, y, r) in fakes]
        res = tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 30.0),
            _fetch_tile=_fetch_key, _decode=_scene_decoder(_disk_scene(disks)))
        self.assertIsNotNone(res)
        self.assertEqual(res["shadow_bearing"], "N")
        self.assertEqual(len(res["trees"]), len(crowns))
        mpp = res["m_per_px"]
        for (gx, gy, _r) in crowns:
            tlat, tlng = tree_detect._global_px_to_latlng(gx + 0.5, gy + 0.5,
                                                          _Z)
            best = min(_dist_m(tlat, tlng, t["lat"], t["lng"])
                       for t in res["trees"])
            self.assertLess(best, 3.5 * mpp)
        self.assertEqual(res["dropped"]["shadow"], len(fakes))
        for t in res["trees"]:
            self.assertIn("shadow-verified", t["detect_confidence"])

    def test_building_shadow_anchors_tree_heights(self):
        # The creative anchor: a building of KNOWN height casts a shadow in
        # the same photo — tan(sun elevation) = height / shadow length turns
        # every tree's shadow into a measured height. Two trees, one with a
        # shadow twice as long, must come out ≈ twice as tall.
        cx, cy = _center_px()
        r = 10
        disks = _shadowed_crown(cx - 70, cy, r, 24)      # short shadow
        disks += _shadowed_crown(cx + 70, cy, r, 48)     # double shadow
        disks += _shadowed_crown(cx - 20, cy + 50, r, 24)  # 3rd voter
        # Building: 20×16 px roof + a 40 px northward shadow band.
        bx0, by0, bx1, by1 = cx - 10, cy - 60, cx + 10, cy - 44
        bcx, bcy = (bx0 + bx1) // 2, (by0 + by1) // 2
        extras = [(bx0, by0, bx1, by1, ROOF)]
        disks += _shadow_band(bcx, by0, 0, 40, disk_r=6)
        ring = []
        for (vx, vy) in ((bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)):
            vlat, vlng = tree_detect._global_px_to_latlng(vx, vy, _Z)
            ring.append([vlng, vlat])
        blat, blng = tree_detect._global_px_to_latlng(bcx + 0.5, bcy + 0.5,
                                                      _Z)
        res = tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 30.0),
            buildings=[{"lat": blat, "lng": blng, "height_m": 5.0,
                        "ring": ring}],
            _fetch_tile=_fetch_key,
            _decode=_scene_decoder(_disk_scene(disks, extras=extras)))
        self.assertIsNotNone(res)
        self.assertIsNotNone(res["shadow_bearing"])
        self.assertEqual((res["anchor"] or {}).get("type"), "building")
        self.assertEqual(len(res["trees"]), 3)
        short = [t for t in res["trees"] if abs(t["lng"] - blng) > 0
                 and t["lng"] < blng and abs(t["lat"] - blat) < 1e-4]
        tall = [t for t in res["trees"] if t["lng"] > blng]
        self.assertEqual(len(tall), 1)
        self.assertTrue(short)
        ratio = tall[0]["height_m"] / max(t["height_m"] for t in short)
        self.assertGreater(ratio, 1.5)      # double shadow ≈ double height
        self.assertLess(ratio, 2.6)
        for t in res["trees"]:              # sane absolute range
            self.assertGreaterEqual(t["height_m"], 3.0)
            self.assertLessEqual(t["height_m"], 25.0)

    def test_foliage_tagging(self):
        cx, cy = _center_px()
        res = tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 30.0), _fetch_tile=_fetch_key,
            _decode=_scene_decoder(_disk_scene(
                [(cx, cy, 14, crown_texture)])))
        self.assertEqual(len(res["trees"]), 1)
        self.assertEqual(res["trees"][0]["foliage"], "evergreen")
        res2 = tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 30.0), _fetch_tile=_fetch_key,
            _decode=_scene_decoder(_disk_scene(
                [(cx, cy, 14, deciduous_texture)])))
        self.assertEqual(len(res2["trees"]), 1)
        self.assertEqual(res2["trees"][0]["foliage"], "deciduous")

    def test_shadow_swath_on_grass_yields_no_trees(self):
        # Park regression v3 (the mega-blob): long tree shadows falling ON
        # grass are dark AND green AND textured, so they enter the canopy
        # mask and weld crowns + lawn into one giant blob. But cast shadow
        # receives no direct light — the internal-contrast gate drops those
        # disks and hands their pixels to the shadow stages instead.
        cx, cy = _center_px()
        disks = []
        crowns = [(cx - 50, cy - 30, 11), (cx, cy - 30, 12),
                  (cx + 50, cy - 30, 11)]
        for (x, y, r) in crowns:
            disks += _shadowed_crown(x, y, r, 2 * r)
        # A big shadow swath attached to the crown row (welds the blob),
        # spreading south-east where no crown shadow belongs.
        extras = [(cx - 60, cy - 20, cx + 70, cy + 25,
                   shadow_on_grass_texture)]
        res = tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 30.0), _fetch_tile=_fetch_key,
            _decode=_scene_decoder(_disk_scene(disks, background=LAWN,
                                               extras=extras)))
        self.assertIsNotNone(res)
        self.assertGreater(res["dropped"]["flat"], 0)
        self.assertEqual(len(res["trees"]), len(crowns))
        mpp = res["m_per_px"]
        for (gx, gy, _r) in crowns:
            tlat, tlng = tree_detect._global_px_to_latlng(gx + 0.5, gy + 0.5,
                                                          _Z)
            best = min(_dist_m(tlat, tlng, t["lat"], t["lng"])
                       for t in res["trees"])
            self.assertLess(best, 3.5 * mpp)

    def test_capped_result_truncates_not_aborts(self):
        # With the physics gates in front, hitting the cap means a genuinely
        # busy/tree-dense read — import the (already strongest-first) trees
        # and say the cap was hit, rather than refusing wholesale.
        dlng = 5.0 / (111320.0 * math.cos(math.radians(_LAT)))
        res = {"trees": [{"kind": "tree", "lat": _LAT, "lng": _LNG + i * dlng,
                          "radius_m": 3.0, "height_m": 8.0}
                         for i in range(3)],
               "capped": True, "m_per_px": 0.18, "zoom": 19,
               "tiles_ok": 9, "tiles_failed": 0, "partial": False}
        project = {"features": []}
        out = tree_detect.import_detected_trees(res, project)
        self.assertEqual(out["added"], 3)
        self.assertIn("safety cap", out["message"])
        self.assertIn("strongest", out["message"])

    def test_short_shadow_retry_finds_high_sun_bearing(self):
        # Near-noon capture: shadows are a thin fringe the standard band
        # misses — the tight-band retry must still elect a bearing and keep
        # the shadow gate online (the third park run regression: bearing
        # None made the fallback too permissive).
        cx, cy = _center_px()
        disks = []
        crowns = [(cx - 60, cy - 20, 12), (cx, cy - 40, 12),
                  (cx + 60, cy, 12)]
        for (x, y, r) in crowns:
            disks.append((x, y, r, crown_texture))
            disks += _shadow_band(x, y, r, 4, disk_r=2)   # 4 px fringe
        fakes = [(cx - 50, cy + 55, 12), (cx + 45, cy + 60, 12)]
        disks += [(x, y, r, crown_texture) for (x, y, r) in fakes]
        res = tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 30.0), _fetch_tile=_fetch_key,
            _decode=_scene_decoder(_disk_scene(disks)))
        self.assertIsNotNone(res)
        self.assertEqual(res["shadow_bearing"], "N")
        self.assertEqual(len(res["trees"]), len(crowns))
        self.assertEqual(res["dropped"]["shadow"], len(fakes))

    def test_no_shadow_fallback_is_strict(self):
        # With genuinely no shadows anywhere, evidence is thinner — the
        # internal-contrast bar rises, so marginal candidates are dropped
        # while strongly-lit crowns survive.
        cx, cy = _center_px()
        res = tree_detect.detect_trees(
            _bbox_around(_LAT, _LNG, 30.0), _fetch_tile=_fetch_key,
            _decode=_scene_decoder(_disk_scene(
                [(cx - 40, cy, 13, crown_texture),
                 (cx + 45, cy + 10, 13, dim_crown_texture)])))
        self.assertIsNotNone(res)
        self.assertIsNone(res["shadow_bearing"])
        self.assertEqual(len(res["trees"]), 1)
        self.assertEqual(res["dropped"]["weak"], 1)
        tlat, tlng = tree_detect._global_px_to_latlng(cx - 39.5, cy + 0.5,
                                                      _Z)
        t = res["trees"][0]
        self.assertLess(_dist_m(tlat, tlng, t["lat"], t["lng"]),
                        3.5 * res["m_per_px"])


class TestCanopyMaskGuards(unittest.TestCase):
    def _uniform(self, brightness, n=2048):
        veg = bytearray([1] * n)
        bright = bytearray([brightness] * n)
        hist = [0] * 256
        hist[brightness] = n
        return veg, bright, hist

    def test_uniform_bright_vegetation_is_lawn(self):
        veg, bright, hist = self._uniform(135)
        self.assertIsNone(tree_detect._canopy_mask(veg, bright, hist,
                                                   64, 32))

    def test_uniform_dark_vegetation_is_forest(self):
        veg, bright, hist = self._uniform(55)
        mask = tree_detect._canopy_mask(veg, bright, hist, 64, 32)
        self.assertIsNotNone(mask)
        self.assertEqual(sum(mask), len(veg))

    def test_bimodal_splits_on_darkness(self):
        n = 1024
        veg = bytearray([1] * (2 * n))
        bright = bytearray([55] * n + [135] * n)
        hist = [0] * 256
        hist[55] = n
        hist[135] = n
        mask = tree_detect._canopy_mask(veg, bright, hist, 64, 32)
        self.assertEqual(sum(mask[:n]), n)      # dark half kept
        self.assertEqual(sum(mask[n:]), 0)      # bright half dropped


class TestImportTail(unittest.TestCase):
    def _tree(self, lat, lng, radius=3.0):
        return {"kind": "tree", "lat": lat, "lng": lng,
                "radius_m": radius, "height_m": 8.0,
                "label": "Tree (detected)", "source": "imagery",
                "dedupe_m": max(2.0, 0.8 * radius)}

    def _res(self, trees):
        return {"trees": trees, "zoom": _Z, "m_per_px": 0.18,
                "tiles_ok": 4, "tiles_failed": 0, "capped": False}

    def test_failure_message_is_honest(self):
        out = tree_detect.import_detected_trees(None, {"features": []})
        self.assertEqual(out["added"], 0)
        self.assertIn("nothing was imported", out["message"])

    def test_alignment_offset_shifts_positions(self):
        project = {"features": []}
        out = tree_detect.import_detected_trees(
            self._res([self._tree(_LAT, _LNG)]), project,
            offset_east_m=5.0, offset_north_m=-3.0)
        self.assertEqual(out["added"], 1)
        lng, lat = project["features"][0]["geometry"]["coordinates"]
        cos_lat = math.cos(math.radians(_LAT))
        self.assertAlmostEqual((lng - _LNG) * 111320.0 * cos_lat, 5.0,
                               delta=0.05)
        self.assertAlmostEqual((lat - _LAT) * 111320.0, -3.0, delta=0.05)

    def test_boundary_and_margin_clip(self):
        half = 20.0 / 111320.0
        dlng = 20.0 / (111320.0 * math.cos(math.radians(_LAT)))
        boundary = [(_LAT - half, _LNG - dlng), (_LAT - half, _LNG + dlng),
                    (_LAT + half, _LNG + dlng), (_LAT + half, _LNG - dlng)]
        far_lng = _LNG + 100.0 / (111320.0 * math.cos(math.radians(_LAT)))
        project = {"features": []}
        out = tree_detect.import_detected_trees(
            self._res([self._tree(_LAT, _LNG), self._tree(_LAT, far_lng)]),
            project, boundary=boundary, margin_m=30.0)
        self.assertEqual(out["found"], 2)
        self.assertEqual(out["kept"], 1)
        self.assertEqual(out["added"], 1)
        self.assertIn("inside your boundary", out["message"])

    def test_dedupes_against_existing_tree(self):
        project = {"features": []}
        add_features_to_project([self._tree(_LAT, _LNG)], project)
        self.assertEqual(len(project["features"]), 1)
        # Second detection 1.5 m away, inside the crown → same tree, skipped.
        near_lng = _LNG + 1.5 / (111320.0 * math.cos(math.radians(_LAT)))
        out = tree_detect.import_detected_trees(
            self._res([self._tree(_LAT, near_lng)]), project)
        self.assertEqual(out["added"], 0)
        self.assertEqual(len(project["features"]), 1)


try:
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtGui import QImage
    from PyQt6.QtCore import QBuffer, QIODevice
    _HAVE_QT = True
except ImportError:  # pragma: no cover — CI without Qt
    _HAVE_QT = False


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed")
class TestQImageDecoder(unittest.TestCase):
    """The production tile decoder (tree_detect_flow._qimage_decode) — the
    only piece of the pipeline the synthetic-scene tests can't reach."""

    def _png_bytes(self, img):
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        return bytes(buf.data())

    def _pattern_image(self, w, h):
        img = QImage(w, h, QImage.Format.Format_RGB888)
        for y in range(h):
            for x in range(w):
                img.setPixel(x, y, (x * 7 % 256) << 16 | (y * 3 % 256) << 8
                             | ((x + y) % 256))
        return img

    def test_roundtrip_and_scanline_repack(self):
        from src.tree_detect_flow import _qimage_decode
        # 250 px wide → bytesPerLine padding → exercises the repack branch.
        for w, h in ((64, 64), (250, 40)):
            img = self._pattern_image(w, h)
            decoded = _qimage_decode(self._png_bytes(img))
            self.assertIsNotNone(decoded)
            dw, dh, rgb = decoded
            self.assertEqual((dw, dh), (w, h))
            self.assertEqual(len(rgb), w * h * 3)
            for (x, y) in ((0, 0), (w - 1, h - 1), (w // 2, h // 3)):
                i = (y * w + x) * 3
                self.assertEqual((rgb[i], rgb[i + 1], rgb[i + 2]),
                                 (x * 7 % 256, y * 3 % 256, (x + y) % 256))

    def test_garbage_bytes_decode_to_none(self):
        from src.tree_detect_flow import _qimage_decode
        self.assertIsNone(_qimage_decode(b"not an image"))


class TestFoliageAtPoints(unittest.TestCase):
    """classify_foliage_at_points tags CHM-detected trees (height, no colour)
    with conifer/broadleaf from the satellite photo at each point — the
    height ⊗ colour cross (V2.26)."""

    def test_tags_conifer_and_broadleaf(self):
        cx, cy = _center_px()
        scene = _disk_scene([(cx - 45, cy, 14, crown_texture),
                             (cx + 45, cy, 14, deciduous_texture)])
        bbox = _bbox_around(_LAT, _LNG, 30.0)
        le, ne = tree_detect._global_px_to_latlng(cx - 45 + 0.5, cy + 0.5, _Z)
        ld, nd = tree_detect._global_px_to_latlng(cx + 45 + 0.5, cy + 0.5, _Z)
        trees = [{"lat": le, "lng": ne, "radius_m": 2.5, "foliage": None},
                 {"lat": ld, "lng": nd, "radius_m": 2.5, "foliage": None}]
        tree_detect.classify_foliage_at_points(
            trees, bbox, _fetch_tile=_fetch_key, _decode=_scene_decoder(scene))
        self.assertEqual(trees[0]["foliage"], "evergreen")
        self.assertEqual(trees[1]["foliage"], "deciduous")

    def test_leaf_off_bare_crown_is_deciduous(self):
        # The user's spring/fall imagery: a bare deciduous crown is grey/brown
        # (not green). Because the height map already confirmed a tall tree
        # here, a non-green crown reads decisively as deciduous — the signal
        # that made RGB *detection* hard is the *classification* win.
        def bare(gx, gy):
            j = ((gx * 13 + gy * 7) % 21) - 10
            return (120 + j, 112 + j, 96 + j)   # grey-brown, ExG≈8
        cx, cy = _center_px()
        scene = _disk_scene([(cx, cy, 14, bare)])
        le, ne = tree_detect._global_px_to_latlng(cx + 0.5, cy + 0.5, _Z)
        trees = [{"lat": le, "lng": ne, "radius_m": 2.5, "foliage": None}]
        tree_detect.classify_foliage_at_points(
            trees, _bbox_around(_LAT, _LNG, 30.0),
            _fetch_tile=_fetch_key, _decode=_scene_decoder(scene))
        self.assertEqual(trees[0]["foliage"], "deciduous")

    def test_no_decoder_leaves_foliage_unchanged(self):
        trees = [{"lat": _LAT, "lng": _LNG, "radius_m": 2.0, "foliage": None}]
        tree_detect.classify_foliage_at_points(
            trees, _bbox_around(_LAT, _LNG, 30.0), _decode=None)
        self.assertIsNone(trees[0]["foliage"])

    def test_fetch_failure_leaves_foliage_unchanged(self):
        trees = [{"lat": _LAT, "lng": _LNG, "radius_m": 2.0, "foliage": None}]
        tree_detect.classify_foliage_at_points(
            trees, _bbox_around(_LAT, _LNG, 30.0),
            _fetch_tile=lambda z, x, y: None,
            _decode=_scene_decoder(_disk_scene([])))
        self.assertIsNone(trees[0]["foliage"])


class TestAddFeaturesOverrides(unittest.TestCase):
    def test_detected_item_overrides_and_foliage(self):
        project = {"features": []}
        n = add_features_to_project(
            [{"kind": "tree", "lat": _LAT, "lng": _LNG, "radius_m": 3.0,
              "height_m": 8.0, "label": "Tree (detected)",
              "source": "imagery", "foliage": "evergreen"}], project)
        self.assertEqual(n, 1)
        props = project["features"][0]["properties"]
        self.assertEqual(props["label"], "Tree (detected)")
        self.assertEqual(props["source"], "imagery")
        self.assertEqual(props["tree_foliage"], "evergreen")
        self.assertEqual(props["element_type"], "existing_tree")

    def test_osm_item_keeps_legacy_defaults(self):
        project = {"features": []}
        add_features_to_project(
            [{"kind": "tree", "lat": _LAT, "lng": _LNG,
              "radius_m": 3.0, "height_m": 7.0}], project)
        props = project["features"][0]["properties"]
        self.assertEqual(props["label"], "Tree (OSM)")
        self.assertEqual(props["source"], "osm")
        self.assertNotIn("tree_foliage", props)


if __name__ == "__main__":
    unittest.main()
