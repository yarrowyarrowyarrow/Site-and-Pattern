/* Site & Pattern — 3D viewer: plant surfaces and the material that wears them.
 *
 * Design principle P5 — see docs/DESIGN_PHILOSOPHY.md
 *
 * Everything in this viewer was flat-shaded vertex colour until V2.29: no bark
 * texture, no leaf texture, so a trunk was one brown and a crown one green and
 * the app read as a diagram rather than an illustration. The sprite audit put
 * texture LAST on its list of improvements precisely because it multiplies
 * whatever variety is already there — "texturing a library that has 75 distinct
 * looks just makes 75 nicer-looking repeats". Items 1-4 have since landed, so
 * this is now the level-up it was held back to be.
 *
 * Surfaces are procedural rather than UV-mapped images, for two reasons that are
 * contract, not preference (docs/3D_ASSETS.md):
 *   * the baked GLBs carry POSITION, NORMAL and COLOR_0 and NO texture
 *     coordinates, and tests/test_model_assets.py forbids them embedding
 *     textures at all;
 *   * these are INSTANCED meshes, so one per-archetype UV set would repeat
 *     identically across every instance anyway.
 * So the pattern is sampled from OBJECT space in the fragment shader, offset per
 * instance so two neighbouring aspens are not stamped from the same grain.
 *
 * WHY ONE TEXTURE PER CLASS RATHER THAN ONE SHARED ATLAS. The roadmap (F63)
 * specified a single 1024² atlas with bark rows and leaf rows. An atlas earns
 * its keep when one material has to reach several patterns; here each material
 * samples exactly one class, so the atlas buys nothing and costs real fidelity:
 * a ten-row atlas gives each pattern ~100px of vertical space, and bark grain
 * has to tile VERTICALLY up a trunk, which a row inside an atlas cannot do
 * without bleeding into its neighbour. Ten separate 512² canvases tile freely on
 * both axes, need no row uniform and no inset fudge, and cost less texture
 * memory than the atlas would (2.6 Mpx against a 1024² per... nothing). The
 * generated-at-runtime part of the roadmap's design is kept exactly: no asset
 * files, nothing to fetch, nothing to bundle, deterministic.
 */

// ── the surface vocabulary ──────────────────────────────────────────────────
// Bark classes are the ones a person can actually name at ten paces, which is
// the right granularity for a legible model (P5) and for what the seed data can
// honestly record (P9). Species → class comes from the catalogue
// (`bark_texture`, schema v52), never from a genus table in here — same rule as
// `flower_form` and `fruit_form`.
const BARK_CLASSES = ['smooth', 'furrowed', 'papery', 'shaggy', 'scaly'];
const LEAF_SURFACES = ['matte', 'glossy', 'pubescent', 'glaucous'];

// Per-genus fallback for a species with nothing recorded — an honest default
// rather than an invented measurement, and the same shape as the profile tables
// in 02-plants.js.
const BARK_BY_GENUS = {
  betula: 'papery', populus: 'smooth', quercus: 'furrowed', salix: 'furrowed',
  picea: 'scaly', pinus: 'scaly', abies: 'smooth', pseudotsuga: 'furrowed',
  larix: 'scaly', juniperus: 'shaggy', prunus: 'smooth', malus: 'scaly',
  amelanchier: 'smooth', cornus: 'smooth', alnus: 'smooth', corylus: 'smooth',
  acer: 'smooth', sorbus: 'smooth', crataegus: 'scaly', ribes: 'shaggy',
  rubus: 'shaggy', elaeagnus: 'shaggy', shepherdia: 'shaggy',
};

function barkClassFor(p) {
  const rec = (p && p.bark_texture || '').toLowerCase();
  if (BARK_CLASSES.indexOf(rec) >= 0) return rec;
  return BARK_BY_GENUS[(p && p.genus || '').toLowerCase()] || 'furrowed';
}

function leafSurfaceFor(p) {
  const rec = (p && p.leaf_surface || '').toLowerCase();
  return LEAF_SURFACES.indexOf(rec) >= 0 ? rec : 'matte';
}

