// Part of the Site & Pattern 3D viewer, split out of the former
// single html/scene3d.html <script> (V2.24). Loaded as an ordered
// CLASSIC script by the bootstrap in scene3d.html — it shares the
// global scope with its siblings (THREE/OrbitControls/mergeGeometries
// are globals set by the bootstrap), so load ORDER is dependency
// order. Do not add ES `import`/`export` here.

// ── Herbaceous growth forms (V1.98) ─────────────────────────────────────────
// The foliage of a wildflower/herb is built to match its real growth habit, not
// one generic stem-clump: fireweed is a tall erect leafy stem, yarrow a low
// ferny mound, fleabane a basal rosette of leaves under wiry flower stalks. A
// form sets how many leafy stems there are and how upright, where the leaves sit
// (up the stem / basal rosette / low mound), the leaf size + width (lance vs
// broad vs fine), and how many bare flower stalks rise above (the flower sprite
// lands on top). `q(n)` quality-scales the counts.
const HERB_FORMS = {
  // erect leafy stem(s), narrow lance leaves spiralling up — fireweed, goldenrod,
  // penstemon, blazingstar, lupine, paintbrush, loosestrife.
  erect:   { stems: [1, 3], splay: 0.1,  leafFrom: 0.22, leaf: [0.2, 0.04],
             shape: 'lance', perStem: [6, 10], leafTilt: 1.1, stalks: 0, basal: 0, fine: 0 },
  // low ferny mound of fine divided foliage + thin flower stalks — yarrow,
  // tansy, meadow rue, columbine, cinquefoil, sweet cicely.
  ferny:   { stems: [0, 0], splay: 0,    leafFrom: 0,    leaf: [0.13, 0.02],
             shape: 'lance', perStem: 0, leafTilt: 1.3, stalks: [3, 5], basal: [20, 34], fine: 1 },
  // basal leaf rosette of broad spoon leaves under wiry flower stalks — fleabane,
  // arnica, evening primrose, avens, alumroot, agoseris, shooting star.
  rosette: { stems: [0, 0], splay: 0,    leafFrom: 0,    leaf: [0.26, 0.085],
             shape: 'ovate', perStem: 0, leafTilt: 1.32, stalks: [3, 6], basal: [8, 13], fine: 0 },
  // bushy upright leafy clump, broad ovate leaves — asters, sunflower, milkweed,
  // bee balm, monkeyflower.
  clump:   { stems: [3, 6], splay: 0.42, leafFrom: 0.12, leaf: [0.22, 0.1],
             shape: 'ovate', perStem: [4, 7], leafTilt: 0.95, stalks: 0, basal: [2, 3], fine: 0 },
  // upright strap / linear basal leaves — onion, harebell, blue-eyed grass, lily, camas.
  grassy:  { stems: [0, 0], splay: 0,    leafFrom: 0,    leaf: [0.9, 0.035],
             shape: 'strap', perStem: 0, leafTilt: 0.16, stalks: [2, 4], basal: [6, 9], fine: 0 },
  // low cushion / mat of small spoon leaves — umbrella-plant, moss campion, violets.
  mat:     { stems: [0, 0], splay: 0,    leafFrom: 0,    leaf: [0.14, 0.075],
             shape: 'ovate', perStem: 0, leafTilt: 1.45, stalks: [2, 4], basal: [14, 22], fine: 0, low: 1 },
  // arching divided fronds from a crown — ferns.
  fern:    { stems: [0, 0], splay: 0,    leafFrom: 0,    leaf: [0.95, 0.11],
             shape: 'lance', perStem: 0, leafTilt: 0.5, stalks: 0, basal: [6, 9], fine: 0 },
};

