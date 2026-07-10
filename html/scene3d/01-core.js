// Part of the Site & Pattern 3D viewer, split out of the former
// single html/scene3d.html <script> (V2.24). Loaded as an ordered
// CLASSIC script by the bootstrap in scene3d.html — it shares the
// global scope with its siblings (THREE/OrbitControls/mergeGeometries
// are globals set by the bootstrap), so load ORDER is dependency
// order. Do not add ES `import`/`export` here.

// Spark — the OPTIONAL photoreal yard-scan backdrop (V1.65). Load it WITHOUT
// blocking module evaluation: a top-level `await` here would stall the entire
// viewer — window.permaSetScene is registered far below, so nothing past this
// point runs until the import settles, and if Spark were slow or hung the whole
// 3D view would silently never start. Fire-and-forget instead; SplatMesh /
// SparkRenderer fill in when ready and the splat code (all guarded, and the
// SparkRenderer is created lazily) simply no-ops until then. The core 3D view
// never waits on Spark.
let SplatMesh = null, SparkRenderer = null;
import('@sparkjsdev/spark')
  .then((m) => { SplatMesh = m.SplatMesh; SparkRenderer = m.SparkRenderer; })
  .catch((err) => console.warn('Spark splat backdrop unavailable:', err));

const SKY = 0xcfe3f2, GROUND = 0x8aa86f;

// ── wind + time ─────────────────────────────────────────────────────────────
const clock = new THREE.Clock();
const windUniforms = { uTime: { value: 0 } };

