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
// `gain` scales the beat: 1 is full flight, 0 folds the wings to their resting
// `base` angle. Birds use it to fold on the perch and beat while crossing the
// yard; everything else leaves it at 1 and flaps continuously.
//
// `phase` (V2.36) offsets one creature's beat from the next. Without it every
// flier in the scene drives off the same global `t`, so six butterflies beat in
// PERFECT UNISON — the wings were never frozen, but a synchronised swarm reads
// as clockwork rather than as animals, and that is indistinguishable from
// "they don't flap" in any still frame. Every critter already carries a
// `wanderPh` used for its wander and bob; this is the same number.
//
// `skew` is the FRACTION OF THE BEAT SPENT RAISING THE WINGS, 0.5 being the
// plain symmetric sine every taxon used before. A lepidopteran downstroke is
// the power stroke and is quicker than the recovery, so butterflies want a
// value above 0.5: a long unhurried lift, then a snap. A symmetric beat is the
// other half of why these looked mechanical.
//
// `hold` (V2.46) is WHERE THE WING SITS when the beat stops, and it is the
// difference between a glide and a small fast tremble.
//
// Until now `gain` scaled the amplitude, so a gliding butterfly went on
// oscillating at 22% of full sweep *at full rate* — a rapid shiver, which is
// the least butterfly-like thing a butterfly can do, and half of the author's
// report that the flapping is *"too fast and unnatural… visually
// distracting"*. A gliding lepidopteran holds its wings still, in a shallow V
// above the body, and sails.
//
// So `gain` now interpolates the wing between the beat and a held pose rather
// than shrinking the beat. `hold` defaults to `base` — the authored rest angle,
// which is a folded wing — so a perched bird is unchanged, and at gain 1 the
// result is bit-identical to before.
function flapWings(obj, t, gain, phase, extended) {
  const fp = obj.userData.flap;
  if (!fp || !obj.userData.wings) return;
  const g = gain == null ? 1 : gain;
  // Position within the beat, 0..1.
  let u = ((t * fp.speed + (phase || 0)) / (Math.PI * 2)) % 1;
  if (u < 0) u += 1;
  const k = Math.min(0.9, Math.max(0.1, fp.skew == null ? 0.5 : fp.skew));
  // Time-warp: the first `k` of the cycle covers the up-sweep (v: 0→0.5) and
  // the rest covers the down-sweep (v: 0.5→1). Continuous at u=k and u=1, so
  // the wing never jumps. k=0.5 reduces exactly to the old symmetric beat.
  const v = u < k ? 0.5 * (u / k) : 0.5 + 0.5 * ((u - k) / (1 - k));
  const beat = fp.base + (0.5 - 0.5 * Math.cos(v * Math.PI * 2)) * fp.amp;
  // Extended glide (a sailing butterfly, a soaring hawk) holds `fp.hold`;
  // a folded pause (a bounding chickadee) holds the authored rest angle.
  const hold = (extended && fp.hold != null) ? fp.hold : fp.base;
  const w = hold + (beat - hold) * g;
  for (const { pivot, sign } of obj.userData.wings) pivot.rotation.z = sign * w;
}

// The procedural creature BODIES — and the kind→builder table — are in
// 21-critters.js (split out at V2.46d when this file hit its ceiling again).
// The line the split follows is the one 20-walker.js already set: that file is
// what an animal is MADE OF, this one is how it behaves — sized, placed,
// moved, flapped and pitched.
//
// Nothing in 21-critters.js is called from the animation loop, which is the
// property that matters (see _loopFault in 08-modes.js). `rebuildWildlife`
// reaches the table below at RUNTIME, long after every chunk has loaded, and
// guards for it anyway.

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

