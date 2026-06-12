"""
tests/test_mcp_server.py

Tests the MCP server's TOOL LOGIC (the plain tool_* functions) without
needing the `mcp` SDK installed. The SDK plumbing (build_server) is
guarded and verified to fail with a clear message when the SDK is
absent. Runs headless (no PyQt6).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Sandbox + pin the DB (same pattern as the other facade tests).
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_mcp_test_")
_DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
import src.db.plants as _plants_mod  # noqa: E402
import src.permadesign_api as _api  # noqa: E402


def _use_our_db() -> None:
    from src.db.plants import init_db
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = _DB_PATH
    init_db()
    _api._DB_READY = True


import src.mcp_server as mcp_server  # noqa: E402
from src.errors import ProjectError, PlantNotFoundError  # noqa: E402


class TestMcpToolLogic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _use_our_db()

    def _project_path(self, name: str) -> str:
        return os.path.join(_TMP_DIR, name)

    def test_query_plants_tool(self):
        rows = mcp_server.tool_query_plants("yarrow", limit=5)
        self.assertIsInstance(rows, list)
        self.assertLessEqual(len(rows), 5)

    def test_query_plants_native_filter(self):
        rows = mcp_server.tool_query_plants(native_only=True, limit=10)
        self.assertTrue(all(p.get("native_to_alberta") for p in rows))

    def test_list_communities_and_structures(self):
        self.assertIsInstance(mcp_server.tool_list_communities(), list)
        structs = mcp_server.tool_list_structures()
        self.assertTrue(any(s.get("id") for s in structs))

    def test_create_then_place_then_analyze_flow(self):
        path = self._project_path("mcp_flow.perma.geojson")
        # create
        summary = mcp_server.tool_create_project(
            path, "MCP Flow",
            boundary=[[53.55, -113.50], [53.55, -113.49],
                      [53.54, -113.49], [53.54, -113.50]],
        )
        self.assertEqual(summary["name"], "MCP Flow")
        self.assertEqual(summary["n_plants"], 0)
        self.assertTrue(os.path.exists(path))

        # place a plant (file-based: load → mutate → save)
        plant = mcp_server.tool_query_plants(native_only=True, limit=1)[0]
        s2 = mcp_server.tool_place_plant(path, plant["id"], 53.545, -113.495)
        self.assertEqual(s2["n_plants"], 1)

        # the change persisted to disk
        s3 = mcp_server.tool_project_summary(path)
        self.assertEqual(s3["n_plants"], 1)

        # place a structure
        s4 = mcp_server.tool_place_structure(path, "pond", 53.546, -113.496)
        self.assertEqual(s4["n_structures"], 1)

        # analyze
        result = mcp_server.tool_analyze_project(path)
        self.assertIn("habitat_score", result)
        self.assertIsNotNone(result["habitat_score"])

    def test_place_community_tool(self):
        comms = mcp_server.tool_list_communities()
        if not comms:
            self.skipTest("no seeded communities")
        path = self._project_path("mcp_comm.perma.geojson")
        mcp_server.tool_create_project(path, "Comm")
        summary = mcp_server.tool_place_community(
            path, comms[0]["id"], 53.545, -113.495
        )
        self.assertGreaterEqual(summary["n_plants"], 1)

    def test_place_plant_bad_id_raises(self):
        path = self._project_path("mcp_bad.perma.geojson")
        mcp_server.tool_create_project(path, "Bad")
        with self.assertRaises(PlantNotFoundError):
            mcp_server.tool_place_plant(path, 10_000_000, 53.5, -113.5)

    def test_analyze_missing_file_raises(self):
        with self.assertRaises(ProjectError):
            mcp_server.tool_analyze_project("/no/such/file.perma.geojson")

    def test_tool_specs_cover_all_tool_functions(self):
        # Every tool_* function should be registered in TOOL_SPECS.
        registered = {spec["func"] for spec in mcp_server.TOOL_SPECS}
        tool_funcs = {
            getattr(mcp_server, n) for n in dir(mcp_server)
            if n.startswith("tool_") and callable(getattr(mcp_server, n))
        }
        self.assertEqual(registered, tool_funcs)

    def test_tool_specs_names_unique(self):
        names = [s["name"] for s in mcp_server.TOOL_SPECS]
        self.assertEqual(len(names), len(set(names)))

    def test_build_server_without_sdk_raises_clear_error(self):
        # The `mcp` SDK isn't installed in this env; build_server must
        # raise RuntimeError with an install hint (not ImportError).
        try:
            import mcp.server.fastmcp  # noqa: F401
            self.skipTest("mcp SDK is installed in this env")
        except ImportError:
            pass
        with self.assertRaises(RuntimeError) as ctx:
            mcp_server.build_server()
        self.assertIn("pip install", str(ctx.exception))

    def test_module_imports_no_qt(self):
        import ast
        tree = ast.parse(Path(mcp_server.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertFalse(alias.name.startswith("PyQt6"))
            elif isinstance(node, ast.ImportFrom):
                self.assertFalse((node.module or "").startswith("PyQt6"))


if __name__ == "__main__":
    unittest.main()
