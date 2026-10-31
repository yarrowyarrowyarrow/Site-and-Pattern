// html/map/08-footprint.js — what the next click will cover, under the cursor
// while the map is placing (F191, V2.99).
//
// Classic script, loaded after 07-network.js by map.html — same shared-global
// model as the rest of html/map/*.js (see the header of 01-core.js). Its own
// file because 03-plants.js, where the pattern preview lives, is at its ceiling.
//
// Until V2.99 an armed map showed nothing where the pointer was: a pattern drew
// its plants only after its first click, and a single plant or a community not
// at all, though a Saskatoon is spaced 2.5 m apart and a community is ~3 m
// across. This draws, in the pattern preview's language (a yellow ring at the
// planting spacing, a green one at mature canopy):
//   - one plant, in Single;
//   - a Qty cluster exactly as _hexBurstPositions will lay it, with its count;
//   - the first plant of a Row, Grid or Circle, until its first click hands
//     over to _drawPatternPreview (a community's pattern: one ring its size);
//   - a single community's members where they will land, inside a ring round
//     all of them. The payload comes from src/placement_footprint.py and the
//     offsets use MapEventRouter._on_polyculture_click's arithmetic.
// Fill Area draws nothing here: its polygon preview is its footprint.
//
// Circles are built once per arming and moved on every mousemove, since a
// 50-plant cluster is 100 circles. They sit in a pane that takes no pointer
// events, so a click always reaches the map under them.

    var _footprintLayer = null;   // L.layerGroup, on the map while shown
    var _footprintKey = '';       // what the circles were built for
    var _footprintRings = [];     // [{circle, i}], i indexes the positions
    var _footprintOutline = null; // the ring round a community
    var _footprintBadge = null;   // "5 plants", for a cluster

    function _footprintPane() {
      if (!map.getPane('footprintPane')) {
        var p = map.createPane('footprintPane');
        p.style.zIndex = 450;             // over placed plants, under markers
        p.style.pointerEvents = 'none';
      }
      return 'footprintPane';
    }

    // What the next click will cover: {key, sizes: [[spacingM, canopyM]],
    // at(lat, lng) -> [[lat, lng]], outline: metres, badge: text}; or null when
    // nothing is armed, or a pattern's own preview is drawing.
    function _footprintSpec() {
      var sizes = [], i;
      if (currentMode === 'plant' && currentPlant) {
        var pat = currentPlant.pattern || {kind: 'single'};
        var kind = pat.kind || 'single';
        if (kind !== 'single' && _patternStage >= 1) return null;
        var s = currentPlant.spacing_m || 1.0;
        var canopy = currentPlant.mature_canopy_m || (s * 1.5);
        if ((pat.params || {}).community) canopy = s;
        var qty = kind === 'single' ? Math.max(1, currentPlant.quantity || 1) : 1;
        for (i = 0; i < qty; i++) sizes.push([s, canopy]);
        return {
          key: ['plant', currentPlant.id, kind, qty, s, canopy].join('|'),
          sizes: sizes,
          at: function (lat, lng) {
            return qty > 1 ? _hexBurstPositions(lat, lng, s, qty) : [[lat, lng]];
          },
          outline: 0,
          badge: qty > 1 ? qty + ' plants' : ''
        };
      }
      if (currentMode === 'polyculture' && currentCommunity) {
        var members = currentCommunity.members || [];
        for (i = 0; i < members.length; i++) sizes.push([members[i][2], members[i][3]]);
        return {
          key: 'community|' + currentCommunity.name + '|' + members.length,
          sizes: sizes,
          at: function (lat, lng) {
            var cosLat = Math.cos(lat * Math.PI / 180) || 1e-9;
            return members.map(function (m) {
              return [lat + m[1] / 111320, lng + m[0] / (111320 * cosLat)];
            });
          },
          outline: currentCommunity.radius_m || 0,
          badge: ''
        };
      }
      return null;
    }

    function _clearFootprint() {
      if (_footprintLayer) map.removeLayer(_footprintLayer);
      _footprintLayer = null;
      _footprintKey = '';
      _footprintRings = [];
      _footprintOutline = null;
      _footprintBadge = null;
    }

    function _buildFootprint(spec) {
      _clearFootprint();
      var pane = _footprintPane();
      var layer = L.layerGroup();
      for (var i = 0; i < spec.sizes.length; i++) {
        // A placed marker's radius (placePlantMarker), so the ghost is the
        // size of what lands.
        var spacingR = Math.max((spec.sizes[i][0] || 1.0) / 2, 0.05);
        var canopyR = Math.max((spec.sizes[i][1] || 0) / 2, spacingR);
        _footprintRings.push({i: i, circle: L.circle([0, 0], {
          radius: canopyR, color: '#a5d6a7', weight: 1, dashArray: '4 5',
          fill: false, opacity: 0.8, interactive: false, pane: pane
        }).addTo(layer)});
        _footprintRings.push({i: i, circle: L.circle([0, 0], {
          radius: spacingR, color: '#fdd835', weight: 1, dashArray: '2 3',
          fillColor: '#fdd835', fillOpacity: 0.15, interactive: false, pane: pane
        }).addTo(layer)});
      }
      if (spec.outline > 0) {
        _footprintOutline = L.circle([0, 0], {
          radius: spec.outline, color: '#fdd835', weight: 2, dashArray: '4 4',
          fill: false, opacity: 0.7, interactive: false, pane: pane
        }).addTo(layer);
      }
      if (spec.badge) {
        // In the tooltip pane, over markers and labels, like the pattern
        // preview's count; a tooltip takes no pointer events either.
        _footprintBadge = L.tooltip({permanent: true, direction: 'right',
                                     offset: [10, 0], className: 'measure-label',
                                     opacity: 0.9})
                           .setContent(spec.badge).setLatLng([0, 0]);
        _footprintBadge.addTo(layer);
      }
      _footprintKey = spec.key;
      _footprintLayer = layer;
    }

    // onMapMouseMove (01-core.js) calls this with the pointer's position.
    function updateCursorFootprint(latlng) {
      var spec = _footprintSpec();
      if (!spec || !latlng) { hideCursorFootprint(); return; }
      if (spec.key !== _footprintKey) _buildFootprint(spec);
      var pts = spec.at(latlng.lat, latlng.lng);
      for (var j = 0; j < _footprintRings.length; j++) {
        var p = pts[_footprintRings[j].i];
        if (p) _footprintRings[j].circle.setLatLng(p);
      }
      if (_footprintOutline) _footprintOutline.setLatLng(latlng);
      if (_footprintBadge) _footprintBadge.setLatLng(latlng);
      if (!map.hasLayer(_footprintLayer)) _footprintLayer.addTo(map);
    }

    // The pointer left the map, or nothing is armed: off the map, still built.
    function hideCursorFootprint() {
      if (_footprintLayer && map.hasLayer(_footprintLayer)) {
        map.removeLayer(_footprintLayer);
      }
    }

    // setMode (05-features.js) calls this on every mode change: whatever was
    // armed before needs new circles, or none.
    function resetCursorFootprint() { _clearFootprint(); }
