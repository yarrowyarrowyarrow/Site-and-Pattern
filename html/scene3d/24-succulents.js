// ── Succulents and cacti (V2.93, F177) ──────────────────────────────────────
// Design principle P5 — see docs/DESIGN_PHILOSOPHY.md
//
// Until V2.93 the prickly pears were the groundcover mat's star of narrow
// blades (a cactus's leaves are scales, and a scale is a narrow outline), the
// ball cactus and roseroot were the herb mat drawn in 5 mm and 3 cm leaves, and
// the yucca was a leafy bush with its flowers inside it. Each now arrives with a
// `drawn` block from src/succulent_habit.py (its body, how tall it is drawn,
// the ground it covers, how many balls, rosettes or stems) and this chunk draws
// the four bodies:
//
//   pads    flat jointed stems in chains: a first pad leaning low, more standing
//           on its rim, pale spines at the areoles, the flowers on the top rims;
//   ball    one or a few globes of tubercles, each tipped with a star of pale
//           radial spines, so the ball reads grey-white over green;
//   swords  rosettes of stiff narrow leaves at the recorded leaf length, each
//           sending up a flower stalk to the recorded height in its season;
//   fleshy  upright stems crowded with the species' own fleshy leaves, the
//           flowers on top.
//
// The flowers are the floret layer's, at their recorded size and architecture.
// This chunk only says where they go: succulentAnchorsFor(p), asked after
// vineAnchorsFor(p) by the floret, billboard and fruit layers. Its anchors carry
// `top: true`, meaning the anchor is where the bloom's top is: a vine's solitary
// flower is held on a short stalk above its leaf, and a prickly pear's sits on
// the rim of its pad.
//
// A body is stiff: the pads and balls do not sway at all, the swords barely.
// Spread offspring (F35) are not drawn; none of these species records any.

window.SUCCULENT_BODIES = { pads: 1, ball: 1, swords: 1, fleshy: 1 };
let SUCC_ANCHORS = new Map();       // plant -> [{x, y, z, nx, nz, top}], world

function succulentAnchorsFor(p) {
  const a = SUCC_ANCHORS.get(p);
  return a && a.length ? a : null;
}

// Materials, cached by surfaceMaterial per (preset x class x style).
const _SUCC_BODY = { key: 'succBody', detailKind: 'leaf', roughness: 0.62,
                     wind: 0, vertexColors: true, doubleSide: true,
                     detailScale: 10.0, detailAmount: 0.16 };
const _SUCC_SPINE = { key: 'succSpine', detailKind: '', roughness: 0.55, wind: 0,
                      vertexColors: true, doubleSide: true };
const _SUCC_SWORD = { key: 'succSword', detailKind: 'leaf', roughness: 0.7,
                      wind: 0.025, vertexColors: true, doubleSide: true,
                      detailScale: 14.0, detailAmount: 0.2 };
const _SUCC_FLESH = { key: 'succFlesh', detailKind: 'leaf', roughness: 0.65,
                      wind: 0.04, vertexColors: true, doubleSide: true,
                      detailScale: 14.0, detailAmount: 0.2 };
// A spine is pale straw whatever the plant; the catalogue records no spine
// colour, as it records no bark colour for most shrubs.
const _SPINE_HEX = '#ddd5bf';
// A stalk after its flowers, the herb layer's winter tan (01-core.js).
const _SUCC_DRY = new THREE.Color('#a09060');

const _sv = new THREE.Vector3(), _sq = new THREE.Quaternion(),
      _ss = new THREE.Vector3(), _sUp = new THREE.Vector3(0, 1, 0);

function _succGroup(groups, key, part, geo, mat, shadow) {
  let g = groups.get(key);
  if (!g) groups.set(key, g = { part, geo, mat, shadow: shadow !== false,
                                mats: [], cols: [], names: [], ids: [] });
  return g;
}

function _succPush(g, m, col, p) {
  g.mats.push(m); g.cols.push(col); g.names.push(p.common_name || '');
  g.ids.push(p.plant_id);
}

