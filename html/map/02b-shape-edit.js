// html/map/02b-shape-edit.js — a shape's outline, dragged corner by corner (footprint edit mode).
//
// Moved out of 02-boundary.js in V3.11, unchanged, to make room there for the
// boundary's corner-handle switch and its name (F216, F217). It lived there
// because it reuses the boundary's vertex-drag pattern; it edits shapes
// (imported buildings, drawn footprints), not boundaries. Loaded straight
// after 02-boundary.js, so the scripts run in the order they always did.
//
// CLASSIC script, not an ES module: the shared-global model of html/map/*.js
// (see the header of 01-core.js). Cross-file calls resolve at call time.
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
        '<span style="color:#b0bec5;font-size:12px">Area: ' + escH(aStr)
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
