// Part of the Site & Pattern 3D viewer. Loaded as an ordered CLASSIC
// script by the bootstrap in scene3d.html — it shares the global scope
// with its siblings (THREE and friends are globals set by the
// bootstrap). Do not add ES `import`/`export` here.
//
// ── The bloom, as geometry (V2.34, schema v53) ──────────────────────────────
//
// A wildflower in bloom is 60–80% flower to the eye. Until this chunk existed
// the app drew that flower as ONE 64 × 64 image per `flower_form` — fifteen
// pictures for 228 wildflowers — on `MeshBasicMaterial`, which is unlit, so a
// bloom took no sun, cast into no shadow and did not change at dusk. Seven
// copies were scattered in a disc at 90% of the plant's height. The body
// underneath had by then grown real leaves of the species' own outline and size
// at ~1,200 triangles.
//
// That mismatch is what reads as a cheap video game, and it is not a resolution
// problem: a faceted low-poly plant looks *fine* because it is a confident
// abstraction, while a realistically-leaved body wearing a cartoon bloom invites
// a comparison with a real plant and loses it.
//
// So a flower is built from the characters someone standing in front of it would
// actually name (schema v53):
//
//   the FLORET   petal count × petal shape × radial/bilateral symmetry, plus a
//                separate disc in its own colour — a black-eyed Susan IS its
//                dark disc, and it was a yellow blob
//   the ARCHITECTURE  where the florets sit in space, which is most of a forb's
//                silhouette: a goldenrod's plume, a yarrow's flat corymb and a
//                lupine's spike are three ARCHITECTURES, not three textures
//
// Empty data falls back to the billboard (05-flowers.js), so partial coverage is
// never a broken plant. Stylised keeps the billboard on purpose: a flat coloured
// stamp is honest inside a flat-shaded diagram, which is exactly what it is not
// inside a Lifelike scene.
//
// Design principle P5 (perception is constructed, not received) — see
// docs/DESIGN_PHILOSOPHY.md.

const FLORET_ARCHITECTURES = ['solitary', 'raceme', 'spike', 'panicle',
                              'corymb', 'umbel', 'head', 'cyme', 'whorl'];
const PETAL_SHAPES = ['narrow', 'oval', 'notched', 'tubular', 'lipped'];

// How many florets are DRAWN, against how many the plant carries. A yarrow
// corymb holds ~200 and reads as roughly fifteen white dots at yard scale;
// drawing all 200 would cost 13× for a picture nobody can resolve. sqrt keeps
// the ordering honest (a 200-floret corymb still reads denser than a 12-floret
// raceme) without the count running away.
const _FLORET_CAP = 20;
function _drawnFlorets(n) {
  const want = Math.round(Math.sqrt(Math.max(1, n || 1)) * 2.6);
  return Math.max(1, Math.min(qn(_FLORET_CAP), want));
}

// ── one floret ──────────────────────────────────────────────────────────────

// A petal as a flat tapered blade lying in the XZ plane, its base at the origin
// and its tip out along +X, cupped by `lift` so a flower is a shallow bowl
// rather than a paper cut-out. Position-only, so it merges with its siblings.
function _petal(len, wid, lift, shape) {
  const g = new THREE.BufferGeometry();
  const w = wid * 0.5;
  let v;
  if (shape === 'narrow') {
    // A ray floret: widest a third of the way out, tapering to a point.
    v = [0, 0, 0, len * 0.35, lift * 0.35, -w, len * 0.35, lift * 0.35, w,
         len, lift, 0];
    g.setIndex([0, 1, 2, 1, 3, 2]);
  } else if (shape === 'notched') {
    // Two lobes and a notch at the tip — the mark on a phlox, a geranium, a
    // blanketflower ray.
    v = [0, 0, 0, len * 0.45, lift * 0.5, -w, len * 0.45, lift * 0.5, w,
         len, lift, -w * 0.55, len * 0.72, lift * 0.9, 0, len, lift, w * 0.55];
    g.setIndex([0, 1, 2, 1, 3, 4, 1, 4, 2, 2, 4, 5]);
  } else {
    // oval — the default broad petal.
    v = [0, 0, 0, len * 0.4, lift * 0.45, -w, len * 0.4, lift * 0.45, w,
         len * 0.8, lift * 0.9, -w * 0.6, len * 0.8, lift * 0.9, w * 0.6,
         len, lift, 0];
    g.setIndex([0, 1, 2, 1, 3, 4, 1, 4, 2, 3, 5, 4]);
  }
  g.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
  return g;
}

