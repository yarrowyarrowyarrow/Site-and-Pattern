// Part of the Site & Pattern 3D viewer, split out of the former
// single html/scene3d.html <script> (V2.24). Loaded as an ordered
// CLASSIC script by the bootstrap in scene3d.html — it shares the
// global scope with its siblings (THREE/OrbitControls/mergeGeometries
// are globals set by the bootstrap), so load ORDER is dependency
// order. Do not add ES `import`/`export` here.

// ── "Fly as a bee" first-person mode (F37 increment 2; V2.12 nectar run) ────
// A low fly camera + bee-vision overlay + glowing nectar beacons over the
// chosen bee's floral-host plants. V2.12 turns the flight into a game: brush
// a glowing flower to collect its nectar (sparkle burst + HUD counter, F =
// autopilot to the nearest unvisited flower). Purely additive: when beeMode
// is off nothing here runs and OrbitControls owns the camera as before.
let beeMode = false;
let beeKind = 'bee';                     // 'bee' | 'butterfly' | 'moth' — picks the avatar
let beeApp = null;                       // avatar appearance spec (styles the flyer)
let beeTargetIds = new Set();            // String(plant_id) of the adult nectar plants
let beeHostIds = new Set();              // String(plant_id) of larval host plants (leps)
let beeLabel = '';                       // display name of the chosen creature (HUD)
let beaconGroup = null;
let beeBeacons = [];                     // [{key,name,pos,core,glow,beam,phase,visited}]
let beeHosts = [];                       // [{marker,glow,phase}] caterpillar-host markers
let beeVisited = new Set();              // beacon keys collected this run
let beeBursts = [];                      // live sparkle bursts [{pts,vel,t0}]
let beeAuto = null;                      // autopilot target {key,pos} | null
let tourMode = false;                    // seasonal auto-tour (host advances the month)
let sceneMonth = 6;                      // current scene month — bloom-gating + HUD
let beeMsg = '', beeMsgUntil = 0;        // transient HUD line ("nectar collected!")
let beeHudAt = 0;                        // last HUD refresh (throttled)
let beeGraceUntil = 0;                   // no collection right after spawning
let beeAvatar = null;                    // the visible flyer, parented to camera
let beeAvatarKind = '';                  // which kind the current avatar was built for
let beeBank = 0;                         // eased roll for a bit of life on turns
const beeVel = new THREE.Vector3();      // smoothed velocity (m/s) — glide, not stop
const beeKeys = new Set();
let beeYaw = 0, beePitch = -0.05;        // radians; yaw 0 → looking north (−z)
let beeDragging = false, beeLastX = 0, beeLastY = 0;
let beePrevT = 0;
const BEE_SPEED = 4.0;                    // flyer cruise (m/s) — an unhurried bee (was 7)
let beeNameSprite = null, beeNameText = '';   // floating flower-name label on approach
const _MONTHS3 = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December'];

// A small floating text label (canvas → sprite) used to name the flower the
// flyer is approaching. One reusable sprite; its texture is rebuilt only when
// the text changes.
function makeTextSprite() {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({
    transparent: true, depthWrite: false, depthTest: false }));
  s.renderOrder = 999;
  return s;
}
function setSpriteText(sprite, text) {
  const pad = 10, fs = 40;
  const cv = document.createElement('canvas');
  const ctx = cv.getContext('2d');
  ctx.font = '600 ' + fs + 'px system-ui, sans-serif';
  const w = Math.ceil(ctx.measureText(text).width) + pad * 2;
  const h = fs + pad * 2;
  cv.width = w; cv.height = h;
  const g = cv.getContext('2d');
  g.font = '600 ' + fs + 'px system-ui, sans-serif';
  g.textBaseline = 'middle';
  g.fillStyle = 'rgba(20,30,22,0.86)';
  const r = 12;
  g.beginPath();
  g.moveTo(r, 0); g.arcTo(w, 0, w, h, r); g.arcTo(w, h, 0, h, r);
  g.arcTo(0, h, 0, 0, r); g.arcTo(0, 0, w, 0, r); g.closePath(); g.fill();
  g.fillStyle = '#eafaea'; g.fillText(text, pad, h / 2 + 1);
  const tex = new THREE.CanvasTexture(cv);
  if (THREE.SRGBColorSpace) tex.colorSpace = THREE.SRGBColorSpace;
  if (sprite.material.map) sprite.material.map.dispose();
  sprite.material.map = tex; sprite.material.needsUpdate = true;
  sprite.userData.aspect = w / h;   // scale is set per-frame from the view distance
}

// Is a plant in bloom for the current scene month? Drives bloom-gated nectar
// beacons (V2.12 fix — nectar was collectable even out of bloom).
function inBloomNow(p) {
  const bs = p.bloom_start || 0, be = p.bloom_end || 0;
  return bs > 0 && sceneMonth >= bs && sceneMonth <= be;
}

