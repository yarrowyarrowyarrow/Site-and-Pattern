/* Site & Pattern — 3D viewer: graminoid seed heads (V2.33, F66).
 *
 * Design principle P5 — see docs/DESIGN_PHILOSOPHY.md
 *
 * A grass is identified by its SEED HEAD. Every blade in the catalogue is
 * recorded `linear` and all 79 grasses, sedges and rushes carried
 * flower_form='plume', so one generic feathery spray stood for the whole group
 * and nothing on screen separated a big bluestem from a wire rush. The sprite
 * audit named it: "a big bluestem's turkey-foot inflorescence is most of how it
 * is identified in the field, and there is no geometry for it at all."
 *
 * These are drawn, not baked: a seed head is SEASONAL, and 05-flowers.js
 * already owns instanced oriented quads with a season window and a per-form
 * attitude — so a nodding brome nods. The forms are the vocabulary
 * `inflorescence_form` (schema v52) records; 05-flowers.js delegates here from
 * makeFlowerTexture and holds the size and attitude tables.
 *
 * Split out of 05-flowers.js because eight more drawings took it to 799 lines
 * against a 700-line-era ceiling of 800 — the guard's stated remedy is a
 * further split, not a bigger number.
 */

// Returns a THREE.CanvasTexture for a graminoid form, or null if `form` is not
// one — which is how 05-flowers.js can call this for every form it has.
function makeGraminoidTexture(form) {
  if (['turkey_foot', 'one_sided_raceme', 'open_panicle', 'contracted_spike',
       'nodding_raceme', 'bristly', 'sedge_cluster',
       'rush_umbel'].indexOf(form) < 0) return null;
  const s = 64, cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const g = cv.getContext('2d');
  g.clearRect(0, 0, s, s);
  g.fillStyle = '#ffffff';
  const cx = s / 2;
  const dot = (x, y, r) => { g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill(); };
  if (form === 'turkey_foot') {     // Andropogon — the field mark it is named for
    for (let k = -1; k <= 1; k++) {        // three stiff splayed fingers
      const a = k * 0.42;
      g.save(); g.translate(cx, s * 0.86); g.rotate(a);
      g.fillRect(-1, -s * 0.62, 2, s * 0.62);
      for (let i = 0; i < 7; i++) {        // paired spikelets up each finger
        const y = -s * (0.16 + i * 0.068);
        dot(-2.6, y, 1.7); dot(2.6, y, 1.7);
      }
      g.restore();
    }
  } else if (form === 'one_sided_raceme') { // Bouteloua — the comb / eyebrow
    g.save(); g.translate(s * 0.16, s * 0.30);
    g.beginPath(); g.moveTo(0, 0);
    g.quadraticCurveTo(s * 0.34, s * 0.10, s * 0.66, s * 0.34);
    g.lineWidth = 2; g.strokeStyle = '#ffffff'; g.stroke();
    for (let i = 0; i < 13; i++) {         // teeth all on the lower side
      const t = i / 12, x = s * 0.66 * t;
      const y = (1 - t) * (1 - t) * 0 + 2 * (1 - t) * t * s * 0.10 + t * t * s * 0.34;
      g.save(); g.translate(x, y); g.rotate(1.1);
      g.fillRect(0, -1.2, s * 0.13, 2.4); g.restore();
    }
    g.restore();
  } else if (form === 'open_panicle') {    // switchgrass, dropseed, hairgrass
    g.fillRect(cx - 1, s * 0.42, 2, s * 0.58);
    for (let i = 0; i < 16; i++) {
      const t = i / 15, y = s * (0.86 - t * 0.72);
      const side = i % 2 ? 1 : -1, len = s * (0.10 + t * 0.30);
      g.save(); g.translate(cx, y); g.rotate(side * (0.7 + t * 0.5));
      g.lineWidth = 1; g.strokeStyle = '#ffffff';
      g.beginPath(); g.moveTo(0, 0); g.lineTo(0, -len); g.stroke();
      g.restore();
      dot(cx + side * Math.sin(0.7 + t * 0.5) * len,
          y - Math.cos(0.7 + t * 0.5) * len, 1.8);
    }
  } else if (form === 'contracted_spike') { // wheatgrass, fescue, June grass
    g.fillRect(cx - 1, s * 0.60, 2, s * 0.40);
    for (let i = 0; i < 14; i++) {
      const y = s * (0.68 - i * 0.045), w = s * 0.085;
      g.save(); g.translate(cx, y);
      g.beginPath(); g.ellipse(-w * 0.7, 0, w, 2.4, -0.28, 0, Math.PI * 2); g.fill();
      g.beginPath(); g.ellipse(w * 0.7, 0, w, 2.4, 0.28, 0, Math.PI * 2); g.fill();
      g.restore();
    }
  } else if (form === 'nodding_raceme') {  // the bromes, drooping wood-reed
    // Attached high on the culm: the branches hang BELOW where they join, so
    // hanging them from mid-canvas runs them off the bottom of the card.
    g.fillRect(cx - 1, s * 0.30, 2, s * 0.70);
    for (let i = 0; i < 9; i++) {
      const t = i / 8, y = s * (0.44 - t * 0.30);
      const side = i % 2 ? 1 : -1, len = s * (0.16 + t * 0.20);
      g.save(); g.translate(cx, y); g.rotate(side * 1.9);   // past horizontal: it droops
      g.lineWidth = 1.2; g.strokeStyle = '#ffffff';
      g.beginPath(); g.moveTo(0, 0); g.lineTo(0, -len); g.stroke();
      g.beginPath(); g.ellipse(0, -len, 2.2, s * 0.055, 0, 0, Math.PI * 2); g.fill();
      g.restore();
    }
  } else if (form === 'bristly') {         // needle-and-thread, cotton-grass
    g.fillRect(cx - 1, s * 0.62, 2, s * 0.38);
    for (let i = 0; i < 11; i++) {
      const a = -1.25 + i * 0.25;
      g.save(); g.translate(cx, s * 0.62); g.rotate(a);
      g.lineWidth = 1; g.strokeStyle = '#ffffff';
      g.beginPath(); g.moveTo(0, 0); g.lineTo(0, -s * 0.56); g.stroke();
      g.restore();
      dot(cx + Math.sin(a) * s * 0.12, s * 0.62 - Math.cos(a) * s * 0.12, 2.1);
    }
  } else if (form === 'sedge_cluster') {   // Carex, the bulrushes
    g.fillRect(cx - 1.2, s * 0.52, 2.4, s * 0.48);
    const spikes = [[-0.17, 0.30, 0.20], [0.0, 0.16, 0.26], [0.17, 0.32, 0.18]];
    for (const [dx, top, len] of spikes) {
      g.save(); g.translate(cx + dx * s, s * top);
      g.beginPath();
      g.ellipse(0, len * s * 0.5, s * 0.055, len * s * 0.5, 0, 0, Math.PI * 2);
      g.fill(); g.restore();
    }
  } else if (form === 'rush_umbel') {      // Juncus — the lateral burst
    g.fillRect(cx - 1.2, 0, 2.4, s);       // the culm runs past the head
    for (let i = 0; i < 12; i++) {
      const a = 0.5 + (i / 11) * 1.6, len = s * (0.16 + (i % 3) * 0.06);
      g.save(); g.translate(cx, s * 0.44); g.rotate(a);
      g.lineWidth = 1; g.strokeStyle = '#ffffff';
      g.beginPath(); g.moveTo(0, 0); g.lineTo(0, -len); g.stroke();
      g.restore();
      dot(cx + Math.sin(a) * len, s * 0.44 - Math.cos(a) * len, 2.0);
    }
  }
  const t = new THREE.CanvasTexture(cv);
  t.needsUpdate = true;
  return t;
}
window.makeGraminoidTexture = makeGraminoidTexture;
