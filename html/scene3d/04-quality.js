// Part of the Site & Pattern 3D viewer, split out of the former
// single html/scene3d.html <script> (V2.24). Loaded as an ordered
// CLASSIC script by the bootstrap in scene3d.html — it shares the
// global scope with its siblings (THREE/OrbitControls/mergeGeometries
// are globals set by the bootstrap), so load ORDER is dependency
// order. Do not add ES `import`/`export` here.

// ── Detail / quality (V1.94) ────────────────────────────────────────────────
// One global knob scales BUILD-TIME geometry density only (blade/blob/tier/tuft
// counts) — never per-frame work, which stays instanced.
//
// V2.34 renamed the three levels Stylised / Balanced / Lifelike, because level 0
// stopped being "the same look, thinner" and became a style of its own (see
// 01b-surface.js setStylised for the argument). "Low" implied worse; Stylised is
// a choice, and on a weak machine it is also by far the cheapest scene the app
// can draw.
let QUALITY = 1;                      // 0 Stylised · 1 Balanced · 2 Lifelike
function qn(n) {                      // scale + round a count, never below 1
  const f = QUALITY === 0 ? 0.6 : (QUALITY === 2 ? 1.35 : 1.0);
  return Math.max(1, Math.round(n * f));
}

// Whether to reach for the baked GLB library at all. Stylised deliberately does
// not: the GLB set IS the realism (real leaf cards, branch skeletons, bark
// grain), so the mode is expressed by falling back to the procedural builders —
// which have always been the library's fallback path and are therefore always
// exercised, never a second renderer that rots.
function useGLB() { return !STYLISED; }

// One low-poly foliage mass — a faceted icosahedron (not a smooth sphere)
// squashed to an ellipsoid by `shape`, so a clump reads as angular leaf masses
// rather than blobs while staying very cheap (20 faces).
function makeFoliageMass(rng, r, shape) {
  const m = new THREE.IcosahedronGeometry(r, 0);
  m.scale(shape[0] * (0.85 + rng() * 0.3),
          shape[1] * (0.85 + rng() * 0.3),
          shape[2] * (0.85 + rng() * 0.3));
  m.rotateY(rng() * Math.PI);
  return m;
}

// A shrub as a multi-stem woody clump (V1.96): a few ascending stems splayed
// from a shared base, each clothed with foliage along its upper length, the whole
// silhouette set by the species' growth form (vase / spreading / mound / thicket
// / irregular). Returns {foliageGeo, stemGeo} so the woody stems carry their own
// bark (or red-osier) colour — no more generic dome.
//
// V2.29: where the species records its own leaf characters, each foliage position
// becomes a small cluster of REAL leaves of that outline and size instead of a
// faceted icosahedron — the "lollipop" look in the shrub screenshots was those
// ellipsoids. Without morphology it stays on the tuned masses, which is honest:
// no data, no invented detail.
const _CLUSTER_LEAVES = 7;         // per foliage position, before quality/cost
function buildShrubGeo(rng, profile, morph) {
  const prof = profile || {};
  const m = morph || {};
  const F = SHRUB_FORMS[prof.form] || SHRUB_FORMS.spreading;
  const fineMul = prof.fine ? 0.82 : 1;
  const stemGeos = [], foliageGeos = [];
  const shape = m.shape || '';
  // A shrub is metres tall with centimetre leaves, so these are far smaller
  // fractions of the unit frame than a forb's (flora_shrubs.build_shrub).
  const leafLen = [0.055, 0.085, 0.13][Math.max(0, Math.min(2, m.grain == null ? 1 : m.grain))]
    * (isCompoundShape(shape) ? 1.5 : 1);
  const nCluster = shape
    ? qn(Math.round(_CLUSTER_LEAVES * leafCountScale(shape))) : 0;
  // A cluster of leaves radiating from one attachment point, filling the volume
  // the faceted mass used to occupy.
  const foliageAt = (at, r) => {
    if (!shape) {
      const mass = makeFoliageMass(rng, r, F.shape);
      mass.translate(at.x, at.y, at.z);
      return [mass];
    }
    const out = [];
    for (let i = 0; i < nCluster; i++) {
      const az = i * 2.39996 + rng() * 0.4;
      const lf = makeBladeOrLeaf(rng, leafLen, leafWidthFor(shape, leafLen),
                                 0.7 + rng() * 0.6, az, null, shape);
      lf.translate(at.x + Math.cos(az) * r * 0.5, at.y + (rng() - 0.5) * r,
                   at.z + Math.sin(az) * r * 0.5);
      out.push(lf);
    }
    return out;
  };

  const nStems = qn(F.stems[0] + Math.floor(rng() * (F.stems[1] - F.stems[0] + 1)));
  for (let i = 0; i < nStems; i++) {
    const az = (i / nStems) * Math.PI * 2 + rng() * 0.7;
    const splay = F.splay * (0.6 + rng() * 0.8);            // lean from vertical
    const h = F.stemH[0] + rng() * (F.stemH[1] - F.stemH[0]);
    const rad = 0.016 + rng() * 0.012;
    const rot = new THREE.Matrix4().makeRotationY(az)
      .multiply(new THREE.Matrix4().makeRotationZ(splay));
    const stem = new THREE.CylinderGeometry(rad * 0.4, rad, h, 4, 1);
    stem.translate(0, h / 2, 0);
    stem.applyMatrix4(rot);
    stemGeos.push(stem);
    // foliage masses spaced along the upper portion of the stem (start..tip)
    const nMass = qn(F.masses[0] + Math.floor(rng() * (F.masses[1] - F.masses[0] + 1)));
    for (let j = 0; j < nMass; j++) {
      const t = F.start + (1 - F.start) * (nMass === 1 ? 0.7 : j / (nMass - 1));
      const at = new THREE.Vector3(0, h * t, 0).applyMatrix4(rot);
      const r = (F.massR[0] + rng() * (F.massR[1] - F.massR[0])) * fineMul;
      at.x += (rng() - 0.5) * 0.08; at.z += (rng() - 0.5) * 0.08;
      for (const g of foliageAt(at, r)) foliageGeos.push(g);
    }
  }
  // A low basal mound fills the bottom of dense forms (mound/spreading/thicket).
  if (F.basal) {
    const nb = qn(2 + Math.floor(rng() * 2));
    for (let i = 0; i < nb; i++) {
      const r = (0.15 + rng() * 0.08) * fineMul;
      const at = new THREE.Vector3((rng() - 0.5) * 0.34, 0.1 + rng() * 0.12,
                                   (rng() - 0.5) * 0.34);
      for (const g of foliageAt(at, r)) foliageGeos.push(g);
    }
  }

  const foliageGeo = mergeGeometries(foliageGeos, false);
  const stemGeo = mergeGeometries(stemGeos, false);
  normalizeUnit([foliageGeo, stemGeo]);     // shared 0..1 frame
  applyFoliageGradient(foliageGeo);
  return { foliageGeo, stemGeo };
}

