// Part of the Site & Pattern 3D viewer. Loaded as an ordered CLASSIC
// script by the bootstrap in scene3d.html — it shares the global scope
// with its siblings (THREE and friends are globals set by the
// bootstrap). Do not add ES `import`/`export` here.
//
// Design principle P10 — see docs/DESIGN_PHILOSOPHY.md
//
// Vines, drawn by what they hold onto (V2.89, F179). A vine's recorded height is
// how far it CLIMBS. Until V2.89 all six catalogue vines were drawn as free-
// standing leafy columns that tall, so a 6 m Wild Clematis was a 6 m pillar in
// the open. The owner's rule, decided once in Python (src/vine_habit.py) and
// handed over as each vine's `drawn` block: a vine climbs the tree or shrub
// beside it, or, with neither, lies on the ground.
//
// Climbing, it is fitted to the crown that is actually ON SCREEN. A host's crown
// is a baked model scaled to its species, not an ellipsoid, and an ellipsoid is
// wrong where it matters: at 40% of a spruce's height the cone is 60% of its full
// radius and the ellipsoid nearly all of it, so the leaves would hang a metre off
// the tree. 04-quality.js notes every tree and shrub as it instances them; this
// measures that geometry's outer radius per height band and bearing (once per
// archetype) and lays the vine's stems up that surface, on its own side.
//
// The leaves are the species' own outline at its recorded size, from the
// procedural leaf builders in 03-herbs.js. The flowers and fruit sit on them:
// the floret, billboard and fruit layers ask vineAnchorsFor(p) first and fall
// back to their disc around the root only when a plant has no anchors.

let VINE_HOSTS = new Map();      // tree/shrub plant -> the frame it was drawn in
let VINE_ANCHORS = new Map();    // vine plant -> [{x, y, z, nx, nz}], world
const _VPROF = new Map();        // geometry uuid -> outer-radius profile
const _VP_A = 16, _VP_H = 24;    // bearings x height bands per profile
const _VUP = new THREE.Vector3(0, 1, 0);

function vinesReset() { VINE_HOSTS = new Map(); VINE_ANCHORS = new Map(); }

// 04-quality.js, for the first placement of every tree and shrub it instances.
function noteVineHost(p, geos, x, gy, z, sxz, sy, rotY) {
  if (!VINE_HOSTS.has(p)) {
    VINE_HOSTS.set(p, { geos: geos.filter(Boolean), x, gy, z, sxz, sy, rotY,
                        prof: null });
  }
}

function vineAnchorsFor(p) {
  const a = VINE_ANCHORS.get(p);
  return a && a.length ? a : null;
}

// One archetype's outer radius per bearing and height band, in its unit frame
// (height 0..1). The 85th percentile, not the maximum: one leaf card sticking
// out is not where the crown's surface is. Sampled along every triangle EDGE,
// not only at vertices: a trunk is a few long cylinders with vertices at their
// ends only, and read by its vertices it was empty from 2 m to 5 m, so a vine
// climbing an aspen stopped at 1.6 m.
function _profileOf(geo) {
  let pr = _VPROF.get(geo.uuid);
  if (pr) return pr;
  const pos = geo.getAttribute && geo.getAttribute('position');
  const idx = geo.index;
  const bins = Array.from({ length: _VP_A * _VP_H }, () => []);
  const put = (x, y, z) => {
    if (y < 0 || y > 1.02) return;
    const a = Math.floor((Math.atan2(z, x) / (2 * Math.PI) + 0.5) * _VP_A) % _VP_A;
    const h = Math.min(_VP_H - 1, Math.floor(Math.min(0.9999, y) * _VP_H));
    bins[h * _VP_A + a].push(Math.hypot(x, z));
  };
  const n = pos ? (idx ? idx.count : pos.count) : 0;
  const vi = (k) => (idx ? idx.getX(k) : k);
  for (let t = 0; t + 2 < n; t += 3) {
    for (let e = 0; e < 3; e++) {
      const i0 = vi(t + e), i1 = vi(t + (e + 1) % 3);
      const x0 = pos.getX(i0), y0 = pos.getY(i0), z0 = pos.getZ(i0);
      const x1 = pos.getX(i1), y1 = pos.getY(i1), z1 = pos.getZ(i1);
      const steps = Math.max(1, Math.ceil(Math.abs(y1 - y0) * _VP_H * 1.5));
      for (let k = 0; k < steps; k++) {        // the far end is the next edge's start
        const u = k / steps;
        put(x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, z0 + (z1 - z0) * u);
      }
    }
  }
  pr = new Float32Array(_VP_A * _VP_H);
  bins.forEach((r, b) => {
    if (!r.length) return;
    r.sort((u, v) => u - v);
    pr[b] = r[Math.min(r.length - 1, Math.floor(r.length * 0.85))];
  });
  _VPROF.set(geo.uuid, pr);
  return pr;
}

