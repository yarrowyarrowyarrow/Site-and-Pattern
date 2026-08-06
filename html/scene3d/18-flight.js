// 18-flight.js — wingbeats that come from the animal (V2.45).
//
// Design principle P9 (ship ranges, never false precision) and P5 (make the
// invisible visible) — see docs/DESIGN_PHILOSOPHY.md. The physics and every
// number are in src/flight_model.py; this file only spends them.
//
// Author's report: birds *"are just gliding as if along a zip line"*,
// butterflies should flap *"fast, fast, slow"*, and it *"should be
// mathematically correct"*.
//
// ── What was actually wrong ─────────────────────────────────────────────────
//
// Two separate faults, and the second is the one that mattered:
//
// 1. `flapWings` (07-wildlife.js) is a good function fed by hardcoded
//    constants — `{ base: 0.2, amp: 0.75, speed: 0.09 }`. `speed` was a raw
//    multiplier on the millisecond clock: not hertz, not derived from
//    anything, and identical for every species in a taxon.
//
// 2. **The body path and the wings were completely decoupled.** A bird crossed
//    the yard on `c.pos.lerp(tgt, dt * 3.0)` — a smooth exponential ease — no
//    matter what its wings were doing. That decoupling *is* the zipline. You
//    can beat the wings perfectly and the bird still slides, because nothing
//    it does with them changes where it goes.
//
// So this file does three things: real hertz, a bout envelope, and — the
// actual fix — a body offset that comes *from* the bout.
//
// ── The bout, and why the pause is the whole point ──────────────────────────
//
// A bounding chickadee flaps 4–9 beats, folds its wings, and travels
// ballistically for a fifth of a second, dropping a few centimetres. Then it
// does it again. That rise-and-fall is what a small bird looks like at fifty
// metres, and it is the single most recognisable thing about how one flies.
//
// A butterfly does the slower version: a burst of beats, then a glide with the
// wings held in a shallow V, sinking gently. Same envelope, different numbers.
//
// A bee never stops at all.
//
// The pause length and the dip come from Python, where the dip is derived from
// the pause by s = ¼gt² — so a longer pause really does drop the bird further,
// rather than the two being tuned separately until they looked right.
//
// ── Blur, and the honest limit ──────────────────────────────────────────────
//
// A bumblebee beats at ~160 Hz. At 60 fps the fastest thing that can be
// sampled is 30 Hz, so animating a bee's wings at their true rate produces a
// slow backwards flutter — the wagon-wheel effect — which is confidently
// wrong. Python marks those `render:'blur'` and this holds the wing at
// mid-sweep, translucent, with a shimmer well under the limit. That is also
// all anybody has ever actually seen of a bee's wings.

// ── Setup ────────────────────────────────────────────────────────────────────

// `flapWings` advances its beat as `t * fp.speed / 2π` with t in milliseconds.
// For f hertz we want one full cycle per 1000/f ms, so speed = 2πf/1000. That
// one line is what turns a magic number into a measured frequency, and it is
// why flapWings itself did not have to change.
function hzToFlapSpeed(hz) { return (2 * Math.PI * Math.max(0.01, hz)) / 1000; }

function initFlight(c, flight) {
  // No flight block (an older scene, a creature with no morphology) leaves the
  // authored constants in place, so this chunk is purely additive.
  if (!flight || !flight.hz) { c.flight = null; return; }
  c.flight = flight;
  c.beatPhase = ((c.seed || 0) % 100) / 100;      // desynchronise the flock
  const fp = c.obj && c.obj.userData && c.obj.userData.flap;
  if (fp) {
    fp.speed = hzToFlapSpeed(flight.hz);
    // Blur: the wing stops being a wing, so it should not swing far either.
    if (flight.render === 'blur') fp.amp = (fp.amp || 0.75) * 0.35;
  }
  if (flight.render === 'blur') _makeWingsBlurry(c.obj);
  // Put the number where a person can read it (P5). The hover tip and the
  // dossier both draw from critterInfo, so setting it here means the label and
  // the animation cannot disagree about what the animal is doing.
  const info = c.obj && c.obj.userData && c.obj.userData.critterInfo;
  if (info) info.beat = flightLabel(c);
}

// A blurred wing is translucent and doubled in the sweep direction — the
// envelope the wing passes through, rather than the wing.
function _makeWingsBlurry(obj) {
  if (!obj || !obj.userData || !obj.userData.wings) return;
  for (const { pivot } of obj.userData.wings) {
    pivot.traverse((o) => {
      if (!o.material) return;
      const m = o.material.clone ? o.material.clone() : o.material;
      m.transparent = true;
      m.opacity = Math.min(m.opacity == null ? 1 : m.opacity, 0.38);
      m.depthWrite = false;
      o.material = m;
      o.scale.y = Math.max(o.scale.y, 1.0) * 1.35;
    });
  }
}

// ── The bout envelope ────────────────────────────────────────────────────────

