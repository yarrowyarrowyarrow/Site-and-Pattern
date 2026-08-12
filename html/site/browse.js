(function () {
  var data = JSON.parse(document.getElementById('catalogue').textContent);
  var results = document.getElementById('results');
  var count = document.getElementById('count');
  var q = document.getElementById('q');
  var nativeOnly = document.getElementById('nativeonly');
  var MONTHS = ['january','february','march','april','may','june','july',
                'august','september','october','november','december'];
  var cards = {};
  Array.prototype.forEach.call(results.children, function (el) {
    cards[el.getAttribute('href')] = el;
  });
  function chosen(name) {
    var out = [];
    document.querySelectorAll('input[data-f="' + name + '"]:checked')
      .forEach(function (i) { out.push(i.value); });
    return out;
  }
  function apply() {
    var text = (q.value || '').trim().toLowerCase();
    var colours = chosen('colour'), types = chosen('type'), months = chosen('month');
    var monthNums = months.map(function (m) { return MONTHS.indexOf(m) + 1; });
    var shown = 0;
    data.forEach(function (p) {
      var el = cards['../plants/' + p.slug + '/'] || cards['plants/' + p.slug + '/'];
      if (!el) { return; }
      var ok = true;
      if (text) {
        ok = (p.name + ' ' + p.scientific_name).toLowerCase().indexOf(text) >= 0;
      }
      if (ok && colours.length) { ok = colours.indexOf(p.colour) >= 0; }
      if (ok && types.length) { ok = types.indexOf(p.type) >= 0; }
      if (ok && monthNums.length) {
        ok = monthNums.some(function (m) { return p.months.indexOf(m) >= 0; });
      }
      if (ok && nativeOnly.checked) { ok = !!p.native; }
      el.hidden = !ok;
      if (ok) { shown++; }
    });
    count.textContent = shown + (shown === 1 ? ' plant' : ' plants');
  }
  document.getElementById('filters').addEventListener('input', apply);
  document.getElementById('clear').addEventListener('click', function () {
    q.value = '';
    document.querySelectorAll('#filters input[type=checkbox]').forEach(
      function (i) { i.checked = false; });
    apply();
  });
  apply();
})();
