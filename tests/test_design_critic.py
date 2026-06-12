"""
tests/test_design_critic.py — the evaluate→revise→repair loop (V1.62).

Three layers:

  1. critique_lines — pure dict-in/lines-out (no DB).
  2. evaluate_design + apply_repairs against the real seeded catalogue in
     a sandboxed temp DB (same pattern as test_llm_design).
  3. The revision round inside generate_design: a fake client whose
     revise_spec returns a richer spec → adopted (with the score-delta
     warning); a same-spec revision → rejected (strictly-better rule);
     a raising revise_spec → round-1 design survives.

Headless: no Qt, no network, no real LLM.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_critic_test_")
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
from src.design_critic import (  # noqa: E402
    apply_repairs, critique_lines, evaluate_design,
)

_EDM = {"latitude": 53.5461, "longitude": -113.4938}


def _habitat(**overrides):
    """A baseline 'everything is fine' habitat dict; overrides poke holes."""
    comp = {
        "native": {"ratio": 1.0, "score": 20, "max": 20},
        "keystone": {"species": ["willow"], "score": 10, "max": 15},
        "host": {"species": ["willow"], "score": 8, "max": 10},
        "bird_food": {"species": ["saskatoon"], "score": 6, "max": 10},
        "layers": {"present": ["overstory", "shrub_layer", "herbaceous"],
                   "score": 9, "max": 15},
        "structures": {"types": ["bee_hotel"], "score": 5, "max": 10},
        "bloom": {"months": [5, 6, 7, 8, 9], "gap_months": [],
                  "score": 18, "max": 20},
    }
    comp.update(overrides)
    return {"total": 70, "grade": "Solid habitat", "components": comp}


class TestCritiqueLines(unittest.TestCase):

    def test_healthy_design_has_no_critique(self):
        self.assertEqual(critique_lines(_habitat()), [])

    def test_bloom_gap_names_months(self):
        h = _habitat(bloom={"months": [5, 6], "gap_months": [8, 9],
                            "score": 9, "max": 20})
        lines = critique_lines(h)
        self.assertEqual(len(lines), 1)
        self.assertIn("August", lines[0])
        self.assertIn("September", lines[0])

    def test_zero_components_flagged(self):
        h = _habitat(
            keystone={"species": [], "score": 0, "max": 15},
            host={"species": [], "score": 0, "max": 10},
            structures={"types": [], "score": 0, "max": 10},
        )
        text = "\n".join(critique_lines(h))
        self.assertIn("keystone", text)
        self.assertIn("host", text)
        self.assertIn("structure", text)

    def test_low_native_ratio_flagged(self):
        h = _habitat(native={"ratio": 0.5, "score": 10, "max": 20})
        self.assertTrue(any("native" in ln.lower()
                            for ln in critique_lines(h)))

    def test_thin_layers_flagged(self):
        h = _habitat(layers={"present": ["herbaceous"], "score": 3,
                             "max": 15})
        self.assertTrue(any("layer" in ln.lower()
                            for ln in critique_lines(h)))


class TestEvaluateAndRepair(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _use_our_db()

    def _project_with(self, queries):
        from src.permadesign_api import Project, query_plants
        proj = Project.create("critic-test", site_config=_EDM)
        for q in queries:
            rows = query_plants(query=q)
            self.assertTrue(rows, f"catalogue should match {q!r}")
            proj.place_plant(rows[0]["id"],
                             _EDM["latitude"], _EDM["longitude"])
        return proj

    def test_evaluate_design_returns_breakdown(self):
        proj = self._project_with(["yarrow"])
        h = evaluate_design(proj)
        self.assertIsNotNone(h)
        self.assertIn("total", h)
        self.assertIn("bloom", h["components"])

    def test_evaluate_empty_project_is_none(self):
        from src.permadesign_api import Project
        self.assertIsNone(evaluate_design(Project.create("e",
                                                         site_config=_EDM)))

    def test_repairs_fill_keystone_and_host_gaps(self):
        from src.permadesign_api import query_plants
        proj = self._project_with(["yarrow"])
        before = len(proj.placed_plants)
        msgs = apply_repairs(
            proj, query_plants,
            lambda: (_EDM["latitude"], _EDM["longitude"]))
        after = len(proj.placed_plants)
        self.assertGreater(after, before)
        self.assertTrue(msgs)
        self.assertLessEqual(after - before, 3)   # repair cap
        # The repairs actually move the relevant scores off zero.
        h = evaluate_design(proj)
        self.assertGreater(h["components"]["keystone"]["score"], 0)

    def test_repairs_respect_cap(self):
        from src.permadesign_api import query_plants
        proj = self._project_with(["yarrow"])
        msgs = apply_repairs(
            proj, query_plants,
            lambda: (_EDM["latitude"], _EDM["longitude"]),
            max_additions=1)
        self.assertLessEqual(len(msgs), 1)

    def test_healthy_design_needs_no_repairs(self):
        from src.permadesign_api import query_plants
        proj = self._project_with(["yarrow"])
        healthy = _habitat()
        msgs = apply_repairs(
            proj, query_plants,
            lambda: (_EDM["latitude"], _EDM["longitude"]),
            habitat=healthy)
        self.assertEqual(msgs, [])


class _ReviseClient:
    """Fake LLM client with a revision round."""

    def __init__(self, spec1, spec2=None, raise_on_revise=False):
        self._spec1 = spec1
        self._spec2 = spec2 if spec2 is not None else spec1
        self._raise = raise_on_revise
        self.revise_calls = []
        self.endpoint = "fake://local"
        self.model = "fake-model"

    def generate_spec(self, prompt, context, extra_hints=None):
        return self._spec1

    def revise_spec(self, prompt, context, first_spec, critique,
                    extra_hints=None):
        self.revise_calls.append(list(critique))
        if self._raise:
            from src.errors import LLMError
            raise LLMError("revision endpoint died")
        return self._spec2


def _revision_warnings(project):
    return [w for w in (project.as_dict().get("properties", {})
                        .get("generation_warnings", []))
            if w.startswith("Design revised after evaluation")]


class TestRevisionRound(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _use_our_db()

    _SPARSE = {"plants": [{"query": "yarrow", "quantity": 2}]}
    _RICH = {"plants": [
        {"query": "yarrow", "quantity": 2},
        {"query": "willow", "quantity": 1},      # keystone/host value
        {"query": "saskatoon", "quantity": 1},   # bird food
        {"query": "goldenrod", "quantity": 1},   # late bloom
        {"query": "aster", "quantity": 1},
    ], "structures": [{"structure_id": "bee_hotel"}]}

    def test_better_revision_is_adopted(self):
        client = _ReviseClient(self._SPARSE, self._RICH)
        project = llm.generate_design("habitat", site_config=_EDM,
                                      client=client)
        self.assertEqual(len(client.revise_calls), 1)
        # The critique handed to the model is the concrete issue list.
        self.assertTrue(any("keystone" in ln or "host" in ln
                            for ln in client.revise_calls[0]))
        self.assertEqual(len(_revision_warnings(project)), 1)
        placed_names = " ".join(
            p.get("common_name", "") for p in project.placed_plants).lower()
        self.assertIn("willow", placed_names)

    def test_same_spec_revision_is_rejected(self):
        client = _ReviseClient(self._SPARSE, self._SPARSE)
        project = llm.generate_design("habitat", site_config=_EDM,
                                      client=client)
        self.assertEqual(len(client.revise_calls), 1)
        self.assertEqual(_revision_warnings(project), [])

    def test_failing_revision_keeps_round_one(self):
        client = _ReviseClient(self._SPARSE, raise_on_revise=True)
        project = llm.generate_design("habitat", site_config=_EDM,
                                      client=client)
        self.assertEqual(_revision_warnings(project), [])
        self.assertTrue(project.placed_plants)   # round-1 design intact

    def test_revise_false_skips_the_round(self):
        client = _ReviseClient(self._SPARSE, self._RICH)
        llm.generate_design("habitat", site_config=_EDM, client=client,
                            revise=False)
        self.assertEqual(client.revise_calls, [])

    def test_offline_designs_get_critic_repairs(self):
        # The deterministic critic runs on the no-LLM path too: an offline
        # design should carry repair notes or already cover the gaps.
        project = llm.generate_design_offline(site_config=_EDM)
        h = evaluate_design(project)
        self.assertIsNotNone(h)
        self.assertGreater(h["components"]["keystone"]["score"], 0)


if __name__ == "__main__":
    unittest.main()
