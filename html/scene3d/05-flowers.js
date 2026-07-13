// Part of the Site & Pattern 3D viewer, split out of the former
// single html/scene3d.html <script> (V2.24). Loaded as an ordered
// CLASSIC script by the bootstrap in scene3d.html — it shares the
// global scope with its siblings (THREE/OrbitControls/mergeGeometries
// are globals set by the bootstrap), so load ORDER is dependency
// order. Do not add ES `import`/`export` here.

// ── Flowers (V1.90) ──────────────────────────────────────────────────────────
// Camera-facing point sprites in each plant's real flower colour, shaped by a
// per-form canvas texture so different flowers read differently. Shown only when
// the scene's month falls inside the plant's bloom window.
const FLOWER_FORMS = ['daisy', 'rays', 'spike', 'plume', 'umbel', 'globe',
                      'cluster', 'bell', 'trumpet', 'cattail', 'pea', 'whorl',
                      'star', 'cross', 'lily'];
let FLOWER_TEX = null;

function makeFlowerTexture(form) {
  const s = 64, cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const g = cv.getContext('2d');
  g.clearRect(0, 0, s, s);
  g.fillStyle = '#ffffff';
  const cx = s / 2, cy = s / 2;
  const dot = (x, y, r) => { g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill(); };
  if (form === 'daisy') {
    const petals = 10, R = s * 0.30;          // aster ray florets
    for (let i = 0; i < petals; i++) {
      const a = i / petals * Math.PI * 2;
      g.save(); g.translate(cx + Math.cos(a) * R * 0.6, cy + Math.sin(a) * R * 0.6);
      g.rotate(a); g.beginPath();
      g.ellipse(0, 0, s * 0.20, s * 0.075, 0, 0, Math.PI * 2); g.fill(); g.restore();
    }
    g.fillStyle = 'rgba(255,255,255,0.7)'; dot(cx, cy, s * 0.12);   // dim eye
  } else if (form === 'umbel') {
    for (let i = 0; i < 16; i++) {
      const a = i * 2.39996, rr = Math.sqrt(i / 16) * s * 0.40;
      dot(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr * 0.55, s * 0.055);
    }
  } else if (form === 'spike') {
    for (let i = 0; i < 7; i++) {
      const yy = s * 0.12 + i * s * 0.115;
      const w = s * (0.16 - 0.012 * i);
      g.beginPath(); g.ellipse(cx, yy, w, s * 0.075, 0, 0, Math.PI * 2); g.fill();
    }
  } else if (form === 'bell') {
    g.beginPath();
    g.moveTo(cx - s * 0.20, cy - s * 0.18);
    g.bezierCurveTo(cx - s * 0.24, cy + s * 0.30, cx + s * 0.24, cy + s * 0.30,
                    cx + s * 0.20, cy - s * 0.18);
    g.closePath(); g.fill();
    for (let i = 0; i < 3; i++) dot(cx - s * 0.12 + i * s * 0.12, cy + s * 0.24, s * 0.05);
  } else if (form === 'rays') {            // big sunflower-style composite
    const petals = 16, R = s * 0.40;
    for (let i = 0; i < petals; i++) {
      const a = i / petals * Math.PI * 2;
      g.save(); g.translate(cx + Math.cos(a) * R * 0.5, cy + Math.sin(a) * R * 0.5);
      g.rotate(a); g.beginPath();
      g.ellipse(0, 0, s * 0.24, s * 0.07, 0, 0, Math.PI * 2); g.fill(); g.restore();
    }
    g.fillStyle = 'rgba(255,255,255,0.6)'; dot(cx, cy, s * 0.19);   // dark disc hint
  } else if (form === 'plume') {           // feathery tapering spray (goldenrod, grass)
    for (let i = 0; i < 26; i++) {
      const t = i / 26, yy = s * 0.08 + t * s * 0.84;
      const spread = s * 0.22 * (1 - t) + s * 0.03;
      dot(cx + Math.sin(i * 1.7) * spread, yy, s * 0.045 * (1 - 0.4 * t));
    }
  } else if (form === 'globe') {           // dense spherical head (allium)
    for (let i = 0; i < 22; i++) {
      const a = i * 2.39996, rr = Math.sqrt(i / 22) * s * 0.36;
      dot(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, s * 0.055);
    }
  } else if (form === 'trumpet') {         // 5-point tubular star (columbine, honeysuckle)
    const pts = 5, Ro = s * 0.40, Ri = s * 0.16;
    g.beginPath();
    for (let i = 0; i < pts * 2; i++) {
      const a = -Math.PI / 2 + i * Math.PI / pts, r = (i % 2 ? Ri : Ro);
      const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
      i ? g.lineTo(x, y) : g.moveTo(x, y);
    }
    g.closePath(); g.fill();
    g.fillStyle = 'rgba(255,255,255,0.7)'; dot(cx, cy, s * 0.10);
  } else if (form === 'cattail') {         // brown emergent spike (Typha)
    // slim upper male spike tapering to a point
    g.beginPath();
    g.moveTo(cx - s * 0.035, s * 0.30);
    g.lineTo(cx + s * 0.035, s * 0.30);
    g.lineTo(cx + s * 0.016, s * 0.07);
    g.lineTo(cx - s * 0.016, s * 0.07);
    g.closePath(); g.fill();
    // fat female sausage with rounded ends
    const x0 = cx - s * 0.085;
    g.fillRect(x0, s * 0.34, s * 0.17, s * 0.50);
    dot(cx, s * 0.34, s * 0.085);
    dot(cx, s * 0.84, s * 0.085);
    // thin supporting stalk below
    g.fillRect(cx - s * 0.012, s * 0.84, s * 0.024, s * 0.15);
  } else if (form === 'pea') {             // legume raceme (lupine, vetch, milkvetch)
    const rows = 6;
    for (let i = 0; i < rows; i++) {
      const t = i / (rows - 1);
      const yy = s * 0.15 + t * s * 0.70;
      const w = s * (0.17 - 0.05 * t);     // wider toward the base
      g.beginPath(); g.ellipse(cx, yy - s * 0.03, w, s * 0.065, 0, 0, Math.PI * 2); g.fill();
      dot(cx - w * 0.5, yy + s * 0.03, s * 0.042);   // wings / keel
      dot(cx + w * 0.5, yy + s * 0.03, s * 0.042);
    }
  } else if (form === 'whorl') {           // tubular whorl (bee balm / Monarda)
    const florets = 14;
    for (let i = 0; i < florets; i++) {
      const a = i / florets * Math.PI * 2 + 0.2;
      const rr = s * 0.30 * (0.72 + 0.28 * (((i * 7) % 5) / 5));
      g.save(); g.translate(cx, cy); g.rotate(a); g.beginPath();
      g.ellipse(rr * 0.5, 0, s * 0.17, s * 0.032, 0, 0, Math.PI * 2); g.fill(); g.restore();
    }
    g.fillStyle = 'rgba(255,255,255,0.85)'; dot(cx, cy, s * 0.09);
  } else if (form === 'star') {            // 5 broad rounded petals (flax, geranium, phlox)
    const petals = 5, R = s * 0.34;
    for (let i = 0; i < petals; i++) {
      const a = -Math.PI / 2 + i / petals * Math.PI * 2;
      g.save(); g.translate(cx + Math.cos(a) * R * 0.52, cy + Math.sin(a) * R * 0.52);
      g.rotate(a + Math.PI / 2); g.beginPath();
      g.ellipse(0, 0, s * 0.135, s * 0.2, 0, 0, Math.PI * 2); g.fill(); g.restore();
    }
    g.fillStyle = 'rgba(255,255,255,0.6)'; dot(cx, cy, s * 0.085);
  } else if (form === 'cross') {           // 4 petals (mustard family — draba)
    const petals = 4, R = s * 0.3;
    for (let i = 0; i < petals; i++) {
      const a = i / petals * Math.PI * 2;
      g.save(); g.translate(cx + Math.cos(a) * R * 0.55, cy + Math.sin(a) * R * 0.55);
      g.rotate(a); g.beginPath();
      g.ellipse(0, 0, s * 0.17, s * 0.115, 0, 0, Math.PI * 2); g.fill(); g.restore();
    }
    dot(cx, cy, s * 0.06);
  } else if (form === 'lily') {            // 6 pointed tepals (lily, blue-eyed grass, camas)
    const tepals = 6, R = s * 0.44;
    for (let i = 0; i < tepals; i++) {
      const a = -Math.PI / 2 + i / tepals * Math.PI * 2;
      g.save(); g.translate(cx, cy); g.rotate(a);
      g.beginPath();
      g.moveTo(0, 0); g.lineTo(s * 0.07, -s * 0.13);
      g.lineTo(0, -R); g.lineTo(-s * 0.07, -s * 0.13);
      g.closePath(); g.fill(); g.restore();
    }
    g.fillStyle = 'rgba(255,255,255,0.55)'; dot(cx, cy, s * 0.08);
  } else { // cluster
    for (let i = 0; i < 11; i++) {
      const a = i * 2.39996, rr = Math.sqrt(i / 11) * s * 0.34;
      dot(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, s * 0.10);
    }
  }
  const t = new THREE.CanvasTexture(cv);
  if (THREE.SRGBColorSpace) t.colorSpace = THREE.SRGBColorSpace;
  t.needsUpdate = true;
  return t;
}