const _esc = (s) => String(s).replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// A small procedural bee riding low-forward of the camera — company on the
// flight, not a windshield. Styled by an appearance spec (V2.12) so the avatar
// looks like the chosen species: fuzz/dark colours, abdominal band count, body
// shape (round bumble / slender sweat / stout leafcutter), metallic sheen for
// mason & green sweat bees. Lit + emissive so it reads under any sun; wings are
// swept back, small and mostly transparent (the V2.12 fix — the old wing discs
// covered half the screen).
const _DEF_BEE_APP = { fuzz: '#d99b26', dark: '#201a14', bands: 2,
                       shape: 'round', size: 1.0, metallic: false };
function makeBeeAvatar(app) {
  app = Object.assign({}, _DEF_BEE_APP, app || {});
  const g = new THREE.Group();
  const met = app.metallic ? { metalness: 0.7, roughness: 0.35 } : {};
  const fuzz = new THREE.MeshStandardMaterial(Object.assign({ color: app.fuzz,
                 roughness: 0.9, emissive: 0x241a08, emissiveIntensity: 0.4 }, met));
  const dark = new THREE.MeshStandardMaterial(Object.assign({ color: app.dark,
                 roughness: 0.85, emissive: 0x100c08, emissiveIntensity: 0.4 }, met));
  const sphere = (r) => new THREE.SphereGeometry(r, 14, 10);
  // Body shape: abdomen elongation + girth by growth form.
  const shp = app.shape === 'slender' ? [0.82, 0.8, 1.7]
            : app.shape === 'stout'   ? [1.02, 0.95, 1.2]
            : [0.92, 0.88, 1.45];                                 // round
  const thorax = new THREE.Mesh(sphere(0.5), fuzz); thorax.scale.set(1, 0.9, 1);
  const head = new THREE.Mesh(sphere(0.32), dark); head.position.set(0, 0, -0.62);
  g.add(thorax, head);
  const antGeo = new THREE.CylinderGeometry(0.018, 0.018, 0.4, 5);
  for (const s of [-1, 1]) {
    const a = new THREE.Mesh(antGeo, dark);
    a.position.set(0.1 * s, 0.16, -0.82); a.rotation.set(-0.9, 0, 0.25 * s);
    g.add(a);
  }
  const abdomen = new THREE.Mesh(sphere(0.55), dark);
  abdomen.scale.set(shp[0], shp[1], shp[2]); abdomen.position.set(0, -0.03, 0.8);
  g.add(abdomen);
  // Abdominal bands (0–3): alternating fuzz stripes down the abdomen.
  const nb = Math.max(0, Math.min(3, app.bands | 0));
  for (let i = 0; i < nb; i++) {
    const band = new THREE.Mesh(sphere(0.57), fuzz);
    band.scale.set(shp[0] * 1.02, shp[1] * 1.02, 0.34);
    band.position.set(0, -0.03, 0.5 + i * 0.45);
    g.add(band);
  }
  const tip = new THREE.Mesh(sphere(0.3), app.cuckoo ? fuzz : dark);
  tip.scale.set(0.9, 0.85, 1.1); tip.position.set(0, -0.04, 0.8 + shp[2] * 0.35);
  g.add(tip);
  const wingGeo = new THREE.CircleGeometry(0.55, 12);
  const wingM = new THREE.MeshBasicMaterial({ color: 0xe8f1fa, transparent: true,
                 opacity: 0.22, side: THREE.DoubleSide, depthWrite: false });
  const wings = [];
  for (const s of [-1, 1]) {
    const pivot = new THREE.Group();
    pivot.position.set(0.14 * s, 0.38, 0.05);
    const w = new THREE.Mesh(wingGeo, wingM);
    w.scale.set(0.5, 1.0, 1); w.position.set(0.42 * s, 0.05, 0.18);
    w.rotation.set(-1.15, 0, 0.25 * s);        // swept back, near-flat
    pivot.add(w); g.add(pivot);
    wings.push({ pivot, sign: s });
  }
  g.userData.wings = wings;
  g.userData.flap = { base: 0.2, amp: 0.75, speed: 0.09 };   // fast bee flutter
  g.scale.setScalar(0.2 * (0.82 + 0.32 * (app.size || 1)));
  return g;
}

