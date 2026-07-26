"""
tests/test_flower_morphology.py — the bloom as geometry (V2.34, schema v53).

What this guards is a JOIN, and joins are where this feature can fail silently.
Ten columns are authored in `scripts/seed_flower_morphology.py`, carried through
`src/db/plants.py` into the DB, passed through `src/scene_contract.py`, and read
by `html/scene3d/15-florets.js` to decide which of nine inflorescence
architectures to build. Break any link and the viewer falls back to the flat
64-pixel billboard — which looks like a slightly plainer scene, not like a bug,
and is exactly the state this release exists to leave behind.

Qt-free and DB-free where it can be: the seed script and the JSON catalogue are
plain data.
"""

import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MASTER = os.path.join(_ROOT, "data", "plants_master.json")
_FLORETS = os.path.join(_ROOT, "html", "scene3d", "15-florets.js")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _seeder():
    sys.path.insert(0, os.path.join(_ROOT, "scripts"))
    import seed_flower_morphology                     # noqa: PLC0415
    return seed_flower_morphology


class TestSeedData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = json.loads(_read(_MASTER))
        cls.seeder = _seeder()
        cls.described = [r for r in cls.catalogue if r.get("flower_arch")]

    def test_most_flowering_species_are_described(self):
        s = self.seeder
        flowering = [r for r in self.catalogue if s._flowers(r)]
        self.assertGreater(len(flowering), 250, "the catalogue stopped resolving")
        covered = sum(1 for r in flowering if r.get("flower_arch"))
        self.assertGreater(
            covered / len(flowering), 0.90,
            f"only {covered} of {len(flowering)} flowering species carry a "
            f"described flower — re-run scripts/seed_flower_morphology.py")

    def test_every_value_is_in_the_vocabulary(self):
        s = self.seeder
        for r in self.described:
            sci = r.get("scientific_name")
            self.assertIn(r["flower_arch"], s.ARCHITECTURES, sci)
            self.assertIn(r["flower_symmetry"], s.SYMMETRIES, sci)
            self.assertIn(r["petal_shape"], s.PETAL_SHAPES, sci)
            self.assertIn(r["stem_branching"], s.BRANCHINGS, sci)
            self.assertIn(r.get("basal_rosette"), (0, 1), sci)

    def test_diameters_are_plausible_flower_sizes(self):
        """One FLORET across, not the inflorescence and not the plant.

        The number exists because bloom size used to be derived from canopy. A
        value that has drifted back to inflorescence scale would silently undo
        that, and the render would look merely 'bold' rather than wrong.
        """
        for r in self.described:
            d = r.get("flower_diameter_cm")
            self.assertIsNotNone(d, r.get("scientific_name"))
            self.assertTrue(
                0.1 <= d <= 15.0,
                f"{r.get('scientific_name')}: flower_diameter_cm={d} is not a "
                f"floret — the column is ONE flower across")

    def test_rayless_composites_record_zero_rays_rather_than_a_guess(self):
        """P9: an honest zero, never an invented five.

        A thistle, a prairie sage and pussytoes have no ray florets at all. The
        viewer draws them as their disc alone, which is what they look like.
        """
        by_sci = {r.get("scientific_name"): r for r in self.catalogue}
        for sci in ("Cirsium flodmanii", "Artemisia ludoviciana",
                    "Antennaria parvifolia"):
            rec = by_sci.get(sci)
            if not rec or not rec.get("flower_arch"):
                continue
            self.assertEqual(rec.get("petal_count"), 0,
                             f"{sci} is rayless and must record 0 rays")
            self.assertEqual(rec.get("petal_shape"), "tubular", sci)

    def test_the_seeder_is_idempotent(self):
        """It is the provenance record as much as the tool, so a re-run must
        reproduce the shipped file exactly."""
        records = json.loads(_read(_MASTER))
        before = [{k: r.get(k) for k in self.seeder.FIELDS} for r in records]
        self.seeder.apply(records)
        after = [{k: r.get(k) for k in self.seeder.FIELDS} for r in records]
        self.assertEqual(before, after,
                         "re-running seed_flower_morphology.py would change "
                         "data/plants_master.json — the shipped file is stale")

    def test_flower_form_was_not_widened(self):
        """`flower_form` is a POLLINATOR-ACCESS statement, not a picture.

        bee_habitat.tongue_form_fit and forage_calendar read it. The whole point
        of v53 is that the picture went somewhere else, exactly as
        inflorescence_form did in v52.
        """
        src = _read(os.path.join(_ROOT, "src", "db", "schema.sql"))
        block = re.search(r"flower_form TEXT[^\n]*\n", src)
        self.assertIsNotNone(block)
        forms = set(r.get("flower_form") for r in self.catalogue) - {None, ""}
        self.assertLessEqual(
            len(forms), 16,
            f"flower_form grew to {sorted(forms)} — new PICTURE vocabulary "
            f"belongs in flower_arch/petal_shape, not here")