// The host's profile: its parts together (trunk AND crown), with a bearing that
// has no vertices in a band borrowing its neighbours', so the gap between two
// branches is not read as the crown ending.
function _hostProfile(H) {
  if (H.prof) return H.prof;
  const pr = new Float32Array(_VP_A * _VP_H);
  for (const g of H.geos) {
    const q = _profileOf(g);
    for (let i = 0; i < pr.length; i++) pr[i] = Math.max(pr[i], q[i]);
  }
  const out = pr.slice();
  for (let h = 0; h < _VP_H; h++) {
    for (let a = 0; a < _VP_A; a++) {
      if (pr[h * _VP_A + a] > 0) continue;
      for (const d of [-1, 1, -2, 2]) {
        out[h * _VP_A + a] = Math.max(out[h * _VP_A + a],
                                      pr[h * _VP_A + ((a + d + _VP_A) % _VP_A)]);
      }
    }
  }
  return (H.prof = out);
}

// World radius of the host's surface at world bearing `aw` (atan2(z, x)) and
// world height `yw`; 0 where the host has no geometry.
function _hostRadius(H, aw, yw) {
  const yu = (yw - H.gy) / Math.max(1e-6, H.sy);
  if (yu < 0 || yu >= 1) return 0;
  if (!H.geos.length) {                   // not drawn: the scene's ellipsoid
    const t = yu * 2 - 1;
    return H.R * Math.sqrt(Math.max(0, 1 - t * t));
  }
  const pr = _hostProfile(H);
  // setInst2 rotates by rotY about +Y, which turns a local bearing aL into the
  // world bearing aL - rotY; so the local one is aw + rotY.
  const fa = ((aw + H.rotY) / (2 * Math.PI) + 0.5) * _VP_A - 0.5;
  const fh = yu * _VP_H - 0.5;
  const a0 = Math.floor(fa), ta = fa - a0;
  const h0 = Math.max(0, Math.min(_VP_H - 1, Math.floor(fh)));
  const h1 = Math.min(_VP_H - 1, h0 + 1), th = Math.max(0, Math.min(1, fh - h0));
  const A0 = ((a0 % _VP_A) + _VP_A) % _VP_A, A1 = (A0 + 1) % _VP_A;
  const at = (h, a) => pr[h * _VP_A + a];
  const r = (at(h0, A0) * (1 - ta) + at(h0, A1) * ta) * (1 - th)
          + (at(h1, A0) * (1 - ta) + at(h1, A1) * ta) * th;
  return r * H.sxz;
}

// The frame the host was drawn in; failing that (it was not drawn this build),
// the ellipsoid the scene describes.
function _hostFrame(s, all, terrain) {
  const near = (q) => q && Math.abs(q.x - s.x) < 0.05 && Math.abs(q.y - s.y) < 0.05;
  let host = all && s.index != null ? all[s.index] : null;
  if (!near(host)) {
    host = (all || []).find((q) => (q.plant_type === 'tree'
                                     || q.plant_type === 'shrub') && near(q));
  }
  const H = host && VINE_HOSTS.get(host);
  if (H) return H;
  return { geos: [], x: s.x, z: -s.y, gy: terrainHeightAt(s.x, s.y, terrain),
           sxz: 1, sy: Math.max(0.2, s.height_m || 1), rotY: 0,
           R: Math.max(0.1, (s.canopy_m || 1) / 2), prof: null };
}

