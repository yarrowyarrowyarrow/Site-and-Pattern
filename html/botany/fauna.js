/* html/botany/fauna.js — the fauna vocabulary, drawn (V2.36).
 *
 * Design principle P5 — see docs/DESIGN_PHILOSOPHY.md
 *
 * The companion to diagrams.js, for the animals. Same argument: the fauna bench
 * asks a person to choose `falcate` or `angular`, `tent` or `swept`, and a word
 * you cannot picture is not a control. Same public shape too —
 * faunaDiagram(vocab, term) / faunaChart(vocab) / FAUNA_GLOSSARY — so the bench
 * can drive both modules through one code path.
 *
 * Drawn from the descriptions, not traced from any published figure. See
 * docs/DATA_SOURCES.md for why that line is kept carefully here.
 *
 * THE BUMBLEBEE BAND PREVIEW is the piece with no botanical equivalent.
 * `band_pattern` is thorax + T1..T6 as colour tokens, it is how every bumblebee
 * key in existence is written, and it is the single field that turns the
 * catalogue's 29 identical Bombus into 29 animals. Typing a band code blind is
 * exactly the failure this module exists to prevent, so `beeBandDiagram()`
 * draws the actual bee from the pattern as you type it.
 *
 * Classic script, shared globals — the repo's convention for browser JS.
 */