function _colored(g, fn) {
  const pos = g.attributes.position, col = new Float32Array(pos.count * 3);
  for (let i = 0; i < pos.count; i++) {
    const v = fn(pos.getX(i), pos.getY(i), pos.getZ(i), i);
    col[i * 3] = col[i * 3 + 1] = col[i * 3 + 2] = v;
  }
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  return g;
}

// ── unit shapes ─────────────────────────────────────────────────────────────

// A pad: an egg-shaped lens, length 1 up +Y from its joint at the origin, width
// `w` across X, thickness `t` through Z, broadest above the middle. Proportions
// are built in rather than scaled per instance, because a squashed instance
// matrix bends the normals of a thin lens and lights its faces as edges.
function _lensPoint(u, v, w, t) {
  const s = Math.sin(u) * (1 - 0.22 * Math.cos(u));
  return [0.5 * w * s * Math.cos(v), 0.5 * (1 - Math.cos(u)), 0.5 * t * s * Math.sin(v)];
}

function _padGeoS(w, t, nu, nv) {
  const pos = [], idx = [];
  for (let i = 0; i <= nu; i++) {
    for (let j = 0; j < nv; j++) pos.push(..._lensPoint(i / nu * Math.PI, j / nv * Math.PI * 2, w, t));
  }
  for (let i = 0; i < nu; i++) {
    for (let j = 0; j < nv; j++) {
      const a = i * nv + j, b = i * nv + (j + 1) % nv, c = a + nv, d = b + nv;
      idx.push(a, c, b, b, c, d);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return _colored(g, (x, y) => 0.74 + 0.26 * Math.min(1, y * 1.4));  // the joint shaded
}

// One spine: a thin triangle from `at` along `dir`, `len` long.
function _spine(out, at, dir, len, wid, shade, cols) {
  const side = new THREE.Vector3().crossVectors(dir, _sUp);
  if (side.lengthSq() < 1e-6) side.set(1, 0, 0);
  side.normalize().multiplyScalar(wid * 0.5);
  const tip = at.clone().addScaledVector(dir, len);
  out.push(at.x - side.x, at.y - side.y, at.z - side.z,
           at.x + side.x, at.y + side.y, at.z + side.z, tip.x, tip.y, tip.z);
  cols.push(shade, shade, shade, shade, shade, shade, shade * 0.8, shade * 0.8, shade * 0.8);
}

function _trisGeo(pos, cols) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3));
  g.computeVertexNormals();
  return g;
}

// A pad's spines: areoles in a quincunx over both faces and round the rim, each
// a small tuft angled back towards the joint (the prickly pears' spines are
// deflexed), in the same unit frame as _padGeoS.
function _padSpinesGeo(w, t) {
  const pos = [], cols = [], e = 0.01;
  let s = 7;
  const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  const P = (u, v) => new THREE.Vector3(..._lensPoint(u, v, w, t));
  for (let i = 0; i < 5; i++) {
    const u = (0.32 + 0.6 * i / 4) * Math.PI;
    const nv = i < 1 ? 4 : 6;
    for (let j = 0; j < nv; j++) {
      const v = (j + (i % 2) * 0.5) / nv * Math.PI * 2;
      const at = P(u, v);
      const du = P(u + e, v).sub(P(u - e, v)), dv = P(u, v + e).sub(P(u, v - e));
      const n = new THREE.Vector3().crossVectors(dv, du).normalize();
      if (n.dot(at.clone().setY(0)) < 0) n.negate();         // outward
      const dir = n.clone().addScaledVector(_sUp, -0.55 - 0.3 * rnd())
        .add(new THREE.Vector3(rnd() - 0.5, 0, rnd() - 0.5).multiplyScalar(0.7))
        .normalize();
      _spine(pos, at, dir, 0.12 + 0.14 * rnd(), 0.03, 1, cols);
    }
  }
  return _trisGeo(pos, cols);
}

