"""
tests/test_plant_directory.py — the catalogue as a reference work (F90, V2.41).

*"explore the plant directory (which we have not built yet but I think would be
an excellent feature of a native plant education app and we have all the data)."*

What these hold down:

  * the facet table cannot drift from ``search_plants``' real signature — the
    directory's whole cheapness rests on driving a query layer it did not write;
  * a species page carries its **evidence**, not just its claims;
  * the in-bloom line never implies a regional count it cannot support;
  * ``plant_panel.py`` gains no lines — it is at its ceiling, and the directory
    exists partly so it never has to grow.
"""

import ast
import inspect
import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestTheFacetsDriveTheRealQuery(unittest.TestCase):
    """The directory writes no query layer of its own: it names parameters on
    ``db.plants.search_plants``. A typo there is a filter that silently does
    nothing, which is the exact shape of the V2.37 dead-control bugs."""

    def test_every_facet_names_a_real_search_parameter(self):
        from src.db.plants import search_plants
        from src import plant_directory as pd
        real = set(inspect.signature(search_plants).parameters)
        self.assertEqual(pd.facet_params() - real, set())

    def test_it_surfaces_filters_no_other_screen_exposes(self):
        """The point of the directory, in one assertion. These worked the whole
        time with nothing to press."""
        from src import plant_directory as pd
        panel = (_ROOT / "src" / "plant_panel.py").read_text(encoding="utf-8")
        exposed = {t[2] for t in pd.TOGGLES}
        new = {p for p in exposed if p not in panel}
        self.assertGreaterEqual(len(new), 6, sorted(exposed))

    def test_criteria_become_keyword_arguments(self):
        from src import plant_directory as pd
        kw = pd.criteria_to_kwargs({
            "query": " bergamot ", "type": ["shrub", "tree"],
            "keystone_only": True, "bloom_months": ["6", "7"],
            "sun": [], "edible_only": False,
        })
        self.assertEqual(kw["query"], "bergamot")
        self.assertEqual(kw["plant_type"], ["shrub", "tree"])
        self.assertTrue(kw["keystone_only"])
        self.assertEqual(kw["bloom_months"], [6, 7])
        # An untouched facet must be absent, not an empty list — "no
        # restriction" and "match nothing" are one typo apart downstream.
        self.assertNotIn("sun_req", kw)
        self.assertNotIn("edible_only", kw)

    def test_an_empty_criteria_asks_for_everything(self):
        from src import plant_directory as pd
        self.assertEqual(pd.criteria_to_kwargs(None), {})
        self.assertEqual(pd.criteria_to_kwargs({}), {})

    def test_search_passes_them_through_and_sorts(self):
        from src import plant_directory as pd
        seen = {}

        def fake(**kwargs):
            seen.update(kwargs)
            return [{"common_name": "Wild Bergamot"}, {"common_name": "Aster"}]

        rows = pd.search({"keystone_only": True}, search_fn=fake)
        self.assertTrue(seen["keystone_only"])
        self.assertEqual([r["common_name"] for r in rows],
                         ["Aster", "Wild Bergamot"])


class TestSorting(unittest.TestCase):
    _ROWS = [
        {"common_name": "Beaked Hazelnut", "plant_type": "shrub",
         "mature_height_meters": 4, "_wildlife_count": 2},
        {"common_name": "Aspen", "plant_type": "tree",
         "mature_height_meters": 20, "_wildlife_count": 9},
        {"common_name": "Yarrow", "plant_type": "wildflower",
         "mature_height_meters": 0.6, "_wildlife_count": 5},
    ]

    def test_by_name_is_the_default(self):
        from src import plant_directory as pd
        self.assertEqual([r["common_name"] for r in pd.sort_species(self._ROWS)],
                         ["Aspen", "Beaked Hazelnut", "Yarrow"])

    def test_by_height_is_tallest_first(self):
        from src import plant_directory as pd
        rows = pd.sort_species(self._ROWS, "height")
        self.assertEqual(rows[0]["common_name"], "Aspen")
        self.assertEqual(rows[-1]["common_name"], "Yarrow")

    def test_an_unknown_key_falls_back_rather_than_raising(self):
        """A directory that refuses to draw because a sort key was misspelt is
        worse than one that draws in the wrong order."""
        from src import plant_directory as pd
        self.assertEqual(
            [r["common_name"] for r in pd.sort_species(self._ROWS, "nonsense")],
            ["Aspen", "Beaked Hazelnut", "Yarrow"])

    def test_missing_numbers_do_not_crash_the_sort(self):
        from src import plant_directory as pd
        rows = pd.sort_species([{"common_name": "A"},
                                {"common_name": "B",
                                 "mature_height_meters": None}], "height")
        self.assertEqual(len(rows), 2)


