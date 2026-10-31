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

// Where a click meets the ground. Until V3.04 this was a horizontal plane at
// height 0, on the reasoning that the plant is placed by lat/lng and only its
// position in PLAN rides on the hit. True, but the terrain's heights are metres
// above the site's LOWEST point, so on a slope the plane lay under nearly all of
// the yard and a click on the uphill side planted metres beyond the spot under
// the cursor: 3 m of rise seen 30 degrees down is 5 m out. So the ray is walked
// from the camera against terrainHeightAt, the height every plant stands on, and
// the crossing refined by halving. The flat plane is still the answer with no
// terrain, and the walk is bounded by the plane through the highest ground.
let _hiKey = null, _hiM = 0;
function groundPointAt(clientX, clientY) {
  const rect = renderer.domElement.getBoundingClientRect();
  _editPtr.x = ((clientX - rect.left) / rect.width) * 2 - 1;
  _editPtr.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  _editRay.setFromCamera(_editPtr, camera);
  const ray = _editRay.ray, t = lastTerrain;
  if (!t || t.rows < 2 || t.cols < 2) {
    if (!ray.intersectPlane(_GROUND, _hitPoint)) return null;
    return { x: _hitPoint.x, y: -_hitPoint.z, h: 0 };
  }
  if (_hiKey !== t) { _hiKey = t; _hiM = Math.max(...t.heights.map(r => Math.max(...r))); }
  const o = ray.origin, dy = ray.direction.y;
  if (o.y > _hiM && dy >= 0) return null;               // above every hill, looking up
  const over = (s) => { ray.at(s, _hitPoint);
    return _hitPoint.y - terrainHeightAt(_hitPoint.x, -_hitPoint.z, t); };
  const s0 = (o.y > _hiM && dy < 0) ? (o.y - _hiM) / -dy : 0;
  const s1 = dy < 0 ? o.y / -dy : 3000;                  // y = 0 is the lowest ground
  const step = Math.max(0.25, (s1 - s0) / 600);
  let a = s0, b = -1;
  for (let s = s0; s <= s1 + step; s += step) {
    if (over(s) <= 0) { b = s; break; }
    a = s;
  }
  if (b < 0) return null;
  for (let i = 0; i < 30; i++) { const m = (a + b) / 2; if (over(m) > 0) a = m; else b = m; }
  ray.at(b, _hitPoint);
  return { x: _hitPoint.x, y: -_hitPoint.z,
           h: terrainHeightAt(_hitPoint.x, -_hitPoint.z, t) };
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
  g.position.set(pt.x, (pt.h || 0) + 0.02, -pt.y);
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
  // No ground ghost for the net — you are aiming at a creature, not a spot,
  // and in walk mode the net in his hand is the pointer (V2.46).
  if (_editMode === 'net') { hideGhost(); return; }
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
  // The net gets a looser gesture than the trowel (V2.46d). Planting is a
  // precise act on a static point, so 4 px and 700 ms are right for it. Swinging
  // a net is not: you are lining up on a moving animal, the aim takes as long as
  // it takes, and the hand drifts. A deliberate click that took a second used to
  // be discarded in silence — which looks exactly like "the net doesn't work".
  const netting = _editMode === 'net';
  const slop = netting ? 12 : 4;
  const hold = netting ? 2500 : 700;
  if (Math.abs(e.clientX - _eDownX) > slop || Math.abs(e.clientY - _eDownY) > slop) return;
  if (performance.now() - _eDownT > hold) return;

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
    // V2.46c — YOU SWING THE NET, you do not click the animal.
    //
    // V2.46 required a raycast hit on the creature, which meant landing the
    // cursor on a 34 mm object crossing the yard at a metre a second:
    //
    //     *"Catching the bugs is impossible with the way it is set up… If I am
    //     within range of a bug and click while holding the net, not clicking
    //     on the bug because it is tiny and too kind of too fast moving."*
    //
    // So in walk mode with the net out, the click means "swing", and what it
    // catches is whatever is in arm's reach — which is what a net does, and why
    // people can catch insects they could never touch. `critterInReach` is
    // also what the on-screen ring has been following, so the thing you get is
    // the thing that was highlighted before you clicked.
    // `netTarget()`, not `critterInReach()` — the ring latches its creature and
    // the click takes THAT one. Two independent proximity queries a few hundred
    // milliseconds apart is a race against a moving animal, and losing it is
    // what *"the circle shows up and I click to swing but I don't catch
    // anything"* looked like.
    let critter = (typeof walkerHasNet === 'function' && walkerHasNet()
                   && typeof netTarget === 'function')
      ? netTarget() : null;
    // Out of walk mode there is no arm and no reach: the god's-eye view keeps
    // the old aim-and-click, which is fine on a creature you can see from above.
    const aimed = !critter && typeof critterObjectAt === 'function'
      ? critterObjectAt(e.clientX, e.clientY) : null;
    if (!critter && aimed) {
      const ai = aimed.userData && aimed.userData.critterInfo;
      // With the net in hand, an aimed click at something out of reach is a
      // MISS and has to say so — a click that silently does nothing reads as a
      // broken button, which is half of "impossible".
      if (typeof walkerHasNet === 'function' && walkerHasNet()) {
        if (ai && ai.name) _bridge.outOfReach && _bridge.outOfReach(String(ai.name));
        return;
      }
      critter = aimed;
    }
    const info = critter && critter.userData && critter.userData.critterInfo;
    if (!critter || !info || !info.name) {
      // Nothing in reach and nothing aimed at. Say that too, rather than
      // leaving the user to wonder whether the button works.
      if (typeof walkerHasNet === 'function' && walkerHasNet()) {
        _bridge.outOfReach && _bridge.outOfReach('');
      }
      return;
    }
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
// The verb itself, not just "is one on" — 08-modes.js reads it when the walker
// is built, because the walker is created lazily on entering walk mode and can
// therefore be born after the Net button was already pressed (V2.46).
window.__permaEditVerb = '';

const _MODES = ['plant', 'pull', 'net'];

window.permaSetEditMode = function (mode, pick) {
  _editMode = _MODES.indexOf(mode) >= 0 ? mode : '';
  _editPick = pick || null;
  window.__permaEditMode = !!_editMode;
  window.__permaEditVerb = _editMode;
  if (!_editMode) hideGhost();
  // Put the net in (or take it out of) the walker's hand (V2.46, 08-modes.js).
  if (typeof setWalkerNet === 'function') setWalkerNet(_editMode === 'net');
  // …and refresh the walk hint, which now names the net's reach.
  if (typeof walkMode !== 'undefined' && walkMode
      && typeof setWalkHintUI === 'function') setWalkHintUI(true);
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
