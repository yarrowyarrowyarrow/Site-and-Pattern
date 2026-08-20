// Part of the Site & Pattern 3D viewer. Loaded as an ordered CLASSIC
// script by the bootstrap in scene3d.html — it shares the global scope
// with its siblings, so load ORDER is dependency order. Do not add ES
// `import`/`export` here.

// ── The person in the scene, and what he is carrying (V2.46b split) ─────────
//
// Split out of 08-modes.js when that file reached its 600-line ceiling — the
// held net (V2.46) was the growth that did it. The line the split follows:
// **08 is how walk mode behaves** (state, keys, the per-frame step, the follow
// camera); **this file is what the walker and his kit are made of**.
//
// `walkAvatar`, `walkMode`, `_cmat` and `terrainHeightAt` are declared in
// earlier chunks and shared through the classic-script global scope.
//
// LOAD-ORDER NOTE, and it is the whole reason this seam was chosen over the
// obvious one: **nothing in here is called from the animation loop.**
// `makeWalker` runs from `enterWalkMode`, the net helpers from 16-editing.js
// and 17-anim.js at click time — all long after every chunk has loaded. Moving
// `walkStep` here instead would have put a loop callee in a chunk that loads
// after the loop is registered, which is exactly the mistake that blanked the
// viewer in V2.46 (see `_loopFault` in 08-modes.js, and
// tests/test_creature_scale.TestTheRenderLoopSurvivesItself).

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
  // The net goes in his right hand (V2.46) — see makeNet. Hidden until the Net
  // verb is on, so he is not permanently carrying one.
  const rightArm = arms.find((a) => a.sign === 1);
  if (rightArm) {
    const net = makeNet();
    net.visible = false;
    rightArm.pivot.add(net);
    g.userData.net = net;
    g.userData.netArm = rightArm.pivot;
    g.userData.netSwing = 0;
  }
  return g;
}

// ── The net, held (V2.46) ────────────────────────────────────────────────────
//
// Author: *"I want to be able to … catch a bug in a net the guy holds, to make
// it more like a game."* Until now the net was a hoop that flew in from the
// camera on a click — a cursor effect, not a tool anybody was carrying.
//
// Built in the ARM PIVOT's frame so it swings with him for free: the walk cycle
// already rotates that pivot, so a walking figure carries the net properly with
// no extra code, and the catch is one more rotation on the same joint.
//
// Sized to a real aerial net — a 38 cm hoop on a metre of handle. That number
// now MEANS something: since the creatures are drawn life size, an 8 cm
// swallowtail is genuinely a fifth of the hoop it goes into.
const NET_HOOP_R = 0.21;

// A real aerial net (V2.46d). The first cut was a torus, a straight cone and a
// stick — *"I also wonder if you can make the net look a little more
// realistic."* The shape that reads as a butterfly net is the BAG: wide at the
// mouth, narrowing through a belly, and closed with a soft round bottom. A
// straight cone reads as a paper funnel, which is what it was.
//
// Built with a lathe so the profile is a curve rather than a bevel, plus a
// ferrule where the hoop meets the handle — a small joint is most of what makes
// a tool look like a tool rather than two primitives sharing a coordinate.
function makeNet() {
  const net = new THREE.Group();
  const wood = _cmat('#a1794c', { flat: true });
  const grip = _cmat('#3f4a52', { flat: true });
  const rim = new THREE.MeshStandardMaterial({ color: 0xd8dee2, roughness: 0.45,
                                               metalness: 0.55, flatShading: true });
  // Two-sided and thin: you should see the far wall of the bag through the near
  // one, which is the single strongest "this is gauze" cue.
  const gauze = new THREE.MeshStandardMaterial({
    color: 0xf4f8f0, roughness: 0.95, transparent: true, opacity: 0.26,
    side: THREE.DoubleSide, depthWrite: false });

  const HANDLE_L = 1.02;
  const handle = new THREE.Mesh(
    new THREE.CylinderGeometry(0.014, 0.021, HANDLE_L, 8), wood);
  handle.position.y = HANDLE_L / 2;
  const butt = new THREE.Mesh(new THREE.CylinderGeometry(0.023, 0.023, 0.14, 8), grip);
  butt.position.y = 0.07;
  const ferrule = new THREE.Mesh(
    new THREE.CylinderGeometry(0.018, 0.018, 0.06, 8), rim);
  ferrule.position.y = HANDLE_L - 0.01;

  const hoop = new THREE.Mesh(
    new THREE.TorusGeometry(NET_HOOP_R, 0.009, 8, 28), rim);
  hoop.position.y = HANDLE_L + NET_HOOP_R;
  hoop.rotation.x = Math.PI / 2;                 // the mouth faces the way it points

  // The bag profile, in the hoop's plane: mouth → belly → rounded bottom.
  // Points are (radius, depth); depth runs away from the handle.
  const BAG_DEPTH = 0.52;
  const prof = [[1.00, 0.00], [0.97, 0.12], [0.88, 0.28], [0.72, 0.46],
                [0.52, 0.64], [0.30, 0.81], [0.13, 0.93], [0.00, 1.00]];
  const bag = new THREE.Mesh(
    new THREE.LatheGeometry(
      prof.map(([r, d]) => new THREE.Vector2(r * NET_HOOP_R, d * BAG_DEPTH)), 20),
    gauze);
  bag.position.y = hoop.position.y;
  net.add(handle, butt, ferrule, hoop, bag);

  // Held out and forward rather than shouldered: the mouth of the net is what
  // the user is aiming, so it has to be where they can see it.
  net.position.set(0, -0.5, 0);
  net.rotation.x = -1.05;
  net.rotation.z = -0.18;
  return net;
}