// A herbaceous plant built to its growth form (V1.98): leafy erect stems
// (fireweed), a low ferny mound (yarrow), a basal leaf rosette under wiry stalks
// (fleabane), a bushy clump, a strappy grassy tuft, a low mat, or arching fern
// fronds. `form` is a HERB_FORMS entry. Returns ONE green geometry — herb stems
// are green, so no separate woody-stem colour is needed.
const _rint = (rng, lo, hi) => lo + Math.floor(rng() * (hi - lo + 1));
// makeBlade leaves carry only a position attribute, so a stem cylinder must be
// stripped to match before mergeGeometries (which requires identical attribute
// sets); normalizeUnit recomputes normals on the merged result.
function _stem(rBot, rTop, h, rot) {
  const s = new THREE.CylinderGeometry(rTop, rBot, h, 4, 1);
  s.translate(0, h / 2, 0); s.applyMatrix4(rot);
  s.deleteAttribute('normal'); s.deleteAttribute('uv');
  return s;
}
// `morph` is the species' own leaf characters (schema v47/v48): `shape` its blade
// outline, `grain` its leaf size against its mature height, `arrangement` whether
// leaves sit in opposite pairs, whorls of three, or a spiral. Omit it and the
// form's authored defaults apply, which is exactly the pre-V2.29 look.
function buildPerennialGeo(rng, form, morph) {
  const F = form || HERB_FORMS.clump;
  const m = morph || {};
  if (STYLISED) return stylisedHerbGeo(rng, F);
  const geos = [];
  const shape = m.shape || F.shape;
  const lL = F.leaf[0] * GRAIN_LEAF_SCALE[Math.max(0, Math.min(2, m.grain == null ? 1 : m.grain))];
  // Width follows the OUTLINE, not the form: a 20 cm arrowhead balsamroot leaf
  // and a 20 cm iris strap are the same length and nothing like the same leaf.
  const lW = m.shape ? leafWidthFor(shape, lL) : F.leaf[1];
  // Opposite leaves come in pairs at one node and whorled in rings of three;
  // alternate ones spiral by the golden angle. That is the field mark separating
  // a penstemon from a goldenrod at a glance.
  const perNode = m.arrangement === 'opposite' ? 2
    : (m.arrangement === 'whorled' ? 3 : 1);
  const cost = leafCountScale(shape);

  // Leafy stems: a stem cylinder with leaves spaced up its upper length.
  const nStems = F.stems[1] ? qn(_rint(rng, F.stems[0], F.stems[1])) : 0;
  for (let i = 0; i < nStems; i++) {
    const az0 = (i / Math.max(1, nStems)) * Math.PI * 2 + rng() * 0.7;
    const splay = F.splay * (0.5 + rng());
    const h = 0.7 + rng() * 0.3;
    const rot = new THREE.Matrix4().makeRotationY(az0)
      .multiply(new THREE.Matrix4().makeRotationZ(splay));
    geos.push(_stem(0.012, 0.006, h, rot));
    const nLeaf = qn(_rint(rng, F.perStem[0], F.perStem[1]) * cost);
    const nodes = Math.max(1, Math.round(nLeaf / perNode));
    for (let j = 0; j < nodes; j++) {
      const t = F.leafFrom + (1 - F.leafFrom) * (j / Math.max(1, nodes - 1));
      const at = new THREE.Vector3(0, h * t, 0).applyMatrix4(rot);
      const baseAz = (perNode > 1 ? j * 1.5708 : j * 2.39996) + az0;
      for (let k = 0; k < perNode; k++)
        geos.push(makeBladeOrLeaf(rng, lL, lW, F.leafTilt,
                                  baseAz + k * Math.PI * 2 / perNode, at, shape));
    }
  }

  // Basal leaves: a rosette / ferny mound / strap tuft / mat at the ground.
  if (F.basal) {
    const nb = qn(_rint(rng, F.basal[0], F.basal[1]) * cost);
    for (let i = 0; i < nb; i++) {
      const az = rng() * Math.PI * 2;
      const len = lL * (F.fine ? 0.6 + rng() * 0.5 : 1);
      const lf = makeBladeOrLeaf(rng, len, lW, F.leafTilt * (0.8 + rng() * 0.4),
                                 az, null, shape);
      const rr = (F.low ? 0.18 : 0.1) * rng();
      lf.translate(Math.cos(az) * rr, (F.low ? 0.01 : 0.02), Math.sin(az) * rr);
      geos.push(lf);
    }
  }

  // Bare flower stalks rising above the foliage (the flower sprite lands on top).
  if (F.stalks) {
    const ns = qn(_rint(rng, F.stalks[0], F.stalks[1]));
    for (let i = 0; i < ns; i++) {
      const h = 0.75 + rng() * 0.25;
      const lean = 0.05 + rng() * 0.18;
      const rot = new THREE.Matrix4().makeRotationY(rng() * Math.PI * 2)
        .multiply(new THREE.Matrix4().makeRotationZ(lean));
      geos.push(_stem(0.008, 0.005, h, rot));
    }
  }

  const g = mergeGeometries(geos, false);
  normalizeUnit([g]);
  applyFoliageGradient(g);
  return g;
}

