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
// ── Solid things, for the animals too (V2.46) ────────────────────────────────
//
// Author's report: *"The guy doesn't go through trees or buildings now but the
// creatures still do."* Exactly right — `walkObstacles` was built for the
// walker, built ONLY while walking, and never consulted by `animateWildlife`,
// so every bird crossed the yard straight through the house.
//
// Two things a flying animal needs that a walker does not:
//
//   · **A height.** A bird flying over the roof is not colliding with it, and a
//     bee at 3 m clears the fence. A walker is always at ground level, so
//     `walkObstacles` never needed one; a critter list without one would bounce
//     swifts off buildings they are legitimately above.
//   · **An exemption for the thing it is heading for.** A chickadee's whole
//     route is *perch in that tree*. Blanket collision would push it out of
//     every tree it was sent to and leave it circling the trunk forever, which
//     is a worse bug than the one being fixed.
//
// Trees block at the TRUNK, not the canopy — a bird lands in foliage, it does
// not bounce off it — which is the same call `buildWalkObstacles` makes and for
// the same reason.
let critterObstacles = [];              // {x, z, r, top}

function buildCritterObstacles() {
  critterObstacles = [];
  const sc = lastSceneObj;
  if (!sc) return;
  for (const p of sc.plants || []) {
    const h = p.height_m || 0;
    if (p.plant_type === 'tree') critterObstacles.push({ x: p.x, z: -p.y, r: 0.32, top: Math.max(1, h) });
    else if (p.plant_type === 'shrub' && h > 1.2) critterObstacles.push({ x: p.x, z: -p.y, r: 0.3, top: h });
  }
  for (const b of sc.buildings || []) {
    const ring = b.ring || [];
    if (ring.length < 3) continue;
    let cx = 0, cy = 0;
    for (const pt of ring) { cx += pt[0]; cy += pt[1]; }
    cx /= ring.length; cy /= ring.length;
    let r = 0;
    for (const pt of ring) r = Math.max(r, Math.hypot(pt[0] - cx, pt[1] - cy));
    // The full footprint, not a trunk: nothing flies through a house.
    critterObstacles.push({ x: cx, z: -cy, r: r * 0.9, top: (b.height_m || 4) });
  }
}