// A globe of tubercles: height 1 up +Y from a base sunk a little into the soil,
// `w` across. The tubercles sit on a phyllotaxis spiral, as a cactus's do.
const _BALL_TUB = 44;
function _tubercles(w) {
  const out = [];
  for (let i = 0; i < _BALL_TUB; i++) {
    const f = (i + 0.5) / _BALL_TUB, polar = Math.acos(1 - 1.75 * f);  // top 7/8
    out.push({ polar, az: i * 2.39996 });
  }
  return out;
}

function _ballPoint(polar, az, w) {
  return new THREE.Vector3(0.5 * w * Math.sin(polar) * Math.cos(az),
                           0.5 + 0.5 * Math.cos(polar),
                           0.5 * w * Math.sin(polar) * Math.sin(az));
}

function _ballGeoS(w) {
  const g = new THREE.SphereGeometry(0.5, 20, 14);
  const pos = g.attributes.position, tubs = _tubercles(w);
  const dirs = tubs.map((q) => _ballPoint(q.polar, q.az, 1).sub(new THREE.Vector3(0, 0.5, 0)).normalize());
  const v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.set(pos.getX(i), pos.getY(i), pos.getZ(i)).normalize();
    let bump = 0;
    for (const d of dirs) bump += Math.exp(-(1 - v.dot(d)) * 60);
    const r = 0.5 * (1 + 0.1 * Math.min(1, bump));
    pos.setXYZ(i, v.x * r * w, 0.5 + v.y * r, v.z * r * w);
  }
  g.computeVertexNormals();
  return _colored(g, (x, y) => 0.7 + 0.3 * Math.min(1, y * 1.6));
}

// Each tubercle's star: radial spines lying close over the surface, and one or
// two centrals standing out, darker at the tip.
function _ballSpinesGeo(w) {
  const pos = [], cols = [];
  let s = 11;
  const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  const c = new THREE.Vector3(0, 0.5, 0);
  for (const q of _tubercles(w)) {
    const at = _ballPoint(q.polar, q.az, w).multiplyScalar(1).sub(c).multiplyScalar(1.1).add(c);
    const n = at.clone().sub(c).normalize();
    const t1 = new THREE.Vector3().crossVectors(n, _sUp);
    if (t1.lengthSq() < 1e-6) t1.set(1, 0, 0);
    t1.normalize();
    const t2 = new THREE.Vector3().crossVectors(n, t1).normalize();
    // E. vivipara carries a dozen or more radials per areole, white, and they
    // are most of what the eye sees of the plant: the ball reads grey-white.
    for (let k = 0; k < 9; k++) {
      const a = (k / 9) * Math.PI * 2 + rnd() * 0.3;
      const dir = t1.clone().multiplyScalar(Math.cos(a)).addScaledVector(t2, Math.sin(a))
        .addScaledVector(n, 0.3).normalize();
      _spine(pos, at, dir, 0.14 + 0.06 * rnd(), 0.032, 1, cols);
    }
    _spine(pos, at, n.clone().addScaledVector(t1, rnd() - 0.5).normalize(),
           0.13, 0.024, 0.55, cols);
  }
  return _trisGeo(pos, cols);
}

// A sword leaf: length 1 up +Y, channelled (a shallow V, open towards +Z), a
// little broader a third of the way up, drawn to a sharp point.
function _swordGeoS() {
  const n = 5, pos = [], idx = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, hw = 0.5 * 0.024 * (1 + 0.35 * Math.sin(Math.PI * t * 0.9))
                                       * (1 - Math.pow(t, 2.2));
    pos.push(-hw, t, hw * 0.5, 0, t, 0, hw, t, hw * 0.5);
  }
  for (let i = 0; i < n; i++) {
    const a = i * 3;
    idx.push(a, a + 1, a + 3, a + 1, a + 4, a + 3, a + 1, a + 2, a + 4, a + 2, a + 5, a + 4);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return _colored(g, (x, y) => 0.72 + 0.28 * Math.min(1, y * 2.5));
}