// Built once, reused across every scene rebuild (deterministic seeds).
// ARCH holds the cheap shrub/peren/ground variant arrays; trees are built
// lazily and memoised by (class, form, tier, sub) in TREE_CACHE.
let ARCH = null;
let MATS = null;     // shared plant materials (per-instance colour does the rest)
let SHADOW_TEX = null;
const TREE_SUBVARS = 3;    // distinct random branchings per species, so a stand
                           // of one species reads as individuals, not clones

// A tree's structural tier — which is a SIZE class, not a growth stage. The
// asset set carries three builds per species and this picks between them from
// the plant's height right now (which already folds the growth year in, since
// height_m = mature height x the year's growth factor).
//
// It used to key off scale_factor alone, i.e. "how far along is this tree", so
// every mature tree got the most complex build and every young one the
// sparsest — regardless of whether "mature" meant a 3 m pin cherry or a 25 m
// white spruce. That reads especially wrong on conifers: a young spruce is not
// a sparse adult, it is a small DENSE cone foliated to the ground, and the
// sparse build drew a 5 m sapling as a bare mast (V2.29). Growth still moves a
// tree up through the tiers — it just arrives there by getting bigger.
const _TIER_H_M = [3, 9];        // <3 m small · 3–9 m medium · >9 m large
function tierFor(p) {
  const h = (p && p.height_m) || 0;
  return h < _TIER_H_M[0] ? 0 : (h < _TIER_H_M[1] ? 1 : 2);
}

// Horizontal instance scale for an archetype whose authored proportions were
// preserved by normalizeUnit: its geometry is `2·unitHalfWidth` wide at height
// 1, so dividing lands the instance on exactly canopy_m across — and the two
// axes only agree (leaving foliage clumps round) when the archetype was
// authored at the species' real height/canopy. 0.5 is the pre-V2.29 squashed
// frame, so an archetype without the mark behaves exactly as it always did.
function unitXZ(geo, canopy_m) {
  const hw = (geo && geo.userData && geo.userData.unitHalfWidth) || 0.5;
  return canopy_m / (2 * hw);
}

// Per-individual sub-variation from position (+ species id): two trees of the
// same species standing apart get different branchings, so a grove looks
// natural rather than procedurally stamped.
function indHash(p) {
  const xi = Math.round((p.x || 0) * 10), zi = Math.round((p.y || 0) * 10);
  return Math.abs(((xi * 73856093) ^ (zi * 19349663) ^ hashPid(p.plant_id)) | 0);
}

// Lazily build + cache one tree archetype, keyed by (class, form, tier, sub).
// Only the combinations a scene actually uses are generated. Conifers are
// clean cone stacks; deciduous are Da Vinci crowns shaped by their form.
const TREE_CACHE = new Map();
function getTreeArch(cls, prof, form, tier, sub) {
  const ck = cls === 'conifer' ? (prof.conifer || 'standard') : 'd';
  // QUALITY is in the key so Low/Med/High keep distinct cached archetypes.
  const key = cls + '_' + ck + '_' + prof.id + '_' + form + '_' + tier + '_' + sub + '_q' + QUALITY;
  let a = TREE_CACHE.get(key);
  if (a) return a;
  // Blender GLB archetype first (09-models.js), procedural as the fallback.
  a = (useGLB() && window.glbTreeArch
       && window.glbTreeArch(cls, ck, prof.id, form, tier)) || null;
  if (!a) {
    if (cls === 'conifer') {
      const seed = 5000 + (_FORM_SEED[form] || 0) + tier * 11 + sub * 191 + (_CK_SEED[ck] || 0);
      // Both pine kinds take the open tufted builder; everything else is a
      // whorled cone. (The scraggly-vs-spire difference between jack pine and
      // lodgepole is baked into the GLB; the procedural fallback draws them
      // alike, which is the honest limit of the fallback set.)
      a = (ck === 'pine' || ck === 'pine_jack')
        ? buildPineGeo(form, tier, mulberry32(seed))
        : buildConiferGeo(form, tier, mulberry32(seed), ck);
    } else {
      const cfg = decidCfg(form, tier, prof);
      const seed = 100 + (_FORM_SEED[form] || 0) + tier * 11 + sub * 191 + prof.id.charCodeAt(0);
      a = treeToGeometry(generateDaVinciTree(0.06, 0.42, 0, cfg, mulberry32(seed)),
                         cfg, mulberry32(seed + 7));
    }
  }
  TREE_CACHE.set(key, a);
  return a;
}

// Which groundcover unit a species gets: its own (blade class × grain class),
// looked up in the manifest. Falls back to the plant-id hash when there are no
// baked models, where the units really are interchangeable procedural draws.
// Which aspect unit a grass / aquatic / vine gets: its own height ÷ canopy,
// looked up in the manifest. Falls back to the plant-id hash when there are no
// baked models — the procedural fallback really does draw three interchangeable
// random tufts, so a hash is the honest answer there.
function aspectBucket(p, kind) {
  const i = useGLB() && window.glbLayerVariantIndex
    ? window.glbLayerVariantIndex(kind, aspectVariantKeyFor(p, kind))
    : null;
  return i == null ? hashPid(p.plant_id) : i;
}