// A tube floret (a penstemon throat, a bergamot's, a thistle's): a short open
// cylinder pointing along +X. No spreading petals to draw — the tube IS the
// flower, and pretending otherwise is what made every tubular species look like
// a daisy.
function _tube(len, wid) {
  const g = new THREE.CylinderGeometry(wid * 0.42, wid * 0.62, len, 6, 1, true);
  g.rotateZ(-Math.PI / 2);
  g.translate(len * 0.5, 0, 0);
  g.deleteAttribute('normal');
  g.deleteAttribute('uv');
  return g.toNonIndexed();
}

// One floret, in a frame 1.0 across (so the caller scales by real diameter) with
// its face looking up +Y and its stem attachment at the origin.
//
// A bilateral flower is not a daisy with the petals moved: it is a banner above,
// two wings out to the sides and a keel below (the pea), or an upper and a lower
// lip (the mints and penstemons). Drawing it radially is the single most
// common way a generated flower gives itself away.
function _buildFloret(petals, shape, symmetry) {
  const parts = [];
  const n = Math.max(1, Math.min(60, petals || 5));
  if (shape === 'tubular') {
    // Radially arranged tubes on a small head (a thistle, a blazingstar).
    const m = Math.max(3, Math.min(9, n || 5));
    for (let i = 0; i < m; i++) {
      const a = (i / m) * Math.PI * 2;
      const t = _tube(0.5, 0.16);
      t.rotateZ(0.95);                    // stand them up, splayed outward
      t.rotateY(a);
      parts.push(t);
    }
  } else if (symmetry === 'bilateral') {
    const banner = _petal(0.52, 0.60, 0.10, shape === 'lipped' ? 'oval' : shape);
    banner.rotateZ(0.85);                             // upright behind
    parts.push(banner);
    for (const s of [-1, 1]) {
      const wing = _petal(0.44, 0.26, 0.05, 'oval');
      wing.rotateZ(0.18);
      wing.rotateY(s * 0.85);
      parts.push(wing);
    }
    const keel = _petal(0.40, 0.22, -0.04, 'narrow');
    keel.rotateZ(-0.45);                              // the lower lip / keel
    parts.push(keel);
  } else {
    const len = 0.5, lift = shape === 'narrow' ? 0.06 : 0.11;
    const wid = Math.min(0.62, (2 * Math.PI * len * 0.62) / n);
    for (let i = 0; i < n; i++) {
      const p = _petal(len, wid, lift, shape);
      p.rotateY((i / n) * Math.PI * 2);
      parts.push(p);
    }
  }
  const g = mergeGeometries(parts, false);
  g.computeVertexNormals();
  return g;
}

// The disc / eye, in the same frame: a shallow dome at the centre. Its size is
// the ray-vs-disc balance — a coneflower is mostly cone, an aster mostly ray.
function _buildDisc(arch, symmetry) {
  const r = arch === 'head' ? 0.20 : 0.11;
  const g = new THREE.SphereGeometry(r, 8, 5, 0, Math.PI * 2, 0, Math.PI * 0.55);
  g.scale(1, arch === 'head' ? 0.9 : 0.55, 1);
  g.deleteAttribute('uv');
  return g;
}

const _FLORET_CACHE = new Map();
function floretGeometry(petals, shape, symmetry) {
  const key = petals + '|' + shape + '|' + symmetry;
  let g = _FLORET_CACHE.get(key);
  if (!g) { g = _buildFloret(petals, shape, symmetry); _FLORET_CACHE.set(key, g); }
  return g;
}
const _DISC_CACHE = new Map();
function discGeometry(arch, symmetry) {
  const key = arch + '|' + symmetry;
  let g = _DISC_CACHE.get(key);
  if (!g) { g = _buildDisc(arch, symmetry); _DISC_CACHE.set(key, g); }
  return g;
}

