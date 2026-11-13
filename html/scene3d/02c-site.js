// html/scene3d/02c-site.js — the yard itself: what the ground is, the lines on
// it, the street beside it and the houses on it (V3.45, F262).
//
// The V3.43 review's findings 2 and 3: nothing drawn on the ground reached the
// 3D preview. A bed, mulch, a lawn, a path, a patio and a pond were all the one
// meadow texture that ran to the horizon; a fence or a hedge was not there; the
// street was not there; a house was a tan box. This chunk draws what
// src/scene_site.py decides (scene.ground / surfaces / lines / street, and a
// roof hint on each building): it decides nothing itself.
//
// Three rules, each somebody's lesson:
//   * TEXTURE, NEVER GEOMETRY (V2.29). A surface is a flat polygon with a quiet
//     procedural texture. No blades of grass, no chips of mulch: invented
//     ground cover "muddles the real plants from these fake ones".
//   * WHAT IS NOT THE DESIGN IS PALE (the owner's D3). The ground outside the
//     outline, the sidewalk and the road are pale and plain; houses are massing,
//     with no window and no colour nobody recorded.
//   * ANYTHING LYING ON THE GROUND ASKS terrainHeightAt (V3.04). A surface is
//     cut finer where there is terrain, so it follows a slope instead of
//     cutting through it. tests/test_slope_render.py reads it back.
//
// Loaded straight after 02-plants.js, whose buildBoundary and buildBuildings
// moved here (that file was at 687 of its 700 lines). Nothing here runs per
// frame: everything is built once per scene push.

// ── looks ───────────────────────────────────────────────────────────────────
// One quiet tileable texture per look, painted the way the meadow is. `tile`
// is the metres one repeat covers; `rank` orders overlapping surfaces (a path
// lies over a bed, which lies over the lawn) and is each look's depth offset,
// so two surfaces a few millimetres apart do not flicker at a distance.
// src/scene_site.py:KINDS is the list of kinds; a test keeps the two equal.
const SURFACE_LOOK = {
  lawn:         { rank: 1, tile: 5, base: '#7c9c62', soft: true, turns: true,
                  blobs: [[44, 14, 30, ['134,164,104', '108,142,88'], 0.14, 0.22]],
                  specks: [360, 'rgba(84,116,70,0.4)', 0.5, 1.0] },
  meadow:       { rank: 2, tile: 7, soft: true, turns: true, meadow: 0xffffff },
  young_meadow: { rank: 2, tile: 7, soft: true, turns: true, meadow: 0xe9e6c4 },
  seeded:       { rank: 3, tile: 3, base: '#b39a6e', soft: true,
                  blobs: [[30, 8, 20, ['150,126,90', '196,176,128'], 0.14, 0.2]],
                  specks: [500, 'rgba(232,214,160,0.5)', 0.4, 1.2] },
  bed:          { rank: 3, tile: 3, base: '#574b40', soft: true,
                  blobs: [[34, 10, 24, ['74,64,54', '64,55,46'], 0.16, 0.2]],
                  specks: [520, 'rgba(38,30,22,0.5)', 0.5, 1.3] },
  mulch:        { rank: 3, tile: 2.5, base: '#7b5b41', soft: true,
                  blobs: [[30, 8, 18, ['104,76,52', '136,100,70'], 0.18, 0.2]],
                  specks: [700, 'rgba(60,42,28,0.55)', 0.7, 1.9] },
  water:        { rank: 4, tile: 6, base: '#5d90b8', rough: 0.22,
                  blobs: [[18, 20, 46, ['112,160,200', '78,124,170'], 0.1, 0.12]] },
  path:         { rank: 5, tile: 2, base: '#bbb09c', hard: true,
                  blobs: [[20, 8, 18, ['172,162,144', '200,192,176'], 0.14, 0.16]],
                  specks: [800, 'rgba(120,112,98,0.5)', 0.4, 1.1] },
  patio:        { rank: 6, tile: 2.4, base: '#aab0b3', hard: true, joints: 4,
                  blobs: [[16, 20, 40, ['156,162,166', '186,190,192'], 0.12, 0.14]] },
  custom:       { rank: 7, tile: 1, soft: true },   // the person's own colour
  // Not surfaces of the design: the ground where nothing is recorded, and the
  // street. Pale, plain, and under everything.
  pale:         { rank: 0, tile: 9, base: '#bfc3b2', soft: true,
                  blobs: [[26, 24, 56, ['178,184,166', '204,206,192'], 0.12, 0.14]] },
  sidewalk:     { rank: 0, tile: 1.5, base: '#d6d4cc', hard: true, joints: 1 },
  road:         { rank: 0, tile: 4, base: '#a9a9a5', hard: true,
                  specks: [400, 'rgba(120,120,116,0.4)', 0.4, 1.0] },
};
const _SITE_LIFT_M = 0.004;      // per rank, over the ground
const _SITE_EDGE_M = 1.5;        // a draped surface's longest edge, on terrain
const _SITE_MAX_CUTS = 5;