// Genus → herb growth form for the common prairie/Alberta forbs. Foliage colour
// still comes from the genus (silver sages etc.) via scene_contract.
const _HPROF = {
  chamaenerion: 'erect', epilobium: 'erect', solidago: 'erect', euthamia: 'erect',
  penstemon: 'erect', liatris: 'erect', lupinus: 'erect', castilleja: 'erect',
  physostegia: 'erect', stachys: 'erect', dalea: 'erect', lythrum: 'erect',
  verbena: 'erect', gentiana: 'erect', maianthemum: 'erect', anticlea: 'grassy',
  hedysarum: 'erect', astragalus: 'erect', oxytropis: 'rosette', vicia: 'erect',
  lathyrus: 'erect', heuchera: 'rosette', mertensia: 'clump',
  achillea: 'ferny', tanacetum: 'ferny', thalictrum: 'ferny', aquilegia: 'ferny',
  potentilla: 'ferny', osmorhiza: 'ferny', polemonium: 'ferny', anemone: 'ferny',
  erigeron: 'rosette', arnica: 'rosette', oenothera: 'rosette', geum: 'rosette',
  agoseris: 'rosette', primula: 'rosette', draba: 'rosette', townsendia: 'rosette',
  balsamorhiza: 'rosette', taraxacum: 'rosette', antennaria: 'mat',
  symphyotrichum: 'clump', eurybia: 'clump', canadanthus: 'clump', doellingeria: 'clump',
  dieteria: 'clump', heterotheca: 'clump', helianthus: 'clump', asclepias: 'clump',
  erythranthe: 'clump', echinacea: 'rosette', ratibida: 'rosette', monarda: 'clump',
  allium: 'grassy', campanula: 'grassy', sisyrinchium: 'grassy', iris: 'grassy',
  lilium: 'grassy', zigadenus: 'grassy', viola: 'mat', eriogonum: 'mat',
  fragaria: 'mat', silene: 'mat', phlox: 'mat',
};
// Habits the seed data records that this viewer has no distinct archetype for;
// each maps onto its nearest built form. tussock/emergent/floating never reach
// here (plant_type routes those to the grass/aquatic layers), but a herbaceous
// row carrying one should still land somewhere sensible.
const _FORM_ALIAS = {
  cushion: 'mat', succulent: 'mat', sprawling: 'mat', vining: 'clump',
  tussock: 'grassy', emergent: 'grassy', floating: 'mat',
  jointed: 'grassy',     // horsetails route to 14-layers.js first (V2.89)
  submerged: 'mat',      // wetland bodies route to 23-pond.js first (V2.90)
  pads: 'mat', globose: 'mat',   // cacti route to 24-succulents.js first (V2.93)
};
function herbFormFor(p) {
  if (p.plant_type === 'fern') return 'fern';
  // The species' own recorded habit wins (schema v48). Before it existed, form
  // came from the genus table below, which named 65 genera — so 64 of the 211
  // wildflowers had their shape guessed from flower form and aspect ratio, and
  // two thirds of those guesses collapsed onto one generic bushy clump.
  const recorded = (p.growth_form || '').toLowerCase();
  if (recorded) {
    if (HERB_FORMS[recorded]) return recorded;
    if (_FORM_ALIAS[recorded]) return _FORM_ALIAS[recorded];
  }
  const named = _HPROF[(p.genus || '').toLowerCase()];
  if (named) return named;
  // Fall back from the flower form + aspect (height/canopy).
  const ff = p.flower_form, h = p.height_m || 0.5, c = p.canopy_m || 0.4;
  const tall = h / Math.max(0.05, c) >= 1.6;
  if (ff === 'umbel') return 'ferny';
  if (ff === 'daisy') return tall ? 'clump' : 'rosette';
  if (ff === 'rays' || ff === 'spike' || ff === 'plume' || ff === 'pea')
    return tall ? 'erect' : 'clump';
  if (ff === 'globe' || ff === 'whorl') return 'clump';
  return tall ? 'erect' : 'clump';
}