// ── Life size (V2.46) ────────────────────────────────────────────────────────
//
// Author's report: *"the relative size of the bees, butterflies, birds to the
// person that walks the scene is all wrong. The calligrapher bee seems to be
// the only one rendered smaller/more correctly."*
//
// It was not slightly wrong. Every builder above ends with a hand-chosen
// constant — `g.scale.setScalar(0.9 * (app.size || 1))` — picked by eye in
// V2.12, before there was any morphology to check it against. Measured:
//
//     bee        0.54 m drawn   vs 0.011 m real    27x
//     butterfly  0.83 m         vs 0.079 m          8x
//     bird       0.74 m         vs 0.225 m          6x
//     hoverfly   0.47 m         vs 0.015 m         39x
//
// A bee the size of a cat, beside a 1.75 m walker. There is morphology now —
// bee `body_length_mm`, lep wingspan, and since schema v63 bird `wingspan_mm` —
// so `src/scene_wildlife.py` sends `size: {m, true_m, axis, boost}` per creature
// and the viewer stops deciding how big an animal is (P9).
//
// **Measured, not assumed.** The model is scaled by its own bounding box along
// the named axis, so this is correct for the baked GLBs *and* the procedural
// fallbacks without a table of per-kind fudge factors — and it stays correct if
// somebody re-exports a model at a different size.
//
// ── V2.46c: `m` is the DRAWN size, and the viewer does not choose it ─────────
//
// V2.46 shipped a `Creatures:` multiplier — Life size / x3 / x6 / x12 — to make
// the small ones findable. It was the wrong shape for the problem:
//
//     *"I don't want the birds changing size to x3 or more, they look
//     ridiculous. The bugs are not visible unless x3... I don't know if we need
//     this size changing as a changeable drop down menu."*
//
// Correct on both counts. The thing needing help is not "creatures", it is
// creatures below a few centimetres, and a global knob cannot express that.
// Python now applies a soft **visibility floor** per animal
// (scene_wildlife.VISIBLE_FLOOR_M) — a bee comes up 3x, a goldfinch by 1% —
// and sends the result as `m`, with the honest measurement alongside as
// `true_m` for the label. There is nothing here to set, which is why the
// dropdown is gone rather than merely re-defaulted.

function _extentAlong(obj, axis) {
  obj.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(obj);
  if (box.isEmpty()) return 0;
  const s = box.getSize(new THREE.Vector3());
  return axis === 'x' ? s.x : (axis === 'y' ? s.y : s.z);
}

// Returns the factor applied (1 = left alone), so a caller can size a shadow
// or a label to match.
// ── Whose eyes are you looking through? (V2.46d) ────────────────────────────
//
// The visibility floor is a statement about a HUMAN's view: at two to four
// metres a 11 mm bee is a speck, so it gets drawn at 34 mm. In bee mode that
// premise is gone — you are an insect among insects, at insect distances — and
// the floor becomes actively wrong:
//
//     *"I should be the same size as the other bugs but they are still small
//     compared to me as a bee."*
//
// With the floor on, every other insect is drawn about three times its real
// size while your own body is drawn at exactly its real size, so nothing in the
// scene is comparable to you. Off, a bee you fly up to is the size you are.
let CRITTER_LIFE_SIZE = false;

function setCritterLifeSize(on) {
  const want = !!on;
  if (want === CRITTER_LIFE_SIZE) return;
  CRITTER_LIFE_SIZE = want;
  rebuildWildlife();
  if (wildLabelsOn) { buildWildLabels(); updateRoster(); }
}

function scaleCritterToLife(obj, size) {
  if (!obj || !size || !(size.m > 0)) return 1;
  const have = _extentAlong(obj, size.axis || 'z');
  if (!(have > 1e-6)) return 1;                  // no geometry to measure
  const want = (CRITTER_LIFE_SIZE && size.true_m > 0) ? size.true_m : size.m;
  const k = want / have;
  obj.scale.multiplyScalar(k);
  obj.userData.lifeSize = size;
  obj.userData.lifeScale = k;
  return k;
}

// How big this creature is drawn, in metres — the number the shadow, the label
// offset and the collision radius all key off. Zero for a creature from an
// older scene with no size block, which every caller treats as "leave it".
function drawnSizeOf(obj) {
  const s = obj && obj.userData && obj.userData.lifeSize;
  if (!s || !(s.m > 0)) return 0;
  return (CRITTER_LIFE_SIZE && s.true_m > 0) ? s.true_m : s.m;
}

