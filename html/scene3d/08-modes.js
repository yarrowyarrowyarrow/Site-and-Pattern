// Part of the Site & Pattern 3D viewer, split out of the former
// single html/scene3d.html <script> (V2.24). Loaded as an ordered
// CLASSIC script by the bootstrap in scene3d.html — it shares the
// global scope with its siblings (THREE/OrbitControls/mergeGeometries
// are globals set by the bootstrap), so load ORDER is dependency
// order. Do not add ES `import`/`export` here.

// ── Third-person "Walk the garden" (V2.12) ───────────────────────────────────
// A walking human avatar with a follow camera, strolling among the wildlife.
// Parallel to bee mode; when off, OrbitControls owns the camera as before.
let walkMode = false;
let walkAvatar = null;
let walkYaw = 0, walkPitch = 0.22;       // camera orbit around the walker
let walkFacing = 0;                       // avatar heading (eased toward motion)
const walkKeys = new Set();
let walkDragging = false, walkLastX = 0, walkLastY = 0;
let walkPrevT = 0, walkStride = 0;
let walkObstacles = [];                    // {x, z, r} trunks/buildings to not walk through
const _WALK_DIST = 6.5;
const _WALKER_R = 0.35;                     // the walker's body radius

// Solid things the walker shouldn't pass through: tree/tall-shrub trunks and
// building footprints (as bounding circles). Rebuilt on scene push while walking
// so it tracks growth/season. You can still stroll *under* a canopy — only the
// trunk blocks — so the garden stays explorable.
function buildWalkObstacles() {
  walkObstacles = [];
  const sc = lastSceneObj;
  if (!sc) return;
  for (const p of sc.plants || []) {
    const h = p.height_m || 0;
    if (p.plant_type === 'tree') walkObstacles.push({ x: p.x, z: -p.y, r: 0.45 });
    else if (p.plant_type === 'shrub' && h > 1.2) walkObstacles.push({ x: p.x, z: -p.y, r: 0.4 });
  }
  for (const b of sc.buildings || []) {
    const ring = b.ring || [];
    if (ring.length < 3) continue;
    let cx = 0, cy = 0;
    for (const pt of ring) { cx += pt[0]; cy += pt[1]; }
    cx /= ring.length; cy /= ring.length;
    let r = 0;
    for (const pt of ring) r = Math.max(r, Math.hypot(pt[0] - cx, pt[1] - cy));
    walkObstacles.push({ x: cx, z: -cy, r: r * 0.9 });
  }
}
// Push a proposed (x,z) out of any obstacle it lands inside (a couple of passes
// so a corner between two trunks still resolves). Returns [x, z].
function resolveWalkCollision(x, z) {
  for (let pass = 0; pass < 2; pass++) {
    for (const o of walkObstacles) {
      const dx = x - o.x, dz = z - o.z;
      const rr = o.r + _WALKER_R;
      const d2 = dx * dx + dz * dz;
      if (d2 < rr * rr) {
        const d = Math.sqrt(d2) || 1e-4;
        x = o.x + (dx / d) * rr;
        z = o.z + (dz / d) * rr;
      }
    }
  }
  return [x, z];
}

function makeWalker() {
  const g = new THREE.Group();
  const skin = _cmat('#c98d63', { flat: true });
  const coat = _cmat('#4f6b8a', { flat: true });
  const legM = _cmat('#3a4653', { flat: true });
  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.26, 0.7, 8), coat);
  torso.position.y = 1.15;
  const hips = new THREE.Mesh(new THREE.SphereGeometry(0.22, 8, 6), legM);
  hips.scale.set(1, 0.6, 0.8); hips.position.y = 0.82;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.17, 10, 8), skin);
  head.position.y = 1.62;
  const hat = new THREE.Mesh(new THREE.CylinderGeometry(0.19, 0.2, 0.12, 10),
                             _cmat('#7a5a3a', { flat: true }));
  hat.position.y = 1.74;
  const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.02, 12),
                              _cmat('#7a5a3a', { flat: true }));
  brim.position.y = 1.69;
  g.add(torso, hips, head, hat, brim);
  const legs = [], arms = [];
  const legGeo = THREE.CapsuleGeometry
    ? new THREE.CapsuleGeometry(0.075, 0.55, 3, 6)
    : new THREE.CylinderGeometry(0.08, 0.06, 0.7, 6);
  const armGeo = new THREE.CylinderGeometry(0.06, 0.05, 0.55, 6);
  for (const s of [-1, 1]) {
    const legPivot = new THREE.Group(); legPivot.position.set(0.1 * s, 0.82, 0);
    const leg = new THREE.Mesh(legGeo, legM); leg.position.y = -0.32;
    legPivot.add(leg); g.add(legPivot); legs.push({ pivot: legPivot, sign: s });
    const armPivot = new THREE.Group(); armPivot.position.set(0.26 * s, 1.42, 0);
    const arm = new THREE.Mesh(armGeo, coat); arm.position.y = -0.28;
    armPivot.add(arm); g.add(armPivot); arms.push({ pivot: armPivot, sign: s });
  }
  g.userData.legs = legs; g.userData.arms = arms;
  return g;
}

