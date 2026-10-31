"""
tests/test_fauna_morphology.py — what the animals look like, guarded (V2.36).

Schema v58 moved fauna appearance out of Python name-substring tables and into
the catalogue. Four things now depend on the same vocabularies: the seeder, the
data-quality gate, the fauna bench's dropdowns, and the drawings in
html/botany/fauna.js. Every way they can disagree is silent:

  * a term in `data_quality` with no drawing renders an empty box beside the
    dropdown — no error, just a control that stopped helping;
  * a term drawn but not allowed puts a value in the chart that the gate will
    later reject;
  * a `band_pattern` colour outside BAND_COLOUR_HEX draws as a hatched segment
    that is easy to miss in a 100-species pass;
  * a stale docs/img/fauna/*.svg shows the reader a chart the app disagrees with.

Plus the reason the whole increment exists: the COLLAPSE. 69 bees rendered as
12 animals and 31 lepidoptera as 16. That is now a number this file asserts on,
so it cannot quietly regress.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

_JS = os.path.join(_ROOT, "html", "botany", "fauna.js")
_DIAGRAM_DIR = os.path.join(_ROOT, "docs", "img", "fauna")
_BEES = os.path.join(_ROOT, "data", "bee_attributes_master.json")
_LEPS = os.path.join(_ROOT, "data", "lepidoptera_attributes_master.json")

# vocabulary name in fauna.js -> the constant in src/data_quality.py
_VOCABS = {
    "wing_shape": "WING_SHAPES",
    "wing_pattern": "WING_PATTERNS",
    "resting_posture": "RESTING_POSTURES",
    "flight_style": "FLIGHT_STYLES",
    "bee_build": "BEE_BUILDS",
    "scopa_position": "SCOPA_POSITIONS",
}
_TABLE_CONST = {
    "wing_shape": "WING_SHAPES",
    "wing_pattern": "WING_PATTERNS",
    "resting_posture": "RESTING_POSTURES",
    "flight_style": "FLIGHT_STYLES",
    "bee_build": "BEE_BUILDS",
    "scopa_position": "SCOPA_POSITIONS",
}


def _js() -> str:
    with open(_JS, encoding="utf-8") as fh:
        return fh.read()


def _drawn(src: str, table: str) -> set:
    m = re.search(rf"\nvar {table} = \{{\n(.*?)\n\}};", src, re.S)
    assert m, f"{table} not found in fauna.js"
    return set(re.findall(r"^  (\w+):\s*function", m.group(1), re.M))


def _glossary(src: str) -> dict:
    m = re.search(r"var FAUNA_GLOSSARY = \{(.*?)\n\};", src, re.S)
    assert m, "FAUNA_GLOSSARY not found"
    out = {}
    for vocab in _VOCABS:
        block = re.search(rf"\n  {vocab}: \{{(.*?)\n  \}}", m.group(1), re.S)
        assert block, f"no glossary block for {vocab}"
        out[vocab] = dict(re.findall(r"^    (\w+): '(.*?)',?$",
                                     block.group(1), re.M))
    return out


def _records(path):
    with open(path, encoding="utf-8") as fh:
        return [r for r in json.load(fh) if r.get("scientific_name")]


class TestVocabulariesAgree(unittest.TestCase):
    def test_every_python_term_is_drawn(self):
        from src import data_quality                         # noqa: PLC0415
        src = _js()
        for vocab, const in _VOCABS.items():
            python = set(getattr(data_quality, const))
            drawn = _drawn(src, _TABLE_CONST[vocab])
            self.assertEqual(
                python - drawn, set(),
                f"{vocab}: in data_quality.{const} but not drawn — renders as "
                f"an empty box beside the bench dropdown")

    def test_no_term_is_drawn_that_python_does_not_allow(self):
        from src import data_quality                         # noqa: PLC0415
        src = _js()
        for vocab, const in _VOCABS.items():
            python = set(getattr(data_quality, const))
            drawn = _drawn(src, _TABLE_CONST[vocab])
            self.assertEqual(
                drawn - python, set(),
                f"{vocab}: drawn but not in data_quality.{const} — the chart "
                f"would offer a value the gate rejects")

    def test_every_term_has_a_real_definition(self):
        src = _js()
        gloss = _glossary(src)
        for vocab in _VOCABS:
            drawn = _drawn(src, _TABLE_CONST[vocab])
            missing = drawn - set(gloss[vocab])
            self.assertEqual(missing, set(),
                             f"{vocab}: no glossary line for {sorted(missing)}")
            for term, text in gloss[vocab].items():
                self.assertGreater(len(text), 24,
                                   f"{vocab}.{term}: definition too short")

    def test_the_band_palette_matches_python(self):
        """fauna.js mirrors BAND_COLOUR_HEX so the bench can draw a bee without
        a round trip. A drift here paints the wrong bee — which is worse than
        painting none, because it looks right."""
        from src.data_quality import BAND_COLOUR_HEX         # noqa: PLC0415
        m = re.search(r"var BAND_COLOUR_HEX = \{(.*?)\};", _js(), re.S)
        self.assertIsNotNone(m)
        js = dict(re.findall(r"(\w+):\s*'(#[0-9a-fA-F]{6})'", m.group(1)))
        self.assertEqual({k: v.lower() for k, v in js.items()},
                         {k: v.lower() for k, v in BAND_COLOUR_HEX.items()},
                         "fauna.js band palette has drifted from data_quality")


def _described(path):
    """Records that actually carry morphology.

    A row can exist for its `kind` alone — F127 added 46 such leps — and the
    3D scene falls back to `scene_wildlife`'s genus tables for those. The
    morphology guards below apply to what has been described, not to what
    exists.
    """
    return [r for r in _records(path)
            if (r.get("morph_data_source") or "").strip()]


class TestSeededData(unittest.TestCase):
    def test_the_described_roster_only_ever_grows(self):
        """Morphology is OPTIONAL and has a documented fallback.

        `src/scene_wildlife.py` says so at the top: appearance is data since
        schema v58, and its genus/name tables are "the fallback for a species
        nobody has described". So a lep row without a wingspan renders — it
        just renders generically.

        This used to pin 69 bees and 31 leps, the exact roster the bench was
        written against. F127 added 46 leps with a `kind` and no morphology,
        which is the intended shape and made an equality assertion fail. The
        invariant that matters is that the described set never SHRINKS —
        losing a description is rot; not having one yet is a backlog.
        """
        self.assertGreaterEqual(len(_described(_BEES)), 69)
        self.assertGreaterEqual(len(_described(_LEPS)), 31)

    def test_band_patterns_are_well_formed(self):
        from src.data_quality import (BAND_COLOURS,          # noqa: PLC0415
                                      BAND_SEGMENTS_MAX,
                                      band_pattern_tokens)
        for r in _described(_BEES):
            toks = band_pattern_tokens(r.get("band_pattern"))
            self.assertTrue(toks, f"{r['scientific_name']}: no band pattern")
            self.assertLessEqual(len(toks), BAND_SEGMENTS_MAX)
            for t in toks:
                self.assertIn(t, BAND_COLOURS,
                              f"{r['scientific_name']}: bad band colour {t!r}")

    def test_wingspans_are_ranges_the_right_way_round(self):
        """Only for rows that HAVE a wingspan — see
        test_the_described_roster_only_ever_grows. A row with none renders
        from the fallback tables; a row with a backwards one is a bug."""
        for r in _described(_LEPS):
            lo, hi = r.get("wingspan_min_mm"), r.get("wingspan_max_mm")
            self.assertIsNotNone(lo, f"{r['scientific_name']}: no wingspan")
            self.assertLessEqual(lo, hi, f"{r['scientific_name']}: backwards")

    def test_everything_is_marked_estimated(self):
        """The seeder's values are genus-level judgement, not measurements.
        If this ever fails it should be because somebody VERIFIED a species in
        the bench — in which case the citation must be there too, which
        validate_fauna_morphology enforces."""
        for path in (_BEES, _LEPS):
            for r in _described(path):
                src = (r.get("morph_data_source") or "").lower()
                self.assertIn(src, ("estimated", "photo", "flora", "measured"))
                if src != "estimated":
                    self.assertTrue((r.get("morph_data_citation") or "").strip(),
                                    f"{r['scientific_name']}: claimed {src} "
                                    f"with no citation")


class TestTheCollapseIsFixed(unittest.TestCase):
    """The whole reason for schema v58. Before it, appearance came from name
    substrings and 100 species shared 28 looks; if a refactor ever reconnects
    that path these numbers fall back and this fails."""

    def _appearances(self, taxon):
        import tempfile as _t                                # noqa: PLC0415
        os.environ.setdefault("XDG_DATA_HOME", _t.mkdtemp())
        from src.db import plants                            # noqa: PLC0415
        plants.init_db()
        from src.db.fauna import (bee_morphology,            # noqa: PLC0415
                                  lep_morphology, list_fauna)
        from src.scene_wildlife import _appearance_for       # noqa: PLC0415
        morph = bee_morphology() if taxon == "bee" else lep_morphology()
        seen = set()
        for row in list_fauna(taxon):
            app = _appearance_for(row, morph.get(row["id"]))
            seen.add(json.dumps(app, sort_keys=True))
        return len(seen)

    def test_bees_are_not_twelve_animals(self):
        n = self._appearances("bee")
        self.assertGreaterEqual(
            n, 25, f"69 bees collapsed into {n} appearances (was 12 before v58)")

    def test_every_lepidopteran_is_its_own_animal(self):
        n = self._appearances("lepidoptera")
        self.assertGreaterEqual(
            n, 30, f"31 lepidoptera collapsed into {n} appearances (was 16)")


class TestCommittedDiagrams(unittest.TestCase):
    def test_one_file_per_term(self):
        src = _js()
        for vocab in _VOCABS:
            for term in _drawn(src, _TABLE_CONST[vocab]):
                path = os.path.join(_DIAGRAM_DIR, f"{vocab}-{term}.svg")
                self.assertTrue(os.path.isfile(path),
                                f"{os.path.basename(path)} missing — run "
                                f"`node scripts/render_botany_diagrams.js`")

    def test_no_external_references(self):
        banned = re.compile(
            r"""https?://|['"]//[a-z0-9]|<image\b|@import""", re.I)
        for name in sorted(os.listdir(_DIAGRAM_DIR)):
            with open(os.path.join(_DIAGRAM_DIR, name), encoding="utf-8") as fh:
                body = fh.read().replace("http://www.w3.org/2000/svg", "")
            self.assertIsNone(banned.search(body), f"external ref in {name}")

    @unittest.skipIf(shutil.which("node") is None, "node not installed")
    def test_the_committed_files_match_the_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            staged = os.path.join(tmp, "repo")
            os.makedirs(os.path.join(staged, "html", "botany"))
            os.makedirs(os.path.join(staged, "scripts"))
            for f in ("diagrams.js", "fauna.js"):
                shutil.copy(os.path.join(_ROOT, "html", "botany", f),
                            os.path.join(staged, "html", "botany"))
            shutil.copy(os.path.join(_ROOT, "scripts",
                                     "render_botany_diagrams.js"),
                        os.path.join(staged, "scripts"))
            proc = subprocess.run(
                ["node", os.path.join(staged, "scripts",
                                      "render_botany_diagrams.js")],
                capture_output=True, text=True, timeout=60, encoding="utf-8")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            fresh = os.path.join(staged, "docs", "img", "fauna")
            stale = []
            for name in sorted(os.listdir(fresh)):
                with open(os.path.join(fresh, name), encoding="utf-8") as a, \
                     open(os.path.join(_DIAGRAM_DIR, name), encoding="utf-8") as b:
                    if a.read() != b.read():
                        stale.append(name)
            self.assertEqual(stale, [], "committed fauna diagrams are out of "
                                        "date — re-run the generator")


