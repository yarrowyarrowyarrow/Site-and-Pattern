"""
tests/test_old_scan_designs.py — a design saved with a yard scan still opens
(V3.22, RM-2).

File › Import Yard Scan and the Gaussian-splat backdrop were deleted in V3.22
(docs/plans/V3.22-what-goes.md). A design saved while they existed can hold a
``splat_backdrop`` feature (the scan file's path, its placement and a baked
top-down picture) and the ``canopy_footprint`` features a point-cloud scan
became. Nothing reads the first any more, so it must be carried untouched: an
old design opens, draws, builds its 3D scene and saves back with the feature
as it was, in case the owner ever wants it again.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import project as project_io  # noqa: E402
from src.scene_contract import build_scene  # noqa: E402

_RING = [[-113.5002, 53.5], [-113.4998, 53.5], [-113.4998, 53.5003],
         [-113.5002, 53.5003], [-113.5002, 53.5]]

SPLAT = {
    "type": "Feature",
    "geometry": {"type": "Polygon", "coordinates": [_RING]},
    "properties": {
        "element_type": "splat_backdrop",
        "name": "Yard scan",
        "file_path": "/home/someone/scans/yard.ply",
        "origin": {"lat": 53.5, "lng": -113.5},
        "transform": {"scale": 1.0, "theta_rad": 0.1, "tx": 0.5, "ty": -0.2},
        "up_axis": "z",
        "bbox": {"south": 53.5, "north": 53.5003,
                 "west": -113.5002, "east": -113.4998},
        "ortho_opacity": 0.85,
        "ortho_png": "data:image/png;base64,iVBORw0KGgo=",
    },
}

FOOTPRINT = {
    "type": "Feature",
    "geometry": {"type": "Polygon", "coordinates": [_RING]},
    "properties": {"element_type": "canopy_footprint", "height_m": 4.0,
                   "kind": "building", "source": "scan"},
}


class AnOldScanDesignOpens(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        proj = project_io.new_project("Scanned yard")
        proj["features"] += [SPLAT, FOOTPRINT]
        self.path = os.path.join(self.dir, "old.perma.geojson")
        project_io.save_project(proj, self.path)

    def test_it_opens_draws_and_builds_its_scene(self):
        proj = project_io.load_project(self.path)
        project_io.project_to_map_data(proj)
        scene = build_scene(proj, get_plant=lambda pid: None)
        self.assertNotIn("splat", scene)
        self.assertNotIn("scan_points", scene)

    def test_it_saves_back_with_the_scan_untouched(self):
        proj = project_io.load_project(self.path)
        again = os.path.join(self.dir, "again.perma.geojson")
        project_io.save_project(proj, again)
        with open(again, encoding="utf-8") as f:
            features = json.load(f)["features"]
        kept = [f for f in features
                if f["properties"].get("element_type") == "splat_backdrop"]
        self.assertEqual(kept, [SPLAT])
        self.assertIn(FOOTPRINT, features)


if __name__ == "__main__":
    unittest.main()
