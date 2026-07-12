# Blender asset generators (`assetlib`)

Generates the low-poly GLB archetypes the 3D viewer loads from
`html/assets/models/` (chunk `html/scene3d/09-models.js`). The committed
GLBs are the shipped artifact — this package never runs inside the app
(regenerate-and-commit, like `scripts/render_flower_sprites.py`), and `bpy`
never enters `requirements*.txt`.

**Blender 4.2 LTS or newer.** The exact version used for a build is recorded
in `manifest.json → generator`.

Two ways to drive it, **one shared code path** (`assetlib.build_all`), so an
asset iterated in the viewport exports byte-identically in batch. The full
contract (unit frame, part/node/material names, AO-only vertex colors,
budgets) lives in `assetlib/conventions.py` and `docs/3D_ASSETS.md`.

## Headless batch build

```bash
blender --background --python scripts/blender/build_assets.py -- \
    --out html/assets/models            # everything + manifest.json
# subsets / validation:
#   -- --out /tmp/probe --only tree.spruce,fauna*
#   -- --check                          # build + validate, write nothing
```

Then run `python -m unittest tests.test_model_assets` and commit the
`html/assets/models/` changes.

## Driving it through the Blender MCP

With the [Blender MCP](https://github.com/ahujasid/blender-mcp) connected
(addon enabled in Blender → "Connect to Claude"), the agent iterates assets
live. **Bootstrap cell** — the first `execute_blender_code` of a session,
and again after any edit to `assetlib` on disk (it hot-reloads the package):

```python
import sys, importlib
P = "/ABS/PATH/TO/Site-and-Pattern/scripts/blender"   # ← your repo path
if P not in sys.path:
    sys.path.insert(0, P)
import assetlib
importlib.reload(assetlib)
assetlib.reload_all()
from assetlib import mcp_session as S
```

Then iterate one asset per short call (each is idempotent — collections are
wiped and rebuilt):

```python
S.keys("tree.")                 # what exists
S.build("tree.spruce")          # (re)build one asset → tri counts
S.frame("tree.spruce")          # aim the viewport at it
# → get_viewport_screenshot → judge the silhouette →
#   edit assetlib/flora_trees.py on disk → re-run the bootstrap cell →
#   S.build("tree.spruce") → screenshot again … repeat.
S.preview_tint("#2e5d3a")       # judge foliage in spruce-green (view only)
S.status()                      # everything built so far, with tri counts
S.export_all("/ABS/PATH/TO/Site-and-Pattern/html/assets/models")
```

`S.export_all(...)` rebuilds from the deterministic seeds — the screenshot
you approved is what lands on disk. Reproduce headlessly afterwards (same
seeds, same bytes) if you want CI-style confidence.

## What the viewer expects (summary — details in `assetlib/conventions.py`)

- **Flora**: parts named `bark` + `foliage` (herb/layer: `foliage` only),
  prefixed inside tier/variant nodes (`tier0_bark`, `v1_foliage`); unit
  frame base z=0 / height 1 / half-width 0.5; `COLOR_0` = grayscale AO
  (the app tints per instance — never bake hue); deciduous `bark` is a
  complete winter silhouette.
- **Fauna**: named nodes (`WingL`/`WingR` origin at the hinge, `Band0..2`,
  `Spots`, `Beak`…) and named materials (`MatFuzz`, `MatBody`…) — the
  viewer swaps materials by name and animates the wing nodes.
- **Budgets**: `conventions.TRI_BUDGETS` — the build **fails** on violation.

Missing/broken files never break the app: the viewer silently falls back to
its procedural geometry per archetype.