function _siteTexture(look, seed) {
  const s = 256, cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const g = cv.getContext('2d'), rng = mulberry32(seed);
  g.fillStyle = look.base; g.fillRect(0, 0, s, s);
  for (const [n, r0, r1, rgbs, a0, a1] of look.blobs || [])
    for (let i = 0; i < n; i++) {
      const x = rng() * s, y = rng() * s, r = r0 + rng() * (r1 - r0);
      const rgb = rgbs[rng() < 0.5 ? 0 : 1], a = a0 + rng() * (a1 - a0);
      for (const ox of [-s, 0, s]) for (const oy of [-s, 0, s]) {   // wraps
        const grd = g.createRadialGradient(x + ox, y + oy, 0, x + ox, y + oy, r);
        grd.addColorStop(0, 'rgba(' + rgb + ',' + a.toFixed(3) + ')');
        grd.addColorStop(1, 'rgba(' + rgb + ',0)');
        g.fillStyle = grd;
        g.beginPath(); g.arc(x + ox, y + oy, r, 0, Math.PI * 2); g.fill();
      }
    }
  if (look.specks) {
    const [n, colour, r0, r1] = look.specks;
    g.fillStyle = colour;
    for (let i = 0; i < n; i++) {
      g.beginPath();
      g.arc(rng() * s, rng() * s, r0 + rng() * (r1 - r0), 0, Math.PI * 2);
      g.fill();
    }
  }
  if (look.joints) {                       // paving: joints, nothing else
    g.strokeStyle = 'rgba(96,100,102,0.55)'; g.lineWidth = 2;
    for (let i = 0; i < look.joints; i++) {
      const p = Math.round(i * s / look.joints) + 1;
      g.beginPath(); g.moveTo(p, 0); g.lineTo(p, s); g.stroke();
      g.beginPath(); g.moveTo(0, p); g.lineTo(s, p); g.stroke();
    }
  }
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  if (THREE.SRGBColorSpace) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy() || 1);
  return t;
}

// One material per look and season, kept for the session like the ground's
// (05-flowers.js spares them from disposal through siteSharedMats).
const SITE_MATS = {};
function siteSharedMats() { return Object.values(SITE_MATS); }
function _winter(month) { const m = month || 0; return m >= 11 || m <= 3; }

function siteMat(kind, month) {
  const look = SURFACE_LOOK[kind] || SURFACE_LOOK.custom;
  const winter = _winter(month), key = kind + (winter ? '|w' : '');
  let mat = SITE_MATS[key];
  if (!mat) {
    const opts = { roughness: look.rough || 1, side: THREE.DoubleSide,
                   polygonOffset: true, polygonOffsetFactor: -look.rank,
                   polygonOffsetUnits: -2 * look.rank };
    if (winter && kind === 'water') {
      Object.assign(opts, { color: 0xcbd9e4, roughness: 0.35 });      // ice
    } else if (winter) {
      // Snow lies on soft ground; a path, paving and the street are packed.
      opts.map = ensureGroundSnowMat().map; opts.roughness = 0.82;
      if (look.hard) opts.color = 0xd9dee4;
    } else if (look.meadow) {
      opts.map = ensureGroundMat().map;
    } else {
      opts.map = _siteTexture(look, 451 + look.rank * 17 + kind.length);
    }
    mat = SITE_MATS[key] = new THREE.MeshStandardMaterial(opts);
    mat.userData.look = kind;
  }
  // Lawn and meadow turn with the season, as the ground always has.
  if (!winter && look.turns) {
    const base = look.meadow || 0xffffff, m = month || 0;
    mat.color.setHex(m === 10 ? (look.meadow ? 0xbfa878 : 0xd9d2a2)
      : m === 4 ? (look.meadow ? 0xc7cba2 : 0xd8dab6) : base);
  }
  return mat;
}

