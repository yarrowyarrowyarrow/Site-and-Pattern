"""
tests/test_scene_dossier.py — the click-to-inspect learning content (V2.29).

src/scene_dossier.py is a pure function over a built scene, so every
collaborator is injected here and nothing touches the real DB: the point of the
module is that the card's content is derived, testable data rather than strings
assembled in JavaScript.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scene_dossier import build_dossier, TIMELINE_YEARS   # noqa: E402


def _scene(*plant_ids, year=0, month=6):
    return {
        "version": 1, "year": year, "month": month,
        "plants": [{"plant_id": pid, "common_name": f"Plant {pid}",
                    "x": float(i), "y": 0.0, "height_m": 2.0, "canopy_m": 2.0}
                   for i, pid in enumerate(plant_ids)],
    }


_PLANTS = {
    1: {"id": 1, "common_name": "Saskatoon Berry",
        "scientific_name": "Amelanchier alnifolia", "plant_type": "shrub",
        "bloom_period": "May-Jun", "fruit_period": "Jul-Aug",
        "flower_color": "#ffffff", "fruit_color": "#4b2e63",
        "native_provinces": "AB,SK", "sun_requirement": "full_sun",
        "water_needs": "low", "permaculture_uses": "bird_food,pollinator",
        "toxicity_pets": "", "toxicity_humans": "", "has_thorns": 0,
        "price_low_cad": 25, "price_high_cad": 50,
        "availability_class": "garden_centre",
        "mature_height_meters": 4.0, "years_to_maturity": 5,
        "growth_curve": "steady", "notes": "A prairie keystone."},
    2: {"id": 2, "common_name": "Showy Milkweed",
        "scientific_name": "Asclepias speciosa", "plant_type": "wildflower",
        "bloom_period": "Jun-Aug", "permaculture_uses": "host_plant",
        "toxicity_pets": "high", "toxicity_humans": "low", "has_thorns": 0,
        "mature_height_meters": 1.2, "years_to_maturity": 3,
        "growth_curve": "steady"},
}

# Monarch uses milkweed only; the waxwing uses the saskatoon only; the bumble
# bee uses both — so "only source here" must name the first two and not the bee.
_EDGES = [
    {"plant_id": 1, "id": 10, "common_name": "Cedar Waxwing",
     "scientific_name": "Bombycilla cedrorum", "taxon": "bird",
     "relationship": "fruit_food", "specificity": "generalist"},
    {"plant_id": 1, "id": 11, "common_name": "Bumble Bee",
     "scientific_name": "Bombus sp.", "taxon": "bee",
     "relationship": "nectar", "specificity": "generalist"},
    {"plant_id": 2, "id": 11, "common_name": "Bumble Bee",
     "scientific_name": "Bombus sp.", "taxon": "bee",
     "relationship": "nectar", "specificity": "generalist"},
    {"plant_id": 2, "id": 12, "common_name": "Monarch",
     "scientific_name": "Danaus plexippus", "taxon": "lepidoptera",
     "relationship": "larval_host", "specificity": "specialist"},
]


def _get_plant(pid):
    return _PLANTS.get(int(pid))


def _edges(pids):
    return [dict(r) for r in _EDGES if r["plant_id"] in set(pids)]


def _attrs(fid, taxon):
    if fid == 12:
        return {"kind": "butterfly", "flight_season": "Jun-Sep",
                "overwintering_stage": "migrant",
                "conservation_status": "At Risk",
                "larval_host_note": "Milkweeds only."}
    if fid == 11:
        return {"nesting_habit": "social_ground", "tongue_length": "long",
                "flight_season": "Apr-Sep", "pollen_specialist": 0}
    return {}


def _state(plant, lat, lng, year):
    """Stand-in for scene3d.plant_3d_state — linear to maturity, then flat."""
    ytm = plant.get("years_to_maturity") or 5
    f = min(1.0, max(0.1, year / float(ytm)))
    h = float(plant.get("mature_height_meters") or 1.0)
    return {"height_m": h * f, "canopy_m": h * 0.8 * f}


def _build(**kw):
    kw.setdefault("get_plant", _get_plant)
    kw.setdefault("fauna_edges", _edges)
    kw.setdefault("fauna_attrs", _attrs)
    kw.setdefault("plant_3d_state", _state)
    return build_dossier(kw.pop("scene"), **kw)


class DossierShapeTest(unittest.TestCase):
    def test_empty_scene_is_empty_not_an_error(self):
        d = build_dossier({"plants": []})
        self.assertEqual(d, {"plants": {}, "fauna": {}})

    def test_is_json_serialisable(self):
        d = _build(scene=_scene(1, 2))
        json.loads(json.dumps(d))       # the whole point: it is pushed as JSON

    def test_keys_are_the_ids_the_scene_carries(self):
        d = _build(scene=_scene(1, 2))
        # Plants by id-as-string (the viewer looks up from userData.pickId);
        # fauna by common name (what a creature record carries).
        self.assertEqual(set(d["plants"]), {"1", "2"})
        self.assertIn("Monarch", d["fauna"])


class PlantEntryTest(unittest.TestCase):
    def test_identity_and_seasons(self):
        e = _build(scene=_scene(1))["plants"]["1"]
        self.assertEqual(e["name"], "Saskatoon Berry")
        self.assertEqual(e["scientific_name"], "Amelanchier alnifolia")
        self.assertEqual(e["bloom"], "May–Jun")
        self.assertEqual(e["fruit"], "Jul–Aug")
        self.assertEqual(e["fruit_color"], "#4b2e63")

    def test_users_carry_the_relationship_and_specialism(self):
        e = _build(scene=_scene(1, 2))["plants"]["2"]
        monarch = next(u for u in e["users"] if u["name"] == "Monarch")
        self.assertEqual(monarch["how"], "caterpillar host for")
        self.assertTrue(monarch["specialist"])
        bee = next(u for u in e["users"] if u["name"] == "Bumble Bee")
        self.assertFalse(bee["specialist"])

    def test_only_source_names_species_this_plant_alone_supports(self):
        d = _build(scene=_scene(1, 2))
        # The bee uses both plants, so neither is its only source.
        self.assertEqual(d["plants"]["1"]["only_source"], ["Cedar Waxwing"])
        self.assertEqual(d["plants"]["2"]["only_source"], ["Monarch"])

    def test_only_source_is_relative_to_the_design_on_screen(self):
        """Remove the other plant and the bee's support becomes exclusive —
        the whole point of computing this against the live design (P3)."""
        d = _build(scene=_scene(1))
        self.assertEqual(d["plants"]["1"]["only_source"],
                         ["Bumble Bee", "Cedar Waxwing"])

    def test_unassessed_toxicity_is_reported_as_unassessed(self):
        """'' is not 'none': the card must not imply safety nobody checked."""
        e = _build(scene=_scene(1))["plants"]["1"]
        self.assertTrue(any("not assessed" in s for s in e["safety"]))

    def test_known_toxicity_is_stated_per_audience(self):
        e = _build(scene=_scene(2))["plants"]["2"]
        self.assertIn("High toxicity to pets", e["safety"])
        self.assertIn("Low toxicity to people", e["safety"])
        self.assertFalse(any("not assessed" in s for s in e["safety"]))

    def test_prices_are_labelled_estimates(self):
        e = _build(scene=_scene(1))["plants"]["1"]
        self.assertIn("estimate", e["sourcing"]["price"])

    def test_timeline_uses_the_growth_module_and_marks_the_scene_year(self):
        e = _build(scene=_scene(1, year=5))["plants"]["1"]
        self.assertEqual([r["year"] for r in e["timeline"]], list(TIMELINE_YEARS))
        self.assertTrue(all(r["height_m"] > 0 for r in e["timeline"]))
        now = [r for r in e["timeline"] if r["now"]]
        self.assertEqual([r["year"] for r in now], [5])

    def test_badges_come_from_the_shared_ecological_role_module(self):
        e = _build(scene=_scene(2))["plants"]["2"]
        self.assertIn("Hosts 1 caterpillar", e["badges"])
        self.assertIn("Specialist host", e["badges"])


class FaunaEntryTest(unittest.TestCase):
    def test_lists_only_the_plants_present_in_this_design(self):
        d = _build(scene=_scene(2))
        bee = d["fauna"]["Bumble Bee"]
        self.assertEqual([u["plant"] for u in bee["uses"]], ["Plant 2"])
        d2 = _build(scene=_scene(1, 2))
        self.assertEqual(len(d2["fauna"]["Bumble Bee"]["uses"]), 2)

    def test_relationship_reads_from_the_animals_side(self):
        d = _build(scene=_scene(2))
        self.assertEqual(d["fauna"]["Monarch"]["uses"][0]["how"], "lays eggs on")

    def test_bee_facts_come_from_the_narrow_attribute_table(self):
        f = _build(scene=_scene(1))["fauna"]["Bumble Bee"]
        self.assertTrue(any("ground" in s for s in f["facts"]))
        self.assertTrue(any("long tongue" in s for s in f["facts"]))
        self.assertEqual(f["season"], "Apr-Sep")

    def test_lep_facts_and_conservation_status(self):
        f = _build(scene=_scene(2))["fauna"]["Monarch"]
        self.assertEqual(f["status"], "At Risk")
        self.assertTrue(any("migrat" in s.lower() for s in f["facts"]))


class ResilienceTest(unittest.TestCase):
    def test_an_edge_query_failure_still_yields_plant_entries(self):
        """The card is a read nicety — a data hiccup must never cost the user
        the identity of what they clicked."""
        def boom(_pids):
            raise RuntimeError("db down")
        d = _build(scene=_scene(1), fauna_edges=boom)
        self.assertEqual(d["plants"]["1"]["name"], "Saskatoon Berry")
        self.assertEqual(d["plants"]["1"]["users"], [])
        self.assertEqual(d["fauna"], {})

    def test_unknown_plant_id_is_skipped_not_fatal(self):
        d = _build(scene=_scene(1, 999))
        self.assertEqual(set(d["plants"]), {"1"})

    def test_one_query_per_design_not_one_per_plant(self):
        calls = []

        def counting(pids):
            calls.append(list(pids))
            return _edges(pids)
        _build(scene=_scene(1, 2), fauna_edges=counting)
        self.assertEqual(len(calls), 1, "edges must be fetched once for the design")


if __name__ == "__main__":
    unittest.main()