// ── where the florets sit ───────────────────────────────────────────────────
//
// Returns positions in a UNIT INFLORESCENCE frame: y from 0 (where the head
// meets its stalk) to 1, radius within ±0.5. The caller scales that frame to the
// head's real size and drops it on the plant. `tilt` is the floret's nod from
// face-up; `spin` its bearing about the stem.
function floretPlacements(arch, count, rnd) {
  const out = [];
  const push = (x, y, z, tilt, spin, scale) =>
    out.push({ x, y, z, tilt, spin, scale: scale == null ? 1 : scale });
  const n = Math.max(1, count);
  switch (arch) {
    case 'solitary':
      push(0, 1, 0, 0.25 + rnd() * 0.2, rnd() * 6.28);
      break;
    case 'head':
      // The florets ARE the head: one face-up flower, drawn as the floret plus
      // its disc. Anything more is invisible at the scale a head is seen.
      push(0, 1, 0, 0.18 + rnd() * 0.18, rnd() * 6.28);
      break;
    case 'raceme':
    case 'spike': {
      // Up an axis, oldest at the bottom, each on a short pedicel (a raceme) or
      // sessile against the stem (a spike). Both face outward, so the classic
      // lupine/penstemon column reads from any angle.
      const ped = arch === 'raceme' ? 0.16 : 0.05;
      for (let i = 0; i < n; i++) {
        const t = n === 1 ? 1 : i / (n - 1);
        const a = i * 2.39996;
        const r = ped * (0.7 + 0.6 * rnd());
        push(Math.cos(a) * r, 0.08 + 0.92 * t, Math.sin(a) * r,
             1.15 + (rnd() - 0.5) * 0.5, a + Math.PI,
             // Buds at the growing tip are smaller than the open flowers below.
             0.72 + 0.34 * (1 - t));
      }
      break;
    }
    case 'panicle': {
      // A branching spray, widest low and tapering to a point — the goldenrod
      // plume, and the reason nine Solidago species should not look like discs.
      for (let i = 0; i < n; i++) {
        const t = n === 1 ? 1 : i / (n - 1);
        const a = i * 2.39996;
        const r = (0.42 * (1 - t) + 0.05) * (0.5 + rnd());
        push(Math.cos(a) * r, 0.10 + 0.90 * t, Math.sin(a) * r,
             0.9 + (rnd() - 0.5) * 0.7, a + Math.PI, 0.7 + 0.4 * (1 - t));
      }
      break;
    }
    case 'corymb': {
      // Flat-topped: florets at DIFFERENT stem heights reaching the SAME level.
      // That flat plate is what makes a yarrow a landing platform for the short-
      // tongued bees and flies that work it — the shape is the ecology.
      for (let i = 0; i < n; i++) {
        const a = i * 2.39996, r = Math.sqrt((i + 0.5) / n) * 0.48;
        push(Math.cos(a) * r, 0.94 + rnd() * 0.06, Math.sin(a) * r,
             0.06 + rnd() * 0.16, rnd() * 6.28);
      }
      break;
    }
    case 'umbel': {
      // Rays from ONE point, so the cluster domes: the Apiaceae signature, and
      // the nodding onion's.
      for (let i = 0; i < n; i++) {
        const a = i * 2.39996, f = Math.sqrt((i + 0.5) / n);
        const r = f * 0.46;
        push(Math.cos(a) * r, 1 - f * f * 0.22, Math.sin(a) * r,
             f * 0.9 + rnd() * 0.15, a + Math.PI);
      }
      break;
    }
    case 'whorl': {
      // Rings around the stem at intervals — the mints, and mare's tail.
      const rings = Math.max(1, Math.min(4, Math.round(n / 5)));
      const per = Math.max(2, Math.round(n / rings));
      for (let k = 0; k < rings; k++) {
        const y = 0.25 + 0.75 * (rings === 1 ? 1 : k / (rings - 1));
        for (let i = 0; i < per; i++) {
          const a = (i / per) * Math.PI * 2 + k * 0.7;
          push(Math.cos(a) * 0.16, y, Math.sin(a) * 0.16,
               1.35 + (rnd() - 0.5) * 0.3, a + Math.PI);
        }
      }
      break;
    }
    default: {          // cyme — the terminal flower opens first, then the sides
      push(0, 1, 0, 0.2 + rnd() * 0.2, rnd() * 6.28);
      for (let i = 1; i < n; i++) {
        const a = i * 2.39996, t = i / n;
        const r = 0.16 + 0.30 * t;
        push(Math.cos(a) * r, 0.98 - 0.34 * t, Math.sin(a) * r,
             0.35 + rnd() * 0.5, a + Math.PI, 0.8 + 0.25 * (1 - t));
      }
      break;
    }
  }
  return out;
}

// ── the layer ───────────────────────────────────────────────────────────────

// How far a multi-floret inflorescence reaches, as a multiple of what its
// florets alone would occupy. A goldenrod's florets are 6 mm and its plume is
// 25 cm; a yarrow's are 5 mm and its corymb is 8 cm across. The architecture,
// not the floret, sets that — which is the whole reason this column exists
// separately from flower_diameter_cm.
const _ARCH_REACH = { raceme: 2.6, spike: 2.6, panicle: 3.4, corymb: 1.7,
                      umbel: 1.6, whorl: 2.4, cyme: 1.7 };

