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

// Crown form from the (already-scaled) height/canopy aspect ratio.
function formOf(p) {
  const c = Math.max(0.1, p.canopy_m || 1), h = Math.max(0.1, p.height_m || 1);
  const aspect = h / c;
  return aspect >= 2.0 ? 'slender' : (aspect <= 1.1 ? 'spreading' : 'oval');
}

// Which crown form a TREE gets, preferring what its own record says over what
// its genus does.
//
// `prof.formBias` exists (per its own note in 02-plants.js) "so a species reads
// right even when its dimensions are ambiguous" — but it was applied as an
// OVERRIDE, so every Betula got `oval` whether it was a 20 m paper birch
// (aspect 2.7, slender) or an 8 m water birch (1.8, oval), and every Prunus and
// every Malus was one shape. That is most of why the sprite audit scored
// deciduous trees 3/10 for distinctness. It is a fallback now, as written.
//
// `branching` (schema v47) is the other species character, and nothing read it
// until V2.29: a multi_stem tree — water birch, Bebb's willow, alder — is a
// broad low clump of stems, not a single-leadered spire, and reading the column
// is the whole fix.
function treeFormFor(p, prof) {
  if (p.branching === 'multi_stem') return 'spreading';
  if (p.branching === 'excurrent' && (p.height_m || 0) > 0) {
    // One dominant leader: never draw it as the broad no-leader form.
    const f = formOf(p);
    return f === 'spreading' ? 'oval' : f;
  }
  const known = (p.height_m || 0) > 0 && (p.canopy_m || 0) > 0;
  return known ? formOf(p) : ((prof && prof.formBias) || formOf(p));
}

function decidCfg(form, tier, prof) {
  const cfg = Object.assign({}, DECID_CFG, DECID_FORMS[form], { maxDepth: DECID_DEPTH[tier] });
  if (prof) {
    if (prof.foliageScale != null) cfg.foliageScale = (cfg.foliageScale || 1) * prof.foliageScale;
    if (prof.droopOuter != null) cfg.droopOuter = prof.droopOuter;
  }
  return cfg;
}

function generateDaVinciTree(radius, length, depth, cfg, rng) {
  if (depth >= cfg.maxDepth || radius < cfg.minRadiusCutoff) {
    return { radiusBottom: radius, radiusTop: radius * 0.6, length, depth, children: [] };
  }
  const node = { radiusBottom: radius, length, depth, children: [] };
  let numSplits;
  if (cfg.conifer) {
    const lo = cfg.splitMin ?? 3, hi = cfg.splitMax ?? 4;  // whorls
    numSplits = lo + Math.floor(rng() * (hi - lo + 1));
  } else {
    numSplits = rng() < (cfg.splitBias ?? 0.2) ? 3 : 2;    // forks
  }
  const leaderShare = cfg.leaderShare ?? 0.6;

  const cap = Math.pow(radius, cfg.davinciExponent);
  let remaining = cap;
  const childRadii = [];
  for (let i = 0; i < numSplits; i++) {
    if (i === numSplits - 1) {
      childRadii.push(Math.pow(Math.max(0, remaining), 1 / cfg.davinciExponent));
    } else if (cfg.conifer && i === 0) {
      const a = remaining * leaderShare;                  // central leader (monopodial)
      childRadii.push(Math.pow(a, 1 / cfg.davinciExponent)); remaining -= a;
    } else {
      const share = cfg.conifer ? (0.15 + rng() * 0.1) : (0.3 + rng() * 0.25);
      const a = remaining * share;
      childRadii.push(Math.pow(a, 1 / cfg.davinciExponent)); remaining -= a;
    }
  }
  node.radiusTop = Math.pow(
    childRadii.reduce((s, r) => s + Math.pow(r, cfg.davinciExponent), 0),
    1 / cfg.davinciExponent);

  for (let i = 0; i < numSplits; i++) {
    const cr = childRadii[i];
    const cl = length * Math.pow(Math.max(0.05, cr / radius), cfg.lengthScaling);
    const child = generateDaVinciTree(cr, cl, depth + 1, cfg, rng);
    if (cfg.conifer && i === 0) {
      child.angleSpread = cfg.branchAngleBase * 0.08 * (rng() - 0.5);
      child.angleRotation = rng() * Math.PI * 2;
    } else {
      child.angleSpread = cfg.branchAngleBase * (0.8 + rng() * 0.4);
      child.angleRotation = (i * (Math.PI * 2 / numSplits)) + rng() * 0.5;
    }
    node.children.push(child);
  }
  return node;
}

