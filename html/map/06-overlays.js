// html/map/06-overlays.js — sun path, contours/terrain, shade overlays, wind, legend, site pin, QWebChannel bootstrap.
//
// Split from the former single map.html <script> (V1.64). These are
// CLASSIC scripts loaded sequentially by map.html — NOT ES modules —
// so the shared-global execution model (and order) is byte-for-byte
// what the monolith had; ES modules can't load from file:// in
// Chromium without CORS flags. Cross-file calls resolve at call time
// through the shared global scope. The Python↔JS contract over these
// globals is pinned by tests/test_map_js.py + tests/test_bridge_contract.py.
    // ── A1: Sun path / shadow overlay ──────────────────────────────────────
    var sunPathLayer   = null;   // L.layerGroup
    var _sunPathData   = null;   // last drawSunPath payload (for redraw on zoom)
    var _sunPathAnchor = null;   // {lat, lng}

    function _viewportRadiusMetres(lat) {
      // Returns a radius that is ~22% of the shorter viewport dimension, in metres.
      // This keeps the arc legible at any zoom level.
      var size = map.getSize();
      var pxRadius = Math.min(size.x, size.y) * 0.22;
      // Metres per pixel at current zoom and latitude
      var metersPerPx = 40075016.686 * Math.cos(lat * Math.PI / 180) / Math.pow(2, map.getZoom() + 8);
      return pxRadius * metersPerPx;
    }

    function drawSunPath(data, anchorLat, anchorLng) {
      clearSunPath();
      _sunPathData = data;
      sunPathLayer = L.layerGroup().addTo(map);

      var lat = (anchorLat !== undefined) ? anchorLat
              : (_sunPathAnchor ? _sunPathAnchor.lat : map.getCenter().lat);
      var lng = (anchorLng !== undefined) ? anchorLng
              : (_sunPathAnchor ? _sunPathAnchor.lng : map.getCenter().lng);
      if (anchorLat !== undefined) _sunPathAnchor = { lat: lat, lng: lng };

      var positions = data.positions || [];  // [{altitude, azimuth, hour}, ...]
      var dateLabel = data.date_label || '';
      var showShadows = data.show_shadows !== false;
      var showShadowLength = data.show_shadow_length || false;
      var sunriseHour = data.sunrise_hour || 6;
      var sunsetHour = data.sunset_hour || 18;

      if (positions.length < 2) return;

      // Arc radius: viewport-relative so arc is always legible regardless of zoom.
      // The user-supplied arc_radius (metres) is still honoured if explicitly provided
      // and larger than the auto value, giving them override capability.
      var autoRadius = _viewportRadiusMetres(lat);
      var arcRadius  = data.arc_radius ? Math.max(data.arc_radius, autoRadius * 0.5)
                                       : autoRadius;

      var arcPoints = [];
      var positionMap = {}; // index -> {ptLat, ptLng, pos}

      positions.forEach(function(pos, i) {
        if (pos.altitude < 0) return;
        var azRad = (pos.azimuth) * Math.PI / 180;
        var dist = arcRadius * (1 - pos.altitude / 90 * 0.3);
        var dLat = dist * Math.cos(azRad) / 111320;
        var dLng = dist * Math.sin(azRad) / (111320 * Math.cos(lat * Math.PI / 180));
        var ptLat = lat + dLat;
        var ptLng = lng + dLng;
        arcPoints.push([ptLat, ptLng]);
        positionMap[arcPoints.length - 1] = { ptLat: ptLat, ptLng: ptLng, pos: pos };
      });

      // Single polyline for the arc (replaces ~48 individual circleMarkers)
      if (arcPoints.length >= 2) {
        L.polyline(arcPoints, {
          color: '#ffb300',
          weight: 3,
          opacity: 0.8,
          interactive: false
        }).addTo(sunPathLayer);
      }

      // Only place markers at key times: sunrise, solar noon, sunset (~3 markers)
      positions.forEach(function(pos, i) {
        if (pos.altitude < 0) return;
        var isKey = Math.abs(pos.hour - sunriseHour) < 0.5 ||
                    Math.abs(pos.hour - 12) < 0.3 ||
                    Math.abs(pos.hour - sunsetHour) < 0.5;
        if (!isKey) return;

        var azRad = (pos.azimuth) * Math.PI / 180;
        var dist = arcRadius * (1 - pos.altitude / 90 * 0.3);
        var dLat = dist * Math.cos(azRad) / 111320;
        var dLng = dist * Math.sin(azRad) / (111320 * Math.cos(lat * Math.PI / 180));
        var ptLat = lat + dLat;
        var ptLng = lng + dLng;

        L.circleMarker([ptLat, ptLng], {
          radius: 5, color: '#ffb300', fillColor: '#ffb300',
          fillOpacity: 0.9, weight: 1.5, interactive: false
        }).addTo(sunPathLayer);

        var timeStr = Math.floor(pos.hour) + ':' + ('0' + Math.round((pos.hour % 1) * 60)).slice(-2);
        var altStr = pos.altitude.toFixed(0) + '°';
        var labelIcon = L.divIcon({
          className: 'measure-label',
          html: '<span style="font-size:10px">' + timeStr + ' ☀ ' + altStr + '</span>',
          iconSize: [0, 0],
          iconAnchor: [0, 14]
        });
        L.marker([ptLat, ptLng], { icon: labelIcon, interactive: false }).addTo(sunPathLayer);
      });

      // Shadow direction arrows at key times
      if (showShadows) {
        var shadowTimes = [
          { hour: sunriseHour + 1, label: 'Morning' },
          { hour: 12, label: 'Noon' },
          { hour: sunsetHour - 1, label: 'Evening' }
        ];
        shadowTimes.forEach(function(st) {
          var closest = null;
          var minDiff = 999;
          positions.forEach(function(p) {
            var diff = Math.abs(p.hour - st.hour);
            if (diff < minDiff && p.altitude > 0) { minDiff = diff; closest = p; }
          });
          if (!closest) return;

          // Shadow goes opposite to sun
          var shadowAz = (closest.azimuth + 180) % 360;
          var shadowRad = shadowAz * Math.PI / 180;
          var arrowLen = arcRadius * 0.5; // shadow arrow length proportional to arc
          if (showShadowLength && closest.altitude > 0) {
            arrowLen = Math.min(arcRadius, (arcRadius * 0.25) / Math.tan(closest.altitude * Math.PI / 180));
          }
          var dLat = arrowLen * Math.cos(shadowRad) / 111320;
          var dLng = arrowLen * Math.sin(shadowRad) / (111320 * Math.cos(lat * Math.PI / 180));

          // Draw shadow arrow
          var arrowLine = L.polyline(
            [[lat, lng], [lat + dLat, lng + dLng]],
            { color: '#455a64', weight: 3, opacity: 0.6, interactive: false }
          ).addTo(sunPathLayer);

          // Arrowhead
          var headLen = 8 / 111320;
          var headAngle = Math.PI / 6;
          var endLat = lat + dLat;
          var endLng = lng + dLng;
          var angle = Math.atan2(dLng, dLat);
          L.polyline([
            [endLat - headLen * Math.cos(angle - headAngle),
             endLng - headLen * Math.sin(angle - headAngle)],
            [endLat, endLng],
            [endLat - headLen * Math.cos(angle + headAngle),
             endLng - headLen * Math.sin(angle + headAngle)]
          ], { color: '#455a64', weight: 2.5, opacity: 0.6, interactive: false }).addTo(sunPathLayer);

          // Label
          var labelIcon = L.divIcon({
            className: 'structure-label',
            html: '<span style="font-size:10px">' + st.label + ' shadow</span>',
            iconSize: [0, 0],
            iconAnchor: [0, -4]
          });
          L.marker([lat + dLat, lng + dLng], { icon: labelIcon, interactive: false }).addTo(sunPathLayer);
        });
      }

      // Centre marker — interactive for right-click remove
      var centerMk = L.circleMarker([lat, lng], {
        radius: 6, color: '#ff6f00', fillColor: '#ffb300', fillOpacity: 1,
        weight: 2, interactive: true
      }).addTo(sunPathLayer);
      centerMk.bindTooltip('Sun path · right-click to remove · shift+click to select', { sticky: true, offset: [10, 0] });
      centerMk.on('click', function(e) {
        var oe = e.originalEvent;
        if (oe && (oe.shiftKey || oe.ctrlKey || oe.metaKey)) {
          L.DomEvent.stop(e);
          toggleSelection({ kind: 'sunpath' });
        }
      });
      centerMk.on('contextmenu', function(e) {
        L.DomEvent.stop(e);
        showContextMenu(e.originalEvent.clientX, e.originalEvent.clientY, [
          { label: 'Remove Sun Path', action: function() {
            clearSunPath();
            if (bridge) bridge.onSunPathRemoved();
          }}
        ]);
      });

      // Title label
      var titleIcon = L.divIcon({
        className: 'measure-label',
        html: '☀ ' + escH(dateLabel),
        iconSize: [0, 0],
        iconAnchor: [0, 24]
      });
      L.marker([lat, lng], { icon: titleIcon, interactive: false }).addTo(sunPathLayer);
    }

    function clearSunPath() {
      if (sunPathLayer) { map.removeLayer(sunPathLayer); sunPathLayer = null; }
      _sunPathData   = null;
      _sunPathAnchor = null;
    }

    // ── A3: Contour lines ───────────────────────────────────────────────────
    var contourLayers = [];  // array of L.layerGroup (one per contour line)

    // Contour drawing state
    var contourPoints  = [];
    var contourPreview = null;
    var currentContour = null;

    function handleContourClick(lat, lng) {
      contourPoints.push([lat, lng]);
      var color = currentContour ? currentContour.color : '#795548';
      L.circleMarker([lat, lng], {
        radius: 3, color: color, fillColor: color, fillOpacity: 1
      }).addTo(drawnItems);
      refreshContourPreview();
    }

    function refreshContourPreview() {
      if (contourPreview) { map.removeLayer(contourPreview); contourPreview = null; }
      if (contourPoints.length >= 2) {
        var color = currentContour ? currentContour.color : '#795548';
        contourPreview = L.polyline(contourPoints, {
          color: color, weight: 2, opacity: 0.6, dashArray: '6 4'
        }).addTo(map);
      }
    }

    function updateContourPreview(latlng) {
      if (contourPreview) { map.removeLayer(contourPreview); }
      var color = currentContour ? currentContour.color : '#795548';
      var pts = contourPoints.concat([[latlng.lat, latlng.lng]]);
      contourPreview = L.polyline(pts, {
        color: color, weight: 2, opacity: 0.5, dashArray: '4 4'
      }).addTo(map);
    }

    function finishContour() {
      if (contourPoints.length < 2) return;
      if (contourPreview) { map.removeLayer(contourPreview); contourPreview = null; }
      drawnItems.clearLayers();

      var cfg = currentContour || {};
      var color = cfg.color || '#795548';
      var elevation = cfg.elevation_m || 0;
      var showLabels = cfg.show_labels !== false;
      var showSlope = cfg.show_slope_arrows || false;

      var group = L.layerGroup().addTo(map);

      // Main contour line (interactive for right-click delete)
      var line = L.polyline(contourPoints, {
        color: color,
        weight: 2.5,
        opacity: 0.7,
        interactive: true
      }).addTo(group);

      // Elevation labels along the line
      if (showLabels && contourPoints.length >= 2) {
        var labelPositions = [0, Math.floor(contourPoints.length / 2), contourPoints.length - 1];
        labelPositions.forEach(function(idx) {
          if (idx >= contourPoints.length) return;
          var pt = contourPoints[idx];
          var labelIcon = L.divIcon({
            className: 'structure-label',
            html: '<span style="font-size:9px;color:' + color + '">' + elevation.toFixed(1) + 'm</span>',
            iconSize: [0, 0],
            iconAnchor: [0, 8]
          });
          L.marker(pt, { icon: labelIcon, interactive: false }).addTo(group);
        });
      }

      // Slope arrows (perpendicular to contour, pointing downhill)
      if (showSlope && contourPoints.length >= 2) {
        var midIdx = Math.floor(contourPoints.length / 2);
        var p1 = contourPoints[Math.max(0, midIdx - 1)];
        var p2 = contourPoints[Math.min(contourPoints.length - 1, midIdx + 1)];
        // Perpendicular direction (right-hand rule → downhill assumed to the right)
        var dx = p2[1] - p1[1];
        var dy = p2[0] - p1[0];
        var perpAngle = Math.atan2(dx, dy) - Math.PI / 2;
        var arrowLen = 15; // metres
        var mid = contourPoints[midIdx];
        var dLat = arrowLen * Math.cos(perpAngle) / 111320;
        var dLng = arrowLen * Math.sin(perpAngle) / (111320 * Math.cos(mid[0] * Math.PI / 180));

        L.polyline(
          [mid, [mid[0] + dLat, mid[1] + dLng]],
          { color: color, weight: 2, opacity: 0.5, dashArray: '4 2', interactive: false }
        ).addTo(group);
        // Small arrowhead
        var endLat = mid[0] + dLat;
        var endLng = mid[1] + dLng;
        var headLen = 5 / 111320;
        var headAngle = Math.PI / 5;
        L.polyline([
          [endLat - headLen * Math.cos(perpAngle - headAngle),
           endLng - headLen * Math.sin(perpAngle - headAngle)],
          [endLat, endLng],
          [endLat - headLen * Math.cos(perpAngle + headAngle),
           endLng - headLen * Math.sin(perpAngle + headAngle)]
        ], { color: color, weight: 2, opacity: 0.5, interactive: false }).addTo(group);

        var arrowLabel = L.divIcon({
          className: 'structure-label',
          html: '<span style="font-size:9px;color:' + color + '">▼ downhill</span>',
          iconSize: [0, 0],
          iconAnchor: [0, -2]
        });
        L.marker([endLat, endLng], { icon: arrowLabel, interactive: false }).addTo(group);
      }

      // Save a copy of points for the removal signal
      var savedPoints = contourPoints.slice();

      // Right-click to delete individual contour
      line.bindTooltip(
        '<b>Contour: ' + elevation.toFixed(1) + 'm</b>' +
        '<br><span style="color:#78909c;font-size:10px">Right-click to remove</span>',
        { className: 'plant-marker-label' }
      );
      line.on('contextmenu', function(e) {
        L.DomEvent.stop(e);
        map.removeLayer(group);
        var idx = contourLayers.indexOf(group);
        if (idx >= 0) contourLayers.splice(idx, 1);
        if (bridge) bridge.onContourRemoved(
          JSON.stringify(savedPoints), elevation, color
        );
      });

      // Stash elevation on the group so undoLastContour can pop the
      // matching layer.
      group._pdContour = { elevation: elevation };
      contourLayers.push(group);

      // Notify Python
      if (bridge) bridge.onContourComplete(
        JSON.stringify(contourPoints.slice()),
        elevation, color
      );

      contourPoints = [];
      setMode('none');
    }

    // Undo helper — remove the most recently placed contour layer
    // matching the given elevation. Returns true if a layer was removed.
    function undoLastContour(elevation) {
      for (var i = contourLayers.length - 1; i >= 0; i--) {
        var g = contourLayers[i];
        var meta = g && g._pdContour;
        if (!meta) continue;
        if (Math.abs((meta.elevation || 0) - elevation) > 1e-3) continue;
        try { map.removeLayer(g); } catch (e) {}
        contourLayers.splice(i, 1);
        return true;
      }
      // Fallback: just pop the most recent layer.
      if (contourLayers.length > 0) {
        var last = contourLayers.pop();
        try { map.removeLayer(last); } catch (e) {}
        return true;
      }
      return false;
    }

    function clearContours() {
      contourLayers.forEach(function(g) { map.removeLayer(g); });
      contourLayers = [];
    }

    // ── A3b: Auto-generated terrain (slope contours + ramp overlay) ─────────
    var autoContourLayer = null;
    var slopeOverlayLayer = null;
    var _terrainRectStart = null;
    var _terrainRectPreview = null;

    function emitTerrainBboxFromViewport() {
      var b = map.getBounds();
      if (bridge) bridge.onTerrainBboxReady(
        b.getSouth(), b.getNorth(), b.getWest(), b.getEast()
      );
    }

    function emitTerrainBboxFromBoundary() {
      // Use the first boundary in `boundaries` (matches current single-property
      // workflow). If multiple boundaries exist, the user can switch to
      // free-draw or viewport.
      if (!boundaries || boundaries.length === 0) {
        if (bridge) bridge.onTerrainBboxCancelled();
        return;
      }
      var b = boundaries[0].layer;
      if (!b || !b.getBounds) {
        if (bridge) bridge.onTerrainBboxCancelled();
        return;
      }
      var bnds = b.getBounds();
      if (bridge) bridge.onTerrainBboxReady(
        bnds.getSouth(), bnds.getNorth(), bnds.getWest(), bnds.getEast()
      );
    }

    function _terrainRectOnMouseDown(e) {
      if (currentMode !== 'terrain_rect') return;
      L.DomEvent.stop(e);
      _terrainRectStart = e.latlng;
      map.dragging.disable();
    }

    function _terrainRectOnMouseMove(e) {
      if (currentMode !== 'terrain_rect' || !_terrainRectStart) return;
      var bnds = L.latLngBounds(_terrainRectStart, e.latlng);
      if (_terrainRectPreview) {
        _terrainRectPreview.setBounds(bnds);
      } else {
        _terrainRectPreview = L.rectangle(bnds, {
          color: '#2e7d32', weight: 2, dashArray: '6 4',
          fillOpacity: 0.08, interactive: false
        }).addTo(map);
      }
    }

    function _terrainRectOnMouseUp(e) {
      if (currentMode !== 'terrain_rect' || !_terrainRectStart) return;
      L.DomEvent.stop(e);
      var bnds = L.latLngBounds(_terrainRectStart, e.latlng);
      _terrainRectStart = null;
      map.dragging.enable();
      if (_terrainRectPreview) {
        map.removeLayer(_terrainRectPreview);
        _terrainRectPreview = null;
      }
      setMode('none');
      // A degenerate (single-pixel) rectangle is treated as cancelled.
      var w = Math.abs(bnds.getEast()  - bnds.getWest());
      var h = Math.abs(bnds.getNorth() - bnds.getSouth());
      if (w < 1e-6 || h < 1e-6) {
        if (bridge) bridge.onTerrainBboxCancelled();
        return;
      }
      if (bridge) bridge.onTerrainBboxReady(
        bnds.getSouth(), bnds.getNorth(), bnds.getWest(), bnds.getEast()
      );
    }

    function drawAutoContours(payload) {
      // payload: {contours: [{elevation_m, segments: [[[lat,lng],...], ...]}],
      //           color: hex, show_labels: bool}
      if (autoContourLayer) {
        map.removeLayer(autoContourLayer);
        autoContourLayer = null;
      }
      if (!payload || !payload.contours || payload.contours.length === 0) {
        return;
      }
      // The contour-count log below is the safest of the diagnostics
      // to remove (no observed effect on the maximise-resize fix), but
      // it's handy when sizing complaints land -- 246k vertices on
      // canvas is the difference between "snappy" and "freeze". If you
      // do trim it, keep the canvas renderer on the L.polyline call
      // below; that's the load-bearing piece for the freeze fix.
      var _segCount = 0, _vertCount = 0;
      payload.contours.forEach(function(c) {
        c.segments.forEach(function(s) { _segCount++; _vertCount += s.length; });
      });
      console.log('[dbg] drawAutoContours: ' + payload.contours.length +
                  ' contours, ' + _segCount + ' segments, ' +
                  _vertCount + ' vertices');
      autoContourLayer = L.layerGroup().addTo(map);

      var color = payload.color || '#5d4037';
      var showLabels = payload.show_labels !== false;
      // Find the elevation range so we can pick "index" contours (every 5th).
      var elevs = payload.contours.map(function(c) { return c.elevation_m; });
      var minE = Math.min.apply(null, elevs);
      var maxE = Math.max.apply(null, elevs);

      payload.contours.forEach(function(c, i) {
        var elev = c.elevation_m;
        // Index contours every 5th; emphasised slightly.
        var isIndex = (Math.round((elev - minE) * 2) % 10 === 0);
        var weight  = isIndex ? 2.0 : 1.2;
        var opacity = isIndex ? 0.85 : 0.55;

        c.segments.forEach(function(seg) {
          var line = L.polyline(seg, {
            renderer: canvasRenderer,
            color: color, weight: weight, opacity: opacity,
            interactive: false
          }).addTo(autoContourLayer);
        });

        // Label: pick the longest segment's mid-point for index contours only.
        if (showLabels && isIndex && c.segments.length > 0) {
          var longest = c.segments[0];
          var longestLen = longest.length;
          c.segments.forEach(function(s) {
            if (s.length > longestLen) { longest = s; longestLen = s.length; }
          });
          var mid = longest[Math.floor(longest.length / 2)];
          var labelIcon = L.divIcon({
            className: 'structure-label',
            html: '<span style="font-size:9px;color:' + color +
                  ';background:rgba(255,255,255,0.55);padding:0 3px;border-radius:2px">' +
                  elev.toFixed(1) + 'm</span>',
            iconSize: [0, 0],
            iconAnchor: [0, 6]
          });
          L.marker(mid, { icon: labelIcon, interactive: false }).addTo(autoContourLayer);
        }
      });
    }

    function drawSlopeOverlay(payload) {
      // payload: {image: data-url, bbox: {south, north, west, east}, opacity: 0..1}
      if (slopeOverlayLayer) {
        map.removeLayer(slopeOverlayLayer);
        slopeOverlayLayer = null;
      }
      if (!payload || !payload.image || !payload.bbox) return;
      var b = payload.bbox;
      var bnds = L.latLngBounds(
        [b.south, b.west],
        [b.north, b.east]
      );
      slopeOverlayLayer = L.imageOverlay(payload.image, bnds, {
        opacity: typeof payload.opacity === 'number' ? payload.opacity : 0.6,
        interactive: false
      }).addTo(map);
      // Place beneath vector layers but above tiles. Leaflet defaults are fine.
    }

    function setSlopeOverlayOpacity(opacity) {
      if (slopeOverlayLayer && slopeOverlayLayer.setOpacity) {
        slopeOverlayLayer.setOpacity(opacity);
      }
    }

    function clearAutoTerrain() {
      if (autoContourLayer) {
        map.removeLayer(autoContourLayer);
        autoContourLayer = null;
      }
      if (slopeOverlayLayer) {
        map.removeLayer(slopeOverlayLayer);
        slopeOverlayLayer = null;
      }
      if (waterOverlayLayer) {
        map.removeLayer(waterOverlayLayer);
        waterOverlayLayer = null;
      }
    }

    // ── Water flow & accumulation (V2.13) — a layerGroup holding the blue
    // accumulation raster plus sparse downhill arrows, so it composes with
    // the slope ramp and clears with the rest of the auto terrain.
    var waterOverlayLayer = null;

    function drawWaterOverlay(payload) {
      // payload: {image: data-url, bbox: {south,north,west,east},
      //           opacity: 0..1, arrows: [{lat,lng,bearing,strength}, ...]}
      if (waterOverlayLayer) {
        map.removeLayer(waterOverlayLayer);
        waterOverlayLayer = null;
      }
      if (!payload || !payload.image || !payload.bbox) return;
      var b = payload.bbox;
      waterOverlayLayer = L.layerGroup().addTo(map);
      L.imageOverlay(payload.image,
        L.latLngBounds([b.south, b.west], [b.north, b.east]),
        { opacity: typeof payload.opacity === 'number' ? payload.opacity : 0.65,
          interactive: false }
      ).addTo(waterOverlayLayer);

      // Downhill arrows: length/weight scale with log-accumulation strength.
      var arrows = payload.arrows || [];
      var spanM = (b.north - b.south) * 111320;
      var baseLen = Math.max(1.5, spanM * 0.03);   // metres
      for (var i = 0; i < arrows.length; i++) {
        var a = arrows[i];
        var rad = a.bearing * Math.PI / 180;
        var len = baseLen * (0.5 + a.strength);
        var cosLat = Math.cos(a.lat * Math.PI / 180);
        var dLat = len * Math.cos(rad) / 111320;
        var dLng = len * Math.sin(rad) / (111320 * cosLat);
        var endLat = a.lat + dLat, endLng = a.lng + dLng;
        var weight = 1 + a.strength * 1.5;
        var opacity = 0.35 + a.strength * 0.45;
        var style = { color: '#1976d2', weight: weight, opacity: opacity,
                      interactive: false };
        L.polyline([[a.lat, a.lng], [endLat, endLng]], style)
          .addTo(waterOverlayLayer);
        var headLen = (len * 0.35) / 111320;
        var headAngle = Math.PI / 5;
        L.polyline([
          [endLat - headLen * Math.cos(rad - headAngle),
           endLng - headLen * Math.sin(rad - headAngle) / cosLat],
          [endLat, endLng],
          [endLat - headLen * Math.cos(rad + headAngle),
           endLng - headLen * Math.sin(rad + headAngle) / cosLat]
        ], style).addTo(waterOverlayLayer);
      }
    }

    // ── Shade overlay (V1.51) — a SEPARATE image layer from the slope
    // overlay so the two can be shown at once. Mirrors drawSlopeOverlay.
    var shadeOverlayLayer = null;

    function drawShadeOverlay(payload) {
      // payload: {image: data-url, bbox: {south, north, west, east}, opacity}
      if (shadeOverlayLayer) {
        map.removeLayer(shadeOverlayLayer);
        shadeOverlayLayer = null;
      }
      if (!payload || !payload.image || !payload.bbox) return;
      var b = payload.bbox;
      var bnds = L.latLngBounds([b.south, b.west], [b.north, b.east]);
      shadeOverlayLayer = L.imageOverlay(payload.image, bnds, {
        opacity: typeof payload.opacity === 'number' ? payload.opacity : 0.5,
        interactive: false
      }).addTo(map);
    }

    function setShadeOverlayOpacity(opacity) {
      if (shadeOverlayLayer && shadeOverlayLayer.setOpacity) {
        shadeOverlayLayer.setOpacity(opacity);
      }
    }

    function clearShadeOverlay() {
      if (shadeOverlayLayer) {
        map.removeLayer(shadeOverlayLayer);
        shadeOverlayLayer = null;
      }
    }

    // ── Splat "yard photo" overlay (V1.65) — a top-down render of the
    // imported Gaussian-splat backdrop, baked in the 3D viewer and shown
    // here as a personal, fresher satellite layer. Its own image layer
    // (like slope/shade) so it composes with everything; markers/boundary
    // stay on top via the default overlay pane. Mirrors drawShadeOverlay.
    var splatOrthoLayer = null;

    function drawSplatOrthoOverlay(payload) {
      // payload: {image: data-url, bbox: {south, north, west, east}, opacity}
      clearSplatOrtho();
      if (!payload || !payload.image || !payload.bbox) return;
      var b = payload.bbox;
      var bnds = L.latLngBounds([b.south, b.west], [b.north, b.east]);
      splatOrthoLayer = L.imageOverlay(payload.image, bnds, {
        opacity: typeof payload.opacity === 'number' ? payload.opacity : 1.0,
        interactive: false
      }).addTo(map);
    }

    function setSplatOrthoVisible(visible) {
      if (!splatOrthoLayer) return;
      if (visible) { splatOrthoLayer.addTo(map); }
      else { map.removeLayer(splatOrthoLayer); }
    }

    function setSplatOrthoOpacity(opacity) {
      if (splatOrthoLayer && splatOrthoLayer.setOpacity) {
        splatOrthoLayer.setOpacity(opacity);
      }
    }

    function clearSplatOrtho() {
      if (splatOrthoLayer) {
        map.removeLayer(splatOrthoLayer);
        splatOrthoLayer = null;
      }
    }

    // ── Site photo overlay (F24) — a user yard/drone photo dropped on the map
    // as a georeferenced underlay. Same image-layer machinery as the splat
    // "yard photo"; bbox is computed Python-side (src/site_photo.py).
    var sitePhotoLayer = null;

    function drawSitePhotoOverlay(payload) {
      clearSitePhoto();
      if (!payload || !payload.image || !payload.bbox) return;
      var b = payload.bbox;
      sitePhotoLayer = L.imageOverlay(payload.image,
        L.latLngBounds([b.south, b.west], [b.north, b.east]),
        { opacity: typeof payload.opacity === 'number' ? payload.opacity : 1.0,
          interactive: false }).addTo(map);
    }

    function setSitePhotoVisible(visible) {
      if (!sitePhotoLayer) return;
      if (visible) { sitePhotoLayer.addTo(map); } else { map.removeLayer(sitePhotoLayer); }
    }

    function setSitePhotoOpacity(opacity) {
      if (sitePhotoLayer && sitePhotoLayer.setOpacity) sitePhotoLayer.setOpacity(opacity);
    }

    function clearSitePhoto() {
      if (sitePhotoLayer) { map.removeLayer(sitePhotoLayer); sitePhotoLayer = null; }
    }

    // ── Planting-zone shade map (discrete sun/partial/shade cells) ──────────
    // The "Classify planting zones" result drawn as a coloured grid so you can
    // see, at a glance, where full-sun / partial / full-shade planting spots
    // are. Toggleable via setShadeZonesVisible.
    var shadeZonesLayer = null;
    var SHADE_ZONE_COLORS = {
      full_sun:      '#ffd54f',   // gold
      partial_shade: '#fb8c00',   // orange
      full_shade:    '#5c6bc0'    // indigo
    };

    function drawShadeZones(payload) {
      // payload: {cells: [{lat,lng,tag}], dLat, dLng, opacity}
      clearShadeZones();
      if (!payload || !payload.cells || !payload.cells.length) return;
      var op = (typeof payload.opacity === 'number') ? payload.opacity : 0.45;
      var hLat = (payload.dLat || 0.00004) / 2;
      var hLng = (payload.dLng || 0.00006) / 2;
      shadeZonesLayer = L.layerGroup();
      payload.cells.forEach(function (z) {
        var color = SHADE_ZONE_COLORS[z.tag] || '#90a4ae';
        L.rectangle(
          [[z.lat - hLat, z.lng - hLng], [z.lat + hLat, z.lng + hLng]],
          { stroke: false, fill: true, fillColor: color, fillOpacity: op,
            interactive: false, renderer: canvasRenderer }
        ).addTo(shadeZonesLayer);
      });
      shadeZonesLayer.addTo(map);
    }

    function setShadeZonesVisible(visible) {
      if (!shadeZonesLayer) return;
      if (visible) { shadeZonesLayer.addTo(map); }
      else { map.removeLayer(shadeZonesLayer); }
    }

    function clearShadeZones() {
      if (shadeZonesLayer) { map.removeLayer(shadeZonesLayer); shadeZonesLayer = null; }
    }

    // ── Vector shadow overlay (true-shape polygons) ─────────────────────────
    // Preferred over the raster shade overlay when shapely is available: real
    // footprint shadows drawn as crisp polygons that stay sharp at any zoom and
    // don't get dropped by the coarse elevation grid.
    var shadowPolyLayer = null;

    function _shadowStyle(opacity) {
      return {
        stroke: true, color: '#283593',
        weight: 1, opacity: Math.min(1, opacity + 0.2),
        fill: true, fillColor: '#3f51b5', fillOpacity: opacity,
        interactive: false
      };
    }

    function drawShadowPolygons(payload) {
      // payload: {polygons: [ [ringLatLng, hole...], ... ], opacity}
      clearShadowPolygons();
      if (!payload || !payload.polygons || !payload.polygons.length) return;
      var opacity = (typeof payload.opacity === 'number') ? payload.opacity : 0.5;
      shadowPolyLayer = L.layerGroup();
      payload.polygons.forEach(function (rings) {
        // rings = [exterior, hole1, ...]; L.polygon takes [lat,lng] pairs and
        // treats trailing rings as holes.
        L.polygon(rings, _shadowStyle(opacity)).addTo(shadowPolyLayer);
      });
      shadowPolyLayer.addTo(map);
    }

    function setShadowPolygonOpacity(opacity) {
      if (!shadowPolyLayer) return;
      shadowPolyLayer.eachLayer(function (l) {
        if (l.setStyle) l.setStyle(_shadowStyle(opacity));
      });
    }

    function clearShadowPolygons() {
      if (shadowPolyLayer) {
        map.removeLayer(shadowPolyLayer);
        shadowPolyLayer = null;
      }
    }

    // ── A4: Wind overlay ────────────────────────────────────────────────────
    var windLayer = null;

    function drawWindOverlay(data) {
      clearWindOverlay();
      windLayer = L.layerGroup().addTo(map);
      var center = map.getCenter();
      var lat = center.lat;
      var lng = center.lng;
      var dirFrom  = data.direction_from || 315; // degrees (where wind comes FROM)
      var speedLabel = data.speed_label || 'Moderate';
      var showShelter = data.show_shelter !== false;
      var showArrows  = data.show_arrows !== false;

      // Wind blows FROM dirFrom TOWARDS dirFrom+180
      var windToward = (dirFrom + 180) % 360;
      var windRad = windToward * Math.PI / 180;

      // Speed-based visual parameters
      var speedMap = { 'Light': 1, 'Moderate': 2, 'Strong': 3, 'Very Strong': 4 };
      var speedLevel = speedMap[speedLabel] || 2;

      if (showArrows) {
        // Draw a 3x3 grid of wind flow arrows (reduced from 5x5 for performance)
        var bounds = map.getBounds();
        var stepLat = (bounds.getNorth() - bounds.getSouth()) / 4;
        var stepLng = (bounds.getEast() - bounds.getWest()) / 4;
        var arrowLen = stepLat * 111320 * 0.3; // metres

        for (var r = 1; r < 4; r++) {
          for (var c = 1; c < 4; c++) {
            var aLat = bounds.getSouth() + r * stepLat;
            var aLng = bounds.getWest() + c * stepLng;
            var dLat = arrowLen * Math.cos(windRad) / 111320;
            var dLng = arrowLen * Math.sin(windRad) / (111320 * Math.cos(aLat * Math.PI / 180));

            var opacity = 0.15 + speedLevel * 0.08;
            var weight = 1 + speedLevel * 0.5;

            L.polyline(
              [[aLat, aLng], [aLat + dLat, aLng + dLng]],
              { color: '#42a5f5', weight: weight, opacity: opacity, interactive: false }
            ).addTo(windLayer);

            // Arrowhead
            var endLat = aLat + dLat;
            var endLng = aLng + dLng;
            var headLen = arrowLen * 0.25 / 111320;
            var headAngle = Math.PI / 5;
            L.polyline([
              [endLat - headLen * Math.cos(windRad - headAngle),
               endLng - headLen * Math.sin(windRad - headAngle)],
              [endLat, endLng],
              [endLat - headLen * Math.cos(windRad + headAngle),
               endLng - headLen * Math.sin(windRad + headAngle)]
            ], { color: '#42a5f5', weight: weight, opacity: opacity, interactive: false }).addTo(windLayer);
          }
        }
      }

      // Direction indicator at centre
      var indicatorLen = 60;
      var fromRad = dirFrom * Math.PI / 180;
      var fromLat = lat + indicatorLen * Math.cos(fromRad) / 111320;
      var fromLng = lng + indicatorLen * Math.sin(fromRad) / (111320 * Math.cos(lat * Math.PI / 180));

      L.polyline(
        [[fromLat, fromLng], [lat, lng]],
        { color: '#1565c0', weight: 3, opacity: 0.8, interactive: false }
      ).addTo(windLayer);

      var dirLabel = L.divIcon({
        className: 'measure-label',
        html: '<span style="font-size:10px">Wind from ' + dirFrom + '° (' + speedLabel + ')</span>',
        iconSize: [0, 0],
        iconAnchor: [0, 14]
      });
      L.marker([fromLat, fromLng], { icon: dirLabel, interactive: false }).addTo(windLayer);

      // Show shelter zones behind windbreak hedgerows/structures
      if (showShelter) {
        drawWindShelterZones(windRad, speedLevel);
      }
    }

    function drawWindShelterZones(windRad, speedLevel) {
      // Check hedgerows
      Object.keys(hedgerowLayers).forEach(function(hid) {
        var group = hedgerowLayers[hid];
        group.eachLayer(function(layer) {
          if (layer._hedge) {
            var pts = layer._hedge.points;
            if (!pts || pts.length < 2) return;
            // Average height estimate for hedgerow: 2-4m
            var height = (layer._hedge.style === 'windbreak') ? 6 : 3;
            var shelterLen = height * 10; // 10× height
            _drawShelterBehindLine(pts, windRad, shelterLen);
          }
        });
      });

      // Check structures that are windbreaks
      Object.keys(structureMarkers).forEach(function(sid) {
        var group = structureMarkers[sid];
        group.eachLayer(function(layer) {
          if (layer._struct && (layer._struct.name === 'Fence / Wall' || layer._struct.name === 'Tool Shed')) {
            var height = 2.0;
            var lat = layer._struct.lat;
            var lng = layer._struct.lng;
            var shelterLen = height * 10;
            // Simple shelter rectangle behind the structure
            var dLat = shelterLen * Math.cos(windRad) / 111320;
            var dLng = shelterLen * Math.sin(windRad) / (111320 * Math.cos(lat * Math.PI / 180));
            var halfW = (layer._struct.sizeM || 3) / 2;
            var perpRad = windRad + Math.PI / 2;
            var pLat = halfW * Math.cos(perpRad) / 111320;
            var pLng = halfW * Math.sin(perpRad) / (111320 * Math.cos(lat * Math.PI / 180));

            var shelterPoly = L.polygon([
              [lat - pLat, lng - pLng],
              [lat + pLat, lng + pLng],
              [lat + pLat + dLat, lng + pLng + dLng],
              [lat - pLat + dLat, lng - pLng + dLng]
            ], {
              color: '#81d4fa',
              weight: 1,
              fillColor: '#81d4fa',
              fillOpacity: 0.12,
              dashArray: '4 3',
              interactive: false
            }).addTo(windLayer);
          }
        });
      });
    }

    function _drawShelterBehindLine(pts, windRad, shelterLen) {
      // Create a shelter polygon behind the hedgerow line
      if (pts.length < 2) return;
      var shelterPts = [];
      // Forward side (the hedgerow itself)
      pts.forEach(function(p) { shelterPts.push(p); });
      // Back side (offset in wind direction)
      for (var i = pts.length - 1; i >= 0; i--) {
        var p = pts[i];
        var dLat = shelterLen * Math.cos(windRad) / 111320;
        var dLng = shelterLen * Math.sin(windRad) / (111320 * Math.cos(p[0] * Math.PI / 180));
        shelterPts.push([p[0] + dLat, p[1] + dLng]);
      }

      L.polygon(shelterPts, {
        color: '#81d4fa',
        weight: 1,
        fillColor: '#b3e5fc',
        fillOpacity: 0.10,
        dashArray: '4 3',
        interactive: false
      }).addTo(windLayer);

      // Label
      var mid = pts[Math.floor(pts.length / 2)];
      var dLat = shelterLen * 0.5 * Math.cos(windRad) / 111320;
      var dLng = shelterLen * 0.5 * Math.sin(windRad) / (111320 * Math.cos(mid[0] * Math.PI / 180));
      var labelIcon = L.divIcon({
        className: 'structure-label',
        html: '<span style="font-size:9px;color:#81d4fa">Shelter zone (' + shelterLen.toFixed(0) + 'm)</span>',
        iconSize: [0, 0],
        iconAnchor: [0, 8]
      });
      L.marker([mid[0] + dLat, mid[1] + dLng], { icon: labelIcon, interactive: false }).addTo(windLayer);
    }

    function clearWindOverlay() {
      if (windLayer) { map.removeLayer(windLayer); windLayer = null; }
    }

    // ── Dynamic wind shadow (V1.68) ─────────────────────────────────────────
    // Two layers: a per-plant ghost (JS-computed, redrawn live as the dial turns
    // / a plant drags — zero Python round-trips) and the authoritative merged,
    // porosity-banded shelter that Python pushes on commit.
    // Geometry mirrors src/wind_shadow.py.
    var windShadowLayer = null;   // merged (idle view)
    var windGhostLayer  = null;   // per-plant wedges (during interaction)
    var _windCasters = [];        // [{id,lat,lng,height_m,half_width_m,porosity}]
    var _windAngle   = 270;       // wind FROM, degrees
    var _windShadowOn = false;
    var _WIND_BANDS = [[0.70, 1.00, 'weak'], [0.40, 0.70, 'moderate'],
                       [0.0, 0.40, 'strong']];
    var _WIND_STYLE = {
      strong:   { color: '#0277bd', weight: 0, fillColor: '#0277bd', fillOpacity: 0.34 },
      moderate: { color: '#0288d1', weight: 0, fillColor: '#0288d1', fillOpacity: 0.20 },
      weak:     { color: '#4fc3f7', weight: 0, fillColor: '#4fc3f7', fillOpacity: 0.11 }
    };

    function _windReachH(p) {
      p = Math.max(0, Math.min(1, p));
      return 15.0 - 14.0 * Math.abs(p - 0.5);
    }

    function _windWedges(c) {
      // Per-band trapezoids for one caster at the current angle, leeward.
      var out = [];
      var reach = Math.min(250, _windReachH(c.porosity) * c.height_m);
      var hw = Math.max(0.3, c.half_width_m);
      var th = (_windAngle + 180) * Math.PI / 180;     // downwind bearing
      var cosLat = Math.cos(c.lat * Math.PI / 180) || 1e-9;
      var nLat = Math.cos(th) / 111320, nLng = Math.sin(th) / (111320 * cosLat);
      var pTh = th + Math.PI / 2;
      var pLat = Math.cos(pTh) / 111320, pLng = Math.sin(pTh) / (111320 * cosLat);
      _WIND_BANDS.forEach(function (b) {
        var r0 = b[0] * reach, r1 = b[1] * reach;
        if (r1 - r0 < 0.1) return;
        var w0 = hw * (1 - 0.6 * b[0]), w1 = hw * Math.max(0.4, 1 - 0.6 * b[1]);
        var n0Lat = c.lat + nLat * r0, n0Lng = c.lng + nLng * r0;
        var n1Lat = c.lat + nLat * r1, n1Lng = c.lng + nLng * r1;
        out.push({ strength: b[2], poly: [
          [n0Lat + pLat * w0, n0Lng + pLng * w0],
          [n0Lat - pLat * w0, n0Lng - pLng * w0],
          [n1Lat - pLat * w1, n1Lng - pLng * w1],
          [n1Lat + pLat * w1, n1Lng + pLng * w1]
        ]});
      });
      return out;
    }

    function _drawWindGhost() {
      if (!windGhostLayer) windGhostLayer = L.layerGroup();
      windGhostLayer.clearLayers();
      // Weak first so strong paints on top (matches merged draw order).
      ['weak', 'moderate', 'strong'].forEach(function (strength) {
        _windCasters.forEach(function (c) {
          _windWedges(c).forEach(function (w) {
            if (w.strength !== strength) return;
            L.polygon(w.poly, Object.assign({ interactive: false },
                      _WIND_STYLE[strength])).addTo(windGhostLayer);
          });
        });
      });
      if (_windShadowOn && !map.hasLayer(windGhostLayer)) windGhostLayer.addTo(map);
    }

    function setWindCasters(list) {
      _windCasters = list || [];
      if (_windShadowOn) _drawWindGhost();
    }

    function setWindAngleLive(deg) {
      _windAngle = deg;
      if (!_windShadowOn) return;
      // Live: show the fast ghost, hide the now-stale merged shape.
      if (windShadowLayer && map.hasLayer(windShadowLayer)) map.removeLayer(windShadowLayer);
      _drawWindGhost();
    }

    function drawMergedWindShelter(payload) {
      if (!windShadowLayer) windShadowLayer = L.layerGroup();
      windShadowLayer.clearLayers();
      (payload && payload.bands || []).forEach(function (band) {
        (band.rings || []).forEach(function (polyRings) {
          L.polygon(polyRings, Object.assign({ interactive: false },
                    _WIND_STYLE[band.strength] || _WIND_STYLE.moderate))
            .addTo(windShadowLayer);
        });
      });
      if (typeof payload.wind_from_deg === 'number') _windAngle = payload.wind_from_deg;
      // Authoritative result in — drop the ghost, show the clean merged layer.
      if (windGhostLayer) windGhostLayer.clearLayers();
      if (_windShadowOn && !map.hasLayer(windShadowLayer)) windShadowLayer.addTo(map);
    }

    function setWindShadowVisible(v) {
      _windShadowOn = !!v;
      if (_windShadowOn) {
        if (windShadowLayer && windShadowLayer.getLayers().length) windShadowLayer.addTo(map);
        else _drawWindGhost();
      } else {
        if (windShadowLayer) map.removeLayer(windShadowLayer);
        if (windGhostLayer) map.removeLayer(windGhostLayer);
      }
    }

    function clearWindShadow() {
      if (windShadowLayer) windShadowLayer.clearLayers();
      if (windGhostLayer) windGhostLayer.clearLayers();
    }

    // ── Snow-catch microsites (Step 3) — winter snow drifts into the lee of
    // windbreaks (same geometry as wind shelter, snow framing). Cool palette,
    // deeper catch = more saturated. Its own layer so it composes with the rest.
    var snowCatchLayer = null;
    var _SNOW_STYLE = {
      deep:     { color: '#1565c0', weight: 1, opacity: 0.6, fill: true,
                  fillColor: '#42a5f5', fillOpacity: 0.32 },
      moderate: { color: '#1976d2', weight: 1, opacity: 0.5, fill: true,
                  fillColor: '#90caf9', fillOpacity: 0.22 },
      light:    { color: '#90caf9', weight: 1, opacity: 0.4, fill: true,
                  fillColor: '#bbdefb', fillOpacity: 0.14 }
    };

    function drawSnowCatch(payload) {
      if (!snowCatchLayer) snowCatchLayer = L.layerGroup();
      snowCatchLayer.clearLayers();
      (payload && payload.bands || []).forEach(function (band) {
        (band.rings || []).forEach(function (polyRings) {
          L.polygon(polyRings, Object.assign({ interactive: false },
                    _SNOW_STYLE[band.catch] || _SNOW_STYLE.moderate))
            .addTo(snowCatchLayer);
        });
      });
      if (!map.hasLayer(snowCatchLayer)) snowCatchLayer.addTo(map);
    }

    function setSnowCatchVisible(v) {
      if (!snowCatchLayer) return;
      if (v) { snowCatchLayer.addTo(map); } else { map.removeLayer(snowCatchLayer); }
    }

    function clearSnowCatch() {
      if (snowCatchLayer) { snowCatchLayer.clearLayers(); map.removeLayer(snowCatchLayer); }
    }

    // Called from the plant drag handler (03-plants.js) so dragged plants'
    // shelter follows live. Match casters→markers ONCE at drag start (positions
    // drift each frame), then update by markerId per frame.
    var _windDrag = null;   // [{c: caster, markerId}]

    function windShadowDragStart(origins) {
      _windDrag = null;
      if (!_windShadowOn || !_windCasters.length || !origins) return;
      _windDrag = [];
      origins.forEach(function (o) {
        var best = null, bd = Infinity;
        _windCasters.forEach(function (c) {
          var d = (c.lat - o.lat) * (c.lat - o.lat) + (c.lng - o.lng) * (c.lng - o.lng);
          if (d < bd) { bd = d; best = c; }
        });
        if (best) _windDrag.push({ c: best, markerId: o.markerId });
      });
      if (windShadowLayer && map.hasLayer(windShadowLayer)) map.removeLayer(windShadowLayer);
    }

    function windShadowApplyDrag(currentByMarkerId) {
      if (!_windDrag) return;
      _windDrag.forEach(function (e) {
        var cur = currentByMarkerId[e.markerId];
        if (cur) { e.c.lat = cur.lat; e.c.lng = cur.lng; }
      });
      _drawWindGhost();
    }

    function windShadowDragEnd() { _windDrag = null; }

    // ── Legend toggle ──────────────────────────────────────────────────────
    function toggleLegend() {
      var legend = document.getElementById('map-legend');
      var btn    = document.getElementById('legend-toggle');
      var show   = !legend.classList.contains('visible');
      legend.classList.toggle('visible', show);
      btn.classList.toggle('active', show);
    }

    function setLegendVisible(visible) {
      var legend = document.getElementById('map-legend');
      var btn    = document.getElementById('legend-toggle');
      legend.classList.toggle('visible', visible);
      btn.classList.toggle('active', visible);
    }

    // ── Site pin ──────────────────────────────────────────────────────────
    // Geocoding moved to the Python-side Site panel (src/site_panel.py +
    // src/property_data.geocode_alberta). The panel calls placeSitePin /
    // clearSitePin via map_widget.run_js after resolving an address.
    // Pin is draggable; right-click to remove. Drag and remove notify
    // Python via bridge.onSitePinPlaced / onSitePinRemoved.
    var sitePinMarker = null;

    function placeSitePin(lat, lng, label) {
      if (sitePinMarker) {
        try { map.removeLayer(sitePinMarker); } catch (e) {}
        sitePinMarker = null;
      }
      sitePinMarker = L.marker([lat, lng], {
        title: label || 'Site',
        draggable: true,
        zIndexOffset: 1000,
        icon: L.icon({
          iconUrl:    'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
          iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
          shadowUrl:  'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
          iconSize:   [25, 41],
          iconAnchor: [12, 41],
          popupAnchor:[1, -34],
          shadowSize: [41, 41]
        })
      }).addTo(map);
      if (label) {
        sitePinMarker.bindPopup('<div class="site-pin-popup">' +
          label.replace(/</g,'&lt;') + '</div>');
      }
      sitePinMarker.on('dragend', function(){
        var p = sitePinMarker.getLatLng();
        if (bridge && bridge.onSitePinPlaced) {
          bridge.onSitePinPlaced(p.lat, p.lng, '');
        }
      });
      sitePinMarker.on('contextmenu', function(ev){
        L.DomEvent.stop(ev);
        clearSitePin(true);
      });
      if (bridge && bridge.onSitePinPlaced) {
        bridge.onSitePinPlaced(lat, lng, label || '');
      }
    }

    function clearSitePin(notify) {
      if (sitePinMarker) {
        try { map.removeLayer(sitePinMarker); } catch (e) {}
        sitePinMarker = null;
      }
      if (notify && bridge && bridge.onSitePinRemoved) {
        bridge.onSitePinRemoved();
      }
    }

    function setSitePinVisible(visible) {
      if (!sitePinMarker) return;
      if (visible) sitePinMarker.addTo(map);
      else map.removeLayer(sitePinMarker);
    }

    // While pin-drop mode is armed, give the map a crosshair cursor so
    // the user has a visual "you are placing a point" affordance.
    function setSitePinDropMode(active) {
      try {
        map.getContainer().style.cursor = active ? 'crosshair' : '';
      } catch (e) {}
    }

    function _initSiteSearchHandlers() {
      // Site search bar moved to the Python-side Site panel; no DOM
      // handlers to wire up here. Kept as a no-op so the bootstrap
      // call sites below don't need to be conditional.
    }

    // ── QWebChannel bootstrap ─────────────────────────────────────────────────
    function initChannel() {
      if (typeof QWebChannel === 'undefined') {
        // Running outside Qt (browser dev) — skip channel
        initMap();
        _initSiteSearchHandlers();
        return;
      }
      new QWebChannel(qt.webChannelTransport, function(channel) {
        bridge = channel.objects.bridge;
        initMap();
        _initSiteSearchHandlers();
        if (bridge && bridge.onMapReady) bridge.onMapReady();
      });
    }

    window.addEventListener('load', initChannel);