function groundcoverBucket(p) {
  const i = useGLB() && window.glbLayerVariantIndex
    ? window.glbLayerVariantIndex('groundcover', variantKeyFor(p, 'groundcover'))
    : null;
  return i == null ? hashPid(p.plant_id) : i;
}

function buildArchetypes() {
  if (ARCH) return;
  // Shrubs (SHRUB_CACHE) and herbs (HERB_CACHE) are built per-profile on demand;
  // the rest are the cheap shared variant arrays.
  const ground = [], grass = [], aquatic = [], vine = [];
  const glb = (kind, i) =>
    useGLB() && window.glbLayerArch && window.glbLayerArch(kind, i);
  // Groundcover ships one unit per (blade class × grain class) its 32 species
  // use, so the count comes from the manifest rather than a hard-coded 2. Two
  // procedural seeds remain the fallback when there are no baked models.
  const nGround = (useGLB() && window.glbLayerCount
                   && window.glbLayerCount('groundcover')) || 0;
  if (nGround) {
    for (let i = 0; i < nGround; i++) ground.push(glb('groundcover', i));
  } else {
    [331, 379].forEach((sd) => ground.push(buildGroundcoverGeo(mulberry32(sd))));
  }
  [421, 457, 503].forEach((sd, i) =>
    grass.push(glb('grass', i) || buildGrassGeo(mulberry32(sd))));
  [541, 587, 631].forEach((sd, i) =>
    aquatic.push(glb('aquatic', i) || buildAquaticGeo(mulberry32(sd))));
  [661, 707, 743].forEach((sd, i) =>
    vine.push(glb('vine', i) || buildVineGeo(mulberry32(sd))));
  ARCH = { ground, grass, aquatic, vine };
}

// Presets for the surfaces that vary BY SPECIES (F63). `surfaceMaterial(preset,
// cls)` builds one material per (preset × class) on first use — a birch's papery
// bark and an oak's furrowed bark are genuinely different shaders' worth of
// look, and plants are already bucketed into one InstancedMesh per archetype
// variant, so this is one lookup per bucket rather than a per-plant cost.
const MAT_PRESETS = {
  bark: { key: 'bark', detailKind: 'bark', roughness: 0.92, wind: 0.015,
          vertexColors: true, detailScale: 1.0, detailAmount: 0.5 },
  crown: { key: 'crown', detailKind: 'leaf', roughness: 0.85, wind: 0.07,
           vertexColors: true, doubleSide: true, detailScale: 9.0,
           detailAmount: 0.34 },
  shrubLeaf: { key: 'shrubLeaf', detailKind: 'leaf', roughness: 0.82,
               wind: 0.06, vertexColors: true, flatShading: true,
               doubleSide: true, detailScale: 12.0, detailAmount: 0.30 },
  herbLeaf: { key: 'herbLeaf', detailKind: 'leaf', roughness: 0.8, wind: 0.09,
              vertexColors: true, doubleSide: true, detailScale: 14.0,
              detailAmount: 0.28 },
  // Conifers wear needles, which have one surface and no class axis — their one
  // visible mark is the pale stomatal band running the needle's length.
  //
  // `wind` is also the STIFFNESS CLASS (F68). It always varied by material and
  // nothing said why; the values are now deliberate and ordered the way the
  // plants are: a trunk (0.015) is rigid, a mature spruce's needle crown (0.03)
  // barely moves in wind that has a grass blade (0.11) lying flat, a broadleaf
  // crown (0.07) tosses, and a forb leaf (0.09) flutters. Multiplied by the
  // site's real wind speed through uWindAmp, so a calm June day and a 40 km/h
  // chinook are visibly different weather on the same yard.
  needle: { key: 'needle', detailKind: 'needle', roughness: 0.88, wind: 0.03,
            vertexColors: true, doubleSide: true, detailScale: 22.0,
            detailAmount: 0.30 },
};

function ensurePlantMats() {
  if (MATS) return;
  if (!SHADOW_TEX) SHADOW_TEX = makeShadowTexture();
  MATS = {
    branch:  plantMaterial({ roughness: 0.92, wind: 0.015,
               detail: 'bark.furrowed', detailScale: 1.0, detailAmount: 0.5 }),
    // Tree crowns became part-ribbon in V2.29: the OUTERMOST clumps are now
    // rosettes of real leaf cards (assetlib/flora_trees.py) so a birch's
    // silhouette is made of birch leaves, while interior clumps stay closed
    // ellipsoids. Mixed geometry, so it takes the ribbon's rule — the first
    // build with cards on FrontSide drew every broadleaf crown almost black,
    // which is the same bug the shrubs had, one archetype family later. When
    // geometry changes KIND, every material applied to it is unreviewed.
    foliage: surfaceMaterial(MAT_PRESETS.crown, 'matte', true),
    shrub:   plantMaterial({ roughness: 0.85, wind: 0.06, vertexColors: true,
               detail: 'leaf.matte', detailScale: 11.0, detailAmount: 0.30 }),
    // Shrub foliage is now REAL LEAVES — flat ribbons (V2.29) — where the older
    // faceted masses were closed icosahedra. A solid can be FrontSide, which is
    // what this material was; a flat ribbon under backface culling is INVISIBLE
    // from behind, so the V2.29 shrub rebuild silently deleted most of every
    // shrub's foliage and the whole family rendered as bare wiry canes in
    // midsummer. Every geometry check passed — the leaves were built, budgeted,
    // sized and positioned correctly, and simply not drawn.
    // Flat-shaded still, so the procedural fallback's faceted masses (used where
    // a species records no leaf shape) stay crisp low-poly clumps (V1.96).
    shrubFoliage: surfaceMaterial(MAT_PRESETS.shrubLeaf, 'matte', true),
    // Flat leaf blades for herbaceous plants (V1.98) — double-sided so a leaf
    // shows from both faces, gentle sway.
    leaf:    surfaceMaterial(MAT_PRESETS.herbLeaf, 'matte', true),
    // Flat grass/reed blades read from both sides and catch top light via
    // lifted normals (V1.92) — lush tufts rather than thin spindly stalks.
    blade:   plantMaterial({ roughness: 0.72, wind: 0.11, vertexColors: true,
               doubleSide: true, detail: 'leaf.matte', detailScale: 16.0,
               detailAmount: 0.26 }),
    simple:  plantMaterial({ roughness: 0.9, wind: 0.06 }),
    ground:  plantMaterial({ roughness: 0.95, wind: 0.02, vertexColors: true }),
    // Slightly lighter than pre-V2.12 — ACES tone mapping deepens darks.
    shadow:  new THREE.MeshBasicMaterial({ map: SHADOW_TEX, transparent: true,
               depthWrite: false, color: 0x2b3a20, opacity: 0.7 }),
  };
}

