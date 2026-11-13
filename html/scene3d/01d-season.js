// html/scene3d/01d-season.js — the season, as the scene decided it (V3.46, F263).
//
// The V3.43 review's finding 7: seasons were half drawn. seasonalColor
// (01-core.js) tinted a plant by the month's number and nothing else about a
// plant changed, so a perennial stood at its July height in April and was
// green in January's snow; trees went bare in winter and shrubs never did; and
// "November to March" was typed into five chunks.
//
// src/scene_season.py decides the season once, from the region pack's frost
// dates, and this chunk is the one place the viewer reads it:
//   scene.season  {snow, ground, leaves, herbs}     → seasonSnow, seasonGround
//   plant.season  {look, t, up}                     → bodyColor, leafless,
//                                                     diedBack, seasonUp
// It decides nothing. A scene with no `season` (the probes, the legacy
// permaSetPlants hook, anything from before V3.46) and a plant with none (an
// evergreen) are drawn by the old month rules, which live on below.
//
// Loaded after 01c-leaves.js. Nothing here runs per frame except seasonSnow,
// which the falling snow asks (01-core.js updatePrecip) and which is one read.

let sceneSeason = null;       // scene.season; set by permaSetScene before it builds

// ── the month rules, for a scene that does not say ──────────────────────────
const _isDecid = (ft) => ft !== 'evergreen';   // unknown ⇒ deciduous-ish
const _bareMonth = (m) => (m >= 11 || m <= 3);

// Does snow lie?
function seasonSnow(month) {
  return sceneSeason ? !!sceneSeason.snow : _bareMonth(month || 0);
}
// What the unplanted ground is doing: snow | dormant | waking | green | turning.
function seasonGround(month) {
  if (sceneSeason && sceneSeason.ground) return sceneSeason.ground;
  const m = month || 0;
  return _bareMonth(m) ? 'snow' : m === 10 ? 'dormant' : m === 4 ? 'waking' : 'green';
}
// Are the leaves down on woody plants in general? A hedge is one plain mass
// with no plant of its own to ask (02c-site.js).
function seasonLeavesDown(month) {
  return sceneSeason ? sceneSeason.leaves === 'bare' : _bareMonth(month || 0);
}

// ── one plant ───────────────────────────────────────────────────────────────

// A woody plant with its leaves down: its foliage is not drawn. Trees, shrubs
// and vines all ask this one; until V3.46 only trees and vines dropped theirs.
function leafless(p, month) {
  const s = p && p.season;
  return s ? s.look === 'bare' : _isDecid(p && p.foliage_type) && _bareMonth(month);
}
// A herb that is last year's dry stems. What floats on a pond is not drawn then.
function diedBack(p, month) {
  const s = p && p.season;
  return s ? s.look === 'dry' : _isDecid(p && p.foliage_type) && _bareMonth(month);
}
// The share of its height a herb coming up in spring stands at (1 = all of it).
function seasonUp(p) {
  const s = p && p.season;
  return (s && s.up) || 1;
}
// How tall a plant is drawn THIS SEASON: fullBodyHeightOf (04-quality.js, the
// V2.88 answer for the body and everything that sits on it) times seasonUp.
// The flowers, the fruit and the seed heads ask this, so they ride down with a
// short spring plant; src/scene_wildlife.py perches the animals by the same
// two numbers (tests/test_accuracy_render.py keeps them equal).
function bodyHeightOf(p) { return fullBodyHeightOf(p) * seasonUp(p); }

// What each look does to a plant's own colour. src/scene_season.py:LOOKS is
// the list; tests/test_scene_season.py keeps the two equal.
const _YOUNG_GREEN = new THREE.Color('#c8e06a');
const _HELD_BRONZE = new THREE.Color('#8b7355');
// Dry stems: tan for a grass, a darker brown for everything else. Estimates,
// as plain as the rest of the season; no plant's winter colour is recorded.
const _DRY_GRASS = new THREE.Color('#c2ac74'), _DRY_STEM = new THREE.Color('#8e7a56');
const _GRASSY = { grass: 1, sedge: 1, rush: 1 };
function _dryOf(p) { return _GRASSY[p.plant_type] ? _DRY_GRASS : _DRY_STEM; }
const _TMP_COL = new THREE.Color();
const SEASON_LOOK = {
  green: (c) => c,
  young: (c, s) => c.lerp(_YOUNG_GREEN, 0.34 - 0.16 * (s.t || 0)),
  // A recorded autumn colour goes most of the way to it (V2.29); a woody
  // plant without one takes the generic amber, a herb goes toward dry.
  turning: (c, s, p) => {
    const t = s.t == null ? 1 : s.t;
    if (p.fall_color) return c.lerp(_TMP_COL.set(p.fall_color), 0.8 * t);
    if (p.plant_type === 'tree' || p.plant_type === 'shrub' || p.plant_type === 'vine')
      return c.lerp(_TMP_COL.set(_FALL_GENERIC), 0.55 * t);
    return c.lerp(_dryOf(p), 0.8 * t);
  },
  dry: (c, s, p) => c.lerp(_dryOf(p), 0.88),
  held: (c) => c.lerp(_HELD_BRONZE, 0.55),
  bare: (c) => c,                    // nothing of this colour is drawn
};
function seasonColor(p, month) {
  const s = p.season, look = s && SEASON_LOOK[s.look];
  if (!look) return seasonalColor(p.color, p.foliage_type, month, p.fall_color);
  return look(new THREE.Color(p.color || '#66bb6a'), s, p);
}
// A plant body's colour: the season, then decline (witherColor, fadeColor).
// Every body layer asks this one function.
function bodyColor(p, month) {
  return fadeColor(witherColor(seasonColor(p, month), p.health), p.opacity);
}
// A grass holds its seed head on its dry stems right through the winter
// (05-flowers.js gates a head by month, which stopped it at December).
function holdsSeedHead(p) {
  return !!(p.inflorescence_form && p.season && p.season.look === 'dry');
}