// Climbing. Two stems in three rise from the root to where the crown reaches out
// to meet the vine (within the vine's own spread of its root) and lean into it;
// the third runs in low, along the ground to where the host rises from it — its
// stems, its trunk — and climbs from there. Each wanders up the surface on the
// vine's side to its own height, below the reach Python gave the vine.
function _climbPaths(p, d, H, gy, rng) {
  const s = d.support, vx = p.x, vz = -p.y;
  const tw = s.toward || [1, 0];
  const phi0 = Math.atan2(-tw[1], tw[0]);          // host -> vine, world bearing
  const R = Math.max(0.2, (s.canopy_m || 1) / 2);
  const spread = Math.max(0.2, (d.canopy_m || 1) / 2);
  // Half the arc of the crown it covers: a big vine on a small shrub wraps
  // most of one side of it; on a tree it is a strip.
  const half = Math.max(0.4, Math.min(1.5, (spread + 0.3) / R));
  const dv = Math.hypot(vx - H.x, vz - H.z);        // the root, off the host's axis
  const top = H.gy + d.height_m;
  const n = qn(Math.max(3, Math.min(9, Math.round(3 + d.height_m * 0.9))));
  const paths = [];
  for (let i = 0; i < n; i++) {
    const off = half * ((i + 0.5) / n * 2 - 1) + (rng() - 0.5) * half / n;
    const end = H.gy + (top - H.gy) * (0.72 + 0.28 * rng());
    const amp = 0.10 + 0.16 * rng(), freq = 1.1 + rng(), ph = rng() * 6.28;
    const a0 = phi0 + off;
    const pts = [], nrm = [], gnd = [];
    const add = (x, y, z, nx, ny, nz, g) => {
      pts.push(new THREE.Vector3(x, y, z));
      nrm.push(new THREE.Vector3(nx, ny, nz).normalize());
      gnd.push(g);
    };
    let yJoin = null, rJoin = 0;
    if (i % 3 !== 2) {
      for (let y = H.gy + 0.1; y <= H.gy + (end - H.gy) * 0.8; y += 0.05) {
        const r = _hostRadius(H, a0, y);
        if (r >= Math.max(0.1, dv - spread)) { yJoin = y; rJoin = r; break; }
      }
    }
    let y, prev;
    if (yJoin != null) {                 // up from the root, leaning in near the top
      const jx = H.x + Math.cos(a0) * rJoin * 1.04, jz = H.z + Math.sin(a0) * rJoin * 1.04;
      const sx = vx + (rng() - 0.5) * 0.2, sz = vz + (rng() - 0.5) * 0.2;
      const steps = Math.max(2, Math.ceil((yJoin - gy) / 0.15));
      for (let k = 0; k < steps; k++) {
        const t = k / steps, e = Math.pow(t, 0.8);   // leaning in as it climbs
        add(sx + (jx - sx) * e, gy + 0.02 + (yJoin - gy - 0.02) * t, sz + (jz - sz) * e,
            Math.cos(a0), 0.3, Math.sin(a0), false);
      }
      y = yJoin; prev = rJoin;
    } else {                             // along the ground, then up the host
      y = H.gy + 0.05;
      let r = _hostRadius(H, a0, y);
      for (let g = 0; r <= 0.01 && y < end && g < 80; g++) {
        y += 0.05;
        r = _hostRadius(H, a0, y);
      }
      if (r <= 0.01) continue;
      const bx = H.x + Math.cos(a0) * r, bz = H.z + Math.sin(a0) * r;
      const run = Math.hypot(bx - vx, bz - vz), px = -(bz - vz) / (run || 1);
      const pz = (bx - vx) / (run || 1);
      for (let k = 0, steps = Math.max(1, Math.ceil(run / 0.25)); k < steps; k++) {
        const t = k / steps, w = Math.sin(t * Math.PI * 2 + ph) * 0.08 * Math.sin(t * Math.PI);
        add(vx + (bx - vx) * t + px * w, gy + 0.02, vz + (bz - vz) * t + pz * w,
            0, 1, 0, true);
      }
      prev = r;
    }
    const dy = Math.max(0.06, Math.min(0.22, (end - y) / 24));
    const surf = [];                   // where it is ON the host, for its side shoots
    for (; y <= end; y += dy) {
      const a = a0 + amp * Math.sin(y * freq + ph);
      let rr = _hostRadius(H, a, y);
      if (rr <= 0.01) {
        if (y > H.gy + (end - H.gy) * 0.6) break;   // over the top of it
        rr = prev;
      }
      // No leap outwards: a stem reaching the crown base runs out through the
      // lower branches instead of jumping straight to the leaf surface.
      rr = prev + Math.max(-2 * dy, Math.min(2 * dy, rr - prev));
      prev = rr;
      const out = rr * (1.03 + 0.03 * rng()) + 0.015;
      add(H.x + Math.cos(a) * out, y, H.z + Math.sin(a) * out,
          Math.cos(a), 0.25, Math.sin(a), false);
      surf.push({ a, y, r: rr });
    }
    if (pts.length >= 3) paths.push({ pts, nrm, gnd });
    _sideShoots(H, surf, rng, paths);
  }
  return paths;
}