// ── the procedural surfaces ─────────────────────────────────────────────────
// Mid grey is "leave the colour alone": the shader reads one channel and treats
// 0.5 as unity, so a pattern's MEAN is a brightness shift as well as its
// variance being a texture. That is deliberate for the leaf surfaces — a
// pubescent leaf really is paler than a glossy one of the same pigment.
const DETAIL_PX = 512;
let DETAIL_TEX = null;

function _lcg(seed) {
  let n = seed;
  return () => (n = (n * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
}

// A vertical run with lateral wander, used by every bark class that has grain.
function _fissure(g, rnd, s, x, opts) {
  const step = opts.step || 14, wander = opts.wander || 6;
  g.beginPath();
  let y = -10, xx = x;
  g.moveTo(xx, y);
  while (y < s + 10) {
    y += step * (0.6 + rnd() * 0.8);
    xx += (rnd() - 0.5) * wander;
    g.lineTo(xx, y);
  }
  g.stroke();
}

function _barkSmooth(g, rnd, s) {
  // Aspen and balsam poplar: a pale, almost featureless bole whose whole
  // character is horizontal lenticel dashes and the black scars where a branch
  // was shed. Drawn wrong (as fissures) an aspen stops being an aspen.
  for (let i = 0; i < 90; i++) {
    const x = rnd() * s, y = rnd() * s, w = 4 + rnd() * 16;
    g.strokeStyle = `rgba(48,46,40,${0.10 + rnd() * 0.22})`;
    g.lineWidth = 1 + rnd() * 1.6;
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + w, y + (rnd() - 0.5) * 2); g.stroke();
  }
  for (let i = 0; i < 7; i++) {          // shed-branch scars
    const x = rnd() * s, y = rnd() * s, r = 7 + rnd() * 16;
    const grd = g.createRadialGradient(x, y, 0, x, y, r);
    grd.addColorStop(0, 'rgba(28,26,22,0.62)');
    grd.addColorStop(0.7, 'rgba(60,56,48,0.24)');
    grd.addColorStop(1, 'rgba(128,128,128,0)');
    g.fillStyle = grd;
    g.beginPath(); g.ellipse(x, y, r, r * 0.72, 0, 0, Math.PI * 2); g.fill();
  }
}

function _barkFurrowed(g, rnd, s) {
  // Bur oak, mature poplar, Douglas-fir: deep vertical fissures with a lit ridge
  // beside each shadow. The paired light/dark stroke is what makes a flat canvas
  // read as relief under a single directional light.
  for (let i = 0; i < 130; i++) {
    const x = rnd() * s;
    g.lineWidth = 2 + rnd() * 7;
    g.strokeStyle = `rgba(26,22,18,${0.20 + rnd() * 0.30})`;
    _fissure(g, rnd, s, x, { step: 16, wander: 7 });
    g.lineWidth = 1 + rnd() * 3;
    g.strokeStyle = `rgba(236,230,214,${0.07 + rnd() * 0.13})`;
    _fissure(g, rnd, s, x + 3 + rnd() * 4, { step: 16, wander: 7 });
  }
}

function _barkPapery(g, rnd, s) {
  // Paper birch: horizontal peeling bands, dark lenticel dashes, and the curled
  // lifting edge that catches light. Horizontal, emphatically — birch is the one
  // bark in the catalogue whose grain runs the other way.
  for (let i = 0; i < 26; i++) {
    const y = rnd() * s, h = 3 + rnd() * 13;
    g.fillStyle = `rgba(40,36,32,${0.07 + rnd() * 0.16})`;
    g.fillRect(0, y, s, h);
    g.fillStyle = `rgba(252,250,244,${0.10 + rnd() * 0.20})`;
    g.fillRect(0, y + h, s, 1 + rnd() * 3);              // the lifted curl
  }
  for (let i = 0; i < 150; i++) {
    const x = rnd() * s, y = rnd() * s, w = 6 + rnd() * 34;
    g.strokeStyle = `rgba(30,26,22,${0.24 + rnd() * 0.34})`;
    g.lineWidth = 1 + rnd() * 2.4;
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + w, y); g.stroke();
  }
}

