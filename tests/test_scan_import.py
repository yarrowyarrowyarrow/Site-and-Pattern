"""
tests/test_scan_import.py — phone-scan import → nDSM → footprints (V1.62).

Synthetic end-to-end: a generated "yard scan" (ground plane + a 3 m shed),
exported to PLY (ASCII and binary), georeferenced with two control-point
pairs under a deliberate rotation+scale error, rasterized, vectorized, and
landed in a project as a shade-casting canopy_footprint — which the 3D
scene contract then extrudes. Skips cleanly when numpy/shapely are absent
(same policy as the rest of the footprint pipeline).
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

try:
    import shapely  # noqa: F401
    _HAVE_SHAPELY = True
except ImportError:
    _HAVE_SHAPELY = False

_LAT0, _LNG0 = 53.5, -113.5


def _synthetic_yard(rng_seed=3):
    """A 20×20 m yard in 'true' local metres: dense ground at z≈0 and a
    4×3 m shed (3 m tall) centred at (5, 4). Returns (points, shed_center)."""
    rng = np.random.default_rng(rng_seed)
    gx = rng.uniform(-10, 10, 16000)
    gy = rng.uniform(-10, 10, 16000)
    gz = rng.normal(0.0, 0.02, 16000)
    sx = rng.uniform(3.0, 7.0, 4000)
    sy = rng.uniform(2.5, 5.5, 4000)
    sz = np.full(4000, 3.0) + rng.normal(0.0, 0.02, 4000)
    pts = np.column_stack([
        np.concatenate([gx, sx]),
        np.concatenate([gy, sy]),
        np.concatenate([gz, sz]),
    ])
    return pts, (5.0, 4.0)


def _distort(points, scale=0.97, theta=math.radians(30), tx=12.0, ty=-7.0):
    """Map 'true' coords into 'scan' coords (what the phone app exported)."""
    c, s = math.cos(theta), math.sin(theta)
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    return np.column_stack([
        scale * (c * x - s * y) + tx,
        scale * (s * x + c * y) + ty,
        z * scale,
    ])


def _true_to_latlng(x, y):
    from src.projection import Projector
    return Projector(_LAT0, _LNG0).to_latlng(x, y)


@unittest.skipUnless(_HAVE_NUMPY, "numpy not installed")
class TestReaders(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="permadesign_scan_test_")

    def _path(self, name):
        return os.path.join(self._tmp, name)

    def test_ascii_ply_round_trip(self):
        from src.scan_import import read_points
        p = self._path("a.ply")
        with open(p, "w") as f:
            f.write("ply\nformat ascii 1.0\nelement vertex 2\n"
                    "property float x\nproperty float y\nproperty float z\n"
                    "end_header\n1.0 2.0 3.0\n-4.5 0.0 9.25\n")
        pts = read_points(p)
        self.assertEqual(pts.shape, (2, 3))
        self.assertAlmostEqual(pts[1][2], 9.25)

    def test_binary_ply_with_extra_properties(self):
        # Typical phone export: double xyz + uchar rgb — stride must skip
        # the colour bytes.
        from src.scan_import import read_points
        p = self._path("b.ply")
        header = ("ply\nformat binary_little_endian 1.0\n"
                  "element vertex 2\n"
                  "property double x\nproperty double y\nproperty double z\n"
                  "property uchar red\nproperty uchar green\n"
                  "property uchar blue\nend_header\n")
        with open(p, "wb") as f:
            f.write(header.encode("ascii"))
            for (x, y, z) in [(1.5, -2.0, 0.25), (100.0, 50.0, 3.0)]:
                f.write(struct.pack("<dddBBB", x, y, z, 10, 20, 30))
        pts = read_points(p)
        self.assertEqual(pts.shape, (2, 3))
        self.assertAlmostEqual(pts[0][0], 1.5)
        self.assertAlmostEqual(pts[1][2], 3.0)

    def test_xyz_text_with_comments_and_commas(self):
        from src.scan_import import read_points
        p = self._path("c.xyz")
        with open(p, "w") as f:
            f.write("# scan export\n1 2 3\n4,5,6\n\n")
        pts = read_points(p)
        self.assertEqual(pts.shape, (2, 3))

    def test_y_up_swap(self):
        from src.scan_import import read_points
        p = self._path("d.xyz")
        with open(p, "w") as f:
            f.write("1 5 2\n")     # x=1, y_up=5, z_fwd=2
        pts = read_points(p, up="y")
        # z-up frame: (x, -z_fwd, y_up)
        self.assertEqual(list(pts[0]), [1.0, -2.0, 5.0])

    def test_unknown_extension_rejected(self):
        from src.scan_import import read_points
        with self.assertRaises(ValueError):
            read_points(self._path("scan.glb"))


@unittest.skipUnless(_HAVE_NUMPY, "numpy not installed")
class TestAlignment(unittest.TestCase):

    def test_similarity_recovers_known_transform(self):
        from src.scan_import import (apply_similarity_2d,
                                     similarity_transform_2d)
        true_pts = np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 1.0],
                             [0.0, 8.0, 2.0]])
        scan = _distort(true_pts)
        tr = similarity_transform_2d(scan[:, :2].tolist(),
                                     true_pts[:, :2].tolist())
        back = apply_similarity_2d(scan, tr)
        self.assertTrue(np.allclose(back[:, :2], true_pts[:, :2], atol=1e-6))
        # z was shrunk by the scan's 0.97 scale error; alignment restores it.
        self.assertAlmostEqual(back[1][2], 1.0, places=6)

    def test_two_pairs_suffice(self):
        from src.scan_import import (apply_similarity_2d,
                                     similarity_transform_2d)
        true_pts = np.array([[0.0, 0.0, 0.0], [10.0, 5.0, 0.0]])
        scan = _distort(true_pts)
        tr = similarity_transform_2d(scan[:, :2].tolist(),
                                     true_pts[:, :2].tolist())
        back = apply_similarity_2d(scan, tr)
        self.assertTrue(np.allclose(back[:, :2], true_pts[:, :2], atol=1e-6))

    def test_coincident_controls_rejected(self):
        from src.scan_import import similarity_transform_2d
        with self.assertRaises(ValueError):
            similarity_transform_2d([[1, 1], [1, 1]], [[0, 0], [5, 5]])


@unittest.skipUnless(_HAVE_NUMPY, "numpy not installed")
class TestRasterize(unittest.TestCase):

    def test_box_heights_and_orientation(self):
        from src.scan_import import rasterize_ndsm
        pts, _center = _synthetic_yard()
        ndsm, extent = rasterize_ndsm(pts, cell_m=0.5)
        finite = ndsm[np.isfinite(ndsm)]
        self.assertAlmostEqual(float(np.nanmax(ndsm)), 3.0, delta=0.2)
        # Most of the yard is ground.
        self.assertGreater(float((finite < 0.5).mean()), 0.7)
        # Row 0 = north: a lone point at max y must land in row 0.
        lone = np.array([[0.0, 0.0, 0.0], [0.0, 20.0, 5.0],
                         [0.0, -20.0, 0.0]] * 5)
        grid, _ = rasterize_ndsm(lone, cell_m=1.0)
        self.assertAlmostEqual(float(grid[0, 0]), 5.0, delta=0.1)

    def test_fliers_clipped(self):
        from src.scan_import import rasterize_ndsm
        pts, _ = _synthetic_yard()
        pts = np.vstack([pts, [[0.0, 0.0, 900.0]]])    # a bird / sensor flier
        ndsm, _ = rasterize_ndsm(pts, cell_m=0.5)
        self.assertLessEqual(float(np.nanmax(ndsm)), 40.0)


@unittest.skipUnless(_HAVE_NUMPY and _HAVE_SHAPELY,
                     "numpy/shapely not installed")
class TestEndToEnd(unittest.TestCase):

    def test_scan_to_footprints_finds_the_shed(self):
        from src.scan_import import align_scan, scan_to_footprints
        true_pts, shed_center = _synthetic_yard()
        scan = _distort(true_pts)

        # Two control pairs: yard corners, in scan coords + map lat/lng.
        ctrl_true = [(-10.0, -10.0), (10.0, 10.0)]
        ctrl_scan = _distort(np.array([[x, y, 0.0]
                                       for (x, y) in ctrl_true]))[:, :2]
        ctrl_latlng = [_true_to_latlng(x, y) for (x, y) in ctrl_true]

        aligned, proj = align_scan(scan, ctrl_scan.tolist(), ctrl_latlng)
        rings = scan_to_footprints(aligned, proj, 0.25)
        self.assertEqual(len(rings), 1)
        ring, height = rings[0]
        self.assertAlmostEqual(height, 3.0, delta=0.3)
        # Ring centroid lands at the shed's true map position.
        clng = sum(p[0] for p in ring) / len(ring)
        clat = sum(p[1] for p in ring) / len(ring)
        want_lat, want_lng = _true_to_latlng(*shed_center)
        self.assertAlmostEqual(clat, want_lat, delta=2e-5)   # ~2 m
        self.assertAlmostEqual(clng, want_lng, delta=3e-5)

    def test_import_scan_feeds_project_and_3d_scene(self):
        from src.scan_import import import_scan
        true_pts, _ = _synthetic_yard()
        scan = _distort(true_pts)
        tmp = tempfile.mkdtemp(prefix="permadesign_scan_e2e_")
        ply = os.path.join(tmp, "yard.ply")
        with open(ply, "w") as f:
            f.write("ply\nformat ascii 1.0\n"
                    f"element vertex {len(scan)}\n"
                    "property float x\nproperty float y\nproperty float z\n"
                    "end_header\n")
            for x, y, z in scan:
                f.write(f"{x:.4f} {y:.4f} {z:.4f}\n")

        ctrl_true = [(-10.0, -10.0), (10.0, 10.0)]
        ctrl_scan = _distort(np.array([[x, y, 0.0]
                                       for (x, y) in ctrl_true]))[:, :2]
        ctrl_latlng = [_true_to_latlng(x, y) for (x, y) in ctrl_true]

        project = {"type": "FeatureCollection", "properties": {},
                   "features": []}
        added = import_scan(ply, project, ctrl_scan.tolist(), ctrl_latlng)
        self.assertEqual(len(added), 1)
        props = added[0]["properties"]
        self.assertEqual(props["element_type"], "canopy_footprint")
        self.assertTrue(props["cast_shade"])
        self.assertEqual(props["source"], "scan")
        self.assertAlmostEqual(props["height_m"], 3.0, delta=0.3)

        # And the 3D scene contract extrudes it with no further wiring.
        from src.scene_contract import build_scene
        scene = build_scene(project, get_plant=lambda pid: None)
        self.assertEqual(len(scene["buildings"]), 1)
        self.assertEqual(scene["buildings"][0]["kind"], "canopy")
        self.assertAlmostEqual(scene["buildings"][0]["height_m"], 3.0,
                               delta=0.3)


if __name__ == "__main__":
    unittest.main()