function _headSize(p, arch, drawn) {
  const dia = Math.max(0.15, Math.min(20, p.flower_diameter_cm || 2)) / 100;
  // A head and a solitary flower are drawn at their TRUE diameter, and that is
  // the point: a black-eyed Susan is 7 cm across and should read as 7 cm across
  // from four metres away. The billboard sized every bloom off the plant's
  // canopy instead, so a pasqueflower and a sunflower scaled with the plant
  // rather than with the flower — which is exactly the translation-to-the-real-
  // world this whole pass is for.
  if (arch === 'head' || arch === 'solitary') return dia;
  const reach = _ARCH_REACH[arch] || 2.0;
  return Math.max(dia * 2.2, Math.min(0.55, dia * Math.sqrt(drawn) * reach));
}

// Which plants this layer can draw. Everything else goes back to the billboard.
function floretsApply(p) {
  return !STYLISED && !!p.flower_arch && !p.inflorescence_form;
}

function buildFlorets(plants, month, terrain) {
  if (!plants || !plants.length) return;
  const buckets = new Map();
  const _c = new THREE.Color(), _cc = new THREE.Color();
  for (const p of plants) {
    const arch = FLORET_ARCHITECTURES.indexOf(p.flower_arch) >= 0
      ? p.flower_arch : 'cyme';
    const shape = PETAL_SHAPES.indexOf(p.petal_shape) >= 0 ? p.petal_shape : 'oval';
    const sym = p.flower_symmetry === 'bilateral' ? 'bilateral' : 'radial';
    const petals = Math.max(0, Math.min(60, p.petal_count == null ? 5 : p.petal_count));
    // petal_count 0 is a real value — the rayless composites (a thistle, sage,
    // pussytoes) have no ray florets at all, and drawing them five is exactly
    // the invented detail P9 forbids. They render as their disc alone.
    const key = petals + '|' + shape + '|' + sym + '|' + arch;
    let b = buckets.get(key);
    if (!b) { b = { arch, shape, sym, petals, items: [] }; buckets.set(key, b); }
    b.items.push(p);
  }

  for (const b of buckets.values()) {
    const petalXf = [], petalCol = [], discXf = [], discCol = [];
    const names = [], ids = [], discNames = [], discIds = [];
    for (const p of b.items) {
      const gy = terrainHeightAt(p.x, p.y, terrain);
      const h = Math.max(0.1, p.height_m);
      const frac = Math.max(0.3, Math.min(1.3, p.flower_height_frac || 1.0));
      const rad = Math.max(0.10, p.canopy_m * 0.5);
      const seed = hashPid(p.plant_id || 1);
      let s = seed >>> 0;
      const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
      _c.set(p.flower_color || '#ffffff');
      const hasDisc = !!p.flower_center_color;
      if (hasDisc) _cc.set(p.flower_center_color);
      const drawn = _drawnFlorets(p.florets_per_head);
      const size = _headSize(p, b.arch, drawn);
      // How many inflorescences the plant carries. The billboard used a flat
      // seven for every forb; a mature bergamot holds thirty heads and a
      // pasqueflower holds two, and the difference is most of what "in full
      // bloom" looks like. Nothing in the catalogue records flowering stems (it
      // is on the list of things worth going out and counting), so this is
      // scaled off the plant's spread, which is the closest honest proxy.
      const heads = qn(p.plant_type === 'tree' ? 10
                     : p.plant_type === 'shrub' ? 9
                     : Math.max(3, Math.min(16, Math.round(3 + 11 * rad))));
      // Flowers are held on STEMS, and stems converge on one crown: they do not
      // fill the canopy disc the way leaves do. The billboard spread its quads
      // right out to the canopy edge (sqrt-spaced for even areal density, which
      // is correct for foliage and wrong for blooms) and a lupine came out with
      // racemes floating half a metre off its own stem.
      const spread = b.arch === 'corymb' || b.arch === 'umbel' ? 0.55 : 0.42;
      for (let k = 0; k < heads; k++) {
        const a = rnd() * Math.PI * 2;
        const rr = rad * spread * Math.sqrt(rnd());
        const hx = p.x + Math.cos(a) * rr;
        const hz = -(p.y + Math.sin(a) * rr);
        // Where on the stem the inflorescence starts. flower_height_frac is the
        // species' own answer (schema v53) — a scape holds its head clear of the
        // foliage, a clump carries them among the leaves.
        const hy = gy + h * frac * (0.70 + 0.22 * rnd());
        const spin0 = rnd() * Math.PI * 2;
        const lean = (rnd() - 0.5) * 0.30;
        for (const f of floretPlacements(b.arch, drawn, rnd)) {
          const sc = size * f.scale;
          // The unit inflorescence frame is `size` tall and `size` across;
          // rotate the whole head about its own axis so a bed is not a rank of
          // clones, then place each floret inside it.
          const cs = Math.cos(spin0), sn = Math.sin(spin0);
          const fx = f.x * cs - f.z * sn, fz = f.x * sn + f.z * cs;
          petalXf.push(hx + fx * size, hy + f.y * size * 1.1, hz + fz * size,
                       f.tilt + lean, f.spin + spin0, sc);
          petalCol.push(_c.r, _c.g, _c.b);
          names.push(p.common_name || '');
          ids.push(p.plant_id);
          if (hasDisc) {
            discXf.push(hx + fx * size, hy + f.y * size * 1.1, hz + fz * size,
                        f.tilt + lean, f.spin + spin0, sc);
            discCol.push(_cc.r, _cc.g, _cc.b);
            discNames.push(p.common_name || '');
            discIds.push(p.plant_id);
          }
        }
      }
    }
    if (b.petals > 0) {
      _addFloretMesh(floretGeometry(b.petals, b.shape, b.sym),
                     petalXf, petalCol, names, ids);
    }
    if (discXf.length) {
      _addFloretMesh(discGeometry(b.arch, b.sym), discXf, discCol,
                     discNames, discIds);
    }
  }
}

