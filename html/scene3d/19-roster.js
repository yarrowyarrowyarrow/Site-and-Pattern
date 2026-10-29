// Part of the Site & Pattern 3D viewer. Loaded as an ordered CLASSIC
// script by the bootstrap in scene3d.html — it shares the global scope
// with its siblings, so load ORDER is dependency order. Do not add ES
// `import`/`export` here.

// ── Who lives here: the roster, the labels, the spotlight (V2.46 split) ──────
//
// Split out of 07-wildlife.js when that file reached its 800-line ceiling
// (creature life-size scaling and obstacle collision landed in the same
// increment). The line the split follows: 07 is the ANIMALS — how they are
// built, how big they are, where they go, what their wings do. This file is
// everything that *explains* them to a person — the corner roster, the floating
// name labels, and the "show me which of my plants this creature uses"
// spotlight (P5: make the invisible ecology visible).
//
// `wildLabelsOn`, `WILD_SUMMARY`, `WILDLIFE`, `wildlifeGroup` and
// `wildlifeCritters` are all declared in 07-wildlife.js and shared through the
// classic-script global scope, as everywhere else in this viewer.

const _KIND_LABEL = { bee: '🐝 Bees', butterfly: '🦋 Butterflies', moth: '🌙 Moths',
  bird: '🐦 Birds', fly: '🪰 Flies & dragonflies', beetle: '🐞 Beetles',
  mammal: '🦇 Mammals' };
const _KIND_ORDER = ['bee', 'butterfly', 'moth', 'fly', 'beetle', 'bird', 'mammal'];

// The roster (V3.39). Until now a wall: every creature out, by group, under a
// count of everything the plants support. The owner: the standalone "who
// lives here" "simply overwhelms and does not encourage learning". So one
// line, and the creatures out now folded under it, each a link to its card
// (25-cards.js), the ones known only by a Latin name folded again. The count
// is the scene's animals recorded as food for (src/scene_dossier.py `reach`,
// the V3.20 rule: each once, shelter alone not counted), and falls back to
// the summary pushed with the creatures.
let _rosterOpen = false;

function _rosterTotal() {
  const reach = (typeof DOSSIER !== 'undefined' && DOSSIER && DOSSIER.reach)
    || WILD_SUMMARY || {};
  return Object.values(reach).reduce((a, b) => a + (b | 0), 0);
}

function _rosterRow(name) {
  const known = DOSSIER.fauna && DOSSIER.fauna[name];
  return '<div class="row' + (known ? ' link" data-open-fauna="' + _escHtml(name)
    + '" tabindex="0' : '') + '">' + _escHtml(name) + '</div>';
}

function updateRoster() {
  const el = document.getElementById('wild-roster');
  if (!el) return;
  if (!wildLabelsOn || !WILDLIFE.length) { el.style.display = 'none'; return; }
  const byKind = {}, seen = new Set();
  for (const c of WILDLIFE) {
    if (!c.name || seen.has(c.name)) continue;
    seen.add(c.name);
    (byKind[c.kind] = byKind[c.kind] || []).push(c.name);
  }
  const total = _rosterTotal();
  let html = '<h4>' + (total ? 'This landscape is recorded as food for ' + total
    + ' kinds of animals.' : 'Who is out') + '</h4>';
  html += '<details class="outnow"' + (_rosterOpen ? ' open' : '') + '><summary>'
    + seen.size + (seen.size === 1 ? ' is' : ' are') + ' out now</summary>';
  for (const k of _KIND_ORDER) {
    const list = byKind[k]; if (!list || !list.length) continue;
    const named = [], latin = [];
    for (const name of list) {
      const f = DOSSIER.fauna && DOSSIER.fauna[name];
      (f && f.english === false ? latin : named).push(name);
    }
    html += '<div class="grp">' + (_KIND_LABEL[k] || k) + ' · ' + list.length + '</div>';
    html += named.map(_rosterRow).join('');
    if (latin.length) {
      html += '<details class="latin"><summary>and ' + latin.length
        + ' known only by a Latin name</summary>' + latin.map(_rosterRow).join('')
        + '</details>';
    }
  }
  el.innerHTML = html + '</details>';
  el.style.display = 'block';
  const fold = el.querySelector('details.outnow');
  if (fold) fold.addEventListener('toggle', () => { _rosterOpen = fold.open; });
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
function stepSpotlight(tRaw) {
  if (!spotGroup || !SPOT.length || !spotCritter) { _spotPrevT = tRaw; return; }
  // The spotlight creature obeys the same speed control as the ambient wildlife
  // (F121, V2.54) — it is the one creature the user has deliberately asked to
  // look at, so it is the last one that should be exempt from "hold still".
  // Same two-clock rule as animateWildlife: `dt` moves it, `t` beats its wings,
  // so both are scaled or the wings run on while the body stops.
  const raw = _spotPrevT ? Math.min(0.05, (tRaw - _spotPrevT) / 1000) : 0.016;
  _spotPrevT = tRaw;
  const dt = raw * (typeof wildlifeSpeed === 'function' ? wildlifeSpeed() : 1);
  const t = _wildClock;
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
      spotCritter.rotation.y = critterHeading(d.x, d.z);
    }
  }
  spotCritter.position.y = tgt.y + Math.sin(t * 0.005 + spotIdx) * 0.06;
  flapWings(spotCritter, t);
}

