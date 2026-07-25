// Part of the Site & Pattern 3D viewer, split out of the former
// single html/scene3d.html <script> (V2.24). Loaded as an ordered
// CLASSIC script by the bootstrap in scene3d.html — it shares the
// global scope with its siblings (THREE/OrbitControls/mergeGeometries
// are globals set by the bootstrap), so load ORDER is dependency
// order. Do not add ES `import`/`export` here.

// ── Click to inspect (V2.29) ────────────────────────────────────────────────
// Until now the only thing you could learn from the 3D view was a name on
// hover; the app's sourced ecology — documented plant↔fauna edges, bee nesting
// habits, flight seasons, bloom and fruit windows, keystone and specialist
// status — never reached the place where you can see the plant. Clicking one
// now opens a card built from exactly that data (src/scene_dossier.py, pushed
// via permaSetDossier), and draws the food-web threads from it to every animal
// in the scene that uses it.
//
// The card is rendered here rather than in Qt because the 3D bridge is
// one-directional by design (no QWebChannel): the content arrives with the
// scene, so a click needs no round trip and works in walk / fly / bee modes.

let DOSSIER = { plants: {}, fauna: {} };
let selection = null;             // {type:'plant'|'fauna', key, x, y}
let threadGroup = null;

const _iRay = new THREE.Raycaster();
const _iPtr = new THREE.Vector2();

function inspectCard() { return document.getElementById('inspect-card'); }

// ── the food-web threads ────────────────────────────────────────────────────
// P3/P10 made literal: the edge between a plant and an animal becomes a drawn
// object. From a plant, one thread to each creature in the scene that uses it;
// from a creature, one to each of its plants here.
function clearThreads() {
  if (!threadGroup) return;
  scene.remove(threadGroup);
  threadGroup.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    if (o.material && o.material.map) o.material.map.dispose();
    if (o.material) o.material.dispose();
  });
  threadGroup = null;
}

function critterAnchors() {
  const out = [];
  if (!wildlifeGroup) return out;
  for (const c of wildlifeGroup.children) {
    const info = c.userData && c.userData.critterInfo;
    if (info) out.push({ obj: c, info: info });
  }
  return out;
}

// A thread is a shallow arc, so several from one plant read as separate strands
// instead of a star of straight lines.
function threadCurve(a, b) {
  const mid = a.clone().lerp(b, 0.5);
  mid.y += Math.max(0.6, a.distanceTo(b) * 0.22);
  return new THREE.QuadraticBezierCurve3(a, mid, b);
}

function addThread(group, from, to, label, index) {
  const pts = threadCurve(from, to).getPoints(24);
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const line = new THREE.Line(geo, new THREE.LineBasicMaterial({
    color: 0xffe89a, transparent: true, opacity: 0.85, depthTest: false }));
  line.renderOrder = 6;
  group.add(line);
  if (label) {
    const sp = makeTextSprite();
    setSpriteText(sp, label);
    // Stagger where each label sits along its thread. Animals cluster on the
    // plant they use, so labels pinned to the midpoint pile into one unreadable
    // slab — walking them apart down the curve keeps a busy plant legible.
    const t = 0.3 + ((index || 0) % 5) * 0.13;
    const at = pts[Math.min(pts.length - 1, Math.round(t * (pts.length - 1)))];
    sp.position.set(at.x, at.y + 0.25, at.z);
    sp.renderOrder = 7;
    // setSpriteText only records the texture's aspect — the caller owns the
    // world size, and leaving it at the default 1×1 renders an unreadable white
    // slab. Same distance-scaled sizing as the wildlife labels (07-wildlife.js)
    // so a thread stays legible up close and shrinks out of the way from orbit.
    sp.userData.threadLabel = true;
    scaleThreadLabel(sp);
    group.add(sp);
  }
}

function scaleThreadLabel(sp) {
  const d = camera.position.distanceTo(sp.position);
  const hh = 0.012 * Math.max(1.5, d);
  sp.scale.set((sp.userData.aspect || 4) * hh, hh, 1);
  sp.material.opacity = Math.max(0.15, Math.min(0.95, (26 - d) / 14));
}