// Unit geometries (height 1, half-width 0.5) for the simpler layers.
const GEO = {
  cone:   new THREE.ConeGeometry(0.5, 1, 7).translate(0, 0.5, 0),
  shadow: new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2),
};

const _isDecid = (ft) => ft !== 'evergreen';   // unknown ⇒ deciduous-ish
const _bareMonth = (m) => (m >= 11 || m <= 3);

// Spread visualisation (F35): a self-sowing / rhizomatous plant scatters
// offspring around the parent that keep accumulating as the years advance — a
// colony creeping outward, not a one-time burst. Offspring positions are
// deterministic per (plant, k) — a golden-angle spiral with sqrt-spaced radii
// for even areal density — so as `year` reveals more of them (K below), the
// ones already shown stay put and new ones appear at the growing frontier.
// Returns {dx, dz (scene metres from the plant), mul (archetype scale)} per
// instance; non-spreaders get a single full-size placement.
const _NO_SPREAD = [{ dx: 0, dz: 0, mul: 1 }];
const _GOLDEN = Math.PI * (3 - Math.sqrt(5));   // golden angle ≈ 137.5°
function spreadPlacements(p, year) {
  const rate = p.spread_rate || 0;              // 0 none · 0.3 slow · 0.6 self-seed · 1 aggressive
  if (rate <= 0.01) return _NO_SPREAD;
  const cap = p.plant_type === 'groundcover' ? 14 : 10;   // bound instance count
  // ~one new offspring every (3 / rate) years → continuous, year-driven spread.
  const K = Math.min(cap, Math.round(rate * (year || 0) / 3));
  if (K <= 0) return _NO_SPREAD;
  const c = Math.max(0.3, p.canopy_m);
  const reach = c * (1.4 + rate * 2.2);         // frontier grows with aggressiveness
  const base = hashPid(p.plant_id) % 97;
  const phase = (hashPid(p.plant_id) % 360) * Math.PI / 180;
  const out = [{ dx: 0, dz: 0, mul: 1 }];
  for (let k = 1; k <= K; k++) {
    const f = k / cap;                          // 0 near … 1 frontier (stable per k)
    const j = Math.sin((k + base) * 12.9898) * 43758.5453;
    const jr = 0.78 + 0.22 * (j - Math.floor(j));   // deterministic radial jitter
    const rr = reach * Math.sqrt(f) * jr;
    const ang = phase + k * _GOLDEN;
    out.push({ dx: Math.cos(ang) * rr, dz: Math.sin(ang) * rr,
               mul: 0.72 - 0.34 * f });          // newer/outer offspring are smaller
  }
  return out;
}

// Build one simple plant layer: bucket items across `variants` archetypes,
// instance each bucket (including spread offspring), scale per item via
// scaleOf(p) → [sx, sy, sz]. `noRot` keeps groundcover flat with no Y spin.
// `bucketOf(p)` optionally decides which archetype unit a plant gets. Without
// it, layers spread over their variants by plant-id hash — right for grass,
// aquatic and vine, whose units are interchangeable random draws. Groundcover
// units are NOT interchangeable: each carries a different leaf outline, so its
// bucket is the species' own (blade × grain) key. Passing a hash there would
// hand a strawberry a linear-leaved mat.
function buildLayer(list, variants, mat, archOf, scaleOf, month, year, noRot,
                    terrain, bucketOf) {
  if (!list || !list.length) return;
  const buckets = Array.from({ length: variants }, () => []);
  for (const p of list) {
    const b = bucketOf ? bucketOf(p) : hashPid(p.plant_id) % variants;
    buckets[((b % variants) + variants) % variants].push(p);
  }
  buckets.forEach((items, v) => {
    if (!items.length) return;
    const places = items.map(p => spreadPlacements(p, year));
    const total = places.reduce((s, pl) => s + pl.length, 0);
    const arch = archOf(v);
    const mesh = instancedMesh(arch, total, mat);
    const names = new Array(total), ids = new Array(total);
    let idx = 0;
    items.forEach((p, ii) => {
      // scaleOf gives [canopy_m, height_m, canopy_m]; the horizontal pair is
      // divided by the archetype's authored width (unitXZ).
      const [cx, sy, cz] = scaleOf(p);
      const sx = unitXZ(arch, cx), sz = unitXZ(arch, cz);
      const rotY0 = noRot ? 0 : (indHash(p) % 628) / 100;
      const col = fadeColor(witherColor(seasonalColor(p.color, p.foliage_type, month, p.fall_color), p.health), p.opacity);
      places[ii].forEach((pl, k) => {
        const m = pl.mul;
        const wx = p.x + pl.dx, wy = p.y + pl.dz;
        const rotY = noRot ? 0 : rotY0 + (k ? pl.dx : 0);
        const gy = terrainHeightAt(wx, wy, terrain);
        setInst2(mesh, idx, wx, gy, -wy,
                 sx * m, sy * (noRot ? 1 : m), sz * m, rotY, col);
        names[idx] = p.common_name || '';
        ids[idx] = p.plant_id;
        idx++;
      });
    });
    mesh.userData.pick = names;
    mesh.userData.pickId = ids;
    plantsGroup.add(mesh);
  });
}

