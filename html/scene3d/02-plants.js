// Part of the Site & Pattern 3D viewer, split out of the former
// single html/scene3d.html <script> (V2.24). Loaded as an ordered
// CLASSIC script by the bootstrap in scene3d.html — it shares the
// global scope with its siblings (THREE/OrbitControls/mergeGeometries
// are globals set by the bootstrap), so load ORDER is dependency
// order. Do not add ES `import`/`export` here.

// ── terrain / ground ────────────────────────────────────────────────────────

// Procedural meadow texture (V2.12): a tileable two-tone green mottle with
// dry-grass accents and fine dark speckle, so the ground reads as meadow
// rather than a flat colour swatch. Built once; each blob is stamped at the
// eight wrap offsets too, so the tile repeats seamlessly.
function makeMeadowTexture() {
  const s = 256, cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const g = cv.getContext('2d');
  g.fillStyle = '#87a56c'; g.fillRect(0, 0, s, s);
  const rng = mulberry32(20250621);
  const blob = (x, y, r, rgb, a) => {
    for (const ox of [-s, 0, s]) for (const oy of [-s, 0, s]) {
      const grd = g.createRadialGradient(x + ox, y + oy, 0, x + ox, y + oy, r);
      grd.addColorStop(0, 'rgba(' + rgb + ',' + a.toFixed(3) + ')');
      grd.addColorStop(1, 'rgba(' + rgb + ',0)');
      g.fillStyle = grd;
      g.beginPath(); g.arc(x + ox, y + oy, r, 0, Math.PI * 2); g.fill();
    }
  };
  for (let i = 0; i < 46; i++)              // broad warm/cool meadow mottling
    blob(rng() * s, rng() * s, 18 + rng() * 34,
         rng() < 0.5 ? '142,160,88' : '112,142,86', 0.16 + rng() * 0.18);
  for (let i = 0; i < 26; i++)              // dry-grass / clover accents
    blob(rng() * s, rng() * s, 5 + rng() * 10,
         rng() < 0.6 ? '158,164,92' : '96,124,78', 0.12 + rng() * 0.14);
  g.fillStyle = 'rgba(70,96,60,0.5)';       // fine soil/shadow speckle
  for (let i = 0; i < 420; i++) {
    g.beginPath();
    g.arc(rng() * s, rng() * s, 0.5 + rng() * 0.9, 0, Math.PI * 2);
    g.fill();
  }
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  if (THREE.SRGBColorSpace) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy() || 1);
  return t;
}

// Winter ground cover — the prairie yard is under snow for much of the year, so
// the ground should not read summer-green in January. A bright, faintly blue-
// hollowed drift texture built the same way as the meadow.
function makeSnowTexture() {
  const s = 256, cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const g = cv.getContext('2d');
  g.fillStyle = '#eef3f8'; g.fillRect(0, 0, s, s);
  const rng = mulberry32(20250131);
  const blob = (x, y, r, rgb, a) => {
    for (const ox of [-s, 0, s]) for (const oy of [-s, 0, s]) {
      const grd = g.createRadialGradient(x + ox, y + oy, 0, x + ox, y + oy, r);
      grd.addColorStop(0, 'rgba(' + rgb + ',' + a.toFixed(3) + ')');
      grd.addColorStop(1, 'rgba(' + rgb + ',0)');
      g.fillStyle = grd;
      g.beginPath(); g.arc(x + ox, y + oy, r, 0, Math.PI * 2); g.fill();
    }
  };
  for (let i = 0; i < 30; i++)              // soft blue hollows between drifts
    blob(rng() * s, rng() * s, 20 + rng() * 40, '188,204,224', 0.10 + rng() * 0.12);
  for (let i = 0; i < 24; i++)              // brighter wind-packed drifts
    blob(rng() * s, rng() * s, 10 + rng() * 22, '255,255,255', 0.12 + rng() * 0.18);
  g.fillStyle = 'rgba(210,222,238,0.6)';    // fine grain / sparkle
  for (let i = 0; i < 300; i++) {
    g.beginPath();
    g.arc(rng() * s, rng() * s, 0.5 + rng() * 0.8, 0, Math.PI * 2);
    g.fill();
  }
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  if (THREE.SRGBColorSpace) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy() || 1);
  return t;
}

