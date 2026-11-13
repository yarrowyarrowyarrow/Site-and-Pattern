// html/scene3d/25b-timeline.js — what the years did to the plan, shown where
// and which (V3.46, F263; the owner's D4).
//
// The V3.43 review's finding 6: the preview quietly kills the plan. Since
// V3.43 the line over the picture has counted the losses ("14 lost to
// shade"), which says how many and nothing a person can act on. The scene now
// carries scene.timeline_notes (src/scene_timeline.py): one note per place,
// with what shades the plants there and which kinds they are. This chunk shows
// them: a button under the line, a short list, and a ring on the ground at
// every spot a note is about.
//
// It decides nothing, and every word it shows is the scene's. The rings lie on
// the ground through onGround (V3.04) and live in designGroup, so a scene push
// disposes them with everything else and showTimeline, called at the end of
// permaSetScene, draws them again while the list is open.
//
// Loaded after 25-cards.js. Nothing here runs per frame, and its one caller in
// an earlier chunk (05-flowers.js) is `typeof`-guarded.

let TL_OPEN = false;          // is the list open (and are the rings drawn)
let TL_PICK = -1;             // the one note ringed; -1 rings them all
const TIMELINE_RING = { shade: 0xe8a23a, short_lived: 0x9aa3ad, self_seeded: 0x5fae6a };
const _TL_RING_M = [0.2, 0.3];     // a ring's inner and outer radius, metres

function _tlNotes() {
  const t = (typeof lastSceneObj !== 'undefined' && lastSceneObj)
    ? lastSceneObj.timeline_notes : null;
  return t && t.notes && t.notes.length ? t : null;
}

function _tlStyle() {
  if (document.getElementById('timeline-style')) return;
  const st = document.createElement('style');
  st.id = 'timeline-style';
  st.textContent = [
    '#timeline-chip { display: block; margin-top: 5px; pointer-events: auto;',
    '  font: inherit; font-size: 12px; color: #1b3a26; cursor: pointer;',
    '  background: #fff; border: 1px solid #7d9a80; border-radius: 6px;',
    '  padding: 2px 10px; min-height: 24px; }',
    '#timeline-chip:hover { background: #eef5ee; }',
    '#timeline-notes { position: absolute; left: 10px; z-index: 6; width: 340px;',
    '  max-width: calc(100% - 20px); max-height: 62%; overflow-y: auto;',
    '  box-sizing: border-box; font-family: system-ui, sans-serif;',
    '  font-size: 13px; line-height: 1.4; color: #eef4ec;',
    '  background: rgba(18,28,20,.9); border: 1px solid #3a5a3a;',
    '  border-radius: 8px; padding: 8px 10px; }',
    '#timeline-notes h4 { margin: 0 0 6px; font-size: 13px; color: #cfe8c8; }',
    '#timeline-notes button { display: block; width: 100%; text-align: left;',
    '  font: inherit; color: #eef4ec; cursor: pointer; min-height: 24px;',
    '  background: rgba(90,140,70,.16); border: 1px solid #3a5a3a;',
    '  border-radius: 6px; padding: 5px 8px; margin: 0 0 6px; }',
    '#timeline-notes button:hover { background: rgba(90,140,70,.32); }',
    '#timeline-notes button.sel { border-color: #b6dfa6; background: rgba(90,140,70,.4); }',
    '#timeline-notes .dot { display: inline-block; width: 10px; height: 10px;',
    '  border-radius: 50%; margin-right: 6px; border: 2px solid; box-sizing: border-box; }',
    '#timeline-notes .kinds { display: block; margin-top: 3px; font-size: 12px; color: #b7c7b0; }',
    '#timeline-notes p { margin: 4px 0 0; font-size: 12px; color: #a9bda2; }',
  ].join('\n');
  document.head.appendChild(st);
}

