// html/map/02-boundary.js — boundary drawing/editing, length labels, multi-boundary helpers, footprint outline editing.
//
// Split from the former single map.html <script> (V1.64). These are
// CLASSIC scripts loaded sequentially by map.html — NOT ES modules —
// so the shared-global execution model (and order) is byte-for-byte
// what the monolith had; ES modules can't load from file:// in
// Chromium without CORS flags. Cross-file calls resolve at call time
// through the shared global scope. The Python↔JS contract over these
// globals is pinned by tests/test_map_js.py + tests/test_bridge_contract.py.
    // ── Boundary drawing (manual polygon) ────────────────────────────────────
    function handleBoundaryClick(lat, lng) {
      // If clicking near the first point, close the polygon
      if (polygonPoints.length >= 3) {
        var first = polygonPoints[0];
        var firstPx = map.latLngToContainerPoint(L.latLng(first));
        var clickPx = map.latLngToContainerPoint(L.latLng(lat, lng));
        var dist = Math.sqrt(Math.pow(firstPx.x - clickPx.x, 2) + Math.pow(firstPx.y - clickPx.y, 2));
        if (dist < 12) {
          finishBoundaryPolygon();
          return;
        }
      }

      polygonPoints.push([lat, lng]);
      drawingPolygon = true;
      refreshPolygonPolyline();
    }

    function refreshPolygonPolyline() {
      if (polygonPolyline) { map.removeLayer(polygonPolyline); }
      if (polygonPoints.length >= 2) {
        polygonPolyline = L.polyline(polygonPoints, {
          color: '#66bb6a', weight: 2, dashArray: '6 4', opacity: 0.9
        }).addTo(map);
      }
      // Draw a circle on first point so user knows they can close it
      if (polygonPoints.length === 1) {
        L.circleMarker(polygonPoints[0], {
          radius: 6, color: '#66bb6a', fillColor: '#66bb6a', fillOpacity: 0.7
        }).addTo(drawnItems);
      }
    }

    function updatePolygonPreview(latlng) {
      if (polygonPreview) { map.removeLayer(polygonPreview); }
      var pts = polygonPoints.concat([[latlng.lat, latlng.lng]]);
      polygonPreview = L.polyline(pts, {
        color: '#66bb6a', weight: 2, dashArray: '4 4', opacity: 0.5
      }).addTo(map);
    }

    // ── Boundary length labels ────────────────────────────────────────────────
    function haversineMeters(a, b) {
      var R = 6371000;
      var dLat = (b[0] - a[0]) * Math.PI / 180;
      var dLng = (b[1] - a[1]) * Math.PI / 180;
      var lat1 = a[0] * Math.PI / 180;
      var lat2 = b[0] * Math.PI / 180;
      var x = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng/2) * Math.sin(dLng/2);
      return R * 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
    }

    function addBoundaryLengthLabels(points) {
      // Legacy stub — used only during loadBoundary; real implementation is _makeBoundaryLengthLabels
      return _makeBoundaryLengthLabels(points, BOUNDARY_COLORS['green'].stroke);
    }

    function calcPolygonAreaM2(points) {
      // Shoelace on projected metre coords relative to centroid
      var n = points.length;
      if (n < 3) return 0;
      var R = 6371000;
      var lat0 = 0, lng0 = 0;
      for (var k = 0; k < n; k++) { lat0 += points[k][0]; lng0 += points[k][1]; }
      lat0 /= n; lng0 /= n;
      var cosLat = Math.cos(lat0 * Math.PI / 180);
      var proj = points.map(function(p) {
        return [
          (p[0] - lat0) * Math.PI / 180 * R,
          (p[1] - lng0) * Math.PI / 180 * R * cosLat
        ];
      });
      var area = 0;
      for (var i = 0; i < n; i++) {
        var j = (i + 1) % n;
        area += proj[i][1] * proj[j][0];
        area -= proj[j][1] * proj[i][0];
      }
      return Math.abs(area) / 2;
    }

    var _AREA_UNITS = ['m²', 'ha', 'ac', 'km²'];
    function _fmtArea(m2, unit) {
      if (unit === 1) return (m2 / 10000).toFixed(3) + ' ha';
      if (unit === 2) return (m2 / 4046.86).toFixed(3) + ' ac';
      if (unit === 3) return (m2 / 1e6).toFixed(4) + ' km²';
      return (m2 >= 10 ? Math.round(m2) : m2.toFixed(1)) + ' m²';
    }

    function addBoundaryAreaLabel(points) {
      // Legacy stub — used only during loadBoundary
      return _makeBoundaryAreaLabel(points);
    }

    function _makeBoundaryId() {
      return 'b' + Date.now() + Math.random().toString(36).slice(2, 6);
    }

    function finishBoundaryPolygon() {
      if (polygonPoints.length < 3) return;

      // Cleanup drawing helpers
      if (polygonPolyline) { map.removeLayer(polygonPolyline); polygonPolyline = null; }
      if (polygonPreview)  { map.removeLayer(polygonPreview);  polygonPreview  = null; }
      drawnItems.clearLayers();

      var bid   = _makeBoundaryId();
      var color = _nextBoundaryColor();
      _addBoundaryToMap(bid, polygonPoints, color, true, true);

      // Zoom to fit the drawn boundary
      var bEntry = _getBoundaryEntry(bid);
      if (bEntry && bEntry.layer) {
        map.fitBounds(bEntry.layer.getBounds(), { padding: [30, 30] });
      }

      // Notify Python
      if (bridge) {
        bridge.onBoundaryComplete(bid, JSON.stringify(polygonPoints), color);
      }

      drawingPolygon = false;
      polygonPoints  = [];
      setMode('none');
    }

    // ── Multi-boundary helpers ────────────────────────────────────────────────

    function _getBoundaryEntry(id) {
      for (var i = 0; i < boundaries.length; i++) {
        if (boundaries[i].id === id) return boundaries[i];
      }
      return null;
    }

    function _addBoundaryToMap(id, pts, colorName, showLengths, showArea) {
      var c = BOUNDARY_COLORS[colorName] || BOUNDARY_COLORS['green'];
      var layer = L.polygon(pts, {
        color: c.stroke, weight: 2,
        fillColor: c.fill, fillOpacity: 0.18,
        interactive: true
      }).addTo(map);

      var labelsLayer = showLengths ? _makeBoundaryLengthLabels(pts, c.stroke) : null;
      var areaLabel   = showArea   ? _makeBoundaryAreaLabel(pts)              : null;

      var entry = {
        id: id, layer: layer, labelsLayer: labelsLayer, areaLabel: areaLabel,
        points: pts, color: colorName, showLengths: showLengths, showArea: showArea
      };
      boundaries.push(entry);

      // Click → enter edit mode (or toggle selection on shift/cmd+click).
      // In a placement mode, forward to onMapClick so the user can place on
      // top of a visible boundary. Leaflet 1.9.4 makes the polygon the event
      // target and does NOT fire the map's own click for it, so we have to
      // run onMapClick ourselves (the layer event carries e.latlng).
      layer.on('click', function(e) {
        var oe = e.originalEvent;
        if (oe && (oe.shiftKey || oe.ctrlKey || oe.metaKey)) {
          L.DomEvent.stop(e);
          toggleSelection({ kind: 'boundary', boundaryId: id });
          return;
        }
        if (currentMode === 'none') {
          L.DomEvent.stop(e);
          enterBoundaryEditMode(id);
          return;
        }
        onMapClick(e);   // placement/draw mode → place on top of the boundary
      });

      // Right-click → context menu
      layer.on('contextmenu', function(e) {
        L.DomEvent.stop(e);
        _showBoundaryContextMenu(e.originalEvent.clientX, e.originalEvent.clientY, id);
      });

      return entry;
    }

    function _removeBoundaryEntry(id) {
      for (var i = 0; i < boundaries.length; i++) {
        if (boundaries[i].id === id) {
          var b = boundaries[i];
          map.removeLayer(b.layer);
          if (b.labelsLayer) map.removeLayer(b.labelsLayer);
          if (b.areaLabel)   map.removeLayer(b.areaLabel);
          boundaries.splice(i, 1);
          return;
        }
      }
    }

    function _refreshBoundaryLabels(id) {
      var b = _getBoundaryEntry(id);
      if (!b) return;
      var c = BOUNDARY_COLORS[b.color] || BOUNDARY_COLORS['green'];
      if (b.labelsLayer) { map.removeLayer(b.labelsLayer); b.labelsLayer = null; }
      if (b.areaLabel)   { map.removeLayer(b.areaLabel);   b.areaLabel   = null; }
      if (b.showLengths) b.labelsLayer = _makeBoundaryLengthLabels(b.points, c.stroke);
      if (b.showArea)    b.areaLabel   = _makeBoundaryAreaLabel(b.points);
    }

    function _showBoundaryContextMenu(x, y, id) {
      var b = _getBoundaryEntry(id);
      if (!b) return;
      var items = [
        {
          label: 'Edge Labels',
          checked: b.showLengths,
          action: function() {
            b.showLengths = !b.showLengths;
            _refreshBoundaryLabels(id);
            if (bridge) bridge.onBoundaryPropsChanged(id, b.color, b.showLengths, b.showArea);
          }
        },
        {
          label: 'Area Label',
          checked: b.showArea,
          action: function() {
            b.showArea = !b.showArea;
            _refreshBoundaryLabels(id);
            if (bridge) bridge.onBoundaryPropsChanged(id, b.color, b.showLengths, b.showArea);
          }
        },
        'sep',
        { label: 'Color:', action: function() {} }
      ];
      items._colorTarget = b.color;
      items._colorAction = function(newColor) {
        _setBoundaryColor(id, newColor);
      };
      items.push('sep');
      items.push({
        label: 'Remove Boundary',
        action: function() {
          if (boundaryEditId === id) exitBoundaryEditMode();
          _removeBoundaryEntry(id);
          if (bridge) bridge.onBoundaryRemoved(id);
        }
      });
      showContextMenu(x, y, items);
    }

    function _setBoundaryColor(id, newColor) {
      var b = _getBoundaryEntry(id);
      if (!b) return;
      b.color = newColor;
      var c = BOUNDARY_COLORS[newColor] || BOUNDARY_COLORS['green'];
      b.layer.setStyle({ color: c.stroke, fillColor: c.fill });
      _refreshBoundaryLabels(id);
      if (bridge) bridge.onBoundaryPropsChanged(id, newColor, b.showLengths, b.showArea);
    }

    // ── Boundary label factories (use fresh layer groups each time) ───────────
    function _makeBoundaryLengthLabels(points, strokeColor) {
      var lg = L.layerGroup().addTo(map);
      var n = points.length;
      for (var i = 0; i < n; i++) {
        var a = points[i];
        var b = points[(i + 1) % n];
        var midLat = (a[0] + b[0]) / 2;
        var midLng = (a[1] + b[1]) / 2;
        var dist = haversineMeters(a, b);
        var label = dist >= 10 ? Math.round(dist) + ' m' : dist.toFixed(1) + ' m';
        L.marker([midLat, midLng], {
          icon: L.divIcon({
            className: '',
            html: '<div style="background:rgba(255,255,255,0.88);border:1px solid ' + escH(strokeColor) + ';border-radius:3px;padding:1px 6px;font-size:11px;font-weight:600;color:#1b5e20;white-space:nowrap;pointer-events:none;">' + escH(label) + '</div>',
            iconSize: null, iconAnchor: null
          }),
          interactive: false
        }).addTo(lg);
      }
      return lg;
    }

    function _makeBoundaryAreaLabel(points) {
      if (!points || points.length < 3) return null;
      var areaM2 = calcPolygonAreaM2(points);
      var clat = 0, clng = 0;
      for (var i = 0; i < points.length; i++) { clat += points[i][0]; clng += points[i][1]; }
      clat /= points.length; clng /= points.length;

      var txt = _fmtArea(areaM2, boundaryAreaUnit);
      var icon = L.divIcon({
        className: '',
        html: '<div style="background:rgba(255,255,255,0.92);border:1.5px solid #388e3c;border-radius:4px;padding:3px 9px;font-size:12px;font-weight:700;color:#1b5e20;white-space:nowrap;cursor:pointer;user-select:none;">⬡ ' + escH(txt) + '</div>',
        iconSize: null, iconAnchor: null
      });
      var marker = L.marker([clat, clng], { icon: icon, interactive: true }).addTo(map);
      marker.on('click', function() {
        boundaryAreaUnit = (boundaryAreaUnit + 1) % 4;
        // Refresh all area labels
        boundaries.forEach(function(b) {
          if (b.showArea && b.areaLabel) {
            map.removeLayer(b.areaLabel);
            b.areaLabel = _makeBoundaryAreaLabel(b.points);
          }
        });
      });
      return marker;
    }

    // ── Boundary edit mode ────────────────────────────────────────────────────

    function enterBoundaryEditMode(id) {
      if (shapeEditId !== null) exitShapeEditMode();
      if (boundaryEditId !== null) exitBoundaryEditMode();
      var b = _getBoundaryEntry(id);
      if (!b) return;
      boundaryEditId = id;
      map.getContainer().style.cursor = 'move';

      // Vertex handles
      b.points.forEach(function(pt, idx) {
        var h = L.circleMarker([pt[0], pt[1]], {
          radius: 7, color: '#fff', fillColor: '#1565c0', fillOpacity: 1,
          weight: 2, interactive: true, draggable: false
        }).addTo(map);
        _makeVertexDraggable(h, id, idx);
        boundaryEditHandles.push(h);
      });

      // Bounding-box corner handles for uniform scale
      _refreshBboxHandles(id);

      // Drag on polygon interior → translate whole polygon
      b.layer.on('mousedown', _onBoundaryPolyMousedown);
    }

    function _makeVertexDraggable(marker, bid, idx) {
      var isDragging = false, startX, startY, startLatLng;

      marker.on('mousedown', function(e) {
        L.DomEvent.stop(e);
        isDragging = true;
        startLatLng = marker.getLatLng();
        map.dragging.disable();

        function onMove(ev) {
          if (!isDragging) return;
          var ll = map.containerPointToLatLng([ev.clientX, ev.clientY]);
          marker.setLatLng(ll);
          var b = _getBoundaryEntry(bid);
          if (!b) return;
          b.points[idx] = [ll.lat, ll.lng];
          b.layer.setLatLngs(b.points);
          _refreshBoundaryLabels(bid);
          _refreshBboxHandles(bid);
        }
        function onUp() {
          isDragging = false;
          map.dragging.enable();
          document.removeEventListener('mousemove', onMove);
          document.removeEventListener('mouseup', onUp);
          var b = _getBoundaryEntry(bid);
          if (b && bridge) bridge.onBoundaryGeomChanged(bid, JSON.stringify(b.points));
        }
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
      });
    }

    function _refreshBboxHandles(id) {
      boundaryBboxHandles.forEach(function(h) { map.removeLayer(h); });
      boundaryBboxHandles = [];
      var b = _getBoundaryEntry(id);
      if (!b) return;

      var lats = b.points.map(function(p) { return p[0]; });
      var lngs = b.points.map(function(p) { return p[1]; });
      var minLat = Math.min.apply(null, lats), maxLat = Math.max.apply(null, lats);
      var minLng = Math.min.apply(null, lngs), maxLng = Math.max.apply(null, lngs);
      var corners = [
        [minLat, minLng], [minLat, maxLng],
        [maxLat, maxLng], [maxLat, minLng]
      ];
      var cLat = (minLat + maxLat) / 2, cLng = (minLng + maxLng) / 2;

      corners.forEach(function(corner, ci) {
        var h = L.circleMarker(corner, {
          radius: 6, color: '#fff', fillColor: '#f57c00', fillOpacity: 1,
          weight: 2, interactive: true
        }).addTo(map);
        _makeScaleDraggable(h, id, ci, cLat, cLng, minLat, maxLat, minLng, maxLng);
        boundaryBboxHandles.push(h);
      });
    }

    function _makeScaleDraggable(handle, bid, cornerIdx, cLat, cLng, minLat, maxLat, minLng, maxLng) {
      handle.on('mousedown', function(e) {
        L.DomEvent.stop(e);
        var b = _getBoundaryEntry(bid);
        if (!b) return;
        var origPts = b.points.map(function(p) { return [p[0], p[1]]; });
        var origDiag = Math.sqrt(Math.pow(maxLat - minLat, 2) + Math.pow(maxLng - minLng, 2));
        map.dragging.disable();

        function onMove(ev) {
          var ll = map.containerPointToLatLng([ev.clientX, ev.clientY]);
          var dx = ll.lat - cLat, dy = ll.lng - cLng;
          var newDiag = Math.sqrt(dx * dx + dy * dy) * 2;
          var scale = origDiag > 0 ? newDiag / origDiag : 1;
          var b2 = _getBoundaryEntry(bid);
          if (!b2) return;
          b2.points = origPts.map(function(p) {
            return [cLat + (p[0] - cLat) * scale, cLng + (p[1] - cLng) * scale];
          });
          b2.layer.setLatLngs(b2.points);
          _refreshBoundaryLabels(bid);
          _refreshBboxHandles(bid);
          // Reposition vertex handles
          boundaryEditHandles.forEach(function(vh, vi) {
            if (b2.points[vi]) vh.setLatLng(b2.points[vi]);
          });
        }
        function onUp() {
          map.dragging.enable();
          document.removeEventListener('mousemove', onMove);
          document.removeEventListener('mouseup', onUp);
          var b3 = _getBoundaryEntry(bid);
          if (b3 && bridge) bridge.onBoundaryGeomChanged(bid, JSON.stringify(b3.points));
        }
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
      });
    }

    function _onBoundaryPolyMousedown(e) {
      if (e.originalEvent.button !== 0) return;
      L.DomEvent.stop(e);
      var bid = boundaryEditId;
      var startLL = e.latlng;
      var b = _getBoundaryEntry(bid);
      if (!b) return;
      var origPts = b.points.map(function(p) { return [p[0], p[1]]; });
      map.dragging.disable();

      function onMove(ev) {
        var ll = map.containerPointToLatLng(map.mouseEventToContainerPoint(ev));
        var dLat = ll.lat - startLL.lat;
        var dLng = ll.lng - startLL.lng;
        var b2 = _getBoundaryEntry(bid);
        if (!b2) return;
        b2.points = origPts.map(function(p) { return [p[0] + dLat, p[1] + dLng]; });
        b2.layer.setLatLngs(b2.points);
        _refreshBoundaryLabels(bid);
        boundaryEditHandles.forEach(function(vh, vi) {
          if (b2.points[vi]) vh.setLatLng(b2.points[vi]);
        });
        _refreshBboxHandles(bid);
      }
      function onUp() {
        map.dragging.enable();
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        var b3 = _getBoundaryEntry(bid);
        if (b3 && bridge) bridge.onBoundaryGeomChanged(bid, JSON.stringify(b3.points));
      }
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    }

    function exitBoundaryEditMode() {
      if (boundaryEditId === null) return;
      var b = _getBoundaryEntry(boundaryEditId);
      if (b) b.layer.off('mousedown', _onBoundaryPolyMousedown);
      boundaryEditHandles.forEach(function(h) { map.removeLayer(h); });
      boundaryEditHandles = [];
      boundaryBboxHandles.forEach(function(h) { map.removeLayer(h); });
      boundaryBboxHandles = [];
      boundaryEditId = null;
      map.getContainer().style.cursor = '';
    }


    // ── Shape (footprint) outline edit mode ───────────────────────────────────
    // Reuses the boundary vertex-drag pattern so imported OSM building outlines
    // (and any drawn canopy footprint) can be resized/reshaped to match reality.
    // Drag a vertex → the polygon updates and Python is told the new ring.
    var shapeEditId      = null;       // shape_id currently in outline-edit mode
    var shapeEditHandles = [];         // draggable vertex handle markers

    function _getShapePolygon(id) {
      var group = shapeLayers[id];
      if (!group) return null;
      var found = null;
      group.eachLayer(function(layer) {
        if (!found && layer instanceof L.Polygon) found = layer;
      });
      return found;
    }

    function enterShapeEditMode(id) {
      if (boundaryEditId !== null) exitBoundaryEditMode();
      if (shapeEditId !== null) exitShapeEditMode();
      var poly = _getShapePolygon(id);
      if (!poly || !poly._shape) return;
      shapeEditId = id;
      map.getContainer().style.cursor = 'move';
      poly._shape.points.forEach(function(pt, idx) {
        var h = L.circleMarker([pt[0], pt[1]], {
          radius: 7, color: '#fff', fillColor: '#5d4037', fillOpacity: 1,
          weight: 2, interactive: true
        }).addTo(map);
        _makeShapeVertexDraggable(h, id, idx);
        shapeEditHandles.push(h);
      });
      // Drag on the polygon interior → translate the whole outline (mirrors the
      // boundary edit). Vertex handles sit on top, so a grab on one still wins.
      poly.on('mousedown', _onShapePolyMousedown);
    }

    // Refresh a shape's stored area + on-map tooltip after its outline changes.
    function _refreshShapeReadout(poly) {
      if (!poly || !poly._shape) return;
      var sh = poly._shape;
      sh.areaM2 = _polygonArea(sh.points);
      if (!poly.getTooltip()) return;
      var cast = sh.heightM > 0;
      var aStr = sh.areaM2 < 10000 ? sh.areaM2.toFixed(1) + ' m²'
        : (sh.areaM2 / 10000).toFixed(2) + ' ha';
      var line = cast
        ? '<br>Casts shade — ' + escH(String(sh.heightM)) + ' m tall'
          + '<br>Click to edit outline · right-click for height/remove'
        : '<br>Click to edit outline · right-click to remove';
      poly.setTooltipContent(
        '<b>' + escH(sh.label || sh.shapeType) + '</b><br>' +
        '<span style="color:#78909c;font-size:10px">Area: ' + escH(aStr)
          + line + '</span>');
    }

    function _makeShapeVertexDraggable(marker, sid, idx) {
      marker.on('mousedown', function(e) {
        L.DomEvent.stop(e);
        map.dragging.disable();
        function onMove(ev) {
          var ll = map.containerPointToLatLng([ev.clientX, ev.clientY]);
          marker.setLatLng(ll);
          var poly = _getShapePolygon(sid);
          if (!poly || !poly._shape) return;
          poly._shape.points[idx] = [ll.lat, ll.lng];
          poly.setLatLngs(poly._shape.points);
        }
        function onUp() {
          map.dragging.enable();
          document.removeEventListener('mousemove', onMove);
          document.removeEventListener('mouseup', onUp);
          var poly = _getShapePolygon(sid);
          if (poly && poly._shape) {
            _refreshShapeReadout(poly);
            if (bridge) bridge.onShapeGeomChanged(sid, JSON.stringify(poly._shape.points));
          }
        }
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
      });
    }

    // Drag the whole outline (every vertex together), keyed on the shape in edit
    // mode. Mirrors _onBoundaryPolyMousedown.
    function _onShapePolyMousedown(e) {
      if (e.originalEvent.button !== 0) return;     // left-drag only
      if (shapeEditId === null) return;
      L.DomEvent.stop(e);
      var sid = shapeEditId;
      var startLL = e.latlng;
      var poly = _getShapePolygon(sid);
      if (!poly || !poly._shape) return;
      var origPts = poly._shape.points.map(function(p) { return [p[0], p[1]]; });
      map.dragging.disable();
      function onMove(ev) {
        var ll = map.containerPointToLatLng(map.mouseEventToContainerPoint(ev));
        var dLat = ll.lat - startLL.lat;
        var dLng = ll.lng - startLL.lng;
        var p2 = _getShapePolygon(sid);
        if (!p2 || !p2._shape) return;
        p2._shape.points = origPts.map(function(p) {
          return [p[0] + dLat, p[1] + dLng];
        });
        p2.setLatLngs(p2._shape.points);
        shapeEditHandles.forEach(function(vh, vi) {
          if (p2._shape.points[vi]) vh.setLatLng(p2._shape.points[vi]);
        });
      }
      function onUp() {
        map.dragging.enable();
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        var p3 = _getShapePolygon(sid);
        if (p3 && p3._shape) {
          _refreshShapeReadout(p3);
          if (bridge) bridge.onShapeGeomChanged(sid, JSON.stringify(p3._shape.points));
        }
      }
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    }

    function exitShapeEditMode() {
      if (shapeEditId === null) return;
      var poly = _getShapePolygon(shapeEditId);
      if (poly) poly.off('mousedown', _onShapePolyMousedown);
      shapeEditHandles.forEach(function(h) { map.removeLayer(h); });
      shapeEditHandles = [];
      shapeEditId = null;
      map.getContainer().style.cursor = '';
    }