function plantWorldPos(pid) {
  const sc = lastSceneObj;
  if (!sc) return null;
  for (const p of sc.plants || []) {
    if (p.plant_id === pid) {
      const gy = terrainHeightAt(p.x, p.y, lastTerrain);
      return new THREE.Vector3(p.x, gy + Math.max(0.3, (p.height_m || 1) * 0.6),
                               -p.y);
    }
  }
  return null;
}

function buildThreads() {
  clearThreads();
  if (!selection) return;
  threadGroup = new THREE.Group();
  const crits = critterAnchors();
  if (selection.type === 'plant') {
    const pid = selection.key;
    const from = plantWorldPos(pid);
    if (from) {
      let i = 0;
      for (const c of crits) {
        if (c.info.onId !== pid) continue;
        addThread(threadGroup, from, c.obj.position.clone(),
                  (REL_WORDS_SHORT[c.info.rel] || '') + ' ' + c.info.name, i++);
      }
    }
  } else {
    // From a creature: a thread to each of ITS plants standing in this design.
    const name = selection.key;
    let i = 0;
    for (const c of crits) {
      if (c.info.name !== name) continue;
      const to = plantWorldPos(c.info.onId);
      if (to) addThread(threadGroup, c.obj.position.clone(), to,
                        (REL_WORDS_SHORT[c.info.rel] || '') + ' ' + c.info.on, i++);
    }
  }
  if (threadGroup.children.length) scene.add(threadGroup);
  else threadGroup = null;
}

const REL_WORDS_SHORT = {
  nectar: 'nectar', pollen: 'pollen', larval_host: 'caterpillar host',
  fruit_food: 'fruit', seed_food: 'seed', cover: 'cover', nesting: 'nest',
};

// ── the card ────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function chips(list, cls) {
  if (!list || !list.length) return '';
  return '<div class="chips">' + list.map(
    (b) => '<span class="chip ' + (cls || '') + '">' + esc(b) + '</span>').join('') + '</div>';
}

// Bloom / fruit against the month on screen, so the season slider becomes a
// teaching instrument: the bar lights up the months this plant is doing
// something, and marks where you currently are (P4).
function seasonBar(entry) {
  const sc = lastSceneObj || {};
  const now = sc.month || 0;
  const rows = [];
  const add = (label, span, color) => {
    if (!span) return;
    rows.push({ label: label, span: span, color: color });
  };
  add('bloom', entry.bloom, entry.bloom_color || '#e8c454');
  add('fruit', entry.fruit, entry.fruit_color || '#b5462e');
  if (entry.season) add('flying', entry.season, '#9ad0e8');
  if (!rows.length) return '';
  const MON = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
  let html = '<div class="season">';
  html += '<div class="srow"><span class="slab"></span>'
    + MON.map((m, i) => '<i class="' + (i + 1 === now ? 'nowm' : '') + '">'
      + m + '</i>').join('') + '</div>';
  for (const r of rows) {
    const months = monthsOf(r.span);
    html += '<div class="srow"><span class="slab">' + esc(r.label) + '</span>'
      + MON.map((_m, i) => '<i class="' + (months.has(i + 1) ? 'on' : '')
        + (i + 1 === now ? ' nowm' : '') + '" style="'
        + (months.has(i + 1) ? 'background:' + esc(r.color) : '') + '"></i>').join('')
      + '</div>';
  }
  return html + '</div>';
}

// 'May–Jul' / 'April-September' → the set of month numbers it covers.
const _MON3 = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7,
                aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
function monthsOf(span) {
  const out = new Set();
  if (!span) return out;
  const parts = String(span).toLowerCase().replace(/[–—]/g, '-').split('-');
  const nums = parts.map((p) => _MON3[p.trim().slice(0, 3)]).filter(Boolean);
  if (!nums.length) return out;
  const a = nums[0], b = nums[nums.length - 1];
  for (let m = a; ; m = (m % 12) + 1) { out.add(m); if (m === b) break; }
  return out;
}

