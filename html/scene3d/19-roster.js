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
      spotCritter.rotation.y = critterHeading(d.x, d.z);
    }
  }
  spotCritter.position.y = tgt.y + Math.sin(t * 0.005 + spotIdx) * 0.06;
  flapWings(spotCritter, t);
}