// A climbing stem branches: every few samples up it a lateral shoot runs off
// across the host's surface, alternately left and right and a little upwards,
// which is what turns seven strands into a vine COVERING the side of a shrub.
function _sideShoots(H, surf, rng, paths) {
  for (let k = 3; k < surf.length - 1; k += 2 + Math.floor(rng() * 2)) {
    const s0 = surf[k], dir = k % 2 ? 1 : -1;
    const len = 0.25 + 0.35 * rng();
    const pts = [], nrm = [], gnd = [];
    let r = s0.r;
    for (let m = 0; m <= 5; m++) {
      const t = m / 5, a = s0.a + dir * t * len / Math.max(0.25, r);
      const y = s0.y + len * 0.35 * t;
      const rr = _hostRadius(H, a, y);
      if (rr > 0.01) r = r + Math.max(-0.15, Math.min(0.15, rr - r));
      const out = r * 1.04 + 0.015;
      pts.push(new THREE.Vector3(H.x + Math.cos(a) * out, y, H.z + Math.sin(a) * out));
      nrm.push(new THREE.Vector3(Math.cos(a), 0.25, Math.sin(a)).normalize());
      gnd.push(false);
    }
    paths.push({ pts, nrm, gnd });
  }
}

// Nothing to climb: a low tangle of trailing stems over its spread, heaped a
// little over the root and lying flat at the tips.
function _sprawlPaths(p, d, rng, terrain) {
  const vx = p.x, vz = -p.y;
  const R = Math.max(0.1, (d.canopy_m || 0.5) / 2);
  const hMax = Math.max(0.04, d.height_m || _VINE_SPRAWL_H);
  const n = qn(Math.max(5, Math.min(12, Math.round(4 + R * 8))));
  const paths = [];
  for (let i = 0; i < n; i++) {
    const az = (i / n) * Math.PI * 2 + (rng() - 0.5) * 0.7;
    const L = R * (0.55 + 0.45 * rng()), wob = 0.25 + 0.3 * rng();
    const ph = rng() * 6.28, lift = 0.5 + 0.5 * rng();
    const pts = [], nrm = [];
    const segs = Math.max(4, Math.ceil(L / 0.08));
    for (let k = 0; k <= segs; k++) {
      const t = k / segs, a = az + wob * Math.sin(t * 3.2 + ph), r = L * t;
      const x = vx + Math.cos(a) * r, z = vz + Math.sin(a) * r;
      const heap = lift * Math.pow(1 - t, 1.3) * (0.6 + 0.4 * Math.sin(t * 9 + ph) ** 2);
      pts.push(new THREE.Vector3(x, terrainHeightAt(x, -z, terrain) + 0.015
                                    + (hMax - 0.015) * heap, z));
      nrm.push(new THREE.Vector3(Math.cos(a) * 0.35, 1, Math.sin(a) * 0.35).normalize());
    }
    paths.push({ pts, nrm });
  }
  return paths;
}

