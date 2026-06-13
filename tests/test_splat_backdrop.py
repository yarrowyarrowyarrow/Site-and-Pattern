"""
tests/test_splat_backdrop.py — the Qt-free core of the Gaussian-splat
backdrop (V1.65): splat-PLY detection, the fast binary reader, the
file→three.js world matrix, the lat/lng footprint, and the
``splat_backdrop`` feature round-trip through a saved project.

Headless: numpy + stdlib only, temp files via tempfile (never the real
user DB / project dir), matching the existing scan-import tests.
"""

import math
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import numpy as np
    _HAVE_NUMPY = True
except ImportError:
    _HAVE_NUMPY = False

from src import splat_backdrop as sb


def _write_ply(path, props, verts):
    """Write a binary_little_endian PLY. ``props`` is a list of property
    names (all float32 here); ``verts`` a list of equal-length float tuples."""
    header = ("ply\n"
              "format binary_little_endian 1.0\n"
              f"element vertex {len(verts)}\n"
              + "".join(f"property float {n}\n" for n in props)
              + "end_header\n")
    with open(path, "wb") as f:
        f.write(header.encode("ascii"))
        for v in verts:
            f.write(struct.pack("<" + "f" * len(props), *v))


# Splat-PLY vertex layout: position + the attributes that mark a 3DGS file.
_SPLAT_PROPS = ["x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2",
                "opacity", "scale_0", "scale_1", "scale_2",
                "rot_0", "rot_1", "rot_2", "rot_3"]