function _stickGeoS() {
  const g = new THREE.CylinderGeometry(0.6, 1, 1, 6, 1, true);
  g.translate(0, 0.5, 0);
  return _colored(g, () => 0.9);
}

// ── the bodies ──────────────────────────────────────────────────────────────

function _matAt(pos, axis, side, scale) {
  // A frame whose +Y is `axis` and +X is `side` (made square to it).
  const y = axis.clone().normalize();
  const x = side.clone().addScaledVector(y, -side.dot(y)).normalize();
  const z = new THREE.Vector3().crossVectors(x, y).normalize();
  const m = new THREE.Matrix4().makeBasis(x, y, z).scale(new THREE.Vector3(scale, scale, scale));
  m.setPosition(pos.x, pos.y, pos.z);
  return m;
}

// Chains of pads, in units of one pad's length, rooted at the origin: a first
// pad leaning low, a pad or two on its rim standing more upright, fewer on
// theirs. The first chain is the tallest on purpose, so the clump reaches the
// height it is recorded at.
function _padChain(rng, lead) {
  const pads = [];
  const grow = (base, az, lean, tier) => {
    const d = new THREE.Vector3(Math.sin(lean) * Math.cos(az), Math.cos(lean),
                                Math.sin(lean) * Math.sin(az));
    const w = new THREE.Vector3(-Math.sin(az), 0, Math.cos(az))
      .applyAxisAngle(d, (rng() - 0.5) * 1.2);
    const pad = { base, d, w, tier, kids: 0 };
    pads.push(pad);
    const nk = lead ? (tier < 3 ? 1 : 0)
      : tier === 1 ? (rng() < 0.55 ? 1 : 0) + (rng() < 0.15 ? 1 : 0)
      : tier === 2 ? (rng() < 0.35 ? 1 : 0) : 0;
    for (let k = 0; k < nk; k++) {
      pad.kids++;
      const at = base.clone().addScaledVector(d, 0.9).addScaledVector(w, (rng() - 0.5) * 0.4);
      const kLean = lead ? [0, 0.8, 0.35, 0.15][tier + 1] : lean * (0.3 + 0.35 * rng());
      grow(at, az + (lead ? 0.3 : (rng() - 0.5) * 1.3), kLean, tier + 1);
    }
  };
  grow(new THREE.Vector3(), rng() * Math.PI * 2, lead ? 0.8 : 0.9 + 0.5 * rng(), 1);
  return pads;
}