// A unit leaf of the species' outline: length 1 along +Y, width along +X, face
// +Z. makeLeaf draws its length factor first and its facing second, so both are
// pinned; everything after that is the usual seeded variation.
function _unitLeaf(shape) {
  const fixed = [0.5, 0.75, 0.5];
  let s = 97;
  const rng = () => (fixed.length ? fixed.shift()
                     : ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296));
  const g = makeBladeOrLeaf(rng, 1, leafWidthFor(shape, 1), 0, 0, null, shape);
  g.computeVertexNormals();
  const pos = g.attributes.position, col = new Float32Array(pos.count * 3);
  for (let i = 0; i < pos.count; i++) {
    const v = 0.8 + 0.2 * Math.min(1, Math.max(0, pos.getY(i)));  // darker at the stalk
    col[i * 3] = col[i * 3 + 1] = col[i * 3 + 2] = v;
  }
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  return g;
}

// Leaves along one path: out to the side of the stem and a little up, their
// faces turned outwards. Opposite-leaved species carry them in pairs; a runner
// along the ground carries them sparsely, and blooms only above `floorY`.
function _leavesAlong(path, len, opposite, rng, mats, anchors, floorY, dense) {
  const step = len * (opposite ? 1.7 : 0.95) / (dense || 1);
  let next = step * rng(), dist = 0, side = 1, count = 0;
  const T = new THREE.Vector3(), B = new THREE.Vector3(), P = new THREE.Vector3();
  const ly = new THREE.Vector3(), lz = new THREE.Vector3(), lx = new THREE.Vector3();
  for (let j = 1; j < path.pts.length; j++) {
    const A = path.pts[j - 1], C = path.pts[j], N = path.nrm[j];
    const seg = A.distanceTo(C);
    T.subVectors(C, A).normalize();
    B.crossVectors(T, N);
    if (B.lengthSq() < 1e-8) B.set(-T.z, 0, T.x);
    B.normalize();
    const run = path.gnd && path.gnd[j];
    for (; next <= dist + seg; next += run ? step * 2.5 : step) {
      P.copy(A).lerp(C, seg > 0 ? (next - dist) / seg : 0);
      for (const sg of opposite ? [1, -1] : [side]) {
        const l = len * (0.85 + 0.3 * rng());
        ly.copy(N).multiplyScalar(0.55).addScaledVector(B, sg * 0.75)
          .addScaledVector(_VUP, 0.25 + (rng() - 0.5) * 0.3).normalize();
        lz.copy(N).addScaledVector(ly, -N.dot(ly));
        if (lz.lengthSq() < 1e-8) lz.set(0, 1, 0);
        lz.normalize();
        lx.crossVectors(ly, lz).normalize();
        const m = new THREE.Matrix4().makeBasis(lx, ly, lz)
          .scale(new THREE.Vector3(l, l, l));
        m.setPosition(P.x + N.x * 0.004, P.y, P.z + N.z * 0.004);
        mats.push(m);
      }
      if (count++ % 3 === 0 && !run && P.y >= floorY) {
        anchors.push({ x: P.x, y: P.y, z: P.z, nx: N.x, nz: N.z });
      }
      side = -side;
    }
    dist += seg;
  }
}

const _VINE_LEAF_CAP = 1200;

