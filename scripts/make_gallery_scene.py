#!/usr/bin/env python3
"""
make_gallery_scene.py — write the 3D sprite-gallery scenes JSON.

Thin wrapper around ``src.sprite_gallery.gallery_scenes()`` (the single source of
truth, shared with the in-app gallery window). Writes
``html/sprite_gallery_scenes.json`` for the standalone ``html/sprite_gallery.html``.

Run:  python scripts/make_gallery_scene.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sprite_gallery import gallery_scenes   # noqa: E402

OUT = ROOT / "html" / "sprite_gallery_scenes.json"


def main():
    scenes = gallery_scenes()
    OUT.write_text(json.dumps(scenes, separators=(",", ":")), encoding="utf-8")
    n_flw = sum(1 for k in scenes if k.startswith("flower_"))
    n_geo = len(scenes) - n_flw - 1
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(scenes)} entries "
          f"({n_geo} geometry + {n_flw} flower forms + 1 grid).")
    print("Keys:", ", ".join(sorted(scenes)))


if __name__ == "__main__":
    main()
