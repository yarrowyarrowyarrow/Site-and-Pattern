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

// The species' own photo, above the card, with its credit ALWAYS beneath it.
// The photo is an open-licensed iNaturalist observation, and the licence is only
// honoured if the person who made it is named — so the credit is not optional
// styling, and the dossier refuses to send a photo it cannot attribute
// (scene_dossier._photo). `key` is an opaque cache handle served by the app's
// own loopback route; no remote URL ever reaches this page. If the file has gone
// missing, collapse to no photo rather than showing a broken frame.
function photoBlock(e) {
  const p = e.photo;
  if (!p || !p.key || !p.credit) return '';
  // Not loading="lazy": the card is built only when it opens, so the image is in
  // view the moment it exists — deferring it just delays the photo the user is
  // looking at (and never resolves at all under a headless virtual clock).
  return '<figure class="iphoto"><img src="/__image?k=' + encodeURIComponent(p.key)
    + '" alt="' + esc(e.name) + '" decoding="async"'
    + ' onerror="this.closest(\'figure\').remove()">'
    + '<figcaption>' + esc(p.credit) + '</figcaption></figure>';
}

function plantCardHtml(e) {
  let h = photoBlock(e);
  h += '<div class="ihead"><div class="iname">' + esc(e.name) + '</div>'
    + '<div class="isci">' + esc(e.scientific_name) + '</div></div>';
  h += chips(e.badges, 'good');
  const bits = [];
  if (e.plant_type) bits.push(esc(e.plant_type));
  if (e.sun) bits.push(esc(e.sun));
  if (e.water) bits.push(esc(e.water) + ' water');
  if (e.native) bits.push('native to ' + esc(e.native));
  if (bits.length) h += '<div class="ifacts">' + bits.join(' · ') + '</div>';
  // What it looks like — the same morphology that shapes the model on screen.
  if (e.morphology && e.morphology.length) {
    h += '<div class="ifacts">' + esc(e.morphology.join(' · ')) + '</div>';
  }

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
  let h = photoBlock(e);
  h += '<div class="ihead"><div class="iname">' + esc(e.name) + '</div>'
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

// Picking itself lives in 01-core.js as `scenePick` — one implementation shared
// with the hover tip, which had drifted into a near-duplicate raycaster with a
// different mesh filter. It also carries the hit tolerance that makes small
// plants clickable at all.

// A click is only an inspect click when the pointer didn't travel — otherwise
// every camera drag that happens to end on a plant would open a card. That test
// is ALSO what makes this work while flying or walking: in both first-person
// modes the mouse only turns the camera, so a click that doesn't drag is
// unambiguously "tell me about this". It used to bail out on `beeMode`
// entirely, which cost the educational card exactly where a user is closest to
// the plants.
let _downX = 0, _downY = 0, _downT = 0;
renderer.domElement.addEventListener('pointerdown', (e) => {
  _downX = e.clientX; _downY = e.clientY; _downT = performance.now();
});
renderer.domElement.addEventListener('pointerup', (e) => {
  // Left button only. Since V2.37 left is the PAN verb (01-core.js), so an
  // unfiltered handler would open a plant card on the tail of any small drag,
  // and the right button now rotates — neither gesture means "tell me about
  // this".
  if (e.button !== 0) return;
  if (Math.abs(e.clientX - _downX) > 4 || Math.abs(e.clientY - _downY) > 4) return;
  if (performance.now() - _downT > 700) return;
  const hit = scenePick(e.clientX, e.clientY);
  if (!hit) { clearSelection(); return; }
  const entry = hit.type === 'fauna'
    ? DOSSIER.fauna[hit.key] : DOSSIER.plants[String(hit.key)];
  // A hit we have no dossier entry for is NOT a miss — keep whatever card is
  // open rather than closing it out from under the user, which is what a
  // near-miss used to do.
  if (!entry) return;
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

// ── measurement hook (V2.29) ────────────────────────────────────────────────
// Reports the world-space bounding box the built plants actually occupy, per
// species. This is a diagnostic, not a control: it is the only way to check the
// *composition* of archetype geometry x instance transform, which is exactly
// what was silently wrong for two releases — the assets were correct, the
// instancing was correct in isolation, and together they stretched every tree by
// up to 4.2x. tests/test_scene3d_render.py asserts the measured height/width
// against what the scene asked for; it is also the quickest answer to "why does
// this tree look wrong" when iterating by hand.
//
// Not a permaSet* name on purpose: nothing in map3d_js drives it (the bridge
// contract test would flag it), the same way window.glb* is invisible there.
window.permaMeasure = function () {
  const out = { plants: {}, groups: 0, verts: [], parts: [] };
  if (!plantsGroup) return out;
  const box = new THREE.Box3();
  const tmp = new THREE.Box3();
  plantsGroup.updateMatrixWorld(true);
  plantsGroup.traverse((o) => {
    if (!o.geometry) return;
    // Plant geometry only. The contact-shadow discs live in this group too and
    // are deliberately 1.35x the canopy, so counting them reported every tree
    // and shrub as exactly 35% too wide — a measurement artefact that would
    // have made the render guard cry wolf on every single woody species.
    // userData.pick is the reliable marker: it is set on plant meshes and
    // nothing else.
    if (!o.userData || !o.userData.pick) return;
    // InstancedMesh's own computeBoundingBox folds in every instance matrix;
    // a plain Mesh only has the geometry box. Handle both explicitly rather
    // than relying on which three.js version does what inside setFromObject.
    if (o.isInstancedMesh) {
      o.computeBoundingBox();
      if (!o.boundingBox) return;
      tmp.copy(o.boundingBox);
    } else {
      if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
      if (!o.geometry.boundingBox) return;
      tmp.copy(o.geometry.boundingBox);
    }
    tmp.applyMatrix4(o.matrixWorld);
    box.union(tmp);
    // The archetype's own vertex count. Bounds alone cannot show that a species'
    // recorded leaf outline actually selected a different baked variant — two
    // variants of one form are shaped to the SAME aspect on purpose, so they
    // differ in their mesh, not their box.
    const pos = o.geometry.getAttribute && o.geometry.getAttribute('position');
    if (pos) out.verts.push(pos.count);
    // Per-mesh, because a plant is built from several (a shrub's canes and its
    // foliage are separate InstancedMeshes) and "the plant looks wrong" is
    // usually ONE of them being the wrong size, empty, or not reaching the top —
    // none of which the union box above can show.
    //
    // Report `top` and `base`, not only the height: the bare-shrub regression
    // was foliage that stopped partway UP a full-height plant, and a part's
    // height alone cannot distinguish that from a part that legitimately spans
    // less (a vase shrub's leaves start above its bare lower canes). Measuring
    // the extent instead of the top is what made the first read of that bug
    // look like a partial fix.
    out.parts.push({
      verts: pos ? pos.count : 0,
      n: o.isInstancedMesh ? o.count : 1,
      w: +Math.max(tmp.max.x - tmp.min.x, tmp.max.z - tmp.min.z).toFixed(3),
      h: +(tmp.max.y - tmp.min.y).toFixed(3),
      base: +tmp.min.y.toFixed(3),
      top: +tmp.max.y.toFixed(3),
    });
    out.groups++;
  });
  out.verts.sort((a, b) => a - b);
  // How much of the frame the camera is actually giving the design. "The plant
  // looks wrong" is sometimes "the plant is 4% of the viewport", which no amount
  // of geometry measuring can show — and `camera` is a const in a classic script,
  // so a probe page cannot reach it any other way.
  if (typeof camera !== "undefined" && controls) {
    const dist = camera.position.distanceTo(controls.target);
    out.view = {
      dist_m: +dist.toFixed(2),
      fov: camera.fov,
      // The world height the frame spans at the orbit target.
      visible_h_m: +(2 * dist * Math.tan(camera.fov * Math.PI / 360)).toFixed(2),
    };
  }
  if (out.groups) {
    out.height_m = +(box.max.y - box.min.y).toFixed(3);
    out.width_m = +Math.max(box.max.x - box.min.x,
                            box.max.z - box.min.z).toFixed(3);
  }
  return out;
};

// Does every mesh the viewer builds actually put PIXELS on the screen?
//
// Three separate V2.29 bugs were invisible to every geometry-level check because
// the geometry was right and the image was wrong: shrub foliage that stopped
// partway up the plant, an aster's leaves detached from their stems, and — the
// one this exists for — shrub leaves that were built, budgeted, sized, placed and
// then NOT DRAWN, because the rebuild changed them from closed icosahedra to flat
// ribbons while their material stayed single-sided. Backface culling deleted the
// whole family's foliage in midsummer and no assertion could see it.
//
// So: hide one mesh, re-render, count the pixels that changed. A mesh carrying
// thousands of vertices that changes almost nothing is being culled, occluded, or
// drawn transparent — all bugs. Returns [{verts, n, pixels}] per plant mesh.
//
// Not a permaSet* name, same as permaMeasure: nothing in map3d_js drives it.
window.permaVisibility = function () {
  const out = [];
  if (!plantsGroup || !renderer) return out;
  const gl = renderer.getContext();
  const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
  const shot = () => {
    renderer.render(scene, camera);
    const buf = new Uint8Array(w * h * 4);
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf);
    return buf;
  };
  const meshes = [];
  plantsGroup.traverse((o) => {
    if (o.geometry && o.userData && o.userData.pick) meshes.push(o);
  });
  const base = shot();
  for (const m of meshes) {
    m.visible = false;
    const off = shot();
    m.visible = true;
    let changed = 0;
    for (let i = 0; i < base.length; i += 4) {
      if (base[i] !== off[i] || base[i + 1] !== off[i + 1]
          || base[i + 2] !== off[i + 2]) changed++;
    }
    const pos = m.geometry.getAttribute && m.geometry.getAttribute('position');
    out.push({ verts: pos ? pos.count : 0,
               n: m.isInstancedMesh ? m.count : 1, pixels: changed });
  }
  renderer.render(scene, camera);          // leave the canvas as we found it
  return out;
};

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
