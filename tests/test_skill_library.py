"""
tests/test_skill_library.py — keep the .claude/skills library honest.

The skill library (V2.19) is the project's institutional memory: procedural
playbooks that let a fresh session — human or model — debug, extend, and
release this project without a senior engineer in the room. Like
test_architecture_guard.py and test_philosophy.py, this test freezes the
contract so the library can't silently rot:

  1. Every expected skill exists and has a well-formed SKILL.md
     (frontmatter ``name`` matching its directory, a non-empty
     ``description`` that says when to use it).
  2. Every backticked repo-relative path mentioned in a skill body points
     at a file or directory that actually exists — a refactor that moves
     or deletes a module must update the skills that reference it.
     (Placeholder paths use angle brackets, e.g. ``src/db/<module>.py``,
     and glob examples use ``*`` — both are exempt.)
  3. The library index (.claude/skills/README.md) mentions every skill,
     so the router can't drift from the shelves.

Pure file reads — no Qt, no DB.
"""

import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SKILLS = _ROOT / ".claude" / "skills"

# Lost-skill guard: additions are free, deletions/renames must be deliberate
# edits here (same discipline as the EXPECTED_* maps in
# test_architecture_guard.py).
EXPECTED_SKILLS = {
    # data layer
    "schema-change", "seed-data", "offline-packs", "external-data",
    # architecture
    "codebase-map", "add-feature", "placed-plants", "agent-api",
    # frontend / geo / 3D
    "map-frontend", "geo-projection", "scene-3d",
    # quality
    "testing", "debugging", "verify", "run",
    # process
    "start-work", "philosophy-check", "release-packaging",
}

# Backticked tokens that look like repo paths. Anchored to the top-level
# dirs/files skills legitimately reference; ``:symbol`` suffixes are split
# off before the existence check.
_PATH_RE = re.compile(
    r"`((?:src|docs|data|tests|html|scripts|examples|web3d|\.claude|\.github)"
    r"/[^`\s]+|main\.py|CLAUDE\.md|README\.md|INSTALL\.md|pyproject\.toml|"
    r"requirements(?:-optional)?\.txt)`"
)

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _skill_dirs():
    return sorted(p for p in _SKILLS.iterdir()
                  if p.is_dir() and not p.name.startswith("."))


def _frontmatter(text: str) -> dict:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fields = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if km:
            fields[km.group(1)] = km.group(2).strip().strip("'\"")
    return fields


class TestLibraryShape(unittest.TestCase):
    def test_skills_dir_exists(self):
        self.assertTrue(_SKILLS.is_dir(), ".claude/skills/ is missing")

    def test_expected_skills_present(self):
        present = {p.name for p in _skill_dirs()}
        missing = EXPECTED_SKILLS - present
        self.assertFalse(
            missing,
            f"skill(s) disappeared from .claude/skills/: {sorted(missing)} — "
            f"restore them or deliberately update EXPECTED_SKILLS.",
        )

    def test_every_skill_has_skill_md(self):
        offenders = [p.name for p in _skill_dirs()
                     if not (p / "SKILL.md").is_file()]
        self.assertFalse(offenders,
                         f"skill dirs without SKILL.md: {offenders}")


class TestFrontmatter(unittest.TestCase):
    def test_name_matches_directory(self):
        offenders = []
        for d in _skill_dirs():
            md = d / "SKILL.md"
            if not md.is_file():
                continue
            fields = _frontmatter(md.read_text(encoding="utf-8"))
            if not fields:
                offenders.append(f"{d.name}: no YAML frontmatter block")
            elif fields.get("name") != d.name:
                offenders.append(
                    f"{d.name}: frontmatter name {fields.get('name')!r} "
                    f"!= directory name")
        self.assertFalse(offenders, "\n".join(offenders))

    def test_description_present_and_bounded(self):
        offenders = []
        for d in _skill_dirs():
            md = d / "SKILL.md"
            if not md.is_file():
                continue
            fields = _frontmatter(md.read_text(encoding="utf-8"))
            desc = fields.get("description", "")
            if len(desc) < 40:
                offenders.append(
                    f"{d.name}: description missing or too thin to trigger "
                    f"on ({len(desc)} chars)")
            elif len(desc) > 1024:
                offenders.append(
                    f"{d.name}: description over 1024 chars ({len(desc)})")
        self.assertFalse(offenders, "\n".join(offenders))


class TestPathsResolve(unittest.TestCase):
    """A skill that points at a moved/deleted file is worse than no skill."""

    def test_backticked_paths_exist(self):
        offenders = []
        for d in _skill_dirs():
            for md in sorted(d.glob("*.md")):
                text = md.read_text(encoding="utf-8")
                for token in _PATH_RE.findall(text):
                    if "<" in token or "*" in token or "..." in token:
                        continue  # placeholder / glob examples
                    path_part = token.split(":", 1)[0].rstrip("/")
                    if not (_ROOT / path_part).exists():
                        offenders.append(
                            f"{md.relative_to(_ROOT)}: `{token}` does not "
                            f"exist")
        self.assertFalse(
            offenders,
            "dead path reference(s) in skill docs — update the skill(s) to "
            "match the tree:\n" + "\n".join(offenders),
        )


class TestIndex(unittest.TestCase):
    def test_readme_lists_every_skill(self):
        readme = _SKILLS / "README.md"
        self.assertTrue(readme.is_file(), ".claude/skills/README.md missing")
        text = readme.read_text(encoding="utf-8")
        unlisted = [p.name for p in _skill_dirs() if p.name not in text]
        self.assertFalse(
            unlisted,
            f".claude/skills/README.md does not mention: {unlisted}",
        )


if __name__ == "__main__":
    unittest.main()