function _succPads(p, d, gy, rng, col, groups, anchors) {
  const H = Math.max(0.05, d.height_m || 0.15);
  const R = Math.max(0.08, (d.canopy_m || 0.5) / 2);
  const dia = Math.max(0.01, (p.flower_diameter_cm || 5) / 100);
  const rimTop = Math.max(0.6 * H, H - 0.7 * dia);   // the flowers sit on the top rims
  const lead = _padChain(rng, true);
  const topU = Math.max(...lead.map((q) => q.base.y + q.d.y));
  const L = Math.min(H / 2.5, rimTop / topU);          // one pad's length, metres
  // Small joints are plumper: Brittle Prickly-pear's are nearly round in
  // section, the plains species' flat. Rounded so a design shares a few shapes.
  const tr = Math.round(Math.max(0.15, Math.min(0.6, 0.02 / L)) * 20) / 20;
  const wr = +(0.92 - 0.45 * (tr - 0.15)).toFixed(2);
  // Small joints are many and need fewer facets each: a brittle prickly-pear
  // is a mat of them, a plains prickly pear a clump of a few dozen pads.
  const small = L < 0.06;
  const want = Math.max(6, Math.min(qn(small ? 80 : 50), Math.round(2 * (R / L) ** 2)));
  const key = wr + ':' + tr;
  const body = _succGroup(groups, 'pad:' + key + ':' + leafSurfaceFor(p), 'succ_pad',
    () => _padGeoS(wr, tr, small ? 4 : 5, small ? 6 : 8),
    () => surfaceMaterial(_SUCC_BODY, leafSurfaceFor(p), true));
  const spines = _succGroup(groups, 'padspine:' + key, 'succ_spine',
    () => _padSpinesGeo(wr, tr), () => surfaceMaterial(_SUCC_SPINE, '', true), false);
  const spineCol = fadeColor(new THREE.Color(_SPINE_HEX), p.opacity);
  let placed = 0, chain = 0;
  while (placed < want && chain < 400) {
    const pads = chain === 0 ? lead : _padChain(rng, false);
    const r = chain === 0 ? 0 : (R - 0.45 * L) * Math.pow(rng(), 0.6);
    const a = rng() * Math.PI * 2;
    const ox = p.x + Math.cos(a) * r, oz = -p.y + Math.sin(a) * r;
    // A chain leans away from the middle of the clump more often than not, as
    // a spreading one does; leaning all one way made a wreath round a bare hole.
    const turn = chain === 0 ? 0 : a - Math.atan2(pads[0].d.z, pads[0].d.x) + (rng() - 0.5) * 2.6;
    for (const q of pads) {
      if (placed >= want) break;
      const b = q.base.clone().applyAxisAngle(_sUp, -turn).multiplyScalar(L);
      const at = new THREE.Vector3(ox + b.x, gy + b.y, oz + b.z);
      const axis = q.d.clone().applyAxisAngle(_sUp, -turn);
      const side = q.w.clone().applyAxisAngle(_sUp, -turn);
      const m = _matAt(at, axis, side, L);
      const c = col.clone().multiplyScalar((q.tier === 1 ? 0.86 : 1.0) * (0.9 + 0.2 * rng()));
      _succPush(body, m, c, p);
      _succPush(spines, m, spineCol, p);
      placed++;
      // A flower on the rim of a pad with nothing growing from it, and never on
      // one lying on the ground.
      if (!q.kids && (q.tier > 1 || q.d.y > 0.5)) {
        const tip = at.clone().addScaledVector(axis, L * 0.97);
        anchors.push({ x: tip.x, y: tip.y + 0.12 * dia, z: tip.z, nx: 0, nz: 0, top: true });
      }
    }
    chain++;
  }
}

function _succBall(p, d, gy, rng, col, groups, anchors) {
  const n = Math.max(1, d.stems || 1);
  const hb = Math.max(0.02, d.ball_m || 0.85 * (d.height_m || 0.1));
  const w = 0.85;                                      // succulent_habit.BALL_WIDTH
  const dia = Math.max(0.01, (p.flower_diameter_cm || 3) / 100);
  const body = _succGroup(groups, 'ball:' + leafSurfaceFor(p), 'succ_ball',
    () => _ballGeoS(w), () => surfaceMaterial(_SUCC_BODY, leafSurfaceFor(p), true));
  const spines = _succGroup(groups, 'ballspine', 'succ_spine',
    () => _ballSpinesGeo(w), () => surfaceMaterial(_SUCC_SPINE, '', true), false);
  const spineCol = fadeColor(new THREE.Color(_SPINE_HEX), p.opacity);
  const a0 = rng() * Math.PI * 2;
  for (let i = 0; i < n; i++) {
    // The tallest in the middle, the rest round it and smaller.
    const h = i === 0 ? hb : hb * (0.6 + 0.3 * rng());
    const ring = i === 0 ? 0 : 0.5 * w * (hb + h) * (0.92 + 0.1 * rng());
    const a = a0 + (i - 1) * (Math.PI * 2 / Math.max(1, n - 1)) + (rng() - 0.5) * 0.5;
    const x = p.x + Math.cos(a) * ring, z = -p.y + Math.sin(a) * ring;
    const tilt = i === 0 ? 0 : 0.12 + 0.1 * rng();     // the outer ones lean out
    const axis = new THREE.Vector3(Math.sin(tilt) * Math.cos(a), Math.cos(tilt),
                                   Math.sin(tilt) * Math.sin(a));
    const at = new THREE.Vector3(x, gy - 0.06 * h, z);
    const m = _matAt(at, axis, new THREE.Vector3(Math.cos(i * 2.4), 0, Math.sin(i * 2.4)), h);
    _succPush(body, m, col.clone().multiplyScalar(0.9 + 0.2 * rng()), p);
    _succPush(spines, m, spineCol, p);
    // The flowers come from the young tubercles round the crown, held just
    // clear of the spines.
    for (let k = 0; k < 3; k++) {
      const q = _ballPoint(0.3, a + k * 2.1, w).applyMatrix4(m);
      anchors.push({ x: q.x, y: q.y + 0.35 * dia, z: q.z, nx: 0, nz: 0, top: true });
    }
  }
}

