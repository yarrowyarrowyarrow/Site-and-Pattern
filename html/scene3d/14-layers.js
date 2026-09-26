// Part of the Site & Pattern 3D viewer. Loaded as an ordered CLASSIC
// script by the bootstrap in scene3d.html — it shares the global scope
// with its siblings (THREE and friends are globals set by the
// bootstrap). Do not add ES `import`/`export` here.
//
// The procedural LAYER tufts — groundcover, grass/sedge/rush and aquatic
// emergents — split out of 04-quality.js in V2.34 when that file hit its
// ceiling, and the horsetails (V2.89). Vines were here too, as a free-standing
// leafy column; since V2.89 they are drawn on what they climb (22-vines.js). Nothing here runs at evaluation time;
// buildArchetypes calls these during a scene push, so this chunk's position in
// the load order is not a dependency, only a place to live.
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

// A horsetail clump (V2.89, F176). Equisetum has no leaves to speak of — they
// are reduced to a toothed sheath around every node — so the plant IS its
// jointed stems: a dark ring at each joint and, as the species records its
// `stem_branching`, whorls of thin branches all the way up (unit 2, Common
// Horsetail's bottlebrush), at the middle nodes only (unit 1, Swamp
// Horsetail), or none (unit 0, the scouring-rushes, whose sheaths are banded
// ash and black and whose stems end in the pointed cone). Until V2.89 the four
// were a grass tuft, a reed tuft and two rush tufts, and two wore grass plumes.
//
// Drawn, not baked: a handful of jointed cylinders is what the procedural path
// does well, and it is the path Stylised draws anyway (see the V2.89 plan).
//
// Unit 3 is Common Mare's-tail (V2.90, F175), the plant horsetail is most often
// mistaken for: unbranched stems clothed their whole length in whorls of short
// narrow LEAVES, green throughout, with no dark joints and no cone.
function buildHorsetailGeo(rng, unit) {
  const geos = [];
  const tint = (g, v) => {
    const c = new Float32Array(g.attributes.position.count * 3).fill(v);
    g.setAttribute('color', new THREE.BufferAttribute(c, 3));
    return g;
  };
  const seg = (a, b, r0, r1, radial) => {       // open tube from a to b
    const d = new THREE.Vector3().subVectors(b, a);
    const len = Math.max(1e-4, d.length());
    const s = new THREE.CylinderGeometry(r1, r0, len, radial, 1, true);
    s.translate(0, len / 2, 0);
    s.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(0, 1, 0), d.normalize()));
    s.translate(a.x, a.y, a.z);
    s.deleteAttribute('normal'); s.deleteAttribute('uv');
    return s;
  };
  const leafy = unit === 3;
  const whorl = unit === 2 ? [0.18, 0.92, 11, 0.20, 1.0, 0.75]  // from, to, count,
              : unit === 1 ? [0.38, 0.74, 7, 0.12, 0.9, 0.75]   // length, lift,
              : leafy ? [0.04, 1.0, 8, 0.04, 0.55, 0.3] : null; // taper
  // A stand, not a handful: horsetails come up in dense colonies.
  const stems = qn(unit === 2 || leafy ? 12 : 18) + Math.floor(rng() * 4);
  for (let i = 0; i < stems; i++) {
    const ang = rng() * Math.PI * 2, rad = 0.3 * Math.sqrt(rng());
    const base = new THREE.Vector3(Math.cos(ang) * rad, 0, Math.sin(ang) * rad);
    const dir = new THREE.Vector3((rng() - 0.5) * 0.12, 1, (rng() - 0.5) * 0.12)
      .normalize();
    const h = 0.7 + 0.3 * rng(), r = 0.0045 * (0.8 + 0.4 * rng());
    const nodes = leafy ? 16 + Math.floor(rng() * 5) : 7 + Math.floor(rng() * 5);
    const at = (y) => base.clone().addScaledVector(dir, y);
    for (let k = 0; k < nodes; k++) {
      const y0 = h * k / nodes, y1 = h * (k + 1) / nodes;
      // The internode, lighter towards the growing tip.
      geos.push(tint(seg(at(y0), at(y1), r, r * 0.97, 5),
                     leafy ? 0.92 : 0.78 + 0.25 * (y1 / h)));
      // The sheath at the joint: dark, and banded ash-and-black on the plain
      // (scouring-rush) stems, where it is the field mark. Mare's-tail has none.
      const sh = Math.min(0.018, (y1 - y0) * 0.22);
      if (!whorl) geos.push(tint(seg(at(y1 - sh * 2), at(y1 - sh), r * 1.25, r * 1.25, 5), 0.85));
      if (!leafy) geos.push(tint(seg(at(y1 - sh), at(y1), r * 1.3, r * 1.3, 5), whorl ? 0.42 : 0.14));
      const f = y1 / h;
      if (!whorl || f < whorl[0] || f > whorl[1] || k === nodes - 1) continue;
      // A whorl: longest low down, so the stem reads as a tapering brush.
      const nb = whorl[2] + Math.floor(rng() * 3);
      const len = whorl[3] * (1 - whorl[5] * (f - whorl[0]) / (whorl[1] - whorl[0]));
      for (let b = 0; b < nb; b++) {
        const phi = (b / nb) * Math.PI * 2 + k * 0.4;
        const tip = new THREE.Vector3(Math.cos(phi), whorl[4], Math.sin(phi))
          .normalize().multiplyScalar(len).add(at(y1));
        geos.push(tint(seg(at(y1), tip, r * 0.38, r * 0.2, 3), 0.9));
      }
    }
    if (!whorl) {                                 // the pointed cone at the tip
      geos.push(tint(seg(at(h), at(h + 0.028), r * 1.15, r * 0.1, 5), 0.2));
    }
  }
  const g = mergeGeometries(geos, false);
  for (const p of geos) p.dispose();
  normalizeUnit([g]);
  return g;
}

// Which unit: the species' recorded branching (V2.89), or mare's-tail's whorled
// leaves (V2.90, src/pond_habit.py `whorled`). Moved out of 04-quality.js.
const _HORSETAIL_UNIT = { unbranched: 0, branched_above: 1, branched_throughout: 2 };
function horsetailBucket(p) {
  return p.drawn && p.drawn.body === 'whorled' ? 3 : _HORSETAIL_UNIT[p.stem_branching] || 0;
}