// A floret takes the SUN, which the billboard never did: MeshBasicMaterial is
// unlit, so a bed of flowers stayed the same flat colour at noon, at dusk and in
// the shade of the tree beside it. This is a bloom's whole relationship with the
// scene it is in, and it was the second half of why the flowers read as pasted
// on rather than growing there.
let _FLORET_MAT = null;
function floretMaterial() {
  if (_FLORET_MAT) return _FLORET_MAT;
  _FLORET_MAT = new THREE.MeshStandardMaterial({
    roughness: 0.62, metalness: 0.0, side: THREE.DoubleSide,
    // Petals are thin and translucent — a real one glows when the sun is behind
    // it. A small emissive lift stands in for the transmission that would cost a
    // second render pass, and it is what keeps a shaded bloom from going grey.
    emissive: 0x000000, emissiveIntensity: 1.0,
  });
  _FLORET_MAT.onBeforeCompile = (shader) => {
    // Emissive from the INSTANCE colour, so each species' bloom lifts in its own
    // hue rather than every flower in the scene lifting in one.
    shader.fragmentShader = shader.fragmentShader.replace(
      '#include <emissivemap_fragment>',
      ['#include <emissivemap_fragment>',
       '#ifdef USE_INSTANCING_COLOR',
       '  totalEmissiveRadiance += vInstanceColor * ' +
       (sceneNight ? '0.45' : '0.22') + ';',
       '#endif'].join('\n'));
  };
  _FLORET_MAT.customProgramCacheKey = () => 'floret' + (sceneNight ? 'n' : 'd');
  return _FLORET_MAT;
}

function _addFloretMesh(geo, xf, col, names, ids) {
  const count = xf.length / 6;
  if (!count) return;
  const mesh = instancedMesh(geo, count, floretMaterial(), false);
  const q = new THREE.Quaternion(), e = new THREE.Euler();
  const v = new THREE.Vector3(), s = new THREE.Vector3(), m = new THREE.Matrix4();
  const c = new THREE.Color();
  for (let i = 0; i < count; i++) {
    const o = i * 6, sc = xf[o + 5];
    v.set(xf[o], xf[o + 1], xf[o + 2]);
    s.set(sc, sc, sc);
    // The floret is built face-up (+Y), so `tilt` nods it away from vertical
    // and `spin` turns it about the stem — the same YXZ order the billboard
    // quads use, minus the -PI/2 that stood a face-on drawing up.
    e.set(xf[o + 3], xf[o + 4], 0, 'YXZ');
    q.setFromEuler(e);
    m.compose(v, q, s);
    mesh.setMatrixAt(i, m);
    mesh.setColorAt(i, c.setRGB(col[i * 3], col[i * 3 + 1], col[i * 3 + 2]));
  }
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  mesh.userData.pick = names;
  mesh.userData.pickId = ids;
  plantsGroup.add(mesh);
}

window.buildFlorets = buildFlorets;
window.floretsApply = floretsApply;
