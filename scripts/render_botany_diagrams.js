/* scripts/render_botany_diagrams.js — the vocabulary charts, as files.
 *
 *   node scripts/render_botany_diagrams.js
 *
 * Writes one self-contained SVG per vocabulary into docs/img/, which
 * docs/BOTANY_FIELD_GUIDE.md references as images. Re-run it after changing a
 * drawing in html/botany/diagrams.js — the plates are generated, not authored,
 * and the whole reason they are SVG rather than screenshots is that a chart
 * which teaches a vocabulary must not be allowed to drift from the vocabulary.
 *
 * Node only for the file writing; the drawings themselves are the same code the
 * browser runs. tests/test_botany_diagrams.py checks the committed plates are
 * in step with the source, so a forgotten re-run fails the build rather than
 * shipping a chart that disagrees with the bench.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(__dirname);
const sandbox = {};
// The modules are classic scripts assigning onto a global object, not CommonJS
// — the repo's convention for browser JS. Run each with `sandbox` standing in
// for `window`, so both share one global exactly as they do in the browser.
function load(file) {
  new Function('window', fs.readFileSync(file, 'utf8')
    .replace(/\}\)\(typeof window[^;]*;\s*$/, '})(window);'))(sandbox);
}
load(path.join(ROOT, 'html', 'botany', 'diagrams.js'));
load(path.join(ROOT, 'html', 'botany', 'fauna.js'));

const outDir = path.join(ROOT, 'docs', 'img', 'botany');
const faunaDir = path.join(ROOT, 'docs', 'img', 'fauna');
fs.mkdirSync(outDir, { recursive: true });
fs.mkdirSync(faunaDir, { recursive: true });

// ONE FILE PER TERM, and the labels live in the Markdown table beside them
// rather than inside the picture. A combined plate with <text> labels was the
// obvious thing and is the wrong thing: it makes the term names part of an
// image — unsearchable, uncopyable, not selectable, invisible to a screen
// reader, and dependent on the viewer's font stack. Text belongs in the
// document; the drawing is only the drawing.
let n = 0;
for (const vocab of ['leaf_shape', 'flower_arch', 'leaf_arrangement']) {
  for (const term of sandbox.botanyTerms(vocab)) {
    const svg = sandbox.botanyDiagram(vocab, term, { size: 92 });
    if (!svg) throw new Error('no diagram for ' + vocab + '/' + term);
    fs.writeFileSync(path.join(outDir, vocab + '-' + term + '.svg'), svg + '\n');
    n++;
  }
  console.log(vocab, '·', sandbox.botanyTerms(vocab).length, 'terms');
}
console.log(n + ' diagrams written to ' + path.relative(ROOT, outDir));

// ── fauna (V2.36) ──────────────────────────────────────────────────────────
let m = 0;
for (const vocab of ['wing_shape', 'wing_pattern', 'resting_posture',
                     'flight_style', 'bee_build', 'scopa_position']) {
  for (const term of sandbox.faunaTerms(vocab)) {
    const svg = sandbox.faunaDiagram(vocab, term, { size: 92 });
    if (!svg) throw new Error('no diagram for ' + vocab + '/' + term);
    fs.writeFileSync(path.join(faunaDir, vocab + '-' + term + '.svg'), svg + '\n');
    m++;
  }
  console.log(vocab, '·', sandbox.faunaTerms(vocab).length, 'terms');
}
// Six worked bumblebee band patterns for the field guide — the point being
// that six species a key describes differently now LOOK different.
const BANDS = {
  'huntii':        'yellow,yellow,orange,orange,yellow,black,black',
  'terricola':     'yellow,black,yellow,yellow,black,black,black',
  'occidentalis':  'yellow,black,black,yellow,white,white,white',
  'vagans':        'yellow,yellow,yellow,black,black,black,black',
  'mixtus':        'yellow,yellow,yellow,black,orange,orange,orange',
  'griseocollis':  'yellow,yellow,brown,black,black,black,black',
};
for (const [name, pattern] of Object.entries(BANDS)) {
  fs.writeFileSync(path.join(faunaDir, 'band-' + name + '.svg'),
                   sandbox.beeBandDiagram(pattern, { size: 92 }) + '\n');
  m++;
}
console.log(m + ' diagrams written to ' + path.relative(ROOT, faunaDir));