// ── seeded PRNG (mulberry32) ────────────────────────────────────────────────
function mulberry32(a) {
  return function() {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function hashPid(pid) {
  if (pid == null) return 0;
  if (typeof pid === 'number') return Math.abs(pid);
  let h = 0; const s = String(pid);
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

// ── seasonal color modifier ─────────────────────────────────────────────────
const _skyCol = new THREE.Color(SKY);

function seasonalColor(hex, foliageType, month) {
  const c = new THREE.Color(hex || '#66bb6a');
  const ft = (foliageType || '').toLowerCase();
  if (ft === 'evergreen') {
    if (month >= 11 || month <= 2) c.multiplyScalar(0.85);
    return c;
  }
  if (ft === 'deciduous' || ft === 'semi-evergreen') {
    if (month >= 4 && month <= 5)
      c.lerp(new THREE.Color('#c8e06a'), 0.3);
    else if (month >= 9 && month <= 10)
      c.lerp(new THREE.Color('#d4a030'), 0.55);
    else if (month >= 11 || month <= 3)
      c.set('#8b7355');
    return c;
  }
  if (month >= 11 || month <= 3) c.lerp(new THREE.Color('#a09060'), 0.5);
  return c;
}

let renderer;
try {
  // preserveDrawingBuffer lets the yard-photo bake read the canvas back with
  // toDataURL after an off-axis render (V1.65); negligible cost at this scale.
  renderer = new THREE.WebGLRenderer({ antialias: true,
                                       preserveDrawingBuffer: true });
} catch (e) {
  window.permaBootError = '<b>3D needs WebGL</b><br>This system\'s graphics '
    + 'stack doesn\'t offer WebGL, so the 3D preview can\'t render here. '
    + 'The 2D map is unaffected.';
  window.permaFatal(window.permaBootError);
  throw e;
}
// Cap the pixel ratio so 4K / Retina panels don't render 4× the fragments on
// modest GPUs (the visual gain past ~1.5× is negligible here).
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
// Filmic tone mapping (V2.12): rolls highlights off gently and deepens the
// greens — the single biggest step away from the old flat, clipped look.
// Light intensities below are tuned for it.
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
// The gradient sky dome (below) is the backdrop; fog blends the ground plane
// into its horizon band. Both colours track the sun via updateAtmosphere.
scene.fog = new THREE.Fog(0xeaf2f8, 380, 1500);

// Spark needs a SparkRenderer in the scene to draw splats with the normal
// THREE.WebGLRenderer (V1.65). Created LAZILY — only once Spark has loaded
// (background import above) AND a splat is actually added — so the core view
// never depends on Spark. Constructed defensively: if it fails, the design
// still renders, only the photoreal backdrop is unavailable.
let sparkRenderer = null;
function ensureSparkRenderer() {
  if (sparkRenderer || !SparkRenderer) return sparkRenderer;
  try {
    sparkRenderer = new SparkRenderer({ renderer });
    scene.add(sparkRenderer);
  } catch (e) {
    sparkRenderer = null;
  }
  return sparkRenderer;
}

const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 4000);
camera.position.set(45, 38, 55);

const controls = new OrbitControls(camera, renderer.domElement);
controls.maxPolarAngle = Math.PI / 2 - 0.02;   // never go underground
controls.target.set(0, 0, 0);
// Put the camera in the scene graph so objects parented to it (the bee avatar in
// "fly as a bee" mode) are traversed and rendered. Harmless for normal rendering.
scene.add(camera);

// Hover → name (V1.99; wildlife V2.12): raycast the ambient creatures first
// (so you can tell what a bug is — "Bumble bee · nectar on Wild Bergamot"), then
// fall back to the instanced plant meshes (each carries userData.pick = [name
// per instance]). Throttled; flower point-sprites aren't pickable.
const _ray = new THREE.Raycaster();
const _ptr = new THREE.Vector2();
let _lastPick = 0;
const _REL_WORDS = { nectar: 'sips nectar at', pollen: 'gathers pollen at',
  larval_host: 'lays eggs on', fruit_food: 'eats fruit of', seed_food: 'eats seed of',
  cover: 'shelters in', nesting: 'nests in' };
function _critterAt(object) {
  let o = object;
  while (o) { if (o.userData && o.userData.critterInfo) return o.userData.critterInfo; o = o.parent; }
  return null;
}
renderer.domElement.addEventListener('pointermove', (ev) => {
  const tip = document.getElementById('plant-tip');
  if (!tip) return;
  tip.style.left = ev.clientX + 'px'; tip.style.top = ev.clientY + 'px';
  const now = performance.now();
  if (now - _lastPick < 45) return;             // throttle the raycast
  _lastPick = now;
  const r = renderer.domElement.getBoundingClientRect();
  _ptr.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
  _ptr.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
  _ray.setFromCamera(_ptr, camera);
  let html = '';
  // 1) A creature under the cursor — name + what it uses this plant for.
  if (wildlifeGroup && wildlifeGroup.visible) {
    const cw = [];
    wildlifeGroup.traverse(o => { if (o.isMesh && _critterAt(o)) cw.push(o); });
    const ch = _ray.intersectObjects(cw, false);
    if (ch.length) {
      const info = _critterAt(ch[0].object);
      if (info) {
        const verb = _REL_WORDS[info.rel] || 'uses';
        html = '🐾 <b>' + info.name + '</b>'
          + (info.on ? ' · ' + verb + ' ' + info.on : '');
      }
    }
  }
  // 2) Otherwise the plant under the cursor.
  if (!html && plantsGroup) {
    const meshes = [];
    plantsGroup.traverse(o => { if (o.isInstancedMesh && o.userData.pick) meshes.push(o); });
    const hits = _ray.intersectObjects(meshes, false);
    for (const h of hits) {
      const nm = h.object.userData.pick[h.instanceId];
      if (nm) { html = nm; break; }
    }
  }
  tip.innerHTML = html;
  tip.style.display = html ? 'block' : 'none';
});
renderer.domElement.addEventListener('pointerleave', () => {
  const tip = document.getElementById('plant-tip');
  if (tip) tip.style.display = 'none';
});

const hemi = new THREE.HemisphereLight(0xdfeefc, 0x5d6e51, 0.9);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff4d6, 2.4);
sun.castShadow = true;
// 1024 is plenty: the crisp per-plant grounding comes from the cheap contact-
// shadow discs, not this map — halving it lightens the shadow pass for weak GPUs.
sun.shadow.mapSize.set(1024, 1024);
// Acne/peter-panning tune for a metre-scale scene with thin foliage shells.
sun.shadow.bias = -0.0003;
sun.shadow.normalBias = 0.02;
scene.add(sun, sun.target);

// ── sky dome + time-of-day atmosphere (V2.12) ───────────────────────────────
// A cheap BackSide sphere with a zenith→horizon gradient and an analytic sun
// disc/halo, replacing the flat background colour. updateAtmosphere() slides
// the palette between noon and golden hour from the sun's altitude, and keeps
// the fog + key light in step — so the "Time of day" slider now changes the
// whole mood of the scene, not just the shadow angle.
const skyU = {
  uZenith:  { value: new THREE.Color(0x7fb3e0) },
  uHorizon: { value: new THREE.Color(0xeaf2f8) },
  uSunDir:  { value: new THREE.Vector3(0, 1, 0) },
  uSunGlow: { value: new THREE.Color(0xfff2cc) },
  uGlowAmt: { value: 0.3 },
};
const skyDome = new THREE.Mesh(
  new THREE.SphereGeometry(2600, 32, 15),
  new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: skyU,
    vertexShader: [
      'varying vec3 vDir;',
      'void main() {',
      '  vDir = normalize(position);',
      '  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);',
      '}',
    ].join('\n'),
    fragmentShader: [
      'varying vec3 vDir;',
      'uniform vec3 uZenith; uniform vec3 uHorizon; uniform vec3 uSunGlow;',
      'uniform vec3 uSunDir; uniform float uGlowAmt;',
      'void main() {',
      '  float h = clamp(vDir.y, 0.0, 1.0);',
      '  float t = pow(1.0 - h, 2.2);',                 // haze thickens low
      '  vec3 col = mix(uZenith, uHorizon, t);',
      '  float s = clamp(dot(normalize(vDir), normalize(uSunDir)), 0.0, 1.0);',
      '  col += uSunGlow * (pow(s, 350.0) * 1.1 + pow(s, 24.0) * uGlowAmt);',
      '  gl_FragColor = vec4(col, 1.0);',
      '}',
    ].join('\n'),
  }));