// One line about how big it really is, for the hover tip and the dossier.
// Mirrors src/scene_wildlife.size_sentence — an animal shown larger than life
// has to say so, or the app teaches that a leafcutter bee is walnut-sized.
function _sizeLine(size) {
  if (!size) return '';
  const trueM = Number(size.true_m || size.m || 0);
  if (!(trueM > 0)) return '';
  const measure = trueM < 0.1 ? Math.round(trueM * 1000) + ' mm'
                              : Math.round(trueM * 100) + ' cm';
  const boost = Number(size.boost || 1);
  return boost >= 1.15
    ? measure + ' — shown ' + Math.round(boost) + '× life size so you can see it'
    : measure + ' — shown life size';
}

function rebuildWildlife() {
  disposeWildlife();
  if (!WILDLIFE.length) return;
  wildlifeGroup = new THREE.Group();
  for (const spec of WILDLIFE) {
    const app = spec.app || { kind: spec.kind };
    // `typeof`-guarded: 21-critters.js loads after this chunk. This runs from
    // permaSetWildlife, long after load, so the guard is belt-and-braces — but
    // the 19-roster.js regression is what belt-and-braces is for.
    const F = (typeof _CRITTER_FACTORY !== 'undefined') ? _CRITTER_FACTORY : {};
    const make = F[spec.kind] || F[app.kind];
    let obj;   // Blender GLB critter first (09-models.js), procedural fallback.
    try { obj = (window.glbCritter && window.glbCritter(spec.kind, app)) || (make && make(app)); }
    catch (e) { continue; }
    if (!obj) continue;
    // Life size, before anything measures or positions it (V2.46).
    scaleCritterToLife(obj, spec.size);
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
                                 rel: spec.rel || '', kind: spec.kind,
                                 onId: spec.on_id,
                                 // How this species flies (V2.36) — see
                                 // _FLIGHT_STYLE. The key matches the column
                                 // name (lepidoptera_attributes.flight_style)
                                 // so there is nothing to rename in between.
                                 // Empty falls back to 'fluttery', the old
                                 // behaviour, which is what an undescribed
                                 // species gets.
                                 flight: (app && app.flight_style) || '',
                                 rest: (app && app.resting_posture) || '',
                                 // How big it really is, and whether the screen
                                 // is exaggerating (V2.46c). This is what the
                                 // removed Creatures: dropdown was actually
                                 // for — except it names the animal, the real
                                 // measurement and the exact factor, only when
                                 // there is one (P5 + P9).
                                 size: _sizeLine(spec.size) };
    const flier = obj.userData.anim === 'flier' || obj.userData.anim === 'hover';
    // The contact shadow follows the animal's real size too — a half-metre
    // smudge under an 11 mm bee is the same mistake in a second place, and it
    // was doing most of the work of making the insects look enormous.
    const drawn = drawnSizeOf(obj);
    const shadow = makeCritShadow(drawn > 0
      ? Math.max(0.05, Math.min(flier ? 0.5 : 0.4, drawn * 2.2))
      : (flier ? 0.5 : 0.4));
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
      // Collision radius (V2.46). Half the animal, floored — a bee is 11 mm and
      // a sub-centimetre radius makes the obstacle test worthless numerically
      // without making it visibly wrong.
      bodyR: Math.max(0.04, drawn * 0.5),
      speed: (0.7 + ((spec.seed || 0) % 50) / 45),   // m/s scale per animal
      wanderPh: ((spec.seed || 0) % 628) / 100,
    });
    // Real wingbeat physics for this species (V2.45, 18-flight.js). Guarded
    // with `typeof` because that chunk loads after this one; without it the
    // authored constants stay in place and the viewer behaves as before.
    if (typeof initFlight === 'function') {
      initFlight(wildlifeCritters[wildlifeCritters.length - 1], spec.flight);
    }
    wildlifeGroup.add(obj);
  }
  // V2.46c (F110): the other animals stay visible in bee mode. This was
  // `!beeMode` — right when the ambient creatures were cat-sized and would have
  // filled a bee's view; wrong now that they are honest, because sharing a
  // flower patch with other pollinators is the point of being down there.
  wildlifeGroup.visible = true;
  scene.add(wildlifeGroup);
}