// Size at years 1/5/15/25 as proportional bars — "when does this stop looking
// like a twig?", the question the year slider exists to answer (P4).
function growthStrip(entry) {
  const t = entry.timeline || [];
  if (!t.length) return '';
  const maxH = Math.max.apply(null, t.map((r) => r.height_m).concat([0.1]));
  let html = '<div class="grow"><div class="ghead">size over time</div>';
  for (const r of t) {
    const pct = Math.max(3, Math.round((r.height_m / maxH) * 100));
    html += '<div class="growrow' + (r.now ? ' gnow' : '') + '">'
      + '<span class="gy">yr ' + r.year + '</span>'
      + '<span class="gbar"><i style="width:' + pct + '%"></i></span>'
      + '<span class="gv">' + r.height_m.toFixed(1) + ' m tall · '
      + r.canopy_m.toFixed(1) + ' m wide</span></div>';
  }
  return html + '</div>';
}

function plantCardHtml(e) {
  let h = '<div class="ihead"><div class="iname">' + esc(e.name) + '</div>'
    + '<div class="isci">' + esc(e.scientific_name) + '</div></div>';
  h += chips(e.badges, 'good');
  const bits = [];
  if (e.plant_type) bits.push(esc(e.plant_type));
  if (e.sun) bits.push(esc(e.sun));
  if (e.water) bits.push(esc(e.water) + ' water');
  if (e.native) bits.push('native to ' + esc(e.native));
  if (bits.length) h += '<div class="ifacts">' + bits.join(' · ') + '</div>';

  h += seasonBar(e);
  h += growthStrip(e);

  if (e.users && e.users.length) {
    h += '<div class="isec">who uses it here — ' + e.users.length
      + ' documented ' + (e.users.length === 1 ? 'species' : 'species') + '</div><ul class="ilist">';
    for (const u of e.users) {
      h += '<li><b>' + esc(u.name) + '</b>'
        + (u.specialist ? '<span class="chip warn">specialist</span>' : '')
        + '<span class="how">' + esc(u.how) + ' this plant</span></li>';
    }
    h += '</ul>';
  } else {
    h += '<div class="isec">no documented wildlife edges yet</div>';
  }
  if (e.only_source && e.only_source.length) {
    h += '<div class="ionly"><b>Pull this plant and ' + e.only_source.length
      + ' species lose their only support here:</b> '
      + esc(e.only_source.join(', ')) + '</div>';
  }
  if (e.safety && e.safety.length) h += chips(e.safety, 'warn');
  if (e.sourcing && (e.sourcing.price || e.sourcing.availability)) {
    h += '<div class="isrc">' + esc([e.sourcing.price, e.sourcing.availability]
      .filter(Boolean).join(' · ')) + '</div>';
  }
  if (e.notes) h += '<div class="inotes">' + esc(e.notes) + '</div>';
  return h;
}

function faunaCardHtml(e) {
  let h = '<div class="ihead"><div class="iname">' + esc(e.name) + '</div>'
    + '<div class="isci">' + esc(e.scientific_name)
    + (e.taxon_label ? ' · ' + esc(e.taxon_label) : '') + '</div></div>';
  if (e.status) h += chips([e.status], 'warn');
  if (e.description) h += '<div class="inotes">' + esc(e.description) + '</div>';
  h += seasonBar(e);
  if (e.facts && e.facts.length) {
    h += '<ul class="ilist plain">';
    for (const f of e.facts) h += '<li>' + esc(f) + '</li>';
    h += '</ul>';
  }
  if (e.uses && e.uses.length) {
    h += '<div class="isec">your plants it uses</div><ul class="ilist">';
    for (const u of e.uses) {
      h += '<li><b>' + esc(u.plant) + '</b><span class="how">'
        + esc(u.how) + ' it</span></li>';
    }
    h += '</ul>';
  }
  if (e.range_notes) h += '<div class="isrc">' + esc(e.range_notes) + '</div>';
  return h;
}