// The ground where nothing is drawn (the owner's D3): pale for a yard. A scene
// that does not say (the probes, the sprite gallery, anything from before
// V3.45) and a walk through a wild community keep the meadow.
function sitePaleGround(sc) {
  return sc && sc.ground === 'pale' && !_winter(sc.month)
    ? siteMat('pale', sc.month) : null;
}

// ── draped polygons ─────────────────────────────────────────────────────────

// A ring ([[x, y], …], scene metres) as a mesh lying `lift` metres over the
// ground. Where there is terrain each triangle is cut in four, the same way
// for every triangle so neighbours share their new corners and no crack opens,
// until none is longer than about a metre and a half.
function drapedShape(ring, terrain, lift, tile) {
  const flat = new THREE.ShapeGeometry(
    new THREE.Shape(ring.map(p => new THREE.Vector2(p[0], p[1]))));
  const src = flat.attributes.position, pts = [];
  for (let i = 0; i < src.count; i++) pts.push([src.getX(i), src.getY(i)]);
  let tris = Array.from(flat.index.array);
  flat.dispose();
  let xs = ring.map(p => p[0]), ys = ring.map(p => p[1]);
  const span = Math.max(Math.max(...xs) - Math.min(...xs),
                        Math.max(...ys) - Math.min(...ys));
  const cuts = terrain ? Math.max(0, Math.min(_SITE_MAX_CUTS,
    Math.ceil(Math.log2(Math.max(1, span) / _SITE_EDGE_M)))) : 0;
  for (let c = 0; c < cuts; c++) {
    const made = new Map(), out = [];
    const mid = (a, b) => {
      const k = a < b ? a * 1e6 + b : b * 1e6 + a;
      let i = made.get(k);
      if (i === undefined) {
        i = pts.length;
        pts.push([(pts[a][0] + pts[b][0]) / 2, (pts[a][1] + pts[b][1]) / 2]);
        made.set(k, i);
      }
      return i;
    };
    for (let i = 0; i < tris.length; i += 3) {
      const a = tris[i], b = tris[i + 1], c2 = tris[i + 2];
      const ab = mid(a, b), bc = mid(b, c2), ca = mid(c2, a);
      out.push(a, ab, ca, ab, b, bc, ca, bc, c2, ab, bc, ca);
    }
    tris = out;
  }
  const pos = new Float32Array(pts.length * 3), uv = new Float32Array(pts.length * 2);
  pts.forEach(([x, y], i) => {
    pos[i * 3] = x; pos[i * 3 + 1] = terrainHeightAt(x, y, terrain) + lift;
    pos[i * 3 + 2] = -y;
    uv[i * 2] = x / tile; uv[i * 2 + 1] = y / tile;
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  geo.setIndex(tris);
  geo.computeVertexNormals();
  return geo;
}

function _surfaceMesh(group, ring, kind, mat, terrain, name) {
  if (!ring || ring.length < 3) return null;
  const look = SURFACE_LOOK[kind] || SURFACE_LOOK.custom;
  const mesh = new THREE.Mesh(
    drapedShape(ring, terrain, _SITE_LIFT_M * (look.rank + 1), look.tile), mat);
  mesh.name = name;
  mesh.receiveShadow = true;
  mesh.renderOrder = look.rank;
  group.add(mesh);
  return mesh;
}

// A road line as wide quads, one per stretch, each a polygon of its own.
function _ribbonRings(points, width) {
  const out = [], h = width / 2;
  for (let i = 0; i + 1 < points.length; i++) {
    const [ax, ay] = points[i], [bx, by] = points[i + 1];
    const len = Math.hypot(bx - ax, by - ay);
    if (len < 0.01) continue;
    const nx = -(by - ay) / len * h, ny = (bx - ax) / len * h;
    const ex = (bx - ax) / len * h, ey = (by - ay) / len * h;   // closes a bend
    out.push([[ax - ex + nx, ay - ey + ny], [bx + ex + nx, by + ey + ny],
              [bx + ex - nx, by + ey - ny], [ax - ex - nx, ay - ey - ny]]);
  }
  return out;
}

// ── lines: fences and hedges ────────────────────────────────────────────────

// A box from (ax, ay) to (bx, by), standing `up` metres over the ground at its
// two ends and leaning with the slope between them. `top` narrows its top to
// that share of its width: a clipped hedge is not a wall.
function _boxBetween(ax, ay, bx, by, terrain, up, h, w, top) {
  const ga = terrainHeightAt(ax, ay, terrain), gb = terrainHeightAt(bx, by, terrain);
  const dx = bx - ax, dz = -(by - ay), run = Math.hypot(dx, dz) || 1e-6;
  const geo = new THREE.BoxGeometry(Math.hypot(run, gb - ga), h, w);
  if (top) {
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++)
      if (pos.getY(i) > 0) pos.setZ(i, pos.getZ(i) * top);
    geo.computeVertexNormals();
  }
  geo.translate(0, h / 2 + up, 0);
  geo.applyMatrix4(new THREE.Matrix4().makeRotationZ(Math.atan2(gb - ga, run)));
  geo.applyMatrix4(new THREE.Matrix4().makeRotationY(Math.atan2(-dz, dx)));
  geo.translate((ax + bx) / 2, (ga + gb) / 2, -(ay + by) / 2);
  return geo;
}

// The stops along a line, no further apart than `step`: every corner is one.
function _stops(points, step) {
  const out = [points[0]];
  for (let i = 0; i + 1 < points.length; i++) {
    const [ax, ay] = points[i], [bx, by] = points[i + 1];
    const n = Math.max(1, Math.ceil(Math.hypot(bx - ax, by - ay) / step));
    for (let k = 1; k <= n; k++)
      out.push([ax + (bx - ax) * k / n, ay + (by - ay) * k / n]);
  }
  return out;
}

const _LINE_GREEN = { hedge: 0x58794a, living_fence: 0x5f8050, windbreak: 0x4f6f47 };
function buildLines(group, lines, terrain, month) {
  const fence = [], green = {};
  for (const ln of lines || []) {
    const pts = ln.points || [];
    if (pts.length < 2) continue;
    const h = ln.height_m || 1.2;
    if (ln.kind === 'fence') {
      // Posts and three rails: a fence a person can see through and over.
      const posts = _stops(pts, 2.4);
      for (const [x, y] of posts) {
        const p = new THREE.BoxGeometry(0.1, h + 0.08, 0.1);
        p.translate(x, terrainHeightAt(x, y, terrain) + (h + 0.08) / 2, -y);
        fence.push(p);
      }
      for (let i = 0; i + 1 < posts.length; i++)
        for (const up of [0.2, 0.5, 0.8])       // the top rail under the posts' tops
          fence.push(_boxBetween(posts[i][0], posts[i][1], posts[i + 1][0],
            posts[i + 1][1], terrain, up * h, 0.12 * h, 0.03));
    } else {
      // A hedge, a living fence, a windbreak: one plain mass. Nothing records
      // its plants one by one, so none is drawn.
      const stops = _stops(pts, 2), w = ln.width_m || 1.5;
      const key = _LINE_GREEN[ln.kind] ? ln.kind : 'hedge';
      for (let i = 0; i + 1 < stops.length; i++)
        (green[key] = green[key] || []).push(_boxBetween(stops[i][0], stops[i][1],
          stops[i + 1][0], stops[i + 1][1], terrain, 0, h, w, 0.6));
    }
  }
  const add = (geos, colour, name) => {
    if (!geos.length) return;
    const mesh = new THREE.Mesh(geos.length === 1 ? geos[0] : mergeGeometries(geos, false),
      new THREE.MeshStandardMaterial({ color: colour, roughness: 1 }));
    mesh.name = name;
    mesh.castShadow = mesh.receiveShadow = true;
    group.add(mesh);
  };
  add(fence, 0xb9a98c, 'fences');
  for (const key in green)        // bare and twiggy under snow
    add(green[key], _winter(month) ? 0x6f6a55 : _LINE_GREEN[key], 'hedges:' + key);
}

// ── everything on the ground ────────────────────────────────────────────────

function buildSite(group, sc) {
  const t = sc.terrain || null, m = sc.month;
  const street = sc.street || null;
  if (street) {
    for (const r of street.roads || [])
      for (const ring of _ribbonRings(r.points || [], r.width_m || 8))
        _surfaceMesh(group, ring, 'road', siteMat('road', m), t, 'street:road');
    _surfaceMesh(group, street.road, 'road', siteMat('road', m), t, 'street:road');
    _surfaceMesh(group, street.sidewalk, 'sidewalk', siteMat('sidewalk', m), t,
                 'street:sidewalk');
  }
  for (const s of sc.surfaces || []) {
    const kind = SURFACE_LOOK[s.kind] ? s.kind : 'custom';
    let mat = siteMat(kind, m);
    if (kind === 'custom' && !_winter(m)) {
      // The person's own colour, flat: one material for this one surface.
      mat = new THREE.MeshStandardMaterial({ color: s.color || '#9e9e9e',
        roughness: 1, side: THREE.DoubleSide, polygonOffset: true,
        polygonOffsetFactor: -SURFACE_LOOK.custom.rank,
        polygonOffsetUnits: -2 * SURFACE_LOOK.custom.rank });
      mat.userData.look = 'custom';
    }
    _surfaceMesh(group, s.ring, kind, mat, t, 'surface:' + s.kind);
  }
  buildLines(group, sc.lines, t, m);
}

// ── the outline ─────────────────────────────────────────────────────────────

// Draped over the ground (V3.04): each edge cut into steps of a metre, each
// 12 cm above the ground under it. A ring at a flat 12 cm ran under a slope.
function buildBoundary(group, ring, terrain) {
  if (!ring || ring.length < 3) return;
  const pts = [], closed = ring.concat([ring[0]]);
  for (let i = 0; i + 1 < closed.length; i++) {
    const [x0, y0] = closed[i], [x1, y1] = closed[i + 1];
    const n = terrain ? Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0))) : 1;
    for (let k = 0; k < n; k++) {
      const x = x0 + (x1 - x0) * k / n, y = y0 + (y1 - y0) * k / n;
      pts.push(new THREE.Vector3(x, terrainHeightAt(x, y, terrain) + 0.12, -y));
    }
  }
  pts.push(pts[0].clone());
  const line = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color: 0xf9a825 }));
  line.name = 'boundary';
  group.add(line);
}

