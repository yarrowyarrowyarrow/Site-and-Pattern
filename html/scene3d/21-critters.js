// Part of the Site & Pattern 3D viewer. Loaded as an ordered CLASSIC
// script by the bootstrap in scene3d.html — it shares the global scope
// with its siblings, so load ORDER is dependency order. Do not add ES
// `import`/`export` here.

// ── The creature bodies (V2.46d split) ──────────────────────────────────────
//
// Split out of 07-wildlife.js when that file reached its 800-line ceiling for
// the second increment running (the bird flight attitude was the last straw).
// The seam is the one 20-walker.js established: **this file is what an animal
// is made of; 07 is how it behaves.**
//
// Load-order note, which is the property that actually matters after the
// 19-roster.js regression: nothing here is called from the animation loop.
// `rebuildWildlife` reads `_CRITTER_FACTORY` at runtime — when Python pushes a
// wildlife list, long after every chunk has loaded — and guards for it anyway.
//
// `_cmat`, `_wingMat`, `makeBeeAvatar` and `makeButterflyAvatar` all live in
// earlier chunks and are reached through the shared global scope, as everywhere
// else in this viewer.

// Bees + butterflies/moths reuse the (species-styled) avatar bodies, scaled down.
function makeBeeCritter(app) {
  const g = makeBeeAvatar(app); g.scale.multiplyScalar(0.85);
  g.userData.anim = 'flier'; return g;
}
function makeButterflyCritter(app) {
  const g = makeButterflyAvatar(app.kind === 'moth', app);
  g.scale.multiplyScalar(1.15); g.userData.anim = 'flier'; return g;
}

// A perched (or hovering, for hummingbirds) low-poly bird.
function makeBirdCritter(app) {
  const g = new THREE.Group();
  const body = _cmat(app.body, { flat: true }), belly = _cmat(app.belly, { flat: true });
  const wing = _cmat(app.wing, { flat: true });
  const b = new THREE.Mesh(new THREE.SphereGeometry(0.16, 10, 8), body);
  b.scale.set(0.85, 0.9, 1.35);
  const bel = new THREE.Mesh(new THREE.SphereGeometry(0.13, 8, 6), belly);
  bel.scale.set(0.7, 0.8, 1.0); bel.position.set(0, -0.05, 0.06);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 9, 7), body);
  head.position.set(0, 0.12, -0.16);
  const beak = new THREE.Mesh(new THREE.ConeGeometry(0.03, app.hummer ? 0.22 : 0.09, 5),
                              _cmat('#2a221a', { flat: true }));
  beak.rotation.x = -Math.PI / 2; beak.position.set(0, 0.12, -0.28 - (app.hummer ? 0.08 : 0));
  const tail = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.02, 0.22), wing);
  tail.position.set(0, 0.02, 0.28); tail.rotation.x = 0.3;
  g.add(b, bel, head, beak, tail);
  const wings = [];
  const wg = new THREE.SphereGeometry(0.14, 8, 3);
  for (const s of [-1, 1]) {
    const pivot = new THREE.Group(); pivot.position.set(0.08 * s, 0.04, 0.02);
    const w = new THREE.Mesh(wg, wing); w.scale.set(0.5, 0.14, 1.0);
    w.position.set(0.12 * s, 0, 0.02); pivot.add(w); g.add(pivot);
    wings.push({ pivot, sign: s });
  }
  g.userData.wings = wings;
  if (app.hummer) {
    g.userData.flap = { base: 0, amp: 1.1, speed: 0.4 };   // blur
    g.userData.anim = 'hover';
  } else {
    // A real wingbeat: slow and deep, nothing like a bee's blur. `amp` was 0.0
    // — the comment said "folded", but with the perch branch never calling
    // flapWings either, it meant a bird's wings never moved at all. Both had to
    // change. animateWildlife folds them to `base` on the perch by passing
    // gain 0, so the settled pose the old config wanted is still there.
    // V2.45b: matches _GLB_CRITTER.bird in 09-models.js — the two flap
    // tables have to agree or the baked and procedural birds beat
    // differently in the same scene.
    g.userData.flap = { base: -0.55, amp: 1.7, speed: 0.22, hold: 0.0 };
    g.userData.anim = 'perch';
  }
  g.scale.setScalar(0.9 * (app.size || 1));
  return g;
}

// Flower fly / hover fly, or an elongate dragonfly/damselfly.
function makeFlyCritter(app) {
  const g = new THREE.Group();
  const body = _cmat(app.body, { metal: !app.elongate, flat: true });
  const wing = _wingMat(app.wing);
  if (app.elongate) {
    const th = new THREE.Mesh(new THREE.SphereGeometry(0.06, 8, 6), body);
    const abd = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.015, 0.5, 6), body);
    abd.rotation.x = Math.PI / 2; abd.position.set(0, 0, 0.28);
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.055, 8, 6),
                                _cmat('#20242a', { flat: true }));
    head.position.set(0, 0, -0.1);
    g.add(th, abd, head);
    const wings = [];
    for (const s of [-1, 1]) for (const z of [-0.02, 0.12]) {
      const pivot = new THREE.Group(); pivot.position.set(0.04 * s, 0.03, z);
      const w = new THREE.Mesh(new THREE.PlaneGeometry(0.4, 0.09).rotateX(-Math.PI / 2), wing);
      w.position.set(0.2 * s, 0, 0); pivot.add(w); g.add(pivot);
      if (z < 0) wings.push({ pivot, sign: s });
    }
    g.userData.wings = wings;
    g.userData.flap = { base: 0, amp: 0.25, speed: 0.3 };
    g.userData.anim = 'hover';
  } else {
    const th = new THREE.Mesh(new THREE.SphereGeometry(0.07, 9, 7), body);
    th.scale.set(0.9, 0.8, 1.3);
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 6),
                                _cmat('#20242a', { flat: true }));
    head.position.set(0, 0.01, -0.12);
    g.add(th, head);
    const wings = [];
    const wg = new THREE.CircleGeometry(0.16, 10);
    for (const s of [-1, 1]) {
      const pivot = new THREE.Group(); pivot.position.set(0.03 * s, 0.05, 0.0);
      const w = new THREE.Mesh(wg, wing); w.scale.set(0.55, 1, 1);
      w.position.set(0.14 * s, 0, 0.03); w.rotation.set(-1.2, 0, 0.2 * s);
      pivot.add(w); g.add(pivot);
      wings.push({ pivot, sign: s });
    }
    g.userData.wings = wings;
    g.userData.flap = { base: 0.1, amp: 0.8, speed: 0.5 };
    g.userData.anim = 'flier';
  }
  g.scale.setScalar(0.9 * (app.size || 1));
  return g;
}

