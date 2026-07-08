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
        self.extra_hints_seen = []
        self.endpoint = "fake://local"
        self.model = "fake-model"

    def generate_spec(self, prompt, context, extra_hints=None):
        self.calls.append((prompt, context))
        self.extra_hints_seen.append(list(extra_hints or []))
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
        # V1.50: each group expands into its quantity via a layout pattern, so
        # the yarrow(3) + willow(1) spec yields several placements, not 2.
        self.assertGreaterEqual(len(placed), 4)
        # Both requested species resolve and appear.
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
        # A boundary alone anchors placement (no site_config needed); plants are
        # placed inside it. (Count is density-driven in V1.50, so don't pin it.)
        self.assertGreaterEqual(len(project.placed_plants), 1)
        poly = llm._boundary_polygon(boundary)
        from src.geometry import point_in_polygon
        for p in project.placed_plants:
            self.assertTrue(point_in_polygon(p["lat"], p["lng"], poly))

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


class TestGoalsAndOffline(unittest.TestCase):
    """Design-goal wiring (hybrid filters + hints) and the no-LLM fallback."""

    @classmethod
    def setUpClass(cls):
        _use_our_db()

    def test_edible_and_perennial_filters_whitelisted(self):
        self.assertIn("edible_only", llm._ALLOWED_FILTERS)
        self.assertIn("perennial_only", llm._ALLOWED_FILTERS)

    def test_goal_hard_filter_binds_without_spec_filters(self):
        # Model returns bare names with no filters; native_only must still bind
        # so everything placed is Alberta-native.
        from src.db.plants import get_plant
        spec = {"plants": [{"query": "willow"}, {"query": "yarrow"}]}
        client = _FakeClient(spec)
        project = llm.generate_design("x", site_config=_EDM, client=client,
                                      goals=["native_only"])
        placed = project.placed_plants
        self.assertGreaterEqual(len(placed), 1)
        for p in placed:
            rec = get_plant(p["plant_id"])
            self.assertTrue(rec and rec.get("native_to_alberta"),
                            f"{p.get('common_name')} should be Alberta-native")

    def test_goal_hint_appended_to_brief(self):
        client = _FakeClient({"plants": [{"query": "yarrow"}]})
        llm.generate_design("x", site_config=_EDM, client=client,
                            goals=["pet_friendly"])
        self.assertTrue(client.extra_hints_seen)
        hints = client.extra_hints_seen[0]
        self.assertTrue(any("toxic" in h.lower() for h in hints),
                        f"pet_friendly hint missing from {hints}")

    def test_unbacked_goal_recorded_as_warning(self):
        # year_round_interest is still hint-only (no data backs it).
        client = _FakeClient({"plants": [{"query": "yarrow"}]})
        project = llm.generate_design("x", site_config=_EDM, client=client,
                                      goals=["year_round_interest"])
        warnings = project.as_dict()["properties"].get("generation_warnings", [])
        self.assertTrue(any("guidance" in w.lower() for w in warnings))

    def test_allowed_filters_include_cost(self):
        self.assertIn("max_unit_price", llm._ALLOWED_FILTERS)
        self.assertIn("common_only", llm._ALLOWED_FILTERS)

    def test_offline_budget_trims_and_notes(self):
        # A tight budget still yields a usable design and records a cost note.
        project = llm.generate_design_offline(
            site_config=_EDM, goals=["native_only"], budget=20)
        self.assertGreaterEqual(len(project.placed_plants), 1)
        warnings = project.as_dict()["properties"].get("generation_warnings", [])
        self.assertTrue(any("Estimated plant cost" in w for w in warnings),
                        f"cost note missing from {warnings}")

    def test_offline_no_budget_has_no_cost_note(self):
        project = llm.generate_design_offline(
            site_config=_EDM, goals=["native_only"])
        warnings = project.as_dict()["properties"].get("generation_warnings", [])
        self.assertFalse(any("Estimated plant cost" in w for w in warnings))

    def test_offline_places_multiple_communities(self):
        # D2: a pollinator design now lays down >=2 distinct seeded communities
        # as grouped units (previously a single default).
        project = llm.generate_design_offline(
            site_config=_EDM, goals=["pollinator"])
        names = set()
        for f in project.as_dict().get("features", []):
            props = f.get("properties", {})
            if props.get("element_type") == "plant":
                pn = (props.get("polyculture_name") or "").strip()
                if pn:
                    names.add(pn)
        self.assertGreaterEqual(
            len(names), 2, f"expected >=2 communities placed, got {names}")

    def test_offline_fauna_targeting_places_supporters(self):
        # Designing for the Monarch must include a plant that supports it
        # (milkweed); the offline path leads with such plants.
        from src.db.fauna import list_fauna
        from src.permadesign_api import query_plants
        mon = next(f for f in list_fauna() if f["common_name"] == "Monarch")
        project = llm.generate_design_offline(
            site_config=_EDM, goals=["native_only"], fauna_ids=[mon["id"]])
        placed = {p.get("plant_id") for p in project.placed_plants}
        supporters = {p["id"] for p in query_plants(supports_fauna_id=mon["id"])}
        self.assertTrue(supporters)
        self.assertTrue(placed & supporters,
                        "expected a Monarch-supporting plant in the design")

    def test_fauna_feedback_adds_supporter_when_missing(self):
        # A fake spec naming only an unrelated plant; fauna feedback should add
        # a Monarch supporter so the chosen wildlife is actually served.
        from src.db.fauna import list_fauna
        from src.permadesign_api import query_plants
        mon = next(f for f in list_fauna() if f["common_name"] == "Monarch")
        client = _FakeClient({"plants": [{"query": "white spruce"}]})
        project = llm.generate_design(
            "x", site_config=_EDM, client=client, fauna_ids=[mon["id"]])
        placed = {p.get("plant_id") for p in project.placed_plants}
        supporters = {p["id"] for p in query_plants(supports_fauna_id=mon["id"])}
        self.assertTrue(placed & supporters)
        warnings = project.as_dict()["properties"].get("generation_warnings", [])
        self.assertTrue(any("wildlife" in w.lower() for w in warnings))

    def test_fauna_hint_reaches_brief(self):
        from src.db.fauna import list_fauna
        mon = next(f for f in list_fauna() if f["common_name"] == "Monarch")
        client = _FakeClient({"plants": [{"query": "showy milkweed"}]})
        llm.generate_design("x", site_config=_EDM, client=client,
                            fauna_ids=[mon["id"]])
        hints = client.extra_hints_seen[0]
        self.assertTrue(any("Monarch" in h for h in hints),
                        f"fauna hint missing from {hints}")

    def test_safety_goal_caveat_recorded(self):
        # Pet friendly is now backed by a denylist filter, but carries an
        # honest "not a guarantee" caveat in the generation warnings.
        client = _FakeClient({"plants": [{"query": "saskatoon"}]})
        project = llm.generate_design("x", site_config=_EDM, client=client,
                                      goals=["pet_friendly"])
        warnings = project.as_dict()["properties"].get("generation_warnings", [])
        self.assertTrue(any("guarantee" in w.lower() for w in warnings),
                        f"safety caveat missing from {warnings}")
        # And it should NOT be mislabelled as unbacked "guidance".
        self.assertFalse(any("guidance" in w.lower() for w in warnings))

    def test_apply_goal_feedback_repairs_unsatisfied_hard_goal(self):
        from src.permadesign_api import Project, query_plants
        from src.db.plants import get_plant
        non_native = next((p for p in query_plants()
                           if not p.get("native_to_alberta")), None)
        if non_native is None:
            self.skipTest("no non-native plants in catalogue")
        project = Project.create("t", site_config=_EDM)
        project.place_plant(non_native["id"], _EDM["latitude"], _EDM["longitude"])
        llm._apply_goal_feedback(project, ["native_only"], query_plants,
                                 (_EDM["latitude"], _EDM["longitude"]))
        placed = project.placed_plants
        # The repair adds at least one native to honour the goal (exact count
        # isn't pinned — the invariant is that a native was added).
        self.assertGreaterEqual(len(placed), 2)
        self.assertTrue(any(get_plant(p["plant_id"]).get("native_to_alberta")
                            for p in placed))
        warnings = project.as_dict()["properties"]["generation_warnings"]
        self.assertTrue(any("honour" in w.lower() for w in warnings))

    def test_offline_generation_needs_no_client(self):
        project = llm.generate_design_offline(site_config=_EDM,
                                              goals=["food_producing"])
        self.assertGreaterEqual(len(project.placed_plants), 1)

    def test_offline_with_no_goals_still_produces_design(self):
        project = llm.generate_design_offline(site_config=_EDM)
        self.assertGreaterEqual(len(project.placed_plants), 1)

    def test_offline_matches_community_by_name(self):
        communities = _api.list_polycultures()
        ids = llm._match_communities_by_name(communities, ["Pollinator"])
        self.assertTrue(ids, "expected a 'Pollinator' community match")

    def test_offline_requires_site_location(self):
        with self.assertRaises(LLMError):
            llm.generate_design_offline(goals=["native_only"])


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


