// html/map/13-species-numbers.js — the species numbers on the map, readable
// at every zoom, and a species found from the legend (F218, V3.11).
//
// Classic script, loaded last by map.html, after 12-legend.js: the
// shared-global model of html/map/*.js (see the header of 01-core.js). Nothing
// here runs at load but declarations, so node can load it (tests/test_legend.py).
//
// The owner, after the first Species legend: "I didn't realize there were
// numbers as I did not zoom in enough." A number was drawn only on a plant at
// least 7 px across on screen, so at the zoom a whole yard is read at there
// were none, and nothing said so. Now:
//   - a plant big enough to hold its number carries it, as before;
//   - smaller plants of one species close together share one number, on the
//     plant nearest their middle: a printed planting plan's tag for a drift;
//   - no number covers another: one that would moves beside its plant or
//     waits for a closer zoom, and the legend says how many are waiting; it
//     keeps clear of the map's own labels when it can;
//   - pointing at a species in the legend rings its plants, at any zoom, and a
//     click keeps them ringed.
// A colour per species was tried first and set aside: at the zoom the numbers
// went missing a plant is about 3 px across and mostly outline, and the best
// palette measured left neighbouring species close to one colour there.

    var NUMBER_OWN_PX = 9;      // a plant this big (radius on screen) holds its own
    var NUMBER_REACH_PX = 40;   // smaller ones within this share a number
    var NUMBER_H = 16;          // a number's tag (map.html .sp-species-num)
    var _speciesNumberLayer = null;
    var _numberMoves = [];      // [circle, handler]: a moved plant takes its number
    var _numberTimer = null;
    var _findLayer = null;      // the rings round one species' plants
    var _findShown = null;      // the species ringed now (its plant id, a string)
    var _findPinned = null;     // the one a click in the legend keeps ringed

    // A tag's width for a number: room for its digits in the page's font, and
    // round for one digit.
    function numberTagWidth(num) {
      return Math.max(NUMBER_H, 9 + 8 * String(num).length);
    }

    function _overlaps(a, b) {
      return a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
    }

    // Where the numbers go, in screen pixels. `points`: one per plant,
    // {key, id, num, x, y, r} with r its radius on screen; opts.labels: boxes
    // [left, top, right, bottom] of the labels already on the map, which a
    // number keeps clear of when it can and covers only when it cannot (a
    // small yard's own labels are bigger than it, and hiding every number
    // behind them is the fault this replaces). Returns {tags, hidden}: each
    // tag {id, num, key, x, y, w, dx, dy, members}, where key is the plant it
    // sits on, x/y its centre (dx/dy from that plant), members the keys of the
    // plants it names; hidden counts the tags with no room clear of another.
    function numberGroups(points, opts) {
      opts = opts || {};
      var own = opts.ownPx || NUMBER_OWN_PX, reach = opts.reachPx || NUMBER_REACH_PX;
      var owned = [], grouped = [], small = {};
      points.forEach(function (p) {
        if (p.r >= own) owned.push({ id: p.id, num: p.num, members: [p] });
        else (small[p.id] = small[p.id] || []).push(p);
      });
      // A small plant joins the nearest group of its species within reach,
      // measured to the plant that began the group; otherwise it begins one.
      Object.keys(small).forEach(function (id) {
        var mine = [];
        small[id].slice().sort(function (a, b) { return a.y - b.y || a.x - b.x; })
          .forEach(function (p) {
            var near = null, best = reach;
            mine.forEach(function (g) {
              var d = Math.hypot(p.x - g.members[0].x, p.y - g.members[0].y);
              if (d <= best) { best = d; near = g; }
            });
            if (near) near.members.push(p);
            else mine.push({ id: p.id, num: p.num, members: [p] });
          });
        grouped = grouped.concat(mine);
      });
      grouped.forEach(function (g) {        // its number sits on the plant nearest the middle
        var n = g.members.length, mx = 0, my = 0;
        g.members.forEach(function (p) { mx += p.x / n; my += p.y / n; });
        g.at = g.members.reduce(function (a, p) {
          return Math.hypot(p.x - mx, p.y - my) < Math.hypot(a.x - mx, a.y - my) ? p : a;
        });
      });
      owned.forEach(function (g) { g.at = g.members[0]; });
      // A plant's own number first, inside it, so a group's cannot take its
      // middle and read as its; then the biggest groups.
      grouped.sort(function (a, b) {
        return b.members.length - a.members.length || a.num - b.num ||
               a.at.y - b.at.y || a.at.x - b.at.x;
      });
      owned.sort(function (a, b) { return a.num - b.num || a.at.y - b.at.y || a.at.x - b.at.x; });
      var labels = opts.labels || [], boxes = [], tags = [], hidden = 0;
      owned.concat(grouped).forEach(function (g) {
        var w = numberTagWidth(g.num), h = NUMBER_H, sx = w + 2, sy = h + 2;
        var tries = [[0, 0], [0, -sy], [0, sy], [sx, 0], [-sx, 0],
                     [sx, -sy], [-sx, -sy], [sx, sy], [-sx, sy]];
        var pick = null;
        for (var i = 0; i < tries.length; i++) {
          var x = g.at.x + tries[i][0], y = g.at.y + tries[i][1];
          var box = [x - w / 2 - 1, y - h / 2 - 1, x + w / 2 + 1, y + h / 2 + 1];
          var hit = function (b) { return _overlaps(box, b); };
          if (boxes.some(hit)) continue;                     // never over a number
          var clear = !labels.some(hit);
          if (clear || !pick) pick = { box: box, x: x, y: y, d: tries[i] };
          if (clear) break;
        }
        if (!pick) { hidden++; return; }
        boxes.push(pick.box);
        tags.push({ id: g.id, num: g.num, key: g.at.key, x: pick.x, y: pick.y, w: w,
                    dx: pick.d[0], dy: pick.d[1],
                    members: g.members.map(function (p) { return p.key; }) });
      });
      return { tags: tags, hidden: hidden };
    }

    // ── The page's side ─────────────────────────────────────────────────────

    // A plant's radius on screen now, from its radius in metres. Not the
    // circle's own pixel radius: on zoomend this runs before the plants
    // re-project (it was hooked first), and read that it showed every number.
    function _pixelRadius(c) {
      var ll = c.getLatLng();
      var a = map.latLngToContainerPoint(ll);
      var b = map.latLngToContainerPoint([ll.lat + c.getRadius() / 111320, ll.lng]);
      return Math.abs(a.y - b.y);
    }

    // What the numbers keep clear of: the labels and icons already drawn on
    // the map (a boundary's lengths and area, a plant's name, a structure's
    // icon), as boxes in the map's pixels. The boundary's labels sit over the
    // middle of the planting, where the numbers are. Less their padding: a
    // number on a label's edge hides none of its words, and pushing a plant's
    // own number out of the plant for that reads worse.
    function _labelBoxes() {
      var root = map.getContainer(), at = root.getBoundingClientRect(), out = [];
      var els = root.querySelectorAll('.leaflet-marker-pane > *, .leaflet-tooltip-pane > *');
      for (var i = 0; i < els.length; i++) {
        if (els[i].classList.contains('sp-species-num')) continue;
        var r = els[i].getBoundingClientRect();
        if (r.width > 8 && r.height > 6) {
          out.push([r.left - at.left + 4, r.top - at.top + 3,
                    r.right - at.left - 4, r.bottom - at.top - 3]);
        }
      }
      return out;
    }

    function _plantCircles() {
      return Object.keys(plantMarkers).map(function (k) { return plantMarkers[k]; })
        .filter(function (c) { return c && c._pd; });
    }

    function _clearSpeciesNumbers() {
      if (_numberTimer) { clearTimeout(_numberTimer); _numberTimer = null; }
      _numberMoves.forEach(function (f) { f[0].off('move', f[1]); });
      _numberMoves = [];
      if (_speciesNumberLayer) map.removeLayer(_speciesNumberLayer);
      _speciesNumberLayer = null;
    }

    // Species left: no numbers, no rings, and no click kept.
    function _endSpeciesView() {
      _clearSpeciesNumbers();
      _findPinned = null;
      _ringSpecies(null);
    }

    // In Species, the legend's numbers on the plants, as on the printed
    // planting plan: from refreshLegend (12-legend.js), a zoom, or a move.
    function _drawSpeciesNumbers() {
      _clearSpeciesNumbers();
      if (legendDetail.plants !== 'species' || !_legendOpen() || !_shown(plantLayerGroup)) {
        _endSpeciesView();
        return;
      }
      var circles = _plantCircles();
      var nums = speciesNumbers(circles.map(function (c) {
        return { id: c._pd.plantId, name: c._pd.commonName };
      }));
      var laid = numberGroups(circles.map(function (c) {
        var pt = map.latLngToContainerPoint(c.getLatLng());
        return { key: c._pd.markerId, id: String(c._pd.plantId), num: nums[c._pd.plantId],
                 x: pt.x, y: pt.y, r: _pixelRadius(c) };
      }), { labels: _labelBoxes() });
      _speciesNumberLayer = L.layerGroup();
      _speciesNumberLayer._spLegendOwn = true;
      var tagOn = {};
      laid.tags.forEach(function (t) {
        var c = plantMarkers[t.key];
        var mk = L.marker(c.getLatLng(), { interactive: false, keyboard: false,
          zIndexOffset: 1000,                // over a label it had to cover
          icon: L.divIcon({ className: 'sp-species-num', html: String(t.num),
                            iconSize: [t.w, NUMBER_H],
                            iconAnchor: [t.w / 2 - t.dx, NUMBER_H / 2 - t.dy] }) });
        mk._spLegendOwn = true;
        mk._spCircle = c;
        mk._spMembers = t.members;
        tagOn[t.key] = mk;
        _speciesNumberLayer.addLayer(mk);
      });
      _speciesNumberLayer.addTo(map);
      // A dragged plant takes its number along, and the groups are worked out
      // again once it stops.
      circles.forEach(function (c) {
        var move = function (ev) {
          var mk = tagOn[c._pd.markerId];
          if (mk) mk.setLatLng(ev.latlng);
          if (_numberTimer) clearTimeout(_numberTimer);
          _numberTimer = setTimeout(_drawSpeciesNumbers, 150);
        };
        c.on('move', move);
        _numberMoves.push([c, move]);
      });
      _sayHidden(laid.hidden);
      var present = function (id) {
        return id !== null && circles.some(function (c) { return String(c._pd.plantId) === id; });
      };
      if (!present(_findPinned)) _findPinned = null;          // its last plant went
      _ringSpecies(present(_findShown) ? _findShown : _findPinned);
      _markPinned();
    }

    // The legend says how many numbers wait for a closer zoom, under the plants.
    function _sayHidden(n) {
      var sec = document.querySelector('#legend-body [data-section="plants"]');
      if (!sec) return;
      var note = sec.querySelector('.legend-hidden');
      if (!n) { if (note) note.parentNode.removeChild(note); return; }
      if (!note) {
        note = document.createElement('div');
        note.className = 'legend-note legend-hidden';
        sec.appendChild(note);
      }
      note.textContent = 'Zoom in for ' + n + (n === 1 ? ' more number' : ' more numbers');
    }

    // Plants changed size on screen: a zoom, or the timeline (04-tools.js).
    function _refitSpeciesNumbers() {
      if (_speciesNumberLayer) _drawSpeciesNumbers();
      else if (_findShown !== null) _ringSpecies(_findShown);
    }

    function _findPane() {
      if (!map.getPane('speciesFindPane')) {
        var p = map.createPane('speciesFindPane');
        p.style.zIndex = 590;             // over the plants, under the numbers
        p.style.pointerEvents = 'none';
      }
      return 'speciesFindPane';
    }

    // Ring every plant of one species (its plant id), or none (null): a dark
    // ring under a white one, so it shows on a photo and on the street map.
    function _ringSpecies(id) {
      if (_findLayer) map.removeLayer(_findLayer);
      _findLayer = null;
      _findShown = id === null || id === undefined ? null : String(id);
      if (_findShown === null || !_shown(plantLayerGroup)) return;
      var pane = _findPane();
      _findLayer = L.layerGroup();
      _findLayer._spLegendOwn = true;
      _plantCircles().forEach(function (c) {
        if (String(c._pd.plantId) !== _findShown) return;
        var r = Math.max(_pixelRadius(c) + 4, 7);
        [['#000000', 6, 0.6], ['#ffffff', 2.5, 1]].forEach(function (s) {
          var ring = L.circleMarker(c.getLatLng(), { radius: r, color: s[0], weight: s[1],
            opacity: s[2], fill: false, interactive: false, pane: pane });
          ring._spLegendOwn = true;
          _findLayer.addLayer(ring);
        });
      });
      _findLayer.addTo(map);
    }

    function _markPinned() {
      var list = document.querySelectorAll('#legend-body button[data-find]');
      for (var i = 0; i < list.length; i++) {
        list[i].setAttribute('aria-pressed', String(list[i].dataset.find === _findPinned));
      }
    }

    // A click on a species in the legend keeps its plants ringed; a second
    // click, or Type, or closing the legend, lets them go.
    function _pinSpecies(id) {
      id = String(id);
      _findPinned = _findPinned === id ? null : id;
      _ringSpecies(_findPinned);
      _markPinned();
    }

    // Pointing at a species in the legend, or tabbing to it, rings its plants;
    // leaving it puts back the one a click keeps.
    function _hoverFind(ev, on) {
      var b = ev.target && ev.target.closest ? ev.target.closest('button[data-find]') : null;
      if (!b || (ev.relatedTarget && b.contains(ev.relatedTarget))) return;
      var id = on ? b.dataset.find : _findPinned;
      if (id !== _findShown) _ringSpecies(id);
    }