// One shared ground material across every scene rebuild (its texture is never
// disposed — disposeDesignGroup skips it via the shared-material set). Plane
// UVs are scaled so one texture tile always covers ~_GROUND_TILE_M metres.
let GROUND_MAT = null;
const _GROUND_TILE_M = 7;
function ensureGroundMat() {
  if (!GROUND_MAT)
    GROUND_MAT = new THREE.MeshStandardMaterial({
      map: makeMeadowTexture(), roughness: 1 });
  return GROUND_MAT;
}
function scaleGroundUv(geo, w, d) {
  const uv = geo.attributes.uv;
  for (let i = 0; i < uv.count; i++)
    uv.setXY(i, uv.getX(i) * (w / _GROUND_TILE_M),
                uv.getY(i) * (d / _GROUND_TILE_M));
}

// A second cached material for snow, plus a seasonal picker: deep winter
// (Nov–Mar) lays snow on the ground; the Oct / Apr shoulders tint the meadow
// toward straw / a waking green rather than swapping it. Driven by the scene
// month — the same signal the plants' seasonalColor uses — so ground, foliage
// and bare branches turn together.
let GROUND_SNOW_MAT = null;
function ensureGroundSnowMat() {
  if (!GROUND_SNOW_MAT)
    GROUND_SNOW_MAT = new THREE.MeshStandardMaterial({
      map: makeSnowTexture(), roughness: 0.82 });
  return GROUND_SNOW_MAT;
}
function groundMatFor(month) {
  const m = month || 0;
  if (m >= 11 || m <= 3) return ensureGroundSnowMat();   // snow on the ground
  const mat = ensureGroundMat();
  // .color multiplies the texture: white = untouched growing-season green.
  if (m === 10) mat.color.setHex(0xbfa878);              // October straw
  else if (m === 4) mat.color.setHex(0xc7cba2);          // April, still waking
  else mat.color.setHex(0xffffff);
  return mat;
}

function buildGround(group, sc) {
  const b = sc.bounds, t = sc.terrain;
  const mat = groundMatFor(sc.month);
  if (t && t.rows > 1 && t.cols > 1) {
    const w = t.max_x - t.min_x, d = t.max_y - t.min_y;
    const geo = new THREE.PlaneGeometry(w, d, t.cols - 1, t.rows - 1);
    // PlaneGeometry grid: row 0 = +y edge (north after rotation) — matches
    // the contract's "heights row 0 = north".
    const pos = geo.attributes.position;
    for (let r = 0; r < t.rows; r++)
      for (let c = 0; c < t.cols; c++)
        pos.setZ(r * t.cols + c, t.heights[r][c]);
    geo.computeVertexNormals();
    scaleGroundUv(geo, w, d);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.set(t.min_x + w / 2, 0, -(t.min_y + d / 2));
    mesh.receiveShadow = true;
    group.add(mesh);
  }
  // A wide flat apron under/around everything (also the only ground when
  // no terrain came with the scene).
  const aw = (b.max_x - b.min_x) * 3, ad = (b.max_y - b.min_y) * 3;
  const ageo = new THREE.PlaneGeometry(aw, ad);
  scaleGroundUv(ageo, aw, ad);
  const apron = new THREE.Mesh(ageo, mat);
  apron.rotation.x = -Math.PI / 2;
  apron.position.set((b.min_x + b.max_x) / 2, -0.02, -(b.min_y + b.max_y) / 2);
  apron.receiveShadow = true;
  group.add(apron);
}

function buildBoundary(group, ring) {
  if (!ring || ring.length < 3) return;
  const pts = ring.concat([ring[0]]).map(p => new THREE.Vector3(p[0], 0.12, -p[1]));
  const line = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color: 0xf9a825 }));
  group.add(line);
}

// ── buildings / footprints ─────────────────────────────────────────────────

