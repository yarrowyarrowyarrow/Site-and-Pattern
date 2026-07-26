// Part of the Site & Pattern 3D viewer, split out of the former
// single html/scene3d.html <script> (V2.24). Loaded as an ordered
// CLASSIC script by the bootstrap in scene3d.html — it shares the
// global scope with its siblings (THREE/OrbitControls/mergeGeometries
// are globals set by the bootstrap), so load ORDER is dependency
// order. Do not add ES `import`/`export` here.

// ── Flowers (V1.90; oriented V2.29) ─────────────────────────────────────────
// One instanced quad per bloom, in the plant's real flower colour, shaped by a
// per-form canvas texture and — since V2.29 — HELD AT THE ATTITUDE ITS FORM
// ACTUALLY HOLDS (_FLOWER_ATTITUDE below) rather than turned to face the
// camera. Shown only when the scene's month falls inside the bloom window.
const FLOWER_FORMS = ['daisy', 'rays', 'spike', 'plume', 'umbel', 'globe',
                      'cluster', 'bell', 'trumpet', 'cattail', 'pea', 'whorl',
                      'star', 'cross', 'lily'];
// ── graminoid seed heads (V2.33, F66) ───────────────────────────────────────
// A grass is identified by its SEED HEAD. Every blade in the catalogue is
// recorded `linear` and all 79 grasses, sedges and rushes carried
// flower_form='plume', so one generic spray stood for the whole group and there
// was nothing on screen separating a big bluestem from a wire rush. These are
// the forms `inflorescence_form` (schema v52) records, drawn in PROFILE like
// the spike and the cattail. `cattail_spike` reuses the cattail texture, which
// already draws exactly that.
const GRAMINOID_FORMS = ['turkey_foot', 'one_sided_raceme', 'open_panicle',
                         'contracted_spike', 'nodding_raceme', 'bristly',
                         'sedge_cluster', 'rush_umbel'];
let FLOWER_TEX = null;

