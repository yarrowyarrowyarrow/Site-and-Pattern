// html/map/01-core.js — map/layer state, selection model, marquee, map init, click routing, context menu.
//
// Split from the former single map.html <script> (V1.64). These are
// CLASSIC scripts loaded sequentially by map.html — NOT ES modules —
// so the shared-global execution model (and order) is byte-for-byte
// what the monolith had; ES modules can't load from file:// in
// Chromium without CORS flags. Cross-file calls resolve at call time
// through the shared global scope. The Python↔JS contract over these
// globals is pinned by tests/test_map_js.py + tests/test_bridge_contract.py.
    // ── State ────────────────────────────────────────────────────────────────
    var map, osmLayer, satelliteLayer, mapboxSat, drawnItems, drawControl;

    // ── Multi-boundary state ─────────────────────────────────────────────────
    // Each entry: {id, layer, labelsLayer, areaLabel, points, color, showLengths, showArea}
    var boundaries      = [];
    var boundaryAreaUnit = 0;          // 0=m² 1=ha 2=acre 3=km²
    // Legacy single refs used only by setBoundaryVisible/clearAll redirects
    var _legacyBoundaryLayer = null;   // unused sentinel

    // Edit-mode state for boundary vertex dragging
    var boundaryEditId      = null;    // id of boundary currently in edit mode
    var boundaryEditHandles = [];      // draggable vertex handle markers
    var boundaryBboxHandles = [];      // corner scale handle markers
    var _bboxDragState      = null;    // {origPts, origBounds, cornerIdx, centerLat, centerLng}
    var _polyDragState      = null;    // {startLat, startLng, origPts}

    // Context menu element
    var _ctxMenu = null;

    // Zoom sensitivity (zoomDelta applied to map.options at runtime)
    var _zoomSensitivity = 'fine';     // 'fine'|'normal'|'fast'|'coarse'

    var measureVisible    = true;  // whether measure result is shown
    var plantMarkers  = {};   // id -> marker
    var plantLayerGroup = null; // L.layerGroup for batch visibility toggle
    var bridge        = null; // Python QObject exposed via QWebChannel
    var currentMode   = 'none'; // 'none' | 'boundary' | 'plant' | 'measure' | 'annotate' | 'structure' | 'hedgerow' | 'shape'
    var currentPlant  = null;   // {id, common_name} when in plant-placement mode

    // Structure state
    var structureMarkers = {};  // id -> L.layerGroup
    var currentStructure = null; // structure def when in structure-placement mode

    // Hedgerow state
    var hedgerowLayers  = {};   // id -> L.layerGroup
    var hedgerowPoints  = [];   // points being drawn
    var hedgerowPreview = null; // preview polyline
    var currentHedgerow = null; // hedgerow config when drawing

    // Custom shape state
    var shapeLayers     = {};   // id -> L.layerGroup
    var shapePoints     = [];   // points being drawn
    var shapePreview    = null; // preview polyline
    var currentShape    = null; // shape config when drawing

    // Measurement state
    // Measurement state — each completed measurement is its own
    // L.layerGroup so visibility can be toggled without losing them, and
    // each one can be right-clicked to delete just that measurement.
    var measureStart      = null;   // L.latLng or null while waiting for 2nd click
    var measureLayers     = [];     // array of L.layerGroup, one per measurement
    var _measureWipMarker = null;   // start-marker between clicks

    // Annotation state
    var annotations   = {};     // id -> {marker, text}

    // Anchor placement preview marker (sun-path placement mode)
    var _anchorPreviewMarker = null;

    // ── Unified selection model ──────────────────────────────────────────────
    // Each entry is a `_pd`-style descriptor with at least { kind, ... }
    // where kind ∈ 'plant' | 'boundary' | 'structure' | 'shape'
    // | 'sunpath' and the rest of the fields identify the underlying object
    // (markerId, boundaryId, shapeId, etc.). 'shape' covers OSM buildings,
    // shade-casting footprints and custom area shapes — all in shapeLayers.
    // Keeping a flat list lets marquee/Delete/right-click operate uniformly
    // across feature types — the previous code had per-type isolated state.
    var selectedItems = [];

    // Marquee (rubber-band) drag state — populated on shift+mousedown over
    // the empty map background; cleared on mouseup.
    var _marqueeState = null;   // { startPx, currentPx, rectEl, additive }

    // Pattern placement state. When currentPlant.pattern is set, plant clicks
    // collect anchors instead of placing immediately:
    //   row    : 2 clicks (start, end)
    //   grid   : 2 clicks (corner A, corner B)
    //   circle : 2 clicks (centre, radius point)
    //   single : default — place immediately on click
    // _patternStage tracks how many anchors have been collected. _patternPreview
    // is the Leaflet layer group used for live feedback as the cursor moves.
    var _patternStage   = 0;
    var _patternAnchors = [];
    var _patternPreview = null;

    function _selectionContains(pd) {
      for (var i = 0; i < selectedItems.length; i++) {
        if (_sameSelectable(selectedItems[i], pd)) return true;
      }
      return false;
    }

    function _sameSelectable(a, b) {
      if (!a || !b || a.kind !== b.kind) return false;
      if (a.kind === 'plant')     return a.markerId === b.markerId;
      if (a.kind === 'boundary')  return a.boundaryId === b.boundaryId;
      if (a.kind === 'structure') return a.structureId === b.structureId;
      if (a.kind === 'shape')     return a.shapeId === b.shapeId;
      if (a.kind === 'sunpath')   return true;   // single sunpath at a time
      return false;
    }

    // How many plants are in the current marquee selection (drives group-move).
    function _selectedPlantCount() {
      var n = 0;
      for (var i = 0; i < selectedItems.length; i++) {
        if (selectedItems[i].kind === 'plant') n++;
      }
      return n;
    }

    function _clearSelectionEntry(markerId) {
      // Drop a plant marker from the selection without redrawing other items.
      for (var i = selectedItems.length - 1; i >= 0; i--) {
        if (selectedItems[i].kind === 'plant' && selectedItems[i].markerId === markerId) {
          selectedItems.splice(i, 1);
        }
      }
    }

    // Toggle a single item's membership in the selection (shift+click pattern).
    function toggleSelection(pd) {
      if (_selectionContains(pd)) {
        for (var i = selectedItems.length - 1; i >= 0; i--) {
          if (_sameSelectable(selectedItems[i], pd)) selectedItems.splice(i, 1);
        }
      } else {
        selectedItems.push(pd);
      }
      _refreshSelectionVisuals();
    }

    function clearSelection() {
      selectedItems = [];
      _refreshSelectionVisuals();
    }

    // Select every placed marker of one species (V2.13). Driven from Python
    // by the On This Design list (click a species row → its plants light up);
    // replaces the current selection so Delete/group-move then operate on
    // exactly that species through the normal pipeline.
    function selectPlantsBySpecies(plantId) {
      selectedItems = [];
      Object.keys(plantMarkers).forEach(function(mid) {
        var c = plantMarkers[mid];
        if (c && c._pd && c._pd.plantId === plantId) {
          selectedItems.push(c._pd);
        }
      });
      _refreshSelectionVisuals();
    }

    // Apply / remove the selection highlight on every relevant feature.
    // Plants get a thicker yellow border + brighter fill while selected;
    // boundaries get a thicker stroke.
    function _refreshSelectionVisuals() {
      // Plants
      Object.keys(plantMarkers).forEach(function(mid) {
        var c = plantMarkers[mid];
        if (!c || !c._pd) return;
        var sel = _selectionContains(c._pd);
        var baseColor = c._pd.customColor || TYPE_COLORS[c._pd.plantType] || '#66bb6a';
        c.setStyle({
          color:       sel ? '#fdd835' : baseColor,
          weight:      sel ? 3.0 : 1.5,
          fillOpacity: sel ? 0.55 : 0.35
        });
      });
      // Boundaries
      boundaries.forEach(function(b) {
        var sel = _selectionContains({ kind: 'boundary', boundaryId: b.id });
        if (b.layer && b.layer.setStyle) {
          var palette = BOUNDARY_COLORS[b.color] || BOUNDARY_COLORS['green'];
          b.layer.setStyle({
            color:  sel ? '#fdd835' : palette.stroke,
            weight: sel ? 4 : 2
          });
        }
      });
      // Structures — thicken the outline of the selected ones.
      Object.keys(structureMarkers).forEach(function(sid) {
        var sel = _selectionContains({ kind: 'structure', structureId: sid });
        var g = structureMarkers[sid];
        if (g && g.eachLayer) {
          g.eachLayer(function(lyr) {
            if (lyr.setStyle) lyr.setStyle({ weight: sel ? 4 : 2 });
          });
        }
      });
      // Shapes (OSM buildings, shade footprints, custom shapes) — yellow
      // outline while selected; base style restored from the polygon's own
      // _shape metadata on deselect (shade casters draw heavier at rest).
      if (typeof shapeLayers !== 'undefined') {
        Object.keys(shapeLayers).forEach(function(shid) {
          var sel = _selectionContains({ kind: 'shape', shapeId: shid });
          var g = shapeLayers[shid];
          if (!g || !g.eachLayer) return;
          g.eachLayer(function(lyr) {
            var meta = lyr._shape;
            if (!meta || !lyr.setStyle) return;
            lyr.setStyle({
              color:  sel ? '#fdd835' : (meta.strokeColor || '#2e7d32'),
              weight: sel ? 4 : ((meta.heightM > 0) ? 3 : 2)
            });
          });
        });
      }
      _updateSelectionBadge();
    }

    // Tiny floating badge in the top-right corner showing N selected items
    // and a "Delete" affordance — keeps the UI obvious for first-time users.
    function _updateSelectionBadge() {
      var el = document.getElementById('_pd_sel_badge');
      if (selectedItems.length === 0) {
        if (el && el.parentNode) el.parentNode.removeChild(el);
        return;
      }
      if (!el) {
        el = document.createElement('div');
        el.id = '_pd_sel_badge';
        el.style.cssText = [
          'position:absolute', 'top:8px', 'right:8px', 'z-index:1100',
          'background:rgba(38,50,56,0.92)', 'border:1px solid #fdd835',
          'border-radius:4px', 'padding:6px 10px', 'color:#fdd835',
          'font-size:12px', 'font-family:sans-serif', 'user-select:none',
          'box-shadow:0 2px 8px rgba(0,0,0,0.5)'
        ].join(';');
        document.body.appendChild(el);
      }
      el.innerHTML = '<b>' + selectedItems.length + '</b> selected · ' +
        '<a href="#" id="_pd_sel_del" style="color:#ef9a9a;text-decoration:none">Delete</a> · ' +
        '<a href="#" id="_pd_sel_clr" style="color:#80cbc4;text-decoration:none">Clear</a>';
      document.getElementById('_pd_sel_del').onclick = function(ev) {
        ev.preventDefault(); deleteSelected();
      };
      document.getElementById('_pd_sel_clr').onclick = function(ev) {
        ev.preventDefault(); clearSelection();
      };
    }

    // ── Marquee (shift+drag) selection ───────────────────────────────────────
    // Shift+drag on the map background draws a yellow dashed rectangle and
    // selects every plant / boundary / structure (incl. marked
    // trees+buildings) / shape (OSM buildings, shade footprints, custom
    // shapes) / sun-path centre that intersects it. Plain drag continues to
    // pan; ctrl+shift+drag is additive (extend the existing selection). We
    // intercept at the DOM level so we don't fight Leaflet's pan handler —
    // when shift is held on mousedown we simply prevent Leaflet from
    // receiving the event.

    function _initMarqueeHandlers() {
      // Disable Leaflet's native shift-zoom box so it doesn't collide
      // with our marquee. We re-implement the same gesture for selection.
      if (map.boxZoom) map.boxZoom.disable();

      var container = map.getContainer();
      container.addEventListener('mousedown', _marqueeOnDown, true);
      // mousemove/up listen on document so we keep tracking when the
      // cursor leaves the map container during a drag.
      document.addEventListener('mousemove', _marqueeOnMove, true);
      document.addEventListener('mouseup',   _marqueeOnUp,   true);
    }

    // True when the cursor is over a placed plant marker (canvas-rendered, so
    // not reachable via DOM hit-testing). Used so Select-mode drags on a plant
    // move it instead of starting a marquee.
    function _marqueePointHitsPlant(ev) {
      var rect = map.getContainer().getBoundingClientRect();
      var cx = ev.clientX - rect.left, cy = ev.clientY - rect.top;
      var keys = Object.keys(plantMarkers);
      for (var i = 0; i < keys.length; i++) {
        var m = plantMarkers[keys[i]];
        if (!m || !m._pd) continue;
        var p = map.latLngToContainerPoint(m.getLatLng());
        var r = ((m.options && m.options.radius) || 6) + 4;
        var dx = p.x - cx, dy = p.y - cy;
        if (dx * dx + dy * dy <= r * r) return true;
      }
      return false;
    }

    function _marqueeOnDown(ev) {
      // Arm on Shift+drag (any time) OR on a plain drag while the Select tool is
      // active (the toolbar "Select" button → setMode('select')).
      var inSelectMode = (currentMode === 'select');
      if ((!ev.shiftKey && !inSelectMode) || ev.button !== 0) return;
      // Skip if the user is interacting with a feature — Leaflet handles
      // those events on the marker itself before bubbling here.
      if (ev.target && ev.target.closest && ev.target.closest('.leaflet-marker-pane > *')) return;
      // Plants are drawn on a canvas (not in the marker-pane), so the check
      // above can't see them. In Select mode a mousedown on a plant must NOT
      // start a marquee — let it through so the plant/selection drag arms.
      if (inSelectMode && _marqueePointHitsPlant(ev)) return;
      // Outside Select mode, only Shift-arm when idle / placing plants.
      if (!inSelectMode && currentMode !== 'none' && currentMode !== 'plant') return;
      ev.stopPropagation();
      ev.preventDefault();
      var container = map.getContainer();
      var rect = container.getBoundingClientRect();
      var x = ev.clientX - rect.left;
      var y = ev.clientY - rect.top;
      var rectEl = document.createElement('div');
      rectEl.style.cssText = [
        'position:absolute', 'border:1.5px dashed #fdd835',
        'background:rgba(253,216,53,0.10)', 'pointer-events:none',
        'z-index:1050', 'left:' + x + 'px', 'top:' + y + 'px',
        'width:0px', 'height:0px'
      ].join(';');
      container.appendChild(rectEl);
      _marqueeState = {
        startPx: { x: x, y: y },
        currentPx: { x: x, y: y },
        rectEl: rectEl,
        additive: ev.ctrlKey || ev.metaKey,
      };
    }

    function _marqueeOnMove(ev) {
      if (!_marqueeState) return;
      var rect = map.getContainer().getBoundingClientRect();
      var x = ev.clientX - rect.left;
      var y = ev.clientY - rect.top;
      _marqueeState.currentPx = { x: x, y: y };
      var minX = Math.min(_marqueeState.startPx.x, x);
      var minY = Math.min(_marqueeState.startPx.y, y);
      var w = Math.abs(x - _marqueeState.startPx.x);
      var h = Math.abs(y - _marqueeState.startPx.y);
      _marqueeState.rectEl.style.left = minX + 'px';
      _marqueeState.rectEl.style.top  = minY + 'px';
      _marqueeState.rectEl.style.width  = w + 'px';
      _marqueeState.rectEl.style.height = h + 'px';
    }

    function _marqueeOnUp(ev) {
      if (!_marqueeState) return;
      var rectEl = _marqueeState.rectEl;
      var sX = _marqueeState.startPx.x, sY = _marqueeState.startPx.y;
      var eX = _marqueeState.currentPx.x, eY = _marqueeState.currentPx.y;
      var additive = _marqueeState.additive;
      if (rectEl && rectEl.parentNode) rectEl.parentNode.removeChild(rectEl);
      _marqueeState = null;

      var minX = Math.min(sX, eX), maxX = Math.max(sX, eX);
      var minY = Math.min(sY, eY), maxY = Math.max(sY, eY);
      // Reject tiny drags (treat as accidental click).
      if (maxX - minX < 4 && maxY - minY < 4) return;

      var bounds = L.latLngBounds(
        map.containerPointToLatLng([minX, minY]),
        map.containerPointToLatLng([maxX, maxY])
      );
      var hits = _marqueeHitTest(bounds);
      if (!additive) selectedItems = [];
      hits.forEach(function(h) {
        if (!_selectionContains(h)) selectedItems.push(h);
      });
      _refreshSelectionVisuals();
    }

    // Find every selectable feature whose anchor point falls inside the
    // marquee bounds. Returns a list of selection descriptors.
    function _marqueeHitTest(bounds) {
      var hits = [];
      // Plants — point-in-bounds on the marker centre.
      Object.keys(plantMarkers).forEach(function(mid) {
        var c = plantMarkers[mid];
        if (!c || !c._pd) return;
        if (bounds.contains(L.latLng(c._pd.lat, c._pd.lng))) {
          hits.push(c._pd);
        }
      });
      // Boundaries — any vertex inside the rect counts.
      boundaries.forEach(function(b) {
        var ps = b.points || [];
        for (var i = 0; i < ps.length; i++) {
          if (bounds.contains(L.latLng(ps[i][0], ps[i][1]))) {
            hits.push({ kind: 'boundary', boundaryId: b.id });
            return;
          }
        }
      });
      // Structures — anchor point stashed on the layer group.
      Object.keys(structureMarkers).forEach(function(sid) {
        var g = structureMarkers[sid];
        var anc = g && g._pdStruct;
        if (anc && bounds.contains(L.latLng(anc.lat, anc.lng))) {
          hits.push({ kind: 'structure', structureId: sid,
                      structId: anc.structId, lat: anc.lat, lng: anc.lng });
        }
      });
      // Shapes (OSM buildings, shade footprints, custom shapes) — any
      // vertex inside the rect counts (matching boundaries), with a
      // centroid fallback so a marquee drawn fully inside a large
      // footprint still catches it.
      if (typeof shapeLayers !== 'undefined') {
        Object.keys(shapeLayers).forEach(function(shid) {
          var g = shapeLayers[shid];
          if (!g || !g.eachLayer) return;
          var hit = false;
          g.eachLayer(function(lyr) {
            if (hit || !lyr._shape) return;
            var ps = lyr._shape.points || [];
            for (var i = 0; i < ps.length; i++) {
              if (bounds.contains(L.latLng(ps[i][0], ps[i][1]))) {
                hit = true;
                return;
              }
            }
            if (lyr.getBounds && bounds.contains(lyr.getBounds().getCenter())) {
              hit = true;
            }
          });
          if (hit) hits.push({ kind: 'shape', shapeId: shid });
        });
      }
      // Sun path — represented by its centre tooltip; we check the
      // existing centre marker via sunPathLayer if present.
      if (typeof sunPathLayer !== 'undefined' && sunPathLayer && sunPathLayer.getLayers) {
        var layers = sunPathLayer.getLayers();
        for (var i = 0; i < layers.length; i++) {
          var l = layers[i];
          if (l.getLatLng && bounds.contains(l.getLatLng())) {
            hits.push({ kind: 'sunpath' });
            break;
          }
        }
      }
      return hits;
    }

    // Delete every currently-selected item across types, emitting the
    // appropriate per-type bridge signal so Python project state stays
    // synchronised. Uses a snapshot since underlying maps mutate.
    function deleteSelected() {
      var snapshot = selectedItems.slice();
      selectedItems = [];
      var removedPlants = [];   // batch plant removals into one bridge call
      for (var i = 0; i < snapshot.length; i++) {
        var item = snapshot[i];
        if (item.kind === 'plant') {
          var c = plantMarkers[item.markerId];
          if (c && c._pd) {
            removedPlants.push({ plantId: c._pd.plantId,
                                 lat: c._pd.lat, lng: c._pd.lng });
          }
          _removeSinglePlantMarker(item.markerId, true);
        } else if (item.kind === 'boundary') {
          if (boundaryEditId === item.boundaryId && typeof exitBoundaryEditMode === 'function') {
            exitBoundaryEditMode();
          }
          if (typeof _removeBoundaryEntry === 'function') {
            _removeBoundaryEntry(item.boundaryId);
            if (bridge) bridge.onBoundaryRemoved(item.boundaryId);
          }
        } else if (item.kind === 'structure') {
          var sg2 = structureMarkers[item.structureId];
          if (sg2) { map.removeLayer(sg2); delete structureMarkers[item.structureId]; }
          if (bridge && bridge.onStructureRemoved) {
            bridge.onStructureRemoved(item.structureId, item.structId,
                                      item.lat, item.lng);
          }
        } else if (item.kind === 'shape') {
          if (typeof shapeEditId !== 'undefined' && shapeEditId === item.shapeId
              && typeof exitShapeEditMode === 'function') {
            exitShapeEditMode();
          }
          var shg = (typeof shapeLayers !== 'undefined') ? shapeLayers[item.shapeId] : null;
          if (shg) { map.removeLayer(shg); delete shapeLayers[item.shapeId]; }
          if (bridge && bridge.onShapeRemoved) bridge.onShapeRemoved(item.shapeId);
        } else if (item.kind === 'sunpath') {
          if (typeof clearSunPath === 'function') {
            clearSunPath();
            if (bridge) bridge.onSunPathRemoved();
          }
        }
      }
      if (removedPlants.length && bridge && bridge.onPlantsRemovedBatch) {
        bridge.onPlantsRemovedBatch(JSON.stringify(removedPlants));
      }
      _refreshSelectionVisuals();
    }

    // Polygon drawing state (manual mode)
    var drawingPolygon  = false;
    var polygonPoints   = [];
    var polygonPolyline = null;
    var polygonPreview  = null;

    // ── Map init ─────────────────────────────────────────────────────────────
    function initMap() {
      map = L.map('map', {
        center: [53.5461, -113.4938],
        zoom: 12,
        maxZoom: 24,
        zoomControl: true,
        zoomSnap: 0.1,
        zoomDelta: 0.15,          // ~1.1× per scroll tick ("fine" default)
        wheelPxPerZoomLevel: 60
      });

      osmLayer = L.tileLayer(
        'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
        {
          attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
          subdomains: 'abcd',
          maxZoom: 22,
          maxNativeZoom: 19
        }
      ).addTo(map);

      // Satellite imagery lives in its own pane (below the tile pane so the
      // shade/contour overlays still draw on top) so the alignment nudge
      // (setSatelliteOffset) can shift just these tiles. maxNativeZoom starts
      // safe and is raised to the deepest real Esri zoom for the current area
      // by _refreshSatNativeZoom() (it probes Esri's tilemap) — that keeps full
      // detail where it exists, while maxZoom > maxNativeZoom lets Leaflet
      // upscale ("enlarge") past coverage instead of showing Esri's
      // "Map Data Unavailable" placeholder.
      map.createPane('satellitePane');
      map.getPane('satellitePane').style.zIndex = 150;

      satelliteLayer = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        { attribution: '© Esri', maxZoom: 24, maxNativeZoom: 19,
          pane: 'satellitePane' }
      );

      drawnItems = new L.FeatureGroup().addTo(map);
      plantLayerGroup = L.layerGroup().addTo(map);

      // Map click handler
      map.on('click', onMapClick);
      map.on('mousemove', onMapMouseMove);
      map.on('dblclick', onMapDblClick);

      // Push the current view centre to Python on every pan/zoom so
      // the address finder can bias its query against where the user
      // is currently looking. Fire once on init too — moveend won't
      // fire until the user actually moves.
      map.on('moveend', _emitMapMoved);
      _emitMapMoved();

      // Free-draw rectangle for terrain bbox selection
      map.on('mousedown', _terrainRectOnMouseDown);
      map.on('mousemove', _terrainRectOnMouseMove);
      map.on('mouseup',   _terrainRectOnMouseUp);

      // Drag-to-reposition for placed plants (singletons + polyculture
      // groups). The drag itself is armed from the plant marker's own
      // mousedown via _onPlantMouseDown; the map-level handlers below
      // just deliver the subsequent movement and release events.
      map.on('mousemove', _onPlantDragMove);
      map.on('mouseup',   _onPlantDragEnd);

      // Right-click cancels anchor-placement modes; suppress native browser menu
      map.on('contextmenu', function(e) {
        if (currentMode === 'terrain_rect') {
          L.DomEvent.stop(e);
          setMode('none');
          map.dragging.enable();
          if (bridge) bridge.onTerrainBboxCancelled();
          return;
        }
        if (currentMode === 'sun_anchor') {
          L.DomEvent.stop(e);
          setMode('none');
          if (bridge) bridge.onAnchorCancelled(currentMode);
          return;
        }
        // Cancel a pattern placement in progress (after first click)
        if (currentMode === 'plant' && currentPlant && currentPlant.pattern
            && currentPlant.pattern.kind !== 'single' && _patternStage >= 1) {
          L.DomEvent.stop(e);
          _resetPatternState();
        }
      });

      // Escape exits edit mode / cancels in-progress polygon
      document.addEventListener('keydown', function(ev) {
        if (ev.key === 'Escape') {
          if (shapeEditId !== null) {
            exitShapeEditMode();
          } else if (boundaryEditId !== null) {
            exitBoundaryEditMode();
          } else if (currentMode !== 'none') {
            setMode('none');
          }
        }
      });

      // Click on map background while in boundary/shape-edit → exit edit mode
      // (polygon clicks stop propagation so this only fires on background)
      map.on('click', function() {
        if (currentMode !== 'none') return;
        if (shapeEditId !== null) {
          exitShapeEditMode();
        } else if (boundaryEditId !== null) {
          exitBoundaryEditMode();
        }
      });

      // Zoom-dependent label visibility
      map.on('zoomend', updateLabelVisibility);

      // Re-apply the satellite alignment nudge — metres→pixels changes per zoom.
      map.on('zoomend', _applySatOffset);

      // Re-check how deep Esri imagery actually goes for the current area, so we
      // keep full detail and only upscale past real coverage.
      map.on('moveend', _scheduleSatProbe);

      // Load-bearing: don't remove. This listener is what makes
      // Leaflet's own _onResize handler fire reliably after a Qt
      // maximise on Windows. Registering it triggers Leaflet to add
      // its window-resize bookkeeping, and the console.log inside
      // forces a layout reflow when Leaflet's resize event arrives.
      // Together with the clientWidth reads in invalidate_size (see
      // src/map_widget.py), this is what keeps the embedded viewport
      // in sync with the Qt widget size.
      map.on('resize', function(e) {
        console.log('[dbg] map resize event, newSize=' +
                    e.newSize.x + 'x' + e.newSize.y);
      });

      // Shift+drag marquee selection (replaces Leaflet's box-zoom).
      _initMarqueeHandlers();
    }

    // Emit the current view centre to Python — wired to map.moveend
    // and called once on init. Lets the address finder bias its
    // Nominatim query against where the user is looking.
    function _emitMapMoved() {
      if (!bridge || !bridge.onMapMoved) return;
      try {
        var c = map.getCenter();
        bridge.onMapMoved(c.lat, c.lng, map.getZoom());
      } catch (e) {}
    }

    // ── Click / move handlers ────────────────────────────────────────────────
    function onMapClick(e) {
      var lat = e.latlng.lat;
      var lng = e.latlng.lng;

      // Apply snap if enabled and in a placement mode
      if (snapEnabled && currentMode === 'plant') {
        var snapped = snapLatLng(lat, lng);
        lat = snapped[0];
        lng = snapped[1];
      }

      if (bridge) {
        bridge.onMapClick(lat, lng);
      }

      if (currentMode === 'boundary') {
        handleBoundaryClick(lat, lng);
      } else if (currentMode === 'plant' && currentPlant) {
        var pat = currentPlant.pattern || { kind: 'single' };
        if (pat.kind && pat.kind !== 'single') {
          _handlePatternClick(lat, lng);
        } else {
          var qty = currentPlant.quantity || 1;
          var cc  = currentPlant.custom_color || null;
          if (qty > 1) {
            // Single-mode burst: place qty plants at once (hex pattern).
            // All share one group id so they can be deleted together.
            var positions = _hexBurstPositions(lat, lng, currentPlant.spacing_m, qty);
            if (bridge) {
              bridge.onPatternPlaced(currentPlant.id, currentPlant.common_name,
                                     currentPlant.spacing_m, currentPlant.plant_type,
                                     cc || '', JSON.stringify(positions), 'burst');
            }
          } else {
            placePlantMarker(currentPlant.id, currentPlant.common_name, lat, lng,
                             currentPlant.spacing_m, currentPlant.plant_type, cc);
            if (bridge) bridge.onPlantPlaced(currentPlant.id, currentPlant.common_name, lat, lng);
          }
          // Stay in plant mode so user can place multiple
        }
      } else if (currentMode === 'contour') {
        handleContourClick(lat, lng);
      } else if (currentMode === 'structure' && currentStructure) {
        placeStructureOnMap(currentStructure, lat, lng);
        if (bridge) bridge.onStructurePlaced(currentStructure.id, currentStructure.name, lat, lng, currentStructure.size_m);
        // Stay in structure mode for multiple placements
      } else if (currentMode === 'hedgerow') {
        handleHedgerowClick(lat, lng);
      } else if (currentMode === 'shape' || currentMode === 'fill') {
        handleShapeClick(lat, lng);   // 'fill' reuses the shape polygon drawing
      } else if (currentMode === 'measure') {
        handleMeasureClick(lat, lng);
      } else if (currentMode === 'annotate') {
        handleAnnotateClick(lat, lng);
      } else if (currentMode === 'sun_anchor') {
        // Place sun-path anchor then render via Python callback
        setMode('none');
        if (bridge) bridge.onSunAnchorPlaced(lat, lng);
      }
    }

    function onMapMouseMove(e) {
      if (bridge) {
        bridge.onMouseMove(e.latlng.lat, e.latlng.lng);
      }
      if (currentMode === 'boundary' && drawingPolygon && polygonPoints.length > 0) {
        updatePolygonPreview(e.latlng);
      }
      if (currentMode === 'hedgerow' && hedgerowPoints.length > 0) {
        updateHedgerowPreview(e.latlng);
      }
      if ((currentMode === 'shape' || currentMode === 'fill') && shapePoints.length > 0) {
        updateShapePreview(e.latlng);
      }
      if (currentMode === 'contour' && contourPoints.length > 0) {
        updateContourPreview(e.latlng);
      }
      if (currentMode === 'sun_anchor' && _anchorPreviewMarker) {
        _anchorPreviewMarker.setLatLng(e.latlng);
      }
      if (currentMode === 'plant' && currentPlant && currentPlant.pattern
          && currentPlant.pattern.kind !== 'single' && _patternStage >= 1) {
        _drawPatternPreview(e.latlng);
      }
    }

    function onMapDblClick(e) {
      L.DomEvent.stop(e);
      if (currentMode === 'boundary' && drawingPolygon) {
        finishBoundaryPolygon();
      } else if (currentMode === 'hedgerow' && hedgerowPoints.length >= 2) {
        finishHedgerow();
      } else if (currentMode === 'shape' && shapePoints.length >= 3) {
        finishShape();
      } else if (currentMode === 'fill' && shapePoints.length >= 3) {
        finishFillArea();
      } else if (currentMode === 'contour' && contourPoints.length >= 2) {
        finishContour();
      }
    }

    // ── Boundary color palette ────────────────────────────────────────────────
    var BOUNDARY_COLORS = {
      'green':      { stroke: '#4caf50', fill: '#4caf50' },
      'red':        { stroke: '#f44336', fill: '#f44336' },
      'blue':       { stroke: '#2196f3', fill: '#2196f3' },
      'lightblue':  { stroke: '#03a9f4', fill: '#03a9f4' },
      'yellow':     { stroke: '#f9a825', fill: '#f9a825' },
      'orange':     { stroke: '#ff9800', fill: '#ff9800' },
      'purple':     { stroke: '#9c27b0', fill: '#9c27b0' },
      'magenta':    { stroke: '#e91e63', fill: '#e91e63' },
      'brown':      { stroke: '#795548', fill: '#795548' },
      'black':      { stroke: '#212121', fill: '#212121' },
      'lightgreen': { stroke: '#8bc34a', fill: '#8bc34a' },
      'grey':       { stroke: '#9e9e9e', fill: '#9e9e9e' }
    };
    var _nextBoundaryColor = (function() {
      var _colorNames = Object.keys(BOUNDARY_COLORS);
      var _idx = 0;
      return function() { return _colorNames[_idx++ % _colorNames.length]; };
    })();

    // ── Context menu ─────────────────────────────────────────────────────────
    function showContextMenu(x, y, items) {
      hideContextMenu();
      var div = document.createElement('div');
      div.id = '_pd_ctx_menu';
      div.style.cssText = [
        'position:fixed', 'left:' + x + 'px', 'top:' + y + 'px',
        'background:#263238', 'border:1px solid #546e7a', 'border-radius:4px',
        'box-shadow:0 2px 10px rgba(0,0,0,0.55)', 'z-index:9999',
        'min-width:170px', 'padding:4px 0', 'font-size:13px', 'color:#eceff1',
        'user-select:none'
      ].join(';');

      items.forEach(function(item) {
        if (item === 'sep') {
          var sep = document.createElement('div');
          sep.style.cssText = 'height:1px;background:#546e7a;margin:3px 0';
          div.appendChild(sep);
          return;
        }
        var btn = document.createElement('div');
        btn.style.cssText = 'padding:6px 14px;cursor:pointer;display:flex;align-items:center;gap:8px';
        if (item.checked !== undefined) {
          var chk = document.createElement('span');
          chk.textContent = item.checked ? '✓' : '  ';
          chk.style.cssText = 'font-size:11px;width:12px;display:inline-block;color:#80cbc4';
          btn.appendChild(chk);
        }
        var lbl = document.createElement('span');
        lbl.textContent = item.label;
        btn.appendChild(lbl);
        btn.addEventListener('mouseover', function() { btn.style.background = '#37474f'; });
        btn.addEventListener('mouseout',  function() { btn.style.background = ''; });
        btn.addEventListener('click', function(ev) {
          ev.stopPropagation();
          hideContextMenu();
          item.action();
        });
        div.appendChild(btn);
      });

      // Color swatches row for boundaries
      if (items._colorTarget !== undefined) {
        var swatchDiv = document.createElement('div');
        swatchDiv.style.cssText = 'padding:6px 14px;display:flex;flex-wrap:wrap;gap:5px;';
        Object.keys(BOUNDARY_COLORS).forEach(function(name) {
          var sw = document.createElement('div');
          sw.title = name;
          sw.style.cssText = 'width:16px;height:16px;border-radius:3px;cursor:pointer;border:2px solid transparent;';
          sw.style.background = BOUNDARY_COLORS[name].stroke;
          if (name === items._colorTarget) sw.style.border = '2px solid #fff';
          sw.addEventListener('click', function(ev) {
            ev.stopPropagation();
            hideContextMenu();
            items._colorAction(name);
          });
          swatchDiv.appendChild(sw);
        });
        div.appendChild(swatchDiv);
      }

      document.body.appendChild(div);
      _ctxMenu = div;
      setTimeout(function() {
        document.addEventListener('click', hideContextMenu, { once: true, capture: true });
      }, 50);
    }

    function hideContextMenu() {
      if (_ctxMenu && _ctxMenu.parentNode) {
        _ctxMenu.parentNode.removeChild(_ctxMenu);
      }
      _ctxMenu = null;
    }

    // Suppress native browser context menu everywhere in the map container
    document.addEventListener('contextmenu', function(e) {
      if (e.target.closest && e.target.closest('#map')) {
        e.preventDefault();
      }
    });

