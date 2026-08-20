/* html/botany/diagrams.js — the botanical vocabulary, drawn (V2.36).
 *
 * Design principle P5 — see docs/DESIGN_PHILOSOPHY.md
 *
 * The catalogue asks a person to choose "corymb" or "cyme", "ovate" or
 * "obovate", from a dropdown of bare words. Nobody can do that reliably, and
 * the tuning bench had been asking it for a whole release — which means some
 * share of the 307 described species carry a term somebody guessed at. A word
 * you cannot picture is not a control; it is a coin flip with extra steps.
 *
 * So: every term in the three vocabularies that describe a plant's SHAPE gets
 * a line drawing, generated here as inline SVG. No image files, no external
 * references — the artifact CSP forbids them, the frozen build would have to
 * ship them, and a drawing defined as code can be corrected in one line.
 *
 * Drawn from the botanical definitions, not traced from any published figure.
 * A raceme is a raceme; the drawing is ours. See docs/DATA_SOURCES.md for why
 * that distinction is kept carefully in this project.
 *
 * THE TWO THINGS THE DRAWINGS ARE FOR
 *   1. The bench (html/tune_morphology.html) — a diagram beside every
 *      dropdown, and a full comparison chart one click away.
 *   2. docs/BOTANY_FIELD_GUIDE.md — the same drawings, as a glossary to read
 *      away from the screen with a flora open.
 * A future plant-identification lesson (F83) is the third, and is the reason
 * this lives in html/botany/ rather than inside the dev tool.
 *
 * Classic script, shared globals — the repo's convention for browser JS
 * (see html/map/*.js). Not an ES module.
 */