// A ring on the ground at each spot of each note shown, one mesh per note.
function _tlRings() {
  if (!designGroup) return;
  const old = designGroup.getObjectByName('timeline-rings');
  if (old) { disposeDesignGroup(old); designGroup.remove(old); }
  const t = _tlNotes();
  if (!TL_OPEN || !t) return;
  const group = new THREE.Group();
  group.name = 'timeline-rings';
  t.notes.forEach((note, i) => {
    const spots = note.spots || [];
    if (!spots.length || (TL_PICK >= 0 && TL_PICK !== i)) return;
    const mesh = new THREE.InstancedMesh(
      new THREE.RingGeometry(_TL_RING_M[0], _TL_RING_M[1], 24).rotateX(-Math.PI / 2),
      new THREE.MeshBasicMaterial({ color: TIMELINE_RING[note.kind] || 0xffffff,
        side: THREE.DoubleSide, depthWrite: false, polygonOffset: true,
        polygonOffsetFactor: -8, polygonOffsetUnits: -16 }), spots.length);
    spots.forEach(([x, y], k) => {
      onGround(x, y, lastTerrain, 0.05);          // sets _v and _q (02-plants.js)
      _s.set(1, 1, 1); _m.compose(_v, _q, _s);
      mesh.setMatrixAt(k, _m);
    });
    mesh.name = 'timeline-rings:' + i;
    mesh.userData.note = note.kind;
    mesh.renderOrder = 20;
    group.add(mesh);
  });
  designGroup.add(group);
}

function _tlPanel(t) {
  let panel = document.getElementById('timeline-notes');
  if (!TL_OPEN || !t) { if (panel) panel.remove(); return; }
  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'timeline-notes';
    panel.setAttribute('role', 'region');
    panel.setAttribute('aria-label', 'What the years changed');
    document.body.appendChild(panel);
  }
  const hud = document.getElementById('hud').getBoundingClientRect();
  panel.style.top = Math.round(hud.bottom + 6) + 'px';
  panel.textContent = '';
  const h = document.createElement('h4');
  h.textContent = 'By ' + t.when;
  panel.appendChild(h);
  t.notes.forEach((note, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = TL_PICK === i ? 'sel' : '';
    b.setAttribute('aria-pressed', TL_PICK === i ? 'true' : 'false');
    b.title = TL_PICK === i ? 'Ring every spot again' : 'Ring only these spots';
    const dot = document.createElement('span');
    dot.className = 'dot';
    dot.style.borderColor = '#' + (TIMELINE_RING[note.kind] || 0xffffff)
      .toString(16).padStart(6, '0');
    b.appendChild(dot);
    b.appendChild(document.createTextNode(note.text || ''));
    if (note.kinds) {
      const k = document.createElement('span');
      k.className = 'kinds';
      k.textContent = note.kinds;
      b.appendChild(k);
    }
    b.onclick = () => { TL_PICK = TL_PICK === i ? -1 : i; showTimeline(i); };
    panel.appendChild(b);
  });
  if (t.about) {
    const p = document.createElement('p');
    p.textContent = t.about;
    panel.appendChild(p);
  }
}

// The button under the line at the top left, the list and the rings, for the
// scene on screen. `focus`: true puts the keyboard back on the button, a
// number on that note's row, after a click rebuilt them.
function showTimeline(focus) {
  const hud = document.getElementById('hud'), t = _tlNotes();
  const was = document.getElementById('timeline-chip');
  if (was) was.remove();
  if (!t) { TL_OPEN = false; TL_PICK = -1; }
  if (t && TL_PICK >= t.notes.length) TL_PICK = -1;
  if (t && hud) {
    _tlStyle();
    const b = document.createElement('button');
    b.id = 'timeline-chip';
    b.type = 'button';
    b.textContent = TL_OPEN ? 'Hide where' : 'Show where, and which plants';
    b.setAttribute('aria-expanded', TL_OPEN ? 'true' : 'false');
    b.onclick = () => { TL_OPEN = !TL_OPEN; TL_PICK = -1; showTimeline(true); };
    hud.appendChild(b);
    if (focus === true) b.focus();
  }
  _tlPanel(t);
  _tlRings();
  if (typeof focus === 'number') {
    const rows = document.querySelectorAll('#timeline-notes button');
    if (rows[focus]) rows[focus].focus();
  }
}
// A scene pushed while this chunk was still loading has its button too.
if (_tlNotes()) showTimeline();
