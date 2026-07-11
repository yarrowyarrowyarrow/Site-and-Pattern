// Part of the Site & Pattern 3D viewer, split out of the former
// single html/scene3d.html <script> (V2.24). Loaded as an ordered
// CLASSIC script by the bootstrap in scene3d.html — it shares the
// global scope with its siblings (THREE/OrbitControls/mergeGeometries
// are globals set by the bootstrap), so load ORDER is dependency
// order. Do not add ES `import`/`export` here.

// ── Ambient wildlife (V2.12) ─────────────────────────────────────────────────
// The animals the design's plants support, placed on/near a plant they use and
// drawn to look like their real species (from src/scene_wildlife.py). Shown in
// the orbit + walk views; hidden while flying as one creature. A separate group
// (like the beacons) so a scene rebuild doesn't dispose it — the host re-pushes
// wildlife after each scene push.
let WILDLIFE = [];
// wildlifeGroup is forward-declared in 01-core.js (the first chunk) because
// 01-core's pointermove handler reads it — see the note there. Assign, don't
// re-declare, or the two `let`s would collide in the shared global scope.
wildlifeGroup = null;
let wildlifeCritters = [];

function _cmat(hex, opts) {
  opts = opts || {};
  const c = new THREE.Color(hex);
  return new THREE.MeshStandardMaterial({
    color: c, roughness: opts.metal ? 0.35 : 0.82, metalness: opts.metal ? 0.7 : 0.0,
    emissive: c.clone().multiplyScalar(0.28), emissiveIntensity: 0.6,
    flatShading: !!opts.flat });
}
function _wingMat(hex) {
  return new THREE.MeshBasicMaterial({ color: new THREE.Color(hex || 0xeef4f8),
    transparent: true, opacity: 0.3, side: THREE.DoubleSide, depthWrite: false });
}
function flapWings(obj, t) {
  const fp = obj.userData.flap;
  if (!fp || !obj.userData.wings) return;
  const w = fp.base + (0.5 + 0.5 * Math.sin(t * fp.speed)) * fp.amp;
  for (const { pivot, sign } of obj.userData.wings) pivot.rotation.z = sign * w;
}

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
    g.userData.flap = { base: -0.2, amp: 0.0, speed: 0.05 };  // folded
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

function disposeWildlife() {
  if (!wildlifeGroup) { wildlifeCritters = []; return; }
  scene.remove(wildlifeGroup);
  // Dispose per-critter geometry/materials, but NOT the shared contact-shadow
  // geometry/material (reused across rebuilds) or its shared SHADOW_TEX.
  wildlifeGroup.traverse(o => {
    // Skip sprite geometry (shared THREE internal) and the shared shadow geo.
    if (o.geometry && !o.isSprite && o.geometry !== _CRIT_SHADOW_GEO) o.geometry.dispose();
    const m = o.material;
    if (m) for (const mm of (Array.isArray(m) ? m : [m]))
      if (mm && mm !== _CRIT_SHADOW_MAT) {
        if (mm.map && mm.map !== SHADOW_TEX) mm.map.dispose();   // per-label canvas
        mm.dispose();
      }
  });
  wildlifeGroup = null; wildlifeCritters = [];
}

// A soft contact-shadow disc on the ground under a critter — grounds the
// hovering ones and helps you tell a low bee from a flower.
let _CRIT_SHADOW_MAT = null, _CRIT_SHADOW_GEO = null;
function makeCritShadow(r) {
  if (!SHADOW_TEX) SHADOW_TEX = makeShadowTexture();
  if (!_CRIT_SHADOW_MAT) _CRIT_SHADOW_MAT = new THREE.MeshBasicMaterial({
    map: SHADOW_TEX, transparent: true, depthWrite: false, color: 0x243018, opacity: 0.5 });
  if (!_CRIT_SHADOW_GEO) _CRIT_SHADOW_GEO = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
  const sh = new THREE.Mesh(_CRIT_SHADOW_GEO, _CRIT_SHADOW_MAT);
  sh.scale.set(r, 1, r);
  return sh;
}