// Clamp a point sprite's on-screen size (V2.12). sizeAttenuation has no cap,
// so a bloom right at the bee camera's nose would otherwise fill the screen as
// a giant washed-out disc. String-replace on the stock points chunk — if the
// chunk ever changes in a three bump, the material just runs unclamped.
function clampPointSize(mat, px) {
  mat.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader.replace(
      'gl_PointSize *= ( scale / - mvPosition.z );',
      'gl_PointSize *= ( scale / - mvPosition.z ); '
      + 'gl_PointSize = min( gl_PointSize, ' + px.toFixed(1) + ' );');
  };
  mat.customProgramCacheKey = () => 'pclamp' + px;
  return mat;
}

// Like clampPointSize, but each point also carries a per-sprite size multiplier
// (a required `aSize` attribute). Varying bloom sizes is the other half of the
// de-blob fix (V2.13): a plant reads as several distinct flowers of different
// sizes rather than one uniform coloured disc.
function flowerPointSize(mat, px) {
  mat.onBeforeCompile = (shader) => {
    shader.vertexShader = 'attribute float aSize;\n' + shader.vertexShader.replace(
      'gl_PointSize *= ( scale / - mvPosition.z );',
      'gl_PointSize *= ( scale / - mvPosition.z ) * aSize; '
      + 'gl_PointSize = min( gl_PointSize, ' + px.toFixed(1) + ' );');
  };
  mat.customProgramCacheKey = () => 'fsize' + px;
  return mat;
}

