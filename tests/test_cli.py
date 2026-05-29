"""
tests/test_cli.py

Tests for the headless CLI (src/cli.py). Drives main(argv) directly,
capturing stdout, against a sandboxed seeded DB. Runs under bare python
(no PyQt6) — the CLI is a thin shell over the Qt-free facade.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Sandbox the DB to this module's own temp dir, init it, and pin the
# facade ready-flag at this path (the suite's module-level DB patching
# means the global can otherwise point at an un-init'd path by run time).
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_cli_test_")
_DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
import src.db.plants as _plants_mod  # noqa: E402
import src.permadesign_api as _api  # noqa: E402


def _use_our_db() -> None:
    from src.db.plants import init_db
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = _DB_PATH
    init_db()
    _api._DB_READY = True


from src.cli import main  # noqa: E402


def _run(argv: list[str]) -> tuple[int, str, str]:
    """Run the CLI, return (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class TestCli(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _use_our_db()

    def test_query_text(self):
        code, out, _ = _run(["query", "yarrow"])
        self.assertEqual(code, 0)
        self.assertIn("plant(s).", out)

    def test_query_json_is_valid(self):
        code, out, _ = _run(["query", "--native", "--limit", "3", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIsInstance(data, list)
        self.assertLessEqual(len(data), 3)
        for p in data:
            self.assertIn("id", p)

    def test_query_native_filter(self):
        code, out, _ = _run(["query", "--native", "--json"])
        data = json.loads(out)
        self.assertTrue(all(p.get("native_to_alberta") for p in data))

    def test_list_communities(self):
        code, out, _ = _run(["list-communities"])
        self.assertEqual(code, 0)
        self.assertIn("community", out.lower())

    def test_list_structures_json(self):
        code, out, _ = _run(["list-structures", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(any(s.get("id") for s in data))

    def test_analyze_project(self):
        # Build a small project via the API, save, then analyze via CLI.
        from src.permadesign_api import Project, query_plants
        proj = Project.create("CLI Test", boundary=[
            (53.55, -113.50), (53.55, -113.49),
            (53.54, -113.49), (53.54, -113.50),
        ])
        for p in query_plants(native_only=True)[:4]:
            proj.place_plant(p["id"], 53.545, -113.495)
        path = os.path.join(_TMP_DIR, "cli_proj.perma.geojson")
        proj.save(path)

        code, out, _ = _run(["analyze", path])
        self.assertEqual(code, 0)
        self.assertIn("Habitat Value Score", out)

        code, out, _ = _run(["analyze", path, "--json"])
        data = json.loads(out)
        self.assertIn("habitat_score", data)
        self.assertIsNotNone(data["habitat_score"])

    def test_analyze_missing_file_exit_code(self):
        code, _out, err = _run(["analyze", "/no/such/project.perma.geojson"])
        self.assertEqual(code, 2)   # PermaDesignError → exit 2
        self.assertIn("error:", err)

    def test_validate_data(self):
        # Shipped data should be error-free → exit 0.
        code, out, _ = _run(["validate-data", "--quiet"])
        self.assertEqual(code, 0)

    def test_no_subcommand_errors(self):
        # argparse exits (SystemExit) when a required subcommand is missing.
        with self.assertRaises(SystemExit):
            _run([])

    # ── generate (offline path — no LLM required) ────────────────────────────

    def test_generate_offline_with_goals(self):
        path = os.path.join(_TMP_DIR, "gen_offline.perma.geojson")
        code, out, _ = _run([
            "generate", "--no-llm",
            "--goal", "native_only", "--goal", "food_producing",
            "--lat", "53.5461", "--lng", "-113.4938", "--out", path,
        ])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(path))
        self.assertIn("plant placements", out)
        from src.permadesign_api import Project
        proj = Project.load(path)
        self.assertGreaterEqual(len(proj.placed_plants), 1)

    def test_generate_offline_without_goals(self):
        path = os.path.join(_TMP_DIR, "gen_offline_nogoals.perma.geojson")
        code, _out, _ = _run([
            "generate", "--no-llm",
            "--lat", "53.5461", "--lng", "-113.4938", "--out", path,
        ])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(path))

    def test_generate_rejects_unknown_goal(self):
        path = os.path.join(_TMP_DIR, "gen_bad.perma.geojson")
        with self.assertRaises(SystemExit):   # argparse `choices` rejects it
            _run(["generate", "--no-llm", "--goal", "definitely_not_a_goal",
                  "--lat", "53.5", "--lng", "-113.5", "--out", path])

    def test_generate_offline_needs_location(self):
        path = os.path.join(_TMP_DIR, "gen_noloc.perma.geojson")
        code, _out, err = _run(["generate", "--no-llm",
                                "--goal", "native_only", "--out", path])
        self.assertEqual(code, 2)   # LLMError (no site location) → exit 2
        self.assertIn("error:", err)


if __name__ == "__main__":
    unittest.main()