function _succSwords(p, d, gy, rng, col, groups, anchors, month) {
  const H = Math.max(0.2, d.height_m || 0.9);
  const R = Math.max(0.2, (d.canopy_m || 1) / 2);
  const Lf = Math.max(0.08, d.leaf_m || 0.4);
  const n = Math.max(1, d.stems || 1), stalks = Math.min(n, d.stalks || 1);
  const leaves = _succGroup(groups, 'sword:' + leafSurfaceFor(p), 'succ_sword',
    _swordGeoS, () => surfaceMaterial(_SUCC_SWORD, leafSurfaceFor(p), true));
  const sm = d.stalk_months || [];
  const standing = _inSeason(sm, month);
  const dry = standing && month > (p.bloom_end || sm[0]);
  const stalkCol = fadeColor(dry ? new THREE.Color(p.color).lerp(_SUCC_DRY, 0.8)
                                 : col.clone().lerp(new THREE.Color('#c8c070'), 0.25), p.opacity);
  const stalkG = _succGroup(groups, 'stalk', 'succ_stalk', _stickGeoS,
                            () => surfaceMaterial(_SUCC_FLESH, '', true));
  // A rosette of this species holds fifty to a hundred leaves, radiating from
  // flat (the oldest, outermost) to upright (the youngest), so it is a burst,
  // not a tuft: most of its leaves stand at middling angles.
  const per = qn(Math.round(50 + 50 * Lf));
  const a0 = rng() * Math.PI * 2;
  for (let i = 0; i < n; i++) {
    const ring = i === 0 ? 0 : Math.min(R - 0.6 * Lf, Lf * (0.7 + 0.3 * rng()));
    const a = a0 + i * 2.39996;
    const cx = p.x + Math.cos(a) * Math.max(0, ring), cz = -p.y + Math.sin(a) * Math.max(0, ring);
    for (let k = 0; k < per; k++) {
      const t = k / Math.max(1, per - 1);              // outermost first, young last
      const az = k * 2.39996 + (rng() - 0.5) * 0.3;
      const el = Math.min(1.5, Math.max(0.03, -0.08 + 1.5 * Math.pow(t, 0.75)
                                            + (rng() - 0.5) * 0.2));  // the oldest lie on the soil
      const len = Lf * (0.78 + 0.28 * rng()) * (1 - 0.3 * Math.pow(t, 3));
      const dir = new THREE.Vector3(Math.cos(el) * Math.cos(az), Math.sin(el),
                                    Math.cos(el) * Math.sin(az));
      const r0 = 0.03 * (1 - t);
      const base = new THREE.Vector3(cx + Math.cos(az) * r0, gy + 0.01, cz + Math.sin(az) * r0);
      const m = _matAt(base, dir, new THREE.Vector3(-Math.sin(az), 0, Math.cos(az)), len);
      const age = t < 0.12 ? 0.82 : 1.0;               // the oldest leaves duller
      _succPush(leaves, m, col.clone().multiplyScalar(age * (0.9 + 0.2 * rng())), p);
    }
    if (i >= stalks) continue;
    // The stalk: from the middle of the rosette to the recorded height, the
    // first one exactly, the rest a little short of it.
    const hs = i === 0 ? H : H * (0.86 + 0.1 * rng());
    const lean = 0.03 + 0.06 * rng();
    const axis = new THREE.Vector3(Math.sin(lean) * Math.cos(a), Math.cos(lean),
                                   Math.sin(lean) * Math.sin(a));
    const len = hs / Math.cos(lean);
    const base = new THREE.Vector3(cx, gy, cz);
    const top = base.clone().addScaledVector(axis, len);
    anchors.push({ x: top.x, y: top.y, z: top.z, nx: 0, nz: 0, top: true });
    if (!standing) continue;
    _sq.setFromUnitVectors(_sUp, axis);
    _ss.set(0.011, len, 0.011);
    _succPush(stalkG, new THREE.Matrix4().compose(base, _sq, _ss), stalkCol, p);
  }
}