function makeFlowerTexture(form) {
  // Graminoid seed heads live in 12-seedheads.js — eight more drawings in here
  // would have taken this file past its ceiling, and they are a coherent group
  // with their own reason to exist (F66). It loads after this one, which is
  // fine: makeFlowerTexture is only ever called from buildFlowers at
  // scene-build time, never at load time.
  if (window.makeGraminoidTexture) {
    const gt = window.makeGraminoidTexture(form);
    if (gt) return gt;
  }
  const s = 64, cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const g = cv.getContext('2d');
  g.clearRect(0, 0, s, s);
  g.fillStyle = '#ffffff';
  const cx = s / 2, cy = s / 2;
  const dot = (x, y, r) => { g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill(); };
  if (form === 'daisy') {
    const petals = 10, R = s * 0.30;          // aster ray florets
    for (let i = 0; i < petals; i++) {
      const a = i / petals * Math.PI * 2;
      g.save(); g.translate(cx + Math.cos(a) * R * 0.6, cy + Math.sin(a) * R * 0.6);
      g.rotate(a); g.beginPath();
      g.ellipse(0, 0, s * 0.20, s * 0.075, 0, 0, Math.PI * 2); g.fill(); g.restore();
    }
    g.fillStyle = 'rgba(255,255,255,0.7)'; dot(cx, cy, s * 0.12);   // dim eye
  } else if (form === 'umbel') {
    for (let i = 0; i < 16; i++) {
      const a = i * 2.39996, rr = Math.sqrt(i / 16) * s * 0.40;
      dot(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr * 0.55, s * 0.055);
    }
  } else if (form === 'spike') {
    for (let i = 0; i < 7; i++) {
      const yy = s * 0.12 + i * s * 0.115;
      const w = s * (0.16 - 0.012 * i);
      g.beginPath(); g.ellipse(cx, yy, w, s * 0.075, 0, 0, Math.PI * 2); g.fill();
    }
  } else if (form === 'bell') {
    g.beginPath();
    g.moveTo(cx - s * 0.20, cy - s * 0.18);
    g.bezierCurveTo(cx - s * 0.24, cy + s * 0.30, cx + s * 0.24, cy + s * 0.30,
                    cx + s * 0.20, cy - s * 0.18);
    g.closePath(); g.fill();
    for (let i = 0; i < 3; i++) dot(cx - s * 0.12 + i * s * 0.12, cy + s * 0.24, s * 0.05);
  } else if (form === 'rays') {            // big sunflower-style composite
    const petals = 16, R = s * 0.40;
    for (let i = 0; i < petals; i++) {
      const a = i / petals * Math.PI * 2;
      g.save(); g.translate(cx + Math.cos(a) * R * 0.5, cy + Math.sin(a) * R * 0.5);
      g.rotate(a); g.beginPath();
      g.ellipse(0, 0, s * 0.24, s * 0.07, 0, 0, Math.PI * 2); g.fill(); g.restore();
    }
    g.fillStyle = 'rgba(255,255,255,0.6)'; dot(cx, cy, s * 0.19);   // dark disc hint
  } else if (form === 'plume') {           // feathery tapering spray (goldenrod, grass)
    for (let i = 0; i < 26; i++) {
      const t = i / 26, yy = s * 0.08 + t * s * 0.84;
      const spread = s * 0.22 * (1 - t) + s * 0.03;
      dot(cx + Math.sin(i * 1.7) * spread, yy, s * 0.045 * (1 - 0.4 * t));
    }
  } else if (form === 'globe') {           // dense spherical head (allium)
    for (let i = 0; i < 22; i++) {
      const a = i * 2.39996, rr = Math.sqrt(i / 22) * s * 0.36;
      dot(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, s * 0.055);
    }
  } else if (form === 'trumpet') {         // 5-point tubular star (columbine, honeysuckle)
    const pts = 5, Ro = s * 0.40, Ri = s * 0.16;
    g.beginPath();
    for (let i = 0; i < pts * 2; i++) {
      const a = -Math.PI / 2 + i * Math.PI / pts, r = (i % 2 ? Ri : Ro);
      const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
      i ? g.lineTo(x, y) : g.moveTo(x, y);
    }
    g.closePath(); g.fill();
    g.fillStyle = 'rgba(255,255,255,0.7)'; dot(cx, cy, s * 0.10);
  } else if (form === 'cattail') {         // brown emergent spike (Typha)
    // slim upper male spike tapering to a point
    g.beginPath();
    g.moveTo(cx - s * 0.035, s * 0.30);
    g.lineTo(cx + s * 0.035, s * 0.30);
    g.lineTo(cx + s * 0.016, s * 0.07);
    g.lineTo(cx - s * 0.016, s * 0.07);
    g.closePath(); g.fill();
    // fat female sausage with rounded ends
    const x0 = cx - s * 0.085;
    g.fillRect(x0, s * 0.34, s * 0.17, s * 0.50);
    dot(cx, s * 0.34, s * 0.085);
    dot(cx, s * 0.84, s * 0.085);
    // thin supporting stalk below
    g.fillRect(cx - s * 0.012, s * 0.84, s * 0.024, s * 0.15);
  } else if (form === 'pea') {             // legume raceme (lupine, vetch, milkvetch)
    const rows = 6;
    for (let i = 0; i < rows; i++) {
      const t = i / (rows - 1);
      const yy = s * 0.15 + t * s * 0.70;
      const w = s * (0.17 - 0.05 * t);     // wider toward the base
      g.beginPath(); g.ellipse(cx, yy - s * 0.03, w, s * 0.065, 0, 0, Math.PI * 2); g.fill();
      dot(cx - w * 0.5, yy + s * 0.03, s * 0.042);   // wings / keel
      dot(cx + w * 0.5, yy + s * 0.03, s * 0.042);
    }
  } else if (form === 'whorl') {           // tubular whorl (bee balm / Monarda)
    const florets = 14;
    for (let i = 0; i < florets; i++) {
      const a = i / florets * Math.PI * 2 + 0.2;
      const rr = s * 0.30 * (0.72 + 0.28 * (((i * 7) % 5) / 5));
      g.save(); g.translate(cx, cy); g.rotate(a); g.beginPath();
      g.ellipse(rr * 0.5, 0, s * 0.17, s * 0.032, 0, 0, Math.PI * 2); g.fill(); g.restore();
    }
    g.fillStyle = 'rgba(255,255,255,0.85)'; dot(cx, cy, s * 0.09);
  } else if (form === 'star') {            // 5 broad rounded petals (flax, geranium, phlox)
    const petals = 5, R = s * 0.34;
    for (let i = 0; i < petals; i++) {
      const a = -Math.PI / 2 + i / petals * Math.PI * 2;
      g.save(); g.translate(cx + Math.cos(a) * R * 0.52, cy + Math.sin(a) * R * 0.52);
      g.rotate(a + Math.PI / 2); g.beginPath();
      g.ellipse(0, 0, s * 0.135, s * 0.2, 0, 0, Math.PI * 2); g.fill(); g.restore();
    }
    g.fillStyle = 'rgba(255,255,255,0.6)'; dot(cx, cy, s * 0.085);
  } else if (form === 'cross') {           // 4 petals (mustard family — draba)
    const petals = 4, R = s * 0.3;
    for (let i = 0; i < petals; i++) {
      const a = i / petals * Math.PI * 2;
      g.save(); g.translate(cx + Math.cos(a) * R * 0.55, cy + Math.sin(a) * R * 0.55);
      g.rotate(a); g.beginPath();
      g.ellipse(0, 0, s * 0.17, s * 0.115, 0, 0, Math.PI * 2); g.fill(); g.restore();
    }
    dot(cx, cy, s * 0.06);
  } else if (form === 'lily') {            // 6 pointed tepals (lily, blue-eyed grass, camas)
    const tepals = 6, R = s * 0.44;
    for (let i = 0; i < tepals; i++) {
      const a = -Math.PI / 2 + i / tepals * Math.PI * 2;
      g.save(); g.translate(cx, cy); g.rotate(a);
      g.beginPath();
      g.moveTo(0, 0); g.lineTo(s * 0.07, -s * 0.13);
      g.lineTo(0, -R); g.lineTo(-s * 0.07, -s * 0.13);
      g.closePath(); g.fill(); g.restore();
    }
    g.fillStyle = 'rgba(255,255,255,0.55)'; dot(cx, cy, s * 0.08);
  } else { // cluster
    for (let i = 0; i < 11; i++) {
      const a = i * 2.39996, rr = Math.sqrt(i / 11) * s * 0.34;
      dot(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, s * 0.10);
    }
  }
  const t = new THREE.CanvasTexture(cv);
  if (THREE.SRGBColorSpace) t.colorSpace = THREE.SRGBColorSpace;
  t.needsUpdate = true;
  return t;
}