// ── buildings / footprints ─────────────────────────────────────────────────

// Plain massing (the owner's D3): light walls and a darker roof with an
// overhang, and nothing nobody recorded: no window, no door, no colour. The
// roof is the scene's hint (src/scene_site.py:roof_for): a gable on a clean
// four-corner footprint, its ridge AT the recorded height with the walls
// stopping lower, so a house is never taller than the shade map's; flat on
// anything else, and on a scene that carries no hint.
//
// Static footprints: each ring is extruded and all of a kind merged into one
// mesh, so N buildings cost a few draw calls. The −90° turn is baked into each
// geometry: shape (x, y) → (x, −z), depth → +y. On a slope (V3.04) each stands
// on the lowest ground under its ring, so no side hangs in the air, and keeps
// its height above the highest, so none is buried.
const _ROOF_OVERHANG_M = 0.4, _FLAT_ROOF_M = 0.2;

function _extruded(ring, base, depth) {
  const geo = new THREE.ExtrudeGeometry(
    new THREE.Shape(ring.map(p => new THREE.Vector2(p[0], p[1]))),
    { depth: Math.max(0.05, depth), bevelEnabled: false });
  geo.rotateX(-Math.PI / 2);
  geo.translate(0, base, 0);
  return geo;
}

// Triangles from points given as [x, y(up), z], two-sided at the material.
function _faces(tris) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(tris.flat(2)), 3));
  geo.computeVertexNormals();
  return geo;
}