class TestViewerContract(unittest.TestCase):
    """The vocabularies have to match at both ends, or an architecture the seed
    data emits silently renders as something else."""

    @classmethod
    def setUpClass(cls):
        cls.js = _read(_FLORETS)
        cls.seeder = _seeder()

    def _js_list(self, name):
        m = re.search(r"const " + name + r" = \[(.*?)\];", self.js, re.S)
        self.assertIsNotNone(m, f"15-florets.js lost {name}")
        return set(re.findall(r"'(\w+)'", m.group(1)))

    def test_viewer_implements_every_architecture(self):
        have = self._js_list("FLORET_ARCHITECTURES")
        missing = set(self.seeder.ARCHITECTURES) - have
        self.assertFalse(
            missing,
            f"the seed data can emit {sorted(missing)} but the viewer does not "
            f"implement it — those species would fall through to the default "
            f"cyme and lose the silhouette the column exists for")

    def test_viewer_implements_every_petal_shape(self):
        have = self._js_list("PETAL_SHAPES")
        self.assertFalse(set(self.seeder.PETAL_SHAPES) - have)

    def test_every_architecture_has_a_placement(self):
        """A branch missing from floretPlacements is the silent case: the switch
        falls through to `default` and the species gets a cyme."""
        block = re.search(r"function floretPlacements\(.*?\n\}", self.js, re.S)
        self.assertIsNotNone(block, "15-florets.js lost floretPlacements")
        cases = set(re.findall(r"case '(\w+)':", block.group(0)))
        # `cyme` is the default branch on purpose, so it needs no case label.
        missing = set(self.seeder.ARCHITECTURES) - cases - {"cyme"}
        self.assertFalse(missing, f"no placement for {sorted(missing)}")

    def test_the_bloom_is_lit(self):
        """MeshBasicMaterial is unlit, and that was half of why a bed of flowers
        read as pasted on: it stayed the same flat colour at noon, at dusk, and
        in the shade of the tree beside it."""
        self.assertIn("MeshStandardMaterial", self.js)
        # Only the CODE — the module header names the old material to explain
        # why it is gone, and a comment is not a regression.
        code = "\n".join(ln for ln in self.js.splitlines()
                          if not ln.lstrip().startswith("//"))
        self.assertNotIn("MeshBasicMaterial", code,
                         "the floret layer went back to an unlit material")

    def test_empty_data_falls_back_to_the_billboard(self):
        """Partial coverage must never be a broken plant (P9)."""
        self.assertRegex(
            self.js, r"function floretsApply\(p\)[^}]*!!p\.flower_arch",
            "floretsApply stopped gating on flower_arch — a species the seed "
            "data does not describe would be built from defaults instead of "
            "drawing the billboard it drew before")
        flowers = _read(os.path.join(_ROOT, "html", "scene3d", "05-flowers.js"))
        self.assertIn("window.floretsApply(p)", flowers,
                      "05-flowers.js stopped handing modelled species over")

    def test_stylised_keeps_the_billboard(self):
        """A flat coloured stamp is honest inside a flat-shaded diagram, which
        is exactly what it is not inside a Lifelike scene."""
        self.assertRegex(self.js, r"function floretsApply\(p\)[^}]*!STYLISED")


class TestSceneContract(unittest.TestCase):
    def test_every_column_reaches_the_viewer(self):
        """The fields are read by name in the viewer, so a passthrough dropped
        in scene_contract is invisible until someone looks at a render."""
        src = _read(os.path.join(_ROOT, "src", "scene_contract.py"))
        for field in ("flower_arch", "flower_symmetry", "petal_shape",
                      "petal_count", "florets_per_head", "flower_diameter_cm",
                      "flower_center_color", "flower_height_frac"):
            self.assertIn(f'"{field}"', src,
                          f"scene_contract.py does not pass {field} through")

    def test_the_columns_exist_in_the_schema_and_the_seed_insert(self):
        schema = _read(os.path.join(_ROOT, "src", "db", "schema.sql"))
        plants = _read(os.path.join(_ROOT, "src", "db", "plants.py"))
        for field in _seeder().FIELDS:
            self.assertIn(field, schema, f"schema.sql has no {field}")
            self.assertIn(field, plants,
                          f"src/db/plants.py never seeds {field} — the column "
                          f"would exist and stay empty on every install")


if __name__ == "__main__":
    unittest.main()
