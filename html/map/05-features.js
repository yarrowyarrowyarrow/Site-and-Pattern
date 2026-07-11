// html/map/05-features.js — structures, hedgerows, custom shapes, mode control, satellite alignment/detail, layer visibility, project load/clear, zoom.
//
// Split from the former single map.html <script> (V1.64). These are
// CLASSIC scripts loaded sequentially by map.html — NOT ES modules —
// so the shared-global execution model (and order) is byte-for-byte
// what the monolith had; ES modules can't load from file:// in
// Chromium without CORS flags. Cross-file calls resolve at call time
// through the shared global scope. The Python↔JS contract over these
// globals is pinned by tests/test_map_js.py + tests/test_bridge_contract.py.
    // ── Structure placement (S1) ───────────────────────────────────────────
    function placeStructureOnMap(structDef, lat, lng) {
      var id = 'struct_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
      var group = L.layerGroup().addTo(map);
      var sizeM = structDef.size_m || 3.0;
      var widthM = structDef.width_m || sizeM;
      var color = structDef.color || '#78909c';
      var fillColor = structDef.fill_color || color;
      var fillOpacity = structDef.fill_opacity || 0.35;
      var shape = structDef.shape || 'rectangle';
      var name = structDef.name || 'Structure';
      var icon = structDef.icon || '';

      var mainLayer;

      if (shape === 'circle' || shape === 'ellipse' || shape === 'spiral' || shape === 'keyhole') {
        // Render as circle
        mainLayer = L.circle([lat, lng], {
          radius: sizeM / 2,
          color: color,
          weight: 2,
          fillColor: fillColor,
          fillOpacity: fillOpacity
        }).addTo(group);

        // Spiral: add decorative inner arcs
        if (shape === 'spiral') {
          var innerR = sizeM / 4;
          L.circle([lat, lng], {
            radius: innerR,
            color: color,
            weight: 1.5,
            fillOpacity: 0,
            dashArray: '4 3'
          }).addTo(group);
        }

        // Keyhole: add a small notch indicator
        if (shape === 'keyhole') {
          var notchLat = lat - (sizeM * 0.3) / 111320;
          L.circle([notchLat, lng], {
            radius: sizeM / 6,
            color: '#5d4037',
            weight: 1.5,
            fillColor: '#8d6e63',
            fillOpacity: 0.5
          }).addTo(group);
        }

      } else {
        // Rectangle: use L.rectangle
        var halfLen = sizeM / 2;
        var halfWid = widthM / 2;
        var dLat = halfLen / 111320;
        var dLng = halfWid / (111320 * Math.cos(lat * Math.PI / 180));
        var bounds = [[lat - dLat, lng - dLng], [lat + dLat, lng + dLng]];
        mainLayer = L.rectangle(bounds, {
          color: color,
          weight: 2,
          fillColor: fillColor,
          fillOpacity: fillOpacity
        }).addTo(group);
      }

      // Label with icon
      var labelIcon = L.divIcon({
        className: 'structure-label',
        html: '<span class="struct-icon">' + escH(icon) + '</span> ' + escH(name),
        iconSize: [0, 0],
        iconAnchor: [0, 12]
      });
      var labelMarker = L.marker([lat, lng], { icon: labelIcon, interactive: false }).addTo(group);

      // Tooltip on hover
      mainLayer.bindTooltip(
        '<b>' + escH(icon) + ' ' + escH(name) + '</b><br>' +
        '<span style="color:#78909c;font-size:10px">' + Number(sizeM) + 'm' +
        (structDef.maintenance_hours_year ? ' · ~' + Number(structDef.maintenance_hours_year) + ' hrs/yr' : '') +
        '<br>Right-click to remove</span>',
        { className: 'plant-marker-label' }
      );

      // Store metadata
      mainLayer._struct = {
        id: id,
        structId: structDef.id,
        name: name,
        icon: icon,
        lat: lat,
        lng: lng,
        sizeM: sizeM,
        widthM: widthM,
        maintenance: structDef.maintenance_hours_year || 0
      };

      // Right-click: existing trees get a small menu (switch conifer/
      // deciduous, or remove); everything else removes directly. Uses the
      // group's live position so a dragged marker removes at its real spot.
      mainLayer.on('contextmenu', function(e) {
        L.DomEvent.stop(e);
        var pos = group._pdStruct || { lat: lat, lng: lng };
        function _remove() {
          map.removeLayer(group);
          delete structureMarkers[id];
          if (bridge) bridge.onStructureRemoved(id, structDef.id,
                                                pos.lat, pos.lng);
        }
        if (structDef.id === 'existing_tree' &&
            typeof showContextMenu === 'function') {
          var oe = e.originalEvent;
          showContextMenu(oe.clientX, oe.clientY, [
            { label: '🌲 Make coniferous', action: function() {
                if (group._pdExisting)
                  _setExistingFoliage(group._pdExisting, 'evergreen'); } },
            { label: '🌳 Make deciduous', action: function() {
                if (group._pdExisting)
                  _setExistingFoliage(group._pdExisting, 'deciduous'); } },
            'sep',
            { label: '🗑 Remove tree', action: _remove },
          ]);
          return;
        }
        _remove();
      });

      // Stash identifying metadata on the group so undoStructureAt can
      // find this exact marker by (structId, lat, lng) later.
      group._pdStruct = { structId: structDef.id, lat: lat, lng: lng };
      structureMarkers[id] = group;

      // Existing tree/building marks are editable like plants (V2.26): drag
      // to the real spot, scroll to match the crown size. Gated to the
      // 'Existing' category so decorative structures stay fixed.
      if (structDef.category === 'Existing') {
        _makeExistingEditable(group, mainLayer, labelMarker, id,
                              structDef.id, lat, lng, sizeM, shape, widthM,
                              name);
      }
      return id;
    }

    // Switch an existing tree between conifer/deciduous from the map (V2.26):
    // recolour the crown + swap the label icon live, and persist the choice
    // (src/tree_edit_flow.on_existing_feature_foliage) — drives the 2D colour,
    // the 3D crown shape and the winter-shade weighting.
    var _FOLIAGE_STYLE = {
      evergreen: { color: '#1b5e20', fill: '#2e7d32', icon: '🌲' },
      deciduous: { color: '#8d6e00', fill: '#c0ca33', icon: '🌳' },
    };
    function _setExistingFoliage(st, foliage) {
      var s = _FOLIAGE_STYLE[foliage];
      if (!s) return;
      if (st.layer.setStyle) st.layer.setStyle({ color: s.color,
                                                 fillColor: s.fill });
      st.foliage = foliage;
      if (st.label && st.label.setIcon) {
        st.label.setIcon(L.divIcon({ className: 'structure-label',
          html: '<span class="struct-icon">' + s.icon + '</span> ' +
                escH(st.name || 'Tree'),
          iconSize: [0, 0], iconAnchor: [0, 12] }));
      }
      if (bridge && bridge.onExistingFeatureFoliage)
        bridge.onExistingFeatureFoliage(st.id, st.structId, st.lat, st.lng,
                                        foliage);
    }

    // ── Editable existing features (drag + scroll-resize, V2.26) ─────────────
    // Detected/marked trees & buildings can be dragged to their true spot and
    // scroll-resized to match the satellite photo. Persisted via the bridge
    // (src/tree_edit_flow.py); the marker itself moves/resizes live here.
    var _existingWheelReady = false;
    var _existingResizeTimer = null, _existingResizePending = null;

    function _moveExistingLayer(st) {
      if (st.layer.setLatLng) {                 // circle (trees)
        st.layer.setLatLng([st.lat, st.lng]);
      } else if (st.layer.setBounds) {          // rectangle (marked building)
        var dLat = (st.sizeM / 2) / 111320;
        var dLng = (st.widthM / 2) / (111320 * Math.cos(st.lat * Math.PI / 180));
        st.layer.setBounds([[st.lat - dLat, st.lng - dLng],
                            [st.lat + dLat, st.lng + dLng]]);
      }
      if (st.label && st.label.setLatLng) st.label.setLatLng([st.lat, st.lng]);
    }

    function _makeExistingEditable(group, layer, label, id, structId,
                                   lat, lng, sizeM, shape, widthM, name) {
      var st = { id: id, structId: structId, lat: lat, lng: lng,
                 sizeM: sizeM, widthM: widthM || sizeM, layer: layer,
                 label: label, group: group, name: name };
      group._pdExisting = st;                   // read by the wheel handler
      var el = layer.getElement && layer.getElement();
      if (el) el.style.cursor = 'move';
      var dragging = false, moved = false;
      function onMove(e) {
        moved = true;
        st.lat = e.latlng.lat; st.lng = e.latlng.lng;
        _moveExistingLayer(st);
      }
      function onUp() {
        if (!dragging) return;
        dragging = false;
        map.off('mousemove', onMove); map.off('mouseup', onUp);
        try { map.dragging.enable(); } catch (_) {}
        if (moved && bridge && bridge.onExistingFeatureMoved) {
          bridge.onExistingFeatureMoved(st.id, st.structId,
                                        st._baseLat, st._baseLng,
                                        st.lat, st.lng);
        }
        st._baseLat = st.lat; st._baseLng = st.lng;
        group._pdStruct.lat = st.lat; group._pdStruct.lng = st.lng;
      }
      st._baseLat = lat; st._baseLng = lng;
      layer.on('mousedown', function(e) {
        if (currentMode !== 'none' && currentMode !== 'select') return;
        var oe = e.originalEvent;
        if (oe && oe.button !== undefined && oe.button !== 0) return;
        L.DomEvent.stop(e);
        dragging = true; moved = false;
        try { map.dragging.disable(); } catch (_) {}
        map.on('mousemove', onMove); map.on('mouseup', onUp);
      });
      _initExistingWheel();
    }

    // One container-level wheel handler resizes the existing-feature circle
    // under the cursor (instead of zooming). When the cursor isn't over one,
    // it does nothing and Leaflet zooms as normal.
    function _initExistingWheel() {
      if (_existingWheelReady) return;
      _existingWheelReady = true;
      map.getContainer().addEventListener('wheel', function(ev) {
        var st = _existingCircleUnderCursor(ev);
        if (!st) return;                        // not over a tree → zoom
        ev.preventDefault(); ev.stopPropagation();
        var newR = Math.max(0.5, st.layer.getRadius() +
                            (ev.deltaY < 0 ? 0.5 : -0.5));
        st.layer.setRadius(newR);
        st.sizeM = newR * 2;
        _existingResizePending = st;
        if (_existingResizeTimer) clearTimeout(_existingResizeTimer);
        _existingResizeTimer = setTimeout(function() {
          var p = _existingResizePending; _existingResizePending = null;
          if (p && bridge && bridge.onExistingFeatureResized)
            bridge.onExistingFeatureResized(p.id, p.structId, p.lat, p.lng,
                                            p.sizeM);
        }, 350);
      }, { passive: false, capture: true });
    }

    function _existingCircleUnderCursor(ev) {
      var pt;
      try { pt = map.mouseEventToLatLng(ev); } catch (_) { return null; }
      var best = null, bestR = Infinity;
      Object.keys(structureMarkers).forEach(function(sid) {
        var st = structureMarkers[sid] && structureMarkers[sid]._pdExisting;
        if (!st || !st.layer.getRadius) return;    // circles (trees) only
        var d = map.distance(pt, st.layer.getLatLng());
        var r = st.layer.getRadius();
        if (d <= r && r < bestR) { best = st; bestR = r; }
      });
      return best;
    }

    // Load a structure from saved project
    function loadStructure(structDef, lat, lng) {
      // Idempotent: drop any marker already at this exact spot so re-rendering
      // (e.g. a second OSM import) replaces it in place instead of stacking a
      // duplicate. Project load clears first, so this is a no-op there.
      undoStructureAt(structDef.id, lat, lng);
      placeStructureOnMap(structDef, lat, lng);
    }

    // Undo helper — remove the most recently placed structure marker
    // matching (structId, lat, lng). Walks structureMarkers in reverse
    // insertion order so undo always pops the latest. No-op if nothing
    // matches.
    function undoStructureAt(structId, lat, lng) {
      var keys = Object.keys(structureMarkers);
      for (var i = keys.length - 1; i >= 0; i--) {
        var key = keys[i];
        var group = structureMarkers[key];
        var meta  = group && group._pdStruct;
        if (!meta) continue;
        if (meta.structId !== structId) continue;
        if (Math.abs(meta.lat - lat) > 1e-6) continue;
        if (Math.abs(meta.lng - lng) > 1e-6) continue;
        try { map.removeLayer(group); } catch (e) {}
        delete structureMarkers[key];
        return true;
      }
      return false;
    }

    // ── Hedgerow drawing (S2) ────────────────────────────────────────────────
    function handleHedgerowClick(lat, lng) {
      hedgerowPoints.push([lat, lng]);

      // Draw vertex marker
      L.circleMarker([lat, lng], {
        radius: 4,
        color: currentHedgerow ? currentHedgerow.color : '#4caf50',
        fillColor: currentHedgerow ? currentHedgerow.color : '#4caf50',
        fillOpacity: 1
      }).addTo(drawnItems);

      refreshHedgerowPolyline();
    }

    function refreshHedgerowPolyline() {
      if (hedgerowPreview) { map.removeLayer(hedgerowPreview); hedgerowPreview = null; }
      if (hedgerowPoints.length >= 2) {
        var color = currentHedgerow ? currentHedgerow.color : '#4caf50';
        hedgerowPreview = L.polyline(hedgerowPoints, {
          color: color, weight: 3, opacity: 0.7, dashArray: '6 4'
        }).addTo(map);
      }
    }

    function updateHedgerowPreview(latlng) {
      if (hedgerowPreview) { map.removeLayer(hedgerowPreview); }
      var color = currentHedgerow ? currentHedgerow.color : '#4caf50';
      var pts = hedgerowPoints.concat([[latlng.lat, latlng.lng]]);
      hedgerowPreview = L.polyline(pts, {
        color: color, weight: 3, opacity: 0.5, dashArray: '4 4'
      }).addTo(map);
    }

    function finishHedgerow() {
      if (hedgerowPoints.length < 2) return;
      if (hedgerowPreview) { map.removeLayer(hedgerowPreview); hedgerowPreview = null; }
      drawnItems.clearLayers();

      var id = 'hedge_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
      var cfg = currentHedgerow || {};
      var color   = cfg.color    || '#4caf50';
      var widthM  = cfg.width_m  || 1.5;
      var spacing = cfg.spacing_m || 1.0;
      var style   = cfg.style    || 'hedge';
      var species = cfg.species  || '';
      var group   = L.layerGroup().addTo(map);

      // Style definitions
      var styleMap = {
        'hedge':       { weight: 6, opacity: 0.6, dashArray: null,    fillDots: true },
        'fence':       { weight: 3, opacity: 0.8, dashArray: '8 6',  fillDots: false },
        'living_fence':{ weight: 5, opacity: 0.6, dashArray: '12 4', fillDots: true },
        'windbreak':   { weight: 8, opacity: 0.5, dashArray: null,    fillDots: true }
      };
      var s = styleMap[style] || styleMap['hedge'];

      // Main polyline
      var mainLine = L.polyline(hedgerowPoints, {
        color: color,
        weight: s.weight,
        opacity: s.opacity,
        dashArray: s.dashArray,
        lineCap: 'round',
        lineJoin: 'round'
      }).addTo(group);

      // Plant markers along the line
      if (s.fillDots) {
        var totalLen = 0;
        var segments = [];
        for (var i = 1; i < hedgerowPoints.length; i++) {
          var from = L.latLng(hedgerowPoints[i-1]);
          var to   = L.latLng(hedgerowPoints[i]);
          var segLen = from.distanceTo(to);
          segments.push({ from: from, to: to, len: segLen });
          totalLen += segLen;
        }
        var numPlants = Math.floor(totalLen / spacing) + 1;
        var distAlong = 0;
        var segIdx = 0;
        var segDist = 0;
        for (var p = 0; p < numPlants; p++) {
          var target = p * spacing;
          while (segIdx < segments.length - 1 && segDist + segments[segIdx].len < target) {
            segDist += segments[segIdx].len;
            segIdx++;
          }
          var seg = segments[segIdx];
          var frac = seg.len > 0 ? (target - segDist) / seg.len : 0;
          frac = Math.max(0, Math.min(1, frac));
          var ptLat = seg.from.lat + (seg.to.lat - seg.from.lat) * frac;
          var ptLng = seg.from.lng + (seg.to.lng - seg.from.lng) * frac;

          var dotColor = style === 'living_fence' ?
            (p % 2 === 0 ? color : shiftColor(color, 30)) : color;
          L.circleMarker([ptLat, ptLng], {
            radius: 3.5,
            color: dotColor,
            fillColor: dotColor,
            fillOpacity: 0.8,
            weight: 1
          }).addTo(group);
        }
      }

      // Label at midpoint
      var midIdx = Math.floor(hedgerowPoints.length / 2);
      var labelText = species || (style.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); }));
      var labelIcon = L.divIcon({
        className: 'hedgerow-label',
        html: escH(labelText),
        iconSize: [0, 0],
        iconAnchor: [0, 12]
      });
      L.marker(hedgerowPoints[midIdx], { icon: labelIcon, interactive: false }).addTo(group);

      // Tooltip
      var tooltipText = '<b>Hedgerow</b>';
      if (species) tooltipText += '<br>' + escH(species);
      tooltipText += '<br><span style="color:#78909c;font-size:10px">~' + Number(numPlants) + ' plants · ' +
        totalLen.toFixed(1) + 'm<br>Right-click to remove</span>';
      mainLine.bindTooltip(tooltipText, { className: 'plant-marker-label' });

      // Store metadata
      mainLine._hedge = {
        id: id,
        points: hedgerowPoints.slice(),
        style: style,
        color: color,
        widthM: widthM,
        spacingM: spacing,
        species: species,
        lengthM: totalLen,
        numPlants: numPlants
      };

      // Right-click to remove
      mainLine.on('contextmenu', function(e) {
        L.DomEvent.stop(e);
        map.removeLayer(group);
        delete hedgerowLayers[id];
        if (bridge) bridge.onHedgerowRemoved(id, JSON.stringify(hedgerowPoints));
      });

      hedgerowLayers[id] = group;

      // Notify Python
      if (bridge) bridge.onHedgerowComplete(id, JSON.stringify(hedgerowPoints.slice()), species, style, totalLen, numPlants);

      hedgerowPoints = [];
      setMode('none');
    }

    // Undo helper — remove a hedgerow group by its id. Returns true on hit.
    function undoHedgerowById(hedgeId) {
      var group = hedgerowLayers[hedgeId];
      if (!group) return false;
      try { map.removeLayer(group); } catch (e) {}
      delete hedgerowLayers[hedgeId];
      return true;
    }

    // Load a hedgerow from saved project
    function loadHedgerow(hedgeDef) {
      hedgerowPoints = hedgeDef.points || [];
      currentHedgerow = hedgeDef;
      if (hedgerowPoints.length >= 2) {
        finishHedgerow();
      }
      hedgerowPoints = [];
    }

    // ── Custom shape drawing (S3) ────────────────────────────────────────────
    function handleShapeClick(lat, lng) {
      // Close polygon if clicking near first point
      if (shapePoints.length >= 3) {
        var first = shapePoints[0];
        var firstPx = map.latLngToContainerPoint(L.latLng(first));
        var clickPx = map.latLngToContainerPoint(L.latLng(lat, lng));
        var dist = Math.sqrt(Math.pow(firstPx.x - clickPx.x, 2) + Math.pow(firstPx.y - clickPx.y, 2));
        if (dist < 12) {
          if (currentMode === 'fill') { finishFillArea(); } else { finishShape(); }
          return;
        }
      }

      shapePoints.push([lat, lng]);

      // Draw vertex marker
      var strokeColor = currentShape ? currentShape.stroke_color : '#2e7d32';
      L.circleMarker([lat, lng], {
        radius: 4, color: strokeColor,
        fillColor: strokeColor, fillOpacity: 1
      }).addTo(drawnItems);

      // Show close indicator on first point
      if (shapePoints.length === 1) {
        L.circleMarker([lat, lng], {
          radius: 6, color: strokeColor,
          fillColor: strokeColor, fillOpacity: 0.5
        }).addTo(drawnItems);
      }

      refreshShapePolyline();
    }

    function refreshShapePolyline() {
      if (shapePreview) { map.removeLayer(shapePreview); shapePreview = null; }
      if (shapePoints.length >= 2) {
        var color = currentShape ? currentShape.stroke_color : '#2e7d32';
        shapePreview = L.polyline(shapePoints, {
          color: color, weight: 2, opacity: 0.7, dashArray: '6 4'
        }).addTo(map);
      }
    }

    function updateShapePreview(latlng) {
      if (shapePreview) { map.removeLayer(shapePreview); }
      var color = currentShape ? currentShape.stroke_color : '#2e7d32';
      var pts = shapePoints.concat([[latlng.lat, latlng.lng]]);
      // Close preview polygon
      if (pts.length >= 3) {
        pts.push(pts[0]);
      }
      shapePreview = L.polyline(pts, {
        color: color, weight: 2, opacity: 0.5, dashArray: '4 4'
      }).addTo(map);
    }

    function finishShape() {
      if (shapePoints.length < 3) return;
      if (shapePreview) { map.removeLayer(shapePreview); shapePreview = null; }
      drawnItems.clearLayers();

      var cfg = currentShape || {};
      // Reuse an existing id when re-drawing in place (height edit) or loading a
      // saved shape, so the JS layer id stays in sync with the project feature's
      // shape_id; otherwise mint a fresh one.
      var id = cfg.shape_id || cfg.id ||
        ('shape_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5));
      // Idempotent redraw: re-rendering an id already on the map (e.g. a second
      // OSM import, or a load_shape after an edit) must replace in place, not
      // stack an orphaned duplicate layer. Drop any existing group first.
      if (shapeLayers[id]) {
        if (shapeEditId === id) exitShapeEditMode();
        map.removeLayer(shapeLayers[id]);
        delete shapeLayers[id];
      }
      var fillColor   = cfg.fill_color   || '#4caf50';
      var strokeColor = cfg.stroke_color || '#2e7d32';
      var fillOpacity = cfg.fill_opacity !== undefined ? cfg.fill_opacity : 0.25;
      var dashArray   = cfg.dash_array   || '';
      var label       = cfg.label        || '';
      var shapeType   = cfg.shape_type   || 'Custom';
      // Height (metres) makes a shape a shade caster. 0 = a plain area shape.
      var heightM     = cfg.height_m !== undefined ? +cfg.height_m : 0;

      var group = L.layerGroup().addTo(map);

      // A shade caster (heightM > 0) reads distinctly from a flat area shape:
      // a dashed stroke and a thin diagonal-hatch feel via a heavier border.
      var castsShade = heightM > 0;

      // Main polygon
      var polygon = L.polygon(shapePoints, {
        color: strokeColor,
        weight: castsShade ? 3 : 2,
        fillColor: fillColor,
        fillOpacity: fillOpacity,
        dashArray: castsShade ? '6 4' : (dashArray || null)
      }).addTo(group);

      // Calculate area
      var areaM2 = _polygonArea(shapePoints);
      var areaStr = areaM2 < 10000 ?
        areaM2.toFixed(1) + ' m²' :
        (areaM2 / 10000).toFixed(2) + ' ha';

      // Centre label. A shade caster shows a compact badge — a house/tree icon
      // (by what it represents) plus the height, e.g. "🏠 5m" / "🌳 5m" —
      // instead of the busier "<label> ☀ 5m". A flat area shape keeps its text
      // label. Hidden together with the shape via the "Structures" view toggle.
      var center = polygon.getBounds().getCenter();
      if (label || shapeType !== 'Custom' || castsShade) {
        var displayLabel;
        if (castsShade) {
          var treeCaster = /tree/i.test(shapeType) || cfg.caster_kind === 'tree';
          displayLabel = (treeCaster ? '🌳 ' : '🏠 ') + heightM + 'm';
        } else {
          displayLabel = label || shapeType || 'Shape';
        }
        var labelIcon = L.divIcon({
          className: 'shape-label',
          html: escH(displayLabel),
          iconSize: [0, 0],
          iconAnchor: [0, 8]
        });
        L.marker(center, { icon: labelIcon, interactive: false }).addTo(group);
      }

      // Tooltip
      var shadeLine = castsShade
        ? '<br>Casts shade — ' + escH(String(heightM)) + ' m tall'
          + '<br>Click to edit outline · right-click for height/remove'
        : '<br>Click to edit outline · right-click to remove';
      polygon.bindTooltip(
        '<b>' + escH(label || shapeType) + '</b><br>' +
        '<span style="color:#78909c;font-size:10px">Area: ' + escH(areaStr)
          + shadeLine + '</span>',
        { className: 'plant-marker-label' }
      );

      // Metadata
      polygon._shape = {
        id: id,
        points: shapePoints.slice(),
        shapeType: shapeType,
        label: label,
        fillColor: fillColor,
        strokeColor: strokeColor,
        fillOpacity: fillOpacity,
        dashArray: dashArray,
        areaM2: areaM2,
        heightM: heightM
      };

      // Right-click: edit height (shade casters) or remove. A shade caster
      // offers a height prompt; anything else just removes.
      polygon.on('contextmenu', function(e) {
        L.DomEvent.stop(e);
        if (shapeEditId === id) exitShapeEditMode();   // tearing this shape down
        if (castsShade) {
          var entry = prompt(
            'Height of this shade caster in metres (blank or 0 to remove):',
            String(heightM));
          if (entry === null) return;          // cancelled
          var newH = parseFloat(entry);
          if (!isNaN(newH) && newH > 0) {
            if (bridge) bridge.onShapeHeightChanged(id, newH);
            // Redraw in place with the new height.
            map.removeLayer(group);
            delete shapeLayers[id];
            currentShape = {
              shape_id: id,
              points: shapePoints.length ? shapePoints : polygon._shape.points,
              shape_type: shapeType, label: label,
              fill_color: fillColor, stroke_color: strokeColor,
              fill_opacity: fillOpacity, dash_array: dashArray,
              height_m: newH, _suppressBridge: true
            };
            shapePoints = polygon._shape.points.slice();
            finishShape();
            return;
          }
        }
        map.removeLayer(group);
        delete shapeLayers[id];
        if (bridge) bridge.onShapeRemoved(id);
      });

      // Left-click → edit the outline (drag vertices), mirroring boundaries.
      // Guarded on 'none' mode so it never hijacks a placement click; a
      // modifier click (shift/ctrl/cmd) toggles selection instead, matching
      // plants/boundaries/structures.
      polygon.on('click', function(e) {
        var oe = e.originalEvent;
        if (oe && (oe.shiftKey || oe.ctrlKey || oe.metaKey)) {
          L.DomEvent.stop(e);
          if (typeof toggleSelection === 'function') {
            toggleSelection({ kind: 'shape', shapeId: id });
          }
          return;
        }
        if (currentMode === 'none') {
          L.DomEvent.stop(e);
          enterShapeEditMode(id);
          return;
        }
        // Placement mode → forward to onMapClick (Leaflet won't fire the map's
        // click for a layer target) so the user can place on top of a visible
        // shape / shade footprint.
        onMapClick(e);
      });

      shapeLayers[id] = group;

      // Notify Python (trailing heightM; >0 promotes this to a shade caster).
      // _suppressBridge avoids a duplicate append when re-drawing in place
      // (height edit) or loading a saved shape.
      if (bridge && !(currentShape && currentShape._suppressBridge)) {
        bridge.onShapeComplete(id, JSON.stringify(shapePoints.slice()), label, shapeType, fillColor, strokeColor, fillOpacity, dashArray, areaM2, heightM);
      }

      shapePoints = [];
      setMode('none');
    }

    // Draw-then-fill (F3): finish the drawn polygon WITHOUT creating a shape —
    // hand the ring to Python, which scatters the chosen plant/mix/community
    // inside it and leaves only the plant markers (no hardscape shape).
    function finishFillArea() {
      if (shapePoints.length < 3) return;
      var pts = shapePoints.slice();
      if (shapePreview) { map.removeLayer(shapePreview); shapePreview = null; }
      drawnItems.clearLayers();   // remove the temporary vertex/preview artifacts
      shapePoints = [];
      setMode('none');
      if (bridge && bridge.onFillAreaComplete) {
        bridge.onFillAreaComplete(JSON.stringify(pts));
      }
    }

    // Undo helper — remove a custom-shape layer group by its id.
    function undoCustomShapeById(shapeId) {
      var group = shapeLayers[shapeId];
      if (!group) return false;
      try { map.removeLayer(group); } catch (e) {}
      delete shapeLayers[shapeId];
      return true;
    }

    // Load a shape from saved project
    function loadShape(shapeDef) {
      var pts = shapeDef.points || [];
      if (pts.length < 3) return;
      shapePoints = pts;
      // Rendering a saved shape must not notify Python (the feature already
      // exists in the project); suppress the bridge for this redraw.
      currentShape = Object.assign({}, shapeDef, { _suppressBridge: true });
      finishShape();
      shapePoints = [];
    }

    // Approximate polygon area in m² using the Shoelace formula
    function _polygonArea(pts) {
      if (pts.length < 3) return 0;
      // Convert to metres relative to first point
      var refLat = pts[0][0];
      var refLng = pts[0][1];
      var mPts = pts.map(function(p) {
        return [
          (p[1] - refLng) * 111320 * Math.cos(refLat * Math.PI / 180),
          (p[0] - refLat) * 111320
        ];
      });
      var area = 0;
      for (var i = 0; i < mPts.length; i++) {
        var j = (i + 1) % mPts.length;
        area += mPts[i][0] * mPts[j][1];
        area -= mPts[j][0] * mPts[i][1];
      }
      return Math.abs(area / 2);
    }

    // Utility: shift a hex colour's hue slightly
    function shiftColor(hex, amount) {
      var r = parseInt(hex.slice(1,3), 16);
      var g = parseInt(hex.slice(3,5), 16);
      var b = parseInt(hex.slice(5,7), 16);
      r = Math.min(255, r + amount);
      g = Math.max(0, g - amount / 2);
      return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
    }

    // Polyculture placement now goes through placePlantMarker — see
    // src/app.py:_on_polyculture_click. (The old SVG-batch path lived here.)
    // ── Mode control (called from Python) ────────────────────────────────────
    function setMode(mode, data) {
      currentMode  = mode;
      currentPlant = null;
      currentStructure = null;
      currentHedgerow  = null;
      currentShape     = null;
      // Starting any tool ends an in-progress outline edit so its vertex
      // handles (added to the map, not the shape group) don't orphan.
      if (shapeEditId !== null) exitShapeEditMode();

      switch (mode) {
        case 'boundary':
          map.getContainer().style.cursor = 'crosshair';
          drawingPolygon = false;
          polygonPoints  = [];
          drawnItems.clearLayers();
          break;
        case 'plant':
          currentPlant = data || null;
          // 'crosshair' (not 'cell') — 'cell' degrades to a small green box on
          // some QtWebEngine/Chromium builds; matches every other tool's cursor.
          map.getContainer().style.cursor = 'crosshair';
          _resetPatternState();
          break;
        case 'measure':
          map.getContainer().style.cursor = 'crosshair';
          break;
        case 'annotate':
          map.getContainer().style.cursor = 'text';
          break;
        case 'select':
          // Box-select mode: a plain drag draws the marquee (see _marqueeOnDown),
          // no Shift needed. A crosshair signals "drag to select".
          map.getContainer().style.cursor = 'crosshair';
          drawingPolygon = false;
          polygonPoints  = [];
          break;
        case 'structure':
          currentStructure = data || null;
          map.getContainer().style.cursor = 'crosshair';
          break;
        case 'polyculture':
          // Single plant-community drop. No JS-side placement — the bridge
          // map_clicked → _on_polyculture_click does it. A real mode (NOT
          // 'none') so a click on a boundary/shape forwards to onMapClick
          // instead of entering edit mode. setMode already cleared
          // currentStructure/currentPlant above, so no stray tree is dropped.
          map.getContainer().style.cursor = 'crosshair';
          break;
        case 'hedgerow':
          currentHedgerow = data || null;
          hedgerowPoints = [];
          map.getContainer().style.cursor = 'crosshair';
          break;
        case 'shape':
          currentShape = data || null;
          shapePoints = [];
          map.getContainer().style.cursor = 'crosshair';
          break;
        case 'fill':
          // Draw-then-fill (F3): reuse the shape polygon drawing, but finish via
          // finishFillArea() → onFillAreaComplete (scatters plants, makes no shape).
          currentShape = {stroke_color: '#66bb6a', fill_color: '#66bb6a',
                          fill_opacity: 0.12, _fillMode: true};
          shapePoints = [];
          map.getContainer().style.cursor = 'crosshair';
          break;
        case 'contour':
          currentContour = data || null;
          contourPoints = [];
          map.getContainer().style.cursor = 'crosshair';
          break;
        case 'sun_anchor':
          map.getContainer().style.cursor = 'crosshair';
          _anchorPreviewMarker = L.circleMarker(map.getCenter(), {
            radius: 7, color: '#ffb300', fillColor: '#fff', fillOpacity: 0.8,
            weight: 2, interactive: false, dashArray: '4 3'
          }).addTo(map);
          break;
        case 'terrain_rect':
          map.getContainer().style.cursor = 'crosshair';
          _terrainRectStart = null;
          if (_terrainRectPreview) {
            map.removeLayer(_terrainRectPreview);
            _terrainRectPreview = null;
          }
          break;
        default:
          map.getContainer().style.cursor = '';
          if (polygonPolyline) { map.removeLayer(polygonPolyline); polygonPolyline = null; }
          if (polygonPreview)  { map.removeLayer(polygonPreview);  polygonPreview  = null; }
          if (hedgerowPreview) { map.removeLayer(hedgerowPreview); hedgerowPreview = null; }
          if (shapePreview)    { map.removeLayer(shapePreview);    shapePreview    = null; }
          if (contourPreview)  { map.removeLayer(contourPreview);  contourPreview  = null; }
          if (_anchorPreviewMarker) { map.removeLayer(_anchorPreviewMarker); _anchorPreviewMarker = null; }
          if (_terrainRectPreview) { map.removeLayer(_terrainRectPreview); _terrainRectPreview = null; }
          _terrainRectStart = null;
          drawingPolygon = false;
          polygonPoints  = [];
          hedgerowPoints = [];
          shapePoints    = [];
          contourPoints  = [];
          _resetPatternState();
          drawnItems.clearLayers();
      }
      // Keep the placement crosshair over interactive layers (boundaries,
      // shapes, …) instead of Leaflet's default pointer, so hovering a
      // boundary while placing still reads as "click to place here". Idle
      // mode (no crosshair) keeps the pointer as an edit affordance.
      var _container = map.getContainer();
      if (_container.style.cursor === 'crosshair') _container.classList.add('placing');
      else _container.classList.remove('placing');
    }

    // ── Satellite imagery alignment nudge ──────────────────────────────────
    // Esri World Imagery is often georegistered a few metres off from OSM /
    // ground truth. This shifts ONLY the satellite tiles (a pane margin, which
    // Leaflet leaves alone) so the user can line the imagery up with OSM
    // buildings and their placements. It never moves any data.
    var satOffset = { east: 0, north: 0 };   // metres; +east, +north

    function _applySatOffset() {
      var pane = map.getPane('satellitePane');
      if (!pane) return;
      if (!satOffset.east && !satOffset.north) {
        pane.style.marginLeft = '0px';
        pane.style.marginTop = '0px';
        return;
      }
      // Metres per pixel at the current zoom/latitude (Web Mercator).
      var lat = map.getCenter().lat;
      var mPerPx = 40075016.686 * Math.abs(Math.cos(lat * Math.PI / 180)) /
                   Math.pow(2, map.getZoom() + 8);
      pane.style.marginLeft = (satOffset.east / mPerPx) + 'px';
      pane.style.marginTop = (-satOffset.north / mPerPx) + 'px';   // screen y is down
    }

    function setSatelliteOffset(east, north) {
      satOffset.east = +east || 0;
      satOffset.north = +north || 0;
      _applySatOffset();
    }

    // ── Adaptive satellite detail ("enlarge past coverage") ─────────────────
    // Esri World Imagery's real depth varies by area (some residential blocks
    // stop at ~z20). Rather than statically capping detail or showing Esri's
    // "Map Data Unavailable" placeholder, we probe Esri's tilemap for the
    // deepest available zoom over the current view and set that as the layer's
    // maxNativeZoom. Below it: real, full-detail tiles. Above it: Leaflet
    // upscales the deepest real tile (the "screenshot" enlarge). Probes are
    // debounced + cached per coarse area, and degrade safely to z19 (globally
    // present) if the network/CORS blocks them — so we never regress to the
    // placeholder.
    var _ESRI_TILEMAP =
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tilemap/';
    var _SAT_MIN_NATIVE = 19;   // fallback when the probe can't run (network/CORS)
    var _SAT_FLOOR      = 16;   // imagery is essentially always present at/below this
    var _SAT_MAX_NATIVE = 23;   // deepest Esri ever caches
    var _satNativeCache = {};    // coarse-tile key -> deepest native zoom
    var _satProbeTimer = null;

    function _tileXY(lat, lng, z) {
      var n = Math.pow(2, z);
      var latRad = lat * Math.PI / 180;
      return {
        x: Math.floor((lng + 180) / 360 * n),
        y: Math.floor((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) /
                       Math.PI) / 2 * n)
      };
    }

    // Is a single Esri tile real (cached) at (z,x,y)? cb(true|false|null);
    // null means the probe itself failed (network/CORS/timeout).
    function _probeTile(z, x, y, cb) {
      var url = _ESRI_TILEMAP + z + '/' + y + '/' + x + '/1/1?f=json';
      var done = false;
      var to = setTimeout(function () {
        if (!done) { done = true; cb(null); }
      }, 4000);
      fetch(url)
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) {
          if (done) return;
          done = true; clearTimeout(to);
          cb(!!(j && j.data && j.data[0] === 1));
        })
        .catch(function () {
          if (done) return;
          done = true; clearTimeout(to); cb(null);
        });
    }

    // Climb from _SAT_FLOOR upward until a tile is missing; the last present
    // zoom is the deepest real detail here. Crucially the answer may fall BELOW
    // _SAT_MIN_NATIVE (19): over rural areas like Lumsden, Esri's imagery is
    // shallow, and if we left maxNativeZoom at 19 the z18-19 tiles render Esri's
    // "Map data not yet available" placeholder instead of upscaling the deepest
    // real tile. Probing from the floor lets us cap at the true depth (e.g. 17)
    // so Leaflet enlarges real imagery. Deep urban areas (Edmonton) still climb
    // to 23 unchanged. If the probe itself fails (network/CORS) we keep the old
    // safe default of 19.
    function _probeMaxNative(lat, lng, cb) {
      var best = null;
      (function step(z) {
        if (z > _SAT_MAX_NATIVE) { cb(best === null ? _SAT_MIN_NATIVE : best); return; }
        var t = _tileXY(lat, lng, z);
        _probeTile(z, t.x, t.y, function (avail) {
          if (avail === true) { best = z; step(z + 1); return; }
          if (avail === false) {                 // first gap → deepest real is best
            cb(best === null ? Math.max(_SAT_FLOOR, z - 1) : best);
          } else {                               // probe failed → old safe default
            cb(best === null ? _SAT_MIN_NATIVE : best);
          }
        });
      })(_SAT_FLOOR);
    }

    function _setSatNative(z) {
      if (!satelliteLayer || satelliteLayer.options.maxNativeZoom === z) return;
      satelliteLayer.options.maxNativeZoom = z;
      // Re-add (public API) so the new clamp takes effect; the pane + its
      // alignment margin persist across this.
      if (map.hasLayer(satelliteLayer)) {
        satelliteLayer.remove();
        satelliteLayer.addTo(map);
      }
    }

    function _refreshSatNativeZoom() {
      if (!_satVisible || !satelliteLayer) return;
      if (map.getZoom() < 17) return;           // detail only matters up close
      var c = map.getCenter();
      var k = _tileXY(c.lat, c.lng, 13);          // coarse area key (~z13 tile)
      var ck = k.x + '_' + k.y;
      if (_satNativeCache[ck] !== undefined) {
        _setSatNative(_satNativeCache[ck]);
        return;
      }
      _probeMaxNative(c.lat, c.lng, function (maxN) {
        _satNativeCache[ck] = maxN;
        _setSatNative(maxN);
      });
    }

    function _scheduleSatProbe() {
      if (!_satVisible) return;
      if (_satProbeTimer) clearTimeout(_satProbeTimer);
      _satProbeTimer = setTimeout(_refreshSatNativeZoom, 400);
    }

    // ── Layer visibility ──────────────────────────────────────────────────────
    var _satVisible = false;

    function _updateSatLayer() {
      if (!_satVisible) return;
      var z = map.getZoom();
      if (mapboxSat && z >= 23) {
        if (!map.hasLayer(mapboxSat))    { mapboxSat.addTo(map); }
        if (map.hasLayer(satelliteLayer)) { satelliteLayer.remove(); }
      } else {
        if (!map.hasLayer(satelliteLayer)) { satelliteLayer.addTo(map); }
        if (mapboxSat && map.hasLayer(mapboxSat)) { mapboxSat.remove(); }
      }
    }

    function initMapboxLayer(token) {
      if (mapboxSat) { map.removeLayer(mapboxSat); }
      mapboxSat = L.tileLayer(
        'https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{z}/{x}/{y}?access_token=' + token,
        { tileSize: 512, zoomOffset: -1, maxNativeZoom: 22, maxZoom: 22,
          attribution: '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }
      );
      map.on('zoomend', _updateSatLayer);
      _updateSatLayer();
    }

    function setSatelliteVisible(visible) {
      _satVisible = visible;
      if (visible) {
        osmLayer.remove();
        _updateSatLayer();
        _scheduleSatProbe();    // learn this area's deepest real detail
      } else {
        osmLayer.addTo(map);
        satelliteLayer.remove();
        if (mapboxSat) { mapboxSat.remove(); }
      }
    }

    function setBoundaryVisible(visible) {
      boundaries.forEach(function(b) {
        if (visible) {
          b.layer.addTo(map);
          if (b.labelsLayer) b.labelsLayer.addTo(map);
          if (b.areaLabel)   b.areaLabel.addTo(map);
        } else {
          map.removeLayer(b.layer);
          if (b.labelsLayer) map.removeLayer(b.labelsLayer);
          if (b.areaLabel)   map.removeLayer(b.areaLabel);
        }
      });
    }

    function setPlantsVisible(visible) {
      if (visible) {
        plantLayerGroup.addTo(map);
      } else {
        map.removeLayer(plantLayerGroup);
      }
      // Existing trees now live with the plants (V2.26): a tree IS a plant,
      // so it toggles here, not with Structures. Buildings stay under
      // Structures (see map_js.set_structures_visible, which skips trees).
      Object.keys(structureMarkers).forEach(function(sid) {
        var g = structureMarkers[sid];
        if (!g._pdStruct || g._pdStruct.structId !== 'existing_tree') return;
        if (visible) g.addTo(map); else map.removeLayer(g);
      });
    }

    // ── Project load/clear ────────────────────────────────────────────────────
    function clearAll() {
      if (boundaryEditId !== null) exitBoundaryEditMode();
      if (shapeEditId !== null) exitShapeEditMode();
      boundaries.forEach(function(b) {
        map.removeLayer(b.layer);
        if (b.labelsLayer) map.removeLayer(b.labelsLayer);
        if (b.areaLabel)   map.removeLayer(b.areaLabel);
      });
      boundaries = [];
      plantLayerGroup.clearLayers();
      plantMarkers = {};
      Object.values(plantLabels).forEach(function(l) { map.removeLayer(l); });
      plantLabels = {};
      Object.values(structureMarkers).forEach(function(g) { map.removeLayer(g); });
      structureMarkers = {};
      Object.values(hedgerowLayers).forEach(function(g) { map.removeLayer(g); });
      hedgerowLayers = {};
      Object.values(shapeLayers).forEach(function(g) { map.removeLayer(g); });
      shapeLayers = {};
      clearSunPath();
      clearContours();
      clearAutoTerrain();
      clearWindOverlay();
      clearShadeZones();
      clearSitePin(false);
      drawnItems.clearLayers();
    }

    function loadBoundary(dataJson, fit) {
      // dataJson: JSON string of {id, points, color, showLengths, showArea}
      // or legacy: JSON string of [[lat,lng],...] (old single-boundary format)
      // fit (default true): recenter the map on the boundary. Undo/redo
      // re-renders pass false so the camera doesn't jump on every Ctrl+Z.
      var data = JSON.parse(dataJson);
      var pts, bid, color, showLengths, showArea;
      if (Array.isArray(data)) {
        // Legacy format
        pts = data; bid = _makeBoundaryId(); color = 'green';
        showLengths = true; showArea = true;
      } else {
        pts = data.points; bid = data.id || _makeBoundaryId();
        color = data.color || 'green';
        showLengths = data.showLengths !== false;
        showArea    = data.showArea !== false;
      }
      var entry = _addBoundaryToMap(bid, pts, color, showLengths, showArea);
      if (fit !== false) map.fitBounds(entry.layer.getBounds());
    }

    function loadPlantMarker(plantId, commonName, lat, lng, spacingM, plantType, customColor, groupId, communityId) {
      placePlantMarker(plantId, commonName, lat, lng, spacingM, plantType, customColor || null, groupId || null, communityId || null);
    }

    function setView(lat, lng, zoom) {
      map.setView([lat, lng], zoom || 14);
    }

    // Frame a lat/lng box with padding (V2.13). Used by the On This Design
    // list to zoom to one species' placements or a community instance.
    function fitMapBounds(south, west, north, east) {
      map.fitBounds([[south, west], [north, east]],
                    { padding: [40, 40], maxZoom: 21 });
    }

    function cancelDraw() {
      setMode('none');
    }

    // ── Zoom sensitivity ──────────────────────────────────────────────────────
    var _ZOOM_DELTAS = { fine: 0.15, normal: 0.33, fast: 0.58, coarse: 1.0 };
    function setZoomSensitivity(level) {
      _zoomSensitivity = level;
      var delta = _ZOOM_DELTAS[level] || 0.15;
      map.options.zoomDelta = delta;
      map.options.zoomSnap  = Math.min(delta, 0.5);
    }