function _gable(ring, roof, wallTop, ridgeY, walls, roofs) {
  const [[r0x, r0y], [r1x, r1y]] = roof.ridge;
  const len = Math.hypot(r1x - r0x, r1y - r0y) || 1;
  const ux = (r1x - r0x) / len, uy = (r1y - r0y) / len, vx = -uy, vy = ux;
  // Half the short side: how far the corners stand off the ridge line.
  const half = ring.reduce((s, [x, y]) =>
    s + Math.abs((x - r0x) * vx + (y - r0y) * vy), 0) / ring.length;
  const o = _ROOF_OVERHANG_M, P = (x, y, h) => [x, h, -y];
  // The two gable ends, in the walls' own colour: each short side, up to the
  // ridge end that sits over its middle.
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i], b = ring[(i + 1) % ring.length];
    const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
    for (const [ex, ey] of roof.ridge)
      if (Math.hypot(mx - ex, my - ey) < 0.05)
        walls.push(_faces([[P(a[0], a[1], wallTop), P(b[0], b[1], wallTop),
                            P(ex, ey, ridgeY)]]));
  }
  // The two slopes, running past the walls by the overhang on every side.
  const eave = ridgeY - (ridgeY - wallTop) * (half + o) / half;
  const ax = r0x - ux * o, ay = r0y - uy * o, bx = r1x + ux * o, by = r1y + uy * o;
  for (const side of [1, -1]) {
    const ox = vx * side * (half + o), oy = vy * side * (half + o);
    const A = P(ax, ay, ridgeY), B = P(bx, by, ridgeY);
    const A2 = P(ax + ox, ay + oy, eave), B2 = P(bx + ox, by + oy, eave);
    roofs.push(_faces([[A, B, B2], [A, B2, A2]]));
  }
}