class TestBench(unittest.TestCase):
    def test_it_edits_both_taxa_and_nothing_else(self):
        """The bench covers every bee and lepidopteran in the catalogue.

        The count was pinned at 100 — the 69 bees and 31 leps that existed
        when the bench was written — and F127's 159 curated animals took it to
        225. A hard-coded total is a claim about the catalogue's size, which
        is not what this test is for; the invariant is that the bench edits
        those two taxa and nothing else, and that it edits ALL of them.
        """
        import json                                          # noqa: PLC0415
        import tune_fauna as bench                           # noqa: PLC0415
        rows = bench._species_list()
        self.assertEqual({r["taxon"] for r in rows}, {"bee", "lepidoptera"})
        # Counted from the shipped JSON, not the DB: this module redirects the
        # database to an empty temp dir, so a query here raises "no such table"
        # rather than measuring anything.
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "data", "fauna_master.json"),
                  encoding="utf-8") as fh:
            expected = sum(1 for r in json.load(fh)
                           if isinstance(r, dict)
                           and r.get("taxon") in ("bee", "lepidoptera"))
        self.assertEqual(len(rows), expected,
                         "the bench must reach every bee and lep, not a "
                         "snapshot of how many there once were")

    def test_vocabularies_come_from_the_gate(self):
        import tune_fauna as bench                           # noqa: PLC0415
        from src import data_quality                         # noqa: PLC0415
        for field, const in (("build", "BEE_BUILDS"),
                             ("wing_shape", "WING_SHAPES"),
                             ("flight_style", "FLIGHT_STYLES")):
            self.assertEqual(set(bench.VOCABULARIES[field]),
                             set(getattr(data_quality, const)),
                             f"{field} drifted from data_quality.{const}")

    def test_the_html_carries_no_copy_of_a_vocabulary(self):
        """The regression this guards: hand-typed <option> lists going stale,
        which is how the V2.35 photo-slot list drifted."""
        with open(os.path.join(_ROOT, "html", "tune_fauna.html"),
                  encoding="utf-8") as fh:
            html = fh.read()
        for field in ("build", "wing_shape", "wing_pattern", "flight_style",
                      "resting_posture", "scopa_position", "wing_tint"):
            m = re.search(rf'<select id="{field}">(.*?)</select>', html, re.S)
            self.assertIsNotNone(m, f"no <select> for {field}")
            self.assertNotIn("<option", m.group(1),
                             f"{field} has hand-typed options — fill it from "
                             f"/api/vocab instead")


if __name__ == "__main__":
    unittest.main()
