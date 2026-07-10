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


def crown_texture(gx, gy):
    """A real crown at yard scale: dark green with strong pixel-to-pixel
    brightness swings (sunlit tufts + self-shadow). Equal-channel jitter
    keeps ExG and hue identical to CROWN while the texture gate sees ±18."""
    j = ((gx * 31 + gy * 17) % 37) - 18
    return (CROWN[0] + j, CROWN[1] + j, CROWN[2] + j)


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