class TestExistingFeaturesNote(unittest.TestCase):
    """V1.59 — OSM buildings now import as canopy_footprint polygons, so the
    'design around these' prompt note must still count them (and hand-drawn
    building outlines)."""

    def _feat(self, et, **props):
        props["element_type"] = et
        return {"properties": props}

    def test_counts_canopy_footprint_buildings(self):
        proj = {"features": [
            self._feat("existing_tree"),
            self._feat("canopy_footprint", cast_shade=True, source="osm"),
            self._feat("canopy_footprint", cast_shade=True),   # hand-drawn
        ]}
        note = llm._existing_features_note(proj)
        self.assertIn("2 buildings", note)
        self.assertIn("1 existing tree", note)

    def test_non_casting_shape_not_counted(self):
        # A plain area marker (custom_shape, or a canopy_footprint without
        # cast_shade) is not an obstacle to mention.
        proj = {"features": [
            self._feat("custom_shape"),
            self._feat("canopy_footprint"),
        ]}
        self.assertEqual(llm._existing_features_note(proj), "")


class TestPlacementSpread(unittest.TestCase):
    """V2.20 — a generated design must use the whole boundary and mass each
    species as repeated modest drifts, not one blob. Guards the regression
    where every group crammed along the boundary's north edge (row-major
    cell consumption + cohesion pull) leaving ~80% of the lot empty."""

    @classmethod
    def setUpClass(cls):
        _use_our_db()

    @staticmethod
    def _boundary():
        """~90 m × 54 m rectangle at Edmonton, as (lat, lng) corners."""
        import math
        lat0, lng0 = 53.5461, -113.4938
        dlat = 90.0 / 111320.0
        dlng = 54.0 / (111320.0 * math.cos(math.radians(lat0)))
        return [(lat0, lng0), (lat0 + dlat, lng0),
                (lat0 + dlat, lng0 + dlng), (lat0, lng0 + dlng)]

    def _generate(self):
        spec = {
            "summary": "spread test",
            "plants": [
                {"query": "yarrow", "quantity": 18},
                {"query": "willow", "quantity": 4},
            ],
        }
        return llm.generate_design(
            "use the whole yard", boundary=self._boundary(),
            client=_FakeClient(spec), match_site=False, revise=False)

    def test_design_covers_the_boundary(self):
        project = self._generate()
        placed = project.placed_plants
        self.assertGreater(len(placed), 10)
        b = self._boundary()
        b_lat_span = max(p[0] for p in b) - min(p[0] for p in b)
        b_lng_span = max(p[1] for p in b) - min(p[1] for p in b)
        lat_span = (max(p["lat"] for p in placed)
                    - min(p["lat"] for p in placed))
        lng_span = (max(p["lng"] for p in placed)
                    - min(p["lng"] for p in placed))
        self.assertGreaterEqual(
            lat_span / b_lat_span, 0.5,
            f"plants cover only {lat_span / b_lat_span:.0%} of the "
            f"boundary's north–south span — the top-band regression")
        self.assertGreaterEqual(
            lng_span / b_lng_span, 0.5,
            f"plants cover only {lng_span / b_lng_span:.0%} of the "
            f"boundary's east–west span")

    def test_species_repeat_as_separated_drifts(self):
        import math
        project = self._generate()
        yid = _api.query_plants(query="yarrow")[0]["id"]
        pts = [(p["lat"], p["lng"]) for p in project.placed_plants
               if p.get("plant_id") == yid]
        self.assertGreater(len(pts), 9, "density expansion should have "
                                        "grown the yarrow beyond one drift")
        cos_lat = math.cos(math.radians(pts[0][0]))
        max_d = 0.0
        for i, a in enumerate(pts):
            for c in pts[i + 1:]:
                dx = (c[1] - a[1]) * 111320.0 * cos_lat
                dy = (c[0] - a[0]) * 111320.0
                max_d = max(max_d, (dx * dx + dy * dy) ** 0.5)
        self.assertGreater(max_d, 20.0,
                           "one species should spread as repeated drifts "
                           "across the lot, not pool in a single blob")

    def test_split_into_drifts_caps_group_size(self):
        yid = _api.query_plants(query="yarrow")[0]["id"]
        out = llm._split_into_drifts([(yid, 20, "")])
        self.assertEqual(sum(q for _, q, _ in out), 20)
        self.assertTrue(all(q <= llm._DRIFT_MAX_DEFAULT for _, q, _ in out))
        self.assertGreaterEqual(len(out), 3)

    def test_generation_is_deterministic(self):
        p1 = self._generate()
        p2 = self._generate()
        pts1 = sorted((p["plant_id"], round(p["lat"], 9), round(p["lng"], 9))
                      for p in p1.placed_plants)
        pts2 = sorted((p["plant_id"], round(p["lat"], 9), round(p["lng"], 9))
                      for p in p2.placed_plants)
        self.assertEqual(pts1, pts2)


if __name__ == "__main__":
    unittest.main()