class TestASpeciesPageCarriesItsEvidence(unittest.TestCase):
    """P9. A region seen 242 times and one seen 5 times are different claims,
    and a page that prints them identically is inventing certainty."""

    def _entry(self, **over):
        from src import plant_directory as pd
        plant = {
            "id": 7, "common_name": "Saskatoon Berry",
            "scientific_name": "Amelanchier alnifolia", "plant_type": "shrub",
            "sun_requirement": "full_sun", "water_needs": "low",
            "soil_ph_min": 5.5, "soil_ph_max": 7.5,
            "hardiness_zone_min": 2, "hardiness_zone_max": 7,
            "mature_height_meters": 4.0, "ecoregion": "aspen_parkland",
            "permaculture_uses": "bird_food",
        }
        plant.update(over.pop("plant", {}))
        kwargs = dict(
            get_plant=lambda _i: plant,
            fauna_for_plant=lambda _i: over.pop("fauna", []),
            neighbourhood=lambda _i: {"plant_id": 7, "total": 0, "groups": []},
            ranges_for=lambda _ids: over.pop("ranges", {}),
            calendar_for=lambda _i: [],
            photos_for=lambda _n: [],
        )
        return pd.species_entry(7, **kwargs)

    def test_a_sourced_range_keeps_its_count_and_confidence(self):
        entry = self._entry(ranges={7: [
            {"ecoregion": "aspen_parkland", "occurrences": 242,
             "confidence": "high", "source": "GBIF"},
            {"ecoregion": "boreal_mixedwood", "occurrences": 5,
             "confidence": "low", "source": "GBIF"}]})
        first, second = entry["ranges"][0], entry["ranges"][1]
        self.assertEqual((first["occurrences"], first["confidence"]),
                         (242, "high"))
        self.assertEqual((second["occurrences"], second["confidence"]),
                         (5, "low"))

    def test_strongest_evidence_comes_first(self):
        entry = self._entry(ranges={7: [
            {"ecoregion": "boreal_mixedwood", "occurrences": 5,
             "confidence": "low"},
            {"ecoregion": "aspen_parkland", "occurrences": 242,
             "confidence": "high"}]})
        self.assertEqual(entry["ranges"][0]["occurrences"], 242)

    def test_an_underived_range_says_it_has_no_occurrences(self):
        """Falling back to the heuristic column is fine; passing it off as a
        sourced range is not."""
        entry = self._entry(ranges={})
        self.assertTrue(entry["ranges"])
        self.assertEqual(entry["ranges"][0]["occurrences"], 0)
        self.assertEqual(entry["ranges"][0]["confidence"], "")

    def test_specialists_are_counted_apart_from_the_rest(self):
        """A generalist losing this plant finds another. A specialist does
        not — the most consequential thing on the page (P3)."""
        entry = self._entry(fauna=[
            {"common_name": "Monarch", "taxon": "lepidoptera",
             "relationship": "larval_host", "specificity": "specialist"},
            {"common_name": "Robin", "taxon": "bird",
             "relationship": "fruit_food", "specificity": "generalist"}])
        self.assertEqual(entry["wildlife"]["total"], 2)
        self.assertEqual(entry["wildlife"]["specialists"], 1)

    def test_safety_says_unassessed_rather_than_nothing(self):
        entry = self._entry()
        self.assertTrue(any("not assessed" in s for s in entry["safety"]))

    def test_a_missing_plant_is_an_empty_dict_not_a_crash(self):
        from src import plant_directory as pd
        self.assertEqual(pd.species_entry(999, get_plant=lambda _i: None), {})

    def test_one_failing_source_costs_its_section_not_the_page(self):
        """A species page must render even when a collaborator is unavailable.
        A missing section is a gap; a traceback is a dead feature."""
        from src import plant_directory as pd

        def boom(*_a, **_k):
            raise RuntimeError("no database here")

        entry = pd.species_entry(
            7, get_plant=lambda _i: {"id": 7, "common_name": "X",
                                     "scientific_name": "X x"},
            fauna_for_plant=boom, neighbourhood=boom, ranges_for=boom,
            calendar_for=boom, photos_for=boom)
        self.assertEqual(entry["name"], "X")
        self.assertEqual(entry["wildlife"]["total"], 0)
        self.assertEqual(entry["ranges"], [])

    def test_the_photo_falls_back_to_the_single_image_url(self):
        """The 7-slot photo table ships empty; 323 of 434 species carry the
        older single ``image_url``. The page has to read both."""
        entry = self._entry(plant={"image_url": "https://x/y.jpg",
                                   "image_attribution": "someone",
                                   "image_license": "CC BY"})
        self.assertEqual(len(entry["photos"]), 1)
        self.assertEqual(entry["photos"][0]["url"], "https://x/y.jpg")

    def test_no_photo_at_all_is_an_empty_list(self):
        self.assertEqual(self._entry()["photos"], [])