// One leafy shoot: a stem from `base` along `axis`, `len` long, with `per`
// fleshy leaves spiralling up it, spreading-ascending, the last few smaller.
function _fleshyShoot(p, base, axis, len, per, lf, rng, col, leaves, stems, stemCol) {
  _sq.setFromUnitVectors(_sUp, axis);
  _ss.set(0.0025, len, 0.0025);
  _succPush(stems, new THREE.Matrix4().compose(base, _sq, _ss), stemCol, p);
  const a = rng() * Math.PI * 2;
  for (let k = 0; k < per; k++) {
    const t = 0.05 + 0.9 * (k / Math.max(1, per - 1));
    const az = a + k * 2.39996;
    const out = new THREE.Vector3(Math.cos(az), 0, Math.sin(az));
    const dir = axis.clone().addScaledVector(out, 0.8 + 0.4 * rng()).normalize();
    const at = base.clone().addScaledVector(axis, len * t).addScaledVector(out, 0.002);
    const s = lf * (0.8 + 0.3 * rng()) * (t > 0.85 ? 0.7 : 1);
    const m = _matAt(at, dir, new THREE.Vector3(-Math.sin(az), 0, Math.cos(az)), s);
    _succPush(leaves, m, col.clone().multiplyScalar(0.9 + 0.2 * rng()), p);
  }
  return base.clone().addScaledVector(axis, len);
}

// Whether a flowering stalk stands this month (succulent_habit._season).
function _inSeason(sm, month) {
  return !!sm && sm.length === 2 && month >= sm[0] && month <= sm[1];
}

function _leaning(a, lean) {
  return new THREE.Vector3(Math.sin(lean) * Math.cos(a), Math.cos(lean),
                           Math.sin(lean) * Math.sin(a));
}

