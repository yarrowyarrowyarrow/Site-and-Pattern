// 16-editing.js — planting into a wild community, from inside it (V2.43).
//
// Design principle P1, P3, P8 — see docs/DESIGN_PHILOSOPHY.md. The Python side
// is src/reference_edit.py; the window is src/reference_ecosystem_window.py.
//
// The reference landscapes have been walkable since F50 and untouchable with
// it: seven dioramas. This chunk is the click that makes them sandboxes — put
// a plant where you are looking, or pull one out and be told what it cost.
//
// WHAT THIS FILE DOES NOT DO: decide anything. It reports a point in scene
// metres and lets Python place the plant, because the project dict has exactly
// one write path (src/project_store.ProjectStore) and a viewer that edited its
// own copy would be a second one. Geometry in, coordinates out.
//
// ── The channel ──────────────────────────────────────────────────────────────
// The 3D viewer had no Python channel before this. That was a deliberate
// choice, not an oversight: the inspect dossier is *pre-pushed* so a click
// costs no round trip (10-inspect.js). Editing genuinely needs the other
// direction, so this adds a QWebChannel mirroring the proven one in
// src/map_widget.py — and everything else Learn mode wants (the net, the
// discovery ledger, challenge scoring) needs the same channel, so it is worth
// the wire rather than a poll.
//
// It is optional at every step. With no channel — a plain browser, the
// web3d/dist fork build, a screenshot harness — the guards below turn every
// call into a no-op and the viewer behaves exactly as it did before V2.43.

let _editMode = '';          // '' | 'plant' | 'pull'
let _editPick = null;        // {plant_id, common_name} on the trowel
let _bridge = null;
let _ghost = null;

// Scene metres: x east, y north. World: (x, height, -y) — the mapping used by
// every builder since the contract shipped (see buildGround/buildPlants).
// Getting this backwards puts every plant in a mirror image of where it was
// clicked, which looks almost right and is the reason it is written down here.
const _GROUND = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const _hitPoint = new THREE.Vector3();
const _editRay = new THREE.Raycaster();
const _editPtr = new THREE.Vector2();

// Raycast against a mathematical horizontal plane rather than the ground mesh.
// The terrain is a displaced PlaneGeometry that may not exist at all (a scene
// with no DEM gets only the apron), and a click has to land somewhere in every
// case. The height it returns is not used: the plant is placed by lat/lng and
// the next scene build samples the real terrain under it, so the only thing
// riding on this is where in PLAN the plant lands, which the flat plane gets
// right to within the slope error across one plant's width.
function groundPointAt(clientX, clientY) {
  const rect = renderer.domElement.getBoundingClientRect();
  _editPtr.x = ((clientX - rect.left) / rect.width) * 2 - 1;
  _editPtr.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  _editRay.setFromCamera(_editPtr, camera);
  if (!_editRay.ray.intersectPlane(_GROUND, _hitPoint)) return null;
  return { x: _hitPoint.x, y: -_hitPoint.z };
}

// ── The ghost ────────────────────────────────────────────────────────────────
// A translucent marker at the point the plant would go. Without it the user is
// guessing where a click lands in a perspective view, which is exactly the
// thing that makes 3D placement feel unreliable.

function ensureGhost() {
  if (_ghost) return _ghost;
  _ghost = new THREE.Group();
  const ringGeo = new THREE.RingGeometry(0.28, 0.36, 24).rotateX(-Math.PI / 2);
  const ringMat = new THREE.MeshBasicMaterial({
    color: 0x9ccc65, transparent: true, opacity: 0.85,
    depthTest: false, side: THREE.DoubleSide,
  });
  _ghost.add(new THREE.Mesh(ringGeo, ringMat));
  const stemGeo = new THREE.CylinderGeometry(0.03, 0.03, 0.9, 6);
  stemGeo.translate(0, 0.45, 0);
  _ghost.add(new THREE.Mesh(stemGeo, ringMat));
  _ghost.renderOrder = 999;    // never hidden behind the grass it sits in
  _ghost.visible = false;
  scene.add(_ghost);
  return _ghost;
}

function moveGhost(pt, colour) {
  const g = ensureGhost();
  if (!pt) { g.visible = false; return; }
  g.position.set(pt.x, 0.02, -pt.y);
  g.traverse((o) => { if (o.material && o.material.color) o.material.color.setHex(colour); });
  g.visible = true;
}

function hideGhost() { if (_ghost) _ghost.visible = false; }

// ── Input ────────────────────────────────────────────────────────────────────

let _eDownX = 0, _eDownY = 0, _eDownT = 0;
renderer.domElement.addEventListener('pointerdown', (e) => {
  _eDownX = e.clientX; _eDownY = e.clientY; _eDownT = performance.now();
});

