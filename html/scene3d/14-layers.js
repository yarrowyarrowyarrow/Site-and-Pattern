// Part of the Site & Pattern 3D viewer. Loaded as an ordered CLASSIC
// script by the bootstrap in scene3d.html — it shares the global scope
// with its siblings (THREE and friends are globals set by the
// bootstrap). Do not add ES `import`/`export` here.
//
// The four procedural LAYER tufts — groundcover, grass/sedge/rush, aquatic
// emergents and vines — split out of 04-quality.js in V2.34 when that file hit
// its ceiling. Nothing here runs at evaluation time; buildArchetypes calls these
// during a scene push, so this chunk's position in the load order is not a
// dependency, only a place to live.
//
// They are the app's PERMANENT fallback for the layer archetypes: the baked GLB
// units are preferred when the model library has loaded and Stylised skips it on
// purpose, so these run in every session either way and can never quietly rot.

// A groundcover mat: a scatter of small low domes filling a unit circle — a
// textured plant carpet rather than a flat disc.
function buildGroundcoverGeo(rng) {
  const geos = [];
  const n = qn(5 + Math.floor(rng() * 4));   // 5–8 tufts
  for (let i = 0; i < n; i++) {
    const r = 0.08 + rng() * 0.07;
    const ang = rng() * Math.PI * 2, rad = rng() * 0.42;
    const ys = 0.5 + rng() * 0.5;
    const s = new THREE.SphereGeometry(r, 5, 3);
    s.scale(1, ys, 1);
    s.translate(Math.cos(ang) * rad, r * ys * 0.5, Math.sin(ang) * rad);
    geos.push(s);
  }
  const g = mergeGeometries(geos, false);
  normalizeUnit([g]);
  applyFoliageGradient(g);
  return g;
}

// A grass / sedge / rush tuft: a dense fan of flat, arching blades from a shared
// base — full and lush rather than a few thin spindly stalks (V1.92). Flat
// ribbons (double-sided material) read as real blades with width; lifted
// normals let the whole tuft catch top light as one soft mound.
function buildGrassGeo(rng) {
  const geos = [];
  const blades = qn(26 + Math.floor(rng() * 16));   // 26–41 blades — a thick clump
  for (let i = 0; i < blades; i++) {
    const h = 0.62 + rng() * 0.5;
    const wb = 0.016 + rng() * 0.018;            // base half-width (real blade)
    const lean = 0.22 + rng() * 0.7;             // arching meadow sweep
    geos.push(makeBlade(rng, h, wb, lean, 1.5));
  }
  const g = mergeGeometries(geos, false);
  normalizeUnit([g]);
  applyFoliageGradient(g);
  liftNormals(g, 0.8);
  return g;
}

// An aquatic / emergent tuft (cattail, bulrush, reed leaves): taller, stiffer,
// broader, more erect blades than meadow grass — so marsh plants stop rendering
// as the round-leaf perennial clump (V1.92). The brown cattail spike itself is
// drawn by the flower layer (the "cattail" form).
function buildAquaticGeo(rng) {
  const geos = [];
  const blades = qn(16 + Math.floor(rng() * 12));   // 16–27 broad upright leaves
  for (let i = 0; i < blades; i++) {
    const h = 0.85 + rng() * 0.35;
    const wb = 0.03 + rng() * 0.028;             // wide strap leaves
    const lean = 0.06 + rng() * 0.32;            // mostly vertical, slight nod
    geos.push(makeBlade(rng, h, wb, lean, 2.4)); // bend held high → stiff reed
  }
  const g = mergeGeometries(geos, false);
  normalizeUnit([g]);
  applyFoliageGradient(g);
  liftNormals(g, 0.85);
  return g;
}

// A vine (V1.99): several slender stems sprawling/twining out and up from a low
// base, clothed with broad leaves — a leafy tangle, not a cone. Reads as a
// climbing/trailing plant (clematis, vetch, peavine, hops).
function buildVineGeo(rng) {
  const geos = [];
  const stems = qn(4 + Math.floor(rng() * 3));   // 4–6 trailing/twining stems
  for (let i = 0; i < stems; i++) {
    const az = (i / stems) * Math.PI * 2 + rng() * 0.8;
    const splay = 0.6 + rng() * 0.55;            // lean far out — sprawling
    const h = 0.7 + rng() * 0.35;
    const rot = new THREE.Matrix4().makeRotationY(az)
      .multiply(new THREE.Matrix4().makeRotationZ(splay));
    geos.push(_stem(0.013, 0.007, h, rot));
    const nL = qn(4 + Math.floor(rng() * 3));
    for (let j = 0; j < nL; j++) {
      const t = 0.3 + 0.65 * (j / Math.max(1, nL - 1));
      const at = new THREE.Vector3(0, h * t, 0).applyMatrix4(rot);
      geos.push(makeLeaf(rng, 0.16, 0.1, 1.05, j * 2.39996 + az, at, 'ovate'));
    }
  }
  const g = mergeGeometries(geos, false);
  normalizeUnit([g]);
  applyFoliageGradient(g);
  return g;
}

