"""
tests/test_agent_generation_loop.py

The MCP path's automated stand-in for a live agent handshake. An agent
designing a garden from a prompt drives the MCP tools in sequence:
discover species/communities, create a project, place things, then score
it. This test runs that exact tool sequence against the plain tool_*
functions (no LLM, no MCP SDK, no network), proving the tools compose into
a complete, analyzable design. Runs headless (no PyQt6).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Sandbox + pin the DB (same pattern as the other facade tests).
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_agentloop_test_")
_DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
import src.db.plants as _plants_mod  # noqa: E402
import src.permadesign_api as _api  # noqa: E402


def _use_our_db() -> None:
    from src.db.plants import init_db
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = _DB_PATH
    init_db()
    _api._DB_READY = True


import src.mcp_server as mcp  # noqa: E402

_EDM = (53.5461, -113.4938)


class TestAgentGenerationLoop(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _use_our_db()

    def test_prompt_to_scored_design_via_tools(self):
        """Walk the tool sequence an agent runs for 'design a pollinator
        garden at <lat,lng>'."""
        path = os.path.join(_TMP_DIR, "agent_loop.perma.geojson")

        # 1. Discover species the brief calls for.
        pollinators = mcp.tool_query_plants(pollinator_only=True, limit=5)
        self.assertTrue(pollinators, "expected some pollinator plants in seed data")

        # 2. Discover a community to anchor the planting.
        communities = mcp.tool_list_communities()
        self.assertTrue(communities)

        # 3. Discover a habitat structure.
        structures = mcp.tool_list_structures()
        self.assertTrue(structures)

        # 4. Create the project with a small boundary.
        lat, lng = _EDM
        boundary = [[lat + 0.001, lng - 0.001], [lat + 0.001, lng + 0.001],
                    [lat - 0.001, lng + 0.001], [lat - 0.001, lng - 0.001]]
        created = mcp.tool_create_project(path, name="Pollinator Garden",
                                          boundary=boundary)
        self.assertEqual(created["n_plants"], 0)

        # 5. Place the discovered species, a community, and a structure.
        for i, plant in enumerate(pollinators):
            mcp.tool_place_plant(path, plant["id"], lat + i * 1e-4, lng + i * 1e-4)
        mcp.tool_place_community(path, communities[0]["id"], lat, lng)
        mcp.tool_place_structure(path, structures[0]["id"], lat - 5e-4, lng - 5e-4)

        # 6. The project on disk reflects everything placed.
        summary = mcp.tool_project_summary(path)
        self.assertGreaterEqual(summary["n_plants"], len(pollinators))
        self.assertEqual(summary["n_structures"], 1)

        # 7. Score it — the composed design is analyzable end-to-end.
        analysis = mcp.tool_analyze_project(path)
        self.assertIn("habitat_score", analysis)
        self.assertIsNotNone(analysis["habitat_score"])
        self.assertGreater(analysis["habitat_score"]["total"], 0)

    def test_generate_design_tool_is_registered(self):
        names = {spec["name"] for spec in mcp.TOOL_SPECS}
        self.assertIn("generate_design", names)
        # Every registered tool maps to a callable.
        for spec in mcp.TOOL_SPECS:
            self.assertTrue(callable(spec["func"]))


if __name__ == "__main__":
    unittest.main()