@unittest.skipUnless(_HAVE_NUMPY, "needs numpy")
class TestSplatPlyDetection(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def _path(self, name):
        return os.path.join(self.dir, name)

    def test_detects_splat_ply(self):
        p = self._path("yard.ply")
        _write_ply(p, _SPLAT_PROPS,
                   [tuple(float(i) for i in range(len(_SPLAT_PROPS)))])
        self.assertTrue(sb_is_splat(p))

    def test_plain_xyz_ply_is_not_splat(self):
        p = self._path("cloud.ply")
        _write_ply(p, ["x", "y", "z"], [(1.0, 2.0, 3.0)])
        self.assertFalse(sb_is_splat(p))

    def test_non_ply_is_not_splat(self):
        p = self._path("notes.txt")
        with open(p, "w") as f:
            f.write("hello")
        self.assertFalse(sb_is_splat(p))

    def test_missing_file_is_not_splat(self):
        self.assertFalse(sb_is_splat(self._path("nope.ply")))


@unittest.skipUnless(_HAVE_NUMPY, "needs numpy")
class TestFastPlyReader(unittest.TestCase):
    """The numpy structured-array path must return the same x/y/z as the
    bytes written, despite the 14 extra per-vertex splat properties."""

    def test_reads_xyz_through_extra_properties(self):
        from src.scan_import import read_points
        d = tempfile.mkdtemp()
        p = os.path.join(d, "yard.ply")
        verts = []
        for i in range(50):
            row = [float(i), float(i) * 2, float(i) * 3]      # x, y, z
            row += [0.0] * (len(_SPLAT_PROPS) - 3)            # filler attrs
            verts.append(tuple(row))
        _write_ply(p, _SPLAT_PROPS, verts)
        pts = read_points(p)            # up='z' default
        self.assertEqual(pts.shape, (50, 3))
        self.assertTrue(np.allclose(pts[:, 0], np.arange(50)))
        self.assertTrue(np.allclose(pts[:, 1], np.arange(50) * 2))
        self.assertTrue(np.allclose(pts[:, 2], np.arange(50) * 3))


def sb_is_splat(path):
    from src.scan_import import is_gaussian_splat_ply
    return is_gaussian_splat_ply(path)


def _apply_cm(mat_cm, p):
    """Apply a column-major flat 4×4 (three.js order) to a 3-point."""
    x, y, z = p
    out = []
    for row in range(3):
        out.append(mat_cm[0 * 4 + row] * x + mat_cm[1 * 4 + row] * y
                   + mat_cm[2 * 4 + row] * z + mat_cm[3 * 4 + row])
    return out


class TestWorldMatrix(unittest.TestCase):
    """file → three.js (x_east→+x, y_north→−z, up→+y)."""

    def test_identity_z_up_axis_remap(self):
        m = sb.world_matrix((1.0, 0.0, 0.0, 0.0), up="z")
        # (x, y, z) → (x, z, -y)
        self.assertAlmostEqual2(_apply_cm(m, (1, 2, 3)), (1, 3, -2))

    def test_scale_and_translation(self):
        # F_proj: (2x+10, 2y+20, 2z) → three (x', z', -y')
        m = sb.world_matrix((2.0, 0.0, 10.0, 20.0), up="z")
        self.assertAlmostEqual2(_apply_cm(m, (1, 2, 3)), (12, 6, -24))

    def test_quarter_turn(self):
        # theta=90°: x'=-y, y'=x → three (-y, z, -x)
        m = sb.world_matrix((1.0, math.pi / 2, 0.0, 0.0), up="z")
        self.assertAlmostEqual2(_apply_cm(m, (1, 2, 3)), (-2, 3, -1))

    def test_y_up_passthrough_differs_from_z_up(self):
        # A y-up file is already three.js' convention: identity sim → identity.
        m_y = sb.world_matrix((1.0, 0.0, 0.0, 0.0), up="y")
        self.assertAlmostEqual2(_apply_cm(m_y, (1, 2, 3)), (1, 2, 3))
        # z-up disagrees, proving the up swap is actually applied.
        m_z = sb.world_matrix((1.0, 0.0, 0.0, 0.0), up="z")
        self.assertAlmostEqual2(_apply_cm(m_z, (1, 2, 3)), (1, 3, -2))

    def test_origin_offset_shifts_xy(self):
        m = sb.world_matrix((1.0, 0.0, 0.0, 0.0), up="z",
                            origin_offset=(5.0, 7.0))
        # F_scene: (x+5, y+7, z) → three (x+5, z, -(y+7))
        self.assertAlmostEqual2(_apply_cm(m, (1, 2, 3)), (6, 3, -9))

    def assertAlmostEqual2(self, got, want):
        for g, w in zip(got, want):
            self.assertAlmostEqual(g, w, places=6)


@unittest.skipUnless(_HAVE_NUMPY, "needs numpy")
class TestLatLngBbox(unittest.TestCase):

    def test_bbox_orders_and_contains(self):
        from src.projection import Projector
        proj = Projector(53.5, -113.5)
        # A 10 m × 20 m patch in projector metres around the origin.
        pts = np.array([[-5.0, -10.0, 0.0], [5.0, 10.0, 1.0],
                        [0.0, 0.0, 0.5]])
        bbox = sb.latlng_bbox(pts, proj)
        self.assertLess(bbox["south"], bbox["north"])
        self.assertLess(bbox["west"], bbox["east"])
        # Origin lat/lng sit inside the box.
        self.assertLessEqual(bbox["south"], 53.5)
        self.assertGreaterEqual(bbox["north"], 53.5)


class TestFeatureRoundTrip(unittest.TestCase):

    def _feature(self, **over):
        kw = dict(file_path="/tmp/yard.ply",
                  origin={"lat": 53.5, "lng": -113.5},
                  transform=(2.0, 0.5, 10.0, 20.0), up="z",
                  bbox={"south": 53.4, "north": 53.6,
                        "west": -113.6, "east": -113.4},
                  ortho_png="data:image/png;base64,AAAA", opacity=0.8)
        kw.update(over)
        return sb.build_feature(**kw)

    def test_feature_shape(self):
        f = self._feature()
        self.assertEqual(f["type"], "Feature")
        self.assertEqual(f["geometry"]["type"], "Polygon")
        # Closed footprint ring.
        ring = f["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])
        self.assertEqual(f["properties"]["element_type"], sb.ELEMENT_TYPE)

    def test_round_trip_through_saved_project(self):
        from src.project import save_project, load_project
        proj = {"type": "FeatureCollection",
                "features": [self._feature()], "properties": {}}
        d = tempfile.mkdtemp()
        path = os.path.join(d, "garden.perma.geojson")
        save_project(proj, path)
        loaded = load_project(path)
        feat = sb.feature_from_project(loaded)
        self.assertIsNotNone(feat)
        self.assertEqual(sb.transform_tuple(feat), (2.0, 0.5, 10.0, 20.0))
        payload = sb.ortho_overlay_payload(feat)
        self.assertEqual(payload["image"], "data:image/png;base64,AAAA")
        self.assertAlmostEqual(payload["opacity"], 0.8)
        self.assertEqual(payload["bbox"]["north"], 53.6)

    def test_no_ortho_png_yields_no_payload(self):
        f = self._feature(ortho_png=None)
        self.assertIsNone(sb.ortho_overlay_payload(f))

    def test_scene_field_matrix_matches_world_matrix(self):
        f = self._feature()
        # Same origin as the feature → zero offset → equals world_matrix().
        field = sb.scene_field(f, 53.5, -113.5)
        self.assertEqual(field["path"], "/tmp/yard.ply")
        self.assertAlmostEqual(field["opacity"], 0.8)
        expected = sb.world_matrix((2.0, 0.5, 10.0, 20.0), up="z",
                                   origin_offset=(0.0, 0.0))
        for a, b in zip(field["matrix"], expected):
            self.assertAlmostEqual(a, b, places=6)

    def test_latest_splat_feature_wins(self):
        proj = {"features": [self._feature(file_path="/tmp/a.ply"),
                             self._feature(file_path="/tmp/b.ply")]}
        self.assertEqual(
            sb.feature_from_project(proj)["properties"]["file_path"],
            "/tmp/b.ply")


class TestBuildSceneSplatField(unittest.TestCase):
    """build_scene auto-detects the splat feature and exposes scene['splat']."""

    def _project(self, with_splat):
        feats = []
        if with_splat:
            feats.append(sb.build_feature(
                file_path="/tmp/yard.ply",
                origin={"lat": 0.0, "lng": 0.0},
                transform=(1.0, 0.0, 0.0, 0.0), up="z",
                bbox={"south": -0.001, "north": 0.001,
                      "west": -0.001, "east": 0.001},
                opacity=0.9))
        return {"type": "FeatureCollection", "features": feats,
                "properties": {}}

    def test_splat_field_present(self):
        from src.scene_contract import build_scene
        scene = build_scene(self._project(True), get_plant=lambda _i: {})
        self.assertIsNotNone(scene["splat"])
        self.assertEqual(scene["splat"]["path"], "/tmp/yard.ply")
        self.assertEqual(len(scene["splat"]["matrix"]), 16)
        self.assertAlmostEqual(scene["splat"]["opacity"], 0.9)

    def test_splat_field_absent_without_feature(self):
        from src.scene_contract import build_scene
        scene = build_scene(self._project(False), get_plant=lambda _i: {})
        self.assertIsNone(scene["splat"])


if __name__ == "__main__":
    unittest.main()
