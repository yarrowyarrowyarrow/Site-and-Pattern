// html/scene3d/27-views.js — the named viewpoints and the moment in words
// (V3.44, F261).
//
// The V3.43 review's finding 13: no named viewpoints. The window's short
// toolbar offers three (src/scene3d_stops.py: From the street, From the house,
// From above), and each is decided once in Python and only drawn here, so the
// orbit, the stills and the walker cannot disagree about where the street is
// (scene.views, src/scene_views.py).
//
// A new chunk because 08-modes.js, where the camera presets live, has eleven
// lines left. Nothing here runs in the render loop except through the `typeof`
// guards at its two callers (01-core.js: hudText; 07-wildlife.js: the speed
// bar), so a fault here cannot stop the picture (08-modes.js: _loopFault).

// ── where to look from ──────────────────────────────────────────────────────

// How high the eye is, and how high it looks, standing at the house wall.
const _HOUSE_EYE_M = 1.65, _HOUSE_LOOK_M = 0.6;

function _viewFromHouse() {
  const h = lastViews && lastViews.house;
  if (!h) return false;
  const [ex, ey] = h.eye, [lx, ly] = h.look;
  camera.position.set(ex, groundAt(ex, -ey) + _HOUSE_EYE_M, -ey);
  controls.target.set(lx, groundAt(lx, -ly) + _HOUSE_LOOK_M, -ly);
  controls.update();
  return true;
}

// Straight down on the design, north at the top, high enough to hold all of
// it at the window's shape. A hair south of the centre: looking exactly down
// leaves "up" undefined, and from the south the top of the picture is north.
function _viewFromAbove() {
  const b = frameBox();
  if (!b) return false;
  const w = b.max_x - b.min_x, d = b.max_y - b.min_y;
  const cx = (b.min_x + b.max_x) / 2, cz = -(b.min_y + b.max_y) / 2;
  const half = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  const h = Math.max(d / 2, w / 2 / Math.max(0.2, camera.aspect)) / half * 1.08;
  const g = groundAt(cx, cz);
  camera.position.set(cx, g + h, cz + h * 0.004);
  controls.target.set(cx, g, cz);
  controls.update();
  return true;
}

// 'street' | 'house' | 'above' | 'whole'. A view the scene cannot give (no
// building in the outline) is the whole yard too, which is never wrong.
window.permaShowView = function (name) {
  if (!frameBox()) return;
  if (name === 'street') { window.permaSetCameraPreset('sidewalk'); return; }
  if (name === 'house' && _viewFromHouse()) return;
  if (name === 'above' && _viewFromAbove()) return;
  window.permaResetView();
};

// ── the moment, in the toolbar's words ──────────────────────────────────────
// src/scene3d_stops.py:when_words, held equal by tests/test_scene3d_stops.py.
// "Fifth summer", and "Fifth year" in the months a yard is not in its summer.
const _YEAR_WORDS = ['First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth',
  'Seventh', 'Eighth', 'Ninth', 'Tenth', 'Eleventh', 'Twelfth', 'Thirteenth',
  'Fourteenth', 'Fifteenth', 'Sixteenth', 'Seventeenth', 'Eighteenth',
  'Nineteenth', 'Twentieth', 'Twenty-first', 'Twenty-second', 'Twenty-third',
  'Twenty-fourth', 'Twenty-fifth'];
const _COLD_MONTHS = [11, 12, 1, 2, 3];

function whenWords(year, month) {
  const y = Math.round(Number(year) || 0);
  if (y <= 0) return 'Fully grown';
  const unit = _COLD_MONTHS.includes(Number(month) || 7) ? 'year' : 'summer';
  return y <= _YEAR_WORDS.length ? _YEAR_WORDS[y - 1] + ' ' + unit : 'Year ' + y;
}

// ── are the animals what is being looked at? ────────────────────────────────
// The speed bar (07-wildlife.js) sat over every picture. It is for looking at
// an animal, so it shows while one is the subject: walking among them, flying
// as one, Identify, Show its plants, or an animal's card open.
function animalsAreSubject() {
  return !!(walkMode || beeMode || wildLabelsOn || (SPOT && SPOT.length)
    || (selection && selection.type === 'fauna'));
}
