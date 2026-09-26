// ── The pond (V2.90, F175) ──────────────────────────────────────────────────
// Design principle P5 — see docs/DESIGN_PHILOSOPHY.md
//
// Until V2.90 every aquatic was one reed tuft: a pond-lily stood 20 cm up in the
// air and a submerged pondweed half a metre. Each wetland plant now arrives with
// a `drawn` block from src/pond_habit.py (its body, the water level under it,
// how high it is drawn), and this chunk draws three of the bodies:
//
//   floating   pads lying on the water, in the species' leaf outline at its
//              recorded size, as many as cover about 60% of its spread;
//   submerged  only what reaches the surface: a loose tangle of shoot tips
//              lying on it (the flower layer puts the spikes above them);
//   broadleaf  leaves on stalks rising from one crown, each in the species'
//              outline (arrowhead, heart, three leaflets), to its height.
//
// Mare's-tail (`whorled`) is the horsetail builder's unit 3 (14-layers.js),
// Water Parsnip (`herb`) the herb layer's, the reeds the aquatic tuft's.
// A pond's water is an opaque sheet (struct_pond.glb), so a pad drawn at ground
// level inside one would be invisible: pads sit at `drawn.water_m`.
//
// Floating and submerged bodies are not drawn November to March, when the pond
// is frozen and their leaves have died back or sunk. Emergents brown with the
// season like any herb.

const _POND_COVER = 0.6;        // share of a floating plant's spread under pads
const _POND_PAD_MIN_R = 0.006;  // a duckweed frond is drawn no smaller than this
const _POND_PAD_CAP = 150;
const _POND_LIFT = 0.006;       // pads just above the water, clear of z-fighting