function makeBeetleCritter(app) {
  const g = new THREE.Group();
  const body = _cmat(app.body, { metal: true, flat: true });
  const dome = new THREE.Mesh(new THREE.SphereGeometry(0.12, 10, 8,
                 0, Math.PI * 2, 0, Math.PI / 2), body);
  dome.scale.set(1, 0.7, 1.25);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 6),
                              _cmat('#1c1a16', { flat: true }));
  head.position.set(0, 0.01, -0.15);
  g.add(dome, head);
  if (app.spots) {
    const dot = _cmat('#1c1a16', { flat: true });
    for (let i = 0; i < 6; i++) {
      const s = new THREE.Mesh(new THREE.SphereGeometry(0.018, 6, 5), dot);
      const a = i / 6 * Math.PI * 2;
      s.position.set(Math.cos(a) * 0.06, 0.075, Math.sin(a) * 0.08 + 0.02);
      g.add(s);
    }
  }
  g.userData.anim = 'crawl';
  g.scale.setScalar(1.1 * (app.size || 1));
  return g;
}

// A flitting bat: dark body + two membranous wings that flap; flies like the
// other fliers. (Only ever placed at night by scene_wildlife.)
function makeBatCritter(app) {
  const g = new THREE.Group();
  const fur = _cmat(app.body || '#3a2f28', { flat: true });
  const memb = new THREE.MeshStandardMaterial({ color: 0x2a2430, roughness: 0.9,
    emissive: 0x0e0b12, emissiveIntensity: 0.5, side: THREE.DoubleSide, flatShading: true });
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.08, 8, 6), fur);
  body.scale.set(0.8, 0.9, 1.3);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.055, 8, 6), fur);
  head.position.set(0, 0.03, -0.1);
  for (const s of [-1, 1]) {
    const ear = new THREE.Mesh(new THREE.ConeGeometry(0.02, 0.06, 4), fur);
    ear.position.set(0.03 * s, 0.09, -0.11); g.add(ear);
  }
  g.add(body, head);
  const wingShape = new THREE.Shape();
  wingShape.moveTo(0, 0); wingShape.lineTo(0.34, 0.06);
  wingShape.lineTo(0.32, -0.05); wingShape.lineTo(0.18, -0.08);
  wingShape.lineTo(0.1, -0.12); wingShape.lineTo(0, 0);
  const wingGeo = new THREE.ShapeGeometry(wingShape);
  const wings = [];
  for (const s of [-1, 1]) {
    const pivot = new THREE.Group(); pivot.position.set(0.02 * s, 0.02, 0);
    const w = new THREE.Mesh(wingGeo, memb);
    w.scale.x = s; w.rotation.x = -Math.PI / 2;
    pivot.add(w); g.add(pivot);
    wings.push({ pivot, sign: s });
  }
  g.userData.wings = wings;
  g.userData.flap = { base: 0, amp: 0.9, speed: 0.28 };
  g.userData.anim = 'flier';
  g.scale.setScalar(1.1 * (app.size || 1));
  return g;
}

function makeMammalCritter(app) {
  if (app.form === 'bat') return makeBatCritter(app);
  const g = new THREE.Group();
  const fur = _cmat(app.body, { flat: true });
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.13, 10, 8), fur);
  body.scale.set(0.9, 0.85, 1.5);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.09, 9, 7), fur);
  head.position.set(0, 0.04, -0.17);
  const nose = new THREE.Mesh(new THREE.ConeGeometry(0.03, 0.08, 5), fur);
  nose.rotation.x = -Math.PI / 2; nose.position.set(0, 0.02, -0.26);
  g.add(body, head, nose);
  for (const s of [-1, 1]) {
    const ear = new THREE.Mesh(new THREE.CircleGeometry(0.04, 8), fur);
    ear.position.set(0.05 * s, 0.12, -0.14); g.add(ear);
  }
  const tail = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.004, 0.3, 5),
                              _cmat('#caa0a0', { flat: true }));
  tail.rotation.x = -1.2; tail.position.set(0, 0.02, 0.24); g.add(tail);
  g.userData.anim = 'ground';
  g.scale.setScalar(1.0 * (app.size || 1));
  return g;
}

const _CRITTER_FACTORY = {
  bee: makeBeeCritter, butterfly: makeButterflyCritter, moth: makeButterflyCritter,
  bird: makeBirdCritter, fly: makeFlyCritter, beetle: makeBeetleCritter,
  mammal: makeMammalCritter,
};