function _barkShaggy(g, rnd, s) {
  // Juniper, silverberry, older currant canes: long fibrous strips lifting away
  // from the stem, torn rather than fissured.
  for (let i = 0; i < 70; i++) {
    const x = rnd() * s, w = 3 + rnd() * 13;
    g.fillStyle = `rgba(34,29,24,${0.12 + rnd() * 0.26})`;
    g.fillRect(x, 0, w, s);
    g.fillStyle = `rgba(228,220,204,${0.06 + rnd() * 0.14})`;
    g.fillRect(x + w, 0, 1 + rnd() * 2.5, s);
    for (let k = 0; k < 5; k++) {                        // torn ends
      const y = rnd() * s;
      g.fillStyle = `rgba(20,17,14,${0.20 + rnd() * 0.26})`;
      g.fillRect(x - 1, y, w + 2, 1 + rnd() * 3);
    }
  }
}

function _barkScaly(g, rnd, s) {
  // Spruce, pine, hawthorn: irregular plates with dark gaps between them. Drawn
  // as filled cells with a shadowed lower edge, which is what separates a plate
  // from a fissure at any distance.
  for (let i = 0; i < 240; i++) {
    const x = rnd() * s, y = rnd() * s;
    const w = 10 + rnd() * 30, h = 7 + rnd() * 20;
    g.fillStyle = rnd() < 0.5
      ? `rgba(214,204,186,${0.06 + rnd() * 0.15})`
      : `rgba(44,38,31,${0.08 + rnd() * 0.18})`;
    g.beginPath();
    g.ellipse(x, y, w * 0.5, h * 0.5, (rnd() - 0.5) * 0.6, 0, Math.PI * 2);
    g.fill();
    g.strokeStyle = `rgba(22,19,16,${0.18 + rnd() * 0.22})`;
    g.lineWidth = 1 + rnd() * 2;
    g.stroke();
  }
}

// Foliage break-up. Deliberately low-contrast — this is a break-up, not a
// pattern — but the four surfaces differ in MEAN as well as in grain, which is
// most of what separates a glaucous sage from a glossy dogwood on screen.
function _leafSurface(g, rnd, s, kind) {
  const cfg = {
    matte:     { blobs: 260, amp: 0.15, lift: 0.00, spec: 0 },
    glossy:    { blobs: 200, amp: 0.20, lift: 0.03, spec: 46 },
    pubescent: { blobs: 300, amp: 0.10, lift: 0.10, spec: 0, hair: 900 },
    glaucous:  { blobs: 170, amp: 0.07, lift: 0.13, spec: 0, bloom: true },
  }[kind] || {};
  if (cfg.lift) {
    g.fillStyle = `rgba(255,255,255,${cfg.lift * 2})`;
    g.fillRect(0, 0, s, s);
  }
  for (let i = 0; i < (cfg.blobs || 0); i++) {
    const x = rnd() * s, y = rnd() * s, r = 8 + rnd() * 52;
    const dark = rnd() < 0.5;
    const a = 0.04 + rnd() * cfg.amp;
    const grd = g.createRadialGradient(x, y, 0, x, y, r);
    grd.addColorStop(0, dark ? `rgba(28,42,22,${a})` : `rgba(238,248,218,${a})`);
    grd.addColorStop(1, 'rgba(128,128,128,0)');
    g.fillStyle = grd;
    g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill();
  }
  for (let i = 0; i < (cfg.spec || 0); i++) {   // glossy: hard little highlights
    const x = rnd() * s, y = rnd() * s, w = 10 + rnd() * 46;
    g.strokeStyle = `rgba(255,255,255,${0.10 + rnd() * 0.26})`;
    g.lineWidth = 1 + rnd() * 3;
    g.beginPath();
    g.moveTo(x, y); g.lineTo(x + w, y + (rnd() - 0.5) * 14); g.stroke();
  }
  for (let i = 0; i < (cfg.hair || 0); i++) {   // pubescent: fine pale down
    const x = rnd() * s, y = rnd() * s;
    g.fillStyle = `rgba(255,255,250,${0.05 + rnd() * 0.16})`;
    g.fillRect(x, y, 1 + rnd(), 1 + rnd() * 3);
  }
  if (cfg.bloom) {                              // glaucous: waxy powder
    for (let i = 0; i < 1400; i++) {
      const x = rnd() * s, y = rnd() * s;
      g.fillStyle = `rgba(250,252,255,${0.04 + rnd() * 0.10})`;
      g.fillRect(x, y, 1 + rnd() * 2, 1 + rnd() * 2);
    }
  }
}