// A butterfly (or drab moth) riding low-forward of the camera. Two wing pairs
// per side on a slim body; the wings flap up and down with a graceful, slower
// beat than the bee. Colours: butterflies get a warm patterned upper wing, moths
// a muted tan/grey. Lit + emissive so the flyer reads under any sun angle.
function makeButterflyAvatar(moth, app) {
  const g = new THREE.Group();
  const bodyM = new THREE.MeshStandardMaterial({ color: moth ? 0x4a3d2e : 0x2a2320,
                 roughness: 0.85, emissive: 0x140f0a, emissiveIntensity: 0.5 });
  const _c = (hex, fb) => (hex ? new THREE.Color(hex).getHex() : fb);
  const foreCol = _c(app && app.fore, moth ? 0xb8a274 : 0xe6912f);   // upper wing
  const hindCol = _c(app && app.hind, moth ? 0x9c8763 : 0xd8701f);   // lower wing
  const edge = _c(app && app.edge, moth ? 0x5c4a30 : 0x2a1c10);
  const wingMat = (c) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.7,
                    emissive: c, emissiveIntensity: 0.28, side: THREE.DoubleSide,
                    flatShading: true });
  const sphere = (r) => new THREE.SphereGeometry(r, 12, 9);
  // slim segmented body along -z (head) .. +z (abdomen)
  const thorax = new THREE.Mesh(sphere(0.16), bodyM); thorax.scale.set(1, 1, 1.4);
  const head = new THREE.Mesh(sphere(0.12), bodyM); head.position.set(0, 0.02, -0.28);
  const abd = new THREE.Mesh(sphere(0.13), bodyM);
  abd.scale.set(0.8, 0.8, 2.6); abd.position.set(0, -0.01, 0.4);
  g.add(thorax, head, abd);
  const antGeo = new THREE.CylinderGeometry(0.008, 0.008, 0.32, 4);
  const clubGeo = new THREE.SphereGeometry(0.03, 6, 5);
  for (const s of [-1, 1]) {
    const a = new THREE.Mesh(antGeo, bodyM);
    a.position.set(0.06 * s, 0.08, -0.42); a.rotation.set(-0.7, 0, 0.28 * s);
    g.add(a);
    if (!moth) {                                  // clubbed tips = butterfly
      const c = new THREE.Mesh(clubGeo, bodyM);
      c.position.set(0.13 * s, 0.2, -0.54); g.add(c);
    }
  }
  // A wing = fore + hind lobe, built flat in the XZ plane then hung off a pivot
  // on the body midline so it flaps around the forward (z) axis.
  const foreGeo = new THREE.CircleGeometry(0.42, 16).rotateX(-Math.PI / 2);
  const hindGeo = new THREE.CircleGeometry(0.30, 14).rotateX(-Math.PI / 2);
  const wings = [];
  for (const s of [-1, 1]) {
    const pivot = new THREE.Group();
    const fore = new THREE.Mesh(foreGeo, wingMat(foreCol));
    fore.scale.set(0.85, 1, moth ? 0.7 : 0.95);
    fore.position.set(0.42 * s, 0, -0.1);
    const hind = new THREE.Mesh(hindGeo, wingMat(hindCol));
    hind.scale.set(0.9, 1, 1.05);
    hind.position.set(0.4 * s, -0.01, 0.3);
    const rim = new THREE.Mesh(new THREE.RingGeometry(0.35, 0.42, 18).rotateX(-Math.PI / 2),
                  new THREE.MeshBasicMaterial({ color: edge, side: THREE.DoubleSide,
                    transparent: true, opacity: 0.5 }));
    rim.position.set(0.42 * s, 0.002, -0.1); rim.scale.set(0.85, 1, 0.95);
    pivot.add(fore, hind, rim);
    g.add(pivot);
    wings.push({ pivot, sign: s });
  }
  g.userData.wings = wings;
  // Rest angled downward so the wings frame the lower view rather than fill it;
  // moths beat faster + shallower, butterflies a big slow graceful flap.
  g.userData.flap = moth ? { base: -0.45, amp: 0.75, speed: 0.055 }
                         : { base: -0.6, amp: 1.05, speed: 0.028 };
  g.scale.setScalar(moth ? 0.42 : 0.46);
  return g;
}

// (Re)build the avatar for the current beeKind + appearance and park it
// low-forward of the camera. Cached by a signature so switching creatures
// rebuilds, but a same-creature re-push doesn't.
function ensureAvatar() {
  const sig = beeKind + '|' + (beeApp ? JSON.stringify(beeApp) : '');
  if (beeAvatar && beeAvatarKind === sig) return;
  if (beeAvatar) { camera.remove(beeAvatar); disposeObject(beeAvatar); }
  beeAvatar = beeKind === 'bee' ? makeBeeAvatar(beeApp)
            : makeButterflyAvatar(beeKind === 'moth', beeApp);
  beeAvatar.position.set(0, beeKind === 'bee' ? -0.42 : -0.86,
                            beeKind === 'bee' ? -1.1 : -1.5);
  beeAvatarKind = sig;
  camera.add(beeAvatar);
}

function disposeObject(root) {
  root.traverse(o => {
    if (o.geometry) o.geometry.dispose();
    if (o.material) for (const m of (Array.isArray(o.material) ? o.material : [o.material]))
      m && m.dispose();
  });
}
const _BEE_MOVE_CODES = new Set([
  'KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyQ', 'KeyE',
  'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space', 'ShiftLeft']);

function groundAtCamera() {
  // terrainHeightAt expects (x_east, y_north); world z = −y_north.
  return terrainHeightAt(camera.position.x, -camera.position.z, lastTerrain);
}