// Shrub archetypes are profile-specific (growth form, red-stem dogwood…), so
// they're cached by (profile × variant × quality) like trees rather than the
// flat ARCH.shrub array. buildShrubGeo returns {foliageGeo, stemGeo} — the
// faceted leaf masses and the woody stems, each shaded/coloured separately.
const SHRUB_VARIANTS = 3;
const SHRUB_CACHE = new Map();
// `morph` is the species' leaf characters and `vkey` their baked-variant name
// (02-plants.js variantKeyFor). Both belong in the cache key: they select a
// DIFFERENT geometry, so leaving them out would hand a rose the dogwood's leaves
// whenever the two shared a profile and variant.
function getShrubArch(prof, v, vkey, morph) {
  const key = prof.id + '_' + v + '_' + vkey + '_q' + QUALITY;
  let a = SHRUB_CACHE.get(key);
  if (a) return a;
  a = (useGLB() && window.glbShrubArch && window.glbShrubArch(prof.form, vkey)) ||
      buildShrubGeo(mulberry32(13 + v * 97 + prof.id.charCodeAt(0) * 7), prof,
                    morph);
  SHRUB_CACHE.set(key, a);
  return a;
}

// Herb archetypes are growth-form specific (HERB_CACHE), cached by
// (form × variant × quality). One green geometry per form (leaves + stems +
// stalks are all herbaceous).
const HERB_VARIANTS = 3;
const HERB_CACHE = new Map();
function getHerbArch(formName, v, vkey, morph) {
  const key = formName + '_' + v + '_' + vkey + '_q' + QUALITY;
  let a = HERB_CACHE.get(key);
  if (a) return a;
  a = (useGLB() && window.glbHerbArch && window.glbHerbArch(formName, vkey)) ||
      buildPerennialGeo(mulberry32(29 + v * 89 + formName.charCodeAt(0) * 7),
                        HERB_FORMS[formName], morph);
  HERB_CACHE.set(key, a);
  return a;
}

// The leaf characters both procedural builders read, gathered in one place so the
// scene-record field names appear once. `arrangement`/`shape` stay empty where
// the seed data has nothing to say, and the builders keep their tuned defaults —
// an honest empty beats an invented leaf.
// Stylised passes NO shape, which is the same switch a species with no recorded
// morphology already takes: the builders fall back to their form's tuned
// defaults, and buildShrubGeo's foliage positions become faceted masses again
// (makeFoliageMass) rather than clusters of real leaves. Grain still varies,
// because a plant with big leaves reads bigger-leaved even as a diagram.
function morphOf(p, family) {
  return {
    shape: STYLISED ? '' : (p.leaf_shape || ''),
    arrangement: STYLISED ? '' : (p.leaf_arrangement || '').toLowerCase(),
    grain: grainClassFor(p.leaf_size_cm, p.mature_height_m || p.height_m, family),
  };
}

function buildHerbLayer(list, month, year, terrain) {
  if (!list || !list.length) return;
  const buckets = {};
  for (const p of list) {
    const formName = herbFormFor(p);
    const v = hashPid(p.plant_id) % HERB_VARIANTS;
    // The variant key is part of the bucket key because it changes the geometry:
    // two species sharing a form but not a leaf would otherwise be instanced from
    // whichever of them the bucket happened to build first.
    const vkey = variantKeyFor(p, 'herb', formName);
    // Leaf surface joins the key for the same reason it does on trees: one mesh,
    // one material. It pays off most here — the woolly and silvery forbs
    // (pussytoes, pearly everlasting, the sages, silky lupine) are where a
    // reader's eye actually goes looking for that character.
    const surf = leafSurfaceFor(p);
    const bk = formName + '_' + v + '_' + vkey + '_' + surf;
    (buckets[bk] = buckets[bk]
      || { formName, v, vkey, surf, morph: morphOf(p, 'herb'), items: [] })
      .items.push(p);
  }
  for (const key in buckets) {
    const { formName, v, vkey, morph, surf, items } = buckets[key];
    const arch = getHerbArch(formName, v, vkey, morph);
    const places = items.map(p => spreadPlacements(p, year));
    const total = places.reduce((s, pl) => s + pl.length, 0);
    const mesh = instancedMesh(arch, total,
      surfaceMaterial(MAT_PRESETS.herbLeaf, surf, true));
    const names = new Array(total), ids = new Array(total);
    let idx = 0;
    items.forEach((p, ii) => {
      const c = unitXZ(arch, Math.max(0.15, p.canopy_m));
      const h = Math.max(0.08, p.height_m);
      const rotY0 = (indHash(p) % 628) / 100;
      const col = fadeColor(witherColor(seasonalColor(p.color, p.foliage_type, month, p.fall_color), p.health), p.opacity);
      places[ii].forEach((pl, k) => {
        const m = pl.mul, x = p.x + pl.dx, wy = p.y + pl.dz;
        const rotY = rotY0 + (k ? pl.dx : 0);
        const gy = terrainHeightAt(x, wy, terrain);
        setInst2(mesh, idx, x, gy, -wy, c * m, h * m, c * m, rotY, col);
        names[idx] = p.common_name || '';
        ids[idx] = p.plant_id;
        idx++;
      });
    });
    mesh.userData.pick = names;
    mesh.userData.pickId = ids;
    plantsGroup.add(mesh);
  }
}