class TestWhatIsInBloomNow(unittest.TestCase):
    def test_it_counts_this_month(self):
        from src import plant_directory as pd
        seen = {}

        def fake(**kwargs):
            seen.update(kwargs)
            return [{"common_name": "A"}, {"common_name": "B"}]

        out = pd.in_bloom_now(month=6, search_fn=fake)
        self.assertEqual(seen["bloom_months"], [6])
        self.assertEqual(out["count"], 2)
        self.assertEqual(out["month_name"], "June")

    def test_without_a_location_it_says_so(self):
        """"14 species are in bloom" reads as a local claim. It would not be
        one — the start screen runs before any project is open (P9)."""
        from src import plant_directory as pd
        line = pd.bloom_line(pd.in_bloom_now(
            month=6, search_fn=lambda **_k: [{"common_name": "A"}]))
        self.assertIn("across the catalogue", line)
        self.assertNotIn("in None", line)

    def test_with_a_region_it_names_it(self):
        from src import plant_directory as pd
        out = pd.in_bloom_now(month=6, ecoregion="aspen_parkland",
                              search_fn=lambda **_k: [{"common_name": "A"}])
        self.assertIn("Aspen", pd.bloom_line(out))
        self.assertNotIn("across the catalogue", pd.bloom_line(out))

    def test_nothing_in_bloom_draws_no_line(self):
        from src import plant_directory as pd
        self.assertEqual(pd.bloom_line(pd.in_bloom_now(
            month=1, search_fn=lambda **_k: [])), "")

    def test_one_species_reads_as_one(self):
        from src import plant_directory as pd
        line = pd.bloom_line(pd.in_bloom_now(
            month=6, search_fn=lambda **_k: [{"common_name": "A"}]))
        self.assertIn("1 species is in bloom", line)


class TestItCostsThePickerNothing(unittest.TestCase):
    """``src/plant_panel.py`` sits at exactly its 1600-line guard ceiling. The
    directory is a separate surface partly so the browser never has to grow to
    hold a reference work's worth of controls."""

    def test_the_directory_does_not_touch_plant_panel(self):
        panel = (_ROOT / "src" / "plant_panel.py").read_text(encoding="utf-8")
        for name in ("plant_directory", "PlantDirectoryWindow",
                     "open_plant_directory"):
            self.assertNotIn(name, panel)

    def test_plant_panel_is_still_within_its_ceiling(self):
        panel = _ROOT / "src" / "plant_panel.py"
        with open(panel, encoding="utf-8") as f:
            self.assertLessEqual(sum(1 for _ in f), 1600)

    def test_the_core_stays_qt_free(self):
        """It is imported by the start screen's footer before any window
        exists, and tested here without a display."""
        src = (_ROOT / "src" / "plant_directory.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                name = getattr(node, "module", "") or ""
                names = [a.name for a in node.names] + [name]
                self.assertFalse(any("PyQt" in n for n in names if n),
                                 f"line {node.lineno} imports Qt")


class TestP12(unittest.TestCase):
    """The hard rule. The directory shows fields the data model already holds;
    it must not grow ethnobotanical content or relabel a field to imply any."""

    #: Words that would mean the directory had started *encoding* the knowledge
    #: rather than pointing at it. Checked against labels, headings and field
    #: names — never against docstrings, which is where the rule itself is
    #: written down and must be allowed to name what it forbids.
    _FORBIDDEN = ("indigenous", "traditional use", "ethnobotan",
                  "first nations", "medicine wheel", "ceremonial")

    def test_no_indigenous_knowledge_vocabulary_reaches_the_screen(self):
        for name in ("plant_directory.py", "plant_directory_window.py",
                     "start_screen.py"):
            for text in self._user_facing(_ROOT / "src" / name):
                for word in self._FORBIDDEN:
                    self.assertNotIn(word, text.lower(),
                                     f"{name}: {text!r} mentions {word!r}")

    @staticmethod
    def _user_facing(path: pathlib.Path) -> list:
        """Every string literal in the module that is not a docstring, plus
        every name it defines."""
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                body = getattr(node, "body", None) or []
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    docstrings.add(id(body[0].value))
        out = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docstrings):
                out.append(node.value)
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                out.append(node.name)
        return out

    def test_the_guard_would_catch_a_real_violation(self):
        """A test that cannot fail proves nothing. This one is checked against
        a module that does contain the word outside a docstring."""
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                         encoding="utf-8") as f:
            f.write('"""Fine in here: ethnobotanical."""\n'
                    'LABEL = "Traditional use"\n')
            path = pathlib.Path(f.name)
        self.addCleanup(os.unlink, path)
        texts = [t.lower() for t in self._user_facing(path)]
        self.assertTrue(any("traditional use" in t for t in texts))
        self.assertFalse(any("ethnobotan" in t for t in texts))


if __name__ == "__main__":
    unittest.main()