// Clamp a point sprite's on-screen size (V2.12). sizeAttenuation has no cap,
// so a bloom right at the bee camera's nose would otherwise fill the screen as
// a giant washed-out disc. String-replace on the stock points chunk — if the
// chunk ever changes in a three bump, the material just runs unclamped.
function clampPointSize(mat, px) {
  mat.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader.replace(
      'gl_PointSize *= ( scale / - mvPosition.z );',
      'gl_PointSize *= ( scale / - mvPosition.z ); '
      + 'gl_PointSize = min( gl_PointSize, ' + px.toFixed(1) + ' );');
  };
  mat.customProgramCacheKey = () => 'pclamp' + px;
  return mat;
}

// Per-form bloom size — the LARGEST a head of this form is drawn — plus how many
// sprites to scatter per plant (denser = the plant reads as its flower colour
// when in bloom). Deliberately bigger than life: a real 3 cm aster disc would be
// invisible from across a yard, and a bloom you cannot see teaches nothing (P5).
const _FLOWER_SIZE = { rays: 0.42, plume: 0.34, spike: 0.34, umbel: 0.30,
                       globe: 0.32, trumpet: 0.30, bell: 0.24, daisy: 0.24,
                       cluster: 0.26, cattail: 0.7, pea: 0.34, whorl: 0.30,
                       star: 0.28, cross: 0.22, lily: 0.34,
                       // Seed heads are a large fraction of a grass — a big
                       // bluestem's turkey-foot really is a fifth of the plant.
                       turkey_foot: 0.34, one_sided_raceme: 0.26,
                       open_panicle: 0.36, contracted_spike: 0.30,
                       nodding_raceme: 0.32, bristly: 0.34,
                       sedge_cluster: 0.24, rush_umbel: 0.22 };
// …but a head must stay a fraction of its own plant. These were fixed metres per
// FORM, so a 0.6 m blanketflower and a 3 m sunflower both wore a 42 cm head: on
// the small one the bloom was 70% of the plant, a floating orange blob that made
// every small forb look broken in the species gallery. The per-sprite `aSize`
// attribute already exists for bloom-to-bloom variation, so scaling by the
// plant's own canopy costs nothing. The floor keeps a tiny alpine's flower
// visible at scene distance rather than shrinking it back out of existence.
const _FLOWER_REF_CANOPY = 1.1;      // the canopy _FLOWER_SIZE was tuned against
const _FLOWER_MIN_SCALE = 0.28;

// ── how a head is PRESENTED (V2.29) ─────────────────────────────────────────
// Blooms used to be camera-facing point sprites, so every flower in the scene
// always looked straight at you: a bed of asters was a wall of identical discs,
// a nodding onion never nodded, a lupine spike lay flat instead of standing up,
// and orbiting the view slid the whole meadow around like decals. Which way a
// flower faces is not decoration — it is a large part of how a species reads,
// and for a pollinator garden it is the functional bit (P5): a bee approaches an
// upturned daisy differently from a hanging bell.
//
// Heads are now real oriented quads. `tilt` is radians from straight-up, so 0 is
// face-to-the-sky and π is fully nodding; `jitter` is how much that varies bloom
// to bloom; `spin` faces the head outward from the plant's centre rather than
// at the camera.
// The card's attitude is decided by the VIEWPOINT ITS TEXTURE IS DRAWN FROM,
// not by a free reading of the flower. makeFlowerTexture draws some forms
// face-on (petals radiating from a centre — daisy, rays, star) and others in
// PROFILE, as a vertical arrangement seen from the side (spike, plume, pea,
// cattail, and bell, whose hanging shape is already drawn into the image). A
// profile drawing laid face-up is a flower lying on its back; a face-on drawing
// stood vertical is a disc edge-on to the sky. Getting this backwards for the
// bell was the first thing the render showed.
const _FLOWER_ATTITUDE = {
  // ── drawn FACE-ON: the card presents its face ────────────────────────────
  // Flat-topped inflorescences present upward — that is what makes them
  // landing platforms for the flies and short-tongued bees that use them.
  umbel:   { tilt: 0.12, jitter: 0.18 },
  cluster: { tilt: 0.22, jitter: 0.30 },
  globe:   { tilt: 0.10, jitter: 0.35 },
  // Composites track the light: mostly up, tipped outward.
  daisy:   { tilt: 0.42, jitter: 0.28 },
  rays:    { tilt: 0.50, jitter: 0.22 },
  cross:   { tilt: 0.35, jitter: 0.30 },
  star:    { tilt: 0.38, jitter: 0.30 },
  whorl:   { tilt: 0.55, jitter: 0.25 },
  // Tubular faces look outward and slightly down — how a columbine or a
  // honeysuckle actually meets a hovering pollinator.
  trumpet: { tilt: 1.05, jitter: 0.35, spin: true },
  lily:    { tilt: 0.95, jitter: 0.40, spin: true },
  // ── drawn in PROFILE: the card stands vertical, turned outward ───────────
  spike:   { tilt: 1.50, jitter: 0.16, spin: true },
  pea:     { tilt: 1.50, jitter: 0.16, spin: true },
  plume:   { tilt: 1.48, jitter: 0.22, spin: true },
  cattail: { tilt: 1.57, jitter: 0.05, spin: true },
  // The harebell/nodding-onion hang is IN the texture, so the card that shows
  // it is the vertical one; tipping the card down as well hides the shape.
  bell:    { tilt: 1.52, jitter: 0.20, spin: true },
  // Graminoid seed heads are all drawn in profile and stand on a culm, so they
  // take the vertical card. The two that lean are the ones that lean in life:
  // a brome's raceme nods and a blue grama's comb tips over.
  turkey_foot:      { tilt: 1.50, jitter: 0.10, spin: true },
  one_sided_raceme: { tilt: 1.32, jitter: 0.22, spin: true },
  open_panicle:     { tilt: 1.48, jitter: 0.20, spin: true },
  contracted_spike: { tilt: 1.54, jitter: 0.10, spin: true },
  nodding_raceme:   { tilt: 1.30, jitter: 0.26, spin: true },
  bristly:          { tilt: 1.50, jitter: 0.18, spin: true },
  sedge_cluster:    { tilt: 1.50, jitter: 0.14, spin: true },
  rush_umbel:       { tilt: 1.50, jitter: 0.14, spin: true },
};
const _FLOWER_ATTITUDE_DEF = { tilt: 0.5, jitter: 0.3 };
let FLOWER_QUAD = null;              // shared 2-triangle plane, +Z is the face

