#!/usr/bin/env python3
"""
render_flower_sprites.py — render the 3D flower sprite textures to a PNG sheet.

The flower billboards in the 3D viewer are pure 2D-canvas drawings
(``makeFlowerTexture`` in ``html/scene3d.html``). This script **extracts that
exact function** (plus ``FLOWER_FORMS``) from the source by brace-matching — no
duplication, so the PNG always matches the shipped sprite — builds a tiny
harness page that draws every form tinted to its real flower colour, and
screenshots it with the pre-installed headless Chromium (2D canvas only — no
WebGL/GPU needed).

Output: ``docs/3d/flower_sprites.png``.

Run:  python scripts/render_flower_sprites.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENE3D = ROOT / "html" / "scene3d.html"
SCENES_JSON = ROOT / "html" / "sprite_gallery_scenes.json"
OUT = ROOT / "docs" / "3d" / "flower_sprites.png"

_CHROME_CANDIDATES = [
    "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
]


def _chrome() -> str:
    for c in _CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    # last resort: anything matching in /opt/pw-browsers
    hits = list(Path("/opt/pw-browsers").glob("chromium*/chrome-linux/*"))
    for h in hits:
        if h.name in ("headless_shell", "chrome"):
            return str(h)
    raise SystemExit("No headless Chromium found under /opt/pw-browsers")


def _grab_function(src: str, header: str) -> str:
    """Return the full text of a JS function by brace-matching from `header`."""
    i = src.index(header)
    j = src.index("{", i)
    depth, k = 0, j
    while True:
        ch = src[k]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    return src[i:k + 1]


def _real_flower_colors() -> dict:
    """Real per-form flower colours from the generated gallery scenes (so the
    sheet shows each sprite as it actually appears in the app)."""
    colors = {}
    if SCENES_JSON.exists():
        data = json.loads(SCENES_JSON.read_text())
        for key, entry in data.items():
            if key.startswith("flower_"):
                form = key[len("flower_"):]
                plants = entry.get("scene", {}).get("plants", [])
                if plants and plants[0].get("flower_color"):
                    colors[form] = plants[0]["flower_color"]
    return colors


def main():
    src = SCENE3D.read_text()
    make_tex = _grab_function(src, "function makeFlowerTexture")
    forms_lit = re.search(r"const FLOWER_FORMS = (\[[\s\S]*?\]);", src).group(1)

    colors = _real_flower_colors()
    default_colors = {
        "daisy": "#8e6fc4", "rays": "#f2c11e", "spike": "#8e6fc4",
        "plume": "#cbbd80", "umbel": "#f2c11e", "globe": "#e58fb0",
        "cluster": "#6f8fd6", "bell": "#6f8fd6", "trumpet": "#d6453a",
        "cattail": "#7a5230",
    }
    for f, c in default_colors.items():
        colors.setdefault(f, c)

    OUT.parent.mkdir(parents=True, exist_ok=True)

    harness = _HARNESS_TMPL.format(
        make_tex=make_tex,
        forms=forms_lit,
        colors=json.dumps(colors),
    )

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     dir=str(OUT.parent)) as fh:
        fh.write(harness)
        harness_path = Path(fh.name)

    try:
        cmd = [
            _chrome(), "--headless", "--no-sandbox", "--disable-gpu",
            "--hide-scrollbars", "--force-device-scale-factor=2",
            "--window-size=1180,560",
            f"--screenshot={OUT}",
            f"--virtual-time-budget=3000",
            harness_path.as_uri(),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if not OUT.exists() or OUT.stat().st_size < 2000:
            sys.stderr.write(res.stdout + "\n" + res.stderr + "\n")
            raise SystemExit("Screenshot failed or produced an empty file.")
    finally:
        harness_path.unlink(missing_ok=True)

    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB) — "
          f"{forms_lit.count(',') + 1} flower forms.")


_HARNESS_TMPL = """<!doctype html><html><head><meta charset="utf-8">
<style>html,body{{margin:0;background:#16221a}}</style></head><body>
<canvas id="sheet" width="1180" height="560"></canvas>
<script>
// Minimal stubs — makeFlowerTexture only needs CanvasTexture + SRGBColorSpace.
const THREE = {{ CanvasTexture: function(c){{ this.image = c; }}, SRGBColorSpace: 'srgb' }};
{make_tex}
const FLOWER_FORMS = {forms};
const COLORS = {colors};

function tint(srcCanvas, color, size) {{
  const t = document.createElement('canvas'); t.width = t.height = size;
  const c = t.getContext('2d');
  c.drawImage(srcCanvas, 0, 0, size, size);
  c.globalCompositeOperation = 'source-in';
  c.fillStyle = color; c.fillRect(0, 0, size, size);
  return t;
}}

const sheet = document.getElementById('sheet');
const g = sheet.getContext('2d');
g.fillStyle = '#16221a'; g.fillRect(0, 0, sheet.width, sheet.height);
g.fillStyle = '#a5d6a7';
g.font = '600 18px system-ui, sans-serif';
g.fillText('Site & Pattern — 3D flower sprites (real makeFlowerTexture, in real flower colours)', 20, 28);

const cols = 5, sprite = 150, tile = 232, x0 = 24, y0 = 52;
FLOWER_FORMS.forEach((form, i) => {{
  const col = i % cols, row = Math.floor(i / cols);
  const x = x0 + col * tile, y = y0 + row * tile;
  // tile backdrop
  g.fillStyle = '#1e2e22'; g.strokeStyle = '#2e4a36';
  g.fillRect(x, y, sprite, sprite); g.strokeRect(x, y, sprite, sprite);
  const tex = makeFlowerTexture(form);              // the REAL sprite mask
  const colored = tint(tex.image, COLORS[form] || '#cfe8cf', sprite);
  g.drawImage(colored, x, y);
  g.fillStyle = '#cfe8cf'; g.font = '600 15px system-ui, sans-serif';
  g.fillText(form, x + 4, y + sprite + 20);
  g.fillStyle = '#8fae97'; g.font = '12px system-ui, sans-serif';
  g.fillText(COLORS[form] || '', x + 4, y + sprite + 36);
}});
window.__done = true;
</script></body></html>
"""


if __name__ == "__main__":
    main()