function _succFleshy(p, d, gy, rng, col, groups, anchors, month) {
  const H = Math.max(0.05, d.height_m || 0.25);
  const R = Math.max(0.05, (d.canopy_m || 0.3) / 2);
  const n = Math.max(1, d.stems || 1);
  const lf = Math.max(0.01, Math.min(0.08, (p.leaf_size_cm || 3) / 100));
  // A fleshy leaf is thick, so it is the pad's lens made small, broadest above
  // the middle (spatulate to obovate, narrower for a lanceolate one) and lit as
  // a solid: a flat leaf card reads as a dark blade from every side facing away
  // from the sun.
  const lw = /linear|lanceolate|needle|awl/.test(p.leaf_shape || '') ? 0.3 : 0.42;
  const leaves = _succGroup(groups, 'flesh:' + lw + ':' + leafSurfaceFor(p), 'succ_leaf',
    () => _padGeoS(lw, 0.18, 3, 4), () => surfaceMaterial(_SUCC_FLESH, leafSurfaceFor(p), true));
  const stems = _succGroup(groups, 'fstem', 'succ_stem', _stickGeoS,
                           () => surfaceMaterial(_SUCC_FLESH, '', true));
  const stemCol = col.clone().multiplyScalar(0.95);
  // The leaves crowd the stem and overlap, so what shows is a leafy column,
  // not a stem with leaves on it. Roseroot's stems rise from one thick crown;
  // a stonecrop's stand here and there over its mat.
  const per = qn(d.mat ? 8 : 24);
  const a0 = rng() * Math.PI * 2;
  // A stonecrop's flowering stems die after seeding and its mat stays. Out of
  // season they are still generated, into a sink, so the mat does not move
  // when the month does.
  const flowering = !d.mat || _inSeason(d.stalk_months, month);
  const sink = { mats: [], cols: [], names: [], ids: [] };
  for (let i = 0; i < n; i++) {
    const a = a0 + i * 2.39996;
    const r0 = (d.mat ? 0.6 * R : 0.03) * Math.sqrt(rng());
    const axis = _leaning(a, i === 0 ? 0.05 : 0.12 + 0.2 * rng());
    const reach = (i === 0 ? 1 : 0.86 + 0.12 * rng()) * (H - 0.012);
    const base = new THREE.Vector3(p.x + Math.cos(a) * r0, gy, -p.y + Math.sin(a) * r0);
    const top = _fleshyShoot(p, base, axis, reach / axis.y, per, lf, rng, col,
                             flowering ? leaves : sink, flowering ? stems : sink, stemCol);
    if (flowering) anchors.push({ x: top.x, y: top.y + 0.006, z: top.z, nx: 0, nz: 0, top: true });
  }
  if (!d.mat) return;
  // The mat: short sterile shoots, sprawling, over about half the ground.
  const m = Math.max(6, Math.min(qn(24), Math.round(0.55 * (R / (0.9 * lf)) ** 2)));
  for (let i = 0; i < m; i++) {
    const a = rng() * Math.PI * 2, r = (R - 0.5 * lf) * Math.sqrt(rng());
    const base = new THREE.Vector3(p.x + Math.cos(a) * r, gy, -p.y + Math.sin(a) * r);
    const axis = _leaning(rng() * Math.PI * 2, 0.2 + 0.5 * rng());
    _fleshyShoot(p, base, axis, lf * (1.5 + 1.5 * rng()), qn(5), lf, rng, col,
                 leaves, stems, stemCol);
  }
}

// The unit shapes are built per call, as the pond's are: disposeDesignGroup
// frees every geometry it does not know to be shared, and these are cheap.
function buildSucculents(list, month, year, terrain) {
  SUCC_ANCHORS = new Map();
  if (!list || !list.length) return;
  const groups = new Map();
  for (const p of list) {
    const d = p.drawn || {};
    const seed = (hashPid(p.plant_id || 1) ^ Math.round(p.x * 100) * 73856093
                  ^ Math.round(p.y * 100) * 19349663) >>> 0;
    const rng = mulberry32(seed);
    const gy = terrainHeightAt(p.x, p.y, terrain);
    const col = fadeColor(witherColor(seasonalColor(
      p.color, p.foliage_type, month, p.fall_color), p.health), p.opacity);
    const anchors = [];
    if (d.body === 'pads') _succPads(p, d, gy, rng, col, groups, anchors);
    else if (d.body === 'ball') _succBall(p, d, gy, rng, col, groups, anchors);
    else if (d.body === 'swords') _succSwords(p, d, gy, rng, col, groups, anchors, month);
    else if (d.body === 'fleshy') _succFleshy(p, d, gy, rng, col, groups, anchors, month);
    SUCC_ANCHORS.set(p, anchors);
  }
  for (const g of groups.values()) {
    if (!g.mats.length) continue;
    const mesh = instancedMesh(g.geo(), g.mats.length, g.mat(), g.shadow);
    g.mats.forEach((m, i) => { mesh.setMatrixAt(i, m); mesh.setColorAt(i, g.cols[i]); });
    mesh.userData.pick = g.names;
    mesh.userData.pickId = g.ids;
    mesh.userData.part = g.part;
    plantsGroup.add(mesh);
  }
}

window.buildSucculents = buildSucculents;
window.succulentAnchorsFor = succulentAnchorsFor;
