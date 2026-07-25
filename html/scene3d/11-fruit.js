// Part of the Site & Pattern 3D viewer. Loaded as an ordered CLASSIC
// script by the bootstrap in scene3d.html — it shares the global scope
// with its siblings (THREE and friends are globals set by the
// bootstrap). Do not add ES `import`/`export` here.
//
// Split out of 05-flowers.js in V2.29, when fruit stopped being one
// sphere sprite and became nine shaped ones. Nothing here runs at
// evaluation time — buildFruit is called from buildPlants during a scene
// push — so this chunk's position in the load order is not a dependency,
// only a place to live.

// ── Fruit (V2.0; shaped per species V2.29) ───────────────────────────────────
// Fleshy-fruited plants (curated fruit_color) show their fruit through the
// canopy during the fruit season.
//
// Until V2.29 every one of them was the SAME sprite: one radial-gradient disc,
// tinted. That is a fair primitive for a currant and false for most of the rest
// — a strawberry is a pip-studded cone with a green shoulder, a rose hip an urn
// with a dark crown, a chokecherry a drooping raceme, a raspberry a thimble of
// druplets, a mountain ash a flat bunch of dozens. Drawn as spheres they were
// all "red dot", so species you can tell apart in the hand were identical on
// screen — the opposite of what this app is for (P5).
//
// The shape now comes from the species' own `fruit_form` (schema v49), the
// companion to `fruit_color`, so the renderer reads the catalogue instead of
// re-encoding botany in JavaScript.
const FRUIT_FORMS = ['berry', 'strig', 'raceme', 'cherry', 'pome', 'hip',
                     'strawberry', 'aggregate', 'flat_cluster'];
let FRUIT_TEX = null;

// A shaded ball: the shared primitive every fruit sprite is drawn from, so a
// cluster of six reads as six little spheres rather than six flat discs.
function _fruitBall(g, cx, cy, r, shade) {
  const grd = g.createRadialGradient(cx - r * 0.3, cy - r * 0.34, r * 0.08,
                                     cx, cy, r);
  grd.addColorStop(0, '#ffffff');
  grd.addColorStop(0.42, shade || '#d2d2d2');
  grd.addColorStop(1, '#6e6e6e');
  g.fillStyle = grd;
  g.beginPath(); g.arc(cx, cy, r, 0, Math.PI * 2); g.fill();
}