function buildShrubLayer(list, month, year, terrain) {
  if (!list || !list.length) return;
  const buckets = {};
  for (const p of list) {
    const prof = shrubProfileFor(p);
    const v = hashPid(p.plant_id) % SHRUB_VARIANTS;
    const vkey = variantKeyFor(p, 'shrub');
    const bark = barkClassFor(p), surf = leafSurfaceFor(p);
    const bk = prof.id + '_' + v + '_' + vkey + '_' + bark + '_' + surf;
    (buckets[bk] = buckets[bk]
      || { prof, v, vkey, bark, surf, morph: morphOf(p, 'shrub'), items: [] })
      .items.push(p);
  }
  for (const key in buckets) {
    const { prof, v, vkey, morph, bark, surf, items } = buckets[key];
    const arch = getShrubArch(prof, v, vkey, morph);
    const places = items.map(p => spreadPlacements(p, year));
    const total = places.reduce((s, pl) => s + pl.length, 0);
    const foliage = instancedMesh(arch.foliageGeo, total,
      surfaceMaterial(MAT_PRESETS.shrubLeaf, surf));
    const stems = arch.stemGeo
      ? instancedMesh(arch.stemGeo, total,
                      surfaceMaterial(MAT_PRESETS.bark, bark,
                                      !!arch.vertexColorBark))
      : null;
    // Woody stems take the species' own bark colour where the seed data has
    // one — which is how red-osier dogwood gets its red, generalised from the
    // genus special case that used to be the only way to say so.
    const stemHex = items.length && items[0].bark_color
      ? items[0].bark_color : (prof.redStems ? '#b5402e' : '#6b5236');
    const names = new Array(total), ids = new Array(total);
    let idx = 0;
    items.forEach((p, ii) => {
      const c = unitXZ(arch.foliageGeo, Math.max(0.25, p.canopy_m));
      const h = Math.max(0.2, p.height_m);
      const rotY0 = (indHash(p) % 628) / 100;
      const col = fadeColor(witherColor(seasonalColor(p.color, p.foliage_type, month, p.fall_color), p.health), p.opacity);
      const scol = fadeToward(stemHex, p.opacity);
      places[ii].forEach((pl, k) => {
        const m = pl.mul, x = p.x + pl.dx, wy = p.y + pl.dz;
        const rotY = rotY0 + (k ? pl.dx : 0);
        const gy = terrainHeightAt(x, wy, terrain);
        setInst2(foliage, idx, x, gy, -wy, c * m, h * m, c * m, rotY, col);
        if (stems) setInst2(stems, idx, x, gy, -wy, c * m, h * m, c * m, rotY, scol);
        names[idx] = p.common_name || '';
        ids[idx] = p.plant_id;
        idx++;
      });
    });
    foliage.userData.pick = names;
    foliage.userData.pickId = ids;
    // Pick from the stems too, the way trees already do from the trunk: a
    // deciduous shrub in winter is nothing BUT stems, and it should still name
    // and open on a click.
    if (stems) { stems.userData.pick = names; stems.userData.pickId = ids; }
    plantsGroup.add(foliage);
    if (stems) plantsGroup.add(stems);
  }
}