(function (global) {
'use strict';

// ── palette ────────────────────────────────────────────────────────────────
// Semantic, following the convention the botany texts use: green axis, orange
// flower, brown bract. Mid-tone on purpose — the same drawings appear on the
// bench's dark panel (#1e261e) and on a white docs page, so nothing may rely
// on the background being either. Labels are NOT drawn inside the SVG; they
// live in the surrounding HTML where they inherit the page's text colour.
var C = {
  stem:   '#6f9e57',
  fill:   'rgba(111,158,87,0.30)',
  vein:   'rgba(111,158,87,0.75)',
  flower: '#e8a33d',
  bud:    '#b8842f',
  bract:  '#a67c52',
  mark:   '#9a9a8e'
};

// ── tiny helpers ───────────────────────────────────────────────────────────

function n(v) { return Math.round(v * 100) / 100; }

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function line(x1, y1, x2, y2, colour, w, dash) {
  return '<path d="M' + n(x1) + ',' + n(y1) + 'L' + n(x2) + ',' + n(y2) +
    '" fill="none" stroke="' + (colour || C.stem) +
    '" stroke-width="' + (w == null ? 2.2 : w) + '" stroke-linecap="round"' +
    (dash ? ' stroke-dasharray="' + dash + '"' : '') + '/>';
}

/* An open flower is filled; a bud is a hollow ring. This is not decoration —
 * it is how the determinate/indeterminate distinction is drawn. A raceme's
 * open flowers are at the BOTTOM and its buds at the top; a cyme's open
 * flower is at the TOP CENTRE and its buds outside it. That one difference
 * separates the two architectures people most often confuse, and it is
 * visible in the field on any plant in bloom. */
function dot(x, y, r, bud) {
  if (bud) {
    return '<circle cx="' + n(x) + '" cy="' + n(y) + '" r="' + n(r) +
      '" fill="none" stroke="' + C.bud + '" stroke-width="1.5"/>';
  }
  return '<circle cx="' + n(x) + '" cy="' + n(y) + '" r="' + n(r) +
    '" fill="' + C.flower + '"/>';
}

/* The chevron that means "this axis has not finished". An indeterminate
 * inflorescence has no terminal flower — the tip is a growing point that
 * keeps making more. Determinate ones get a flower here instead. */
function growTip(x, y) {
  return '<path d="M' + n(x - 4) + ',' + n(y + 5) + 'L' + n(x) + ',' + n(y) +
    'L' + n(x + 4) + ',' + n(y + 5) + '" fill="none" stroke="' + C.mark +
    '" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>';
}

// ── the blade generator ────────────────────────────────────────────────────
/* Eleven of the nineteen leaf shapes are ONE shape varying in two numbers:
 * where along the blade it is widest, and how sharply it tapers at each end.
 * That is not a shortcut — it is what the terms actually mean. Lanceolate,
 * elliptic, ovate and obovate differ only in where the widest point sits;
 * drawing them from a shared function keeps that relationship true, and makes
 * the family legible instead of nineteen unrelated pictures.
 *
 * halfWidth(t) gives the blade's half-width at t, t=0 at the stalk and t=1 at
 * the tip. The outline is that curve mirrored. */
function bladePath(halfWidth, opts) {
  opts = opts || {};
  var N = opts.samples || 96;
  var L = opts.length == null ? 74 : opts.length;
  var y0 = opts.y0 == null ? 88 : opts.y0;
  var cx = opts.cx == null ? 50 : opts.cx;
  var d = [], i, t;
  for (i = 0; i <= N; i++) {
    t = i / N;
    d.push((i ? 'L' : 'M') + n(cx + halfWidth(t)) + ',' + n(y0 - t * L));
  }
  for (i = N; i >= 0; i--) {
    t = i / N;
    d.push('L' + n(cx - halfWidth(t)) + ',' + n(y0 - t * L));
  }
  return d.join('') + 'Z';
}

/* maxW      half-width at the widest point
 * widestAt  where that point sits, 0 at the stalk to 1 at the tip
 * blunt     how sharply the blade tapers at BOTH ends
 *
 * The curve is t^A·(1−t)^B normalised to its own peak, with A and B set from
 * `widestAt` and `blunt`. Two properties earn it over a pair of power curves:
 * it is smooth across the widest point (a piecewise taper leaves a visible
 * corner there, which was drawing ovate as a diamond), and `blunt` = 1 is
 * exactly an ellipse — so 0.4 is a strap with parallel sides, 1.5 is drawn out
 * to a point, and the number means something.
 *
 * It also gets ovate right for free: with the widest point low, the short base
 * side reads rounded and the long tip side reads drawn-out, which is precisely
 * what separates ovate from obovate. */
function profile(maxW, widestAt, blunt) {
  var S = blunt == null ? 1.1 : blunt;
  var A = Math.max(0.05, widestAt * S), B = Math.max(0.05, (1 - widestAt) * S);
  var peak = Math.pow(widestAt, A) * Math.pow(1 - widestAt, B);
  return function (t) {
    if (t <= 0 || t >= 1) return 0;
    return maxW * Math.pow(t, A) * Math.pow(1 - t, B) / peak;
  };
}

/* Lobes and deep cuts, as a modulation of a blade profile rather than a
 * different kind of drawing — because lobed → pinnatifid → pinnately compound
 * IS one continuum, distinguished only by how far the cuts reach toward the
 * midrib. `depth` 0 is an uncut blade and 1 is cut clean to the rib. */
function cut(base, lobes, depth) {
  return function (t) {
    var m = 1 - depth * 0.5 * (1 - Math.cos(2 * Math.PI * lobes * t));
    return base(t) * Math.max(0.06, m);
  };
}

function blade(halfWidth, opts) {
  opts = opts || {};
  var L = opts.length == null ? 74 : opts.length;
  var y0 = opts.y0 == null ? 88 : opts.y0;
  var cx = opts.cx == null ? 50 : opts.cx;
  var out = '<path d="' + bladePath(halfWidth, opts) + '" fill="' + C.fill +
    '" stroke="' + C.stem + '" stroke-width="1.6" stroke-linejoin="round"/>';
  if (opts.midrib !== false) {
    out += line(cx, y0 - L * 0.02, cx, y0 - L * 0.95, C.vein, 1.1);
  }
  return out;
}

/* One leaflet, or one leaf on a stem: a blade grown from (cx,cy) and rotated
 * so it points `angle` degrees off vertical. */
function leaflet(cx, cy, len, wid, angle, opts) {
  opts = opts || {};
  var p = profile(wid, opts.widestAt == null ? 0.42 : opts.widestAt,
                  opts.blunt == null ? 1.25 : opts.blunt);
  var body = blade(p, { length: len, y0: cy, cx: cx, samples: 48,
                        midrib: opts.midrib });
  return '<g transform="rotate(' + n(angle) + ' ' + n(cx) + ' ' + n(cy) +
    ')">' + body + '</g>';
}

// ═══════════════════════════════════════════════════════════════════════════
// LEAF SHAPES
// ═══════════════════════════════════════════════════════════════════════════

var LEAF_SHAPE_ORDER = [
  // Simple blades, in the order the widest point travels up the leaf — which
  // is the order that makes the family make sense.
  'needle', 'awl', 'scale', 'linear', 'lanceolate', 'elliptic', 'ovate',
  'obovate', 'spatulate', 'orbicular',
  // Blades with a notched or lobed base.
  'cordate', 'reniform', 'sagittate',
  // The cut continuum: shallow → deep → all the way through.
  'lobed', 'pinnatifid', 'trifoliate', 'compound_pinnate',
  'compound_palmate', 'bipinnate'
];

/* A short leaf stalk, drawn below the blade so the base of the blade reads as
 * a base rather than as a cut-off. */
function petiole(y0) {
  return line(50, 96, 50, y0 == null ? 88 : y0, C.stem, 2.0);
}

var LEAF_SHAPES = {

  needle: function () {
    // Drawn as a pair, because a needle in isolation reads as a line and the
    // thing that makes it a needle is that it is stiff and round in section.
    return leaflet(50, 90, 76, 2.8, -5, { widestAt: 0.5, blunt: 0.32, midrib: false }) +
           leaflet(50, 90, 70, 2.6, 9, { widestAt: 0.5, blunt: 0.32, midrib: false });
  },

  awl: function () {
    return petiole(86) +
      blade(profile(7.5, 0.16, 1.5), { length: 70, y0: 86, midrib: false });
  },

  scale: function () {
    // Appressed and overlapping, like shingles — the adult cedar/juniper twig
    // that reads as a braid rather than as a stem with leaves stuck on it.
    // Opaque fill here alone: with the translucent one used everywhere else
    // the overlaps cancel out and eight scales read as a string of beads,
    // which is the opposite of the thing being illustrated.
    var out = line(50, 94, 50, 18, C.stem, 2.6), i, y, s;
    for (i = 0; i < 9; i++) {
      y = 90 - i * 8;                       // bottom-up: each overlaps the last
      s = i % 2 ? 1 : -1;
      out += '<path d="M' + n(50 - s * 2) + ',' + n(y) +
        ' L' + n(50 + s * 8.5) + ',' + n(y - 4.5) +
        ' L' + n(50 + s * 6) + ',' + n(y - 12) +
        ' L' + n(50 - s * 2.5) + ',' + n(y - 8.5) + ' Z"' +
        ' fill="#3c5c33" stroke="' + C.stem + '" stroke-width="1.2"' +
        ' stroke-linejoin="round"/>';
    }
    return out;
  },

  // blunt: 1.0 is exactly an ellipse. Below that the sides run parallel;
  // above it the blade is drawn out toward its ends.
  linear:     function () { return petiole(88) + blade(profile(6.5, 0.50, 0.40), { length: 78 }); },
  lanceolate: function () { return petiole(88) + blade(profile(13,  0.33, 1.45), { length: 78 }); },
  elliptic:   function () { return petiole(88) + blade(profile(20,  0.50, 1.15), { length: 74 }); },
  ovate:      function () { return petiole(88) + blade(profile(24,  0.36, 1.20), { length: 74 }); },
  obovate:    function () { return petiole(88) + blade(profile(24,  0.64, 1.20), { length: 74 }); },
  // Spatulate and obovate are both widest above the middle; what separates a
  // spoon is the LONG narrow taper to the base, which is the higher `blunt`.
  spatulate:  function () { return petiole(92) + blade(profile(21,  0.70, 1.85), { length: 80 }); },
  orbicular:  function () { return petiole(88) + blade(profile(33,  0.50, 1.00), { length: 66 }); },

  cordate: function () {
    return petiole(86) +
      '<path d="M50,14 C64,24 84,42 84,57 C84,71 74,86 62,86 C56,86 52,82 50,76' +
      ' C48,82 44,86 38,86 C26,86 16,71 16,57 C16,42 36,24 50,14 Z" fill="' +
      C.fill + '" stroke="' + C.stem + '" stroke-width="1.6" stroke-linejoin="round"/>' +
      line(50, 82, 50, 20, C.vein, 1.1);
  },

  reniform: function () {
    return petiole(82) +
      '<path d="M50,26 C69,26 85,40 85,55 C85,69 73,80 61,80 C55,80 51,76 50,71' +
      ' C49,76 45,80 39,80 C27,80 15,69 15,55 C15,40 31,26 50,26 Z" fill="' +
      C.fill + '" stroke="' + C.stem + '" stroke-width="1.6" stroke-linejoin="round"/>' +
      line(50, 77, 50, 32, C.vein, 1.1);
  },

  sagittate: function () {
    // The two lobes point BACKWARDS past where the stalk joins — that is the
    // whole term, and it is what separates it from a plain cordate base.
    return line(50, 96, 50, 74, C.stem, 2.0) +
      '<path d="M50,10 C58,28 65,45 67,58 C69,71 70,80 70,90 C61,85 54,77 52,66' +
      ' L52,60 L48,60 L48,66 C46,77 39,85 30,90 C30,80 31,71 33,58' +
      ' C35,45 42,28 50,10 Z" fill="' + C.fill + '" stroke="' + C.stem +
      '" stroke-width="1.6" stroke-linejoin="round"/>' +
      line(50, 64, 50, 16, C.vein, 1.1);
  },

  // ── the cut continuum ────────────────────────────────────────────────────
  lobed: function () {
    // Few, deep, ROUNDED lobes with the notches stopping well short of the
    // midrib. An oak. Compare the next cell: same drawing, deeper cuts.
    return petiole(88) +
      blade(cut(profile(26, 0.52, 1.05), 2.5, 0.52), { length: 74, samples: 200 });
  },

  pinnatifid: function () {
    // Cut almost to the midrib — but the blade is still one continuous piece,
    // and that strip down the middle is the whole distinction from compound.
    return petiole(88) +
      blade(cut(profile(24, 0.50, 1.10), 4.5, 0.86), { length: 76, samples: 240 });
  },

  trifoliate: function () {
    // Three, and they must read as three — so the laterals are swung well out
    // rather than tucked against the terminal leaflet.
    return line(50, 96, 50, 62, C.stem, 2.0) +
      leaflet(50, 62, 34, 10, 0, { widestAt: 0.60 }) +
      leaflet(50, 62, 30, 9, -62, { widestAt: 0.60 }) +
      leaflet(50, 62, 30, 9, 62, { widestAt: 0.60 });
  },

  compound_pinnate: function () {
    // Leaflets in two rows along a central stalk. Cut all the way through:
    // each leaflet has its own base, and there is bare rachis between them.
    var out = line(50, 94, 50, 30, C.stem, 2.0), i, y;
    for (i = 0; i < 4; i++) {
      y = 78 - i * 13;
      out += leaflet(50, y, 24, 7.5, 68) + leaflet(50, y, 24, 7.5, -68);
    }
    return out + leaflet(50, 32, 22, 7, 0);
  },

  compound_palmate: function () {
    // Five from ONE point, splayed like fingers. Narrower than the pinnate
    // leaflets on purpose: at these angles anything wider closes into a
    // rosette and stops reading as separate leaflets at all.
    var out = line(50, 96, 50, 84, C.stem, 2.0), i;
    var ang = [-72, -36, 0, 36, 72], len = [34, 42, 46, 42, 34];
    for (i = 0; i < 5; i++) {
      out += leaflet(50, 84, len[i], len[i] * 0.20, ang[i],
                     { widestAt: 0.55, blunt: 1.5 });
    }
    return out;
  },

  bipinnate: function () {
    // Twice divided: each division of a pinnate leaf is ITSELF pinnate. Kept
    // deliberately sparse — the point is that you can see the second order of
    // division, and a realistic yarrow leaf at this size is just a green
    // smudge. This is the reason `ferny` exists as a growth form.
    function pinna(y, angle) {
      var g = line(50, y, 50, y - 26, C.stem, 1.4), k, yy;
      for (k = 0; k < 2; k++) {
        yy = y - 8 - k * 10;
        g += leaflet(50, yy, 13, 2.9, 70, { midrib: false, blunt: 1.35 }) +
             leaflet(50, yy, 13, 2.9, -70, { midrib: false, blunt: 1.35 });
      }
      g += leaflet(50, y - 26, 11, 2.6, 0, { midrib: false, blunt: 1.35 });
      return '<g transform="rotate(' + n(angle) + ' 50 ' + n(y) + ')">' + g + '</g>';
    }
    var out = line(50, 94, 50, 30, C.stem, 2.0), i, y;
    for (i = 0; i < 2; i++) {
      y = 80 - i * 24;
      out += pinna(y, 66) + pinna(y, -66);
    }
    return out + pinna(32, 0);
  }
};

// Where the blade is widest is the ONLY thing separating some of these, so the
// chart draws that line in. Off by default — it is a teaching aid, not part of
// the shape.
var WIDEST_MARK = {
  lanceolate: 0.33, elliptic: 0.50, ovate: 0.36, obovate: 0.64, spatulate: 0.72
};

// ═══════════════════════════════════════════════════════════════════════════
// INFLORESCENCE ARCHITECTURE
// ═══════════════════════════════════════════════════════════════════════════

var FLOWER_ARCH_ORDER = ['solitary', 'raceme', 'spike', 'panicle', 'corymb',
                         'umbel', 'head', 'cyme', 'whorl'];

/* Two small leaves near the base, so a bare axis reads as a plant. */
function baseLeaves(y) {
  return leaflet(50, y == null ? 84 : y, 20, 6, 68, { midrib: false }) +
         leaflet(50, y == null ? 84 : y, 20, 6, -68, { midrib: false });
}

var ARCHITECTURES = {

  solitary: function () {
    // Determinate by definition: the stem ends in this flower and that is all
    // it will ever make.
    return line(50, 92, 50, 40) + baseLeaves(80) + dot(50, 32, 9);
  },

  raceme: function () {
    // Stalked flowers up one unbranched axis. Opens from the BOTTOM — so the
    // open flowers are low and the buds are high, and the tip is still growing.
    var out = line(50, 92, 50, 18) + baseLeaves(88), i, y, len, side;
    for (i = 0; i < 5; i++) {
      y = 84 - i * 13;
      len = 19 - i * 2.4;
      for (side = -1; side <= 1; side += 2) {
        out += line(50, y, 50 + side * len, y - 5, C.stem, 1.5);
        out += dot(50 + side * len, y - 5, 5.2 - i * 0.5, i >= 3);
      }
    }
    return out + growTip(50, 15);
  },

  spike: function () {
    // A raceme with the stalks taken away — the flowers sit ON the axis.
    var out = line(50, 92, 50, 22) + baseLeaves(88), i, y, side;
    for (i = 0; i < 6; i++) {
      y = 82 - i * 11;
      for (side = -1; side <= 1; side += 2) {
        out += dot(50 + side * 6.5, y, 5.6 - i * 0.35, i >= 4);
      }
    }
    return out + growTip(50, 20);
  },

  panicle: function () {
    // A branched raceme: every branch is itself a little raceme.
    var out = line(50, 92, 50, 20) + baseLeaves(88), i, j, y, len, side, bx, by;
    for (i = 0; i < 4; i++) {
      y = 80 - i * 15;
      len = 26 - i * 4.5;
      for (side = -1; side <= 1; side += 2) {
        bx = 50 + side * len; by = y - 13;
        out += line(50, y, bx, by, C.stem, 1.6);
        for (j = 0; j < 3; j++) {
          out += dot(bx - side * j * (len * 0.30), by + j * 3.6 - 1,
                     4.2 - i * 0.3, i >= 3);
        }
      }
    }
    return out + growTip(50, 18);
  },

  corymb: function () {
    // Stalks rise from DIFFERENT points but end at the SAME height. The flat
    // top is the field mark; the unequal stalk lengths are the cause of it.
    var out = line(50, 92, 50, 42) + baseLeaves(88), i, y, x;
    var top = 30;
    for (i = -2; i <= 2; i++) {
      x = 50 + i * 16;
      y = 44 + Math.abs(i) * 12;               // lower stalks start lower…
      out += line(50, y, x, top + 2, C.stem, 1.5);   // …and are longer.
      out += dot(x, top, 6.4, false);
    }
    return out + growTip(50, 40);
  },

  umbel: function () {
    // Every stalk from ONE point. The ribs of an umbrella.
    var out = line(50, 92, 50, 58) + baseLeaves(88), i, a, x, y;
    for (i = -3; i <= 3; i++) {
      a = i * 0.30;
      x = 50 + Math.sin(a) * 34;
      y = 58 - Math.cos(a) * 30;
      out += line(50, 58, x, y, C.stem, 1.4);
      out += dot(x, y - 2, 5.4, false);
    }
    return out;
  },

  head: function () {
    // Many stalkless florets on one flattened disc, reading as a single
    // flower. Every aster, daisy, thistle and sunflower in the catalogue.
    var out = line(50, 92, 50, 54) + baseLeaves(86), i, a, x, y;
    out += '<path d="M28,52 Q50,62 72,52 Q50,44 28,52 Z" fill="' + C.fill +
           '" stroke="' + C.stem + '" stroke-width="1.5"/>';
    for (i = 0; i < 12; i++) {                 // ray florets, around the rim
      a = i / 12 * Math.PI * 2;
      out += '<ellipse cx="' + n(50 + Math.cos(a) * 24) + '" cy="' +
        n(50 + Math.sin(a) * 13) + '" rx="7" ry="3.1" fill="' + C.flower +
        '" opacity="0.85" transform="rotate(' + n(a * 180 / Math.PI) + ' ' +
        n(50 + Math.cos(a) * 24) + ' ' + n(50 + Math.sin(a) * 13) + ')"/>';
    }
    for (i = 0; i < 7; i++) {                  // disc florets, packed inside
      a = i / 7 * Math.PI * 2;
      out += dot(50 + Math.cos(a) * 7.5, 50 + Math.sin(a) * 4.2, 2.5, false);
    }
    return out + dot(50, 50, 2.5, false);
  },

  cyme: function () {
    // DETERMINATE, and drawn so you can see it: the TOP CENTRE flower is open
    // and everything outside it is still in bud. A raceme is the exact
    // opposite. If you learn one thing off this chart, learn this pair.
    var out = line(50, 92, 50, 44) + baseLeaves(88);
    out += dot(50, 36, 8, false);                    // opened first
    out += line(44, 48, 26, 40, C.stem, 1.6) + line(56, 48, 74, 40, C.stem, 1.6);
    out += dot(24, 36, 6.4, false) + dot(76, 36, 6.4, false);
    out += line(22, 40, 12, 30, C.stem, 1.4) + line(78, 40, 88, 30, C.stem, 1.4);
    out += dot(11, 26, 4.8, true) + dot(89, 26, 4.8, true);
    return out;
  },

  whorl: function () {
    // Rings of flowers at the nodes, with a pair of leaves at each. The mints
    // — and once you have seen it on one you see it on all of them.
    var out = line(50, 92, 50, 18), i, y, side;
    for (i = 0; i < 3; i++) {
      y = 78 - i * 22;
      out += leaflet(50, y, 17, 5.5, 74, { midrib: false }) +
             leaflet(50, y, 17, 5.5, -74, { midrib: false });
      for (side = -1; side <= 1; side += 2) {
        out += dot(50 + side * 13, y - 5, 5.0, i === 2) +
               dot(50 + side * 6, y - 9, 4.2, i === 2);
      }
    }
    return out + growTip(50, 16);
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// LEAF ARRANGEMENT
// ═══════════════════════════════════════════════════════════════════════════

var LEAF_ARRANGEMENT_ORDER = ['alternate', 'opposite', 'whorled', 'fascicled',
                              'basal'];

var ARRANGEMENTS = {

  alternate: function () {
    var out = line(50, 94, 50, 12), i, y;
    for (i = 0; i < 5; i++) {
      y = 84 - i * 16;
      out += leaflet(50, y, 30, 9.5, i % 2 ? -68 : 68);
    }
    return out;
  },

  opposite: function () {
    var out = line(50, 94, 50, 12), i, y;
    for (i = 0; i < 4; i++) {
      y = 82 - i * 20;
      out += leaflet(50, y, 30, 9.5, 68) + leaflet(50, y, 30, 9.5, -68);
    }
    return out;
  },

  whorled: function () {
    // Three or more at ONE node. The two side leaves plus a foreshortened one
    // pointing at the reader, which is how a whorl actually looks.
    var out = line(50, 94, 50, 12), i, y;
    for (i = 0; i < 3; i++) {
      y = 80 - i * 26;
      out += leaflet(50, y, 30, 9.5, 78) + leaflet(50, y, 30, 9.5, -78) +
             leaflet(50, y, 17, 8.5, 20) + leaflet(50, y, 17, 8.5, -20);
    }
    return out;
  },

  fascicled: function () {
    // Bundles from one point — pine needles in twos, threes or fives.
    var out = line(50, 94, 50, 24, C.stem, 2.6), i, j, y, side, ang;
    for (i = 0; i < 3; i++) {
      y = 82 - i * 22;
      for (side = -1; side <= 1; side += 2) {
        for (j = -1; j <= 1; j++) {
          ang = side * 60 + j * 13;
          out += leaflet(50, y, 30, 2.4, ang, { midrib: false, tipPow: 0.5, basePow: 0.35 });
        }
      }
    }
    return out;
  },

  basal: function () {
    // Everything at ground level, with the flowering stem rising bare out of
    // the middle. Half the prairie forbs in the catalogue, and the reason
    // `basal_rosette` is its own column.
    //
    // Drawn from slightly above and squashed vertically, because a rosette
    // seen edge-on is an unreadable pile of overlapping leaves — the
    // foreshortened view is both how you actually meet one in a lawn and the
    // only way eight radiating leaves stay legible at 64 pixels.
    var leaves = '', i, a;
    for (i = 0; i < 8; i++) {
      a = i * 45 + 22.5;
      leaves += leaflet(0, 0, 34, 10, a, { widestAt: 0.70, blunt: 1.5 });
    }
    return '<g transform="translate(50 74) scale(1 0.46)">' + leaves + '</g>' +
      line(50, 74, 50, 14, C.stem, 2.0) + dot(50, 11, 6, false);
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// GLOSSARY
// ═══════════════════════════════════════════════════════════════════════════

var BOTANY_GLOSSARY = {

  flower_arch: {
    solitary: 'One flower, alone at the end of the stem. Nothing comes after it.',
    raceme: 'Stalked flowers up one unbranched axis. Opens from the bottom up, and the tip keeps growing — so buds sit above open flowers.',
    spike: 'A raceme with no stalks: each flower sits directly on the axis.',
    panicle: 'A branched raceme — every branch carries its own row of stalked flowers.',
    corymb: 'Stalks rising from different points but all reaching the same height, giving a flat top.',
    umbel: 'Every stalk rises from one single point, like the ribs of an umbrella.',
    head: 'Many stalkless florets packed on one flattened disc, the whole reading as a single flower. Every aster, daisy and thistle.',
    cyme: 'The tip flower opens FIRST and branches grow out below it — so the open flower is at the centre and the buds are outside. The opposite of a raceme.',
    whorl: 'Flowers in rings around the stem at each node. The mints.'
  },

  leaf_shape: {
    needle: 'Long, thin and stiff, round or flat in section — a conifer leaf.',
    awl: 'Short and stiff, widest at the base and tapering to a sharp point. Juniper’s juvenile foliage.',
    scale: 'Tiny and overlapping, pressed flat to the twig like shingles. Adult cedar and juniper.',
    linear: 'Long and narrow with parallel sides — the edges run alongside each other for most of the blade.',
    lanceolate: 'Lance-shaped: widest below the middle, tapering to a point, roughly three times longer than wide.',
    elliptic: 'Widest at the middle, tapering about equally to both ends.',
    ovate: 'Egg-shaped, widest BELOW the middle — the broad end is at the stalk.',
    obovate: 'Egg-shaped, widest ABOVE the middle — ovate turned upside down.',
    spatulate: 'Spoon-shaped: rounded at the tip, tapering gradually to a narrow base. Common in basal rosettes.',
    orbicular: 'Round — as wide as it is long.',
    cordate: 'Heart-shaped, with a distinct notch where the stalk joins.',
    reniform: 'Kidney-shaped: wider than long, shallow notch at the base, no point at the tip.',
    sagittate: 'Arrowhead-shaped: pointed tip, with two lobes pointing backwards past the stalk.',
    lobed: 'Rounded projections with the notches between them stopping well short of the midrib. An oak.',
    pinnatifid: 'Cut so deeply the notches nearly reach the midrib — but the blade is still one piece.',
    trifoliate: 'Three separate leaflets on one stalk. Clover, strawberry.',
    compound_pinnate: 'Separate leaflets in two rows along a central stalk, like a feather.',
    compound_palmate: 'Separate leaflets all radiating from one point, like fingers from a palm.',
    bipinnate: 'Twice divided — each division is itself pinnate. Yarrow’s ferny foliage.'
  },

  leaf_arrangement: {
    alternate: 'One leaf per node, each on a different side as you go up.',
    opposite: 'Two leaves per node, directly across from one another.',
    whorled: 'Three or more leaves in a ring at one node.',
    fascicled: 'Leaves in tight bundles from one point — pine needles in twos, threes or fives.',
    basal: 'Leaves all at ground level in a rosette, with the flowering stem rising bare from the middle.'
  }
};

/* What to actually look at, per vocabulary. The single distinction that does
 * the most work — worth reading once before using the chart. */
var BOTANY_VOCAB_NOTES = {
  flower_arch:
    'Look at the TIP first. If the topmost flower is open and the ones below ' +
    'it are younger, the axis has finished — that is a cyme. If the tip is ' +
    'still a growing point with buds below it and open flowers lower down, it ' +
    'is a raceme or one of its relatives. After that: stalks or no stalks ' +
    '(raceme vs spike), branched or not (panicle), flat-topped (corymb), and ' +
    'whether every stalk starts from one point (umbel).',
  leaf_shape:
    'For the simple blades, find the WIDEST POINT: below the middle is ovate ' +
    'or lanceolate, at the middle elliptic, above the middle obovate or ' +
    'spatulate. For the cut ones, ask how far the notches reach — short of ' +
    'the midrib is lobed, nearly to it is pinnatifid, all the way through ' +
    'into separate leaflets is compound. It is one continuum, not three ' +
    'unrelated words.',
  leaf_arrangement:
    'Count the leaves at ONE node: one is alternate, two is opposite, three ' +
    'or more is whorled. Bundled from a single point is fascicled. All at ' +
    'ground level is basal.'
};

var BOTANY_VOCAB_TITLES = {
  flower_arch: 'Inflorescence architecture',
  leaf_shape: 'Leaf shape',
  leaf_arrangement: 'Leaf arrangement'
};

// ═══════════════════════════════════════════════════════════════════════════
// PUBLIC API
// ═══════════════════════════════════════════════════════════════════════════

var DRAW = {
  flower_arch: ARCHITECTURES,
  leaf_shape: LEAF_SHAPES,
  leaf_arrangement: ARRANGEMENTS
};

var ORDER = {
  flower_arch: FLOWER_ARCH_ORDER,
  leaf_shape: LEAF_SHAPE_ORDER,
  leaf_arrangement: LEAF_ARRANGEMENT_ORDER
};

/** The ordered term list for a vocabulary, or [] if the name is unknown. */
function botanyTerms(vocab) {
  return (ORDER[vocab] || []).slice();
}

/** One diagram. Returns '' for an unknown vocabulary or term — an empty
 *  string is visible as a gap, where a broken <img> would not be. */
function botanyDiagram(vocab, term, opts) {
  opts = opts || {};
  var table = DRAW[vocab];
  if (!table || !table[term]) return '';
  var size = opts.size || 64;
  var inner = table[term]();
  if (opts.widest && WIDEST_MARK[term] != null) {
    var y = 88 - WIDEST_MARK[term] * 74;
    inner += line(8, y, 92, y, C.mark, 1, '4 3');
  }
  return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" ' +
    'width="' + n(size) + '" height="' + n(size) + '" role="img" ' +
    'aria-label="' + esc(vocab.replace(/_/g, ' ') + ': ' + term) + '">' +
    inner + '</svg>';
}

/** The whole vocabulary at once, as HTML: every term drawn, named and
 *  defined. Comparing side by side is how the words are actually learned —
 *  one diagram at a time only tells you what you already picked. */
function botanyChart(vocab, opts) {
  opts = opts || {};
  var terms = botanyTerms(vocab);
  if (!terms.length) return '';
  var gloss = BOTANY_GLOSSARY[vocab] || {};
  var size = opts.size || 96;
  var out = '<div class="botany-chart">';
  if (opts.note !== false && BOTANY_VOCAB_NOTES[vocab]) {
    out += '<p class="botany-note">' + esc(BOTANY_VOCAB_NOTES[vocab]) + '</p>';
  }
  out += '<div class="botany-grid">';
  for (var i = 0; i < terms.length; i++) {
    var t = terms[i];
    out += '<figure class="botany-cell' +
      (opts.current === t ? ' is-current' : '') + '" data-term="' + esc(t) + '">' +
      botanyDiagram(vocab, t, { size: size, widest: opts.widest !== false }) +
      '<figcaption><b>' + esc(t) + '</b><span>' + esc(gloss[t] || '') +
      '</span></figcaption></figure>';
  }
  return out + '</div></div>';
}

global.botanyDiagram = botanyDiagram;
global.botanyChart = botanyChart;
global.botanyTerms = botanyTerms;
global.BOTANY_GLOSSARY = BOTANY_GLOSSARY;
global.BOTANY_VOCAB_NOTES = BOTANY_VOCAB_NOTES;
global.BOTANY_VOCAB_TITLES = BOTANY_VOCAB_TITLES;

})(typeof window !== 'undefined' ? window : this);
