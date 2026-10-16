"""
tests/test_vocabulary.py — the glossary as a test (V3.21, WD-1;
docs/homeowner/09-words.md §2, the owner's W1).

Every prose string in ``src/`` (a string constant with a space in it, read
with ``ast``: not a docstring, not a log call, not SQL) is read for the
glossary's *Never* words, and every prose string in the modules that build
the simple app for its *Advanced only* words.

The rewrites are WD-2 to WD-6, increment by increment, so this is a ratchet,
as ``data_quality.KNOWN_NOMENCLATURE`` is: :data:`KNOWN` holds today's count
per module and word. A count above it is a new use and fails; a count below it
also fails, with the number to write in, so the list only ever shrinks.
"""

import ast
import os
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import vocabulary  # noqa: E402

_SRC = Path(__file__).resolve().parent.parent / "src"

#: Modules whose words no homeowner reads, with the reason.
EXEMPT = {
    "data_quality.py": "the catalogue's data gate, for the maintainer",
    "cli.py": "the command line, out of the product (part 03 §4)",
    "mcp_server.py": "Claude's way into the app, out of the product",
    "permadesign_api.py": "the scripting facade, out of the product",
    "llm_design.py": "the AI prompts and their errors; the AI leaves the "
                     "app in RM-3",
    "vocabulary.py": "the glossary itself",
}

#: Module-name prefixes exempt the same way: the website is a separate
#: product (grownativeplants.ca), frozen by the owner's G5.
EXEMPT_PREFIXES = ("static_site",)

#: The modules that build what the simple app shows (09 §2: "the Advanced
#: column only in the modules that build simple surfaces"), grown as the
#: rewrites land.
SIMPLE_MODULES = (
    "first_step_bar.py", "onboarding.py", "start_screen.py",
    "structure_panel.py", "share_panel.py", "community_page.py",
    "species_page.py", "plant_filters.py", "filter_area.py",
    "placement_bar.py", "landing_check.py", "plain_messages.py",
    "month_tasks.py", "advanced_tools_flow.py", "start_flow.py",
)

#: Today's uses, ``{(module, word): count}``: WD-2 to WD-6 take these out.
KNOWN = {
    ('analysis_panel.py', 'AB retail estimate'): 1,
    ('app.py', '.perma.geojson'): 1,
    ('controllers/map_events.py', 'polyculture'): 1,
    ('controllers/persistence.py', '.perma.geojson'): 1,
    ('controllers/persistence.py', 'polyculture'): 2,
    ('db/polycultures.py', 'Alberta native'): 2,
    ('db/polycultures.py', 'guild'): 18,
    ('db/polycultures.py', 'polyculture'): 6,
    ('design_critic.py', 'Alberta native'): 1,
    ('design_goals.py', 'pet friendly'): 2,
    ('feedback_flow.py', 'project'): 1,
    ('landing_check.py', 'boundary'): 3,
    ('occurrence_points.py', 'project'): 2,
    ('onboarding.py', 'boundary'): 1,
    ('onboarding.py', 'forb'): 1,
    ('plant_filters.py', 'canopy'): 1,
    ('plant_filters.py', 'early successional'): 1,
    ('plant_filters.py', 'keystone'): 1,
    ('plant_filters.py', 'larval host'): 1,
    ('plant_filters.py', 'species'): 3,
    ('plant_filters.py', 'toxicity'): 2,
    ('polyculture.py', 'polyculture'): 1,
    ('range_map.py', 'spec'): 1,
    ('saves.py', 'project'): 1,
    ('site_panel.py', 'project'): 1,
    ('species_page.py', 'species'): 3,
}

_SQL = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|"
                  r"PRAGMA|WITH)\b|\bFROM\b.*\bWHERE\b", re.I)
_LOG = {"debug", "info", "warning", "error", "exception", "critical", "log"}


def prose(path: Path):
    """The prose string constants of one module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(
                    getattr(first, "value", None), ast.Constant):
                skip.add(id(first.value))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in _LOG):
            skip.update(id(n) for n in ast.walk(node))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in skip and " " in node.value.strip()
                and not _SQL.search(node.value)):
            yield node.value


def _pattern(word: str):
    return re.compile(r"(?<![\w.])" + re.escape(word) + r"(?:s|es)?(?!\w)",
                      re.I)


def counts() -> Counter:
    """``{(module, word): n}`` over the tree, as the test reads it."""
    never = [(w, _pattern(w)) for w in vocabulary.NEVER]
    advanced = [(w, _pattern(w)) for w in vocabulary.ADVANCED_ONLY]
    out = Counter()
    for path in sorted(_SRC.rglob("*.py")):
        name = str(path.relative_to(_SRC))
        if name in EXEMPT or name.startswith(EXEMPT_PREFIXES):
            continue
        words = never + (advanced if name in SIMPLE_MODULES else [])
        for text in prose(path):
            for word, pat in words:
                if pat.search(text):
                    out[(name, word)] += 1
    return out


class TheGlossaryHolds(unittest.TestCase):

    def test_the_table_is_what_09_says(self):
        self.assertIn("polyculture", vocabulary.NEVER)
        self.assertIn("pioneer", vocabulary.NEVER)
        self.assertIn("species", vocabulary.ADVANCED_ONLY)
        self.assertIn("boundary", vocabulary.ADVANCED_ONLY)
        self.assertFalse(set(vocabulary.NEVER) & set(vocabulary.ADVANCED_ONLY))

    def test_every_module_named_exists(self):
        for name in tuple(EXEMPT) + SIMPLE_MODULES:
            self.assertTrue((_SRC / name).exists(), name)

    def test_no_new_word_and_no_stale_count(self):
        found = counts()
        new = {k: n for k, n in found.items() if n > KNOWN.get(k, 0)}
        fewer = {k: n for k, n in found.items() if n < KNOWN.get(k, 0)}
        fewer.update({k: 0 for k in KNOWN if k not in found})
        self.assertEqual(new, {}, "words the glossary keeps out of this text "
                                  "(docs/homeowner/09-words.md §2)")
        self.assertEqual(fewer, {}, "fewer than KNOWN: write the new counts "
                                    "in, so the list shrinks")


if __name__ == "__main__":
    print(dict(sorted(counts().items())))