// A flat leaf with a real width profile (V1.99) so foliage reads as leaves, not
// threads. The three original profiles (lance widest at the base — fireweed /
// willow; ovate widest at the middle — aster / milkweed; strap near-constant —
// onion / iris) are joined by the outlines the seed data actually records
// (schema v47/v48 `leaf_shape`), so a species' blade is drawn rather than
// approximated by whichever of three its growth form happened to carry.
// This is the mirror of mesh_ops._leaf_width — the procedural path is the
// permanent fallback, so the two have to draw the same leaf.
// Position-only indexed geometry so it merges with the (stripped) stems.
function _leafWidth(shape, t) {
  const tc = Math.min(0.96, Math.max(0.06, t));
  const sinp = (e) => Math.pow(Math.sin(Math.PI * tc), e);
  if (shape === 'ovate' || shape === 'elliptic') return sinp(0.7);
  // Widest ABOVE the middle — a pussytoes or fleabane rosette leaf, which the
  // ovate profile draws upside down.
  if (shape === 'obovate' || shape === 'spatulate') return sinp(0.7) * (0.35 + 0.9 * tc);
  if (shape === 'orbicular') return sinp(0.45);
  if (shape === 'reniform') return sinp(0.4) * (1.25 - 0.45 * tc);        // kidney
  if (shape === 'cordate') return sinp(0.55) * (1.35 - 0.6 * tc);         // heart
  // Arrowhead: flared basal lobes, then a long taper.
  if (shape === 'sagittate') return t < 0.16 ? 1.15 : Math.max(0.08, sinp(0.9) * 0.95);
  if (shape === 'lobed' || shape === 'pinnatifid' || shape === 'bipinnate') {
    // Deeply cut blades read as a lobed silhouette on a flat ribbon: a sinusoid
    // on the base profile. True notches would need a triangulated outline, which
    // costs 2-3x the triangles for a sub-centimetre effect.
    const lobes = shape === 'lobed' ? 3 : (shape === 'pinnatifid' ? 5 : 7);
    const wobble = 1 - (shape === 'bipinnate' ? 0.45 : 0.32)
      * (0.5 - 0.5 * Math.cos(2 * Math.PI * lobes * tc));
    return Math.max(0.06, sinp(0.7) * wobble);
  }
  if (shape === 'strap' || shape === 'linear') return t < 0.9 ? 1 : Math.max(0.15, (1 - t) / 0.1);
  if (shape === 'needle' || shape === 'awl' || shape === 'scale') return Math.max(0.08, 1 - 0.55 * t);
  return Math.max(0.05, 1 - 0.9 * t);          // lance / lanceolate / default
}

// Natural width ÷ length per outline (mesh_ops.LEAF_WIDTH_RATIO). Once a
// species' leaf_size_cm sets the LENGTH, the width has to come from the shape:
// a 20 cm balsamroot arrowhead and a 20 cm iris strap are not the same leaf.
const LEAF_WIDTH_RATIO = {
  needle: 0.03, awl: 0.05, scale: 0.25, linear: 0.06, lanceolate: 0.22,
  elliptic: 0.45, ovate: 0.62, obovate: 0.55, spatulate: 0.40, orbicular: 0.95,
  cordate: 0.85, reniform: 1.25, sagittate: 0.55, lobed: 0.75,
  pinnatifid: 0.42, bipinnate: 0.35, trifoliate: 0.85, compound_pinnate: 0.45,
  compound_palmate: 0.9, strap: 0.06,
};
function leafWidthFor(shape, len) {
  const r = LEAF_WIDTH_RATIO[shape];
  return len * (r == null ? 0.3 : r);
}

// Blades stamped as a rachis carrying leaflets rather than one ribbon, and the
// leaflet pairs (plus a terminal) each carries (mesh_ops COMPOUND_SHAPES /
// _LEAFLET_PAIRS).
const LEAFLET_PAIRS = { trifoliate: 1, compound_pinnate: 3, compound_palmate: 2,
                        bipinnate: 4 };
function isCompoundShape(shape) { return LEAFLET_PAIRS[shape] != null; }