function buildFlowers(plants, month, terrain) {
  const ALL_FORMS = FLOWER_FORMS.concat(GRAMINOID_FORMS);
  if (!FLOWER_TEX) {
    FLOWER_TEX = {};
    for (const f of ALL_FORMS) FLOWER_TEX[f] = makeFlowerTexture(f);
    // cattail_spike is the cattail drawing under the name the catalogue uses.
    FLOWER_TEX.cattail_spike = FLOWER_TEX.cattail;
  }
  const byForm = {}; ALL_FORMS.forEach(f => byForm[f] = []);
  for (const p of plants || []) {
    // A grass's inflorescence_form (schema v52) supersedes its flower_form,
    // which stays 'plume' for every graminoid because that column feeds the
    // pollinator logic and a wind-pollinated grass offers a bee nothing.
    const form = (p.inflorescence_form && p.inflorescence_form !== 'cattail_spike')
      ? p.inflorescence_form : p.flower_form;
    if (!p.flower_color || !byForm[form]) continue;
    if ((p.opacity ?? 1) < 0.25) continue;            // not-yet-present plants
    const bs = p.bloom_start || 0;
    // A seed head is not a bloom: prairie grasses hold theirs from flowering
    // right through the winter, and that persistence is most of what a grass
    // contributes to a yard from October to April. So a graminoid's head runs
    // to its FRUIT window's end, not its bloom's.
    const be = p.inflorescence_form
      ? Math.max(p.bloom_end || 0, p.fruit_end || 0, 12) : (p.bloom_end || 0);
    if (!bs || month < bs || month > be) continue;     // out of season
    byForm[form].push(p);
  }
  const _fc = new THREE.Color();
  for (const form of ALL_FORMS) {
    const list = byForm[form];
    if (!list.length) continue;
    const isCattail = form === 'cattail';
    const att0 = _FLOWER_ATTITUDE[form] || _FLOWER_ATTITUDE_DEF;
    const pos = [], col = [], siz = [], tilts = [], spins = [];
    // Per-bloom pick data — the flower quads carried none, so a bloom was the
    // one part of a plant that could not be clicked.
    // Measured honestly (inspect_probe.html?sweep=1): on a 588-point grid this
    // changes the hit rate by ZERO, because a bloom sits above a body that is
    // already pickable and resolves to the same plant. What it fixes is the
    // narrower case of a head held clear of its own foliage — a nodding onion
    // or blazingstar scape — where the flower really is the only target. The
    // tolerance spiral in 01-core.js is what fixed the general complaint.
    const names = [], ids = [];
    for (const p of list) {
      const gy = terrainHeightAt(p.x, p.y, terrain);
      const h = Math.max(0.1, p.height_m);
      const top = gy + h * (isCattail ? 0.96 : 0.9);
      const rad = Math.max(0.12, p.canopy_m * 0.5);
      // How big this species' heads are relative to the form's maximum.
      const pscale = Math.max(_FLOWER_MIN_SCALE,
                              Math.min(1, (p.canopy_m || 0.5) / _FLOWER_REF_CANOPY));
      _fc.set(p.flower_color);
      const seed = hashPid(p.plant_id || 1);
      // Fewer, better-spread heads than before: they used to pile into one
      // uniform disc. Now sqrt-spaced across the canopy for even areal density,
      // with real vertical spread + per-bloom size variation so a plant reads as
      // several distinct flowers (V2.13 de-blob).
      const n = isCattail ? 1 + (seed % 3)
              : qn(p.plant_type === 'tree' ? 10
                 : p.plant_type === 'shrub' ? 8
                 : p.plant_type === 'grass' ? 5 : 7);
      for (let k = 0; k < n; k++) {
        const j1 = ((seed + k * 97) % 997) / 997;
        const j2 = ((seed + k * 53) % 991) / 991;
        const j3 = ((seed + k * 29) % 983) / 983;
        const a = j1 * Math.PI * 2;
        const rr = isCattail ? rad * 0.22 * j2
                             : rad * (0.12 + 0.9 * Math.sqrt(j2));  // even areal spread
        const dy = isCattail ? 0 : (j3 - 0.5) * Math.max(0.14, h * 0.3);
        pos.push(p.x + Math.cos(a) * rr, top + dy, -(p.y + Math.sin(a) * rr));
        col.push(_fc.r, _fc.g, _fc.b);
        siz.push(isCattail ? 1
                 : pscale * (0.6 + 0.85 * (((seed + k * 17) % 100) / 100)));
        // Attitude, jittered per bloom so a plant is not a rank of clones.
        const j4 = ((seed + k * 41) % 977) / 977;
        tilts.push(att0.tilt + (j4 - 0.5) * 2 * att0.jitter);
        // `spin: true` forms are read from the side, so face them AWAY from the
        // plant's centre — `a` is the bloom's own bearing from that centre, and
        // +π aligns the card's outward normal with it. The rest get a free spin.
        spins.push(att0.spin ? a + Math.PI : j4 * Math.PI * 2);
        names.push(p.common_name || '');
        ids.push(p.plant_id);
      }
    }
    // Oriented quads, not camera-facing points: each head is placed with the
    // attitude its form actually holds (see _FLOWER_ATTITUDE).
    if (!FLOWER_QUAD) FLOWER_QUAD = new THREE.PlaneGeometry(1, 1);
    const base = (_FLOWER_SIZE[form] || 0.24) * (sceneNight ? 1.25 : 1);
    const mat = new THREE.MeshBasicMaterial({
      map: FLOWER_TEX[form], color: 0xffffff,
      // NOT vertexColors. The per-bloom colour rides on InstancedMesh's
      // instanceColor, which three.js multiplies in on its own. Asking for
      // vertexColors as well makes the shader read a `color` ATTRIBUTE that a
      // plain PlaneGeometry does not have — it comes through as zero and every
      // flower in the scene renders black.
      transparent: true, alphaTest: 0.4, depthWrite: false,
      side: THREE.DoubleSide,
      // At night the blooms softly luminesce (additive) so they read like
      // moonlit / moth-pollinated flowers instead of vanishing into the dark.
      blending: sceneNight ? THREE.AdditiveBlending : THREE.NormalBlending,
    });
    // MeshBasic, deliberately: a flower's colour is its whole point, and
    // shading a two-triangle card by a normal it does not really have made
    // half of every bed read as grey. Points were unlit too, so this keeps
    // the look while gaining the orientation.
    const mesh = instancedMesh(FLOWER_QUAD, pos.length / 3, mat, false);
    const q = new THREE.Quaternion(), e = new THREE.Euler();
    const v = new THREE.Vector3(), s = new THREE.Vector3(), m = new THREE.Matrix4();
    const c = new THREE.Color();
    for (let i = 0; i < siz.length; i++) {
      const size = base * siz[i];
      v.set(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]);
      s.set(size, size, size);
      // The plane's face is +Z, so rotating X by -π/2 puts it face-up; adding
      // the form's tilt from there leans or nods it. Y spins it about the
      // stem — outward from the plant for the forms read from the side, and
      // free for the rest so a bed is not a rank of clones.
      e.set(-Math.PI / 2 + tilts[i], spins[i], 0, 'YXZ');
      q.setFromEuler(e);
      m.compose(v, q, s);
      mesh.setMatrixAt(i, m);
      mesh.setColorAt(i, c.setRGB(col[i * 3], col[i * 3 + 1], col[i * 3 + 2]));
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    // Same contract the plant-body layers use (04-quality.js): `pick` names the
    // instance for the hover tip, `pickId` keys it for the dossier card.
    mesh.userData.pick = names;
    mesh.userData.pickId = ids;
    plantsGroup.add(mesh);
  }
}