// Walk a skeleton into two merged geometries: woody branches and leaf clusters.
// The canopy is built from many overlapping blobs (rather than one blob per
// tip) so the merged foliage reads as a continuous leaf mass — denser near the
// structural scaffold, finer toward the outer twigs (blob size tapers with
// branch depth).
function treeToGeometry(root, cfg, rng) {
  const branchGeos = [];
  const blobs = [];        // {geo, y} foliage candidates, gated by clear-bole
  const fScale = cfg.foliageScale ?? 1.0;

  function addSeg(node, mat) {
    const seg = new THREE.CylinderGeometry(
      Math.max(0.004, node.radiusTop), Math.max(0.006, node.radiusBottom),
      node.length, 5, 1);
    seg.translate(0, node.length / 2, 0);
    seg.applyMatrix4(mat);
    branchGeos.push(seg);
  }
  // Deciduous: a balloon of 3–5 overlapping flattened spheres at each twig tip
  // (and 1–2 smaller ones at interior junctions) → a full rounded crown. Each
  // blob is tagged with its world Y so the clear-bole pass can strip foliage
  // off the lower trunk after the crown height is known.
  const droopOuter = cfg.droopOuter || 0;     // weeping terminal fringe (birch/willow)
  function addDeciduousCluster(tipMat, depth, terminal) {
    const tipY = tipMat.elements[13];
    const depthScale = Math.max(0.65, 1.0 - depth * 0.08);
    const n = terminal ? qn(3 + Math.floor(rng() * 3)) : qn(1 + Math.floor(rng() * 2));
    const base = (terminal ? 0.20 : 0.15) * depthScale * fScale;
    const spread = (terminal ? 0.22 : 0.16) * fScale;
    // Weeping species hang their outer leaf clusters below the twig and widen
    // them slightly — a cheap, recognizable droop without re-bending branches.
    const dy = terminal ? -droopOuter * 0.13 : 0;
    const dspread = 1 + droopOuter * 0.4;
    for (let i = 0; i < n; i++) {
      const r = base + rng() * 0.14 * depthScale * fScale;
      const s = new THREE.SphereGeometry(r, 5, 4);
      s.scale(1, 0.72 + rng() * 0.2, 1);
      s.translate((rng() - 0.5) * spread * dspread,
                  dy + r * 0.4 + (rng() - 0.2) * 0.1,
                  (rng() - 0.5) * spread * dspread);
      s.applyMatrix4(tipMat);
      blobs.push({ geo: s, y: tipY });
    }
  }
  function walk(node, mat) {
    addSeg(node, mat);
    const tip = mat.clone().multiply(new THREE.Matrix4().makeTranslation(0, node.length, 0));
    const terminal = !node.children.length;
    if (terminal) addDeciduousCluster(tip, node.depth, true);
    else if (node.depth >= 2) addDeciduousCluster(tip, node.depth, false);  // interior fill
    if (terminal) return;
    for (const child of node.children) {
      const rot = new THREE.Matrix4().makeRotationY(child.angleRotation)
        .multiply(new THREE.Matrix4().makeRotationX(child.angleSpread));
      walk(child, tip.clone().multiply(rot));
    }
  }
  walk(root, new THREE.Matrix4());

  // Clear bole: drop leaf clusters below clearBole × crown height so the trunk
  // shows (strongest on slender/aspen forms) — disposing the rejects' buffers.
  const maxY = blobs.reduce((m, b) => Math.max(m, b.y), 0);
  const gate = (cfg.clearBole ?? 0) * maxY;
  const foliageGeos = [];
  for (const b of blobs) {
    if (b.y >= gate) foliageGeos.push(b.geo);
    else b.geo.dispose();
  }

  const branchGeo = branchGeos.length ? mergeGeometries(branchGeos, false) : null;
  const foliageGeo = foliageGeos.length ? mergeGeometries(foliageGeos, false) : null;
  normalizeUnit([branchGeo, foliageGeo]);
  if (foliageGeo) applyFoliageGradient(foliageGeo);
  return { branchGeo, foliageGeo };
}

