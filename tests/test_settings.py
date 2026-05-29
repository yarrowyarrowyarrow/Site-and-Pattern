"""
tests/test_settings.py

Persistence round-trip for src/settings.py: load_config and save_config
are the public surface and are consumed by collapsible_panel.py and
db/recipes.py. Locking down their behaviour means we can't accidentally
break the sidebar-collapse memory or the polyculture-recipe migration
path in later refactors.

The module reads/writes ``~/.permadesign_config.json``. Each test patches
``_CONFIG_PATH`` to a temp file so the real user config is never touched
(same hygiene the polyculture tests apply to the DB).
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.settings as settings  # noqa: E402


class _PatchConfigPath:
    """Context manager: redirect settings._CONFIG_PATH at the temp file."""

    def __init__(self):
        self._tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix="_config.json", delete=False,
        )
        self._tmp.close()
        # File is created empty; settings.load_config should treat it as
        # corrupt (json.JSONDecodeError) and fall back to {}.
        Path(self._tmp.name).unlink()  # drop the empty file
        self.path = self._tmp.name
        self._patcher = mock.patch.object(settings, "_CONFIG_PATH", self.path)

    def __enter__(self):
        self._patcher.start()
        return self.path

    def __exit__(self, *exc):
        self._patcher.stop()
        Path(self.path).unlink(missing_ok=True)


class TestLoadConfig(unittest.TestCase):

    def test_missing_file_returns_empty_dict(self):
        with _PatchConfigPath():
            self.assertEqual(settings.load_config(), {})

    def test_corrupt_file_returns_empty_dict(self):
        with _PatchConfigPath() as path:
            Path(path).write_text("{ not valid json", encoding="utf-8")
            self.assertEqual(settings.load_config(), {})

    def test_well_formed_file_round_trips(self):
        with _PatchConfigPath() as path:
            payload = {"sidebar_collapsed": True, "theme": "dark"}
            Path(path).write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(settings.load_config(), payload)


class TestSaveConfig(unittest.TestCase):

    def test_save_then_load_round_trip(self):
        with _PatchConfigPath():
            payload = {"a": 1, "nested": {"b": [1, 2, 3]}}
            settings.save_config(payload)
            self.assertEqual(settings.load_config(), payload)

    def test_save_overwrites_previous(self):
        with _PatchConfigPath():
            settings.save_config({"a": 1})
            settings.save_config({"b": 2})
            self.assertEqual(settings.load_config(), {"b": 2})

    def test_save_produces_human_readable_json(self):
        """indent=2 means the file is editable by a human in a pinch —
        a stable property worth pinning."""
        with _PatchConfigPath() as path:
            settings.save_config({"k": "v"})
            text = Path(path).read_text(encoding="utf-8")
            self.assertIn("\n  ", text)


class TestLegacyPlantApiSurfaceIsGone(unittest.TestCase):
    """After Chunk 1's cleanup, none of the legacy plant-API symbols should
    be reachable on the public module surface."""

    def test_removed_symbols(self):
        for name in (
            "get_api_keys", "save_api_keys", "has_api_keys",
            "SettingsDialog",
            "get_polyculture_recipes", "save_polyculture_recipes",
        ):
            self.assertFalse(
                hasattr(settings, name),
                f"settings.{name} should have been removed in Chunk 1 cleanup",
            )

    def test_public_surface_is_minimal(self):
        public = [n for n in dir(settings) if not n.startswith("_")]
        # `json` / `os` are module-level imports and are visible too — filter
        # to just the callables defined in this module.
        defined_here = [
            n for n in public
            if getattr(getattr(settings, n), "__module__", "") == "src.settings"
        ]
        self.assertEqual(
            sorted(defined_here),
            ["get_mapbox_token", "load_config", "save_config", "set_mapbox_token"],
        )


if __name__ == "__main__":
    unittest.main()
