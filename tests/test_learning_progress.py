"""
tests/test_learning_progress.py — keep the learning curriculum honest.

The curriculum (docs/learning/) is a lesson-by-lesson self-study path with
a master checklist (docs/learning/PROGRESS.md) and a terminal progress
renderer (scripts/learning_progress.py). Same discipline as the other
guard tests — the contract is a test:

  1. Every lesson in the phase files appears in PROGRESS.md with the same
     title, and vice versa — the checklist can't silently drift from the
     curriculum (ticked/unticked state is the learner's business and is
     ignored).
  2. Every lesson states its Purpose, Aim, Steps and "Done when" — the
     promise the curriculum makes (each lesson has a purpose and an aim).
  3. The renderer's parsing, percentage and next-lesson logic work.

The learner's free-form journal (docs/learning/journal.md) is deliberately
NOT checked. Pure file reads — no Qt, no DB, no network.
"""

from __future__ import annotations

import os
import re
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LEARN = os.path.join(_ROOT, "docs", "learning")

sys.path.insert(0, os.path.join(_ROOT, "scripts"))
import learning_progress  # noqa: E402

# Lesson headings in the phase files: "### L1.3 — Title"
_HEADING_RE = re.compile(r"^### (L\d+\.\d+) — (.+?)\s*$", re.MULTILINE)


def _phase_files():
    names = sorted(n for n in os.listdir(_LEARN)
                   if re.match(r"phase-\d+-.*\.md$", n))
    return [os.path.join(_LEARN, n) for n in names]


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _curriculum_lessons():
    """[(lesson_id, title)] from the phase files, in file/lesson order."""
    lessons = []
    for path in _phase_files():
        lessons.extend(_HEADING_RE.findall(_read(path)))
    return lessons


def _checklist_lessons():
    """[(lesson_id, title)] from PROGRESS.md, tick state ignored."""
    phases = learning_progress.parse_progress(
        _read(os.path.join(_LEARN, "PROGRESS.md")))
    return [(lid, title) for _n, _t, ls in phases for lid, title, _d in ls]


class TestChecklistMatchesCurriculum(unittest.TestCase):
    """PROGRESS.md and the phase files describe the same lessons."""

    def test_phase_files_exist(self):
        self.assertEqual(len(_phase_files()), 6,
                         "expected one phase-N-*.md per phase (0-5)")

    def test_same_lessons_same_titles_same_order(self):
        curriculum = _curriculum_lessons()
        checklist = _checklist_lessons()
        self.assertTrue(curriculum, "no lesson headings found in phase files")
        self.assertEqual(
            curriculum, checklist,
            "docs/learning/PROGRESS.md is out of sync with the phase files "
            "(a lesson was added/renamed/reordered on one side only)")

    def test_lesson_ids_match_their_phase_file(self):
        for path in _phase_files():
            phase_num = re.search(r"phase-(\d+)-", os.path.basename(path)).group(1)
            for lesson_id, _title in _HEADING_RE.findall(_read(path)):
                self.assertTrue(
                    lesson_id.startswith(f"L{phase_num}."),
                    f"{os.path.basename(path)} contains {lesson_id}, which "
                    f"belongs to another phase")


class TestEveryLessonKeepsThePromise(unittest.TestCase):
    """Each lesson block states Purpose, Aim, Steps and Done-when."""

    def test_lesson_blocks_have_required_fields(self):
        required = ("**Purpose:**", "**Aim:**", "**Steps:**", "**Done when:**")
        for path in _phase_files():
            text = _read(path)
            # Split at lesson headings; the chunk after each heading (up to
            # the next heading) is that lesson's block.
            parts = _HEADING_RE.split(text)
            # parts = [preamble, id, title, block, id, title, block, ...]
            for i in range(1, len(parts), 3):
                lesson_id, block = parts[i], parts[i + 2]
                for field in required:
                    self.assertIn(
                        field, block,
                        f"{lesson_id} in {os.path.basename(path)} is missing "
                        f"its {field} — every lesson states its purpose, aim, "
                        f"steps and finish line")


class TestRenderer(unittest.TestCase):
    """parse/next/render logic of scripts/learning_progress.py."""

    _FIXTURE = (
        "# Learning Progress\n"
        "\n"
        "## Phase 0 — Warm up\n"
        "\n"
        "- [x] **L0.1** — First steps\n"
        "- [X] **L0.2** — Second steps\n"
        "- [ ] **L0.3** — Third steps\n"
        "\n"
        "## Phase 1 — Real work\n"
        "\n"
        "- [ ] **L1.1** — Begin\n"
    )

    def test_parse(self):
        phases = learning_progress.parse_progress(self._FIXTURE)
        self.assertEqual(len(phases), 2)
        num, title, lessons = phases[0]
        self.assertEqual((num, title), (0, "Warm up"))
        self.assertEqual([d for _i, _t, d in lessons], [True, True, False])
        self.assertEqual(lessons[0], ("L0.1", "First steps", True))

    def test_next_lesson(self):
        phases = learning_progress.parse_progress(self._FIXTURE)
        self.assertEqual(learning_progress.next_lesson(phases),
                         ("L0.3", "Third steps"))
        all_done = learning_progress.parse_progress(
            self._FIXTURE.replace("[ ]", "[x]"))
        self.assertIsNone(learning_progress.next_lesson(all_done))

    def test_render_counts_and_ascii_mode(self):
        phases = learning_progress.parse_progress(self._FIXTURE)
        for unicode_ok in (True, False):
            out = learning_progress.render(phases, unicode_ok=unicode_ok)
            self.assertIn("2/3", out)
            self.assertIn("0/1", out)
            self.assertIn("2/4", out)   # overall
            self.assertIn("50%", out)   # overall percentage
            self.assertIn("Next up: L0.3 — Third steps", out)
        ascii_out = learning_progress.render(phases, unicode_ok=False)
        self.assertNotIn("█", ascii_out)

    def test_render_real_checklist(self):
        # The real PROGRESS.md parses and renders regardless of how many
        # boxes the learner has ticked.
        phases = learning_progress.parse_progress(
            _read(os.path.join(_LEARN, "PROGRESS.md")))
        out = learning_progress.render(phases)
        self.assertIn("Overall", out)
        self.assertEqual(len(phases), 6)


if __name__ == "__main__":
    unittest.main()