// Where in the flap-then-glide cycle this animal is, 0..1 through the FLAP and
// -1 while gliding. Continuous fliers are always flapping.
function _boutPhase(c, t) {
  const f = c.flight;
  if (!f || !f.burst || !f.pause_s) return 1;      // continuous — never rests
  const beatMs = 1000 / Math.max(0.01, f.hz);
  const burstMs = beatMs * f.burst;
  const pauseMs = f.pause_s * 1000;
  const cycle = burstMs + pauseMs;
  if (cycle <= 0) return 1;
  let u = ((t + c.beatPhase * cycle) % cycle);
  if (u < 0) u += cycle;
  return u < burstMs ? (u / burstMs) : -((u - burstMs) / pauseMs);
}

// Wing amplitude right now: full through the burst, closed through the glide.
// Eased at both ends — a bird does not stop its wings dead, it finishes the
// stroke it is on.
function beatGain(c, t) {
  if (!c || !c.flight) return 1;
  const p = _boutPhase(c, t);
  if (p >= 0) return 1;
  const g = -p;                                    // 0..1 through the pause
  const closing = Math.min(1, g / 0.18);           // fold over the first 18%
  const opening = Math.min(1, (1 - g) / 0.18);     // and unfold at the end
  const folded = c.flight.style === 'bounding' ? 0.0 : 0.22;   // gliders hold a V
  return folded + (1 - folded) * (1 - Math.min(closing, opening));
}

// **The zipline fix.** Metres to add to this animal's height right now,
// straight out of the bout: it rises while the wings are working and falls
// while they are not. Returned as an offset so the caller keeps owning the
// path — this only makes the path answer to the wings.
function boundOffset(c, t) {
  if (!c || !c.flight || !c.flight.dip_m) return 0;
  const p = _boutPhase(c, t);
  const dip = c.flight.dip_m;
  if (p >= 0) {
    // Climbing through the burst: a half-cosine so the top is smooth.
    return dip * 0.5 * (1 - Math.cos(Math.PI * p));
  }
  // Falling through the glide. Ballistic for a bounding bird (it really is in
  // free fall with its wings shut); a gentle linear sink for a glider, whose
  // extended wings are still carrying it.
  const g = -p;
  return c.flight.style === 'bounding'
    ? dip * (1 - g * g)
    : dip * (1 - g) * 0.5;
}

// Is this animal's beat too fast to draw honestly?
function flightIsBlur(c) {
  return !!(c && c.flight && c.flight.render === 'blur');
}

// One line for the dossier — the same sentence Python would write, so the card
// and the animation cannot disagree about what the animal is doing.
function flightLabel(c) {
  const f = c && c.flight;
  if (!f) return '';
  const basis = f.basis === 'measured' ? 'measured'
              : f.basis === 'extrapolated' ? 'extrapolated' : 'estimated';
  let s = f.true_hz + ' wingbeats/sec (' + basis + ')';
  if (f.burst) s += ' · ' + f.burst + ' beats then a glide';
  // The screen is not showing this rate, and must not imply that it is (P9).
  if (f.render === 'slowed') s += ' · shown slowed — too fast to draw at speed';
  if (f.render === 'blur') s += ' · too fast to draw, shown as a blur';
  return s;
}

// ── Diagnostic ───────────────────────────────────────────────────────────────

// `window.permaFlightReport()` — what every creature in the scene is actually
// doing with its wings, right now.
//
// This exists because "the birds still aren't flapping" took a session to
// diagnose from the outside, and the answer turned out to be that
// `userData.wings` was never set on the baked bird — a fact invisible from the
// Python side, invisible in the scene JSON, and invisible on screen except as
// an absence. One call now answers it.
window.permaFlightReport = function () {
  const out = [];
  const list = (typeof wildlifeCritters !== 'undefined') ? wildlifeCritters : [];
  const now = (typeof performance !== 'undefined') ? performance.now() : 0;
  for (const c of list) {
    const o = c.obj, ud = (o && o.userData) || {};
    const info = ud.critterInfo || {};
    out.push({
      name: info.name || '',
      kind: info.kind || '',
      anim: c.anim,
      // The three things that have to ALL be true for a wing to move.
      hasWings: !!(ud.wings && ud.wings.length),
      hasFlap: !!ud.flap,
      flapSpeed: ud.flap ? Number(ud.flap.speed.toFixed(4)) : null,
      // …and the two that decide how far it moves right now.
      hz: c.flight ? c.flight.true_hz : null,
      render: c.flight ? c.flight.render : null,
      gain: Number(beatGain(c, now).toFixed(2)),
      dwelling: c.dwell > 0,
    });
  }
  return out;
};

// A one-line summary for the console: the creatures that CANNOT flap, and why.
window.permaFlightProblems = function () {
  return window.permaFlightReport()
    .filter((r) => !r.hasWings || !r.hasFlap)
    .map((r) => r.name + ' (' + r.kind + '): '
         + (!r.hasWings ? 'no wing pivots' : 'no flap params'));
};