// Static footprints (spec idea 2): extrude each ring, then merge all same-kind
// geometries into one mesh so N buildings cost ≤2 draw calls. The −90° rotation
// is baked into each geometry (so merged parts share orientation) rather than
// set on the mesh: shape (x,y) → (x, −z), extrude depth → +y.
function buildBuildings(group, buildings) {
  const byKind = { building: [], canopy: [] };
  for (const bld of buildings || []) {
    const ring = bld.ring || [];
    if (ring.length < 3) continue;
    const shape = new THREE.Shape(ring.map(p => new THREE.Vector2(p[0], p[1])));
    const geo = new THREE.ExtrudeGeometry(shape, {
      depth: Math.max(0.3, bld.height_m || 3), bevelEnabled: false });
    geo.rotateX(-Math.PI / 2);
    byKind[bld.kind === 'canopy' ? 'canopy' : 'building'].push(geo);
  }
  const mats = {
    building: new THREE.MeshStandardMaterial({ color: 0xb0a18c, roughness: 0.9 }),
    canopy: new THREE.MeshStandardMaterial({ color: 0x4e6e52, roughness: 1,
                                             transparent: true, opacity: 0.85 }),
  };
  for (const kind of ['building', 'canopy']) {
    const geos = byKind[kind];
    if (!geos.length) continue;
    const merged = geos.length === 1 ? geos[0] : mergeGeometries(geos, false);
    const mesh = new THREE.Mesh(merged, mats[kind]);
    mesh.castShadow = mesh.receiveShadow = true;
    group.add(mesh);
  }
}

// ── plants (procedural instanced archetypes) ───────────────────────────────

const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(),
      _s = new THREE.Vector3(), _v = new THREE.Vector3();
const _yAxis = new THREE.Vector3(0, 1, 0);
const _white = new THREE.Color(0xffffff);

function instancedMesh(geo, count, mat, shadow = true) {
  const mesh = new THREE.InstancedMesh(geo, mat, count);
  mesh.castShadow = mesh.receiveShadow = shadow;
  return mesh;
}

// Sample terrain height (world Y) at a plant's scene position (sceneX, sceneY).
// Uses bilinear interpolation over the terrain grid; returns 0 when no terrain.
// terrain.heights[r][c]: r=0 is north edge (max sceneY), r=rows-1 is south (min sceneY).
function terrainHeightAt(sceneX, sceneY, terrain) {
  if (!terrain || terrain.rows < 2 || terrain.cols < 2) return 0;
  const t = terrain;
  const col = (sceneX - t.min_x) / (t.max_x - t.min_x) * (t.cols - 1);
  const row = (t.max_y - sceneY) / (t.max_y - t.min_y) * (t.rows - 1);
  const c0 = Math.max(0, Math.min(t.cols - 2, Math.floor(col)));
  const r0 = Math.max(0, Math.min(t.rows - 2, Math.floor(row)));
  const fc = col - c0, fr = row - r0;
  const h00 = t.heights[r0][c0],     h01 = t.heights[r0][c0 + 1];
  const h10 = t.heights[r0 + 1][c0], h11 = t.heights[r0 + 1][c0 + 1];
  return (h00 * (1 - fc) + h01 * fc) * (1 - fr) + (h10 * (1 - fc) + h11 * fc) * fr;
}

// Compose a per-instance matrix with a Y rotation and set a pre-computed colour.
function setInst2(mesh, i, x, h0, z, sx, sy, sz, rotY, color) {
  _v.set(x, h0, z); _s.set(sx, sy, sz);
  _q.setFromAxisAngle(_yAxis, rotY);
  _m.compose(_v, _q, _s);
  mesh.setMatrixAt(i, _m);
  if (color) mesh.setColorAt(i, color);
}

function fadeColor(col, opacity) {
  const o = Math.max(0, Math.min(1, opacity ?? 1));
  return col.clone().lerp(_skyCol, 1 - o);
}