function rebuildWildlife() {
  disposeWildlife();
  if (!WILDLIFE.length) return;
  wildlifeGroup = new THREE.Group();
  for (const spec of WILDLIFE) {
    const app = spec.app || { kind: spec.kind };
    const make = _CRITTER_FACTORY[spec.kind] || _CRITTER_FACTORY[app.kind];
    if (!make) continue;
    let obj; try { obj = make(app); } catch (e) { continue; }
    // At night, lift each critter's self-illumination so the moths & bats read
    // against the dark instead of disappearing.
    if (sceneNight) obj.traverse(o => {
      const m = o.material;
      if (m && m.emissive) m.emissiveIntensity = Math.min(1.5, (m.emissiveIntensity || 0.5) * 2.4);
    });
    const gy = terrainHeightAt(spec.x, spec.y, lastTerrain);
    const anchor = new THREE.Vector3(spec.x, gy, -spec.y);
    obj.position.set(anchor.x, gy + (spec.h || 0.3), anchor.z);
    // Backref so hover can name the creature + the plant it's using.
    obj.userData.critterInfo = { name: spec.name || '', on: spec.on || '',
                                 rel: spec.rel || '', kind: spec.kind };
    const flier = obj.userData.anim === 'flier' || obj.userData.anim === 'hover';
    const shadow = makeCritShadow(flier ? 0.5 : 0.4);
    shadow.position.set(anchor.x, gy + 0.02, anchor.z);
    wildlifeGroup.add(shadow);
    // Route: the plants this species uses, as world targets (x, ground+perchH, z).
    // The animal travels between them (V2.13) instead of orbiting one plant.
    const route = (spec.route && spec.route.length ? spec.route
                   : [[spec.x, spec.y, spec.h || 0.3]]).map(w => {
      const wgy = terrainHeightAt(w[0], w[1], lastTerrain);
      return new THREE.Vector3(w[0], wgy + (w[2] || 0.3), -w[1]);
    });
    wildlifeCritters.push({
      obj, shadow, anchor, h: spec.h || 0.3, seed: (spec.seed || 0) % 1000,
      anim: obj.userData.anim, route, ri: 0, dwell: 0,
      pos: obj.position.clone(),
      speed: (0.7 + ((spec.seed || 0) % 50) / 45),   // m/s scale per animal
      wanderPh: ((spec.seed || 0) % 628) / 100,
    });
    wildlifeGroup.add(obj);
  }
  wildlifeGroup.visible = !beeMode;   // hidden while flying as one creature
  scene.add(wildlifeGroup);
}