// Show/hide the net in his hand. Safe before the walker exists — the mode can
// be set while the window is still in the orbit view.
function setWalkerNet(on) {
  if (!walkAvatar || !walkAvatar.userData.net) return;
  walkAvatar.userData.net.visible = !!on;
}

function walkerHasNet() {
  return !!(walkMode && walkAvatar && walkAvatar.userData.net
            && walkAvatar.userData.net.visible);
}

// How far he can reach with it. A creature further than this is not caught —
// you walk up to it, which is the whole difference between a net and a click
// (P11: the body knows things the screen does not).
const NET_REACH_M = 3.0;

// How far the LATCHED target may drift before it is genuinely gone. See
// netTarget: the ring and the click must not be two independent queries.
const NET_KEEP_M = 4.2;

function walkerCanReach(worldPos) {
  if (!walkAvatar || !worldPos) return false;
  const dx = worldPos.x - walkAvatar.position.x;
  const dz = worldPos.z - walkAvatar.position.z;
  const dy = worldPos.y - (walkAvatar.position.y + 1.4);
  return dx * dx + dz * dz + dy * dy <= NET_REACH_M * NET_REACH_M;
}

// ── What the net would actually catch (V2.46c) ──────────────────────────────
//
//     *"Catching the bugs is impossible with the way it is set up, make it
//     easier. If I am within range of a bug and click while holding the net,
//     not clicking on the bug because it is tiny and too kind of too fast
//     moving honestly."*
//
// Correct, and the shipped design was indefensible once the sizes were right.
// V2.46 required a RAYCAST HIT on the creature — so catching a leafcutter bee
// meant landing the cursor on a 34 mm object moving at a metre a second on a
// wandering path. Making the creatures honestly small made that target four
// times smaller. Two fixes that had to arrive together.
//
// **You swing the net, you do not click the animal.** In reach + click = catch.
// That is also what a net IS: you sweep it through the air where the insect is,
// which is precisely why real people can catch insects they could never touch.
//
// Nearest wins outright rather than nearest-to-the-cursor: aiming is the thing
// that was impossible, so requiring even approximate aim brings the problem
// back in a milder form. If two creatures are in arm's reach, getting the other
// one is not a failure — that is a net.
function critterInReach() {
  if (!walkAvatar || typeof wildlifeCritters === 'undefined') return null;
  let best = null, bestD = Infinity;
  for (const c of wildlifeCritters) {
    const o = c && c.obj;
    const info = o && o.userData && o.userData.critterInfo;
    if (!o || !info || !info.name || !o.visible) continue;
    const dx = o.position.x - walkAvatar.position.x;
    const dz = o.position.z - walkAvatar.position.z;
    const dy = o.position.y - (walkAvatar.position.y + 1.4);
    const d2 = dx * dx + dz * dz + dy * dy;
    if (d2 < bestD) { bestD = d2; best = o; }
  }
  if (!best || bestD > NET_REACH_M * NET_REACH_M) return null;
  return best;
}