function makeFruitTexture(form) {
  const s = 64, cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const g = cv.getContext('2d');
  g.clearRect(0, 0, s, s);
  const cx = s / 2;
  // A dark stalk/calyx, drawn in the SAME grey ramp as the flesh so the vertex
  // tint colours it too — a green calyx on a red berry would need a second
  // material, and the silhouette is what carries the identification anyway.
  const stalk = (x0, y0, x1, y1, w) => {
    g.strokeStyle = '#4a4a4a'; g.lineWidth = w; g.lineCap = 'round';
    g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke();
  };
  if (form === 'strig') {
    // Currants: a hanging string of small berries off one stem. This is the
    // field mark that separates a currant from a gooseberry on the same bush.
    stalk(cx, s * 0.04, cx * 0.92, s * 0.42, s * 0.035);
    for (let i = 0; i < 5; i++) {
      const t = i / 4;
      const x = cx + (i % 2 ? 1 : -1) * s * 0.10 - s * 0.02 * t;
      const y = s * 0.30 + t * s * 0.58;
      stalk(cx * 0.94, s * 0.30 + t * s * 0.5, x, y, s * 0.022);
      _fruitBall(g, x, y, s * 0.115);
    }
  } else if (form === 'raceme') {
    // Chokecherry: a longer, denser drooping raceme.
    stalk(cx, s * 0.02, cx, s * 0.42, s * 0.04);
    for (let i = 0; i < 8; i++) {
      const t = i / 7;
      const x = cx + Math.sin(i * 2.1) * s * 0.13;
      const y = s * 0.22 + t * s * 0.70;
      _fruitBall(g, x, y, s * 0.105);
    }
  } else if (form === 'cherry') {
    // Pin cherry: round drupes on long visible pedicels, in loose bunches —
    // the long stalk is exactly what distinguishes it from a chokecherry.
    for (const [dx, dy, r] of [[-0.20, 0.30, 0.155], [0.16, 0.36, 0.145],
                               [-0.02, 0.16, 0.13]]) {
      stalk(cx, s * 0.05, cx + dx * s, s * (0.5 + dy) - r * s, s * 0.028);
      _fruitBall(g, cx + dx * s, s * (0.5 + dy), r * s);
    }
  } else if (form === 'pome') {
    // Saskatoon / hawthorn: round, with the five-point calyx EYE at the far
    // end. The eye is the mark that says "pome, not berry".
    _fruitBall(g, cx, s * 0.48, s * 0.34);
    g.strokeStyle = '#3a3a3a'; g.lineWidth = s * 0.035;
    for (let i = 0; i < 5; i++) {
      const a = -Math.PI / 2 + i / 5 * Math.PI * 2;
      g.beginPath();
      g.moveTo(cx + Math.cos(a) * s * 0.05, s * 0.72 + Math.sin(a) * s * 0.05);
      g.lineTo(cx + Math.cos(a) * s * 0.13, s * 0.72 + Math.sin(a) * s * 0.13);
      g.stroke();
    }
  } else if (form === 'hip') {
    // Rose hip: an urn, wider below, with a persistent dark calyx crown.
    g.save(); g.translate(cx, s * 0.52); g.scale(1, 1.22);
    _fruitBall(g, 0, 0, s * 0.30);
    g.restore();
    g.strokeStyle = '#3a3a3a'; g.lineWidth = s * 0.04;
    for (let i = 0; i < 5; i++) {
      const a = -Math.PI / 2 + (i / 5 - 0.5) * 1.7;
      g.beginPath(); g.moveTo(cx, s * 0.16);
      g.lineTo(cx + Math.cos(a) * s * 0.16, s * 0.16 + Math.sin(a) * s * 0.16);
      g.stroke();
    }
  } else if (form === 'strawberry') {
    // A conic accessory fruit: broad shouldered, tapering to a blunt tip,
    // pip-pitted, with the calyx flaring at the top. NOT a sphere — which is
    // the single most obviously wrong thing the old one-sprite fruit did.
    g.fillStyle = '#c8c8c8';
    g.beginPath();
    g.moveTo(cx - s * 0.26, s * 0.34);
    g.bezierCurveTo(cx - s * 0.30, s * 0.62, cx - s * 0.10, s * 0.88,
                    cx, s * 0.90);
    g.bezierCurveTo(cx + s * 0.10, s * 0.88, cx + s * 0.30, s * 0.62,
                    cx + s * 0.26, s * 0.34);
    g.closePath();
    const grd = g.createLinearGradient(cx - s * 0.26, s * 0.3,
                                       cx + s * 0.26, s * 0.85);
    grd.addColorStop(0, '#ffffff'); grd.addColorStop(0.5, '#cfcfcf');
    grd.addColorStop(1, '#767676');
    g.fillStyle = grd; g.fill();
    g.fillStyle = 'rgba(60,60,60,0.75)';                 // achenes (the "seeds")
    for (let i = 0; i < 14; i++) {
      const a = i * 2.39996;
      const rr = Math.sqrt((i + 1) / 15);
      g.beginPath();
      g.ellipse(cx + Math.cos(a) * s * 0.17 * rr,
                s * 0.46 + Math.sin(a) * s * 0.20 * rr + s * 0.08 * rr,
                s * 0.021, s * 0.030, 0, 0, Math.PI * 2);
      g.fill();
    }
    g.strokeStyle = '#3f3f3f'; g.lineWidth = s * 0.045;   // calyx at the shoulder
    for (let i = 0; i < 5; i++) {
      const a = Math.PI + (i / 4 - 0.5) * 2.4;
      g.beginPath(); g.moveTo(cx, s * 0.32);
      g.lineTo(cx + Math.cos(a) * s * 0.22, s * 0.32 + Math.sin(a) * s * 0.14);
      g.stroke();
    }
  } else if (form === 'aggregate') {
    // Raspberry / thimbleberry: a dome of many small druplets.
    for (let ring = 0; ring < 3; ring++) {
      const n = [1, 6, 9][ring], rr = [0, 0.14, 0.26][ring];
      for (let i = 0; i < n; i++) {
        const a = i / n * Math.PI * 2 + ring * 0.4;
        _fruitBall(g, cx + Math.cos(a) * s * rr,
                   s * 0.46 + Math.sin(a) * s * rr * 0.82,
                   s * (ring === 2 ? 0.085 : 0.10));
      }
    }
  } else if (form === 'flat_cluster') {
    // Mountain ash / highbush cranberry / dogwood: a flat-topped bunch of many
    // small fruits, wider than tall.
    for (let i = 0; i < 15; i++) {
      const a = i * 2.39996, rr = Math.sqrt(i / 15);
      _fruitBall(g, cx + Math.cos(a) * s * 0.38 * rr,
                 s * 0.46 + Math.sin(a) * s * 0.22 * rr, s * 0.085);
    }
  } else {                                    // 'berry' — and the safe default
    _fruitBall(g, cx, s * 0.5, s * 0.42);
    g.fillStyle = 'rgba(50,50,50,0.55)';      // the small calyx scar
    g.beginPath(); g.arc(cx, s * 0.80, s * 0.045, 0, Math.PI * 2); g.fill();
  }
  const t = new THREE.CanvasTexture(cv);
  if (THREE.SRGBColorSpace) t.colorSpace = THREE.SRGBColorSpace;
  t.needsUpdate = true;
  return t;
}

