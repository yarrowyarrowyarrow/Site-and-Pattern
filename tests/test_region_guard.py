"""
tests/test_region_guard.py — what is true of one place lives in its pack
(V3.24, ED-11; docs/homeowner/08-edmonton-edition.md §4.9).

Three checks over ``src/``, each growing with every pack in
``region.regions()``:

1. **No module names a pack's place.** Name tokens and non-docstring string
   tokens matching a pack's ``short`` ("Edmonton"), case-insensitive.
2. **No pack coordinates in code.** A numeric literal within 0.01° of a
   pack's area or map centre, in ``src/`` and in ``html/map/*.js`` (comments
   stripped), except the map page's cold-load fallback, which
   ``test_region_packs`` keeps equal to the default pack.
3. **No literal ``native_near`` value.** ``native_near`` given a string
   literal anywhere in ``src/``.

Part 08 expected 188 lines in 26 files on the first check until ED-6 to ED-9
(increment 8) move climate, address search, coverage and nativity onto the
region, so each check is a **ratchet**, as ``tests/test_vocabulary.py`` is:
:data:`KNOWN` holds today's count per file; a higher count fails, and a lower
one fails until the number is written in, so the list only shrinks.
"""

import ast
import io
import os
import re
import sys
import tokenize
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import region  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

#: Files allowed to name a place, with the reason (§4.8).
ALLOWED = {
    "region.py": "the region layer itself",
    "terrain.py": "the City of Edmonton contour dataset",
    "terrain_store.py": "the edmonton_tiles table in users' terrain.db",
    "terrain_downloader.py": "the City of Edmonton contour dataset",
    "services.py": "the City of Edmonton's open data, credited by name",
    "db/polycultures.py": "seeded community names, pending E9",
    "ecoregion_basemap.py": "the basemap's city dots",
    "vocabulary.py": "the glossary's own words (09-words.md §2)",
}
#: Website text is a separate product, frozen by the owner's G5.
ALLOWED_PREFIXES = ("static_site", "site_facet")

#: Today's counts, ``{(check, file): n}``. Increment 8 (ED-6 to ED-9) and the
#: words (WD-2 to WD-6) take these out.
KNOWN = {
    ('coordinates', 'solar.py'): 1,       # frost-date presets: ED-6
    ('place', 'climate.py'): 1,           # the normals' station: ED-6
    ('place', 'native_here.py'): 6,       # the EDMONTON constant's name
    ('place', 'site_panel.py'): 2,        # the City's LiDAR dataset, named
}


def _skip(name: str) -> bool:
    return name in ALLOWED or name.startswith(ALLOWED_PREFIXES)


def _docstrings(tree) -> set:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(
                    getattr(first, "value", None), ast.Constant):
                out.add(first.value.lineno)
    return out


_FSTART = getattr(tokenize, "FSTRING_START", None)
_FEND = getattr(tokenize, "FSTRING_END", None)


def _tokens(text: str):
    """``(type, string, start line)`` with every f-string as ONE string token,
    as Python 3.11 gives it (CI's version). From 3.12 an f-string is split into
    FSTRING_START / MIDDLE / END with its expressions as ordinary tokens, and
    the guard counted differently by version: V3.24 passed here on 3.13 and
    failed on CI (V3.25)."""
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln))

    def at(pos):
        return offsets[pos[0] - 1] + pos[1]
    depth, start = 0, None
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if _FSTART is not None and tok.type == _FSTART:
            if depth == 0:
                start = tok.start
            depth += 1
            continue
        if _FEND is not None and tok.type == _FEND:
            depth -= 1
            if depth == 0:
                yield tokenize.STRING, text[at(start):at(tok.end)], start[0]
            continue
        if depth:
            continue
        yield tok.type, tok.string, tok.start[0]


def place_hits(path: Path, shorts) -> int:
    """Name and string tokens (no docstrings, no comments) naming a pack."""
    text = path.read_text(encoding="utf-8")
    docs = _docstrings(ast.parse(text))
    pats = [re.compile(rf"\b{re.escape(s)}\b", re.I) for s in shorts]
    n = 0
    for kind, string, line in _tokens(text):
        if kind == tokenize.STRING and line in docs:
            continue
        if kind in (tokenize.NAME, tokenize.STRING) and any(
                p.search(string) for p in pats):
            n += 1
    return n


