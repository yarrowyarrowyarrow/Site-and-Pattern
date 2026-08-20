// Part of the Site & Pattern 3D viewer. Loaded as an ordered CLASSIC
// script by the bootstrap in scene3d.html — it shares the global scope
// with its siblings (THREE and friends are globals set by the
// bootstrap). Do not add ES `import`/`export` here.
//
// Stylised bodies (V2.34). Nothing here runs at evaluation time — the
// builders are called from buildPerennialGeo during a scene push — so
// this chunk's position in the load order is not a dependency, only a
// place to live.
//
// ── Why a second body builder exists ────────────────────────────────────────
//
// Detail level 0 is a STYLE now, not a thinned copy of level 1 (the argument is
// in 01b-surface.js setStylised). For trees and shrubs that costs nothing: skip
// the baked models and the procedural builders already draw the faceted masses
// this mode wants — buildShrubGeo's no-morphology branch IS the old look.
//
// Herbs were the exception, and it showed. buildPerennialGeo has no faceted
// path: it always assembles real leaf blades, so all level 0 did was build the
// same forb out of FEWER blades. That is the failure this mode exists to avoid —
// a sparse attempt at realism reads as a broken plant, where a confident
// abstraction reads as a diagram and the eye lets it be. A meadow at level 0
// came out as scattered green threads.
//
// So: at level 0 a forb is a small mound of faceted masses on its form's
// footprint, plus the bare flower stalks the bloom layer lands on. Same unit
// frame, same instancing, roughly a fifth of the triangles.
//
// Design principle P5 (perception is constructed, not received) — see
// docs/DESIGN_PHILOSOPHY.md. Which look is "better" is not a property of the
// geometry; it is a property of what the viewer's eye has been invited to
// compare it against.

// Per growth form: how many masses, how big, the ellipsoid they are squashed to,
// and the height band they fill. Read straight off the same HERB_FORMS habits
// the detailed builder uses — a mat is wide and flat, an erect forb is a narrow
// column, a rosette is a disc at the ground under bare stalks.
// Radii are deliberately smaller than the shrub masses they borrow from: a forb
// is a bundle of stems, and three fat ellipsoids on one read as boulders rather
// than as a plant. More, smaller masses keep the silhouette leafy.
const _STYLISED_HERB = {
  erect:   { n: [4, 6], r: [0.10, 0.16], shape: [0.60, 1.20, 0.60], y: [0.24, 0.90] },
  clump:   { n: [5, 8], r: [0.14, 0.21], shape: [1.00, 0.85, 1.00], y: [0.16, 0.82] },
  ferny:   { n: [4, 6], r: [0.16, 0.23], shape: [1.15, 0.60, 1.15], y: [0.08, 0.46] },
  rosette: { n: [3, 5], r: [0.18, 0.25], shape: [1.25, 0.45, 1.25], y: [0.05, 0.26] },
  grassy:  { n: [3, 4], r: [0.11, 0.17], shape: [0.80, 1.15, 0.80], y: [0.16, 0.68] },
  mat:     { n: [5, 8], r: [0.12, 0.18], shape: [1.30, 0.40, 1.30], y: [0.04, 0.18] },
  fern:    { n: [4, 6], r: [0.14, 0.21], shape: [0.95, 0.90, 0.95], y: [0.12, 0.74] },
};
const _STYLISED_HERB_DEFAULT = _STYLISED_HERB.clump;

// The merged herb geometry is position-only (see _stem in 04-quality.js: blade
// geometry carries no normals, and mergeGeometries requires identical attribute
// sets). normalizeUnit recomputes normals on the merged result.
//
// It also requires them to agree on INDEXING, and that is the trap here:
// CylinderGeometry is indexed and IcosahedronGeometry is not, so the two kinds
// this builder mixes cannot merge as they come. buildShrubGeo never hit it
// because it merges its stems and its masses into two separate geometries.
// mergeGeometries answers a mismatch with null rather than an exception, so the
// symptom is a whole layer silently missing from the scene.
function _flat(g) {
  g.deleteAttribute('normal');
  g.deleteAttribute('uv');
  return g.index ? g.toNonIndexed() : g;
}

function _bareMass(rng, r, shape) {
  return _flat(makeFoliageMass(rng, r, shape));
}

function stylisedHerbGeo(rng, F) {
  const S = _STYLISED_HERB[herbFormId(F)] || _STYLISED_HERB_DEFAULT;
  const geos = [];
  const n = _rint(rng, S.n[0], S.n[1]);
  for (let i = 0; i < n; i++) {
    const r = S.r[0] + rng() * (S.r[1] - S.r[0]);
    // Spiral the masses out from the centre by the golden angle rather than
    // scattering them: a random cloud of three ellipsoids reads as debris, an
    // ordered one reads as a plant. Wide forms spread further than tall ones,
    // which is what the shape vector already says.
    const az = i * 2.39996 + rng() * 0.5;
    const rad = (n === 1 ? 0 : (i / (n - 1))) * 0.30 * S.shape[0];
    const t = n === 1 ? 0.5 : i / (n - 1);
    const y = S.y[0] + (S.y[1] - S.y[0]) * t;
    const mass = _bareMass(rng, r, S.shape);
    mass.translate(Math.cos(az) * rad, y, Math.sin(az) * rad);
    geos.push(mass);
  }
  // Bare flower stalks, kept from the detailed builder: the bloom sprites are
  // placed by the flower layer at ~90% of height and look pasted on mid-air
  // without something rising to meet them. Stylised keeps the billboard blooms
  // deliberately — a flat coloured stamp is honest inside a flat-shaded diagram,
  // which is exactly what it is not inside a Lifelike scene.
  if (F.stalks) {
    const ns = _rint(rng, F.stalks[0], F.stalks[1]);
    for (let i = 0; i < ns; i++) {
      const h = 0.75 + rng() * 0.25;
      const lean = 0.05 + rng() * 0.18;
      geos.push(_flat(_stem(0.008, 0.005, h,
        new THREE.Matrix4().makeRotationY(rng() * Math.PI * 2)
          .multiply(new THREE.Matrix4().makeRotationZ(lean)))));
    }
  } else {
    // Leafy-stemmed forms get their stems instead, so the silhouette still
    // says "upright stalks" and not "a pile of rocks".
    const nStems = F.stems && F.stems[1] ? _rint(rng, F.stems[0], F.stems[1]) : 0;
    for (let i = 0; i < nStems; i++) {
      const h = 0.7 + rng() * 0.3;
      geos.push(_flat(_stem(0.012, 0.006, h,
        new THREE.Matrix4().makeRotationY((i / Math.max(1, nStems)) * Math.PI * 2)
          .multiply(new THREE.Matrix4().makeRotationZ(F.splay * (0.5 + rng()))))));
    }
  }
  const g = mergeGeometries(geos, false);
  normalizeUnit([g]);
  applyFoliageGradient(g);
  return g;
}

// HERB_FORMS is keyed by name and the builders are handed the VALUE, so the
// stylised table has to find its way back to the key. Cheap and done once per
// archetype build, not per plant.
function herbFormId(F) {
  for (const k in HERB_FORMS) if (HERB_FORMS[k] === F) return k;
  return 'clump';
}