function buildBuildings(group, buildings, terrain, month) {
  const walls = [], roofs = [], canopies = [];
  for (const bld of buildings || []) {
    const ring = bld.ring || [];
    if (ring.length < 3) continue;
    const hs = ring.map(p => terrainHeightAt(p[0], p[1], terrain));
    const lo = Math.min(...hs), hi = Math.max(...hs);
    const height = Math.max(0.3, bld.height_m || 3), top = hi + height;
    if (bld.kind === 'canopy') { canopies.push(_extruded(ring, lo, top - lo)); continue; }
    const roof = bld.roof || {};
    if (roof.form === 'gable' && roof.ridge && roof.rise_m > 0) {
      const wallTop = top - roof.rise_m;
      walls.push(_extruded(ring, lo, wallTop - lo));
      _gable(ring, roof, wallTop, top, walls, roofs);
    } else if (roof.form === 'flat' && height > 1) {
      // A slab a little wider than the walls, about the footprint's middle.
      const xs = ring.map(p => p[0]), ys = ring.map(p => p[1]);
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2, w = Math.max(...xs) - Math.min(...xs);
      const cy = (Math.min(...ys) + Math.max(...ys)) / 2, d = Math.max(...ys) - Math.min(...ys);
      const kx = (w + 2 * _ROOF_OVERHANG_M) / Math.max(w, 0.1);
      const ky = (d + 2 * _ROOF_OVERHANG_M) / Math.max(d, 0.1);
      walls.push(_extruded(ring, lo, top - _FLAT_ROOF_M - lo));
      roofs.push(_extruded(ring.map(([x, y]) => [cx + (x - cx) * kx, cy + (y - cy) * ky]),
                           top - _FLAT_ROOF_M, _FLAT_ROOF_M));
    } else {
      walls.push(_extruded(ring, lo, top - lo));      // no hint: a box, as before
    }
  }
  const add = (geos, mat, name) => {
    if (!geos.length) return;
    // The extrusions carry an index and UVs and the hand-made faces neither.
    const plain = geos.map((g) => {
      const n = g.index ? g.toNonIndexed() : g;
      n.deleteAttribute('uv');
      if (n !== g) g.dispose();
      return n;
    });
    const mesh = new THREE.Mesh(plain.length === 1 ? plain[0] : mergeGeometries(plain, false), mat);
    mesh.name = name;
    mesh.castShadow = mesh.receiveShadow = true;
    group.add(mesh);
  };
  add(walls, new THREE.MeshStandardMaterial({ color: 0xd8d1c3, roughness: 0.95,
    side: THREE.DoubleSide }), 'buildings');
  add(roofs, new THREE.MeshStandardMaterial({      // snow lies on a roof too
    color: _winter(month) ? 0xe6ebf1 : 0x80766c, roughness: 0.9,
    side: THREE.DoubleSide }), 'roofs');
  add(canopies, new THREE.MeshStandardMaterial({ color: 0x4e6e52, roughness: 1,
    transparent: true, opacity: 0.85 }), 'canopys');
}
