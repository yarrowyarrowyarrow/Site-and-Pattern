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
// The module is a classic script assigning onto a global object, not a CommonJS
// module — the repo's convention for browser JS. Run it with `sandbox` standing
// in for `window`.
new Function('window', fs.readFileSync(
  path.join(ROOT, 'html', 'botany', 'diagrams.js'), 'utf8')
  .replace(/\}\)\(typeof window[^;]*;\s*$/, '})(window);'))(sandbox);

const outDir = path.join(ROOT, 'docs', 'img', 'botany');
fs.mkdirSync(outDir, { recursive: true });

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