function groundAt(x, z) { return terrainHeightAt(x, -z, lastTerrain); }

function walkSpawn() {
  const cx = lastBounds ? (lastBounds.min_x + lastBounds.max_x) / 2 : 0;
  const cz = lastBounds ? -(lastBounds.min_y + lastBounds.max_y) / 2 : 0;
  walkAvatar.position.set(cx, groundAt(cx, cz), cz);
  walkYaw = 0; walkPitch = 0.22; walkFacing = 0;
  walkAvatar.rotation.y = 0;
  walkPrevT = 0;
}

function setWalkHintUI(on) {
  const h = document.getElementById('bee-hint');
  if (!h) return;
  h.style.display = on ? 'block' : 'none';
  if (on) h.innerHTML = '🚶 <b>Walk the garden</b> — WASD / arrows to walk · '
    + 'drag to look around · the creatures are the wildlife your plants support';
}

function enterWalkMode() {
  controls.enabled = false;
  if (!walkAvatar) { walkAvatar = makeWalker(); scene.add(walkAvatar); }
  walkAvatar.visible = true;
  buildWalkObstacles();
  walkSpawn();
  if (wildlifeGroup) wildlifeGroup.visible = true;
  setWalkHintUI(true);
}

function exitWalkMode() {
  walkKeys.clear(); walkDragging = false;
  if (walkAvatar) walkAvatar.visible = false;
  setWalkHintUI(false);
  controls.enabled = true;
  if (lastBounds) frameCamera(lastBounds); else controls.update();
}

function walkStep(t) {
  const dt = walkPrevT ? Math.min(0.05, (t - walkPrevT) / 1000) : 0.016;
  walkPrevT = t;
  // Movement is relative to the camera's horizontal facing (walkYaw).
  const fwd = new THREE.Vector3(Math.sin(walkYaw), 0, -Math.cos(walkYaw));
  const right = new THREE.Vector3(Math.cos(walkYaw), 0, Math.sin(walkYaw));
  const move = new THREE.Vector3();
  if (walkKeys.has('KeyW') || walkKeys.has('ArrowUp'))    move.add(fwd);
  if (walkKeys.has('KeyS') || walkKeys.has('ArrowDown'))  move.addScaledVector(fwd, -1);
  if (walkKeys.has('KeyD') || walkKeys.has('ArrowRight')) move.add(right);
  if (walkKeys.has('KeyA') || walkKeys.has('ArrowLeft'))  move.addScaledVector(right, -1);
  const moving = move.lengthSq() > 0;
  if (moving) {
    move.normalize();
    const speed = (walkKeys.has('ShiftLeft') ? 7 : 3.5);
    walkAvatar.position.addScaledVector(move, speed * dt);
    walkStride += speed * dt * 2.2;
    // Ease the avatar's heading toward its travel direction.
    const target = Math.atan2(move.x, -move.z);
    let d = (target - walkFacing + Math.PI * 3) % (Math.PI * 2) - Math.PI;
    walkFacing += d * Math.min(1, dt * 10);
  }
  // Don't walk through trunks or the house.
  const [rx, rz] = resolveWalkCollision(walkAvatar.position.x, walkAvatar.position.z);
  walkAvatar.position.x = rx; walkAvatar.position.z = rz;
  // Keep bounded to a sensible stage around the design.
  if (lastBounds) {
    const pad = 20;
    walkAvatar.position.x = Math.max(lastBounds.min_x - pad,
      Math.min(lastBounds.max_x + pad, walkAvatar.position.x));
    walkAvatar.position.z = Math.max(-(lastBounds.max_y) - pad,
      Math.min(-(lastBounds.min_y) + pad, walkAvatar.position.z));
  }
  walkAvatar.position.y = groundAt(walkAvatar.position.x, walkAvatar.position.z);
  walkAvatar.rotation.y = walkFacing;
  // Swing legs + arms while walking; settle when still.
  const sw = moving ? Math.sin(walkStride) * 0.5 : walkAvatar.userData._sw * 0.9 || 0;
  walkAvatar.userData._sw = sw;
  for (const { pivot, sign } of walkAvatar.userData.legs) pivot.rotation.x = sw * sign;
  for (const { pivot, sign } of walkAvatar.userData.arms) pivot.rotation.x = -sw * sign;

  // Follow camera: orbit behind the walker at (walkYaw, walkPitch).
  const head = walkAvatar.position.clone().add(new THREE.Vector3(0, 1.5, 0));
  const cp = Math.cos(walkPitch);
  const cam = new THREE.Vector3(-Math.sin(walkYaw) * cp, Math.sin(walkPitch), Math.cos(walkYaw) * cp);
  const desired = head.clone().addScaledVector(cam, _WALK_DIST);
  const gy = groundAt(desired.x, desired.z) + 0.4;
  if (desired.y < gy) desired.y = gy;          // don't clip through terrain
  camera.position.lerp(desired, Math.min(1, dt * 8));
  camera.lookAt(head);
}