function buildScanPoints(group, pts) {
  // The imported yard scan as a height-tinted point layer — ground truth
  // behind the proposed design. Sampled host-side (≤ ~120k points).
  if (!pts || !pts.length) return;
  const pos = new Float32Array(pts.length * 3);
  const col = new Float32Array(pts.length * 3);
  const lo = new THREE.Color(0x4e5d52), hi = new THREE.Color(0xe8f0d8);
  const c = new THREE.Color();
  for (let i = 0; i < pts.length; i++) {
    const [x, y, z] = pts[i];
    pos[i * 3] = x; pos[i * 3 + 1] = z; pos[i * 3 + 2] = -y;
    c.copy(lo).lerp(hi, Math.max(0, Math.min(1, z / 6)));
    col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  group.add(new THREE.Points(geo, new THREE.PointsMaterial({
    size: 0.08, vertexColors: true })));
}

function buildStructures(group, structures) {
  for (const s of structures || []) {
    // Blender GLB structure first (09-models.js), box as the fallback.
    const glb = window.glbStructure && window.glbStructure(s);
    if (glb) {
      glb.position.set(s.x, terrainHeightAt(s.x, s.y, lastTerrain), -s.y);
      group.add(glb);
      continue;
    }
    const size = Math.max(0.3, s.size_m || 1), h = Math.max(0.3, s.height_m || 1);
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(size, h, size),
      new THREE.MeshStandardMaterial({ color: 0x8d6e63, roughness: 0.9 }));
    mesh.position.set(s.x, h / 2, -s.y);
    mesh.castShadow = mesh.receiveShadow = true;
    group.add(mesh);
  }
}