function buildVines(list, all, month, year, terrain) {
  if (!list || !list.length) return;
  const units = new Map();             // outline -> unit leaf, this build only
  const col = new THREE.Color();
  for (const p of list) {
    const d = p.drawn || { habit: 'sprawling', canopy_m: p.canopy_m || 0.5,
                           height_m: Math.min(_VINE_SPRAWL_H, p.height_m || 0.3) };
    const herbaceous = (p.foliage_type || '') === 'herbaceous';
    const bare = _isDecid(p.foliage_type) && _bareMonth(month);
    if (bare && herbaceous) continue;   // died back to the ground for the winter
    const seed = (hashPid(p.plant_id || 1) ^ Math.round(p.x * 100) * 73856093
                  ^ Math.round(p.y * 100) * 19349663) >>> 0;
    const rng = mulberry32(seed);
    const gy = terrainHeightAt(p.x, p.y, terrain);
    let paths = (d.habit === 'climbing' && d.support)
      ? _climbPaths(p, d, _hostFrame(d.support, all, terrain), gy, rng) : null;
    if (paths && paths.length) paths.climbing = true;
    else paths = _sprawlPaths(p, d, rng, terrain);

    const name = p.common_name || '';
    // Stems: woody ones in their bark, herbaceous ones green.
    const stemHex = p.bark_color || (herbaceous ? '#5f7d3c' : '#6e5a44');
    const tubes = paths.map((pa) => new THREE.TubeGeometry(
      new THREE.CatmullRomCurve3(pa.pts), Math.max(4, pa.pts.length * 2),
      herbaceous ? 0.003 : 0.006, 4, false));
    const stemGeo = tubes.length > 1 ? mergeGeometries(tubes, false) : tubes[0];
    if (tubes.length > 1) tubes.forEach((t) => t.dispose());
    const stems = instancedMesh(stemGeo, 1, MATS.branch, false);
    stems.setMatrixAt(0, new THREE.Matrix4());
    stems.setColorAt(0, fadeToward(stemHex, p.opacity));
    stems.userData.pick = [name];
    stems.userData.pickId = [p.plant_id];
    stems.userData.part = 'vine_stem';
    plantsGroup.add(stems);

    // Where its flowers and fruit may go: up the host, not along the runner at
    // its foot (the lowest third of a climb is mostly stems).
    const climbing = paths.climbing;
    const floorY = climbing ? gy + 0.33 * d.height_m : -Infinity;
    const anchors = [];
    for (const pa of paths) {
      const q = pa.pts[pa.pts.length - 1], n = pa.nrm[pa.nrm.length - 1];
      if (q.y >= floorY) anchors.push({ x: q.x, y: q.y, z: q.z, nx: n.x, nz: n.z });
    }
    if (!bare) {
      const shape = p.leaf_shape || 'elliptic';
      if (!units.has(shape)) units.set(shape, _unitLeaf(shape));
      const len = Math.max(0.03, Math.min(0.25, (p.leaf_size_cm || 6) / 100));
      let mats = [];
      for (const pa of paths) {
        _leavesAlong(pa, len, p.leaf_arrangement === 'opposite', rng, mats, anchors,
                     floorY, 1.6);                // a vine is densely leafy
      }
      if (mats.length > _VINE_LEAF_CAP) {
        const keep = _VINE_LEAF_CAP / mats.length;
        mats = mats.filter(() => rng() < keep);
      }
      if (mats.length) {
        const leaves = instancedMesh(units.get(shape), mats.length, MATS.leaf);
        const base = fadeColor(witherColor(seasonalColor(
          p.color, p.foliage_type, month, p.fall_color), p.health), p.opacity);
        mats.forEach((m, i) => {
          leaves.setMatrixAt(i, m);
          leaves.setColorAt(i, col.copy(base).multiplyScalar(0.9 + 0.2 * rng()));
        });
        leaves.userData.pick = mats.map(() => name);
        leaves.userData.pickId = mats.map(() => p.plant_id);
        leaves.userData.part = 'vine';
        plantsGroup.add(leaves);
      }
    }
    VINE_ANCHORS.set(p, anchors);
  }
}

window.buildVines = buildVines;
window.noteVineHost = noteVineHost;
window.vinesReset = vinesReset;
window.vineAnchorsFor = vineAnchorsFor;