// How big a fruit sprite is drawn, in metres. A cluster form is one sprite
// carrying several fruits, so it has to be bigger than a single berry or the
// individual fruits inside it shrink below a pixel.
const _FRUIT_SIZE = { berry: 0.17, strig: 0.30, raceme: 0.34, cherry: 0.26,
                      pome: 0.19, hip: 0.21, strawberry: 0.20,
                      aggregate: 0.20, flat_cluster: 0.28 };
// …and how many of them a plant wears. A raceme is already eight cherries, so
// eighteen racemes is a solid purple cloud; single berries need more.
const _FRUIT_COUNT = { strig: 0.45, raceme: 0.35, cherry: 0.5,
                       flat_cluster: 0.45, aggregate: 0.7 };

function fruitFormOf(p) {
  const f = (p.fruit_form || '').trim();
  return FRUIT_FORMS.indexOf(f) >= 0 ? f : 'berry';
}

function buildFruit(plants, month, terrain) {
  const byForm = {};
  for (const p of plants || []) {
    if (!p.fruit_color) continue;
    if ((p.opacity ?? 1) < 0.25) continue;
    const fs = p.fruit_start || 0, fe = p.fruit_end || 0;
    if (!fs || month < fs || month > fe) continue;     // not in fruit this month
    const form = fruitFormOf(p);
    (byForm[form] || (byForm[form] = [])).push(p);
  }
  if (!FRUIT_TEX) {
    FRUIT_TEX = {};
    for (const f of FRUIT_FORMS) FRUIT_TEX[f] = makeFruitTexture(f);
  }
  const _c = new THREE.Color();
  for (const form of Object.keys(byForm)) {
    const pos = [], col = [];
    for (const p of byForm[form]) {
      const gy = terrainHeightAt(p.x, p.y, terrain);
      const h = Math.max(0.1, p.height_m), rad = Math.max(0.1, p.canopy_m * 0.5);
      _c.set(p.fruit_color);
      const seed = hashPid(p.plant_id || 1);
      const base = p.plant_type === 'tree' ? 18 : p.plant_type === 'shrub' ? 15 : 8;
      const n = Math.max(2, qn(Math.round(base * (_FRUIT_COUNT[form] || 1))));
      for (let k = 0; k < n; k++) {
        const a = ((seed + k * 97) % 628) / 100;
        const rr = rad * (0.2 + 0.7 * (((seed + k * 61) % 100) / 100));
        const yy = gy + h * (0.4 + 0.45 * (((seed + k * 37) % 100) / 100));
        pos.push(p.x + Math.cos(a) * rr, yy, -(p.y + Math.sin(a) * rr));
        col.push(_c.r, _c.g, _c.b);
      }
    }
    if (!pos.length) continue;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    const mat = clampPointSize(new THREE.PointsMaterial({
      map: FRUIT_TEX[form], color: 0xffffff, vertexColors: true,
      transparent: true, alphaTest: 0.5, depthWrite: false,
      sizeAttenuation: true, size: _FRUIT_SIZE[form] || 0.19,
    }), 72);
    plantsGroup.add(new THREE.Points(geo, mat));
  }
}
