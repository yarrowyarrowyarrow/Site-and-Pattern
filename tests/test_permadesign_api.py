"""
tests/test_permadesign_api.py

Tests for the Qt-free public scripting facade (src/permadesign_api.py) —
the surface AI agents / CLI / MCP server drive. These run under bare
python (no PyQt6), proving the dual-user goal: the whole place →
analyze → save flow works without a QApplication.

Uses the temp-DB seed pattern so the real seeded catalogue backs the
queries and scoring.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp dir BEFORE importing the API (which inits it).
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_api_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.permadesign_api import (  # noqa: E402
    Project,
    query_plants,
    list_polycultures,
    list_structures,
    run_analysis,
)
from src.errors import (  # noqa: E402
    PermaDesignError,
    ProjectError,
    PlantNotFoundError,
    PolycultureNotFoundError,
)


_EDM = (53.5461, -113.4938)
_BOUNDARY = [
    (53.55, -113.50), (53.55, -113.49),
    (53.54, -113.49), (53.54, -113.50),
]


class TestQueries(unittest.TestCase):

    def test_query_plants_returns_rows(self):
        plants = query_plants()
        self.assertGreater(len(plants), 0)
        self.assertIn("id", plants[0])
        self.assertIn("common_name", plants[0])

    def test_query_plants_filter(self):
        native = query_plants(native_only=True)
        all_plants = query_plants()
        self.assertLessEqual(len(native), len(all_plants))
        # every returned plant is actually native
        self.assertTrue(all(p.get("native_to_alberta") for p in native))

    def test_list_polycultures(self):
        polys = list_polycultures()
        self.assertIsInstance(polys, list)
        if polys:
            self.assertIn("id", polys[0])

    def test_list_structures(self):
        structs = list_structures()
        self.assertGreater(len(structs), 0)
        self.assertIn("id", structs[0])


class TestProjectLifecycle(unittest.TestCase):

    def test_create_empty(self):
        p = Project.create("Test Yard")
        self.assertEqual(p.name, "Test Yard")
        self.assertEqual(p.placed_plants, [])
        self.assertEqual(p.structures, [])

    def test_create_with_boundary(self):
        p = Project.create("Bounded", boundary=_BOUNDARY)
        d = p.as_dict()
        kinds = [f["properties"].get("element_type") for f in d["features"]]
        self.assertIn("property_boundary", kinds)

    def test_place_plant(self):
        p = Project.create("Planted", boundary=_BOUNDARY)
        plant = query_plants()[0]
        p.place_plant(plant["id"], *_EDM)
        placed = p.placed_plants
        self.assertEqual(len(placed), 1)
        self.assertEqual(placed[0]["plant_id"], plant["id"])

    def test_place_plant_unknown_id_raises(self):
        p = Project.create("X")
        with self.assertRaises(PlantNotFoundError):
            p.place_plant(10_000_000, *_EDM)
        # and PlantNotFoundError is a PermaDesignError
        self.assertTrue(issubclass(PlantNotFoundError, PermaDesignError))

    def test_place_structure(self):
        p = Project.create("S")
        p.place_structure("pond", *_EDM)
        structs = p.structures
        self.assertEqual(len(structs), 1)
        self.assertEqual(structs[0].get("id"), "pond")

    def test_place_polyculture_unknown_raises(self):
        p = Project.create("X")
        with self.assertRaises(PolycultureNotFoundError):
            p.place_polyculture(10_000_000, *_EDM)

    def test_place_polyculture_real(self):
        polys = list_polycultures()
        if not polys:
            self.skipTest("no seeded polycultures")
        p = Project.create("Community")
        p.place_polyculture(polys[0]["id"], *_EDM)
        # A community expands into ≥1 plant feature.
        self.assertGreaterEqual(len(p.placed_plants), 1)

    def test_save_load_round_trip(self):
        tmp = Path(_TMP_DIR) / "round_trip.perma.geojson"
        p = Project.create("RoundTrip", boundary=_BOUNDARY)
        plant = query_plants()[0]
        p.place_plant(plant["id"], *_EDM)
        p.save(str(tmp))

        loaded = Project.load(str(tmp))
        self.assertEqual(loaded.name, "RoundTrip")
        self.assertEqual(len(loaded.placed_plants), 1)
        self.assertEqual(loaded.as_dict(), p.as_dict())

    def test_load_missing_file_raises_project_error(self):
        with self.assertRaises(ProjectError):
            Project.load("/no/such/path/x.perma.geojson")

    def test_load_garbage_raises_project_error(self):
        bad = Path(_TMP_DIR) / "bad.json"
        bad.write_text("{ not json", encoding="utf-8")
        with self.assertRaises(ProjectError):
            Project.load(str(bad))

    def test_load_non_project_json_raises(self):
        notproj = Path(_TMP_DIR) / "notproj.json"
        notproj.write_text('{"hello": "world"}', encoding="utf-8")
        with self.assertRaises(ProjectError):
            Project.load(str(notproj))


class TestAnalysis(unittest.TestCase):

    def test_run_analysis_shape(self):
        p = Project.create("Analyzed", boundary=_BOUNDARY)
        for plant in query_plants(native_only=True)[:5]:
            p.place_plant(plant["id"], _EDM[0], _EDM[1])
        result = run_analysis(p)
        self.assertIn("habitat_score", result)
        self.assertIn("warnings", result)
        hs = result["habitat_score"]
        self.assertIsNotNone(hs)
        self.assertGreaterEqual(hs["total"], 0)
        self.assertLessEqual(hs["total"], 100)
        self.assertIn("components", hs)

    def test_run_analysis_empty_project(self):
        p = Project.create("Empty")
        result = run_analysis(p)
        # Nothing placed → no score, but warnings list the gaps.
        self.assertIsNone(result["habitat_score"])
        self.assertTrue(result["warnings"])

    def test_analyze_method_matches_run_analysis(self):
        p = Project.create("M", boundary=_BOUNDARY)
        plant = query_plants()[0]
        p.place_plant(plant["id"], *_EDM)
        self.assertEqual(p.analyze(), run_analysis(p))

    def test_structures_count_in_score(self):
        p = Project.create("Struct")
        p.place_structure("pond", *_EDM)
        p.place_structure("bee_hotel", 53.55, -113.49)
        hs = run_analysis(p)["habitat_score"]
        self.assertIsNotNone(hs)
        self.assertEqual(hs["components"]["structures"]["score"], 4)  # 2 types * 2


class TestNoQtImport(unittest.TestCase):
    """The whole point of the facade: it must import and run without
    PyQt6 even being installed. We check the *import statements* (via
    AST), not the source text — the module docstring legitimately
    mentions "PyQt6" in prose explaining why it avoids it.

    The transitive closure matters too: importing permadesign_api must
    not pull PyQt6 into sys.modules. This test runs in a CI env without
    PyQt6, so a stray Qt import would already crash the module import
    above — but we assert it explicitly for clarity."""

    def test_module_import_statements_have_no_qt(self):
        import ast
        import src.permadesign_api as api
        tree = ast.parse(open(api.__file__).read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertFalse(
                        alias.name.startswith("PyQt6"),
                        f"unexpected `import {alias.name}`",
                    )
            elif isinstance(node, ast.ImportFrom):
                self.assertFalse(
                    (node.module or "").startswith("PyQt6"),
                    f"unexpected `from {node.module} import …`",
                )

    def test_import_does_not_pull_in_pyqt6(self):
        import sys
        # If PyQt6 is genuinely installed in this env, this assertion is
        # vacuous but harmless; in CI (no PyQt6) it proves the facade's
        # transitive imports are Qt-free.
        if "PyQt6" in sys.modules:
            self.skipTest("PyQt6 already imported by another test/module")
        import importlib
        importlib.import_module("src.permadesign_api")
        self.assertNotIn("PyQt6", sys.modules)


if __name__ == "__main__":
    unittest.main()