// ── The one the ring is on, not "whatever is in reach right now" ────────────
//
//     *"I caught a bird once but often the circle shows up and I click to swing
//     but I don't catch anything."*
//
// Exactly the symptom of a race, and it was one. `updateReachRing` asked
// `critterInReach()` every frame and the click asked it AGAIN — two independent
// queries about a creature moving at a metre or two a second. Between the frame
// that drew the ring and the pointerup a few hundred milliseconds later, the
// animal could be a few centimetres past 2.4 m, and the click would report
// "nothing in reach" about the very creature the user was looking at a ring
// around.
//
// So the ring LATCHES its target and the click takes that one. The grace radius
// is deliberately wider than the reach: once you have committed to a swing, an
// animal drifting out of arm's length mid-swing is caught, which is both fairer
// and closer to what a net does.
function netTarget() {
  if (_reachOn && _reachOn.parent && walkAvatar) {
    const dx = _reachOn.position.x - walkAvatar.position.x;
    const dz = _reachOn.position.z - walkAvatar.position.z;
    const dy = _reachOn.position.y - (walkAvatar.position.y + 1.4);
    if (dx * dx + dz * dz + dy * dy <= NET_KEEP_M * NET_KEEP_M) return _reachOn;
  }
  return critterInReach();
}

// ── "That one." ─────────────────────────────────────────────────────────────
//
// The other half of "impossible": with no feedback, you cannot tell whether
// you are close enough, so a click that does nothing is indistinguishable from
// a broken button. A ring follows whatever `critterInReach` currently returns,
// so the answer to *"can I catch that?"* is on screen before you try — and it
// doubles as the thing that teaches the reach exists at all.
let _reachRing = null, _reachOn = null;

function _ensureReachRing() {
  if (_reachRing) return _reachRing;
  const g = new THREE.RingGeometry(0.10, 0.13, 24).rotateX(-Math.PI / 2);
  const m = new THREE.MeshBasicMaterial({
    color: 0xffe082, transparent: true, opacity: 0.9,
    depthTest: false, side: THREE.DoubleSide });
  _reachRing = new THREE.Mesh(g, m);
  _reachRing.renderOrder = 998;
  _reachRing.visible = false;
  scene.add(_reachRing);
  return _reachRing;
}

// Called every frame from walkStep. Cheap: one pass over a list that is at most
// a couple of dozen long.
function updateReachRing() {
  const want = walkerHasNet() ? critterInReach() : null;
  _reachOn = want;
  if (!want) { if (_reachRing) _reachRing.visible = false; return; }
  const ring = _ensureReachRing();
  ring.visible = true;
  // Sit it just under the creature and scale it to the creature, so it frames
  // a bee without swallowing a bird.
  const size = (typeof drawnSizeOf === 'function') ? drawnSizeOf(want) : 0;
  const r = Math.max(1, (size || 0.05) * 9);
  ring.scale.setScalar(r);
  ring.position.set(want.position.x, want.position.y - (size || 0.03) * 1.2,
                    want.position.z);
  // A slow pulse — a static ring on a moving animal reads as scene furniture.
  const k = 1 + 0.10 * Math.sin(performance.now() * 0.006);
  ring.scale.multiplyScalar(k);
}

function hideReachRing() {
  if (_reachRing) _reachRing.visible = false;
  _reachOn = null;
}

// One swing of the arm the net is on. Additive: `walkStep` writes the walk
// cycle into that pivot every frame, so the swing rides on top of it rather
// than fighting it (which is what a direct rotation write would do).
function swingNet(ms) {
  if (!walkAvatar) return;
  const dur = ms || 460;
  const t0 = performance.now();
  const tick = () => {
    const k = Math.min(1, (performance.now() - t0) / dur);
    // Up and over: a quick cock backwards, then the sweep through.
    walkAvatar.userData.netSwing =
      k < 0.3 ? -1.1 * (k / 0.3) : -1.1 + 2.3 * ((k - 0.3) / 0.7);
    if (k < 1) requestAnimationFrame(tick);
    else walkAvatar.userData.netSwing = 0;
  };
  tick();
}