skyDome.name = 'sky';
scene.add(skyDome);

// Noon ↔ low-sun palettes; t is driven from the sun's altitude in setSun.
const _ATM = {
  zenNoon: new THREE.Color(0x7fb3e0), zenLow: new THREE.Color(0x54719f),
  horNoon: new THREE.Color(0xeaf2f8), horLow: new THREE.Color(0xf5c88e),
  sunNoon: new THREE.Color(0xfff4d6), sunLow: new THREE.Color(0xffb45e),
};
function updateAtmosphere(altDeg) {
  const t = Math.pow(Math.max(0, Math.min(1, altDeg / 30)), 0.65);  // 1 = high sun
  skyU.uZenith.value.copy(_ATM.zenLow).lerp(_ATM.zenNoon, t);
  skyU.uHorizon.value.copy(_ATM.horLow).lerp(_ATM.horNoon, t);
  skyU.uSunGlow.value.copy(_ATM.sunLow).lerp(_ATM.sunNoon, t);
  skyU.uGlowAmt.value = 0.25 + 0.55 * (1 - t);         // bigger halo when low
  sun.color.copy(_ATM.sunLow).lerp(_ATM.sunNoon, t);
  sun.intensity = 1.5 + 0.9 * t;                       // softer key when low
  hemi.intensity = 0.55 + 0.35 * t;
  scene.fog.color.copy(skyU.uHorizon.value);           // ground melts into haze
}

// ── Night (V2.12) ────────────────────────────────────────────────────────────
// A moonlit render for when the sun is down: a deep sky, a moon disc high in the
// sky feeding the "sun" glow + a dim cool key light, a field of stars, and lower
// exposure. Toggled from permaSetScene via the contract's is_night flag.
let sceneNight = false;
let moonMesh = null, starField = null;
const _NIGHT = {
  zen: new THREE.Color(0x0b1430), hor: new THREE.Color(0x243a5a),
  moon: new THREE.Color(0xdfe6f2), fog: new THREE.Color(0x1a2740),
};
function ensureNightSky() {
  if (starField) return;
  // Stars: a Points field on the inside of a large sphere (upper hemisphere).
  const N = 500, pos = new Float32Array(N * 3);
  const rng = mulberry32(90210);
  for (let i = 0; i < N; i++) {
    const u = rng(), v = rng() * 0.75;              // bias to the upper sky
    const th = u * Math.PI * 2, ph = Math.acos(1 - v);
    const R = 2400;
    pos[i * 3] = Math.sin(ph) * Math.cos(th) * R;
    pos[i * 3 + 1] = Math.cos(ph) * R;
    pos[i * 3 + 2] = Math.sin(ph) * Math.sin(th) * R;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  starField = new THREE.Points(g, new THREE.PointsMaterial({
    color: 0xeaf0ff, size: 7, sizeAttenuation: true, transparent: true,
    opacity: 0.9, depthWrite: false, fog: false }));
  starField.name = 'stars'; starField.visible = false;
  scene.add(starField);
  if (!GLOW_TEX) GLOW_TEX = makeGlowTexture();
  // A crisp moon disc as a camera-facing sprite (so it never goes edge-on).
  const mc = document.createElement('canvas'); mc.width = mc.height = 64;
  const mg = mc.getContext('2d');
  mg.fillStyle = '#eef1f7'; mg.beginPath(); mg.arc(32, 32, 30, 0, Math.PI * 2); mg.fill();
  const moonTex = new THREE.CanvasTexture(mc);
  const moonGroup = new THREE.Group();
  const disc = new THREE.Sprite(new THREE.SpriteMaterial({ map: moonTex,
    transparent: true, depthWrite: false, fog: false }));
  disc.scale.setScalar(220);
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW_TEX,
    color: 0xcfe0ff, transparent: true, opacity: 0.5, depthWrite: false,
    blending: THREE.AdditiveBlending, fog: false }));
  halo.scale.setScalar(560);
  moonGroup.add(halo, disc);
  moonMesh = moonGroup; moonMesh.name = 'moon'; moonMesh.visible = false;
  scene.add(moonMesh);
}
function setNight() {
  sceneNight = true;
  ensureNightSky();
  const moonDir = new THREE.Vector3(0.35, 0.86, 0.37).normalize();
  skyU.uZenith.value.copy(_NIGHT.zen);
  skyU.uHorizon.value.copy(_NIGHT.hor);
  skyU.uSunDir.value.copy(moonDir);       // the "sun" glow becomes the moon glow
  skyU.uSunGlow.value.copy(_NIGHT.moon);
  skyU.uGlowAmt.value = 0.12;
  scene.fog.color.copy(_NIGHT.fog);
  // Dim, cool moonlight from the moon's direction — enough to read the foliage
  // as silhouettes with a hint of colour, but unmistakably night.
  sun.color.set(0xaec4ee); sun.intensity = 0.6;
  hemi.color.set(0x3a4c70); hemi.groundColor.set(0x141c2a); hemi.intensity = 0.5;
  sun.position.copy(moonDir).multiplyScalar(300); sun.target.position.set(0, 0, 0);
  renderer.toneMappingExposure = 1.0;
  moonMesh.position.copy(moonDir).multiplyScalar(1900); moonMesh.visible = true;
  starField.visible = true;
}
function setDay() {
  if (!sceneNight) return;
  sceneNight = false;
  hemi.color.set(0xdfeefc); hemi.groundColor.set(0x5d6e51);
  renderer.toneMappingExposure = 1.15;
  if (moonMesh) moonMesh.visible = false;
  if (starField) starField.visible = false;
}

