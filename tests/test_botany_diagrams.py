"""
tests/test_botany_diagrams.py — the drawn vocabulary stays in step (V2.36).

`html/botany/diagrams.js` draws all 33 terms of the three shape vocabularies,
and three things then depend on it: the bench's dropdowns, the bench's
comparison chart, and the 33 committed SVGs that docs/BOTANY_FIELD_GUIDE.md
references as images.

Every failure mode here is SILENT, which is why this file is long-winded:

  * a term added to `src/data_quality.py` with no drawing renders an empty box
    beside the dropdown — no error, just a control that stopped helping;
  * a term drawn here but removed from the Python set puts a value in the chart
    that the data-quality gate will later reject;
  * a glossary line missing for a term produces a diagram with no caption;
  * a stale `docs/img/botany/*.svg` shows the reader a chart that disagrees
    with the bench, which for a reference chart is worse than having none.

Deliberately node-free for everything that can be: the assertions parse the JS
as text. Only the regeneration check needs `node`, and it skips without it
rather than failing on a machine that has no Node installed.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

_JS = os.path.join(_ROOT, "html", "botany", "diagrams.js")
_DIAGRAM_DIR = os.path.join(_ROOT, "docs", "img", "botany")
_GUIDE = os.path.join(_ROOT, "docs", "BOTANY_FIELD_GUIDE.md")

# vocabulary name in diagrams.js -> the set in src/data_quality.py
_VOCABS = {
    "flower_arch": "FLOWER_ARCHITECTURES",
    "leaf_shape": "LEAF_SHAPES",
    "leaf_arrangement": "LEAF_ARRANGEMENTS",
}


def _js() -> str:
    with open(_JS, encoding="utf-8") as fh:
        return fh.read()


def _order(src: str, const: str) -> list:
    """The ordered term list out of a `var NAME_ORDER = [...]` literal."""
    m = re.search(rf"var {const} = \[(.*?)\];", src, re.S)
    assert m, f"{const} not found in diagrams.js"
    return re.findall(r"'([a-z_]+)'", m.group(1))


def _drawn(src: str, table: str) -> set:
    """The keys of a `var NAME = {...}` drawing table. Matches only top-level
    `  key: function` entries so nested helpers are not counted."""
    m = re.search(rf"\nvar {table} = \{{\n(.*?)\n\}};", src, re.S)
    assert m, f"{table} not found in diagrams.js"
    # `\s*` after the colon: the one-line shapes align their `function` keyword
    # into a column, so several have more than one space there.
    return set(re.findall(r"^  (\w+):\s*function", m.group(1), re.M))


def _glossary(src: str) -> dict:
    m = re.search(r"var BOTANY_GLOSSARY = \{(.*?)\n\};", src, re.S)
    assert m, "BOTANY_GLOSSARY not found"
    out = {}
    for vocab in _VOCABS:
        block = re.search(rf"\n  {vocab}: \{{(.*?)\n  \}}", m.group(1), re.S)
        assert block, f"no glossary block for {vocab}"
        out[vocab] = dict(re.findall(r"^    (\w+): '(.*?)',?$",
                                     block.group(1), re.M))
    return out


_ORDER_CONST = {
    "flower_arch": "FLOWER_ARCH_ORDER",
    "leaf_shape": "LEAF_SHAPE_ORDER",
    "leaf_arrangement": "LEAF_ARRANGEMENT_ORDER",
}
_TABLE_CONST = {
    "flower_arch": "ARCHITECTURES",
    "leaf_shape": "LEAF_SHAPES",
    "leaf_arrangement": "ARRANGEMENTS",
}


class TestVocabulariesAgree(unittest.TestCase):
    """The JS lists and the Python sets are the same 33 words."""

    def test_every_python_term_is_drawn(self):
        from src import data_quality                         # noqa: PLC0415
        src = _js()
        for vocab, const in _VOCABS.items():
            python = set(getattr(data_quality, const))
            drawn = _drawn(src, _TABLE_CONST[vocab])
            self.assertEqual(
                python - drawn, set(),
                f"{vocab}: in data_quality.{const} but not drawn in "
                f"diagrams.js — renders as an empty box beside the dropdown")

    def test_no_term_is_drawn_that_python_does_not_allow(self):
        from src import data_quality                         # noqa: PLC0415
        src = _js()
        for vocab, const in _VOCABS.items():
            python = set(getattr(data_quality, const))
            drawn = _drawn(src, _TABLE_CONST[vocab])
            self.assertEqual(
                drawn - python, set(),
                f"{vocab}: drawn in diagrams.js but not in "
                f"data_quality.{const} — the chart would offer a value the "
                f"data-quality gate rejects")

    def test_the_display_order_covers_every_term_exactly_once(self):
        src = _js()
        for vocab in _VOCABS:
            order = _order(src, _ORDER_CONST[vocab])
            drawn = _drawn(src, _TABLE_CONST[vocab])
            self.assertEqual(len(order), len(set(order)),
                             f"{vocab}: a term appears twice in the order")
            self.assertEqual(set(order), drawn,
                             f"{vocab}: the ordered list and the drawing table "
                             f"disagree — botanyTerms() drives the chart, so a "
                             f"term missing here is invisible in the UI")


class TestGlossary(unittest.TestCase):
    def test_every_term_has_a_definition(self):
        src = _js()
        gloss = _glossary(src)
        for vocab in _VOCABS:
            drawn = _drawn(src, _TABLE_CONST[vocab])
            missing = drawn - set(gloss[vocab])
            self.assertEqual(missing, set(),
                             f"{vocab}: no glossary line for {sorted(missing)} "
                             f"— the chart cell would have a blank caption")

    def test_definitions_are_not_placeholders(self):
        """A one-word definition is not one. These get read by somebody holding
        a plant, trying to decide."""
        for vocab, terms in _glossary(_js()).items():
            for term, text in terms.items():
                self.assertGreater(
                    len(text), 24,
                    f"{vocab}.{term}: definition is too short to be useful")


class TestNoExternalReferences(unittest.TestCase):
    """Nothing may reach off-host. The published-artifact CSP forbids it, the
    frozen build has no network, and a diagram that needs to fetch something is
    a diagram that will one day be blank."""

    # A protocol-relative URL only counts inside a string literal — a bare `//`
    # is the comment marker and appears all over the file.
    _BANNED = re.compile(
        r"""https?://|['"]//[a-z0-9]|<image\b|url\(\s*['"]?(?!\#)|@import"""
        r"""|xlink:href\s*=\s*['"](?!\#)""",
        re.I)

    def test_the_source_pulls_nothing_in(self):
        for line in _js().splitlines():
            if line.lstrip().startswith(("*", "//", "/*")):
                continue                     # prose and doc links are fine
            # the SVG namespace is an identifier, not a fetch
            probe = line.replace("http://www.w3.org/2000/svg", "")
            self.assertIsNone(self._BANNED.search(probe),
                              f"external reference in diagrams.js: {line!r}")

    def test_the_committed_diagrams_pull_nothing_in(self):
        for name in sorted(os.listdir(_DIAGRAM_DIR)):
            with open(os.path.join(_DIAGRAM_DIR, name), encoding="utf-8") as fh:
                body = fh.read().replace("http://www.w3.org/2000/svg", "")
            self.assertIsNone(self._BANNED.search(body),
                              f"external reference in {name}")