// Conifer crown (Phase 1): a clean stack of apex-up cone "skirts" up a thin
// central trunk — radius tapering to a spire — instead of a branch skeleton
// with cones at every whorl. Reads as a natural cone, not a spiky star, and is
// markedly lower-poly. Form sets base radius / tier count / droop; tier sets
// the maturity skirt count.
function buildConiferGeo(form, tier, rng, kind) {
  const fp = CONIFER_FORMS[form] || CONIFER_FORMS.oval;
  const kp = CONIFER_KINDS[kind] || CONIFER_KINDS.standard;
  const M = Math.max(2, qn(CONIFER_TIERS[tier] + fp.tiersAdd + kp.tiersAdd));
  const baseR = fp.baseR * kp.baseRMul;
  const droop = fp.droop + kp.droopAdd;
  const segs = Math.max(5, Math.round(8 * kp.segMul));
  const branchGeos = [], foliageGeos = [];
  const H = 1.0, y0 = 0.05, yTop = 0.93;

  const trunk = new THREE.CylinderGeometry(0.012, 0.05, H, 5, 1);
  trunk.translate(0, H / 2, 0);
  branchGeos.push(trunk);

  for (let i = 0; i < M; i++) {
    const f = M === 1 ? 0 : i / (M - 1);            // 0 base … 1 top
    const y = y0 + (yTop - y0) * f;
    const r = (baseR * Math.pow(1 - f, 0.85) + 0.03) * (0.9 + rng() * 0.2);
    const hh = (0.20 + 0.12 * (1 - f)) * (1 + droop);
    const skirt = new THREE.ConeGeometry(r, hh, segs, 1);
    skirt.translate(0, y - hh * (0.5 - droop), 0);  // flare base down (droop)
    skirt.rotateY(rng() * Math.PI);
    foliageGeos.push(skirt);
  }
  const spire = new THREE.ConeGeometry(0.045, 0.15 * kp.spire, 6, 1);
  spire.translate(0, yTop + 0.05, 0);
  foliageGeos.push(spire);

  const branchGeo = mergeGeometries(branchGeos, false);
  const foliageGeo = mergeGeometries(foliageGeos, false);
  normalizeUnit([branchGeo, foliageGeo]);
  applyFoliageGradient(foliageGeo);
  return { branchGeo, foliageGeo };
}

// Pine (Pinus) reads nothing like a spruce/fir cone: a clear lower trunk, then a
// few irregular tufted needle clumps high in the crown with a flattish, open
// top — the scraggly look of jack/lodgepole pine (V1.94). Built as branch +
// foliage geometries like the others so it shares the tree instance pipeline.
function buildPineGeo(form, tier, rng) {
  const branchGeos = [], foliageGeos = [];
  const H = 1.0;
  const trunk = new THREE.CylinderGeometry(0.016, 0.055, H, 6, 1);
  trunk.translate(0, H / 2, 0);
  branchGeos.push(trunk);

  const clumps = Math.max(3, qn(3 + tier));   // more tufts as it matures
  const yBase = 0.48;                          // clear lower trunk
  for (let i = 0; i < clumps; i++) {
    const f = clumps === 1 ? 1 : i / (clumps - 1);
    const y = yBase + (0.9 - yBase) * f + (rng() - 0.5) * 0.05;
    const ang = rng() * Math.PI * 2;
    const reach = (0.17 + rng() * 0.12) * (1 - f * 0.45);   // tighter near the top → flat crown
    const bx = Math.cos(ang) * reach, bz = Math.sin(ang) * reach;
    const r = (0.13 + rng() * 0.07) * (1 - f * 0.25);
    const tuft = new THREE.SphereGeometry(r, 6, 5);
    tuft.scale(1.25, 0.62, 1.25);                            // flattened needle pad
    tuft.translate(bx, y, bz);
    foliageGeos.push(tuft);
    const blen = reach + 0.04;                               // short branch out to the tuft
    const seg = new THREE.CylinderGeometry(0.006, 0.013, blen, 4, 1);
    seg.translate(0, blen / 2, 0);
    seg.applyMatrix4(new THREE.Matrix4().makeRotationY(ang)
      .multiply(new THREE.Matrix4().makeRotationZ(1.05)));
    seg.translate(0, y - 0.02, 0);
    branchGeos.push(seg);
  }
  const top = new THREE.SphereGeometry(0.12, 6, 5);
  top.scale(1.1, 0.7, 1.1); top.translate(0, 0.93, 0);
  foliageGeos.push(top);

  const branchGeo = mergeGeometries(branchGeos, false);
  const foliageGeo = mergeGeometries(foliageGeos, false);
  normalizeUnit([branchGeo, foliageGeo]);
  applyFoliageGradient(foliageGeo);
  return { branchGeo, foliageGeo };
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