// Per-taxon travel speed (m/s) + dwell (s) when it reaches a plant.
const _WILD_MOVE = {
  flier:  { spd: 1.6, dwell: 1.6, bob: 0.05 },   // bees: cruise, land & sip
  hover:  { spd: 1.2, dwell: 1.1, bob: 0.06 },   // hummingbird/dragonfly darts
  // V2.45b: 4.5 m/s crossed a 20 m yard in under three seconds, and with
  // the old exponential ease most of that happened in the first half
  // second. Halved so a bird can actually be watched.
  perch:  { spd: 2.2, dwell: 3.2, bob: 0.02 },   // birds: fly, then a long sit
  ground: { spd: 2.2, dwell: 1.4, bob: 0.0 },    // mammals: scurry then freeze
  crawl:  { spd: 0.25, dwell: 2.5, bob: 0.0 },   // beetles: slow amble
};
const _WV = new THREE.Vector3();

// How a lepidopteran flies (V2.36). Six documented styles — a skipper darts, a
// monarch sails, a white flutters, a sphinx moth hangs — and until now every
// one of them used the same single sine. `flight_style` is a real character
// out of any butterfly guide, so the roster carries it per species
// (lepidoptera_attributes.flight_style) and it lands here.
//
//   rate  how fast the wander evolves      side  metres/s of sideways weave
//   lift  metres of vertical wander        roll  radians of bank into the weave
const _FLIGHT_STYLE = {
  fluttery: { rate: 1.00, side: 0.85, lift: 0.30, roll: 0.55 },  // whites, sulphurs
  erratic:  { rate: 1.55, side: 1.25, lift: 0.38, roll: 0.75 },  // blues, crescents
  darting:  { rate: 2.10, side: 0.70, lift: 0.16, roll: 0.35 },  // skippers
  gliding:  { rate: 0.45, side: 0.45, lift: 0.22, roll: 0.30 },  // monarchs, swallowtails
  bobbing:  { rate: 0.80, side: 0.40, lift: 0.55, roll: 0.25 },  // fritillaries, satyrs
  hovering: { rate: 1.30, side: 0.22, lift: 0.10, roll: 0.12 },  // sphinx, clearwings
};

// Two out-of-phase wander channels from three incommensurate sines each.
// Amplitude is normalised to ~±1. The rate ratios (1 : 2.37 : 4.11) are
// irrational-ish on purpose — with harmonics the sum would repeat visibly.
function _wander3(t, ph, rate) {
  const s = t * 0.001 * rate;
  return {
    a: (Math.sin(s * 1.00 + ph) * 0.60 +
        Math.sin(s * 2.37 + ph * 2.1) * 0.28 +
        Math.sin(s * 4.11 + ph * 3.7) * 0.12),
    b: (Math.cos(s * 0.83 + ph * 1.4) * 0.60 +
        Math.cos(s * 1.94 + ph * 2.8) * 0.28 +
        Math.cos(s * 3.62 + ph * 0.6) * 0.12),
  };
}

// Yaw that points a critter's NOSE along (dx, dz).
//
// Every critter model in this app faces -Z: the procedural builders put the
// beak/nose/head at negative z and the tail/abdomen at positive z, and the
// baked GLBs follow the same rule (assetlib/fauna.py: "forward = +Y in Blender
// = -Z in the viewer"). A three.js Y-rotation of θ sends local (0,0,-1) to
// (-sinθ, -cosθ), so the yaw that lands it on (dx, dz) is atan2(-dx, -dz).
//
// This used to be atan2(dx, dz) — which orients +Z, i.e. the TAIL, along the
// travel vector, so every bee, bird, butterfly and hare in the preview flew
// exactly backwards. It is one sign, invisible in a still frame and obvious the
// moment anything moves; a user's eye caught it, no test did. Both call sites
// go through here now so they cannot drift apart again (the spotlight bee had
// its own third variant, atan2(dx, -dz), which mirrored the heading instead).
function critterHeading(dx, dz) {
  return Math.atan2(-dx, -dz);
}

