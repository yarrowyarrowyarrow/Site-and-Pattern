// 17-anim.js — planting, pulling and catching, as things that happen (V2.44).
//
// Design principle P5 (perception is constructed — make the invisible visible)
// and P13 (a native planting has to be loved to survive) — see
// docs/DESIGN_PHILOSOPHY.md.
//
// V2.43 made the wild communities editable and every edit was instantaneous: a
// plant blinked into existence, another blinked out, and a creature you clicked
// simply produced a card. The author's report: *"I'd like the animations for
// planting a tree/plant, removing one, catching a critter."*
//
// ── The ordering problem, which is the whole design ──────────────────────────
//
// Every edit ends in a FULL scene rebuild (reference_ecosystem_window._render →
// build_scene → permaSetScene → disposeDesignGroup), because the project dict
// has one definition of how it becomes geometry and a viewer that patched
// itself incrementally would be a second one that drifts.
//
// A rebuild destroys every object in the design group. So an animation started
// before it is wiped mid-flight.
//
// The fix is ordering, not architecture: **animate first, tell Python after.**
// Each function here takes a `done` callback, and 16-editing.js passes the
// bridge call as that callback. The rebuild therefore happens when the
// animation lands, and it lands on a scene that already looks like the result —
// the pulled plant has already shrunk to nothing, so the rebuild without it is
// seamless.
//
// That also means these are the only animations in the viewer that may not be
// skipped: dropping one would drop the edit with it. Every path calls `done`.

// ── The tween registry ───────────────────────────────────────────────────────
// The viewer had no general tween mechanism — the render loop in 08-modes.js
// calls a fixed set of step functions. This is the smallest thing that is
// still one mechanism rather than three ad-hoc timers.

const _tweens = [];

function addTween(ms, step, done) {
  _tweens.push({ t0: performance.now(), ms: Math.max(1, ms), step, done });
}

// Called from the render loop. Guarded there with `typeof`, because that loop
// is already running by the time this chunk loads — the same forward-reference
// hazard 10-inspect.js's stepThreads has.
function stepTweens(now) {
  for (let i = _tweens.length - 1; i >= 0; i--) {
    const tw = _tweens[i];
    const k = Math.min(1, (now - tw.t0) / tw.ms);
    try { tw.step(k); } catch (e) { /* a broken frame must not strand `done` */ }
    if (k >= 1) {
      _tweens.splice(i, 1);
      if (tw.done) { try { tw.done(); } catch (e) { /* ignore */ } }
    }
  }
}

// Easings. `outBack` overshoots slightly, which is what makes a plant read as
// *placed* rather than faded in.
function _outCubic(k) { return 1 - Math.pow(1 - k, 3); }
function _outBack(k) {
  const c = 1.70158, c3 = c + 1;
  return 1 + c3 * Math.pow(k - 1, 3) + c * Math.pow(k - 1, 2);
}

const ANIM_PLANT_MS = 520;
const ANIM_PULL_MS = 420;
const ANIM_CATCH_MS = 460;

// ── Planting ─────────────────────────────────────────────────────────────────

// A ring of soil kicked up at the point, and a green shoot springing out of it.
// Deliberately generic: the real plant arrives on the rebuild a half-second
// later, and since V2.44 it arrives NURSERY-SIZED — a whip, not a mature tree —
// so the shoot is a plausible stand-in rather than a promise the rebuild breaks.
function animatePlant(x, y, done) {
  const group = new THREE.Group();
  group.position.set(x, 0, -y);

  const soil = new THREE.Mesh(
    new THREE.RingGeometry(0.12, 0.30, 20).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: 0x6b4f2a, transparent: true,
                                  opacity: 0.9, side: THREE.DoubleSide,
                                  depthTest: false }));
  soil.position.y = 0.02;
  group.add(soil);

  const shoot = new THREE.Mesh(
    new THREE.ConeGeometry(0.10, 0.55, 6),
    new THREE.MeshBasicMaterial({ color: 0x7cb342, transparent: true,
                                  opacity: 0.95, depthTest: false }));
  shoot.position.y = 0.275;
  group.add(shoot);

  group.renderOrder = 998;
  scene.add(group);

  addTween(ANIM_PLANT_MS, (k) => {
    const s = _outBack(k);
    shoot.scale.set(1, Math.max(0.01, s), 1);
    shoot.position.y = 0.275 * Math.max(0.01, s);
    // The soil ring expands and fades — the puff of a trowel coming out.
    const e = _outCubic(k);
    soil.scale.setScalar(1 + e * 1.6);
    soil.material.opacity = 0.9 * (1 - e);
    shoot.material.opacity = 0.95 * (1 - Math.max(0, k - 0.75) * 4);
  }, () => {
    scene.remove(group);
    soil.geometry.dispose(); soil.material.dispose();
    shoot.geometry.dispose(); shoot.material.dispose();
    if (done) done();
  });
}

// ── Pulling ──────────────────────────────────────────────────────────────────

// Plants live in InstancedMeshes, so one plant is one instance matrix among
// hundreds. Animating it means writing that single matrix per frame and setting
// `instanceMatrix.needsUpdate` — its neighbours are untouched, which is why
// this works at all without a rebuild.
const _pullM = new THREE.Matrix4();
const _pullPos = new THREE.Vector3();
const _pullQuat = new THREE.Quaternion();
const _pullScale = new THREE.Vector3();
const _pullTilt = new THREE.Quaternion();
const _pullAxis = new THREE.Vector3(1, 0, 0);