// Push a flying/walking animal out of anything solid it has entered, in place
// on `pos`. `target` is where it is trying to get to; obstacles that overlap
// the target are skipped, because that is the plant it was sent to.
function resolveCritterCollision(pos, radius, target) {
  if (!critterObstacles.length) return;
  const rad = radius || 0.05;
  for (let pass = 0; pass < 2; pass++) {
    for (const o of critterObstacles) {
      if (pos.y > o.top) continue;                 // clearing it from above
      if (target) {
        const tx = target.x - o.x, tz = target.z - o.z;
        // Its destination is inside/against this obstacle → it belongs there.
        if (tx * tx + tz * tz < (o.r + 0.7) * (o.r + 0.7)) continue;
      }
      const dx = pos.x - o.x, dz = pos.z - o.z;
      const rr = o.r + rad;
      const d2 = dx * dx + dz * dz;
      if (d2 < rr * rr) {
        const d = Math.sqrt(d2) || 1e-4;
        pos.x = o.x + (dx / d) * rr;
        pos.z = o.z + (dz / d) * rr;
      }
    }
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

// The walker's BODY and his net are built in 20-walker.js (split out at
// V2.46b when this file hit its ceiling). The line the split follows: this
// file is how walk mode BEHAVES — state, input, the step, the camera; that
// one is what the person and his kit are MADE OF. Nothing there is called
// from the animation loop, which is the property that matters after the
// 19-roster.js regression — see _loopFault below.

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
    + 'right-drag to look around · <b>left-click a plant</b> to learn about it · '
    + 'the creatures are the wildlife your plants support'
    // V2.46: the net is held, and it has a reach. Say so here, because
    // "I clicked the butterfly and nothing happened" is otherwise the
    // first thing that happens.
    + (window.__permaEditVerb === 'net'
       ? ' · 🥅 <b>net out</b> — walk within arm\'s reach of a creature, '
         + 'then left-click it'
       : '');
}

function enterWalkMode() {
  controls.enabled = false;
  if (!walkAvatar) { walkAvatar = makeWalker(); scene.add(walkAvatar); }
  walkAvatar.visible = true;
  // The walker is built lazily, so the Net verb may already have been on
  // before he existed (V2.46). Re-read it rather than trusting a setter that
  // ran against nothing.
  setWalkerNet(window.__permaEditVerb === 'net');
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
  // The net arm carries the swing on top of the walk cycle (V2.46).
  if (walkAvatar.userData.netArm && walkAvatar.userData.netSwing) {
    walkAvatar.userData.netArm.rotation.x += walkAvatar.userData.netSwing;
  }

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
  // RIGHT button, since V2.45 — the camera verb is the right button
  // everywhere (01-core.js), and the left button is reserved for actions.
  // Looking around while walking is a camera move, and it used to be on the
  // left, which meant every attempt to plant something also swung your head.
  if (e.button !== 2) return;
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
// ── camera presets (V2.33, F69) ─────────────────────────────────────────────
// The docent's beats have carried a `camera` field since V2.13 and nothing has
// ever read it. These are the four it names, plus the one the roadmap calls
// F77 — the neighbour's-eye view, which is the honest test of whether a design
// survives socially and costs nothing once presets exist at all (P13).
// eye = at head height on the ground; otherwise a point at [x, y, z] scaled off
// the design's own size, so a preset frames a 6 m bed and a 40 m lot alike.
const _CAMERA_PRESETS = {
  overview:  { pos: (g) => [g.cx + g.r * 0.9, g.r * 0.85, g.cz + g.r * 1.1],
               look: (g) => [g.cx, 0, g.cz] },
  // Three-quarter, lower and closer than the overview: the designer's angle.
  orbit:     { pos: (g) => [g.cx + g.r * 0.78, g.r * 0.44, g.cz + g.r * 0.78],
               look: (g) => [g.cx, 0, g.cz] },
  // Inside the planting, at eye height, looking across it.
  walk:      { eye: (g) => [g.cx - g.w * 0.18, 1.6, g.cz + g.d * 0.22],
               look: (g) => [g.cx, 1.4, g.cz] },
  // F77 — the neighbour's-eye view: standing on the frontage at eye height,
  // looking in. Not the designer's orbit but the view that actually decides
  // whether this planting gets a complaint or a question about where to buy the
  // seeds. The south edge, because that is the street side of a north-facing
  // prairie lot far more often than not.
  sidewalk:  { eye: (g) => [g.cx, 1.65, -(g.b.min_y) + Math.max(4, g.d * 0.28)],
               look: (g) => [g.cx, 1.5, g.cz] },
};

window.permaSetCameraPreset = function (name) {
  const b = lastBounds;
  const P = _CAMERA_PRESETS[name] || _CAMERA_PRESETS.overview;
  if (!b) return;
  const w = b.max_x - b.min_x, d = b.max_y - b.min_y;
  const g = { b, w, d, r: Math.max(w, d) * 0.75,
              cx: (b.min_x + b.max_x) / 2, cz: -(b.min_y + b.max_y) / 2 };
  const p = P.eye ? P.eye(g) : P.pos(g);
  // An eye-height preset sits on the terrain rather than at an absolute height.
  camera.position.set(p[0], P.eye ? groundAt(p[0], p[2]) + p[1] : p[1], p[2]);
  const t = P.look(g);
  controls.target.set(t[0], t[1], t[2]);
  controls.update();
};

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
  // V2.45b: 60 fps whenever there is WILDLIFE to watch, not just in the
  // first-person modes. The 30 fps cap was set before anything in the
  // scene beat its wings, and at 30 fps a wingbeat cannot be shown at
  // all — six frames per cycle is roughly where repeating motion starts
  // reading as motion, which at 30 fps caps out at 5 Hz, below almost
  // every bird here. See src/flight_model.VISIBLE_HZ.
  const watching = wildlifeGroup && wildlifeGroup.visible;
  const frameMs = (beeMode || walkMode || cinematic || watching)
    ? 1000 / 60 : _FRAME_MS;
  if (document.hidden || (t - _lastFrame) < frameMs) return;
  _lastFrame = t;
  // EVERY step below is inside the try, and `renderer.render` is outside it.
  // See _loopFault: a throw in here used to end the viewer permanently.
  try {
    windUniforms.uTime.value = clock.getElapsedTime();
    if (beeMode) beeStep(t);
    else if (walkMode) walkStep(t);
    else { if (cinematic) cineStep(t); controls.update(); }   // dolly, then auto-orbit
    animateWildlife(t);             // ambient life (no-op when the group is hidden)
    // "Show its plants" tour (orbit/walk overlay). `typeof`-guarded because
    // stepSpotlight lives in 19-roster.js, which loads AFTER this chunk —
    // see the note on _loopFault, and tests/test_creature_scale.py
    // TestTheRenderLoopSurvivesItself, which checks this rule mechanically.
    if (!beeMode && typeof stepSpotlight === 'function') stepSpotlight(t);
    // 10-inspect.js loads after this chunk, and the loop is already running by
    // then — same forward-reference hazard as wildlifeGroup in 01-core.js.
    if (typeof stepThreads === 'function') stepThreads(t);   // food-web threads
    // V2.44 edit animations. Same `typeof` guard and same reason: 17-anim.js
    // loads after this chunk and the loop is already running by then. These
    // tweens own the bridge callback that performs the edit, so a frame that
    // skipped them would drop the user's action, not just its animation.
    if (typeof stepTweens === 'function') stepTweens(t);
    updatePrecip(t);                // falling snow in winter (no-op otherwise)
  } catch (err) {
    _loopFault(err);
  }
  renderer.render(scene, camera);
});

