// html/scene3d/chunks.js — the 3D viewer's chunks, in load order (V3.39).
//
// Moved out of scene3d.html, which was at its 400-line ceiling: the guard's
// own note said the next chunk needed this list out of the page first. A
// classic script, loaded before the page's module, which reads it; each
// chunk's onload loads the next, so the global-scope declarations accumulate
// in this order. Load ORDER is dependency order (see any chunk's header).
window.SCENE3D_CHUNKS = [
  'scene3d/01-core.js',
  // Surfaces + plantMaterial: before 02-plants because everything downstream
  // of it builds geometry that wants a material.
  'scene3d/01b-surface.js',
  'scene3d/01c-leaves.js',   // V2.94: leaves let light through (F186)
  'scene3d/02-plants.js',
  'scene3d/03-herbs.js',
  'scene3d/03b-trees.js',   // V2.92: the procedural trees, split from 03-herbs
  'scene3d/04-quality.js',
  'scene3d/05-flowers.js',
  'scene3d/06-fly.js',
  'scene3d/07-wildlife.js',
  'scene3d/08-modes.js',
  'scene3d/09-models.js',
  'scene3d/10-inspect.js',
  'scene3d/11-fruit.js',
  'scene3d/12-seedheads.js',
  'scene3d/13-stylised.js',
  'scene3d/14-layers.js',
  'scene3d/15-florets.js',
  // V2.43: click-to-plant in the reference sandboxes, and the QWebChannel
  // the viewer never had. Last on purpose — its pointer handlers must
  // register after 10-inspect.js's so both see the same click.
  'scene3d/16-editing.js',
  // V2.44: the tween registry and the plant / pull / catch animations.
  // 16-editing.js only calls into these at click time, long after every
  // chunk has loaded, so it does not need to load first.
  'scene3d/17-anim.js',
  'scene3d/18-flight.js',   // V2.45: real wingbeats (src/flight_model.py)
  // V2.46: the roster / labels / spotlight, split out of 07-wildlife.js when
  // life-size scaling and creature collision took it past its ceiling.
  'scene3d/19-roster.js',
  // V2.46b: the walker's body and his net, split out of 08-modes.js when the
  // held net took it past its ceiling. Nothing here is called from the
  // animation loop — see the load-order note in the file.
  'scene3d/20-walker.js',
  // V2.46d: the procedural creature bodies, split out of 07-wildlife.js when
  // the bird flight attitude took it past its ceiling. Nothing here is called
  // from the animation loop — see 08-modes.js:_loopFault.
  'scene3d/21-critters.js',
  // V2.89: vines on the tree or shrub beside them (F179). Called from
  // buildPlants after the trees and shrubs have noted where they stand.
  'scene3d/22-vines.js',
  // V2.90: the pond (F175) — floating leaves on a pond's water, submerged
  // plants showing what reaches the surface, broad leaves on stalks.
  'scene3d/23-pond.js',
  'scene3d/24-succulents.js',   // V2.93: cacti, yucca and roseroot (F177)
];