function buildPlants(group, plants, month, year, terrain) {
  if (plantsGroup) { disposeDesignGroup(plantsGroup); group.remove(plantsGroup); }
  plantsGroup = new THREE.Group();
  group.add(plantsGroup);
  buildArchetypes();
  ensurePlantMats();
  month = month || 6;
  year = year || 0;

  // Succession: drop plants the closing canopy has shaded to death (V2.21), so
  // the year-N scene is the climax community — the survivors — not every plant
  // ever placed. Undefined health_state (older scenes / existing trees) is kept.
  plants = (plants || []).filter(p => p.health_state !== 'dead');

  const byKind = { tree: [], shrub: [], vine: [], groundcover: [], grass: [],
                   aquatic: [], herb: [] };
  for (const p of plants || []) {
    let t = p.plant_type;
    if (t === 'sedge' || t === 'rush') t = 'grass';   // graminoids share blades
    const k = byKind[t] ? t : 'herb';
    byKind[k].push(p);
  }

  // Trees — bucketed by crown class (conifer vs deciduous) × crown form (from
  // the plant's aspect ratio: slender/oval/spreading) × maturity tier (young
  // trees are simpler) × per-individual sub-variation (so repeats of one
  // species aren't identical clones).
  if (byKind.tree.length) {
    const buckets = {};
    for (const p of byKind.tree) {
      const prof = profileFor(p);
      // A genus profile may force a needle crown (larch keeps deciduous needle-
      // drop) or a crown form, so a species reads right regardless of dimensions.
      const cls = (p.foliage_type === 'evergreen' || prof.conifer) ? 'conifer' : 'deciduous';
      const form = treeFormFor(p, prof);
      const t = tierFor(p);
      const sub = indHash(p) % TREE_SUBVARS;
      const ck = cls === 'conifer' ? (prof.conifer || 'standard') : 'd';
      // Surface classes join the bucket key (F63): one InstancedMesh carries one
      // material, so a papery-barked birch and a furrowed-barked oak cannot share
      // a bucket even when everything else about them matches.
      const bark = barkClassFor(p);
      const surf = cls === 'conifer' ? 'needle' : leafSurfaceFor(p);
      const key = cls + '_' + ck + '_' + prof.id + '_' + form + '_' + t + '_' + sub
        + '_' + bark + '_' + surf;
      (buckets[key] = buckets[key] || { cls, prof, form, t, sub, bark, surf, items: [] })
        .items.push(p);
    }
    for (const key in buckets) {
      const { cls, prof, form, t, sub, bark, surf, items } = buckets[key];
      const arch = getTreeArch(cls, prof, form, t, sub);
      const places = items.map(p => spreadPlacements(p, year));
      const total = places.reduce((s, pl) => s + pl.length, 0);
      const vcBark = !!arch.vertexColorBark;
      const branch = instancedMesh(arch.branchGeo, total,
        surfaceMaterial(MAT_PRESETS.bark, bark, vcBark));
      const foliage = instancedMesh(arch.foliageGeo, total,
        surf === 'needle' ? surfaceMaterial(MAT_PRESETS.needle, '', true)
                          : surfaceMaterial(MAT_PRESETS.crown, surf, true));
      const names = new Array(total), ids = new Array(total);
      let idx = 0;
      items.forEach((p, ii) => {
        const h = Math.max(0.4, p.height_m);
        const c = unitXZ(arch.foliageGeo, Math.max(0.4, p.canopy_m));
        const rotY0 = (indHash(p) % 628) / 100;
        const bare = _isDecid(p.foliage_type) && _bareMonth(month);
        // The species' own bark colour (schema v47) if the seed data has it,
        // else the genus default the viewer has always used.
        const bcol = fadeToward(p.bark_color || prof.bark || '#5d4433', p.opacity);
        const fcol = fadeColor(witherColor(seasonalColor(p.color, p.foliage_type, month, p.fall_color), p.health), p.opacity);
        places[ii].forEach((pl, k) => {
          const m = pl.mul, x = p.x + pl.dx, wy = p.y + pl.dz, z = -wy;
          const rotY = rotY0 + (k ? pl.dx + pl.dz : 0);
          const gy = terrainHeightAt(x, wy, terrain);
          setInst2(branch, idx, x, gy, z, c * m, h * m, c * m, rotY, bcol);
          if (bare) setInst2(foliage, idx, x, gy, z, 0.001, 0.001, 0.001, rotY, _white);
          else setInst2(foliage, idx, x, gy, z, c * m, h * m, c * m, rotY, fcol);
          names[idx] = p.common_name || '';
          ids[idx] = p.plant_id;
          idx++;
        });
      });
      // Pick from the trunk too, so a bare-winter tree still names on hover.
      branch.userData.pick = names; foliage.userData.pick = names;
      branch.userData.pickId = ids; foliage.userData.pickId = ids;
      plantsGroup.add(branch, foliage);
    }
  }

  // Shrubs — bucketed by genus profile so dogwood shows red stems, willow stands
  // upright, etc. (V1.94). One InstancedMesh per (profile × variant).
  buildShrubLayer(byKind.shrub, month, year, terrain);

  // Herbaceous plants (wildflower / herb / fern) — built to each species' growth
  // form (V1.98): fireweed erect, yarrow ferny, fleabane rosette, etc.
  buildHerbLayer(byKind.herb, month, year, terrain);

  // Grasses / sedges / rushes — dense flat-blade tufts (V1.92).
  buildLayer(byKind.grass, 3, MATS.blade, (v) => ARCH.grass[v],
             (p) => [Math.max(0.16, p.canopy_m), Math.max(0.3, p.height_m),
                     Math.max(0.16, p.canopy_m)], month, year, false, terrain,
             (p) => aspectBucket(p, 'grass'));

  // Aquatic / emergent marsh plants — tall erect reed/strap-leaf clumps; the
  // cattail's brown spike comes from the flower layer (V1.92).
  buildLayer(byKind.aquatic, 3, MATS.blade, (v) => ARCH.aquatic[v],
             (p) => [Math.max(0.18, p.canopy_m), Math.max(0.5, p.height_m),
                     Math.max(0.18, p.canopy_m)], month, year, false, terrain,
             (p) => aspectBucket(p, 'aquatic'));
  // Vines — sprawling/twining leafy stems (V1.99), not a cone.
  buildLayer(byKind.vine, 3, MATS.leaf, (v) => ARCH.vine[v],
             (p) => [Math.max(0.25, p.canopy_m), Math.max(0.2, p.height_m),
                     Math.max(0.25, p.canopy_m)], month, year, false, terrain,
             (p) => aspectBucket(p, 'vine'));

  // Groundcover — a creeping mat of REAL leaves since V2.29 (it was faceted
  // domes), so each species gets the unit carrying its own leaf outline.
  buildLayer(byKind.groundcover, ARCH.ground.length, MATS.leaf,
             (v) => ARCH.ground[v],
             (p) => [Math.max(0.18, p.canopy_m),
                     Math.min(0.18, Math.max(0.05, p.height_m)),
                     Math.max(0.18, p.canopy_m)], month, year, true, terrain,
             groundcoverBucket);

  // Contact shadows under trees and tall shrubs (skip near-vanished plants).
  const shadowed = byKind.tree
    .concat(byKind.shrub.filter(p => (p.height_m || 0) > 1.2))
    .filter(p => (p.opacity ?? 1) >= 0.2);
  if (shadowed.length) {
    const sh = instancedMesh(GEO.shadow, shadowed.length, MATS.shadow, false);
    shadowed.forEach((p, i) => {
      const c = Math.max(0.4, p.canopy_m) * 1.35;
      _v.set(p.x, 0.03, -p.y); _s.set(c, 1, c); _q.identity();
      _m.compose(_v, _q, _s);
      sh.setMatrixAt(i, _m);
    });
    plantsGroup.add(sh);
  }

  // Flowers — real-coloured blooms on plants in flower for this month (V1.90).
  buildFlowers(plants, month, terrain);
  // Fruit — berries on fleshy-fruited plants in their fruit season (V2.0).
  buildFruit(plants, month, terrain);
}