// MeshStandardMaterial with an optional GPU wind sway injected into the
// vertex stage (the first custom shader work in the app). Lighting, shadows
// and instancing all stay intact — we only nudge `transformed` in local space
// (so the per-instance matrix scales the sway by canopy size) before three
// applies the instance/model matrices in <project_vertex>.
function plantMaterial(opts = {}) {
  const mat = new THREE.MeshStandardMaterial({
    roughness: opts.roughness ?? 0.9,
    vertexColors: !!opts.vertexColors,
    side: opts.doubleSide ? THREE.DoubleSide : THREE.FrontSide,
    flatShading: !!opts.flatShading,
  });
  const strength = opts.wind || 0;
  if (strength > 0) {
    mat.onBeforeCompile = (shader) => {
      shader.uniforms.uTime = windUniforms.uTime;
      shader.vertexShader = 'uniform float uTime;\n' + shader.vertexShader;
      shader.vertexShader = shader.vertexShader.replace(
        '#include <begin_vertex>',
        [
          '#include <begin_vertex>',
          '{',
          '  #ifdef USE_INSTANCING',
          '  vec3 iPos = vec3(instanceMatrix[3][0], instanceMatrix[3][1], instanceMatrix[3][2]);',
          '  #else',
          '  vec3 iPos = vec3(0.0);',
          '  #endif',
          '  float hf = clamp(transformed.y, 0.0, 1.2);',           // taller verts sway more
          '  float ph = iPos.x * 0.35 + iPos.z * 0.35;',            // per-plant phase
          '  float wv = sin(uTime * 1.3 + ph + position.x * 1.1 + position.z * 0.8) * 0.6',
          '           + sin(uTime * 2.6 + ph * 1.7) * 0.4;',
          '  float amp = ' + strength.toFixed(4) + ' * hf * hf;',
          '  transformed.x += wv * amp;',
          '  transformed.z += wv * 0.7 * amp;',
          '}',
        ].join('\n'));
    };
    mat.customProgramCacheKey = () =>
      'windplant' + strength.toFixed(4) + (opts.vertexColors ? 'c' : '');
  }
  return mat;
}