// Find the instance under the cursor, keeping the instanceId that `scenePick`
// throws away — it returns the plant *id*, which several instances share, and
// pulling has to move exactly the one that was clicked.
function pickInstance(clientX, clientY) {
  if (typeof plantsGroup === 'undefined' || !plantsGroup) return null;
  const rect = renderer.domElement.getBoundingClientRect();
  const ptr = new THREE.Vector2(
    ((clientX - rect.left) / rect.width) * 2 - 1,
    -((clientY - rect.top) / rect.height) * 2 + 1);
  const ray = new THREE.Raycaster();
  ray.setFromCamera(ptr, camera);
  const meshes = [];
  plantsGroup.traverse((o) => {
    if (o.isInstancedMesh && (o.userData.pick || o.userData.pickId)) meshes.push(o);
  });
  if (!meshes.length) return null;
  const hits = ray.intersectObjects(meshes, false);
  for (const h of hits) {
    if (h.instanceId != null) return { mesh: h.object, instanceId: h.instanceId };
  }
  return null;
}

// Tilt, lift and shrink — a plant being lifted out by the root ball rather than
// dissolving. Falls straight through to `done` when there is nothing to
// animate, so a miss still performs the edit.
function animatePull(hit, done) {
  if (!hit || !hit.mesh || hit.instanceId == null) { if (done) done(); return; }
  const { mesh, instanceId } = hit;
  mesh.getMatrixAt(instanceId, _pullM);
  _pullM.decompose(_pullPos, _pullQuat, _pullScale);
  const baseY = _pullPos.y;
  const sx = _pullScale.x, sy = _pullScale.y, sz = _pullScale.z;

  addTween(ANIM_PULL_MS, (k) => {
    const e = _outCubic(k);
    const s = Math.max(0.001, 1 - e);
    _pullTilt.setFromAxisAngle(_pullAxis, e * 0.6);       // lean over
    _pullM.compose(
      _pullPos.setY(baseY + e * 0.35),                     // lifted clear
      _pullQuat.clone().multiply(_pullTilt),
      _pullScale.set(sx * s, sy * s, sz * s));
    mesh.setMatrixAt(instanceId, _pullM);
    mesh.instanceMatrix.needsUpdate = true;
  }, done);
}

// ── Catching ─────────────────────────────────────────────────────────────────

// The net (backlog item D). A hoop sweeps through the creature's position and
// the creature shrinks into it — then its species page opens and the ledger
// records how='caught' rather than 'inspected', which is the distinction that
// makes a collection worth having.
function animateCatch(critter, done) {
  if (!critter) { if (done) done(); return; }

  const hoop = new THREE.Mesh(
    new THREE.TorusGeometry(0.28, 0.02, 8, 24),
    new THREE.MeshBasicMaterial({ color: 0xf4f4ec, transparent: true,
                                  opacity: 0.95, depthTest: false }));
  hoop.renderOrder = 999;
  const start = critter.position.clone();
  // Sweep in from the camera side, so the net arrives from where the user is.
  const from = start.clone().add(
    camera.position.clone().sub(start).normalize().multiplyScalar(1.2));
  hoop.position.copy(from);
  hoop.lookAt(camera.position);
  scene.add(hoop);

  const s0 = critter.scale.clone();

  addTween(ANIM_CATCH_MS, (k) => {
    const e = _outCubic(k);
    hoop.position.lerpVectors(from, start, e);
    hoop.scale.setScalar(1 + e * 0.35);
    hoop.material.opacity = 0.95 * (1 - Math.max(0, k - 0.6) * 2.5);
    // The creature is taken after the hoop reaches it, not before.
    const c = Math.max(0, (k - 0.45) / 0.55);
    critter.scale.set(s0.x * (1 - c), s0.y * (1 - c), s0.z * (1 - c));
  }, () => {
    scene.remove(hoop);
    hoop.geometry.dispose(); hoop.material.dispose();
    // Put the creature back. It was caught, looked at and released — which is
    // both the honest field practice and the only option that does not make a
    // learning tool teach children to remove pollinators from a habitat (P11).
    critter.scale.copy(s0);
    if (done) done();
  });
}

// Resolve the clicked object up to the thing that carries `critterInfo`, which
// is the group the animation has to scale — `_critterAt` in 01-core.js returns
// the info, not the object.
function critterObjectAt(clientX, clientY) {
  if (typeof wildlifeGroup === 'undefined' || !wildlifeGroup) return null;
  if (!wildlifeGroup.visible) return null;
  const rect = renderer.domElement.getBoundingClientRect();
  const ptr = new THREE.Vector2(
    ((clientX - rect.left) / rect.width) * 2 - 1,
    -((clientY - rect.top) / rect.height) * 2 + 1);
  const ray = new THREE.Raycaster();
  ray.setFromCamera(ptr, camera);
  const hits = ray.intersectObject(wildlifeGroup, true);
  for (const h of hits) {
    let o = h.object;
    while (o) {
      if (o.userData && o.userData.critterInfo) return o;
      o = o.parent;
    }
  }
  return null;
}
