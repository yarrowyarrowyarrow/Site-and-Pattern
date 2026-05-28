"""
tests/test_agent_session_example.py

Integration test that runs examples/agent_session.py end-to-end against
a sandboxed seeded DB. This guards the worked example (so it never
bit-rots as the API evolves) AND exercises the whole headless flow:
query → create → place plants + community + structure → analyze →
save → reload.

Runs under bare python — no PyQt6. If the example ever imports Qt or
breaks the API contract, this fails.
"""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Sandbox the DB to this module's own temp dir.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_example_test_")
_DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

import src.db.plants as _plants_mod  # noqa: E402
import src.permadesign_api as _api  # noqa: E402


def _use_our_db() -> None:
    """Point the DB + facade at THIS module's temp DB and init it.

    Every test module in this suite patches the module-level
    ``_plants_mod._DB_PATH`` at import, so after discovery the global
    points at whichever module was imported last — which may not have
    init'd yet when this class's methods run. Re-establishing the path
    (and re-init'ing — init_db is idempotent) in setUpClass, immediately
    before our own methods, makes this test order-independent.
    """
    from src.db.plants import init_db
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = _DB_PATH
    init_db()
    _api._DB_READY = True   # facade won't re-init against a stale path


def _load_example_module():
    """Import examples/agent_session.py by path (examples/ isn't a package)."""
    example_path = (Path(__file__).resolve().parent.parent
                    / "examples" / "agent_session.py")
    spec = importlib.util.spec_from_file_location("agent_session", example_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestAgentSessionExample(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _use_our_db()
        cls.example = _load_example_module()

    def test_runs_end_to_end(self):
        # setUpClass already pointed the DB at our temp path and init'd it;
        # nothing runs between setUpClass and this method to clobber it.
        out_dir = tempfile.mkdtemp(prefix="permadesign_example_out_")
        # Skip DOCX (python-docx may be absent in CI; covered separately).
        result = self.example.run(out_dir, with_docx=False)

        # Queried real seeded plants.
        self.assertGreater(result["n_natives"], 0)
        # Placed individual plants + (if seeded) a community.
        self.assertGreaterEqual(result["n_placed"], 6)
        # Produced a bounded 0-100 score.
        self.assertGreaterEqual(result["score"]["total"], 0)
        self.assertLessEqual(result["score"]["total"], 100)
        # Wrote a project file that exists and round-trips (the example
        # asserts identity internally; we just confirm the file landed).
        self.assertTrue(os.path.exists(result["project_path"]))

    def test_example_imports_no_qt(self):
        import ast
        example_path = (Path(__file__).resolve().parent.parent
                        / "examples" / "agent_session.py")
        tree = ast.parse(example_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertFalse(alias.name.startswith("PyQt6"))
            elif isinstance(node, ast.ImportFrom):
                self.assertFalse((node.module or "").startswith("PyQt6"))


if __name__ == "__main__":
    unittest.main()