function showCard(entry) {
  const card = inspectCard();
  if (!card) return;
  card.innerHTML = '<button id="inspect-close" title="Close">×</button>'
    + (entry.kind === 'fauna' ? faunaCardHtml(entry) : plantCardHtml(entry));
  card.style.display = 'block';
  const btn = document.getElementById('inspect-close');
  if (btn) btn.addEventListener('click', clearSelection);
}

function clearSelection() {
  selection = null;
  clearThreads();
  const card = inspectCard();
  if (card) { card.style.display = 'none'; card.innerHTML = ''; }
}

// ── picking ─────────────────────────────────────────────────────────────────

function pickAt(clientX, clientY) {
  const r = renderer.domElement.getBoundingClientRect();
  _iPtr.x = ((clientX - r.left) / r.width) * 2 - 1;
  _iPtr.y = -((clientY - r.top) / r.height) * 2 + 1;
  _iRay.setFromCamera(_iPtr, camera);
  // Creatures first — they sit in front of the plants they're using, and a
  // click that lands on a bee should be about the bee.
  if (wildlifeGroup && wildlifeGroup.visible) {
    const meshes = [];
    wildlifeGroup.traverse((o) => {
      if (o.isMesh && _critterAt(o)) meshes.push(o);
    });
    const hit = _iRay.intersectObjects(meshes, false);
    if (hit.length) {
      const info = _critterAt(hit[0].object);
      if (info && info.name) return { type: 'fauna', key: info.name };
    }
  }
  if (plantsGroup) {
    const meshes = [];
    plantsGroup.traverse((o) => {
      if (o.isInstancedMesh && o.userData.pickId) meshes.push(o);
    });
    const hits = _iRay.intersectObjects(meshes, false);
    for (const h of hits) {
      const pid = h.object.userData.pickId[h.instanceId];
      if (pid != null) return { type: 'plant', key: pid };
    }
  }
  return null;
}

// A click is only an inspect click when the pointer didn't travel — otherwise
// every camera drag that happens to end on a plant would open a card.
let _downX = 0, _downY = 0, _downT = 0;
renderer.domElement.addEventListener('pointerdown', (e) => {
  _downX = e.clientX; _downY = e.clientY; _downT = performance.now();
});
renderer.domElement.addEventListener('pointerup', (e) => {
  if (beeMode) return;                       // flying: the click is the controls
  if (Math.abs(e.clientX - _downX) > 4 || Math.abs(e.clientY - _downY) > 4) return;
  if (performance.now() - _downT > 700) return;
  const hit = pickAt(e.clientX, e.clientY);
  if (!hit) { clearSelection(); return; }
  const entry = hit.type === 'fauna'
    ? DOSSIER.fauna[hit.key] : DOSSIER.plants[String(hit.key)];
  if (!entry) { clearSelection(); return; }
  selection = hit;
  showCard(entry);
  buildThreads();
});

addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && selection) clearSelection();
});

// The threads are anchored to live creature positions and to plants whose size
// changes with the year slider, so they're rebuilt on the animation loop's
// slower cadence rather than per frame.
let _threadT = 0;
function stepThreads(t) {
  if (!selection || !threadGroup) return;
  // Labels re-scale every frame (they track the camera); the geometry only
  // needs rebuilding as the creatures move.
  for (const o of threadGroup.children) {
    if (o.userData && o.userData.threadLabel) scaleThreadLabel(o);
  }
  if (t - _threadT < 120) return;
  _threadT = t;
  buildThreads();
}

// ── host hook ───────────────────────────────────────────────────────────────
// Pushed alongside each scene by src/scene3d_window.py. Re-selecting after a
// push keeps the card live while the year / season sliders move underneath it.
window.permaSetDossier = function (d) {
  DOSSIER = d && d.plants ? d : { plants: {}, fauna: {} };
  if (!selection) return;
  const entry = selection.type === 'fauna'
    ? DOSSIER.fauna[selection.key] : DOSSIER.plants[String(selection.key)];
  if (entry) { showCard(entry); buildThreads(); } else clearSelection();
};