// ── Gaussian-splat backdrop (Spark) ─────────────────────────────────────────
// The splat lives OUTSIDE designGroup so a year-slider scene rebuild never
// reloads it (a yard splat is tens of MB). It is keyed by URL: ensureSplat
// only re-fetches when the file changes, otherwise just refreshes its world
// matrix + opacity from the latest scene push.

let splatMesh = null;
let splatUrl = null;

function applySplatMatrix(mesh, mat16) {
  // mat16 is column-major (three.js order) from src/splat_backdrop.world_matrix.
  mesh.matrixAutoUpdate = false;
  mesh.matrix.fromArray(mat16);
}

function ensureSplat(spec) {
  if (!spec || !spec.url) { removeSplat(); return; }
  if (!SplatMesh) return;          // Spark not loaded (yet) — skip silently
  ensureSparkRenderer();
  if (spec.url !== splatUrl) {
    removeSplat();
    try {
      splatMesh = new SplatMesh({ url: spec.url });
    } catch (e) {
      splatMesh = null; splatUrl = null;
      return;   // bad splat — design still renders
    }
    splatUrl = spec.url;
    scene.add(splatMesh);
  }
  if (splatMesh) {
    applySplatMatrix(splatMesh, spec.matrix);
    if (typeof spec.opacity === 'number' && 'opacity' in splatMesh) {
      splatMesh.opacity = spec.opacity;
    }
  }
}

function removeSplat() {
  if (splatMesh) { scene.remove(splatMesh); }
  splatMesh = null; splatUrl = null;
}

window.permaClearSplat = function () { removeSplat(); };

// Bake a north-up orthographic photo of the splat for the 2D "yard photo"
// map layer. Returns a PNG data URL synchronously (the host calls this once
// the splat has streamed in) — opts frames an exact scene-metre rectangle so
// the image maps 1:1 onto the splat's lat/lng bbox. Returns '' if not ready.
window.permaCaptureOrtho = function (opts) {
  if (!splatMesh || !opts) return '';
  const wx = Math.max(1e-3, opts.max_x - opts.min_x);
  const dz = Math.max(1e-3, opts.max_y - opts.min_y);   // north span
  const cx = (opts.min_x + opts.max_x) / 2;
  const cz = -(opts.min_y + opts.max_y) / 2;            // north → −z centre
  const cam = new THREE.OrthographicCamera(-wx / 2, wx / 2, dz / 2, -dz / 2,
                                           0.1, 2000);
  cam.position.set(cx, 800, cz);
  cam.up.set(0, 0, -1);          // north (−z) points up in the image
  cam.lookAt(cx, 0, cz);

  // Splat-only frame: hide the design + sky so the layer is just the yard.
  const designVis = designGroup ? designGroup.visible : false;
  if (designGroup) designGroup.visible = false;
  const bg = scene.background; scene.background = null;
  const skyVis = skyDome.visible; skyDome.visible = false;

  const longest = Math.round(Math.max(1, Math.min(4096, opts.width || 2048)));
  const px = wx >= dz ? longest : Math.round(longest * (wx / dz));
  const py = wx >= dz ? Math.round(longest * (dz / wx)) : longest;
  const prev = new THREE.Vector2(); renderer.getSize(prev);
  renderer.setSize(px, py, false);
  renderer.render(scene, cam);
  let url = '';
  try { url = renderer.domElement.toDataURL('image/png'); } catch (e) { url = ''; }

  // Restore the live view.
  renderer.setSize(prev.x, prev.y, false);
  scene.background = bg;
  skyDome.visible = skyVis;
  if (designGroup) designGroup.visible = designVis;
  renderer.render(scene, camera);
  return url;
};