class TestCommittedDiagrams(unittest.TestCase):
    """docs/BOTANY_FIELD_GUIDE.md references these by filename."""

    def test_one_file_per_term(self):
        src = _js()
        for vocab in _VOCABS:
            for term in _drawn(src, _TABLE_CONST[vocab]):
                path = os.path.join(_DIAGRAM_DIR, f"{vocab}-{term}.svg")
                self.assertTrue(
                    os.path.isfile(path),
                    f"{os.path.basename(path)} missing — run "
                    f"`node scripts/render_botany_diagrams.js`")

    def test_no_orphans(self):
        src = _js()
        want = {f"{v}-{t}.svg" for v in _VOCABS
                for t in _drawn(src, _TABLE_CONST[v])}
        have = {n for n in os.listdir(_DIAGRAM_DIR) if n.endswith(".svg")}
        self.assertEqual(have - want, set(),
                         "diagrams for terms that no longer exist")

    def test_the_guide_references_every_one(self):
        with open(_GUIDE, encoding="utf-8") as fh:
            doc = fh.read()
        refs = set(re.findall(r'src="img/botany/([^"]+\.svg)"', doc))
        have = {n for n in os.listdir(_DIAGRAM_DIR) if n.endswith(".svg")}
        self.assertEqual(
            have - refs, set(),
            "a diagram exists that the field guide never shows")
        self.assertEqual(
            refs - have, set(),
            "the field guide references a diagram that is not committed")

    @unittest.skipIf(shutil.which("node") is None, "node not installed")
    def test_the_committed_files_match_the_source(self):
        """Regenerate into a temp tree and diff. Catches the case where a
        drawing was corrected but `render_botany_diagrams.js` was never re-run,
        which would leave the documentation quietly disagreeing with the app."""
        with tempfile.TemporaryDirectory() as tmp:
            staged = os.path.join(tmp, "repo")
            os.makedirs(os.path.join(staged, "html", "botany"))
            os.makedirs(os.path.join(staged, "scripts"))
            # BOTH vocabulary modules: one generator emits the botanical and
            # the fauna diagrams (V2.36) and loads both files, so staging only
            # this one leaves it dying on a missing fauna.js.
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
            fresh_dir = os.path.join(staged, "docs", "img", "botany")
            stale = []
            for name in sorted(os.listdir(fresh_dir)):
                with open(os.path.join(fresh_dir, name), encoding="utf-8") as a:
                    fresh = a.read()
                with open(os.path.join(_DIAGRAM_DIR, name), encoding="utf-8") as b:
                    if b.read() != fresh:
                        stale.append(name)
            self.assertEqual(
                stale, [],
                "committed diagrams are out of date — run "
                "`node scripts/render_botany_diagrams.js`")


if __name__ == "__main__":
    unittest.main()
