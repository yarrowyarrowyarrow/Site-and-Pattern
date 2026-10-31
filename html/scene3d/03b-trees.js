// Part of the Site & Pattern 3D viewer. Loaded as an ordered CLASSIC
// script by the bootstrap in scene3d.html — it shares the global scope
// with its siblings (THREE and friends are globals set by the
// bootstrap). Do not add ES `import`/`export` here.
//
// The procedural trees (V2.92): the crown form a tree takes, the da Vinci
// skeleton and its clumps, first forks and climbing limbs (F178), and the
// conifer and pine bodies. Split out of 03-herbs.js when the Stylised half of
// F178 took it past its ceiling. Nothing here runs at evaluation time: the
// builders are called from getTreeArch (04-quality.js) during a scene push,
// and they use normalizeUnit and applyFoliageGradient, which stay in
// 03-herbs.js because the herb and shrub bodies share them.

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
    // The architecture the baked model has (V2.92, F178; flora_trees.
    // _decid_skeleton): trunks from the ground, the trunk's first fork, and
    // limbs that keep climbing. Stylised draws these trees procedurally on
    // purpose, so without them the elm lost its vase there and water birch
    // its clump.
    if (prof.stems) cfg.stems = prof.stems;
    if (prof.leaders) cfg.leaders = prof.leaders;
    if (prof.rise) cfg.rise = prof.rise;
  }
  return cfg;
}

// Several trunks from one clump (`cfg.stems` = [lo, hi, lean]): a zero-length
// root whose children are the stems, each leaning out on its own bearing and
// carrying its share of the trunk's cross-section.
function generateClump(radius, length, cfg, rng) {
  const [lo, hi, lean] = cfg.stems;
  const n = lo + Math.floor(rng() * (hi - lo + 1));
  const sub = Object.assign({}, cfg, { stems: null });
  const root = { radiusBottom: radius, radiusTop: radius, length: 0, depth: 0,
                 children: [], clump: true };
  const r = radius / Math.sqrt(n) * 1.15;
  const base = rng() * Math.PI * 2;
  for (let i = 0; i < n; i++) {
    const stem = generateDaVinciTree(r, length * (0.8 + rng() * 0.4), 0, sub, rng);
    stem.angleSpread = lean * (0.7 + rng() * 0.6);
    stem.angleRotation = base + i * (Math.PI * 2 / n) + (rng() - 0.5) * 0.6;
    stem.offset = radius * 1.2;
    root.children.push(stem);
  }
  return root;
}

function generateDaVinciTree(radius, length, depth, cfg, rng) {
  if (depth === 0 && cfg.stems && cfg.stems[1] > 1) return generateClump(radius, length, cfg, rng);
  if (depth >= cfg.maxDepth || radius < cfg.minRadiusCutoff) {
    return { radiusBottom: radius, radiusTop: radius * 0.6, length, depth, children: [] };
  }
  const node = { radiusBottom: radius, length, depth, children: [] };
  if (depth === 0 && cfg.leaders) {
    // The first fork (`cfg.leaders` = [lo, hi, angle, length]): an elm's four or
    // five steep leaders, a cottonwood's three or four heavy limbs, sharing the
    // trunk's cross-section. Length is a multiple of the trunk's.
    const [lo, hi, angle, lenMul] = cfg.leaders;
    const n = lo + Math.floor(rng() * (hi - lo + 1));
    node.radiusTop = radius * 0.65;
    const base = rng() * Math.PI * 2;
    for (let i = 0; i < n; i++) {
      const cr = node.radiusTop * Math.sqrt(1.3 / n);
      const child = generateDaVinciTree(cr, length * lenMul * (0.85 + rng() * 0.3),
                                        depth + 1, cfg, rng);
      child.angleSpread = angle * (0.8 + rng() * 0.4);
      child.angleRotation = base + i * (Math.PI * 2 / n) + (rng() - 0.5) * 0.4;
      node.children.push(child);
    }
    return node;
  }
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
      if (cfg.rise) child.climb = cfg.rise;
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
  // Turn a branch's growth axis toward +Y by `rise` (cfg.rise, V2.92): without
  // it the walk has no sense of up, and after three forks a limb points
  // anywhere, so a vase came out as a ball on each leader.
  const _up = new THREE.Vector3(0, 1, 0);
  function climb(m, rise) {
    const pos = new THREE.Vector3().setFromMatrixPosition(m);
    const dir = new THREE.Vector3().setFromMatrixColumn(m, 1).normalize();
    const want = dir.clone().addScaledVector(_up, rise).normalize();
    const q = new THREE.Quaternion().setFromUnitVectors(dir, want);
    return new THREE.Matrix4().makeTranslation(pos.x, pos.y, pos.z)
      .multiply(new THREE.Matrix4().makeRotationFromQuaternion(q))
      .multiply(new THREE.Matrix4().makeTranslation(-pos.x, -pos.y, -pos.z))
      .multiply(m);
  }
  function walk(node, mat) {
    if (node.clump) {
      // A clump's root is only where the stems meet: no wood, no leaves.
      for (const stem of node.children) {
        // Offset along the same bearing the stem leans toward (RotY(a) sends
        // the RotX lean to (sin a, cos a)), so the clump opens outward.
        const a = stem.angleRotation, o = stem.offset || 0;
        const base = new THREE.Matrix4().makeTranslation(Math.sin(a) * o, 0, Math.cos(a) * o)
          .multiply(new THREE.Matrix4().makeRotationY(a))
          .multiply(new THREE.Matrix4().makeRotationX(stem.angleSpread));
        walk(stem, mat.clone().multiply(base));
      }
      return;
    }
    addSeg(node, mat);
    const tip = mat.clone().multiply(new THREE.Matrix4().makeTranslation(0, node.length, 0));
    const terminal = !node.children.length;
    if (terminal) addDeciduousCluster(tip, node.depth, true);
    else if (node.depth >= 2) addDeciduousCluster(tip, node.depth, false);  // interior fill
    if (terminal) return;
    for (const child of node.children) {
      const rot = new THREE.Matrix4().makeRotationY(child.angleRotation)
        .multiply(new THREE.Matrix4().makeRotationX(child.angleSpread));
      const m = tip.clone().multiply(rot);
      walk(child, child.climb ? climb(m, child.climb) : m);
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