// Render the CURRENT scene from the CURRENT camera into an off-size frame and
// hand back a data URL. This is what lets the sprite gallery build a contact
// sheet: push a specimen, snapshot it, repeat — every tile drawn by the real
// viewer with the real geometry, materials, lighting and season, each framed to
// its own plant. Comparing sprites side by side is the only way to notice that
// two of them are the same sprite, which is a thing a one-at-a-time menu hides
// completely.
//
// JPEG by default: a 480-tile sheet of PNGs is tens of megabytes of data URL and
// the sky means there is no transparency to preserve.
window.permaSnapshot = function (opts) {
  opts = opts || {};
  const w = Math.max(16, Math.min(2048, Math.round(opts.width || 320)));
  const h = Math.max(16, Math.min(2048, Math.round(opts.height || w)));
  const prev = new THREE.Vector2();
  renderer.getSize(prev);
  const prevAspect = camera.aspect;
  // The DRAWING BUFFER is w x pixelRatio, and the ratio is pinned once at boot
  // to min(devicePixelRatio, 1.5) — so a snapshot's real resolution has always
  // depended on the machine it ran on, which is fine for a 320px gallery tile
  // and useless for print. F69 sets it explicitly and restores it, which is
  // what gets a ~300 dpi page image out of a viewport-sized capture.
  const prevRatio = renderer.getPixelRatio();
  const ratio = Math.max(1, Math.min(4, opts.pixelRatio || 0));
  let url = '';
  try {
    if (ratio) renderer.setPixelRatio(ratio);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.render(scene, camera);
    url = renderer.domElement.toDataURL(opts.mime || 'image/jpeg',
                                        opts.quality || 0.82);
  } catch (e) {
    url = '';
  }
  // Always restore, even if toDataURL threw — a half-resized renderer would
  // leave the live view stretched for the rest of the session.
  if (ratio) renderer.setPixelRatio(prevRatio);
  renderer.setSize(prev.x, prev.y, false);
  camera.aspect = prevAspect;
  camera.updateProjectionMatrix();
  renderer.render(scene, camera);
  return url;
};

// Whether the baked GLB archetypes have finished loading. The gallery waits on
// this before snapshotting: models arrive asynchronously and trigger their own
// scene rebuild, so a contact sheet built too early would be a sheet of the
// procedural FALLBACK geometry, silently mislabelled as what the app renders.
// MODEL_STATE is a `let` in 09-models.js, which loads AFTER this chunk. Classic
// scripts share one global lexical scope, so it is readable here at call time —
// but a top-level `let` is in its temporal dead zone until its own script
// evaluates, and `typeof` on a TDZ binding throws rather than saying
// 'undefined'. try/catch is the honest guard.
window.permaModelsReady = function () {
  try {
    return MODEL_STATE !== 'loading';
  } catch (e) {
    return false;                 // 09-models.js has not evaluated yet
  }
};

// ── hooks ───────────────────────────────────────────────────────────────────

// Free the GPU resources a scene rebuild leaves behind. Without this the
// per-rebuild instance buffers and fresh ground/boundary/building geometries
// pile up in VRAM on every slider move until a weak GPU runs out and crashes.
// Shared archetype geometry (TREE_CACHE/ARCH/GEO) and materials (MATS) are
// reused across rebuilds, so they are skipped.
function disposeDesignGroup(group) {
  if (!group) return;
  const sharedGeo = new Set();
  for (const a of TREE_CACHE.values()) {
    if (a.branchGeo) sharedGeo.add(a.branchGeo);
    if (a.foliageGeo) sharedGeo.add(a.foliageGeo);
  }
  // Every shared archetype is reused across rebuilds and must NOT be disposed:
  // all ARCH variant arrays (peren/ground/grass/aquatic — iterate so adding or
  // removing a category never breaks this), and the per-genus shrub cache
  // (V1.94: shrubs moved out of ARCH into SHRUB_CACHE).
  if (ARCH) for (const arr of Object.values(ARCH))
    for (const g of arr) sharedGeo.add(g);
  for (const a of SHRUB_CACHE.values()) {
    if (a.foliageGeo) sharedGeo.add(a.foliageGeo);
    if (a.stemGeo) sharedGeo.add(a.stemGeo);
  }
  for (const g of HERB_CACHE.values()) sharedGeo.add(g);
  for (const k in GEO) sharedGeo.add(GEO[k]);
  // GLB master geometries (09-models.js) survive cache clears — a quality (or
  // models-ready) rebuild clears the caches above, but the masters are re-served.
  if (window.glbSharedGeos) for (const g of window.glbSharedGeos()) sharedGeo.add(g);
  const sharedMat = new Set(MATS ? Object.values(MATS) : []);
  if (GROUND_MAT) sharedMat.add(GROUND_MAT);   // shared meadow texture lives on
  if (GROUND_SNOW_MAT) sharedMat.add(GROUND_SNOW_MAT);   // and its winter twin
  group.traverse(obj => {
    if (obj.isInstancedMesh) obj.dispose();             // frees instance buffers only
    if (obj.geometry && !sharedGeo.has(obj.geometry)) obj.geometry.dispose();
    const m = obj.material;
    if (m) for (const mm of (Array.isArray(m) ? m : [m]))
      if (mm && !sharedMat.has(mm)) mm.dispose();
  });
}

// Reaching here means the whole module body executed without throwing — the
// hooks are about to register and the 8s "couldn't start" timeout will be
// cancelled. If the log shows 'module-eval-start' but not this line, something
// between the two threw (and should have surfaced via the error handler).
window._pinglog && window._pinglog('registering hooks (boot OK)');

