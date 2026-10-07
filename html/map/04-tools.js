// html/map/04-tools.js — canvas renderer, geometry utilities, snap-to-grid, canopy preview, growth timeline, measurement, annotations.
//
// Split from the former single map.html <script> (V1.64). These are
// CLASSIC scripts loaded sequentially by map.html — NOT ES modules —
// so the shared-global execution model (and order) is byte-for-byte
// what the monolith had; ES modules can't load from file:// in
// Chromium without CORS flags. Cross-file calls resolve at call time
// through the shared global scope. The Python↔JS contract over these
// globals is pinned by tests/test_map_js.py + tests/test_bridge_contract.py.
    // ── Canvas renderer for non-interactive overlays (better perf than SVG) ──
    var canvasRenderer = L.canvas({ padding: 0.5 });

    // ── Utilities ─────────────────────────────────────────────────────────────
    function debounce(fn, delay) {
      var timer = null;
      return function() {
        var args = arguments, ctx = this;
        clearTimeout(timer);
        timer = setTimeout(function() { fn.apply(ctx, args); }, delay);
      };
    }

    // ── Snap to grid ──────────────────────────────────────────────────────────
    var snapEnabled  = false;
    var snapGridSize = 1.0;       // metres — chosen via the Grid menu
    var gridColor    = '#4a7a4a';
    var gridOpacity  = 0.4;       // 0..1
    var gridOverlay  = null;
    var debouncedGridRedraw = debounce(drawGridOverlay, 150);

    function setSnapEnabled(enabled, gridSize) {
      snapEnabled  = enabled;
      if (gridSize && gridSize > 0) snapGridSize = gridSize;
      if (enabled) {
        drawGridOverlay();
        map.on('moveend', debouncedGridRedraw);
        map.on('zoomend', debouncedGridRedraw);
      } else {
        if (gridOverlay) { map.removeLayer(gridOverlay); gridOverlay = null; }
        map.off('moveend', debouncedGridRedraw);
        map.off('zoomend', debouncedGridRedraw);
      }
    }

    // Update grid colour and opacity. Re-renders the overlay so changes
    // are visible immediately; safe to call when the grid is off.
    function setGridStyle(color, opacity) {
      if (typeof color === 'string' && color) gridColor = color;
      if (typeof opacity === 'number' && opacity >= 0 && opacity <= 1) {
        gridOpacity = opacity;
      }
      if (snapEnabled) drawGridOverlay();
    }

    function snapLatLng(lat, lng) {
      if (!snapEnabled) return [lat, lng];
      var gridLat = snapGridSize / 111320;
      var gridLng = snapGridSize / (111320 * Math.cos(lat * Math.PI / 180));
      return [
        Math.round(lat / gridLat) * gridLat,
        Math.round(lng / gridLng) * gridLng
      ];
    }

    function drawGridOverlay() {
      if (gridOverlay) { map.removeLayer(gridOverlay); gridOverlay = null; }
      if (!snapEnabled) return;
      // Only draw when the grid spacing would be at least a few pixels
      // wide; otherwise the overlay looks like solid noise.
      var z = map.getZoom();
      var minZoom = (snapGridSize <= 1) ? 17
                  : (snapGridSize <= 5) ? 15
                  : (snapGridSize <= 10) ? 13
                  : 9;
      if (z < minZoom) return;

      var bounds = map.getBounds();
      var gridLat = snapGridSize / 111320;
      var centerLat = bounds.getCenter().lat;
      var gridLng = snapGridSize / (111320 * Math.cos(centerLat * Math.PI / 180));
      var lines = [];

      var startLat = Math.floor(bounds.getSouth() / gridLat) * gridLat;
      var startLng = Math.floor(bounds.getWest() / gridLng) * gridLng;

      for (var lt = startLat; lt <= bounds.getNorth(); lt += gridLat) {
        lines.push([[lt, bounds.getWest()], [lt, bounds.getEast()]]);
      }
      for (var ln = startLng; ln <= bounds.getEast(); ln += gridLng) {
        lines.push([[bounds.getSouth(), ln], [bounds.getNorth(), ln]]);
      }

      gridOverlay = L.layerGroup(lines.map(function(pts) {
        return L.polyline(pts, {
          color: gridColor, weight: 0.5, opacity: gridOpacity,
          interactive: false, renderer: canvasRenderer
        });
      })).addTo(map);
    }

    // ── Canopy preview ───────────────────────────────────────────────────────
    var canopyVisible = false;
    var canopyGroup = L.layerGroup();  // single group for all canopy circles

    function setCanopyVisible(visible) {
      canopyVisible = visible;
      if (visible) {
        rebuildCanopyGroup();
        canopyGroup.addTo(map);
      } else {
        map.removeLayer(canopyGroup);
      }
    }

    function rebuildCanopyGroup() {
      canopyGroup.clearLayers();
      if (!canopyVisible) return;

      Object.keys(plantMarkers).forEach(function(mid) {
        var m = plantMarkers[mid];
        if (!m._pd) return;
        var radius = Math.max((m._pd.spacingM || 1.0) / 2, 0.5);
        L.circle(m.getLatLng(), {
          radius: radius,
          color: '#a5d6a7', weight: 1, dashArray: '4 3',
          fillColor: '#a5d6a7', fillOpacity: 0.08,
          interactive: false,
          renderer: canvasRenderer,    // see placePlantMarker for the rationale
        }).addTo(canopyGroup);
      });
    }

    function drawCanopies() { rebuildCanopyGroup(); }

    // ── Timeline / succession visualization ─────────────────────────────────
    var timelineActive = false;
    var originalRadii = {};  // markerId -> original radius (for reset)

    function setTimelineYearByPlantId(year, pidFactors, pidPresence, pidSpread) {
      // pidFactors: {plantId: scaleFactor} where scaleFactor is 0.1 to 1.0
      // pidPresence (optional): {plantId: 0..1} succession opacity — pioneers
      //   fade out, climax species fade in. Absent ⇒ all fully present.
      // pidSpread (optional): {plantId: >=1.0} footprint expansion — self-
      //   spreaders widen their canopy as the colony fills in. Absent ⇒ 1.0.
      pidPresence = pidPresence || {};
      pidSpread = pidSpread || {};
      if (year === 0) {
        // Reset all markers to original size
        timelineActive = false;
        Object.keys(originalRadii).forEach(function(mid) {
          var m = plantMarkers[mid];
          if (m && m.setRadius) {
            m.setRadius(originalRadii[mid]);
            m.setStyle({fillOpacity: 0.35, opacity: 1.0});
          }
        });
        originalRadii = {};
        if (canopyVisible) rebuildCanopyGroup();
        _refitSpeciesNumbers();         // sizes changed (13-species-numbers.js)
        return;
      }

      timelineActive = true;

      Object.keys(plantMarkers).forEach(function(mid) {
        var m = plantMarkers[mid];
        if (!m || !m._pd || !m.setRadius) return;
        var factor = pidFactors[m._pd.plantId];
        if (factor === undefined) return;

        // Save original radius on first timeline activation
        if (!originalRadii[mid]) {
          originalRadii[mid] = m.getRadius();
        }

        var spread = pidSpread[m._pd.plantId];
        if (spread === undefined) spread = 1.0;
        var matureRadius = originalRadii[mid];
        // Growth scales the marker; spread additionally widens self-spreaders'
        // footprint (radius only) as the colony fills the gaps over time.
        var currentRadius = matureRadius * factor * spread;
        m.setRadius(Math.max(currentRadius, 0.3));

        // Young plants more transparent; succession presence dims pioneers as
        // they fade and keeps climax species faint until they come up.
        var presence = pidPresence[m._pd.plantId];
        if (presence === undefined) presence = 1.0;
        var fillOp = (0.15 + 0.20 * factor) * presence;
        var strokeOp = (0.4 + 0.6 * factor) * presence;
        m.setStyle({fillOpacity: fillOp, opacity: strokeOp});
      });

      // Rebuild canopy if visible (canopy scales with markers)
      if (canopyVisible) rebuildCanopyGroup();
      _refitSpeciesNumbers();
    }

    // ── Measurement tool ───────────────────────────────────────────────────────
    // A measurement is part of the design since V3.11 (F215). Until then it
    // lived only here: Python never heard of one, so undo could not take it
    // back (Ctrl+Z after measuring undid the thing before it), the selection
    // box could not catch it, nothing saved it and nothing cleared it. Now
    // the page draws it and tells Python (onMeasurementAdded), Python keeps it
    // as a feature, and a redraw (open, undo) puts it back via loadMeasurement.
    var _MEASURE_LOOK   = { color: '#fdd835', weight: 2, dashArray: '8 4', opacity: 0.9 };
    // Selected: solid and heavier, since the selection's yellow is its colour.
    var _MEASURE_PICKED = { color: '#fdd835', weight: 4, dashArray: null, opacity: 1 };

    function _measureDot(ll) {
      return L.circleMarker(ll, { radius: 5, color: '#fdd835',
                                  fillColor: '#fdd835', fillOpacity: 1 });
    }

    function handleMeasureClick(lat, lng) {
      if (!measureStart) {
        // First click: a dot where it starts, nothing committed yet.
        _cancelMeasureStart();
        measureStart = L.latLng(lat, lng);
        _measureWipMarker = _measureDot([lat, lng]).addTo(map);
        return;
      }
      var pts = [[measureStart.lat, measureStart.lng], [lat, lng]];
      var id = 'm' + Date.now() + Math.random().toString(36).slice(2, 6);
      _cancelMeasureStart();                 // ready for the next one
      drawMeasurement(id, pts);
      if (bridge && bridge.onMeasurementAdded) {
        bridge.onMeasurementAdded(id, JSON.stringify(pts));
      }
    }

    // Drop a half-made measurement. Any change of mode does (setMode): until
    // V3.11 its dot stayed after Esc and the next measurement started from it.
    function _cancelMeasureStart() {
      if (_measureWipMarker) {
        try { map.removeLayer(_measureWipMarker); } catch (e) {}
      }
      _measureWipMarker = null;
      measureStart = null;
    }

    // One measurement: a dashed line, a dot at each end, its length on top.
    function drawMeasurement(id, pts) {
      var a = L.latLng(pts[0]), b = L.latLng(pts[1]);
      var dist = a.distanceTo(b);
      var group = L.layerGroup();
      var line = L.polyline([a, b], Object.assign({ interactive: true },
                                                  _MEASURE_LOOK)).addTo(group);
      var ends = [_measureDot(a).addTo(group), _measureDot(b).addTo(group)];
      L.tooltip({ permanent: true, direction: 'top', offset: [0, -10],
                  className: 'measure-label', opacity: 0.95 })
        .setContent(dist < 1000 ? dist.toFixed(1) + ' m'
                                : (dist / 1000).toFixed(2) + ' km')
        .setLatLng([(a.lat + b.lat) / 2, (a.lng + b.lng) / 2]).addTo(group);
      group._measure = { id: id, points: [[a.lat, a.lng], [b.lat, b.lng]],
                         line: line, ends: ends };
      [line].concat(ends).forEach(function (part) {
        // Right-click removes just this one; Shift/Ctrl/Cmd-click selects it.
        part.on('contextmenu', function (ev) {
          L.DomEvent.stop(ev);
          _removeMeasureById(id);
          _refreshSelectionVisuals();
          if (bridge && bridge.onMeasurementsRemoved) {
            bridge.onMeasurementsRemoved(JSON.stringify([id]));
          }
        });
        part.on('click', function (ev) {
          var oe = ev.originalEvent;
          if (oe && (oe.shiftKey || oe.ctrlKey || oe.metaKey)) {
            L.DomEvent.stop(ev);
            toggleSelection({ kind: 'measure', measureId: id });
          }
        });
      });
      if (measureVisible) group.addTo(map);
      measureLayers.push(group);
      return group;
    }

    // From the design (render_project_to_map): draw it, tell nobody.
    function loadMeasurement(id, pts) {
      _removeMeasureById(id);
      if (pts && pts.length === 2) drawMeasurement(id, pts);
    }

    function _removeMeasureById(id) {
      for (var i = measureLayers.length - 1; i >= 0; i--) {
        var g = measureLayers[i];
        if (g._measure && g._measure.id === id) {
          try { map.removeLayer(g); } catch (e) {}
          measureLayers.splice(i, 1);
        }
      }
      for (var j = selectedItems.length - 1; j >= 0; j--) {
        if (selectedItems[j].kind === 'measure' &&
            selectedItems[j].measureId === id) selectedItems.splice(j, 1);
      }
    }

    // The selection's look, from _refreshSelectionVisuals (01-core.js).
    function refreshMeasureSelection() {
      measureLayers.forEach(function (g) {
        var m = g._measure;
        if (!m) return;
        var sel = _selectionContains({ kind: 'measure', measureId: m.id });
        m.line.setStyle(sel ? _MEASURE_PICKED : _MEASURE_LOOK);
        m.ends.forEach(function (dot) { dot.setRadius(sel ? 7 : 5); });
      });
    }

    // The selection box catches a shown measurement when an end, or its middle
    // (where its length is written), is inside (_marqueeHitTest, 01-core.js).
    function measureMarqueeHits(bounds, hits) {
      if (!measureVisible) return;
      measureLayers.forEach(function (g) {
        var p = g._measure && g._measure.points;
        if (!p) return;
        var mid = [(p[0][0] + p[1][0]) / 2, (p[0][1] + p[1][1]) / 2];
        if ([p[0], p[1], mid].some(function (q) { return bounds.contains(L.latLng(q)); })) {
          hits.push({ kind: 'measure', measureId: g._measure.id });
        }
      });
    }

    // Every measurement off the map and nothing said: a redraw is about to
    // load the design's own (render_project_to_map), or a new design starts.
    function clearMeasure() {
      measureLayers.forEach(function(g) {
        try { map.removeLayer(g); } catch (e) {}
      });
      measureLayers = [];
      _cancelMeasureStart();
    }

    function setMeasureVisible(visible) {
      // View-bar toggle: hide existing measurements without deleting
      // them, so toggling back on restores the same lines & labels.
      measureVisible = !!visible;
      measureLayers.forEach(function(g) {
        if (measureVisible) {
          try { g.addTo(map); } catch (e) {}
        } else {
          try { map.removeLayer(g); } catch (e) {}
        }
      });
    }

    // ── Annotations ───────────────────────────────────────────────────────────
    function handleAnnotateClick(lat, lng) {
      if (bridge) bridge.onAnnotateRequested(lat, lng);
    }

    function placeAnnotation(id, lat, lng, text) {
      var icon = L.divIcon({
        className: 'annotation-label',
        html: '<span>' + escH(text) + '</span>',
        iconSize: [0, 0],
        iconAnchor: [0, 0]
      });
      var marker = L.marker([lat, lng], { icon: icon, draggable: true }).addTo(map);
      marker.on('contextmenu', function(e) {
        L.DomEvent.stop(e);
        map.removeLayer(marker);
        delete annotations[id];
        if (bridge) bridge.onAnnotationRemoved(id);
      });
      marker.on('dragend', function() {
        var pos = marker.getLatLng();
        annotations[id].lat = pos.lat;
        annotations[id].lng = pos.lng;
      });
      annotations[id] = { marker: marker, text: text, lat: lat, lng: lng };
    }

    function clearAnnotations() {
      Object.keys(annotations).forEach(function(id) {
        map.removeLayer(annotations[id].marker);
      });
      annotations = {};
    }