// Per-taxon travel speed (m/s) + dwell (s) when it reaches a plant.
const _WILD_MOVE = {
  flier:  { spd: 1.6, dwell: 1.6, bob: 0.05 },   // bees: cruise, land & sip
  hover:  { spd: 1.2, dwell: 1.1, bob: 0.06 },   // hummingbird/dragonfly darts
  perch:  { spd: 4.5, dwell: 3.2, bob: 0.02 },   // birds: quick hop, long sit
  ground: { spd: 2.2, dwell: 1.4, bob: 0.0 },    // mammals: scurry then freeze
  crawl:  { spd: 0.25, dwell: 2.5, bob: 0.0 },   // beetles: slow amble
};
const _WV = new THREE.Vector3();
function animateWildlife(t) {
  if (!wildlifeGroup || !wildlifeGroup.visible) return;
  const dt = _wildDt(t);
  for (const c of wildlifeCritters) {
    const o = c.obj, ph = c.wanderPh, mv = _WILD_MOVE[c.anim] || _WILD_MOVE.flier;
    const tgt = c.route[c.ri];
    const single = c.route.length < 2;
    if (c.dwell > 0) {
      c.dwell -= dt;                              // resting at / on a plant
      if (c.dwell <= 0 && !single) c.ri = (c.ri + 1) % c.route.length;
    } else {
      _WV.subVectors(tgt, c.pos); _WV.y = 0;
      const flat = _WV.length();
      if (flat < 0.25) {                          // arrived → dwell
        c.dwell = mv.dwell * (0.6 + (c.seed % 40) / 50);
      } else if (c.anim === 'perch') {
        // Birds hop discretely between perches: brief hold, then jump.
        c.pos.lerp(tgt, Math.min(1, dt * 3.0));
        o.position.copy(c.pos);
      } else {
        _WV.multiplyScalar(1 / flat);
        c.pos.addScaledVector(_WV, Math.min(flat, mv.spd * c.speed * dt));
        // Butterflies/moths flutter: weave sideways off the straight line.
        if (c.anim === 'flier' && (o.userData.critterInfo &&
            (o.userData.critterInfo.kind === 'butterfly' || o.userData.critterInfo.kind === 'moth'))) {
          const side = new THREE.Vector3(-_WV.z, 0, _WV.x);
          c.pos.addScaledVector(side, Math.sin(t * 0.012 + ph) * 0.6 * dt);
          c.pos.y = tgt.y + Math.sin(t * 0.009 + ph) * 0.25;   // bob up & down
        }
        o.position.copy(c.pos);
        o.rotation.y = Math.atan2(_WV.x, _WV.z);
      }
    }
    // Height + local idle motion by kind.
    if (c.anim === 'flier' || c.anim === 'hover') {
      const wob = single ? 0.18 : 0.0;            // lone fliers wander in place
      o.position.x = c.pos.x + Math.sin(t * 0.0016 + ph) * wob;
      o.position.z = c.pos.z + Math.cos(t * 0.0019 + ph) * wob;
      o.position.y = (c.dwell > 0 || single ? tgt.y : o.position.y) + Math.sin(t * 0.005 + ph) * mv.bob;
      flapWings(o, t);
      if (c.shadow) c.shadow.position.set(o.position.x, c.anchor.y + 0.02, o.position.z);
    } else if (c.anim === 'perch') {
      o.position.y = tgt.y + Math.sin(t * 0.003 + ph) * mv.bob;
      if (c.dwell > 0) o.rotation.y = ph + Math.sin(t * 0.0009 + ph) * 0.4;   // look around
    } else if (c.anim === 'ground') {
      const hop = c.dwell > 0 ? 0 : Math.abs(Math.sin(t * 0.02 + ph)) * 0.06;
      o.position.y = c.anchor.y + 0.02 + hop;
      if (c.shadow) c.shadow.position.set(o.position.x, c.anchor.y + 0.02, o.position.z);
    } else {                                       // crawl (beetle)
      o.position.y = tgt.y + Math.sin(t * 0.001 + ph) * 0.01;
    }
    // Always-on name label: small, constant on-screen size, and only for
    // creatures within ~13 m (the roster is the full list) so distant labels
    // don't pile up. Fades out with distance.
    if (c.label) {
      const d = camera.position.distanceTo(o.position);
      if (d > 13) { c.label.visible = false; }
      else {
        c.label.visible = true;
        const hh = 0.02 * Math.max(1.5, d);
        c.label.scale.set((c.label.userData.aspect || 4) * hh, hh, 1);
        c.label.position.set(o.position.x, o.position.y + 0.28 + hh * 0.7, o.position.z);
        c.label.material.opacity = Math.max(0.25, Math.min(0.95, (13 - d) / 6));
      }
    }
  }
}
let _wildPrevT = 0;
function _wildDt(t) {
  const dt = _wildPrevT ? Math.min(0.05, (t - _wildPrevT) / 1000) : 0.016;
  _wildPrevT = t; return dt;
}

window.permaSetWildlife = function (list, summary) {
  WILDLIFE = Array.isArray(list) ? list : [];
  // Optional {taxon: distinct-species-count} the design supports (from the
  // Habitat Value Score's fauna tally) — shown as the roster headline so the
  // ecological reach behind the score is legible right where you see them.
  WILD_SUMMARY = summary && typeof summary === 'object' ? summary : null;
  rebuildWildlife();
  if (wildLabelsOn) { buildWildLabels(); updateRoster(); }
};
let WILD_SUMMARY = null;