// Everything rebuilt per scene push lives under one group.
let designGroup = null;
let lastOrigin = null;      // {lat, lng} for the legacy permaSetPlants hook
let lastMonth = 6;          // last scene month, for the legacy permaSetPlants hook
let lastYear = 0;           // last scene year, for the legacy permaSetPlants hook
let lastTerrain = null;     // last scene terrain, for the legacy permaSetPlants hook
let plantsGroup = null;     // sub-group holding plant instanced meshes
let framedOrigin = null;    // origin the camera was last auto-framed on
let lastBounds = null;      // last scene bounds, for permaResetView()

function sunVector(azDeg, altDeg) {
  // azimuth CW from north; scene: north = -z, east = +x.
  const az = azDeg * Math.PI / 180, alt = altDeg * Math.PI / 180;
  return new THREE.Vector3(
    Math.sin(az) * Math.cos(alt),    // east
    Math.sin(alt),                   // up
    -Math.cos(az) * Math.cos(alt),   // north → -z
  );
}

function setSun(azDeg, altDeg) {
  const v = sunVector(azDeg, altDeg);
  skyU.uSunDir.value.copy(v);          // sun disc + halo in the sky dome
  updateAtmosphere(altDeg);
  sun.position.copy(v).multiplyScalar(300);
  sun.target.position.set(0, 0, 0);
}
setSun(180, 55);   // sane default until the host pushes the real sun

// Resize the sun's shadow frustum to the scene — always safe to re-run.
function fitShadow(bounds) {
  const w = bounds.max_x - bounds.min_x, d = bounds.max_y - bounds.min_y;
  const r = Math.max(w, d) * 0.75;
  const cam = sun.shadow.camera;
  cam.left = -r; cam.right = r; cam.top = r; cam.bottom = -r;
  cam.near = 1; cam.far = 900;
  cam.updateProjectionMatrix();
}

// Point the camera + orbit target at the design. Only called on the first
// scene or when a different design is opened — never on a slider re-push — so
// the user's own orbit/zoom is preserved across Year/season changes.
function frameCamera(bounds) {
  if (!bounds) return;
  const w = bounds.max_x - bounds.min_x, d = bounds.max_y - bounds.min_y;
  const r = Math.max(w, d) * 0.75;
  const cx = (bounds.min_x + bounds.max_x) / 2;
  const cz = -(bounds.min_y + bounds.max_y) / 2;
  controls.target.set(cx, 0, cz);
  camera.position.set(cx + r * 0.9, r * 0.85, cz + r * 1.1);
  controls.update();
}

function fadeToward(hex, opacity) {
  // presence_opacity < 1 → blend the colour toward the sky tint.
  const c = new THREE.Color(hex || '#66bb6a');
  return c.lerp(new THREE.Color(SKY), 1 - Math.max(0, Math.min(1, opacity ?? 1)));
}

// Succession health (src/succession_engine.py): as the growing overstory shades
// an understory plant past its sun tolerance, its `health` falls 1 → 0 and we
// blend the foliage toward a dry straw-brown so it reads as *withered* rather
// than merely faded. Dead plants (health_state === 'dead') are dropped upstream
// in buildPlants, so this handles the healthy→declining transition. Takes and
// returns a THREE.Color (slots between seasonalColor and fadeColor).
function witherColor(col, health) {
  const h = Math.max(0, Math.min(1, health ?? 1));
  if (h >= 0.85) return col;
  return col.clone().lerp(new THREE.Color(0x8a7a3c), (0.85 - h) / 0.85 * 0.9);
}