let lastSceneObj = null;     // last full scene, so a quality change can re-render
window.permaSetScene = function (sc) {
  if (!sc || !sc.bounds) return;
  lastSceneObj = sc;
  if (designGroup) { disposeDesignGroup(designGroup); scene.remove(designGroup); }
  designGroup = new THREE.Group();
  scene.add(designGroup);
  lastOrigin = sc.origin || null;
  lastMonth = sc.month || 6;
  sceneMonth = sc.month || 6;         // bloom-gating + the seasonal-tour HUD
  sceneNight = !!sc.is_night;         // set before buildPlants so flowers night-glow
  // The site's real wind for this month, and the lee of its own windbreaks
  // (F68). Uniforms only, so this re-aims every plant in the yard without
  // rebuilding or recompiling anything.
  if (window.applySceneWind) applySceneWind(sc.wind);
  lastYear = sc.year || 0;
  lastBounds = sc.bounds;
  lastTerrain = sc.terrain || null;

  buildGround(designGroup, sc);
  buildBoundary(designGroup, sc.boundary);
  buildBuildings(designGroup, sc.buildings);
  buildPlants(designGroup, sc.plants, sc.month, sc.year, sc.terrain);
  buildStructures(designGroup, sc.structures);
  buildScanPoints(designGroup, sc.scan_points);
  ensureSplat(sc.splat);
  if (sc.is_night) setNight();
  else { setDay(); if (sc.sun) setSun(sc.sun.azimuth_deg, sc.sun.altitude_deg); }
  fitShadow(sc.bounds);

  // Frame the camera only on first load or when a genuinely different design is
  // opened (origin moved) — a slider re-push of the same design keeps the
  // user's current orbit/zoom.
  const o = sc.origin;
  const moved = !framedOrigin ||
    (o && (Math.abs(o.lat - framedOrigin.lat) > 1e-6 ||
           Math.abs(o.lng - framedOrigin.lng) > 1e-6));
  if (moved) {
    // Don't yank the camera while the user is flying, walking, or in the
    // cinematic flyover — those modes own the camera.
    if (!beeMode && !walkMode && !cinematic) frameCamera(sc.bounds);
    framedOrigin = o ? { lat: o.lat, lng: o.lng } : { lat: 0, lng: 0 };
  }
  // Re-place the bee's flower beacons against the freshly-built scene.
  if (beeMode) rebuildBeacons();
  // Refresh walk obstacles (plants grow/shift with year & season).
  if (walkMode) buildWalkObstacles();

  const n = (sc.plants || []).length;
  document.getElementById('hud').innerHTML =
    `<b>Year ${sc.year}</b> &nbsp;·&nbsp; ${n} plant${n === 1 ? '' : 's'}`
    + ((sc.buildings || []).length ? ` &nbsp;·&nbsp; ${sc.buildings.length} structure footprint(s)` : '')
    + (sc.terrain ? ' &nbsp;·&nbsp; terrain' : '');
};

window.permaSetSun = function (azDeg, altDeg) { setSun(azDeg, altDeg); };

// Detail / quality knob (V1.94): 0 Stylised · 1 Balanced · 2 Lifelike. Drops the
// cached archetypes (their density AND, at level 0, their whole construction
// depend on QUALITY) and re-renders the current scene. Build-time only —
// per-frame cost is unchanged.
window.permaSetQuality = function (level) {
  const q = Math.max(0, Math.min(2, level | 0));
  if (q === QUALITY) return;
  QUALITY = q;
  // Level 0 is a STYLE, not a thinning (V2.34) — it skips the baked GLB library
  // and the surface textures, so the shared materials have to go with the
  // archetypes. Leaving MATS standing was the bug this line exists to prevent:
  // the scene would rebuild as faceted masses still wearing veined leaf shaders.
  setStylised(q === 0);
  MATS = null;
  TREE_CACHE.clear();
  SHRUB_CACHE.clear();
  HERB_CACHE.clear();
  ARCH = null;
  if (lastSceneObj) permaSetScene(lastSceneObj);   // same origin → camera stays put
};

// Legacy hook: scene3d.placed_plants_3d_state records carry lat/lng — project
// them with the cosLat metric about the last scene origin.
window.permaSetPlants = function (records) {
  if (!designGroup || !lastOrigin) return;
  const mPerDegLat = 111320.0;
  const cosLat = Math.max(1e-9, Math.cos(lastOrigin.lat * Math.PI / 180));
  const plants = (records || []).map(r => ({
    x: (r.lng - lastOrigin.lng) * mPerDegLat * cosLat,
    y: (r.lat - lastOrigin.lat) * mPerDegLat,
    plant_id: r.plant_id,
    height_m: r.height_m, canopy_m: r.canopy_m,
    plant_type: r.plant_type, foliage_type: r.foliage_type,
    scale_factor: r.scale_factor, spread_factor: r.spread_factor,
    spread_rate: r.spread_rate,
    color: r.color, opacity: r.presence_opacity,
    flower_color: r.flower_color, flower_form: r.flower_form,
    bloom_start: r.bloom_start, bloom_end: r.bloom_end,
  }));
  buildPlants(designGroup, plants, lastMonth, lastYear, lastTerrain);
};