def coordinate_hits(text: str, centres) -> int:
    """Numeric literals within 0.01° of a pack centre's latitude or
    longitude."""
    n = 0
    for m in re.finditer(r"(?<![\w.])-?\d+\.\d+", text):
        v = float(m.group(0))
        if any(abs(v - c) < 0.01 for lat, lng in centres for c in (lat, lng)):
            n += 1
    return n


def _strip_js_comments(js: str) -> str:
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(?m)//.*$", "", js)


def _python_code_only(path: Path) -> str:
    """The module's tokens without comments and docstrings, so a number in
    prose is not counted."""
    text = path.read_text(encoding="utf-8")
    docs = _docstrings(ast.parse(text))
    keep = []
    for kind, string, line in _tokens(text):
        if kind == tokenize.COMMENT:
            continue
        if kind == tokenize.STRING and line in docs:
            continue
        keep.append(string)
    return " ".join(keep)


def literal_native_near(path: Path) -> int:
    """``native_near`` given a string literal: a keyword, a dict key's value,
    an assignment or a comparison."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "native_near" \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str) and node.value.value:
            n += 1
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "native_near" \
                        and isinstance(v, ast.Constant) \
                        and isinstance(v.value, str) and v.value:
                    n += 1
    return n


def counts() -> Counter:
    packs = region.regions().values()
    shorts = [p.short for p in packs]
    centres = {tuple(p.centre) for p in packs} | {
        tuple(p.map["centre"]) for p in packs}
    out = Counter()
    for path in sorted(SRC.rglob("*.py")):
        name = path.relative_to(SRC).as_posix()
        if _skip(name):
            continue
        if (n := place_hits(path, shorts)):
            out[("place", name)] += n
        if (n := coordinate_hits(_python_code_only(path), centres)):
            out[("coordinates", name)] += n
        if (n := literal_native_near(path)):
            out[("native_near", name)] += n
    for path in sorted((ROOT / "html" / "map").glob("*.js")):
        if path.name == "01-core.js":       # the cold-load fallback
            continue
        js = _strip_js_comments(path.read_text(encoding="utf-8"))
        if (n := coordinate_hits(js, centres)):
            out[("coordinates", f"html/map/{path.name}")] += n
    return out


class WhatIsTrueOfAPlaceLivesInItsPack(unittest.TestCase):

    def test_no_new_place_names_coordinates_or_literal_lists(self):
        found = counts()
        known = {k: v for k, v in KNOWN.items() if v}
        new = {k: n for k, n in found.items() if n > known.get(k, 0)}
        fewer = {k: n for k, n in found.items() if n < known.get(k, 0)}
        fewer.update({k: 0 for k in known if k not in found})
        self.assertEqual(new, {}, "a place's name, coordinates or list in "
                                  "code: read it from src/region.py")
        self.assertEqual(fewer, {}, "fewer than KNOWN: write the new counts "
                                    "in, so the list shrinks")

    def test_the_guard_grows_with_each_pack(self):
        """A second pack's name is caught with no change here."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.py"
            p.write_text('LABEL = "Calgary natives only"\n', encoding="utf-8")
            self.assertEqual(place_hits(p, ["Edmonton"]), 0)
            self.assertEqual(place_hits(p, ["Edmonton", "Calgary"]), 1)

    def test_an_f_string_counts_once_on_every_python(self):
        """CI runs 3.11, sessions 3.13: one count for one f-string."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.py"
            p.write_text('X = f"In Edmonton, {n} plants near Edmonton"\n'
                         'Y = f"{EDMONTON}"\n', encoding="utf-8")
            self.assertEqual(place_hits(p, ["Edmonton"]), 2)

    def test_docstrings_and_comments_do_not_count(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.py"
            p.write_text('"""About Edmonton."""\n# Edmonton\nX = 1\n',
                         encoding="utf-8")
            self.assertEqual(place_hits(p, ["Edmonton"]), 0)

    def test_a_literal_list_is_caught(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.py"
            p.write_text('f(native_near="edmonton")\nD = {"native_near": "x"}\n'
                         'g(native_near=key)\n', encoding="utf-8")
            self.assertEqual(literal_native_near(p), 2)


if __name__ == "__main__":
    print(dict(sorted(counts().items())))