function _needleSurface(g, rnd, s) {
  // A needle's one visible mark is the pale stomatal band running its length.
  for (let i = 0; i < 220; i++) {
    const x = rnd() * s;
    g.strokeStyle = rnd() < 0.45
      ? `rgba(226,238,232,${0.08 + rnd() * 0.18})`
      : `rgba(28,40,32,${0.08 + rnd() * 0.20})`;
    g.lineWidth = 1 + rnd() * 3;
    g.beginPath(); g.moveTo(x, 0); g.lineTo(x + (rnd() - 0.5) * 6, s); g.stroke();
  }
}

function makeDetailTexture(kind) {
  const s = DETAIL_PX, cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const g = cv.getContext('2d');
  g.fillStyle = '#808080';
  g.fillRect(0, 0, s, s);
  // Seeded per kind so every class is deterministic and none is a copy.
  const rnd = _lcg(7 + kind.length * 131 + (kind.charCodeAt(0) || 0) * 17);
  if (kind === 'needle') _needleSurface(g, rnd, s);
  else if (kind.indexOf('bark') === 0) {
    ({ smooth: _barkSmooth, furrowed: _barkFurrowed, papery: _barkPapery,
       shaggy: _barkShaggy, scaly: _barkScaly }[kind.slice(5)]
     || _barkFurrowed)(g, rnd, s);
  } else _leafSurface(g, rnd, s, kind.slice(5));
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.needsUpdate = true;
  return t;
}

function detailTexture(kind) {
  if (!DETAIL_TEX) DETAIL_TEX = {};
  if (!DETAIL_TEX[kind]) DETAIL_TEX[kind] = makeDetailTexture(kind);
  return DETAIL_TEX[kind];
}

// ── sway ────────────────────────────────────────────────────────────────────
// Its own function so the material above does not have to know how wind works,
// and so F68's real-wind version has one place to land.
function applyWindShader(shader, strength, stiffness) {
  for (const u of ['uTime', 'uWindDir', 'uWindAmp', 'uGust', 'uShelter',
                   'uShelterRect', 'uHasShelter'])
    shader.uniforms[u] = windUniforms[u];
  shader.vertexShader =
    'uniform float uTime;\nuniform vec2 uWindDir;\nuniform float uWindAmp;\n'
    + 'uniform float uGust;\nuniform sampler2D uShelter;\n'
    + 'uniform vec4 uShelterRect;\nuniform float uHasShelter;\n'
    + shader.vertexShader;
  shader.vertexShader = shader.vertexShader.replace(
    '#include <begin_vertex>',
    [
      '#include <begin_vertex>',
      '{',
      '  #ifdef USE_INSTANCING',
      '  vec3 iPos = vec3(instanceMatrix[3][0], instanceMatrix[3][1], instanceMatrix[3][2]);',
      '  #else',
      '  vec3 iPos = vec3(0.0);',
      '  #endif',
      '  float hf = clamp(transformed.y, 0.0, 1.2);',           // taller verts sway more
      '  float ph = iPos.x * 0.35 + iPos.z * 0.35;',            // per-plant phase
      '  float wv = sin(uTime * 1.3 + ph + position.x * 1.1 + position.z * 0.8) * 0.6',
      '           + sin(uTime * 2.6 + ph * 1.7) * 0.4;',
      // A gust is a slow swell over the whole yard, offset by position so it
      // travels across the design rather than pulsing everywhere at once —
      // which is most of what separates "alive" from "vibrating".
      '  float gust = 1.0 + uGust * sin(uTime * 0.31 + iPos.x * 0.06',
      '                                 + iPos.z * 0.05);',
      // How much of its sway this plant keeps where it stands. 1.0 in the open;
      // less inside the lee of the design's own windbreaks.
      '  float shelter = 1.0;',
      '  if (uHasShelter > 0.5) {',
      '    vec2 suv = vec2((iPos.x - uShelterRect.x) / max(1e-4, uShelterRect.z),',
      // Scene +y north is -z in the viewer, which is how the grid was written.
      '                    (-iPos.z - uShelterRect.y) / max(1e-4, uShelterRect.w));',
      '    if (suv.x > 0.0 && suv.x < 1.0 && suv.y > 0.0 && suv.y < 1.0)',
      '      shelter = texture2D(uShelter, suv).r;',
      '  }',
      '  float amp = ' + (strength * stiffness).toFixed(5)
        + ' * hf * hf * uWindAmp * gust * shelter;',
      // Along the wind, not along a hard-coded diagonal.
      '  transformed.x += wv * amp * uWindDir.x;',
      '  transformed.z += wv * amp * uWindDir.y;',
      '}',
    ].join('\n'));
}

