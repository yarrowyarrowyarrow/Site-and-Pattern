"""
tests/test_sandbox_undo.py — undo in the Learn sandbox (F104, V2.55).

Design mode has had a full undo stack since V1.81; the Learn sandbox had none,
so the side of the app built for people who do not know what they are doing yet
was the side where every misclick was permanent. ``scene3d_edit_flow`` even
carried a table saying so, with ``undo: none`` in the sandbox column.

Qt-free throughout: the stack is a plain object over the project dict, which is
the reason it lives in ``src/sandbox_undo.py`` rather than as window methods.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="permadesign_sandbox_undo_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP
    _plants_mod._DB_PATH = os.path.join(_TMP, "t.db")
except Exception:  # pragma: no cover
    pass

from src.project_store import ProjectStore  # noqa: E402
from src.sandbox_undo import (  # noqa: E402
    SandboxHistory, history_for, snapshot,
)


def _project():
    return {"type": "FeatureCollection", "features": [], "properties": {}}


def _plant(project, pid=1, name="Wild Rose", lat=51.05, lng=-114.07):
    ProjectStore(project).add_plant(pid, name, lat, lng)


class TestSnapshot(unittest.TestCase):
    def test_equal_states_compare_equal_as_text(self):
        """sort_keys, or a dict that merely reordered would look like a change
        and push a no-op entry that makes Undo need two presses."""
        a = {"type": "FeatureCollection", "features": [], "properties": {"x": 1}}
        b = {"properties": {"x": 1}, "features": [], "type": "FeatureCollection"}
        self.assertEqual(snapshot(a), snapshot(b))

    def test_none_is_survivable(self):
        self.assertEqual(snapshot(None), "{}")


class TestUndoStack(unittest.TestCase):
    def test_plant_then_undo_restores_the_previous_landscape(self):
        project = _project()
        hist = SandboxHistory()
        hist.record(project, "planting the Wild Rose")
        _plant(project)
        self.assertEqual(len(ProjectStore(project).placed_plants), 1)

        self.assertTrue(hist.undo(project))
        self.assertEqual(len(ProjectStore(project).placed_plants), 0,
                         "undo did not take the plant back out")

    def test_pull_then_undo_brings_it_back(self):
        project = _project()
        _plant(project, pid=7, name="Yarrow")
        hist = SandboxHistory()
        hist.record(project, "pulling the Yarrow")
        store = ProjectStore(project)
        rec = store.placed_plants[0]
        store.remove_plant(rec["plant_id"], rec["lat"], rec["lng"])
        self.assertEqual(len(ProjectStore(project).placed_plants), 0)

        self.assertTrue(hist.undo(project))
        back = ProjectStore(project).placed_plants
        self.assertEqual(len(back), 1)
        self.assertEqual(back[0]["common_name"], "Yarrow")

    def test_reset_is_undoable(self):
        """The point of F104 rather than a bonus: throwing away every edit was
        one click with nothing behind it."""
        project = _project()
        for i in range(4):
            _plant(project, pid=i + 1, name=f"Plant {i}", lng=-114.07 + i * 1e-4)
        hist = SandboxHistory()
        hist.record(project, "the reset")

        # What reset does: the project becomes the shipped community again.
        project.clear()
        project.update(_project())
        self.assertEqual(len(ProjectStore(project).placed_plants), 0)

        self.assertTrue(hist.undo(project))
        self.assertEqual(len(ProjectStore(project).placed_plants), 4,
                         "Reset was not undoable — the whole landscape is gone")

    def test_restores_in_place(self):
        """The window, the bridge and the store all hold the same dict. Rebind a
        new one and they keep pointing at the old landscape."""
        project = _project()
        hist = SandboxHistory()
        hist.record(project)
        _plant(project)
        held = project                       # what another object would hold
        hist.undo(project)
        self.assertIs(held, project)
        self.assertEqual(len(ProjectStore(held).placed_plants), 0)

    def test_steps_back_one_at_a_time(self):
        project = _project()
        hist = SandboxHistory()
        for i in range(3):
            hist.record(project, f"step {i}")
            _plant(project, pid=i + 1, lng=-114.07 + i * 1e-4)
        for expected in (2, 1, 0):
            self.assertTrue(hist.undo(project))
            self.assertEqual(len(ProjectStore(project).placed_plants), expected)

    def test_empty_undo_is_a_no_op_not_an_error(self):
        project = _project()
        hist = SandboxHistory()
        self.assertFalse(hist.can_undo())
        self.assertFalse(hist.undo(project))
        self.assertEqual(project, _project())

    def test_identical_pushes_collapse(self):
        """Otherwise Undo needs several presses to visibly do anything, which
        reads as a broken button."""
        project = _project()
        hist = SandboxHistory()
        for _ in range(5):
            hist.record(project, "nothing changed")
        self.assertEqual(len(hist), 1)

    def test_the_stack_is_bounded(self):
        project = _project()
        hist = SandboxHistory(limit=3)
        for i in range(10):
            hist.record(project, f"step {i}")
            _plant(project, pid=i + 1, lng=-114.07 + i * 1e-4)
        self.assertEqual(len(hist), 3)

    def test_a_corrupt_entry_is_skipped_not_raised(self):
        """This is the button a confused beginner presses; it must never be the
        thing that produces a traceback."""
        project = _project()
        hist = SandboxHistory()
        hist.record(project, "good")
        _plant(project)
        hist._stack.append(("corrupt", "{not json"))
        self.assertTrue(hist.undo(project))
        self.assertEqual(len(ProjectStore(project).placed_plants), 0)

    def test_label_reports_what_undo_would_reverse(self):
        project = _project()
        hist = SandboxHistory()
        self.assertEqual(hist.next_label(), "")
        hist.record(project, "planting the Wild Rose")
        self.assertEqual(hist.next_label(), "planting the Wild Rose")


class TestHistoryFor(unittest.TestCase):
    def test_created_once_and_reused(self):
        class FakeWin:
            pass

        win = FakeWin()
        first = history_for(win)
        self.assertIs(history_for(win), first,
                      "a second history would silently mean 'this verb is not "
                      "undoable', which is the hardest failure to notice")


class TestTheFlowRecordsBeforeMutating(unittest.TestCase):
    """Source shape: a snapshot taken *after* the change records the wrong
    state, and the bug looks like 'undo is off by one' rather than like a
    missing call."""

    def test_every_mutating_handler_remembers_first(self):
        import re
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "src", "reference_edit_flow.py")
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        for handler, mutator in (("on_plant_requested", "plant_at("),
                                 ("on_pull_requested", "pull_at("),
                                 ("on_reset", "reset_sandbox(")):
            body = re.search(rf"def {handler}\(.*?(?=\ndef |\Z)", src, re.S)
            self.assertIsNotNone(body, f"{handler} is gone")
            text = body.group(0)
            self.assertIn("_remember(", text,
                          f"{handler} does not snapshot before mutating — that "
                          f"verb is silently not undoable")
            self.assertLess(
                text.index("_remember("), text.index(mutator),
                f"{handler} snapshots AFTER the change; undo would restore the "
                f"state the user was trying to get away from")


if __name__ == "__main__":
    unittest.main()