// ── A flying bird is not a perched bird moved sideways (V2.46d) ─────────────
//
//     *"The birds do not look real when they fly. They look like a perched
//     bird. Are we basing their flight path on anything because the bobbing up
//     and down in the air also looks rather unrealistic."*
//
// Two answers. **Yes**, the path is based on something: bounding flight — a
// burst of beats, then wings folded and a genuinely ballistic drop, with the
// dip derived from the pause by s = ¼gt² (src/flight_model.py). For a chickadee
// that is a ~21 cm rise and fall, which is what a small passerine actually
// does.
//
// **But nothing was pitching the bird.** `o.rotation.x` was never touched, so a
// perched pose — nose up, tail down — translated through the air and rose and
// fell inside it like a lift. The bobbing looked wrong because the body was not
// answering to it: a real bird's nose drops as it falls and lifts as it climbs,
// and that attitude is most of what "flying" looks like at a distance.
//
// The pitch is MEASURED off the animal's own motion (vertical speed against
// horizontal) rather than tuned, so it cannot disagree with the physics driving
// the bounce — and it stays right if the bout numbers ever change.
const _PERCH_PITCH = 0.45;         // nose-up, the way a passerine sits on a twig
const _MAX_DIVE = 0.55;            // rad; a songbird does not stoop like a falcon

