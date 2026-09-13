/* Client-side faceted search over the embedded catalogue index.
 *
 * The index is one row per species: {s: slug, n: searchable name, <facet key>:
 * [values]}. Facet keys and their values come from src/site_facets.py, so this
 * file never enumerates them; it reads whatever data-f attributes the page
 * rendered. Adding a facet in Python therefore needs no change here.
 *
 * Across facets, checked values are AND (yellow AND blooms in June). Within a
 * facet the default is OR (yellow OR blue), but a facet may declare
 * data-combine="all" and then its own values AND too.
 *
 * That second mode is not a nicety. Ticking "no known pet toxicity" gave 388
 * plants and adding "no known human toxicity" gave 404, because the union of
 * two safety claims is bigger than either one. Somebody ticking both wants a
 * plant that is safe around the dog AND the kids, so the count has to fall.
 * Ecological roles work the same way, and match what search_plants has done
 * with use tags on the desktop since V1.85.
 *
 * A plant with no value for a facet matches nothing in it. That is deliberate:
 * "we do not know when this blooms" is not "it blooms in June".
 */
(function () {
  var node = document.getElementById('catalogue');
  if (!node) { return; }
  var data = JSON.parse(node.textContent);

  var form = document.getElementById('filters');
  var results = document.getElementById('results');
  var noresults = document.getElementById('noresults');
  var count = document.getElementById('count');
  var q = document.getElementById('q');
  var clear = document.getElementById('clear');
  var active = document.getElementById('active');

  // Cards are looked up by slug, taken from the last path segment of the href
  // the renderer emitted, so the two cannot drift over a path prefix, and the
  // one script drives both /plants/ and (since V2.71) /wildlife/ without ever
  // being told which page it is on. It used to match `plants/<slug>/`, which
  // silently found nothing anywhere else.
  var cards = {};
  Array.prototype.forEach.call(results.children, function (el) {
    var parts = (el.getAttribute('href') || '').split('/').filter(Boolean);
    if (parts.length) { cards[parts[parts.length - 1]] = el; }
  });

  // What the running count calls the things. Read off the results container so
  // the noun travels with the rows rather than being hardcoded here.
  var noun = results.getAttribute('data-noun') || 'plant';
  var nounPlural = results.getAttribute('data-noun-plural') || (noun + 's');

  function checkedBoxes() {
    return Array.prototype.slice.call(
      form.querySelectorAll('input[type=checkbox]:checked'));
  }

  // data-combine lives on the <details> wrapper, so the mode travels with the
  // facet the renderer drew rather than being restated in a list here.
  function combineMode(key) {
    var el = form.querySelector('[data-facet="' + key + '"]');
    return (el && el.getAttribute('data-combine')) || 'any';
  }

  function selection() {
    var out = {};
    checkedBoxes().forEach(function (box) {
      var key = box.getAttribute('data-f');
      (out[key] = out[key] || []).push(box.value);
    });
    return out;
  }

  function matches(row, text, sel) {
    if (text && row.n.indexOf(text) < 0) { return false; }
    for (var key in sel) {
      if (!Object.prototype.hasOwnProperty.call(sel, key)) { continue; }
      var have = row[key] || [];
      var wanted = sel[key];
      var i;
      if (combineMode(key) === 'all') {
        for (i = 0; i < wanted.length; i++) {
          if (have.indexOf(wanted[i]) < 0) { return false; }
        }
      } else {
        var hit = false;
        for (i = 0; i < wanted.length; i++) {
          if (have.indexOf(wanted[i]) >= 0) { hit = true; break; }
        }
        if (!hit) { return false; }
      }
    }
    return true;
  }

  function labelFor(box) {
    var label = box.closest('label');
    var span = label && label.querySelector('span:not(.dot)');
    return span ? span.textContent : box.value;
  }

  function paintActive(boxes) {
    active.textContent = '';
    boxes.forEach(function (box) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = labelFor(box) + ' ×';
      btn.title = 'Remove this filter';
      btn.addEventListener('click', function () {
        box.checked = false;
        apply();
      });
      active.appendChild(btn);
    });
  }

  function paintCounts() {
    Array.prototype.forEach.call(form.querySelectorAll('.facet'),
      function (facet) {
        var n = facet.querySelectorAll('input:checked').length;
        var pip = facet.querySelector('summary .on');
        if (!pip) { return; }
        pip.textContent = n ? String(n) : '';
        pip.hidden = !n;
      });
  }

  function apply() {
    var text = (q.value || '').trim().toLowerCase();
    var sel = selection();
    var boxes = checkedBoxes();
    var shown = 0;

    for (var i = 0; i < data.length; i++) {
      var row = data[i];
      var el = cards[row.s];
      if (!el) { continue; }
      var ok = matches(row, text, sel);
      el.hidden = !ok;
      if (ok) { shown++; }
    }

    count.textContent = shown + ' ' + (shown === 1 ? noun : nounPlural);
    noresults.hidden = shown !== 0;
    clear.hidden = !boxes.length && !text;
    paintActive(boxes);
    paintCounts();
  }

  form.addEventListener('input', apply);
  clear.addEventListener('click', function () {
    q.value = '';
    checkedBoxes().forEach(function (box) { box.checked = false; });
    apply();
  });

  apply();
})();