// Per-form bloom size + how many sprites to scatter per plant (denser = the
// plant reads as its flower colour when in bloom).
const _FLOWER_SIZE = { rays: 0.42, plume: 0.34, spike: 0.34, umbel: 0.30,
                       globe: 0.32, trumpet: 0.30, bell: 0.24, daisy: 0.24,
                       cluster: 0.26, cattail: 0.7, pea: 0.34, whorl: 0.30,
                       star: 0.28, cross: 0.22, lily: 0.34 };

function buildFlowers(plants, month, terrain) {
  if (!FLOWER_TEX) {
    FLOWER_TEX = {};
    for (const f of FLOWER_FORMS) FLOWER_TEX[f] = makeFlowerTexture(f);
  }
  const byForm = {}; FLOWER_FORMS.forEach(f => byForm[f] = []);
  for (const p of plants || []) {
    if (!p.flower_color || !byForm[p.flower_form]) continue;
    if ((p.opacity ?? 1) < 0.25) continue;            // not-yet-present plants
    const bs = p.bloom_start || 0, be = p.bloom_end || 0;
    if (!bs || month < bs || month > be) continue;     // out of bloom this month
    byForm[p.flower_form].push(p);
  }
  const _fc = new THREE.Color();
  for (const form of FLOWER_FORMS) {
    const list = byForm[form];
    if (!list.length) continue;
    const isCattail = form === 'cattail';
    const pos = [], col = [], siz = [];
    for (const p of list) {
      const gy = terrainHeightAt(p.x, p.y, terrain);
      const h = Math.max(0.1, p.height_m);
      const top = gy + h * (isCattail ? 0.96 : 0.9);
      const rad = Math.max(0.12, p.canopy_m * 0.5);
      _fc.set(p.flower_color);
      const seed = hashPid(p.plant_id || 1);
      // Fewer, better-spread heads than before: they used to pile into one
      // uniform disc. Now sqrt-spaced across the canopy for even areal density,
      // with real vertical spread + per-bloom size variation so a plant reads as
      // several distinct flowers (V2.13 de-blob).
      const n = isCattail ? 1 + (seed % 3)
              : qn(p.plant_type === 'tree' ? 10
                 : p.plant_type === 'shrub' ? 8
                 : p.plant_type === 'grass' ? 5 : 7);
      for (let k = 0; k < n; k++) {
        const j1 = ((seed + k * 97) % 997) / 997;
        const j2 = ((seed + k * 53) % 991) / 991;
        const j3 = ((seed + k * 29) % 983) / 983;
        const a = j1 * Math.PI * 2;
        const rr = isCattail ? rad * 0.22 * j2
                             : rad * (0.12 + 0.9 * Math.sqrt(j2));  // even areal spread
        const dy = isCattail ? 0 : (j3 - 0.5) * Math.max(0.14, h * 0.3);
        pos.push(p.x + Math.cos(a) * rr, top + dy, -(p.y + Math.sin(a) * rr));
        col.push(_fc.r, _fc.g, _fc.b);
        siz.push(isCattail ? 1 : 0.6 + 0.85 * (((seed + k * 17) % 100) / 100));
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    geo.setAttribute('aSize', new THREE.Float32BufferAttribute(siz, 1));
    const mat = flowerPointSize(new THREE.PointsMaterial({
      map: FLOWER_TEX[form], color: 0xffffff, vertexColors: true,
      transparent: true, alphaTest: 0.4, depthWrite: false,
      // At night the blooms softly luminesce (additive) so they read like
      // moonlit / moth-pollinated flowers instead of vanishing into the dark.
      blending: sceneNight ? THREE.AdditiveBlending : THREE.NormalBlending,
      sizeAttenuation: true, size: (_FLOWER_SIZE[form] || 0.24) * (sceneNight ? 1.25 : 1),
    }), 96);
    plantsGroup.add(new THREE.Points(geo, mat));
  }
}

// ── Fruit / berries (V2.0) ───────────────────────────────────────────────────
// Fleshy-fruited plants (curated fruit_color) show clusters of berries through
// their canopy during the fruit season. A radial-gradient sprite gives each
// berry a highlit, shaded-sphere look once tinted by the real fruit colour.
let BERRY_TEX = null;
function makeBerryTexture() {
  const s = 48, cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const g = cv.getContext('2d');
  const grd = g.createRadialGradient(s * 0.38, s * 0.36, s * 0.04,
                                     s * 0.5, s * 0.5, s * 0.5);
  grd.addColorStop(0, '#ffffff');
  grd.addColorStop(0.4, '#d2d2d2');
  grd.addColorStop(1, '#7e7e7e');
  g.fillStyle = grd;
  g.beginPath(); g.arc(s / 2, s / 2, s * 0.46, 0, Math.PI * 2); g.fill();
  const t = new THREE.CanvasTexture(cv);
  if (THREE.SRGBColorSpace) t.colorSpace = THREE.SRGBColorSpace;
  t.needsUpdate = true;
  return t;
}

function buildFruit(plants, month, terrain) {
  const list = [];
  for (const p of plants || []) {
    if (!p.fruit_color) continue;
    if ((p.opacity ?? 1) < 0.25) continue;
    const fs = p.fruit_start || 0, fe = p.fruit_end || 0;
    if (!fs || month < fs || month > fe) continue;     // not in fruit this month
    list.push(p);
  }
  if (!list.length) return;
  if (!BERRY_TEX) BERRY_TEX = makeBerryTexture();
  const _c = new THREE.Color();
  const pos = [], col = [];
  for (const p of list) {
    const gy = terrainHeightAt(p.x, p.y, terrain);
    const h = Math.max(0.1, p.height_m), rad = Math.max(0.1, p.canopy_m * 0.5);
    _c.set(p.fruit_color);
    const seed = hashPid(p.plant_id || 1);
    const n = qn(p.plant_type === 'tree' ? 18 : p.plant_type === 'shrub' ? 15 : 8);
    for (let k = 0; k < n; k++) {
      const a = ((seed + k * 97) % 628) / 100;
      const rr = rad * (0.2 + 0.7 * (((seed + k * 61) % 100) / 100));
      const yy = gy + h * (0.4 + 0.45 * (((seed + k * 37) % 100) / 100));   // through the canopy
      pos.push(p.x + Math.cos(a) * rr, yy, -(p.y + Math.sin(a) * rr));
      col.push(_c.r, _c.g, _c.b);
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  const mat = clampPointSize(new THREE.PointsMaterial({
    map: BERRY_TEX, color: 0xffffff, vertexColors: true,
    transparent: true, alphaTest: 0.5, depthWrite: false,
    sizeAttenuation: true, size: 0.19,
  }), 72);
  plantsGroup.add(new THREE.Points(geo, mat));
}

function buildScanPoints(group, pts) {
  // The imported yard scan as a height-tinted point layer — ground truth
  // behind the proposed design. Sampled host-side (≤ ~120k points).
  if (!pts || !pts.length) return;
  const pos = new Float32Array(pts.length * 3);
  const col = new Float32Array(pts.length * 3);
  const lo = new THREE.Color(0x4e5d52), hi = new THREE.Color(0xe8f0d8);
  const c = new THREE.Color();
  for (let i = 0; i < pts.length; i++) {
    const [x, y, z] = pts[i];
    pos[i * 3] = x; pos[i * 3 + 1] = z; pos[i * 3 + 2] = -y;
    c.copy(lo).lerp(hi, Math.max(0, Math.min(1, z / 6)));
    col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  group.add(new THREE.Points(geo, new THREE.PointsMaterial({
    size: 0.08, vertexColors: true })));
}

function buildStructures(group, structures) {
  for (const s of structures || []) {
    // Blender GLB structure first (09-models.js), box as the fallback.
    const glb = window.glbStructure && window.glbStructure(s);
    if (glb) {
      glb.position.set(s.x, terrainHeightAt(s.x, s.y, lastTerrain), -s.y);
      group.add(glb);
      continue;
    }
    const size = Math.max(0.3, s.size_m || 1), h = Math.max(0.3, s.height_m || 1);
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(size, h, size),
      new THREE.MeshStandardMaterial({ color: 0x8d6e63, roughness: 0.9 }));
    mesh.position.set(s.x, h / 2, -s.y);
    mesh.castShadow = mesh.receiveShadow = true;
    group.add(mesh);
  }
}

// ── Gaussian-splat backdrop (Spark) ─────────────────────────────────────────
// The splat lives OUTSIDE designGroup so a year-slider scene rebuild never
// reloads it (a yard splat is tens of MB). It is keyed by URL: ensureSplat
// only re-fetches when the file changes, otherwise just refreshes its world
// matrix + opacity from the latest scene push.

let splatMesh = null;
let splatUrl = null;

function applySplatMatrix(mesh, mat16) {
  // mat16 is column-major (three.js order) from src/splat_backdrop.world_matrix.
  mesh.matrixAutoUpdate = false;
  mesh.matrix.fromArray(mat16);
}

function ensureSplat(spec) {
  if (!spec || !spec.url) { removeSplat(); return; }
  if (!SplatMesh) return;          // Spark not loaded (yet) — skip silently
  ensureSparkRenderer();
  if (spec.url !== splatUrl) {
    removeSplat();
    try {
      splatMesh = new SplatMesh({ url: spec.url });
    } catch (e) {
      splatMesh = null; splatUrl = null;
      return;   // bad splat — design still renders
    }
    splatUrl = spec.url;
    scene.add(splatMesh);
  }
  if (splatMesh) {
    applySplatMatrix(splatMesh, spec.matrix);
    if (typeof spec.opacity === 'number' && 'opacity' in splatMesh) {
      splatMesh.opacity = spec.opacity;
    }
  }
}

function removeSplat() {
  if (splatMesh) { scene.remove(splatMesh); }
  splatMesh = null; splatUrl = null;
}

window.permaClearSplat = function () { removeSplat(); };

// Bake a north-up orthographic photo of the splat for the 2D "yard photo"
// map layer. Returns a PNG data URL synchronously (the host calls this once
// the splat has streamed in) — opts frames an exact scene-metre rectangle so
// the image maps 1:1 onto the splat's lat/lng bbox. Returns '' if not ready.
window.permaCaptureOrtho = function (opts) {
  if (!splatMesh || !opts) return '';
  const wx = Math.max(1e-3, opts.max_x - opts.min_x);
  const dz = Math.max(1e-3, opts.max_y - opts.min_y);   // north span
  const cx = (opts.min_x + opts.max_x) / 2;
  const cz = -(opts.min_y + opts.max_y) / 2;            // north → −z centre
  const cam = new THREE.OrthographicCamera(-wx / 2, wx / 2, dz / 2, -dz / 2,
                                           0.1, 2000);
  cam.position.set(cx, 800, cz);
  cam.up.set(0, 0, -1);          // north (−z) points up in the image
  cam.lookAt(cx, 0, cz);

  // Splat-only frame: hide the design + sky so the layer is just the yard.
  const designVis = designGroup ? designGroup.visible : false;
  if (designGroup) designGroup.visible = false;
  const bg = scene.background; scene.background = null;
  const skyVis = skyDome.visible; skyDome.visible = false;

  const longest = Math.round(Math.max(1, Math.min(4096, opts.width || 2048)));
  const px = wx >= dz ? longest : Math.round(longest * (wx / dz));
  const py = wx >= dz ? Math.round(longest * (dz / wx)) : longest;
  const prev = new THREE.Vector2(); renderer.getSize(prev);
  renderer.setSize(px, py, false);
  renderer.render(scene, cam);
  let url = '';
  try { url = renderer.domElement.toDataURL('image/png'); } catch (e) { url = ''; }

  // Restore the live view.
  renderer.setSize(prev.x, prev.y, false);
  scene.background = bg;
  skyDome.visible = skyVis;
  if (designGroup) designGroup.visible = designVis;
  renderer.render(scene, camera);
  return url;
};

// ── hooks ───────────────────────────────────────────────────────────────────

// Free the GPU resources a scene rebuild leaves behind. Without this the
// per-rebuild instance buffers and fresh ground/boundary/building geometries
// pile up in VRAM on every slider move until a weak GPU runs out and crashes.
// Shared archetype geometry (TREE_CACHE/ARCH/GEO) and materials (MATS) are
// reused across rebuilds, so they are skipped.
function disposeDesignGroup(group) {
  if (!group) return;
  const sharedGeo = new Set();
  for (const a of TREE_CACHE.values()) {
    if (a.branchGeo) sharedGeo.add(a.branchGeo);
    if (a.foliageGeo) sharedGeo.add(a.foliageGeo);
  }
  // Every shared archetype is reused across rebuilds and must NOT be disposed:
  // all ARCH variant arrays (peren/ground/grass/aquatic — iterate so adding or
  // removing a category never breaks this), and the per-genus shrub cache
  // (V1.94: shrubs moved out of ARCH into SHRUB_CACHE).
  if (ARCH) for (const arr of Object.values(ARCH))
    for (const g of arr) sharedGeo.add(g);
  for (const a of SHRUB_CACHE.values()) {
    if (a.foliageGeo) sharedGeo.add(a.foliageGeo);
    if (a.stemGeo) sharedGeo.add(a.stemGeo);
  }
  for (const g of HERB_CACHE.values()) sharedGeo.add(g);
  for (const k in GEO) sharedGeo.add(GEO[k]);
  // GLB master geometries (09-models.js) survive cache clears — a quality (or
  // models-ready) rebuild clears the caches above, but the masters are re-served.
  if (window.glbSharedGeos) for (const g of window.glbSharedGeos()) sharedGeo.add(g);
  const sharedMat = new Set(MATS ? Object.values(MATS) : []);
  if (GROUND_MAT) sharedMat.add(GROUND_MAT);   // shared meadow texture lives on
  group.traverse(obj => {
    if (obj.isInstancedMesh) obj.dispose();             // frees instance buffers only
    if (obj.geometry && !sharedGeo.has(obj.geometry)) obj.geometry.dispose();
    const m = obj.material;
    if (m) for (const mm of (Array.isArray(m) ? m : [m]))
      if (mm && !sharedMat.has(mm)) mm.dispose();
  });
}

// Reaching here means the whole module body executed without throwing — the
// hooks are about to register and the 8s "couldn't start" timeout will be
// cancelled. If the log shows 'module-eval-start' but not this line, something
// between the two threw (and should have surfaced via the error handler).
window._pinglog && window._pinglog('registering hooks (boot OK)');

let lastSceneObj = null;     // last full scene, so a quality change can re-render
window.permaSetScene = function (sc) {
  if (!sc || !sc.bounds) return;
  lastSceneObj = sc;
  if (designGroup) { disposeDesignGroup(designGroup); scene.remove(designGroup); }
  designGroup = new THREE.Group();
  scene.add(designGroup);
  lastOrigin = sc.origin || null;
  lastMonth = sc.month || 6;
  sceneMonth = sc.month || 6;         // bloom-gating + the seasonal-tour HUD
  sceneNight = !!sc.is_night;         // set before buildPlants so flowers night-glow
  lastYear = sc.year || 0;
  lastBounds = sc.bounds;
  lastTerrain = sc.terrain || null;

  buildGround(designGroup, sc);
  buildBoundary(designGroup, sc.boundary);
  buildBuildings(designGroup, sc.buildings);
  buildPlants(designGroup, sc.plants, sc.month, sc.year, sc.terrain);
  buildStructures(designGroup, sc.structures);
  buildScanPoints(designGroup, sc.scan_points);
  ensureSplat(sc.splat);
  if (sc.is_night) setNight();
  else { setDay(); if (sc.sun) setSun(sc.sun.azimuth_deg, sc.sun.altitude_deg); }
  fitShadow(sc.bounds);

  // Frame the camera only on first load or when a genuinely different design is
  // opened (origin moved) — a slider re-push of the same design keeps the
  // user's current orbit/zoom.
  const o = sc.origin;
  const moved = !framedOrigin ||
    (o && (Math.abs(o.lat - framedOrigin.lat) > 1e-6 ||
           Math.abs(o.lng - framedOrigin.lng) > 1e-6));
  if (moved) {
    // Don't yank the camera while the user is flying, walking, or in the
    // cinematic flyover — those modes own the camera.
    if (!beeMode && !walkMode && !cinematic) frameCamera(sc.bounds);
    framedOrigin = o ? { lat: o.lat, lng: o.lng } : { lat: 0, lng: 0 };
  }
  // Re-place the bee's flower beacons against the freshly-built scene.
  if (beeMode) rebuildBeacons();
  // Refresh walk obstacles (plants grow/shift with year & season).
  if (walkMode) buildWalkObstacles();

  const n = (sc.plants || []).length;
  document.getElementById('hud').innerHTML =
    `<b>Year ${sc.year}</b> &nbsp;·&nbsp; ${n} plant${n === 1 ? '' : 's'}`
    + ((sc.buildings || []).length ? ` &nbsp;·&nbsp; ${sc.buildings.length} structure footprint(s)` : '')
    + (sc.terrain ? ' &nbsp;·&nbsp; terrain' : '');
};

window.permaSetSun = function (azDeg, altDeg) { setSun(azDeg, altDeg); };

// Detail / quality knob (V1.94): 0 Low · 1 Medium · 2 High. Drops the cached
// archetypes (their density depends on QUALITY) and re-renders the current scene
// at the new detail. Build-time only — per-frame cost is unchanged.
window.permaSetQuality = function (level) {
  const q = Math.max(0, Math.min(2, level | 0));
  if (q === QUALITY) return;
  QUALITY = q;
  TREE_CACHE.clear();
  SHRUB_CACHE.clear();
  HERB_CACHE.clear();
  ARCH = null;
  if (lastSceneObj) permaSetScene(lastSceneObj);   // same origin → camera stays put
};

// Legacy hook: scene3d.placed_plants_3d_state records carry lat/lng — project
// them with the cosLat metric about the last scene origin.
window.permaSetPlants = function (records) {
  if (!designGroup || !lastOrigin) return;
  const mPerDegLat = 111320.0;
  const cosLat = Math.max(1e-9, Math.cos(lastOrigin.lat * Math.PI / 180));
  const plants = (records || []).map(r => ({
    x: (r.lng - lastOrigin.lng) * mPerDegLat * cosLat,
    y: (r.lat - lastOrigin.lat) * mPerDegLat,
    plant_id: r.plant_id,
    height_m: r.height_m, canopy_m: r.canopy_m,
    plant_type: r.plant_type, foliage_type: r.foliage_type,
    scale_factor: r.scale_factor, spread_factor: r.spread_factor,
    spread_rate: r.spread_rate,
    color: r.color, opacity: r.presence_opacity,
    flower_color: r.flower_color, flower_form: r.flower_form,
    bloom_start: r.bloom_start, bloom_end: r.bloom_end,
  }));
  buildPlants(designGroup, plants, lastMonth, lastYear, lastTerrain);
};

