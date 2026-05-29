"""
tests/test_llm_design.py

Offline tests for prompt-driven generation (src.llm_design). A fake client
returns a canned design spec, so generation is exercised end-to-end WITHOUT
contacting any LLM. Also covers spec parsing/validation and the LLMClient
config precedence. Runs headless (no PyQt6, no network).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Sandbox + pin the DB (same pattern as the other facade tests).
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_llm_test_")
_DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
import src.db.plants as _plants_mod  # noqa: E402
import src.permadesign_api as _api  # noqa: E402


def _use_our_db() -> None:
    from src.db.plants import init_db
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = _DB_PATH
    init_db()
    _api._DB_READY = True


import src.llm_design as llm  # noqa: E402
from src.errors import LLMError  # noqa: E402

_EDM = {"latitude": 53.5461, "longitude": -113.4938}


class _FakeClient:
    """Stands in for LLMClient — returns a fixed spec, records the call."""

    def __init__(self, spec):
        self._spec = spec
        self.calls = []
        self.endpoint = "fake://local"
        self.model = "fake-model"

    def generate_spec(self, prompt, context):
        self.calls.append((prompt, context))
        return self._spec


class TestGenerateDesign(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _use_our_db()

    def test_plants_resolved_and_placed(self):
        spec = {
            "summary": "pollinator garden",
            "plants": [
                {"query": "yarrow", "quantity": 3},
                {"query": "willow", "quantity": 1},
            ],
        }
        client = _FakeClient(spec)
        project = llm.generate_design(
            "a pollinator garden", site_config=_EDM, client=client,
        )
        placed = project.placed_plants
        self.assertEqual(len(placed), 2)
        # The two placements resolve to the same ids a direct query would.
        expected_first = _api.query_plants(query="yarrow")[0]["id"]
        placed_ids = {p["plant_id"] for p in placed}
        self.assertIn(expected_first, placed_ids)
        # Every placement carries valid coordinates near the supplied site.
        for p in placed:
            self.assertAlmostEqual(p["lat"], _EDM["latitude"], delta=0.01)
            self.assertAlmostEqual(p["lng"], _EDM["longitude"], delta=0.01)

    def test_prompt_and_context_reach_client(self):
        client = _FakeClient({"plants": [{"query": "yarrow"}]})
        llm.generate_design("xeriscape please", site_config=_EDM, client=client)
        self.assertEqual(len(client.calls), 1)
        prompt, context = client.calls[0]
        self.assertEqual(prompt, "xeriscape please")
        self.assertIn("community_names", context)
        self.assertIn("structure_ids", context)

    def test_generated_design_is_analyzable(self):
        client = _FakeClient({"plants": [
            {"query": "yarrow", "quantity": 2},
            {"query": "rose", "quantity": 2},
        ]})
        project = llm.generate_design("habitat", site_config=_EDM, client=client)
        result = project.analyze()
        self.assertIn("habitat_score", result)
        self.assertIsNotNone(result["habitat_score"])

    def test_community_resolved_by_name(self):
        communities = _api.list_polycultures()
        self.assertTrue(communities, "seed data should include communities")
        name = communities[0]["name"]
        client = _FakeClient({"communities": [{"query": name}]})
        project = llm.generate_design("a community", site_config=_EDM, client=client)
        # A community expands into its members, so at least one plant lands.
        self.assertGreaterEqual(len(project.placed_plants), 1)

    def test_structure_resolved_and_placed(self):
        structures = _api.list_structures()
        sid = structures[0]["id"]
        client = _FakeClient({
            "plants": [{"query": "yarrow"}],
            "structures": [{"structure_id": sid}],
        })
        project = llm.generate_design("with a structure", site_config=_EDM, client=client)
        placed_ids = {s.get("id") for s in project.structures}
        self.assertIn(sid, placed_ids)

    def test_unknown_structure_is_skipped(self):
        client = _FakeClient({
            "plants": [{"query": "yarrow"}],
            "structures": [{"structure_id": "definitely_not_real"}],
        })
        project = llm.generate_design("x", site_config=_EDM, client=client)
        self.assertEqual(len(project.structures), 0)

    def test_boundary_supplies_center_without_site_config(self):
        boundary = [(53.55, -113.50), (53.55, -113.49),
                    (53.54, -113.49), (53.54, -113.50)]
        client = _FakeClient({"plants": [{"query": "yarrow"}]})
        project = llm.generate_design("x", boundary=boundary, client=client)
        self.assertEqual(len(project.placed_plants), 1)

    # ── Failure modes ────────────────────────────────────────────────────────

    def test_no_location_raises(self):
        client = _FakeClient({"plants": [{"query": "yarrow"}]})
        with self.assertRaises(LLMError):
            llm.generate_design("x", client=client)

    def test_empty_spec_raises(self):
        client = _FakeClient({"summary": "nothing here"})
        with self.assertRaises(LLMError):
            llm.generate_design("x", site_config=_EDM, client=client)

    def test_non_list_field_raises(self):
        client = _FakeClient({"plants": "not a list"})
        with self.assertRaises(LLMError):
            llm.generate_design("x", site_config=_EDM, client=client)

    def test_unresolvable_plants_raises(self):
        client = _FakeClient({"plants": [{"query": "zzzznotaplantzzzz"}]})
        with self.assertRaises(LLMError):
            llm.generate_design("x", site_config=_EDM, client=client)

    def test_empty_prompt_raises(self):
        client = _FakeClient({"plants": [{"query": "yarrow"}]})
        with self.assertRaises(LLMError):
            llm.generate_design("   ", site_config=_EDM, client=client)


class TestSpecParsing(unittest.TestCase):

    def test_plain_json(self):
        spec = llm._parse_spec_json('{"plants": []}')
        self.assertEqual(spec, {"plants": []})

    def test_fenced_json(self):
        spec = llm._parse_spec_json('```json\n{"plants": [1]}\n```')
        self.assertEqual(spec, {"plants": [1]})

    def test_json_embedded_in_prose(self):
        spec = llm._parse_spec_json('Sure! Here you go:\n{"a": 1}\nHope that helps.')
        self.assertEqual(spec, {"a": 1})

    def test_empty_content_raises(self):
        with self.assertRaises(LLMError):
            llm._parse_spec_json("")

    def test_no_json_raises(self):
        with self.assertRaises(LLMError):
            llm._parse_spec_json("no json here at all")


class TestLLMClientConfig(unittest.TestCase):

    def setUp(self):
        for var in ("PERMADESIGN_LLM_ENDPOINT", "PERMADESIGN_LLM_MODEL"):
            os.environ.pop(var, None)

    def test_defaults(self):
        c = llm.LLMClient()
        self.assertEqual(c.endpoint, llm.DEFAULT_ENDPOINT)
        self.assertEqual(c.model, llm.DEFAULT_MODEL)

    def test_explicit_args_win(self):
        c = llm.LLMClient(endpoint="http://host:9/v1/", model="m1")
        self.assertEqual(c.endpoint, "http://host:9/v1")  # trailing slash stripped
        self.assertEqual(c.model, "m1")

    def test_env_vars(self):
        os.environ["PERMADESIGN_LLM_ENDPOINT"] = "http://env:1/v1"
        os.environ["PERMADESIGN_LLM_MODEL"] = "envmodel"
        c = llm.LLMClient()
        self.assertEqual(c.endpoint, "http://env:1/v1")
        self.assertEqual(c.model, "envmodel")

    def test_completions_url(self):
        c = llm.LLMClient(endpoint="http://host:9/v1")
        self.assertEqual(c._completions_url(), "http://host:9/v1/chat/completions")
        c2 = llm.LLMClient(endpoint="http://host:9/v1/chat/completions")
        self.assertEqual(c2._completions_url(), "http://host:9/v1/chat/completions")


if __name__ == "__main__":
    unittest.main()