// ── the site's real wind → the uniforms (F68) ───────────────────────────────
// src/wind_scene.py puts {from_deg, mean_kmh, season, approximate, shelter?} on
// the scene. Everything here is a UNIFORM, so a month change re-aims the whole
// yard without recompiling a single shader.
let _SHELTER_TEX = null;

window.applySceneWind = applySceneWind;
function applySceneWind(wind) {
  const u = windUniforms;
  if (!wind || wind.from_deg == null) {
    u.uWindDir.value.set(0.82, 0.57);       // the pre-F68 diagonal
    u.uWindAmp.value = 1.0;
    u.uGust.value = 0.35;
    u.uHasShelter.value = 0;
    return;
  }
  // Degrees the wind blows FROM, 0 = N (src.wind's convention). The vector
  // points where it blows TO, in scene axes: +x east, and north is -z.
  const rad = (wind.from_deg + 180) * Math.PI / 180;
  u.uWindDir.value.set(Math.sin(rad), -Math.cos(rad));
  // A calm day should barely move and a 40 km/h prairie wind should be
  // unmistakable, but the sway is stylised, so this is a bounded ramp rather
  // than a physical model (P9 — no false precision).
  const kmh = Math.max(0, Math.min(45, wind.mean_kmh || 0));
  u.uWindAmp.value = 0.45 + kmh / 45 * 1.25;
  u.uGust.value = 0.22 + kmh / 45 * 0.55;
  const sh = wind.shelter;
  if (!sh || !sh.keep || !sh.keep.length) { u.uHasShelter.value = 0; return; }
  const data = new Uint8Array(sh.cols * sh.rows);
  for (let i = 0; i < data.length && i < sh.keep.length; i++) data[i] = sh.keep[i];
  if (_SHELTER_TEX) _SHELTER_TEX.dispose();
  _SHELTER_TEX = new THREE.DataTexture(data, sh.cols, sh.rows,
                                       THREE.RedFormat, THREE.UnsignedByteType);
  _SHELTER_TEX.minFilter = _SHELTER_TEX.magFilter = THREE.LinearFilter;
  _SHELTER_TEX.needsUpdate = true;
  u.uShelter.value = _SHELTER_TEX;
  u.uShelterRect.value.set(sh.min_x, sh.min_y,
                           sh.max_x - sh.min_x, sh.max_y - sh.min_y);
  u.uHasShelter.value = 1;
}

// ── the material ────────────────────────────────────────────────────────────