// Soft radial glow sprite texture, shared by beacons + sparkle bursts.
let GLOW_TEX = null;
function makeGlowTexture() {
  const s = 64, cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const g = cv.getContext('2d');
  const grd = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  grd.addColorStop(0, 'rgba(255,255,255,1)');
  grd.addColorStop(0.35, 'rgba(255,255,255,.55)');
  grd.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grd; g.fillRect(0, 0, s, s);
  const t = new THREE.CanvasTexture(cv);
  if (THREE.SRGBColorSpace) t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function disposeBeacons() {
  if (beaconGroup) {
    scene.remove(beaconGroup);
    beaconGroup.traverse(o => {
      // Sprites share one three.js-internal geometry — never dispose that.
      if (o.geometry && !o.isSprite) o.geometry.dispose();
      if (o.material) o.material.dispose();    // GLOW_TEX itself is shared & kept
    });
    beaconGroup = null;
  }
  beeBeacons = [];
  beeHosts = [];
}

// Nectar beacons (V2.12): a small warm core + an additive glow sprite + a faint
// light beam rising over each nectar plant — readable across a meadow without
// looking like a second sun. BLOOM-GATED: a plant only beacons in the months it
// actually flowers (the V2.12 fix — nectar used to be collectable year-round).
// Butterflies/moths also get low green "caterpillar nursery" markers over their
// larval host plants (present-gated, never collectable).
function rebuildBeacons() {
  disposeBeacons();
  if (!beeMode || !lastSceneObj) { updateBeeHud(); return; }
  if (beeTargetIds.size === 0 && beeHostIds.size === 0) { updateBeeHud(); return; }
  if (!GLOW_TEX) GLOW_TEX = makeGlowTexture();
  beaconGroup = new THREE.Group();
  const coreGeo = new THREE.SphereGeometry(0.12, 10, 8);
  const beamGeo = new THREE.CylinderGeometry(0.03, 0.10, 2.6, 6, 1, true);
  const hostGeo = new THREE.IcosahedronGeometry(0.16, 0);
  for (const p of (lastSceneObj.plants || [])) {
    if ((p.opacity ?? 1) < 0.25) continue;     // not yet present this year
    const pid = String(p.plant_id);
    const x = p.x, wy = p.y, z = -wy;
    const gy = terrainHeightAt(x, wy, lastTerrain);
    const isNectar = beeTargetIds.has(pid) && inBloomNow(p);   // BLOOM-GATED
    if (isNectar) {
      const top = gy + Math.max(0.4, p.height_m || 0.6) + 0.35;
      const pos = new THREE.Vector3(x, top, z);
      const core = new THREE.Mesh(coreGeo, new THREE.MeshBasicMaterial({
        color: 0xffd75e, transparent: true, opacity: 0.95 }));
      core.position.copy(pos);
      const glow = new THREE.Sprite(new THREE.SpriteMaterial({
        map: GLOW_TEX, color: 0xffc94d, transparent: true, opacity: 0.75,
        blending: THREE.AdditiveBlending, depthWrite: false }));
      glow.position.copy(pos); glow.scale.setScalar(1.5);
      const beam = new THREE.Mesh(beamGeo, new THREE.MeshBasicMaterial({
        color: 0xffd75e, transparent: true, opacity: 0.10, side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending, depthWrite: false }));
      beam.position.set(x, top + 1.1, z);
      beaconGroup.add(core, glow, beam);
      const b = { key: pid + '@' + x + ',' + wy,
                  name: p.common_name || 'flower', pos, core, glow, beam,
                  phase: (hashPid(p.plant_id) % 100) / 16, visited: false };
      if (beeVisited.has(b.key)) styleBeaconVisited(b);
      beeBeacons.push(b);
    } else if (beeHostIds.has(pid)) {
      // Caterpillar host: a low green faceted marker + soft green glow. (Skip if
      // this plant is also a live nectar beacon this month — that took priority.)
      const top = gy + Math.min(1.4, Math.max(0.35, (p.height_m || 0.6) * 0.6));
      const pos = new THREE.Vector3(x, top, z);
      const marker = new THREE.Mesh(hostGeo, new THREE.MeshStandardMaterial({
        color: 0x6ab04a, roughness: 0.6, emissive: 0x1f4d1a,
        emissiveIntensity: 0.6, flatShading: true }));
      marker.position.copy(pos);
      const glow = new THREE.Sprite(new THREE.SpriteMaterial({
        map: GLOW_TEX, color: 0x8fe06a, transparent: true, opacity: 0.4,
        blending: THREE.AdditiveBlending, depthWrite: false }));
      glow.position.copy(pos); glow.scale.setScalar(0.9);
      beaconGroup.add(marker, glow);
      beeHosts.push({ marker, glow, pos, phase: (hashPid(p.plant_id) % 100) / 16 });
    }
  }
  // A vanished autopilot target (its bloom ended on a month change) is dropped.
  if (beeAuto && !beeBeacons.some(b => b.key === beeAuto.key)) beeAuto = null;
  scene.add(beaconGroup);
  updateBeeHud();
}

function styleBeaconVisited(b) {
  b.visited = true;
  b.core.material.color.set(0x9fd68a);
  b.core.material.opacity = 0.55;
  b.glow.material.color.set(0x9fd68a);
  b.glow.material.opacity = 0.12;
  b.glow.scale.setScalar(0.45);
  b.beam.visible = false;
}

function collectBeacon(b, t) {
  styleBeaconVisited(b);
  beeVisited.add(b.key);
  spawnBurst(b.pos, t);
  if (beeAuto && beeAuto.key === b.key) beeAuto = null;
  const got = beeBeacons.filter(x => x.visited).length;
  if (got < beeBeacons.length) {           // else the standard line celebrates
    beeMsg = '🌼 <b>' + _esc(b.name) + '</b> — nectar collected!';
    beeMsgUntil = t + 2000;
  } else { beeMsg = ''; beeMsgUntil = 0; }
  updateBeeHud(t);
}

// A short-lived sparkle burst where the nectar was collected.
function spawnBurst(pos, t) {
  const n = 26, arr = new Float32Array(n * 3), vel = [];
  for (let i = 0; i < n; i++) {
    arr[i * 3] = pos.x; arr[i * 3 + 1] = pos.y; arr[i * 3 + 2] = pos.z;
    const th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
    const sp = 0.8 + Math.random() * 1.6;
    vel.push(new THREE.Vector3(Math.sin(ph) * Math.cos(th) * sp,
                               Math.cos(ph) * sp * 0.8 + 0.6,
                               Math.sin(ph) * Math.sin(th) * sp));
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(arr, 3));
  const pts = new THREE.Points(geo, clampPointSize(new THREE.PointsMaterial({
    map: GLOW_TEX, color: 0xffe28a, size: 0.16, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false,
    sizeAttenuation: true }), 72));
  scene.add(pts);
  beeBursts.push({ pts, vel, t0: t });
}

function stepBursts(t, dt) {
  for (let i = beeBursts.length - 1; i >= 0; i--) {
    const b = beeBursts[i], age = (t - b.t0) / 900;
    if (age >= 1) {
      scene.remove(b.pts); b.pts.geometry.dispose(); b.pts.material.dispose();
      beeBursts.splice(i, 1);
      continue;
    }
    const pos = b.pts.geometry.attributes.position;
    for (let k = 0; k < b.vel.length; k++) {
      b.vel[k].y -= 2.2 * dt;                          // a little gravity
      pos.setXYZ(k, pos.getX(k) + b.vel[k].x * dt,
                    pos.getY(k) + b.vel[k].y * dt,
                    pos.getZ(k) + b.vel[k].z * dt);
    }
    pos.needsUpdate = true;
    b.pts.material.opacity = 1 - age;
  }
}
function clearBursts() {
  for (const b of beeBursts) {
    scene.remove(b.pts); b.pts.geometry.dispose(); b.pts.material.dispose();
  }
  beeBursts = [];
}

// ── nectar HUD ──────────────────────────────────────────────────────────────
const _ARROWS = ['↑', '↗', '→', '↘', '↓', '↙', '←', '↖'];

function nearestUnvisited() {
  let best = null, bd = Infinity;
  for (const b of beeBeacons) {
    if (b.visited) continue;
    const d = camera.position.distanceTo(b.pos);
    if (d < bd) { bd = d; best = b; }
  }
  return best ? { b: best, d: bd } : null;
}

const _CREATURE_ICON = { bee: '🐝', butterfly: '🦋', moth: '🌙' };

function updateBeeHud(t) {
  const h = document.getElementById('bee-hint');
  if (!h || !beeMode) return;
  if (beeMsg && (t ?? performance.now()) < beeMsgUntil) { h.innerHTML = beeMsg; return; }
  const icon = _CREATURE_ICON[beeKind] || '🐝';
  const who = _esc(beeLabel) || 'this pollinator';
  const controls = 'WASD fly · Q/E up-down · drag to look';
  const hostHint = beeHosts.length ? ' · 🌿 green = caterpillar host' : '';
  const total = beeBeacons.length;
  const got = beeBeacons.filter(b => b.visited).length;

  // Seasonal tour: show the month and the running nectar tally.
  if (tourMode) {
    h.innerHTML = '🌸 <b>Touring the year</b> — ' + _MONTHS3[sceneMonth]
      + ' · ' + icon + ' ' + who + ' · nectar collected ' + beeVisited.size
      + hostHint + ' · toggle <b>Tour</b> off to fly yourself';
    return;
  }

  if (!total) {
    // No collectable nectar THIS MONTH. Distinguish "not in bloom now" from
    // "adult doesn't feed" (non-feeding moths) from "no nectar plants at all".
    if (beeTargetIds.size > 0) {
      h.innerHTML = icon + ' <b>' + who + '</b> — nothing it drinks from is in bloom in '
        + _MONTHS3[sceneMonth] + '. Try <b>🌸 Tour the year</b> or the season slider.'
        + hostHint;
    } else if (beeHostIds.size > 0) {
      h.innerHTML = icon + ' <b>' + who + '</b> doesn\'t feed as an adult — the 🌿 green '
        + 'markers are its caterpillar host plants. ' + controls;
    } else {
      h.innerHTML = icon + ' <b>' + who + '</b> — no plants for it in this design yet · '
        + controls;
    }
    return;
  }
  if (got >= total) {
    h.innerHTML = '🎉 <b>All ' + total + ' bloom' + (total === 1 ? '' : 's')
      + ' visited!</b> This design feeds ' + who + ' in ' + _MONTHS3[sceneMonth]
      + '.' + hostHint;
    return;
  }
  // Relative bearing to the nearest unvisited flower → an 8-way arrow.
  const nu = nearestUnvisited();
  const dx = nu.b.pos.x - camera.position.x, dz = nu.b.pos.z - camera.position.z;
  const brg = Math.atan2(dx, -dz) - beeYaw;
  const idx = ((Math.round(brg / (Math.PI / 4)) % 8) + 8) % 8;
  h.innerHTML = icon + ' <b>Nectar ' + got + '/' + total + '</b> · nearest '
    + Math.max(1, Math.round(nu.d)) + ' m ' + _ARROWS[idx] + ' · ' + controls
    + ' · <b>F</b> = fly me there' + hostHint;
}

// The overlay tint is a bee-specific "UV goggles" cue; butterflies/moths get a
// plain soft vignette instead (no false claim about their colour vision).
function setBeeVisionUI(on) {
  const v = document.getElementById('bee-vision');
  const h = document.getElementById('bee-hint');
  if (v) {
    v.style.display = on ? 'block' : 'none';
    v.style.background = beeKind === 'bee' ? '' :
      'radial-gradient(ellipse 84% 84% at center,' +
      ' rgba(0,0,0,0) 58%, rgba(20,28,40,.40) 100%)';
  }
  if (h) h.style.display = on ? 'block' : 'none';
}

// Spawn at the design centre, flower height, facing the nearest target so the
// first glowing flower is on screen immediately (also the bee-mode Reset view).
function beeSpawn() {
  if (lastBounds) {
    const cx = (lastBounds.min_x + lastBounds.max_x) / 2;
    const cz = -(lastBounds.min_y + lastBounds.max_y) / 2;
    camera.position.set(cx, 0, cz + 6);
  }
  beeYaw = 0; beePitch = -0.05;
  camera.position.y = groundAtCamera() + 1.6;   // flower-and-a-bit height
  beeVel.set(0, 0, 0);
  beeAuto = null;
  beeGraceUntil = performance.now() + 800;
  const nu = nearestUnvisited();
  if (nu) beeYaw = Math.atan2(nu.b.pos.x - camera.position.x,
                              -(nu.b.pos.z - camera.position.z));
}

function enterBeeMode() {
  controls.enabled = false;
  beeVisited.clear();                 // every flight is a fresh nectar run
  beeMsg = ''; beeMsgUntil = 0;
  beePrevT = 0;
  ensureAvatar();
  beeAvatar.visible = true;
  setBeeVisionUI(true);
  if (!beeNameSprite) { beeNameSprite = makeTextSprite(); scene.add(beeNameSprite); }
  beeNameSprite.visible = false; beeNameText = '';
  if (wildlifeGroup) wildlifeGroup.visible = false;   // focus on the flown creature
  if (spotGroup) spotGroup.visible = false;           // the spotlight is orbit/walk-only
  rebuildBeacons();
  beeSpawn();
  updateBeeHud();
}

function exitBeeMode() {
  beeKeys.clear();
  beeDragging = false;
  beeAuto = null;
  tourMode = false;
  clearBursts();
  if (beeAvatar) beeAvatar.visible = false;
  if (beeNameSprite) beeNameSprite.visible = false;
  setBeeVisionUI(false);
  rebuildBeacons();                 // beeMode is false now → clears the beacons
  if (wildlifeGroup) wildlifeGroup.visible = true;   // wildlife returns in orbit
  if (spotGroup) spotGroup.visible = true;           // spotlight returns too
  controls.enabled = true;
  if (lastBounds) frameCamera(lastBounds);   // back to a sensible orbit
  else controls.update();
}

// F = autopilot: glide to the nearest unvisited flower (any move key cancels).
function startBeeAutopilot() {
  const nu = nearestUnvisited();
  if (!nu) return;
  beeAuto = { key: nu.b.key, pos: nu.b.pos.clone() };
  beeMsg = '🐝 Flying you to <b>' + _esc(nu.b.name) + '</b>…';
  beeMsgUntil = performance.now() + 1400;
  updateBeeHud();
}

// Shortest-arc angle step, capped at maxStep — the autopilot's easing turn.
function _turnToward(a, b, maxStep) {
  let d = (b - a) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return a + Math.max(-maxStep, Math.min(maxStep, d));
}

function beeStep(t) {
  const dt = beePrevT ? Math.min(0.05, (t - beePrevT) / 1000) : 0.016;
  beePrevT = t;

  if (beeAuto && beeKeys.size) beeAuto = null;   // manual input takes over
  // Seasonal tour: keep auto-hopping to the nearest unvisited bloom (silent — the
  // HUD shows the touring state). The host advances the month underneath us.
  if (tourMode && !beeAuto && beeKeys.size === 0) {
    const nu = nearestUnvisited();
    if (nu) beeAuto = { key: nu.b.key, pos: nu.b.pos.clone() };
  }
  const want = new THREE.Vector3();
  let strafe = 0;
  if (beeAuto) {
    // Ease yaw/pitch toward the target flower and fly at it, slowing on approach.
    const d = new THREE.Vector3().subVectors(beeAuto.pos, camera.position);
    const dist = d.length();
    if (dist < 1.2) beeAuto = null;              // collection radius takes it
    else {
      beeYaw = _turnToward(beeYaw, Math.atan2(d.x, -d.z), 1.9 * dt);
      beePitch = _turnToward(beePitch,
        Math.asin(Math.max(-1, Math.min(1, d.y / dist))), 1.3 * dt);
      // Ease right down as it nears the flower so the arrival reads, not blurs.
      want.copy(d).normalize().multiplyScalar(Math.min(BEE_SPEED, 1.1 + dist * 0.7));
    }
  }
  const cp = Math.cos(beePitch), sp = Math.sin(beePitch);
  const dir = new THREE.Vector3(Math.sin(beeYaw) * cp, sp, -Math.cos(beeYaw) * cp);
  if (!beeAuto && want.lengthSq() === 0) {
    const right = new THREE.Vector3().crossVectors(dir, _yAxis).normalize();
    if (beeKeys.has('KeyW') || beeKeys.has('ArrowUp'))    want.add(dir);
    if (beeKeys.has('KeyS') || beeKeys.has('ArrowDown'))  want.addScaledVector(dir, -1);
    if (beeKeys.has('KeyD') || beeKeys.has('ArrowRight')) { want.add(right); strafe += 1; }
    if (beeKeys.has('KeyA') || beeKeys.has('ArrowLeft'))  { want.addScaledVector(right, -1); strafe -= 1; }
    if (beeKeys.has('KeyE') || beeKeys.has('Space'))      want.y += 1;
    if (beeKeys.has('KeyQ') || beeKeys.has('ShiftLeft'))  want.y -= 1;
    if (want.lengthSq() > 0) want.normalize().multiplyScalar(BEE_SPEED);
  }
  // Smoothed velocity: the bee glides and settles instead of stopping dead.
  beeVel.lerp(want, 1 - Math.exp(-6 * dt));
  camera.position.addScaledVector(beeVel, dt);
  camera.position.y += Math.sin(t * 0.004) * 0.006;   // gentle idle bob
  const g = groundAtCamera() + 0.3;                   // never sink below ground
  if (camera.position.y < g) camera.position.y = g;
  camera.lookAt(camera.position.x + dir.x,
                camera.position.y + dir.y,
                camera.position.z + dir.z);
  // Bank into strafes — fully on the bee, softly on the camera for flight feel.
  beeBank += ((-0.35 * strafe) - beeBank) * Math.min(1, dt * 6);
  camera.rotateZ(beeBank * 0.35);

  // Animate the visible flyer: wingbeat (per-kind rate/amplitude) + a hover bob.
  if (beeAvatar && beeAvatar.visible) {
    const fp = beeAvatar.userData.flap;
    const flap = fp.base + (0.5 + 0.5 * Math.sin(t * fp.speed)) * fp.amp;
    for (const { pivot, sign } of beeAvatar.userData.wings) pivot.rotation.z = sign * flap;
    beeAvatar.position.y = (beeKind === 'bee' ? -0.42 : -0.86) + Math.sin(t * 0.006) * 0.03;
    beeAvatar.rotation.z = beeBank;
  }

  // Nectar collection: brush a glowing flower to collect it. A short grace
  // window after spawning stops a flower under the spawn point from being
  // collected before the player has even moved.
  if (t > beeGraceUntil)
    for (const b of beeBeacons)
      if (!b.visited && camera.position.distanceTo(b.pos) < 1.25) collectBeacon(b, t);
  stepBursts(t, dt);

  // Reveal the flower's name as the flyer approaches it: a floating label over
  // the nearest unvisited bloom within ~3.5 m (the flower the flyer is heading
  // for). The collect callout still names it on arrival.
  if (beeNameSprite) {
    const nu = nearestUnvisited();
    if (nu && nu.d < 4.0) {
      if (beeNameText !== nu.b.name) { beeNameText = nu.b.name; setSpriteText(beeNameSprite, nu.b.name); }
      // Constant on-screen size: world height scales with the view distance so
      // the label reads the same near or far (never fills the screen up close).
      const hh = 0.052 * Math.max(1.2, nu.d);
      beeNameSprite.scale.set((beeNameSprite.userData.aspect || 4) * hh, hh, 1);
      beeNameSprite.position.set(nu.b.pos.x, nu.b.pos.y + 0.45 + hh * 0.6, nu.b.pos.z);
      beeNameSprite.material.opacity = Math.max(0, Math.min(1, (4.0 - nu.d) / 1.6));
      beeNameSprite.visible = true;
    } else {
      beeNameSprite.visible = false;
    }
  }

  // Pulse the unvisited glows; float the cores gently. Everything melts away
  // as the bee arrives (nearFade) — a marker 0.6 m from the camera would
  // otherwise fill half the screen — and the additive glow/beam also dim with
  // proximity so a close beacon never washes the view white.
  for (const b of beeBeacons) {
    const d = camera.position.distanceTo(b.pos);
    const nearFade = Math.max(0, Math.min(1, (d - 0.7) / 1.1));
    if (b.visited) {
      b.core.material.opacity = 0.55 * nearFade;
      b.glow.material.opacity = 0.12 * nearFade;
      continue;
    }
    const near = Math.max(0.3, Math.min(1, d / 6));
    b.glow.scale.setScalar(1.5 * near * (1 + 0.16 * Math.sin(t * 0.005 + b.phase)));
    b.glow.material.opacity = 0.75 * Math.max(0.35, Math.min(1, d / 5)) * nearFade;
    b.beam.material.opacity = 0.10 * Math.max(0.25, Math.min(1, d / 6)) * nearFade;
    b.core.material.opacity = 0.95 * nearFade;
    b.core.position.y = b.pos.y + Math.sin(t * 0.0035 + b.phase) * 0.08;
  }
  // Caterpillar-host markers: slow spin + a gentle green pulse.
  for (const hst of beeHosts) {
    hst.marker.rotation.y += dt * 0.7;
    hst.marker.position.y = hst.pos.y + Math.sin(t * 0.003 + hst.phase) * 0.05;
    hst.glow.scale.setScalar(0.9 * (1 + 0.18 * Math.sin(t * 0.004 + hst.phase)));
  }

  if (t - beeHudAt > 200) { beeHudAt = t; updateBeeHud(t); }
}

addEventListener('keydown', (e) => {
  if (!beeMode) return;
  if (e.code === 'KeyF') { startBeeAutopilot(); e.preventDefault(); return; }
  if (_BEE_MOVE_CODES.has(e.code)) { beeKeys.add(e.code); e.preventDefault(); }
});
addEventListener('keyup', (e) => { beeKeys.delete(e.code); });
renderer.domElement.addEventListener('pointerdown', (e) => {
  if (!beeMode) return;
  beeDragging = true; beeLastX = e.clientX; beeLastY = e.clientY;
});
addEventListener('pointerup', () => { beeDragging = false; });
renderer.domElement.addEventListener('pointermove', (e) => {
  if (!beeMode || !beeDragging) return;
  beeAuto = null;                                  // drag-look takes over
  beeYaw += (e.clientX - beeLastX) * 0.005;
  beePitch = Math.max(-1.4, Math.min(1.4, beePitch - (e.clientY - beeLastY) * 0.005));
  beeLastX = e.clientX; beeLastY = e.clientY;
});

window.permaSetBeeMode = function (on) {
  const want = !!on;
  if (want === beeMode) return;
  beeMode = want;
  if (beeMode) enterBeeMode(); else exitBeeMode();
};
// Set the chosen pollinator's plants + avatar kind. ``ids`` are adult nectar
// plants (bloom-gated beacons); ``hostIds`` are larval hosts (butterflies/moths)
// shown as green nursery markers; ``kind`` picks the flying avatar.
window.permaSetBeeTargets = function (ids, label, kind, hostIds, appearance) {
  beeTargetIds = new Set((ids || []).map(String));
  beeHostIds = new Set((hostIds || []).map(String));
  beeLabel = String(label || '');
  beeApp = appearance || null;
  const k = (kind === 'butterfly' || kind === 'moth') ? kind : 'bee';
  beeKind = k;
  if (beeMode) { ensureAvatar(); beeAvatar.visible = true; setBeeVisionUI(true); }
  beeVisited.clear();                 // a new creature starts a fresh nectar run
  beeAuto = null;
  rebuildBeacons();
};

// Toggle the seasonal nectar tour: the flyer auto-hops flower to flower while
// the host advances the scene month, so blooms come and go across the year.
window.permaSetBeeTour = function (on) {
  tourMode = !!on;
  if (!tourMode) beeAuto = null;
  updateBeeHud();
};

// Reset view — registered for BOTH callers (the 3D window's "Reset view"
// button and the sprite gallery); before V2.12 this hook was never defined,
// so the button silently did nothing. In fly mode it re-spawns the flyer.
window.permaResetView = function () {
  if (beeMode) { beeSpawn(); updateBeeHud(); return; }
  if (walkMode) { walkSpawn(); return; }
  if (lastBounds) frameCamera(lastBounds);
};

