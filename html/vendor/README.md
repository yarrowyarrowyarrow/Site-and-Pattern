# Vendored web assets

Third-party JavaScript the app's two web views need, bundled so neither depends
on a CDN. Two sections: the 3D viewer (since V1.77) and the 2D design map
(since V2.83).

## The built-in 3D viewer

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
| `three/addons/loaders/GLTFLoader.js` | npm `three` → `examples/jsm/loaders/` (Blender GLB assets, V2.27; its `../utils/BufferGeometryUtils.js` import resolves to the row above) | 0.180.0 (MIT) |
| `spark/spark.module.js` | npm `@sparkjsdev/spark` → `dist/spark.module.js` | 2.1.0 (MIT) |

The directory layout mirrors the old importmap keys, so the importmap in
`scene3d.html` just points at `./vendor/...`. The trailing
`//# sourceMappingURL=` comments were stripped (the `.map` files are not
vendored). Spark's wasm is inlined as a `data:` URL and its workers are built
from inline blobs, so no extra files are needed.

To refresh a version: `npm pack <pkg>@<ver>`, copy the files above into place,
strip the trailing sourcemap comment, and bump the table.

## The 2D design map

`html/map.html` loaded Leaflet and Leaflet.draw from a CDN until V2.83. With no
internet, or with the CDN down or blocked, the page loaded with no `L`, every
map script threw `ReferenceError: L is not defined`, and the design window
opened on an empty panel: no boundary, no placement, no overlays. The site pin
(step 1 of getting started) also took its icon from the CDN and drew as nothing.
Map **tiles** still come from the network; the map now starts and draws without
them.

Unlike the 3D viewer these are classic scripts on the `file://` page, loaded by
relative path from `map.html` (`vendor/leaflet/leaflet.js`), and the site pin in
`html/map/06-overlays.js` names its icons the same way. Both stylesheets find
their images relative to themselves, so each `images/` folder has to stay beside
its `.css`.

| File | Source | Version |
|------|--------|---------|
| `leaflet/leaflet.js`, `leaflet.css` | npm `leaflet` → `dist/` | 1.9.4 (BSD-2-Clause, `leaflet/LICENSE`) |
| `leaflet/images/*.png` | npm `leaflet` → `dist/images/` (markers, layer control) | 1.9.4 |
| `leaflet-draw/leaflet.draw.js`, `leaflet.draw.css` | npm `leaflet-draw` → `dist/` | 1.0.4 (MIT, `leaflet-draw/LICENSE`) |
| `leaflet-draw/images/spritesheet*` | npm `leaflet-draw` → `dist/images/` (toolbar icons; the package's copies of Leaflet's own marker images are not needed) | 1.0.4 |

Tarball SHA-1s as fetched, matching the registry's `dist.shasum`:
`leaflet-1.9.4.tgz` `23fae724e282fa25745aff82ca4d394748db7d8d`,
`leaflet-draw-1.0.4.tgz` `45be92f378ed253e7202fdeda1fcc71885198d46`.
The only change to either file is the removed trailing `//# sourceMappingURL=`
line. The `leaflet-draw` package ships no licence file; its `package.json`
declares MIT and the copyright line is taken from the header of
`leaflet.draw.js`.

`tests/test_map_vendor.py` fails if a CDN reference comes back into `map.html`
or any `html/map/*.js`, if a file `map.html` names is missing, or if an image a
stylesheet names is not vendored.