// A soft radial "contact shadow" stamp — a dark blob under big plants that
// grounds them without leaning on the directional shadow map's resolution.
function makeShadowTexture() {
  const s = 128, cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const ctx = cv.getContext('2d');
  const g = ctx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  g.addColorStop(0, 'rgba(0,0,0,0.55)');
  g.addColorStop(0.55, 'rgba(0,0,0,0.28)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, s, s);
  return new THREE.CanvasTexture(cv);
}

// ── Da Vinci procedural trees ───────────────────────────────────────────────
// Part 1 of the spec: a parent branch of radius R splitting into children
// r_i obeys R^x = Σ r_i^x (area conservation; x is species-ish), and child
// length scales as (r_child / R)^lengthScaling. We build an abstract skeleton
// first, then turn it into one merged BufferGeometry — so a whole forest is a
// handful of InstancedMesh draw calls.

const DECID_CFG = {
  // Lower cutoff than the trunk start ⇒ branches recurse to finer twigs, so
  // even narrow-crowned forms carry enough tips for a full canopy.
  davinciExponent: 2.0, lengthScaling: 0.7, branchAngleBase: 0.62,
  maxDepth: 4, minRadiusCutoff: 0.018, conifer: false,
};

// Crown form is chosen from the plant's real height/canopy aspect ratio rather
// than an arbitrary id hash, so a tall-narrow species (aspen/poplar/birch)
// renders slender and a broad one (oak/maple) renders spreading — the trees
// look the way their own dimensions say they should.
//   slender  : narrow upright crown, short side limbs, high clear bole
//   oval     : balanced upright
//   spreading: broad rounded crown (the look the user already liked on oak)
// `clearBole` is the fraction of crown height kept leaf-free at the bottom
// (a real tree's clean trunk); `foliageScale` shrinks slender trees' leaf
// clusters so a fine-leaved aspen crown doesn't read as heavy blobs.
const DECID_FORMS = {
  slender:   { branchAngleBase: 0.46, lengthScaling: 0.84, davinciExponent: 2.0,
               clearBole: 0.52, foliageScale: 0.72 },
  oval:      { branchAngleBase: 0.62, lengthScaling: 0.70, davinciExponent: 2.0,
               clearBole: 0.38, foliageScale: 0.9 },
  spreading: { branchAngleBase: 0.85, lengthScaling: 0.64, davinciExponent: 1.85,
               clearBole: 0.28, foliageScale: 1.0 },
};
// Conifer skirt profiles (Phase 1): conifers are clean stacked cones, not
// branch skeletons. `tiersAdd` shifts the tier count off the maturity base,
// `baseR` the bottom-tier radius, `droop` how far each shelf sweeps down.
const CONIFER_FORMS = {
  slender:   { baseR: 0.38, tiersAdd: 2, droop: 0.10 },   // spire (spruce)
  oval:      { baseR: 0.46, tiersAdd: 1, droop: 0.14 },   // standard
  spreading: { baseR: 0.55, tiersAdd: -1, droop: 0.20 },  // broad / open fir
};
// Maturity-tier branch depth [sapling, young, mature] — a young tree renders
// with fewer structural forks (spec idea 4: maturity drives recursive depth).
const DECID_DEPTH = [2, 3, 4];
const CONIFER_TIERS = [3, 5, 8];   // skirt count by maturity tier

const _FORM_SEED = { slender: 0, oval: 17, spreading: 31 };

// ── Species (genus) profiles (V1.94) ────────────────────────────────────────
// The most impactful keystone/host trees get genus-specific geometry so a
// spruce, pine and fir read apart and aspen/birch show pale bark. A profile is a
// tiny param bag; unknown genera fall to `def` (today's generic look). `conifer`
// selects a needle-crown kind (overriding the decid/conifer split for larch,
// which keeps deciduous needle-drop); `formBias` forces the crown form so a
// species reads right even when its dimensions are ambiguous; `bark` colours the
// trunk; `droopOuter`/`foliageScale` shape the broadleaf crown.
const _PROF = {
  spruce: { id: 'spruce', conifer: 'spruce', bark: '#4b3a2a' },   // Picea
  fir:    { id: 'fir',    conifer: 'fir',    bark: '#3f3022' },   // Abies / Pseudotsuga
  pine:   { id: 'pine',   conifer: 'pine',   bark: '#6b4a2e' },   // Pinus
  larch:  { id: 'larch',  conifer: 'larch',  bark: '#5a4632' },   // Larix (deciduous needles)
  aspen:  { id: 'aspen',  bark: '#cfcab4', formBias: 'slender', foliageScale: 0.9 },  // Populus
  birch:  { id: 'birch',  bark: '#e8e6df', formBias: 'oval', droopOuter: 0.55, foliageScale: 0.82 }, // Betula
  oak:    { id: 'oak',    bark: '#463524', formBias: 'spreading', foliageScale: 1.06 }, // Quercus
  willow: { id: 'willow', bark: '#8a8a6a', formBias: 'slender', droopOuter: 0.7, foliageScale: 0.85 }, // Salix
  cherry: { id: 'cherry', bark: '#5a4636', formBias: 'oval' },    // Prunus
  apple:  { id: 'apple',  bark: '#6a5238', formBias: 'spreading' }, // Malus
  def:    { id: 'def',    bark: '#5d4433' },
};
const TREE_PROFILES = {
  picea: _PROF.spruce, abies: _PROF.fir, pseudotsuga: _PROF.fir, pinus: _PROF.pine,
  larix: _PROF.larch, populus: _PROF.aspen, betula: _PROF.birch, quercus: _PROF.oak,
  salix: _PROF.willow, prunus: _PROF.cherry, malus: _PROF.apple,
};
function profileFor(p) {
  return TREE_PROFILES[(p.genus || '').toLowerCase()] || _PROF.def;
}
// Needle-crown kinds layered on top of the form's CONIFER_FORMS params: spruce =
// narrow dense bluish spire; fir = narrower, very dense, sharp tall summit; larch
// = sparse soft cone. (Pine has its own open builder, buildPineGeo.)
const CONIFER_KINDS = {
  standard: { baseRMul: 1.0,  tiersAdd: 0,  droopAdd: 0.0,  spire: 1.0, segMul: 1.0 },
  spruce:   { baseRMul: 0.82, tiersAdd: 1,  droopAdd: 0.03, spire: 1.15, segMul: 1.0 },
  fir:      { baseRMul: 0.72, tiersAdd: 2,  droopAdd: -0.04, spire: 1.4, segMul: 1.0 },
  larch:    { baseRMul: 0.92, tiersAdd: -1, droopAdd: 0.0,  spire: 0.7, segMul: 0.7 },
};
const _CK_SEED = { standard: 0, spruce: 3, fir: 7, pine: 11, larch: 17 };

// Shrub growth-form silhouettes (V1.96): instead of one blobby dome, a shrub is
// a multi-stem woody clump whose foliage is distributed along ascending stems —
// and the *shape* of that clump differs by species. Each form sets stem count /
// splay / length, how many foliage masses each stem carries and where they start
// (a clear-stemmed "vase" vs foliage to the ground), the mass radius + ellipsoid
// shape (flattened spreading vs upright vs round), and whether a basal mound
// fills the bottom. `q(n)` quality-scales the counts.
//   vase      — upright, clean-based, fountain crown (saskatoon, willow, alder, hazel)
//   spreading — broad, wide flattened masses (dogwood, viburnum)
//   mound     — low dense rounded thicket to the ground (rose, spirea, snowberry)
//   thicket   — many fine canes, airy (currant, raspberry)
//   irregular — sparse asymmetric woody (sage, buffaloberry)
const SHRUB_FORMS = {
  vase:      { stems: [4, 6], splay: 0.26, stemH: [0.78, 1.0], masses: [2, 3],
               start: 0.45, massR: [0.16, 0.24], shape: [0.92, 1.05, 0.92], basal: false },
  spreading: { stems: [4, 6], splay: 0.62, stemH: [0.6, 0.85], masses: [2, 3],
               start: 0.38, massR: [0.18, 0.27], shape: [1.25, 0.7, 1.25], basal: true },
  mound:     { stems: [5, 8], splay: 0.52, stemH: [0.42, 0.66], masses: [2, 3],
               start: 0.18, massR: [0.16, 0.22], shape: [1.06, 0.86, 1.06], basal: true },
  thicket:   { stems: [7, 11], splay: 0.42, stemH: [0.55, 0.92], masses: [1, 2],
               start: 0.34, massR: [0.11, 0.17], shape: [0.9, 1.0, 0.9], basal: true },
  irregular: { stems: [3, 6], splay: 0.5, stemH: [0.5, 0.98], masses: [1, 3],
               start: 0.3, massR: [0.12, 0.2], shape: [1.0, 0.9, 1.0], basal: false },
};

// Genus → shrub profile. `form` picks a silhouette; `redStems` paints the woody
// stems red (red-osier dogwood); `fine` slims the masses. Foliage colour comes
// from the genus (scene_contract _foliage_color) — sages/buffaloberry already go
// silver there. Unknown genera fall back to a generic spreading bush.
const _SPROF = {
  cornus:         { id: 'cornus', form: 'spreading', redStems: true },  // red-osier dogwood
  salix:          { id: 'salix', form: 'vase' },                        // shrub willow
  amelanchier:    { id: 'amel', form: 'vase', fine: true },             // saskatoon
  prunus:         { id: 'choke', form: 'vase' },                        // chokecherry / pin cherry shrub
  corylus:        { id: 'hazel', form: 'vase' },                        // beaked hazelnut
  alnus:          { id: 'alder', form: 'vase' },                        // alder
  crataegus:      { id: 'haw', form: 'vase' },                          // hawthorn
  viburnum:       { id: 'vibur', form: 'spreading' },                   // highbush cranberry
  rosa:           { id: 'rosa', form: 'mound', fine: true },            // wild rose
  spiraea:        { id: 'spir', form: 'mound', fine: true },            // meadowsweet
  symphoricarpos: { id: 'snow', form: 'mound' },                        // snowberry
  vaccinium:      { id: 'vacc', form: 'mound', fine: true },            // blueberry / cranberry
  ribes:          { id: 'ribes', form: 'thicket', fine: true },         // currant / gooseberry
  rubus:          { id: 'rubus', form: 'thicket' },                     // raspberry / bramble
  artemisia:      { id: 'sage', form: 'irregular', fine: true },        // sagebrush (silver)
  shepherdia:     { id: 'shep', form: 'irregular' },                    // buffaloberry (silver)
  def:            { id: 'sdef', form: 'spreading' },
};
function shrubProfileFor(p) {
  return _SPROF[(p.genus || '').toLowerCase()] || _SPROF.def;
}

