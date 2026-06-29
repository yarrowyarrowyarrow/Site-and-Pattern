# Vendored web assets for the built-in 3D viewer

These files are bundled so `html/scene3d.html` loads **offline** and is immune to
CDN outages and Chromium-version drift. They are served from an internal secure
URL scheme (`app://assets/…`, see `src/web_assets.py`), not over the network.

Before V1.77 the 3D viewer imported these from `unpkg.com` / `sparkjs.dev` at
runtime via an importmap on a `file://` page. A newer bundled Chromium (pulled
by the first CI-built Windows installer in V1.76) tightened ES-module loading on
`file://`, so the module graph threw and the viewer showed its "needs the
network once" notice even online. Vendoring removes that whole class of failure.

| File | Source | Version |
|------|--------|---------|
| `three/three.module.js` | npm `three` → `build/three.module.js` | 0.180.0 (MIT) |
| `three/three.core.js` | npm `three` → `build/three.core.js` (three.module.js re-exports from it — **required sibling**) | 0.180.0 (MIT) |
| `three/addons/controls/OrbitControls.js` | npm `three` → `examples/jsm/controls/` | 0.180.0 (MIT) |
| `three/addons/utils/BufferGeometryUtils.js` | npm `three` → `examples/jsm/utils/` | 0.180.0 (MIT) |
| `three/addons/postprocessing/Pass.js` | npm `three` → `examples/jsm/postprocessing/` (Spark needs it) | 0.180.0 (MIT) |
| `spark/spark.module.js` | npm `@sparkjsdev/spark` → `dist/spark.module.js` | 2.1.0 (MIT) |

The directory layout mirrors the old importmap keys, so the importmap in
`scene3d.html` just points at `./vendor/...`. The trailing
`//# sourceMappingURL=` comments were stripped (the `.map` files are not
vendored). Spark's wasm is inlined as a `data:` URL and its workers are built
from inline blobs, so no extra files are needed.

To refresh a version: `npm pack <pkg>@<ver>`, copy the files above into place,
strip the trailing sourcemap comment, and bump the table.