function _birdAttitude(c, o, flying, dt) {
  let want = _PERCH_PITCH;
  if (flying) {
    const vy = c._prevY == null ? 0 : (o.position.y - c._prevY) / Math.max(1e-4, dt);
    const vh = Math.max(0.2, c._vh || 1.0);
    want = Math.max(-_MAX_DIVE, Math.min(_MAX_DIVE, Math.atan2(vy, vh)));
  }
  c._prevY = o.position.y;
  // Ease, so a bird leaving a perch tips forward over a few frames instead of
  // snapping flat, and flares nose-up as it settles.
  const k = Math.min(1, dt * 6);
  c._pitch = (c._pitch == null ? want : c._pitch + (want - c._pitch) * k);
  o.rotation.x = c._pitch;
}

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
        // Birds fly between perches: a direct flight, then a long sit.
        //
        // V2.45b — CONSTANT SPEED, not a lerp. `c.pos.lerp(tgt, dt * 3.0)` is
        // an exponential ease: it launches the bird at enormous speed and
        // decelerates into the perch. Nothing alive moves like that, and it is
        // the other half of the author's report — *"the birds move too fast for
        // me to see what they are doing"* and *"their flight still does not
        // resemble a natural flight for a bird"*. A real bird holds a roughly
        // steady airspeed and stops by braking at the end.
        //
        // The speed is also halved (see _WILD_MOVE.perch): a chickadee really
        // does cross ten metres in about a second, but a yard is only twenty
        // metres wide and a creature that is gone before you can look at it
        // teaches nothing (P5). This is a deliberate legibility choice, not a
        // claim about airspeed — unlike the wingbeat, which stays exact.
        _WV.multiplyScalar(1 / flat);
        c.pos.addScaledVector(_WV, Math.min(flat, mv.spd * c.speed * dt));
        c.pos.y += (tgt.y - c.pos.y) * Math.min(1, dt * 2.2);
        c._vh = mv.spd * c.speed;        // what _birdAttitude pitches against
        // Not through the house (V2.46). Resolved on the PATH, not on the drawn
        // position, or the bird would keep pushing into the wall and be shoved
        // back out every frame — a jitter instead of a detour.
        if (typeof resolveCritterCollision === 'function')
          resolveCritterCollision(c.pos, c.bodyR, tgt);
        o.position.copy(c.pos);
        // Face the way it is going. Every other travel branch does this; this
        // one never did, so a bird crossed the yard sideways — a gap the V2.29
        // heading fix left because it only touched the generic branch.
        o.rotation.y = critterHeading(tgt.x - c.pos.x, tgt.z - c.pos.z);
      } else {
        _WV.multiplyScalar(1 / flat);
        c.pos.addScaledVector(_WV, Math.min(flat, mv.spd * c.speed * dt));
        // Climb or descend toward the waypoint's own height. Without this a
        // flier keeps the altitude it SPAWNED at for the whole cruise (the
        // horizontal step above deliberately zeroes _WV.y), so a bee that
        // started on a 3 m shrub crossed the yard 3 m over the asters it was
        // heading for. Butterflies used to be the only ones that escaped, via
        // their own bob below.
        c.pos.y += (tgt.y - c.pos.y) * Math.min(1, dt * 1.6);
        // Butterflies/moths flutter: weave off the straight line.
        //
        // This was ONE sine sideways and ONE sine vertically — a smooth, even
        // S-curve, which is a paper plane rather than a butterfly. Real
        // lepidopteran flight is the standard example of an erratic path: it
        // is what makes them hard for a bird to catch, and it is the single
        // most recognisable thing about how they move.
        //
        // Layered incommensurate sines instead. The three rates share no
        // common multiple, so the sum never repeats on any timescale you can
        // watch, and the second/third terms are faster and smaller — direction
        // changes arrive at irregular intervals rather than on a beat.
        // DETERMINISTIC on purpose (no per-frame RNG): the presentation still
        // (F69) re-renders the same scene at the same clock and has to get the
        // same frame back.
        if (c.anim === 'flier' && (o.userData.critterInfo &&
            (o.userData.critterInfo.kind === 'butterfly' || o.userData.critterInfo.kind === 'moth'))) {
          const fs = _FLIGHT_STYLE[(o.userData.critterInfo.flight || '')] ||
                     _FLIGHT_STYLE.fluttery;
          const side = new THREE.Vector3(-_WV.z, 0, _WV.x);
          const wob = _wander3(t, ph, fs.rate);
          c.pos.addScaledVector(side, wob.a * fs.side * dt);
          // Vertical wander is a position offset from the waypoint height, not
          // an accumulation, so a lep cannot drift into the ground.
          c.pos.y = tgt.y + wob.b * fs.lift;
          // Roll into the weave. A butterfly banks hard through a direction
          // change and the flat silhouette is most of what you see, so this
          // does more for the "erratic" read than the path itself.
          o.rotation.z = wob.a * fs.roll;
        }
        if (typeof resolveCritterCollision === 'function')
          resolveCritterCollision(c.pos, c.bodyR, tgt);
        o.position.copy(c.pos);
        o.rotation.y = critterHeading(_WV.x, _WV.z);
      }
    }
    // Height + local idle motion by kind.
    if (c.anim === 'flier' || c.anim === 'hover') {
      const wob = single ? 0.18 : 0.0;            // lone fliers wander in place
      o.position.x = c.pos.x + Math.sin(t * 0.0016 + ph) * wob;
      o.position.z = c.pos.z + Math.cos(t * 0.0019 + ph) * wob;
      o.position.y = (c.dwell > 0 || single ? tgt.y : o.position.y) + Math.sin(t * 0.005 + ph) * mv.bob;
      // A settled butterfly closes its wings over its back and holds them
      // there; only the nectaring shiver remains. `gain` already does exactly
      // this for a perched bird — leps never asked for it, so they went on
      // beating at full amplitude while standing still on a flower.
      const settled = c.dwell > 0 && o.userData.critterInfo &&
                      (o.userData.critterInfo.kind === 'butterfly' ||
                       o.userData.critterInfo.kind === 'moth');
      // The bout envelope: full amplitude through the burst, and through the
      // glide the wings go STILL in a shallow V (V2.46 — they used to keep
      // trembling at 22%). `settled` still wins: a butterfly on a flower has
      // its wings over its back regardless of where its bout was, and it folds
      // them, so that one is deliberately not `extended`.
      flapWings(o, t, settled ? 0.12
                : (typeof beatGain === 'function' ? beatGain(c, t) : 1),
                ph, !settled);
      // ...and the body answers to it. A gliding lep sinks between bursts.
      if (typeof boundOffset === 'function') o.position.y += boundOffset(c, t);
      // Level out of the bank when not weaving, so a lep that arrives mid-turn
      // does not sit on the flower tilted over.
      if (c.dwell > 0) o.rotation.z += (0 - o.rotation.z) * Math.min(1, dt * 3);
      if (c.shadow) c.shadow.position.set(o.position.x, c.anchor.y + 0.02, o.position.z);
    } else if (c.anim === 'perch') {
      const flying = c.dwell <= 0;
      // **The height came from the DESTINATION, not from the flight** (V2.46d).
      // The travel branch above climbs `c.pos.y` toward the next perch, and
      // this line then threw that away and used `tgt.y` — so a bird was drawn
      // at its destination's height for the whole crossing, whatever its own
      // path was doing. The idle bob belongs to a perched bird; in the air the
      // bound offset below is the vertical motion.
      o.position.y = flying ? c.pos.y : tgt.y + Math.sin(t * 0.003 + ph) * mv.bob;
      if (!flying) o.rotation.y = ph + Math.sin(t * 0.0009 + ph) * 0.4;   // look around
      // Wings BEAT in flight and fold on the perch. This branch never called
      // flapWings at all, so every bird in the app sat with its wings locked in
      // the authored rest pose — sticking straight out sideways — and crossed
      // the yard without moving them, while every insect flapped. One of the
      // two independent reasons; the other was an amplitude of zero.
      // A BOUNDING bird folds its wings between bursts; a soaring or
      // flap-gliding one holds them out and rides (V2.46). `extended` picks
      // which pose the pause settles into — perched is always folded.
      flapWings(o, t, c.dwell > 0 ? 0
                : (typeof beatGain === 'function' ? beatGain(c, t) : 1), ph,
                c.dwell <= 0 && !!(c.flight && c.flight.style !== 'bounding'));
      // THE ZIPLINE FIX (V2.45). The horizontal path is still the lerp above,
      // but the height now comes from the wingbeat: a bounding bird climbs on
      // the burst and drops ballistically while its wings are folded. Nothing
      // else in this function made the body answer to the wings at all, which
      // is why a chickadee crossed the yard like a cable car.
      if (flying && typeof boundOffset === 'function') {
        o.position.y += boundOffset(c, t);
      }
      _birdAttitude(c, o, flying, dt);
      if (c.shadow) c.shadow.position.set(o.position.x, c.anchor.y + 0.02, o.position.z);
    } else if (c.anim === 'ground') {
      const hop = c.dwell > 0 ? 0 : Math.abs(Math.sin(t * 0.02 + ph)) * 0.06;
      o.position.y = c.anchor.y + 0.02 + hop;
      if (c.shadow) c.shadow.position.set(o.position.x, c.anchor.y + 0.02, o.position.z);
    } else {                                       // crawl (beetle)
      o.position.y = tgt.y + Math.sin(t * 0.001 + ph) * 0.01;
      if (c.shadow) c.shadow.position.set(o.position.x, c.anchor.y + 0.02, o.position.z);
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
        // Sit the label just clear of the animal, not 28 cm over a bee's head
        // pointing at empty air (V2.46).
        const _d = drawnSizeOf(o);
        const clear = _d ? Math.max(0.05, Math.min(0.28, _d * 1.2)) : 0.28;
        c.label.position.set(o.position.x, o.position.y + clear + hh * 0.7, o.position.z);
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

// The roster, the always-on labels and the "show its plants" spotlight are in
// 19-roster.js (split out at V2.46 when this file hit its ceiling). They are
// *presentation over* the wildlife; everything above is the wildlife itself.
// `wildLabelsOn` and `WILD_SUMMARY` stay declared here because this file
// writes them; 19-roster.js reads them and owns the drawing.
let wildLabelsOn = false;