addEventListener('keydown', (e) => {
  if (!walkMode) return;
  if (_BEE_MOVE_CODES.has(e.code) || e.code === 'ShiftLeft') {
    walkKeys.add(e.code); e.preventDefault();
  }
});
addEventListener('keyup', (e) => { walkKeys.delete(e.code); });
renderer.domElement.addEventListener('pointerdown', (e) => {
  if (!walkMode) return;
  walkDragging = true; walkLastX = e.clientX; walkLastY = e.clientY;
});
addEventListener('pointerup', () => { walkDragging = false; });
renderer.domElement.addEventListener('pointermove', (e) => {
  if (!walkMode || !walkDragging) return;
  walkYaw -= (e.clientX - walkLastX) * 0.005;
  walkPitch = Math.max(-0.2, Math.min(1.2, walkPitch + (e.clientY - walkLastY) * 0.004));
  walkLastX = e.clientX; walkLastY = e.clientY;
});

window.permaSetWalkMode = function (on) {
  const want = !!on;
  if (want === walkMode) return;
  walkMode = want;
  if (walkMode) enterWalkMode(); else exitWalkMode();
};

// ── Cinematic flyover (V2.13) ────────────────────────────────────────────────
// A hands-free "watch the lawn become habitat" tour: a slow auto-orbit with a
// gentle breathing dolly, letterbox bars and a lower-third caption, while the
// host advances the growth year / season / time of day underneath it. Orbit
// input is frozen; toggling off restores the free camera.
let cinematic = false;
let _cineBaseR = 0, _cinePrevAuto = false;
function setCinematicCaption(big, sub) {
  const cap = document.getElementById('cine-cap');
  if (!cap) return;
  cap.querySelector('.big').textContent = big || '';
  cap.querySelector('.sub').textContent = sub || '';
  cap.style.display = (big || sub) ? 'block' : 'none';
}
window.permaSetCinematic = function (on) {
  const want = !!on;
  if (want === cinematic) return;
  cinematic = want;
  document.body.classList.toggle('cinematic', cinematic);
  const tip = document.getElementById('plant-tip'); if (tip) tip.style.display = 'none';
  if (cinematic) {
    if (lastBounds) frameCamera(lastBounds);
    _cineBaseR = camera.position.distanceTo(controls.target);
    _cinePrevAuto = controls.autoRotate;
    controls.autoRotate = true; controls.autoRotateSpeed = 0.5;
    controls.enableRotate = false; controls.enablePan = false;
  } else {
    controls.autoRotate = _cinePrevAuto;
    controls.enableRotate = true; controls.enablePan = true;
    setCinematicCaption('', '');
    if (lastBounds) frameCamera(lastBounds);
  }
};
// The host sets the lower-third caption for the current beat ("Year 5", "October").
window.permaSetCinematicCaption = function (big, sub) {
  if (cinematic) setCinematicCaption(big, sub);
};
// A slow breathing dolly layered on the auto-orbit — pushes in/out and rises a
// touch, so the shot never feels like a rigid turntable.
function cineStep(t) {
  const breath = 1 + 0.08 * Math.sin(t * 0.00035);
  const dir = new THREE.Vector3().subVectors(camera.position, controls.target);
  dir.y = 0; const flat = dir.length() || 1;
  const wantFlat = _cineBaseR * 0.92 * breath;
  dir.multiplyScalar(wantFlat / flat);
  camera.position.x = controls.target.x + dir.x;
  camera.position.z = controls.target.z + dir.z;
  camera.position.y = controls.target.y + _cineBaseR * (0.55 + 0.08 * Math.sin(t * 0.0003 + 1.6));
}

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

// Cap rendering at ~30 fps and skip entirely while the tab/window is hidden, so
// the always-on wind sway doesn't peg a weak GPU or drain a laptop battery.
// The bee fly-through runs at ~60 fps — first-person flight feels choppy at 30.
let _lastFrame = 0;
const _FRAME_MS = 1000 / 30;
renderer.setAnimationLoop((t) => {
  const frameMs = (beeMode || walkMode || cinematic) ? 1000 / 60 : _FRAME_MS;
  if (document.hidden || (t - _lastFrame) < frameMs) return;
  _lastFrame = t;
  windUniforms.uTime.value = clock.getElapsedTime();
  if (beeMode) beeStep(t);
  else if (walkMode) walkStep(t);
  else { if (cinematic) cineStep(t); controls.update(); }   // dolly, then auto-orbit
  animateWildlife(t);               // ambient life (no-op when the group is hidden)
  if (!beeMode) stepSpotlight(t);   // "show its plants" tour (orbit/walk overlay)
  renderer.render(scene, camera);
});