// A compound leaf is a rachis plus 2n+1 leaflets, so it costs 3-9x a simple
// blade. Scale the leaf COUNT by the inverse rather than letting a lupine cost
// nine times a fireweed — which is also how the plants themselves resolve the
// same constraint: compound-leaved species carry fewer, larger leaves. The
// generator does this against a hard triangle budget (mesh_ops.thin_leaf_nodes);
// here there is no budget to enforce, only a frame time to protect.
function leafCountScale(shape) {
  const pairs = LEAFLET_PAIRS[shape];
  if (pairs == null) return 1;
  return 8 / (4 + (pairs * 2 + 1) * 8);
}
function makeLeafBlade(rng, len, wid, shape) {
  const segs = 4, dir = rng() * Math.PI * 2;
  const dx = Math.cos(dir), dz = Math.sin(dir), px = -dz, pz = dx;
  const lean = (shape === 'strap' ? 0.05 : 0.12) + rng() * 0.18;
  const pos = [], idx = [];
  for (let s = 0; s <= segs; s++) {
    const t = s / segs, y = len * t;
    const off = lean * Math.pow(t, 1.4);
    const wHalf = wid * 0.5 * _leafWidth(shape, t) + 0.0008;
    const cx = dx * off, cz = dz * off;
    pos.push(cx - px * wHalf, y, cz - pz * wHalf);
    pos.push(cx + px * wHalf, y, cz + pz * wHalf);
  }
  for (let s = 0; s < segs; s++) {
    const a = s * 2, b = s * 2 + 1, c = s * 2 + 2, d = s * 2 + 3;
    idx.push(a, b, c, b, d, c);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  return g;
}

// Place one leaf: build it, tilt `tilt` from vertical at azimuth `az`, translate
// to attachment point `at`. The building block for herbaceous + vine foliage.
function makeLeaf(rng, len, wid, tilt, az, at, shape) {
  const blade = makeLeafBlade(rng, len * (0.8 + rng() * 0.4), wid, shape || 'lance');
  blade.applyMatrix4(new THREE.Matrix4().makeRotationY(az)
    .multiply(new THREE.Matrix4().makeRotationZ(tilt)));
  if (at) blade.translate(at.x, at.y, at.z);
  return blade;
}

// A straight tapering strip along +Y — the spine a compound leaf hangs from.
// Position-only indexed geometry, matching makeLeafBlade so the two merge.
function _rachis(len, halfWidth) {
  const pos = [], idx = [], segs = 2;
  for (let s = 0; s <= segs; s++) {
    const t = s / segs, hw = halfWidth * (1 - 0.5 * t) + 0.0005;
    pos.push(-hw, len * t, 0, hw, len * t, 0);
  }
  for (let s = 0; s < segs; s++) {
    const a = s * 2;
    idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  return g;
}

// One compound leaf: a slim rachis carrying paired leaflets and a terminal one
// (mesh_ops.add_compound_leaf). A third of the catalogue's leaves are compound —
// every pea (lupine, milkvetch, hedysarum), rose, cinquefoil, columbine, meadow
// rue and mountain ash — and drawing them as a single ribbon is what made a
// lupine and a fireweed differ only in size. `compound_palmate` fans its leaflets
// from one point (lupine); the rest run up the rachis.
function makeCompoundLeaf(rng, len, wid, tilt, az, at, shape) {
  const pairs = LEAFLET_PAIRS[shape] || 3;
  const ln = len * (0.8 + rng() * 0.4);
  const palmate = shape === 'compound_palmate';
  // A straight rachis, not a makeLeafBlade one: that primitive leans in a random
  // horizontal direction, which would leave the leaflets attached to nothing.
  const parts = [_rachis(ln, ln * 0.012)];
  const lLen = ln * (palmate ? 0.42 : 0.30);
  const n = pairs * 2 + 1;
  const rFrom = palmate ? 0 : 0.12;
  for (let i = 0; i < n; i++) {
    let frac, spread;
    if (palmate) {                       // a fan from the rachis tip
      frac = 1; spread = (i / (n - 1) - 0.5) * 2.2;
    } else {
      frac = rFrom + (1 - rFrom) * Math.floor(i / 2) / Math.max(1, pairs);
      spread = (i % 2 ? -0.95 : 0.95) * (i === n - 1 ? 0 : 1);
    }
    const lf = makeLeaf(rng, lLen, lLen * 0.42,
                        tilt * 0.45 + Math.abs(spread) * 0.55, spread, null,
                        'elliptic');
    lf.translate(0, ln * frac, 0);
    parts.push(lf);
  }
  const leaf = mergeGeometries(parts, false);
  for (const p of parts) p.dispose();
  leaf.applyMatrix4(new THREE.Matrix4().makeRotationY(az)
    .multiply(new THREE.Matrix4().makeRotationZ(tilt)));
  if (at) leaf.translate(at.x, at.y, at.z);
  return leaf;
}

// The single entry point the builders call, so a new compound outline never needs
// another branch at every call site (mesh_ops.add_blade_or_leaf).
function makeBladeOrLeaf(rng, len, wid, tilt, az, at, shape) {
  return isCompoundShape(shape)
    ? makeCompoundLeaf(rng, len, wid, tilt, az, at, shape)
    : makeLeaf(rng, len, wid, tilt, az, at, shape);
}

// Rescale a set of geometries (in place, sharing one frame) to base y = 0,
// height 1, horizontal half-width 0.5 — so per-instance scale is [canopy,
// height, canopy], matching the rest of the plant pipeline.
// Normalise a set of geometries jointly to the archetype frame: base y=0 and
// height 1, scaled UNIFORMLY so the authored proportions survive. Returns the
// resulting horizontal half-extent and stamps it on each geometry's userData —
// instancing divides the canopy scale by it (unitXZ in 04-quality.js), so the
// plant still lands on exactly (canopy_m wide, height_m tall).
//
// It used to squash to half-width 0.5, which made every archetype 1:1 and left
// the instance transform to stretch it back out by the species' real
// height/canopy — 3.3× on a white spruce, 4.2× on a lodgepole pine. That is
// what turned a poplar's foliage clumps into metre-wide "leaves" (V2.29). The
// same reasoning and the generator's half of the contract are in
// scripts/blender/assetlib/conventions.py.
function normalizeUnit(geos) {
  const box = new THREE.Box3();
  for (const g of geos) {
    if (!g) continue;
    g.computeBoundingBox(); box.union(g.boundingBox);
  }
  const sizeY = Math.max(1e-3, box.max.y - box.min.y);
  const halfXZ = Math.max(1e-3, Math.abs(box.min.x), Math.abs(box.max.x),
                          Math.abs(box.min.z), Math.abs(box.max.z));
  const s = 1 / sizeY;
  const hw = halfXZ * s;
  for (const g of geos) {
    if (!g) continue;
    g.translate(0, -box.min.y, 0);
    g.scale(s, s, s);
    g.computeVertexNormals();
    g.userData.unitHalfWidth = hw;
  }
  return hw;
}

// Multi-tone canopy gradient (spec idea 8): a warm, brighter sunlit crown up
// top fading to a cool, desaturated self-shadowed interior below. Baked as a
// vertex-colour multiplier (values >1 push the sunlit highlight) so the
// per-instance seasonal colour still shows through. A smoothstep curve gives
// more contrast than a flat lerp.
function applyFoliageGradient(geo) {
  const pos = geo.attributes.position;
  const col = new Float32Array(pos.count * 3);
  const bot = [0.40, 0.50, 0.46], top = [1.10, 1.04, 0.80];
  for (let i = 0; i < pos.count; i++) {
    const t = Math.min(1, Math.max(0, pos.getY(i)));
    const tt = t * t * (3 - 2 * t);   // smoothstep → deeper shadow low, hotter top
    col[i * 3] = bot[0] + (top[0] - bot[0]) * tt;
    col[i * 3 + 1] = bot[1] + (top[1] - bot[1]) * tt;
    col[i * 3 + 2] = bot[2] + (top[2] - bot[2]) * tt;
  }
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
}

// Blade lighting trick (V1.92): a flat, near-vertical grass blade has a
// horizontal face normal, so an overhead sun grazes it and the tuft reads dark
// and metallic. Bending every normal toward +Y lets the whole clump catch the
// sky/sun as one soft mass — the standard way real-time grass is shaded.
function liftNormals(geo, amount) {
  const nrm = geo.attributes.normal;
  if (!nrm) return;
  const a = amount ?? 0.7;
  for (let i = 0; i < nrm.count; i++) {
    let x = nrm.getX(i), y = nrm.getY(i) + a, z = nrm.getZ(i);
    const len = Math.hypot(x, y, z) || 1;
    nrm.setXYZ(i, x / len, y / len, z / len);
  }
  nrm.needsUpdate = true;
}

// One arched, tapered grass/reed blade as a flat ribbon (a few quad segments).
// `lean` is the horizontal sweep of the tip; `wb` the base half-width; `erect`
// pushes the bend higher up the blade so reeds stand stiffer than meadow grass.
function makeBlade(rng, h, wb, lean, erect) {
  const segs = 5;
  const dir = rng() * Math.PI * 2;
  const dx = Math.cos(dir), dz = Math.sin(dir);
  const px = -dz, pz = dx;                       // ribbon width axis (horizontal)
  const twist = (rng() - 0.5) * 0.5;             // slight per-blade roll
  const pos = [], idx = [];
  for (let s = 0; s <= segs; s++) {
    const t = s / segs;
    const y = h * t;
    const off = lean * Math.pow(t, erect);       // arch: more sweep near the tip
    const wHalf = wb * (1 - t * 0.92) + 0.0015;  // taper toward a fine point
    const cx = dx * off, cz = dz * off;
    const wpx = px * Math.cos(twist * t) , wpz = pz * Math.cos(twist * t);
    pos.push(cx - wpx * wHalf, y, cz - wpz * wHalf);
    pos.push(cx + wpx * wHalf, y, cz + wpz * wHalf);
  }
  for (let s = 0; s < segs; s++) {
    const a = s * 2, b = s * 2 + 1, c = s * 2 + 2, d = s * 2 + 3;
    idx.push(a, b, c, b, d, c);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  return g;
}


// ── forked forb stems (V2.35) ───────────────────────────────────────────────
// The viewer's copy of assetlib/flora_herbs._branch_skeleton, for the procedural
// path (the baked GLB units carry the fork in their geometry). `stem_branching`
// has been in the catalogue since schema v53 and nothing read it: every forb
// stem was one straight rod, so a goldenrod — two orders of branching, which is
// most of what its silhouette IS — came out as a blazingstar.
//
// Returns spans in the stem's own frame (+Y up, base at the origin); the caller
// rotates them into place. Anything but a recognised branching value gives one
// straight span, which is exactly the pre-axis geometry (P9: no data, no
// invented fork).
function branchSpans(rng, h, branching, budget) {
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const base = V(0, 0, 0);
  if (branching !== 'branched_above' && branching !== 'branched_throughout')
    return [[base, V(0, h, 0)]];
  const deep = branching === 'branched_throughout';
  // A plant that branches throughout forks LOW and spreads wide (an aster, a
  // sunflower); one that branches above holds a clean stem and opens only at
  // the top (a goldenrod, a bergamot).
  const first = deep ? 0.34 : 0.60, spread = deep ? 0.26 : 0.17;
  const fork = V(0, h * first, 0);
  const out = [[base, fork]];
  // `budget` caps the segments, because each one costs geometry the LEAVES
  // come from: an unbudgeted six-stemmed clump forking twice put forty cones on
  // the plant and thinned its foliage to a bare wire spray. The spray is the
  // whole plant, not each stem of it.
  const b = Math.max(2, budget || 12);
  let n = Math.max(1, Math.min(deep ? 4 : 3, b - 1));
  if (deep) n = Math.max(1, Math.min(n, Math.floor((b - 1) / 2)));
  for (let i = 0; i < n; i++) {
    const az = (i / n) * Math.PI * 2 + rng() * 0.8;
    const r = spread * h * (0.6 + rng() * 0.8);
    const top = h * first + h * (1 - first) * (0.70 + rng() * 0.45);
    const tip = V(Math.cos(az) * r, top, Math.sin(az) * r);
    if (!deep) { out.push([fork, tip]); continue; }
    // A second order, because one order reads as a candelabra and a
    // branched-throughout forb is a spray.
    const mid = fork.clone().lerp(tip, 0.45 + rng() * 0.2);
    out.push([fork, mid]);
    const subs = Math.max(1, Math.min(3,
      Math.floor((b - out.length) / Math.max(1, n - i))));
    for (let j = 0; j < subs; j++) {
      const az2 = az + (j - 0.5) * 0.9 + (rng() - 0.5) * 0.5;
      const r2 = spread * h * 0.5 * (0.6 + rng() * 0.7);
      out.push([mid, V(mid.x + Math.cos(az2) * r2,
                       mid.y + (tip.y - mid.y) * (0.7 + rng() * 0.5),
                       mid.z + Math.sin(az2) * r2)]);
    }
  }
  return out;
}

// A point at fraction `t` of the way along the whole skeleton, so leaves are
// distributed in proportion to segment length: a plant that puts most of its
// length into three top branches gets most of its leaves there.
function alongSpans(spans, total, t) {
  let d = Math.max(0, Math.min(1, t)) * (total || 1), run = 0;
  for (let i = 0; i < spans.length; i++) {
    const [a, b] = spans[i];
    const ln = a.distanceTo(b);
    if (d <= run + ln || i === spans.length - 1)
      return a.clone().lerp(b, ln > 1e-6 ? Math.min(1, (d - run) / ln) : 0);
    run += ln;
  }
  return spans[0][0].clone();
}
