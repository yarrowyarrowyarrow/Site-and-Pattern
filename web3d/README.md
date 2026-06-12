# web3d — sun-driven shadows for the embedded map3d 3D view

> **Note (V1.62):** building this fork is now OPTIONAL. When `web3d/dist/`
> is absent, `Map3DWidget` loads the built-in viewer `html/scene3d.html`
> instead — a self-contained three.js scene that renders the design itself
> (plants, buildings, terrain, boundary, sun shadows) from the Scene JSON
> contract (`src/scene_contract.py`). Build this fork when you also want
> the map3d city context (OSM buildings + roads) around the design.

The 3D view fork is the MIT-licensed [cartesiancs/map3d](https://github.com/cartesiancs/map3d)
(React + React-Three-Fiber). Upstream renders 3D buildings but **casts no
shadows** — its `<Canvas>` has no shadow renderer, its lights are fill-only, and
there is no ground for shadows to land on.

`map3d-sun-shadows.patch` adds sun-driven shadow casting, wired so PermaDesign's
own sun path (`src/solar.py`) drives it — the 3D shadows then track the same
solar positions as the 2D shade engine (`src/shade.py`).

## What the patch changes (2 files)

- **`src/state/sunStore.ts`** (new) — a zustand store holding the sun
  `azimuthDeg` (clockwise from north) and `altitudeDeg` (above the horizon), plus
  a `window.permaSetSun(azimuthDeg, altitudeDeg)` hook the desktop host calls.
- **`src/three/Space.tsx`** — the scene:
  - `<Canvas shadows>` turns on the shadow-map renderer.
  - A `<Sun>` component: a `<directionalLight castShadow>` whose direction comes
    from the sun store (`sunVector` maps azimuth/altitude into the scene's
    `+X=east, +Y=up, +Z=south` axes), with an orthographic shadow frustum sized
    to the area so shadows stay sharp.
  - A `<Ground>` shadow-catcher (`<shadowMaterial>`): transparent except where
    shadows fall, so the existing sky/environment look is preserved.
  - `castShadow` + `receiveShadow` on the building meshes (so buildings shade the
    ground *and* each other); ambient light lowered so the sun reads as the key
    light.

## Apply it to the map3d fork

```bash
# from the root of your map3d checkout
git apply /path/to/PermaDesign/web3d/map3d-sun-shadows.patch
npm run build        # tsc -b && vite build  (verified clean against map3d@2c5d732)
```

If you load the built `dist/` from `file://` inside a `QWebEngineView`, set
`base: './'` in `vite.config.ts` first so the asset URLs resolve.

## Drive the sun from PermaDesign

`src/map3d_js.py` builds the JS that calls the hook, reusing `src/solar.py`:

```python
from src import map3d_js
js = map3d_js.set_sun_for(lat, lng, when)   # None when the sun is below horizon
if js:
    map3d_widget.page().runJavaScript(js)   # → window.permaSetSun(az, alt)
```

`set_sun(azimuth_deg, altitude_deg)` is the lower-level builder. Because the
angles are exactly `solar.sun_position`'s, the 3D shadows and the 2D shade
overlay agree by construction — slide the time/season control and both move
together.