function plantMaterial(opts = {}) {
  const mat = new THREE.MeshStandardMaterial({
    roughness: opts.roughness ?? 0.9,
    vertexColors: !!opts.vertexColors,
    side: opts.doubleSide ? THREE.DoubleSide : THREE.FrontSide,
    flatShading: !!opts.flatShading,
  });
  const strength = opts.wind || 0;
  const detail = opts.detail || '';
  const dscale = opts.detailScale || 1.0;
  const damount = opts.detailAmount ?? 0.55;
  // Bark is a cylinder and its grain runs up the trunk; foliage has no axis
  // worth respecting and takes a triplanar blend instead.
  const cylindrical = detail.indexOf('bark') === 0;
  if (strength > 0 || detail) {
    mat.onBeforeCompile = (shader) => {
      if (detail) {
        shader.uniforms.uDetail = { value: detailTexture(detail) };
        // Object-space position + a per-instance offset, so the grain follows
        // the geometry (it does not swim when a plant sways or the camera
        // moves) but neighbouring copies of one archetype are not identical.
        shader.vertexShader = 'varying vec3 vDetailPos;\nvarying vec3 vDetailNrm;\n'
          + shader.vertexShader;
        shader.vertexShader = shader.vertexShader.replace(
          '#include <begin_vertex>',
          ['#include <begin_vertex>',
           '{',
           '  #ifdef USE_INSTANCING',
           '  vec3 dOff = vec3(instanceMatrix[3][0], instanceMatrix[3][1], instanceMatrix[3][2]);',
           '  #else',
           '  vec3 dOff = vec3(0.0);',
           '  #endif',
           '  vDetailPos = position + fract(dOff * 0.37) * 3.1;',
           '  vDetailNrm = normal;',
           '}'].join('\n'));
        shader.fragmentShader =
          'uniform sampler2D uDetail;\nvarying vec3 vDetailPos;\n'
          + 'varying vec3 vDetailNrm;\n' + shader.fragmentShader;
        const uv = cylindrical
          ? ['  vec2 dUV = vec2(atan(vDetailPos.x, vDetailPos.z) * 0.6,',
             '                  vDetailPos.y * ' + (dscale * 3.0).toFixed(3) + ');',
             '  float d = texture2D(uDetail, dUV).r;'].join('\n')
          // Triplanar: three planar samples blended on the surface normal. The
          // old cheap two-plane mix(xz, xy, 0.5) smeared on any face that faced
          // the third axis, which on a leaf card — a flat quad at an arbitrary
          // angle — is most of them, and the smear is exactly the streaking the
          // detail exists to avoid.
          : ['  vec3 dN = abs(normalize(vDetailNrm)) + 1e-5;',
             '  dN /= (dN.x + dN.y + dN.z);',
             '  float ds = ' + dscale.toFixed(3) + ';',
             '  float d = texture2D(uDetail, vDetailPos.yz * ds).r * dN.x',
             '          + texture2D(uDetail, vDetailPos.xz * ds).r * dN.y',
             '          + texture2D(uDetail, vDetailPos.xy * ds).r * dN.z;'].join('\n');
        shader.fragmentShader = shader.fragmentShader.replace(
          '#include <color_fragment>',
          ['#include <color_fragment>',
           '{',
           uv,
           // 0.5 in the texture is "unchanged"; the amount sets how far the
           // light and dark halves can pull the base colour.
           '  diffuseColor.rgb *= 1.0 + (d - 0.5) * 2.0 * '
             + damount.toFixed(3) + ';',
           '}'].join('\n'));
      }
    };
  }
  if (strength > 0) {
    const withDetail = mat.onBeforeCompile;
    mat.onBeforeCompile = (shader) => {
      withDetail(shader);
      applyWindShader(shader, strength, opts.stiffness ?? 1.0);
    };
  }
  // The cache key has to name every branch of the injection above, or three.js
  // reuses one compiled program for materials whose shaders differ.
  if (strength > 0 || detail) {
    mat.customProgramCacheKey = () =>
      'plant' + strength.toFixed(4) + (opts.vertexColors ? 'c' : '')
      + '|' + detail + dscale.toFixed(2) + damount.toFixed(2)
      + (cylindrical ? 'cyl' : 'tri') + (opts.stiffness ?? 1).toFixed(2);
  }
  return mat;
}

// ── per-class material caches ───────────────────────────────────────────────
// One material per (preset × surface class), built on first use. Plants are
// already bucketed into one InstancedMesh per archetype variant, so this is a
// single lookup per bucket and never a per-plant cost.
const _MAT_CACHE = {};

// `vc` is whether the GEOMETRY this will wear carries a colour attribute. It is
// not cosmetic: a baked GLB part ships COLOR_0 (grayscale AO) while the
// procedural fallback's bark has position and normal only, and a
// vertexColors:true material over geometry with no colour attribute renders
// black. The two paths have always needed two materials for this reason; the
// flag is what keeps that true now that the material is also per-surface-class.
function surfaceMaterial(preset, cls, vc) {
  const key = preset.key + '|' + cls + '|' + (vc ? 'c' : '');
  if (!_MAT_CACHE[key]) {
    _MAT_CACHE[key] = plantMaterial(Object.assign({}, preset, {
      vertexColors: !!vc,
      detail: cls ? preset.detailKind + '.' + cls : preset.detailKind,
    }));
  }
  return _MAT_CACHE[key];
}