renderer.domElement.addEventListener('pointermove', (e) => {
  if (!_editMode) { hideGhost(); return; }
  if (_editMode === 'net') { hideGhost(); return; }   // the cursor IS the net
  if (_editMode === 'pull') {
    // In pull mode the ghost marks what would go, not where something lands.
    const hit = scenePick(e.clientX, e.clientY);
    const pt = (hit && hit.type === 'plant') ? groundPointAt(e.clientX, e.clientY) : null;
    moveGhost(pt, 0xef5350);
    return;
  }
  moveGhost(groundPointAt(e.clientX, e.clientY), 0x9ccc65);
});

renderer.domElement.addEventListener('pointerleave', hideGhost);

renderer.domElement.addEventListener('pointerup', (e) => {
  // Same gesture filter as the inspect card (10-inspect.js): left button, no
  // drag, no long press. Left is the PAN verb since V2.37, so an unfiltered
  // handler would plant a shrub on the tail of every camera move.
  if (e.button !== 0) return;
  if (Math.abs(e.clientX - _eDownX) > 4 || Math.abs(e.clientY - _eDownY) > 4) return;
  if (performance.now() - _eDownT > 700) return;

  // Report what was clicked so the discovery ledger can record it. This runs
  // whether or not editing is on: walking up to a bee and clicking it is the
  // collection loop, and it should work in a landscape you are only looking at.
  const hit = scenePick(e.clientX, e.clientY);
  if (_bridge && hit) {
    if (hit.type === 'fauna') _bridge.inspected('fauna', String(hit.key || ''));
    else if (hit.key != null) _bridge.inspected('plant', String(hit.key));
  }

  if (!_editMode || !_bridge) return;

  // V2.44 — every verb below ANIMATES FIRST and calls the bridge as the
  // animation's completion callback. Python rebuilds the whole scene on each
  // edit, which would wipe an animation already in flight, so the ordering is
  // the mechanism (see 17-anim.js). Every branch must reach its bridge call on
  // every path, or the edit is silently dropped.

  if (_editMode === 'net') {
    const critter = (typeof critterObjectAt === 'function')
      ? critterObjectAt(e.clientX, e.clientY) : null;
    const info = critter && critter.userData && critter.userData.critterInfo;
    if (!critter || !info || !info.name) return;
    const send = () => _bridge.caught(String(info.name));
    if (typeof animateCatch === 'function') animateCatch(critter, send);
    else send();
    return;
  }

  if (_editMode === 'pull') {
    if (!hit || hit.type !== 'plant') return;
    const pt = groundPointAt(e.clientX, e.clientY);
    if (!pt) return;
    const send = () => _bridge.pullAt(pt.x, pt.y);
    // Animate the exact instance under the cursor. scenePick returns the plant
    // *id*, which several instances share; pickInstance keeps the instanceId.
    const inst = (typeof pickInstance === 'function')
      ? pickInstance(e.clientX, e.clientY) : null;
    if (inst && typeof animatePull === 'function') animatePull(inst, send);
    else send();
    return;
  }

  const pt = groundPointAt(e.clientX, e.clientY);
  if (!pt || !_editPick) return;
  const pid = Number(_editPick.plant_id) || 0;
  const name = String(_editPick.common_name || '');
  const send = () => _bridge.plantAt(pt.x, pt.y, pid, name);
  if (typeof animatePlant === 'function') animatePlant(pt.x, pt.y, send);
  else send();
});

// ── Hooks Python drives ──────────────────────────────────────────────────────

// window.__permaEditMode is read by 10-inspect.js's click handler so that a
// click meant to pull a plant does not also open its card. It is a global
// rather than a call because that handler registered first and cannot be
// intercepted from here.
window.__permaEditMode = false;

const _MODES = ['plant', 'pull', 'net'];

window.permaSetEditMode = function (mode, pick) {
  _editMode = _MODES.indexOf(mode) >= 0 ? mode : '';
  _editPick = pick || null;
  window.__permaEditMode = !!_editMode;
  if (!_editMode) hideGhost();
};

window.permaEditReady = function () { return !!_bridge; };

// ── The channel ──────────────────────────────────────────────────────────────

(function connectBridge() {
  if (typeof QWebChannel === 'undefined' || !window.qt || !window.qt.webChannelTransport) {
    // No Qt on the other side. Everything above degrades to a no-op.
    return;
  }
  try {
    new QWebChannel(window.qt.webChannelTransport, function (channel) {
      _bridge = channel.objects && channel.objects.bridge;
      window._pinglog && window._pinglog('edit bridge ready');
    });
  } catch (err) {
    window._pinglog && window._pinglog('edit bridge failed: ' + err);
  }
})();