(function (global) {
'use strict';

// Semantic palette, mid-tone so the same drawings read on the bench's dark
// panel and on a white docs page. Labels live in the surrounding HTML.
var C = {
  wing:   '#c8b07a',
  wingFill: 'rgba(200,176,122,0.34)',
  vein:   'rgba(120,100,66,0.85)',
  body:   '#3a322a',
  mark:   '#9a9a8e',
  accent: '#e8a33d',
  path:   '#7fa6c8'
};

function n(v) { return Math.round(v * 100) / 100; }
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
function path(d, fill, stroke, w) {
  return '<path d="' + d + '" fill="' + (fill || 'none') + '" stroke="' +
    (stroke || 'none') + '" stroke-width="' + (w == null ? 1.6 : w) +
    '" stroke-linejoin="round" stroke-linecap="round"/>';
}

// ═══════════════════════════════════════════════════════════════════════════
// WING SHAPE — one wing pair, seen from above, body along the midline
// ═══════════════════════════════════════════════════════════════════════════

var WING_SHAPE_ORDER = ['rounded', 'broad', 'narrow', 'angular', 'falcate',
                        'tailed'];

/* A lepidopteran body: thorax, head, abdomen, antennae. Drawn once so every
 * wing-shape cell differs ONLY in the wings, which is the whole point. */
function lepBody() {
  return '<ellipse cx="50" cy="46" rx="4.2" ry="7" fill="' + C.body + '"/>' +
    '<circle cx="50" cy="37" r="3.4" fill="' + C.body + '"/>' +
    '<ellipse cx="50" cy="62" rx="3" ry="11" fill="' + C.body + '"/>' +
    path('M48,34 C45,28 42,25 39,23', null, C.body, 1.4) +
    path('M52,34 C55,28 58,25 61,23', null, C.body, 1.4) +
    '<circle cx="38.6" cy="22.4" r="1.5" fill="' + C.body + '"/>' +
    '<circle cx="61.4" cy="22.4" r="1.5" fill="' + C.body + '"/>';
}

/* Mirror a right-hand wing path to the left. Every outline below is authored
 * once, on the right of the midline. */
function bothWings(d) {
  return '<g>' + path(d, C.wingFill, C.wing, 1.7) +
    '<g transform="translate(100,0) scale(-1,1)">' +
      path(d, C.wingFill, C.wing, 1.7) + '</g></g>';
}

var WING_SHAPES = {
  // Fore + hind lobe, no corners — the nymphalid/lycaenid default.
  rounded: function () {
    return bothWings('M52,42 C68,30 86,34 88,46 C90,58 74,60 62,54 Z' +
                     'M52,56 C66,52 80,58 79,68 C78,77 62,76 55,66 Z') + lepBody();
  },
  // Same outline, much bigger area — a monarch or an admiral.
  broad: function () {
    return bothWings('M52,40 C72,24 94,30 95,45 C96,60 74,64 60,55 Z' +
                     'M52,57 C70,52 88,60 86,72 C84,84 62,80 55,68 Z') + lepBody();
  },
  // Long and slim — the sphinx/hawkmoth plan built for speed.
  narrow: function () {
    return bothWings('M52,42 C70,34 92,36 95,43 C97,50 74,52 60,50 Z' +
                     'M52,55 C66,52 80,56 80,62 C80,68 62,66 55,60 Z') + lepBody();
  },
  // Straight edges meeting at corners — tortoiseshells, commas, anglewings.
  angular: function () {
    return bothWings('M52,41 L74,30 L90,38 L84,48 L92,52 L64,54 Z' +
                     'M52,57 L76,58 L86,68 L72,72 L68,80 L56,68 Z') + lepBody();
  },
  // Hooked forewing tip that curves BACK toward the body, leaving the outer
  // edge visibly concave below it. The concavity is the term — without it this
  // is just a pointed wing — so it is drawn hard.
  falcate: function () {
    return bothWings('M52,42 C68,28 84,22 95,24 ' +      // leading edge out to the hook
                     'C90,32 86,38 84,44 ' +             // the hook, turning back
                     'C78,40 70,44 66,54 ' +             // concave outer margin
                     'C60,52 55,50 52,48 Z' +
                     'M52,56 C66,52 80,58 79,68 C78,77 62,76 55,66 Z') + lepBody();
  },
  // A long tail off the hind wing — the swallowtail mark, readable across a
  // garden, so drawn at the length that actually makes it recognisable.
  tailed: function () {
    return bothWings('M52,41 C70,28 90,32 92,45 C94,58 72,60 60,53 Z' +
                     'M52,56 C68,52 82,58 82,66 C82,72 78,75 73,75 ' +
                     'L79,94 L67,78 ' +                  // the tail
                     'C61,75 55,68 52,62 Z') + lepBody();
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// WING PATTERN — the same rounded wing every time, differing only in markings
// ═══════════════════════════════════════════════════════════════════════════

var WING_PATTERN_ORDER = ['plain', 'veined', 'spotted', 'banded', 'checkered',
                          'mottled', 'eyespots'];

var _PLAIN_FORE = 'M52,42 C68,30 86,34 88,46 C90,58 74,60 62,54 Z';
var _PLAIN_HIND = 'M52,56 C66,52 80,58 79,68 C78,77 62,76 55,66 Z';

/* Marks are clipped to the wing so nothing floats outside the outline — the
 * thing that makes a pattern diagram read as a pattern rather than as confetti. */
function patternedWings(marks, id) {
  var clip = '<clipPath id="' + id + '"><path d="' + _PLAIN_FORE +
    '"/><path d="' + _PLAIN_HIND + '"/></clipPath>';
  var one = clip +
    path(_PLAIN_FORE, C.wingFill, C.wing, 1.7) +
    path(_PLAIN_HIND, C.wingFill, C.wing, 1.7) +
    '<g clip-path="url(#' + id + ')">' + marks + '</g>';
  return '<g>' + one + '<g transform="translate(100,0) scale(-1,1)">' +
    one.replace(new RegExp(id, 'g'), id + 'm') + '</g></g>';
}

var WING_PATTERNS = {
  plain: function () { return patternedWings('', 'p0') + lepBody(); },

  veined: function () {
    var m = '';
    for (var i = 0; i < 6; i++) {
      m += path('M52,' + (44 + i * 1.5) + ' C68,' + (36 + i * 3.2) + ' 82,' +
                (36 + i * 4.4) + ' 92,' + (40 + i * 5.2), null, C.vein, 1.2);
    }
    return patternedWings(m, 'p1') + lepBody();
  },

  spotted: function () {
    var m = '', pts = [[68, 40], [78, 45], [62, 48], [84, 50], [70, 62],
                       [76, 68], [64, 68]];
    for (var i = 0; i < pts.length; i++) {
      m += '<circle cx="' + pts[i][0] + '" cy="' + pts[i][1] + '" r="3.1" fill="' +
        C.body + '" opacity="0.78"/>';
    }
    return patternedWings(m, 'p2') + lepBody();
  },

  banded: function () {
    // Bands run ACROSS the wing, parallel to the outer margin.
    var m = '';
    for (var i = 0; i < 3; i++) {
      m += path('M' + (58 + i * 11) + ',28 L' + (52 + i * 11) + ',84',
                null, C.body, 4.4);
    }
    return patternedWings(m, 'p3') + lepBody();
  },

  checkered: function () {
    var m = '', r, c;
    for (r = 0; r < 6; r++) for (c = 0; c < 5; c++) {
      if ((r + c) % 2) continue;
      m += '<rect x="' + (52 + c * 9) + '" y="' + (30 + r * 9) +
        '" width="9" height="9" fill="' + C.body + '" opacity="0.7"/>';
    }
    return patternedWings(m, 'p4') + lepBody();
  },

  mottled: function () {
    var m = '', blobs = [[66, 38, 5], [80, 44, 6.5], [60, 50, 4], [88, 52, 4.5],
                         [70, 60, 5.5], [80, 70, 5], [60, 68, 4]];
    for (var i = 0; i < blobs.length; i++) {
      m += '<ellipse cx="' + blobs[i][0] + '" cy="' + blobs[i][1] + '" rx="' +
        blobs[i][2] + '" ry="' + (blobs[i][2] * 0.72) + '" fill="' + C.body +
        '" opacity="0.5"/>';
    }
    return patternedWings(m, 'p5') + lepBody();
  },

  eyespots: function () {
    // A ringed eye, not a spot: dark iris, pale ring, white highlight. That
    // structure IS the term — a Polyphemus or a wood-nymph is identified by it,
    // and it is the difference between this and `spotted`.
    function eye(x, y, r) {
      return '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="' + C.body + '"/>' +
        '<circle cx="' + x + '" cy="' + y + '" r="' + (r * 0.62) + '" fill="' + C.accent + '" opacity="0.8"/>' +
        '<circle cx="' + x + '" cy="' + y + '" r="' + (r * 0.3) + '" fill="#20242a"/>' +
        '<circle cx="' + (x - r * 0.22) + '" cy="' + (y - r * 0.24) + '" r="' + (r * 0.13) + '" fill="#f2f2ee"/>';
    }
    return patternedWings(eye(76, 45, 7.5) + eye(70, 66, 6), 'p6') + lepBody();
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// RESTING POSTURE — head-on, so the wing PLANE is what you see
// ═══════════════════════════════════════════════════════════════════════════

var RESTING_ORDER = ['wings_up', 'wings_flat', 'tent', 'wrapped', 'swept'];

/* A perch line and a small end-on body, shared by every posture cell. */
function perch(bodyY) {
  return path('M14,86 L86,86', null, C.mark, 1.4, '3 3') +
    '<ellipse cx="50" cy="' + (bodyY == null ? 74 : bodyY) +
    '" rx="4.5" ry="9" fill="' + C.body + '"/>';
}

var RESTING_POSTURES = {
  // Held together vertically over the back — the butterfly default, and why a
  // settled butterfly nearly vanishes.
  wings_up: function () {
    return perch() +
      path('M50,66 L38,20 L50,30 Z', C.wingFill, C.wing, 1.7) +
      path('M50,66 L62,20 L50,30 Z', C.wingFill, C.wing, 1.7);
  },
  // Spread flat, basking — satyrs and anglewings on a warm path.
  wings_flat: function () {
    return perch(70) +
      path('M50,66 L10,58 L12,72 L50,74 Z', C.wingFill, C.wing, 1.7) +
      path('M50,66 L90,58 L88,72 L50,74 Z', C.wingFill, C.wing, 1.7);
  },
  // A roof over the abdomen — most moths.
  tent: function () {
    return perch(78) +
      path('M50,40 L18,80 L50,80 Z', C.wingFill, C.wing, 1.7) +
      path('M50,40 L82,80 L50,80 Z', C.wingFill, C.wing, 1.7);
  },
  // Rolled tight round the body, cigar-like — many noctuids and the tussocks.
  wrapped: function () {
    return perch(74) +
      path('M50,52 C36,58 34,74 42,84 L58,84 C66,74 64,58 50,52 Z',
           C.wingFill, C.wing, 1.7) +
      path('M50,54 L50,84', null, C.vein, 1.2);
  },
  // Angled back like a jet — sphinx moths and, in their own way, skippers.
  swept: function () {
    return perch(70) +
      path('M50,58 L16,84 L30,84 L50,72 Z', C.wingFill, C.wing, 1.7) +
      path('M50,58 L84,84 L70,84 L50,72 Z', C.wingFill, C.wing, 1.7);
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// FLIGHT STYLE — the track through the air, plan view
// ═══════════════════════════════════════════════════════════════════════════

var FLIGHT_ORDER = ['fluttery', 'erratic', 'darting', 'gliding', 'bobbing',
                    'hovering'];

/* These are drawn from the SAME layered-sine wander the viewer flies
 * (html/scene3d/07-wildlife.js `_wander3` and `_FLIGHT_STYLE`), so the picture
 * is the behaviour rather than an impression of it. */
function track(rate, side, lift, opts) {
  opts = opts || {};
  var d = '', i, s, a, b, x, y;
  for (i = 0; i <= 90; i++) {
    s = (i / 90) * 9 * rate;
    a = Math.sin(s) * 0.60 + Math.sin(s * 2.37) * 0.28 + Math.sin(s * 4.11) * 0.12;
    b = Math.cos(s * 0.83) * 0.60 + Math.cos(s * 1.94) * 0.28 + Math.cos(s * 3.62) * 0.12;
    x = 10 + (i / 90) * 80 + (opts.stall ? 0 : 0);
    y = 50 + a * side + b * lift;
    d += (i ? 'L' : 'M') + n(x) + ',' + n(y);
  }
  return path(d, null, C.path, 2.0) +
    // A dot at the far end so the direction of travel reads.
    '<circle cx="90" cy="' + n(50 + (Math.sin(9 * rate) * 0.6) * side) +
    '" r="3" fill="' + C.accent + '"/>';
}

var FLIGHT_STYLES = {
  fluttery: function () { return track(1.00, 16, 8); },
  erratic:  function () { return track(1.55, 22, 10); },
  darting:  function () { return track(2.10, 9, 4); },
  gliding:  function () { return track(0.45, 10, 6); },
  bobbing:  function () { return track(0.80, 6, 20); },
  hovering: function () {
    // Not a track at all — a knot in one place, which is the point.
    var d = '', i, s, x, y;
    for (i = 0; i <= 120; i++) {
      s = (i / 120) * 30;
      x = 50 + (Math.sin(s) * 0.6 + Math.sin(s * 2.37) * 0.28) * 7;
      y = 50 + (Math.cos(s * 0.83) * 0.6 + Math.cos(s * 1.94) * 0.28) * 5;
      d += (i ? 'L' : 'M') + n(x) + ',' + n(y);
    }
    return path('M10,50 L34,50', null, C.path, 2.0) + path(d, null, C.path, 1.6) +
      '<circle cx="50" cy="50" r="3" fill="' + C.accent + '"/>';
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// BEE BUILD + SCOPA
// ═══════════════════════════════════════════════════════════════════════════

var BEE_BUILD_ORDER = ['round', 'stout', 'slender', 'leafcutter'];

/* One bee from above: head, thorax, abdomen, wings. `ab` scales the abdomen
 * and `head` the head, which between them are the whole build vocabulary. */
function beeBody(abRx, abRy, headR, opts) {
  opts = opts || {};
  var g = '';
  // wings first, behind
  g += '<ellipse cx="36" cy="52" rx="15" ry="6" fill="rgba(220,232,240,0.42)" ' +
       'stroke="#9fb4c0" stroke-width="1" transform="rotate(-24 36 52)"/>';
  g += '<ellipse cx="64" cy="52" rx="15" ry="6" fill="rgba(220,232,240,0.42)" ' +
       'stroke="#9fb4c0" stroke-width="1" transform="rotate(24 64 52)"/>';
  g += '<circle cx="50" cy="' + (30 - (headR - 7)) + '" r="' + headR + '" fill="' + C.body + '"/>';
  g += '<ellipse cx="50" cy="46" rx="9" ry="9.5" fill="#6b5a3c"/>';   // thorax
  g += '<ellipse cx="50" cy="' + (58 + abRy * 0.55) + '" rx="' + abRx +
       '" ry="' + abRy + '" fill="' + C.accent + '"/>';
  // two dark tergite bands so an abdomen reads as an abdomen
  g += '<path d="M' + (50 - abRx * 0.94) + ',' + (58 + abRy * 0.35) + ' h' + (abRx * 1.88) +
       '" stroke="' + C.body + '" stroke-width="3.4" opacity="0.85"/>';
  g += '<path d="M' + (50 - abRx * 0.8) + ',' + (58 + abRy * 0.95) + ' h' + (abRx * 1.6) +
       '" stroke="' + C.body + '" stroke-width="3.4" opacity="0.85"/>';
  if (opts.scopa) {
    g += '<path d="M' + (50 - abRx * 0.75) + ',' + (58 + abRy * 1.35) + ' h' + (abRx * 1.5) +
         '" stroke="#f0d98a" stroke-width="5" stroke-linecap="round"/>';
  }
  return g;
}

// Pushed apart deliberately. These four differ by a couple of millimetres on a
// real bee, and four cells that look the same teach nothing — the drawing has
// to carry the distinction the word is making, so the proportions are
// exaggerated the way a field-guide silhouette exaggerates them.
var BEE_BUILDS = {
  round:      function () { return beeBody(12.5, 12, 7.5); },   // globular
  stout:      function () { return beeBody(11.5, 8.5, 8); },    // wide, short
  slender:    function () { return beeBody(6.0, 14, 6); },      // narrow, long
  // Broad head and a flat, parallel-sided abdomen carrying pollen UNDERNEATH —
  // the two things a non-specialist actually notices about a Megachile.
  leafcutter: function () { return beeBody(10.5, 11, 10.5, { scopa: true }); }
};

var SCOPA_ORDER = ['hind_leg', 'abdomen', 'none'];

var SCOPA_POSITIONS = {
  hind_leg: function () {
    return beeBody(10, 11, 7.5) +
      path('M40,64 C30,70 26,80 28,88', null, C.body, 2.2) +
      path('M60,64 C70,70 74,80 72,88', null, C.body, 2.2) +
      '<ellipse cx="27" cy="82" rx="5" ry="7.5" fill="#f0d98a" stroke="#c9a83a" stroke-width="1.2" transform="rotate(-18 27 82)"/>' +
      '<ellipse cx="73" cy="82" rx="5" ry="7.5" fill="#f0d98a" stroke="#c9a83a" stroke-width="1.2" transform="rotate(18 73 82)"/>';
  },
  abdomen: function () {
    return beeBody(10, 11.5, 9.5, { scopa: true }) +
      '<path d="M39,76 h22" stroke="#f0d98a" stroke-width="6" stroke-linecap="round"/>';
  },
  // No brush anywhere — and that is the cuckoo bee's field mark, because a bee
  // that steals a nest never has to carry pollen home.
  none: function () {
    return beeBody(8, 11, 7) +
      '<circle cx="50" cy="72" r="17" fill="none" stroke="' + C.mark +
      '" stroke-width="1.6" stroke-dasharray="3 3"/>' +
      path('M39,61 L61,83', null, C.mark, 2.2);
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// THE BUMBLEBEE BAND PREVIEW
// ═══════════════════════════════════════════════════════════════════════════

// Mirrors src/data_quality.BAND_COLOUR_HEX. The Python set is the source of
// truth; tests/test_fauna_morphology.py fails if these drift apart.
var BAND_COLOUR_HEX = {
  black:  '#26211c',
  yellow: '#f2c12e',
  orange: '#d8722a',
  red:    '#b5462e',
  white:  '#e8e4da',
  buff:   '#d8cbb0',
  brown:  '#6b5138',
  grey:   '#9a9186'
};
var BAND_SEGMENTS_MAX = 7;

function bandTokens(pattern) {
  return String(pattern || '').split(',')
    .map(function (t) { return t.trim().toLowerCase(); })
    .filter(function (t) { return t; })
    .slice(0, BAND_SEGMENTS_MAX);
}

/** The bee described by a `band_pattern`, drawn. Thorax then T1..T6, top to
 *  bottom, exactly the order a key names them.
 *
 *  This is the whole reason the fauna bench can be used honestly: a band code
 *  typed blind is unverifiable, and a bee drawn from it can be held next to the
 *  photograph or the plate. Unknown tokens render as a hatched segment rather
 *  than silently as grey — a typo has to LOOK wrong. */
function beeBandDiagram(pattern, opts) {
  opts = opts || {};
  var size = opts.size || 96;
  var toks = bandTokens(pattern);
  var g = '';
  // wings
  g += '<ellipse cx="30" cy="44" rx="17" ry="7" fill="rgba(220,232,240,0.40)" ' +
       'stroke="#9fb4c0" stroke-width="1" transform="rotate(-26 30 44)"/>';
  g += '<ellipse cx="70" cy="44" rx="17" ry="7" fill="rgba(220,232,240,0.40)" ' +
       'stroke="#9fb4c0" stroke-width="1" transform="rotate(26 70 44)"/>';
  g += '<circle cx="50" cy="17" r="7.5" fill="' + C.body + '"/>';   // head
  var bad = '';
  // Thorax is token 0; T1..T6 are the rest, stacked down the abdomen.
  var thorax = toks.length ? toks[0] : null;
  var tcol = thorax && BAND_COLOUR_HEX[thorax];
  g += '<ellipse cx="50" cy="34" rx="13" ry="11" fill="' +
       (tcol || 'url(#bandUnknown)') + '" stroke="' + C.body + '" stroke-width="1.4"/>';
  if (thorax && !tcol) bad += thorax + ' ';
  var segs = toks.slice(1);
  var nSeg = Math.max(1, segs.length);
  var top = 45, h = 44 / nSeg;
  for (var i = 0; i < segs.length; i++) {
    var col = BAND_COLOUR_HEX[segs[i]];
    if (!col) bad += segs[i] + ' ';
    // Abdomen tapers: each tergite a little narrower than the one above.
    var rx = 13.5 - 6.5 * (i / Math.max(1, segs.length - 1 || 1));
    var y = top + i * h;
    g += '<path d="M' + n(50 - rx) + ',' + n(y) + ' h' + n(rx * 2) +
         ' v' + n(h) + ' h' + n(-rx * 2) + ' Z" fill="' +
         (col || 'url(#bandUnknown)') + '" stroke="' + C.body +
         '" stroke-width="0.9"/>';
  }
  var defs = '<defs><pattern id="bandUnknown" width="6" height="6" ' +
    'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">' +
    '<rect width="6" height="6" fill="#5a5148"/>' +
    '<rect width="3" height="6" fill="#b5462e"/></pattern></defs>';
  return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" ' +
    'width="' + n(size) + '" height="' + n(size) + '" role="img" ' +
    'aria-label="' + esc('band pattern: ' + (toks.join(', ') || 'unset')) + '">' +
    defs + g + '</svg>' + (opts.reportBad ? (bad ? bad.trim() : '') : '');
}

// ═══════════════════════════════════════════════════════════════════════════
// GLOSSARY
// ═══════════════════════════════════════════════════════════════════════════

var FAUNA_GLOSSARY = {
  wing_shape: {
    rounded: 'No corners — the outline curves the whole way round. Most blues, coppers and fritillaries.',
    broad: 'Large and wide relative to the body, built for sailing. Monarchs, admirals, swallowtails.',
    narrow: 'Long and slim, a high-speed wing. Sphinx moths and the clearwings.',
    angular: 'Straight edges meeting at corners, often with a ragged margin. Tortoiseshells, commas, anglewings.',
    falcate: 'The forewing tip is hooked and curves back toward the body.',
    tailed: 'A slender tail projects from the hind wing. The swallowtail mark, and visible at a distance.'
  },
  wing_pattern: {
    plain: 'One colour, or a smooth shade across the wing, with no figure on it.',
    veined: 'The veins themselves are picked out in a contrasting colour.',
    spotted: 'Discrete round spots — solid, without a surrounding ring.',
    banded: 'Stripes running across the wing, roughly parallel to the outer margin.',
    checkered: 'A grid of alternating light and dark squares. Crescents, checkerspots.',
    mottled: 'Irregular blotches with soft edges, usually camouflage. Most moths.',
    eyespots: 'Concentric rings with a pale highlight, imitating an eye — NOT the same as a spot. Polyphemus, wood-nymphs, satyrs.'
  },
  resting_posture: {
    wings_up: 'Held together vertically over the back. The butterfly default, and why a settled butterfly can vanish.',
    wings_flat: 'Spread open against the surface, usually basking.',
    tent: 'Sloped over the abdomen like a roof. Most moths.',
    wrapped: 'Rolled tightly around the body, cigar-shaped. Many noctuids and tussock moths.',
    swept: 'Angled back along the body like a jet. Sphinx moths, and skippers in their own half-open way.'
  },
  flight_style: {
    fluttery: 'Loose, irregular flapping with constant small direction changes. Whites and sulphurs.',
    erratic: 'Sharp, unpredictable jinking — hard to follow with the eye and hard for a bird to catch. Blues and crescents.',
    darting: 'Very fast, short, straight dashes with abrupt stops. Skippers.',
    gliding: 'Long sails between slow beats, holding a line. Monarchs and swallowtails.',
    bobbing: 'A rising and falling track, like a bouncing ball. Fritillaries and satyrs.',
    hovering: 'Holds station in mid-air at a flower instead of landing. Sphinx moths and clearwings.'
  },
  bee_build: {
    round: 'Broad and globular, densely furred. Bumblebees.',
    stout: 'Thickset and compact, a little longer than round. Digger and mason bees.',
    slender: 'Narrow and elongate, often small and sparsely haired. Sweat and mining bees.',
    leafcutter: 'Broad head with a flat, parallel-sided abdomen carrying pollen underneath. Megachile.'
  },
  scopa_position: {
    hind_leg: 'Pollen carried in a brush or basket on the hind leg. Most bees.',
    abdomen: 'Pollen carried in a brush under the abdomen, which looks bright yellow from below. Megachile and Osmia.',
    none: 'No pollen brush at all — the field mark of a cuckoo bee, which lays in another bee’s nest and never provisions one.'
  }
};

var FAUNA_VOCAB_NOTES = {
  wing_shape:
    'Look at the OUTLINE, ignoring the colour. Corners or curves first ' +
    '(angular vs rounded); then how much wing there is relative to the body ' +
    '(broad vs narrow); then the two special cases that name a group on their ' +
    'own — a hooked tip is falcate, a projection off the hind wing is tailed.',
  wing_pattern:
    'The distinction that matters most is spotted vs eyespots: a spot is a ' +
    'solid disc, an eyespot has concentric rings and usually a pale ' +
    'highlight. It is the difference between a marking and a bluff, and it is ' +
    'what identifies the big silk moths and the satyrs.',
  resting_posture:
    'This is what you see on a perched animal, and it is often easier to ' +
    'record than anything about the wing itself. It also drives the pose the ' +
    '3D preview uses when a creature settles on a flower.',
  flight_style:
    'Recorded from how the animal moves, not how it looks — and the one ' +
    'character here you can log from ten metres away without a photograph. ' +
    'The 3D preview flies each species by this field.',
  bee_build:
    'Overall body plan, which is what the viewer picks a mesh from. Judge it ' +
    'on the abdomen: globular is round, thickset is stout, narrow and long is ' +
    'slender. Leafcutter is its own thing and worth learning.',
  scopa_position:
    'Where a female carries pollen. Diagnostic, easy to see on a foraging ' +
    'bee, and the absence of any brush is itself the cuckoo-bee field mark.'
};

var FAUNA_VOCAB_TITLES = {
  wing_shape: 'Wing shape',
  wing_pattern: 'Wing pattern',
  resting_posture: 'Resting posture',
  flight_style: 'Flight style',
  bee_build: 'Bee build',
  scopa_position: 'Pollen-carrying (scopa)'
};

// ═══════════════════════════════════════════════════════════════════════════
// PUBLIC API — mirrors html/botany/diagrams.js so the bench drives both alike
// ═══════════════════════════════════════════════════════════════════════════

var DRAW = {
  wing_shape: WING_SHAPES,
  wing_pattern: WING_PATTERNS,
  resting_posture: RESTING_POSTURES,
  flight_style: FLIGHT_STYLES,
  bee_build: BEE_BUILDS,
  scopa_position: SCOPA_POSITIONS
};
var ORDER = {
  wing_shape: WING_SHAPE_ORDER,
  wing_pattern: WING_PATTERN_ORDER,
  resting_posture: RESTING_ORDER,
  flight_style: FLIGHT_ORDER,
  bee_build: BEE_BUILD_ORDER,
  scopa_position: SCOPA_ORDER
};

function faunaTerms(vocab) { return (ORDER[vocab] || []).slice(); }

function faunaDiagram(vocab, term, opts) {
  opts = opts || {};
  var table = DRAW[vocab];
  if (!table || !table[term]) return '';
  var size = opts.size || 64;
  return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" ' +
    'width="' + n(size) + '" height="' + n(size) + '" role="img" ' +
    'aria-label="' + esc(vocab.replace(/_/g, ' ') + ': ' + term) + '">' +
    table[term]() + '</svg>';
}

function faunaChart(vocab, opts) {
  opts = opts || {};
  var terms = faunaTerms(vocab);
  if (!terms.length) return '';
  var gloss = FAUNA_GLOSSARY[vocab] || {};
  var size = opts.size || 96;
  var out = '<div class="botany-chart">';
  if (opts.note !== false && FAUNA_VOCAB_NOTES[vocab]) {
    out += '<p class="botany-note">' + esc(FAUNA_VOCAB_NOTES[vocab]) + '</p>';
  }
  out += '<div class="botany-grid">';
  for (var i = 0; i < terms.length; i++) {
    var t = terms[i];
    out += '<figure class="botany-cell' +
      (opts.current === t ? ' is-current' : '') + '" data-term="' + esc(t) + '">' +
      faunaDiagram(vocab, t, { size: size }) +
      '<figcaption><b>' + esc(t) + '</b><span>' + esc(gloss[t] || '') +
      '</span></figcaption></figure>';
  }
  return out + '</div></div>';
}

global.faunaDiagram = faunaDiagram;
global.faunaChart = faunaChart;
global.faunaTerms = faunaTerms;
global.beeBandDiagram = beeBandDiagram;
global.bandTokens = bandTokens;
global.BAND_COLOUR_HEX = BAND_COLOUR_HEX;
global.FAUNA_GLOSSARY = FAUNA_GLOSSARY;
global.FAUNA_VOCAB_NOTES = FAUNA_VOCAB_NOTES;
global.FAUNA_VOCAB_TITLES = FAUNA_VOCAB_TITLES;

})(typeof window !== 'undefined' ? window : this);