// A floating leaf: a disc, notched to the centre for a heart (pond-lily) or a
// kidney (floating marsh-marigold, which is also wider than it is long).
function _padGeo(shape) {
  const notch = shape === 'cordate' || shape === 'reniform' ? 0.22 : 0;
  const sx = shape === 'reniform' ? 1.2 : 1.0;
  const n = 28, pos = [0, 0, 0], col = [0.8, 0.8, 0.8];
  for (let i = 0; i <= n; i++) {
    const a = notch + (i / n) * (Math.PI * 2 - 2 * notch);
    pos.push(Math.cos(a) * sx, 0, Math.sin(a));
    col.push(1, 1, 1);                          // lighter towards the rim
  }
  const idx = [];
  for (let i = 1; i <= n; i++) idx.push(0, i + 1, i);   // wound to face +y
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

function _stalkGeo() {
  const g = new THREE.CylinderGeometry(1, 1, 1, 5, 1, true);
  g.translate(0, 0.5, 0);
  g.setAttribute('color', new THREE.BufferAttribute(
    new Float32Array(g.attributes.position.count * 3).fill(0.82), 3));
  return g;
}

const _pv = new THREE.Vector3(), _pq = new THREE.Quaternion(),
      _ps = new THREE.Vector3(), _pUp = new THREE.Vector3(0, 1, 0);

// One group of instances: a part of one outline, e.g. every arrowhead blade.
function _pondGroup(groups, key, part, shape) {
  let g = groups.get(key);
  if (!g) groups.set(key, g = { part, shape, mats: [], cols: [], names: [], ids: [] });
  return g;
}

function _pondPush(g, m, col, p) {
  g.mats.push(m); g.cols.push(col); g.names.push(p.common_name || '');
  g.ids.push(p.plant_id);
}

// Pads on the water: the species' outline, sized by its recorded leaf.
function _pondFloating(p, d, gy, rng, col, groups) {
  const shape = p.leaf_shape === 'reniform' || p.leaf_shape === 'cordate'
    ? p.leaf_shape : 'orbicular';
  const R = Math.max(0.05, (p.canopy_m || 0.3) / 2);
  const rp = Math.max(_POND_PAD_MIN_R, (p.leaf_size_cm || 5) / 200);
  const n = qn(Math.max(3, Math.min(_POND_PAD_CAP,
    Math.round(_POND_COVER * R * R / (rp * rp)))));
  const y = gy + (d.water_m || 0) + _POND_LIFT;
  const g = _pondGroup(groups, 'pad:' + shape, 'pond_pad', shape);
  for (let i = 0; i < n; i++) {
    const a = rng() * Math.PI * 2, r = Math.max(0, R - rp * 0.5) * Math.sqrt(rng());
    const s = rp * (0.7 + 0.45 * rng());
    _pv.set(p.x + Math.cos(a) * r, y + (i % 7) * 0.0007, -p.y + Math.sin(a) * r);
    _pq.setFromAxisAngle(_pUp, rng() * Math.PI * 2);
    _ps.set(s, 1, s);
    _pondPush(g, new THREE.Matrix4().compose(_pv, _pq, _ps),
              col.clone().multiplyScalar(0.85 + 0.25 * rng()), p);
  }
}

// What a submerged plant shows: shoot tips lying on the surface, darker for the
// water over them. Their length is a shoot's, not the recorded leaf's (a
// waterweed leaf is 1.5 cm, invisible from a path).
function _pondSubmerged(p, d, gy, rng, col, groups) {
  const shape = p.leaf_shape || 'linear';
  const R = Math.max(0.08, (p.canopy_m || 0.4) / 2);
  const n = qn(Math.max(6, Math.min(28, Math.round(6 + R * 24))));
  const y = gy + (d.water_m || 0) + 0.004;
  const g = _pondGroup(groups, 'sprig:' + shape, 'pond_sprig', shape);
  const ly = new THREE.Vector3(), lz = new THREE.Vector3(), lx = new THREE.Vector3();
  for (let i = 0; i < n; i++) {
    const a = rng() * Math.PI * 2, r = R * Math.sqrt(rng()), az = rng() * Math.PI * 2;
    const len = 0.05 + 0.08 * rng();
    ly.set(Math.cos(az), 0.12 + 0.12 * rng(), Math.sin(az)).normalize();
    lz.copy(_pUp).addScaledVector(ly, -_pUp.dot(ly)).normalize();
    lx.crossVectors(ly, lz).normalize();
    const m = new THREE.Matrix4().makeBasis(lx, ly, lz)
      .scale(new THREE.Vector3(len, len, len));
    m.setPosition(p.x + Math.cos(a) * r, y, -p.y + Math.sin(a) * r);
    _pondPush(g, m, col.clone().multiplyScalar(0.7 + 0.15 * rng()), p);
  }
}

// Broad leaves on stalks from one crown, leaning out, each blade tilted off the
// vertical: arrowheads stand nearly upright, buckbean's trifoliate leaves spread.
function _pondBroad(p, gy, rng, col, groups) {
  const shape = p.leaf_shape || 'ovate';
  const H = Math.max(0.1, bodyHeightOf(p));
  const C = Math.max(0.15, p.canopy_m || 0.4);
  const n = qn(Math.max(5, Math.min(12, Math.round(4 + C * 8))));
  const Lb = Math.max(0.05, Math.min(0.35, (p.leaf_size_cm || 12) / 100));
  const blades = _pondGroup(groups, 'leaf:' + shape, 'pond_leaf', shape);
  const stalks = _pondGroup(groups, 'stalk', 'pond_stalk', '');
  const ly = new THREE.Vector3(), lz = new THREE.Vector3(), lx = new THREE.Vector3();
  const dir = new THREE.Vector3(), base = new THREE.Vector3(), top = new THREE.Vector3();
  const r = H > 0.5 ? 0.005 : 0.0035;
  for (let i = 0; i < n; i++) {
    const az = (i / n) * Math.PI * 2 + (rng() - 0.5) * 0.8;
    const ca = Math.cos(az), sa = Math.sin(az);
    const off = C * 0.08 * rng();
    base.set(p.x + ca * off, gy, -p.y + sa * off);
    const lean = 0.15 + 0.35 * rng();            // stalk off the vertical
    const bt = 0.35 + 0.7 * rng();               // blade off the vertical
    const s = Lb * (0.85 + 0.3 * rng());
    const hp = Math.max(0.04, H * (0.72 + 0.28 * rng()) - s * Math.cos(bt));
    const Lp = hp / Math.cos(lean);
    dir.set(Math.sin(lean) * ca, Math.cos(lean), Math.sin(lean) * sa);
    top.copy(base).addScaledVector(dir, Lp);
    _pq.setFromUnitVectors(_pUp, dir);
    _ps.set(r, Lp, r);
    _pondPush(stalks, new THREE.Matrix4().compose(base, _pq, _ps),
              col.clone().multiplyScalar(0.8), p);
    // The blade leans out; its upper face looks up and in, to the sky.
    ly.set(Math.sin(bt) * ca, Math.cos(bt), Math.sin(bt) * sa);
    lz.set(-Math.cos(bt) * ca, Math.sin(bt), -Math.cos(bt) * sa);
    lx.crossVectors(ly, lz).normalize();
    const m = new THREE.Matrix4().makeBasis(lx, ly, lz)
      .scale(new THREE.Vector3(s, s, s));
    m.setPosition(top.x, top.y, top.z);
    _pondPush(blades, m, col.clone().multiplyScalar(0.9 + 0.2 * rng()), p);
  }
}

// The unit shapes are built per call, as the vines' are: disposeDesignGroup
// frees every geometry it does not know to be shared, and these are cheap.
function buildPond(list, month, year, terrain) {
  if (!list || !list.length) return;
  const groups = new Map();
  for (const p of list) {
    const d = p.drawn || {};
    const onWater = d.body === 'floating' || d.body === 'submerged';
    if (onWater && _isDecid(p.foliage_type) && _bareMonth(month)) continue;
    const seed = (hashPid(p.plant_id || 1) ^ Math.round(p.x * 100) * 73856093
                  ^ Math.round(p.y * 100) * 19349663) >>> 0;
    const rng = mulberry32(seed);
    const gy = terrainHeightAt(p.x, p.y, terrain);
    const col = fadeColor(witherColor(seasonalColor(
      p.color, p.foliage_type, month, p.fall_color), p.health), p.opacity);
    if (d.body === 'floating') _pondFloating(p, d, gy, rng, col, groups);
    else if (d.body === 'submerged') _pondSubmerged(p, d, gy, rng, col, groups);
    else if (d.body === 'broadleaf') _pondBroad(p, gy, rng, col, groups);
  }
  for (const g of groups.values()) {
    if (!g.mats.length) continue;
    const geo = g.part === 'pond_pad' ? _padGeo(g.shape)
              : g.part === 'pond_stalk' ? _stalkGeo() : unitLeafGeo(g.shape);
    const mesh = instancedMesh(geo, g.mats.length, MATS.leaf);
    g.mats.forEach((m, i) => { mesh.setMatrixAt(i, m); mesh.setColorAt(i, g.cols[i]); });
    mesh.userData.pick = g.names;
    mesh.userData.pickId = g.ids;
    mesh.userData.part = g.part;
    plantsGroup.add(mesh);
  }
}

window.buildPond = buildPond;