// ── Why the loop is wrapped (V2.46b) ────────────────────────────────────────
//
// A single throw inside the animation callback used to kill the viewer stone
// dead — not for one frame, forever. three.js's WebGLAnimation is:
//
//     function onAnimationFrame(time, frame) {
//       animationLoop(time, frame);
//       context.requestAnimationFrame(onAnimationFrame);   // ← AFTER the call
//     }
//
// so the re-schedule never happens if the callback throws. You get exactly one
// cleared frame and then nothing, which on screen is a **blank sky-coloured
// window with a perfectly correct HUD sitting on top of it** — because the HUD
// is DOM and was written before the loop ever ran. It reads like "the scene
// failed to build", which is the opposite of what happened.
//
// That is precisely how it shipped in V2.46: splitting 19-roster.js out of
// 07-wildlife.js moved `stepSpotlight` from a chunk that loads BEFORE this one
// to a chunk that loads after, and the unguarded call threw `ReferenceError`
// on the first frame. The `typeof` guard above is the specific fix; this
// wrapper is the general one, because the cost of the failure mode is wildly
// out of proportion to the mistake that causes it.
//
// `renderer.render` stays OUTSIDE the try on purpose: if a step function is
// broken, the right outcome is a scene that still draws (frozen, but visible
// and inspectable), not a black window.
let _loopFaults = 0;
function _loopFault(err) {
  _loopFaults += 1;
  // Report the first few and then go quiet — a per-frame fault would otherwise
  // produce sixty console lines a second and bury its own first occurrence.
  if (_loopFaults <= 3) {
    console.error('scene3d: animation step failed —', err);
    window._pinglog && window._pinglog('animation step failed: ' + err);
  }
}

// How many frames have faulted, for a person asking "is the viewer actually
// running?". Zero is the healthy answer.
window.permaLoopFaults = function () { return _loopFaults; };

// ── Scale rule (V2.35) ──────────────────────────────────────────────────────
// A 10 cm / 1 m rule standing at the origin, for the flower-tuning bench.
//
// "Is that bloom really 7 cm across?" is the question the whole floral-morphology
// pass turns on, and until now the only way to answer it was to believe the
// number. A render with nothing of known size in it gives the eye no purchase:
// every plant looks plausible next to every other plant, because they are all
// scaled by the same wrong factor if the factor is wrong. One object of known
// height fixes that, and it is why field botanists put a ruler in the photo.
//
// Alternating 10 cm bands to 1 m, planted at the design origin. Deliberately
// NOT part of the scene contract — it is a measuring instrument, not something
// the design contains, and it must never appear in a presentation still.
let scaleRule = null;

window.permaSetScaleRule = function (on) {
  if (!scene) return;
  if (scaleRule) { scene.remove(scaleRule); scaleRule = null; }
  if (!on) return;
  scaleRule = new THREE.Group();
  const light = new THREE.MeshBasicMaterial({ color: 0xf4f4ec });
  const dark = new THREE.MeshBasicMaterial({ color: 0x1d2a1d });
  for (let i = 0; i < 10; i++) {
    const band = new THREE.Mesh(
      new THREE.CylinderGeometry(0.012, 0.012, 0.1, 8), i % 2 ? dark : light);
    band.position.set(0, 0.05 + i * 0.1, 0);
    scaleRule.add(band);
  }
  // A 10 cm disc at the foot, so the horizontal scale reads too — a bloom's
  // diameter is the number being judged, and a vertical rule alone answers
  // only half of it.
  const disc = new THREE.Mesh(new THREE.RingGeometry(0.049, 0.05, 32), light);
  disc.rotation.x = -Math.PI / 2;
  disc.position.y = 0.002;
  scaleRule.add(disc);
  scene.add(scaleRule);
};