// ── "Who lives here": roster + always-on labels (V2.13) ──────────────────────
// One toggle answers "what is what" without hovering: a corner roster grouped
// by kind, and a small name label floating over each creature.
let wildLabelsOn = false;
const _KIND_LABEL = { bee: '🐝 Bees', butterfly: '🦋 Butterflies', moth: '🌙 Moths',
  bird: '🐦 Birds', fly: '🪰 Flies & dragonflies', beetle: '🐞 Beetles',
  mammal: '🦇 Mammals' };
const _KIND_ORDER = ['bee', 'butterfly', 'moth', 'fly', 'beetle', 'bird', 'mammal'];
const _TAXON_WORD = { bee: 'bees', lepidoptera: 'butterflies & moths',
  bird: 'birds', other_insect: 'other insects', mammal: 'mammals' };

function updateRoster() {
  const el = document.getElementById('wild-roster');
  if (!el) return;
  if (!wildLabelsOn || !WILDLIFE.length) { el.style.display = 'none'; return; }
  const byKind = {};
  for (const c of WILDLIFE) (byKind[c.kind] = byKind[c.kind] || []).push(c);
  let html = '<h4>🌿 Who lives here — ' + WILDLIFE.length + ' out now</h4>';
  // Headline the design's total ecological reach (the score's wildlife tally):
  // "supports N wildlife species" so the count behind the Habitat Value Score
  // is legible right beside the creatures it represents.
  if (WILD_SUMMARY) {
    const total = Object.values(WILD_SUMMARY).reduce((a, b) => a + (b | 0), 0);
    if (total) {
      const parts = _KIND_ORDER.map(k => {
        const tax = k === 'butterfly' || k === 'moth' ? 'lepidoptera'
          : k === 'fly' || k === 'beetle' ? 'other_insect' : k;
        return [tax, k];
      });
      const seen = {}, bits = [];
      for (const [tax] of parts) {
        if (seen[tax] || !WILD_SUMMARY[tax]) continue;
        seen[tax] = 1;
        bits.push(WILD_SUMMARY[tax] + ' ' + (_TAXON_WORD[tax] || tax));
      }
      html += '<div class="reach">🌎 Your plants support <b>' + total
        + ' wildlife species</b>' + (bits.length ? ' · ' + bits.join(', ') : '')
        + '</div>';
    }
  }
  for (const k of _KIND_ORDER) {
    const list = byKind[k]; if (!list || !list.length) continue;
    html += '<div class="grp">' + (_KIND_LABEL[k] || k) + ' · ' + list.length + '</div>';
    for (const c of list)
      html += '<div class="row">' + _escHtml(c.name)
        + (c.on ? ' <span class="on">· ' + _escHtml(c.on) + '</span>' : '') + '</div>';
  }
  el.innerHTML = html;
  el.style.display = 'block';
}
function _escHtml(s) {
  return String(s || '').replace(/[&<>]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}

function buildWildLabels() {
  clearWildLabels();
  if (!wildlifeGroup) return;
  for (const c of wildlifeCritters) {
    const lab = makeTextSprite(); setSpriteText(lab, c.obj.userData.critterInfo.name || '?');
    lab.material.depthTest = true;      // occlude behind plants → less clutter
    lab.renderOrder = 5;
    wildlifeGroup.add(lab); c.label = lab;
  }
}
function clearWildLabels() {
  for (const c of wildlifeCritters) {
    if (c.label) {
      wildlifeGroup && wildlifeGroup.remove(c.label);
      if (c.label.material.map) c.label.material.map.dispose();
      c.label.material.dispose(); c.label = null;
    }
  }
}

window.permaSetWildlifeLabels = function (on) {
  wildLabelsOn = !!on;
  if (wildLabelsOn) { buildWildLabels(); updateRoster(); }
  else { clearWildLabels(); const el = document.getElementById('wild-roster'); if (el) el.style.display = 'none'; }
};

// ── "Show its plants" spotlight (V2.12) ──────────────────────────────────────
// An orbit/walk overlay that answers "which of my plants does this creature
// benefit from?": a glowing column + name label rises over each plant the
// chosen creature uses, and one of that creature tours them, visiting each in
// turn. Both illuminate AND visit. Cleared by pushing an empty list.
let SPOT = [], spotGroup = null, spotCritter = null, spotIdx = 0, spotPause = 0;

function disposeSpot() {
  if (spotGroup) {
    scene.remove(spotGroup);
    spotGroup.traverse(o => {
      if (o.geometry && !o.isSprite) o.geometry.dispose();   // sprites share geo
      const m = o.material;
      if (m) for (const mm of (Array.isArray(m) ? m : [m])) {
        if (mm && mm.map && mm.map !== GLOW_TEX && mm.map !== SHADOW_TEX) mm.map.dispose();
        if (mm) mm.dispose();
      }
    });
  }
  spotGroup = null; spotCritter = null; SPOT = []; spotIdx = 0; spotPause = 0;
}

window.permaSetPlantSpotlight = function (items, appearance) {
  disposeSpot();
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return;
  if (beeMode) window.permaSetBeeMode(false);   // an orbit/walk overlay, not fly
  if (!GLOW_TEX) GLOW_TEX = makeGlowTexture();
  spotGroup = new THREE.Group();
  for (const it of list) {
    const gy = terrainHeightAt(it.x, it.y, lastTerrain);
    const ph = Math.max(0.8, it.h || 1);
    const top = gy + ph;
    const beam = new THREE.Mesh(
      new THREE.CylinderGeometry(0.06, 0.18, ph + 1.4, 8, 1, true),
      new THREE.MeshBasicMaterial({ color: 0xbfe98a, transparent: true, opacity: 0.16,
        side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false }));
    beam.position.set(it.x, gy + (ph + 1.4) / 2, -it.y);
    const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW_TEX,
      color: 0xd8f0a0, transparent: true, opacity: 0.85,
      blending: THREE.AdditiveBlending, depthWrite: false }));
    glow.position.set(it.x, top, -it.y); glow.scale.setScalar(1.7);
    const label = makeTextSprite(); setSpriteText(label, it.name || 'plant');
    const lh = 1.05; label.scale.set((label.userData.aspect || 4) * lh, lh, 1);
    label.position.set(it.x, top + 1.0, -it.y);
    spotGroup.add(beam, glow, label);
    it._top = new THREE.Vector3(it.x, top, -it.y);
  }
  const app = appearance || { kind: 'bee' };
  spotCritter = (app.kind === 'butterfly' || app.kind === 'moth')
    ? makeButterflyCritter(app) : makeBeeCritter(app);
  spotCritter.scale.multiplyScalar(1.8);
  spotCritter.position.copy(list[0]._top);
  spotGroup.add(spotCritter);
  SPOT = list; spotIdx = 0; spotPause = 0;
  scene.add(spotGroup);
};

let _spotPrevT = 0;
function stepSpotlight(t) {
  if (!spotGroup || !SPOT.length || !spotCritter) { _spotPrevT = t; return; }
  const dt = _spotPrevT ? Math.min(0.05, (t - _spotPrevT) / 1000) : 0.016;
  _spotPrevT = t;
  const tgt = SPOT[spotIdx]._top;
  if (spotPause > 0) {
    spotPause -= dt;
    if (spotPause <= 0) spotIdx = (spotIdx + 1) % SPOT.length;
  } else {
    const d = new THREE.Vector3().subVectors(tgt, spotCritter.position);
    const dist = d.length();
    if (dist < 0.35) { spotPause = 1.3; }        // pause and sip at each flower
    else {
      spotCritter.position.addScaledVector(d.multiplyScalar(1 / dist),
                                           Math.min(dist, (BEE_SPEED * 0.8) * dt));
      spotCritter.rotation.y = Math.atan2(d.x, -d.z);
    }
  }
  spotCritter.position.y = tgt.y + Math.sin(t * 0.005 + spotIdx) * 0.06;
  flapWings(spotCritter, t);
}

