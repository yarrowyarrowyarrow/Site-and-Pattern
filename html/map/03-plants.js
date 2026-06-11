// html/map/03-plants.js — HTML escaping, plant markers, drag-to-reposition + drag-scope cycling, pattern placement, labels.
//
// Split from the former single map.html <script> (V1.64). These are
// CLASSIC scripts loaded sequentially by map.html — NOT ES modules —
// so the shared-global execution model (and order) is byte-for-byte
// what the monolith had; ES modules can't load from file:// in
// Chromium without CORS flags. Cross-file calls resolve at call time
// through the shared global scope. The Python↔JS contract over these
// globals is pinned by tests/test_map_js.py + tests/test_bridge_contract.py.
    // ── HTML escaping (guard against stored-XSS via project files and
    //     any externally-sourced plant data). Every user/file-sourced string
    //     that is concatenated into Leaflet `html:` / `bindTooltip` /
    //     `setContent` MUST flow through escH() first. ──────────────────────
    function escH(s) {
      if (s === null || s === undefined) return '';
      var d = document.createElement('div');
      d.textContent = String(s);
      return d.innerHTML;
    }

    // ── Plant type colours ───────────────────────────────────────────────────
    var TYPE_COLORS = {
      'tree':        '#2e7d32',
      'shrub':       '#558b2f',
      'herb':        '#7cb342',
      'groundcover': '#c6a817',
      'vine':        '#00838f',
      'root':        '#6d4c41'
    };

    // ── Plant labels state ───────────────────────────────────────────────────
    var labelsVisible = false;
    var plantLabels   = {};   // markerId -> L.tooltip (permanent)

    // ── Plant markers ────────────────────────────────────────────────────────
    // spacingM    : plant spacing in metres (used as circle diameter on the map)
    // plantType   : 'tree' | 'shrub' | 'herb' | 'groundcover' | 'vine' | 'root'
    // customColor : optional hex colour override (e.g. '#ff5722')
    // groupId     : optional placement group id (plants placed together share one)
    // communityId : optional per-instance key shared by members of one community
    //               (lets the map isolate one community within a multi-community group)
    function placePlantMarker(plantId, commonName, lat, lng, spacingM, plantType, customColor, groupId, communityId) {
      var markerId = plantId + '_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
      // Marker visual size = mature half-spacing (so two adjacent
      // markers at exactly `spacingM` apart just touch). The previous
      // 1m floor visually overlapped any plant with spacing < 2m at
      // high zoom even though their centres were spaced correctly.
      var radius   = Math.max((spacingM || 1.0) / 2, 0.05);
      var color    = customColor || TYPE_COLORS[plantType] || '#66bb6a';

      // canvasRenderer instead of the default SVG: with dozens of
      // plants on the map, SVG layout against the satellite-tile
      // background was eating enough paint time that the browser
      // dropped tile fetches — visible to the user as the satellite
      // layer "breaking" until the plants were removed. Canvas
      // rendering keeps tooltips, click, contextmenu and the drag
      // handlers all working in Leaflet 1.9.x.
      var circle = L.circle([lat, lng], {
        radius:      radius,
        color:       color,
        weight:      1.5,
        fillColor:   color,
        fillOpacity: 0.35,
        renderer:    canvasRenderer,
      }).bindTooltip(escH(commonName) + '<br><span style="color:#78909c;font-size:10px">Right-click for options</span>',
          { permanent: false, className: 'plant-marker-label' })
        .addTo(plantLayerGroup);

      // Store metadata on the circle for later use
      circle._pd = { plantId: plantId, commonName: commonName, lat: lat, lng: lng,
                      spacingM: spacingM, plantType: plantType, customColor: customColor,
                      groupId: groupId || null, communityId: communityId || null,
                      markerId: markerId, kind: 'plant' };

      circle.on('click', function(e) {
        L.DomEvent.stop(e);
        if (e.originalEvent && (e.originalEvent.shiftKey || e.originalEvent.ctrlKey || e.originalEvent.metaKey)) {
          toggleSelection(circle._pd);
        } else {
          _cycleDragScope(circle._pd);
          if (bridge) bridge.onPlantMarkerClick(markerId, plantId, lat, lng);
        }
      });

      circle.on('contextmenu', function(e) {
        L.DomEvent.stop(e);
        showPlantContextMenu(e, circle);
      });

      // Drag-to-reposition: a singleton plant moves alone; a plant
      // belonging to a multi-plant placement group (polyculture, burst,
      // grid, row, circle) drags the entire group as a cohesive unit.
      circle.on('mousedown', function(e) { _onPlantMouseDown(circle, e); });

      plantMarkers[markerId] = circle;

      // Add permanent label if labels are turned on
      if (labelsVisible) {
        _addPermanentLabel(markerId, circle, commonName);
      }

      return markerId;
    }

    // Build a right-click menu for a plant marker. Offers single delete,
    // delete-group (when this marker is part of a multi-plant placement),
    // and bulk-delete-selection (when ≥1 plant is selected and this is one
    // of them). Reuses the showContextMenu pattern established by sectors
    // and sun path.
    function showPlantContextMenu(e, circle) {
      var pd = circle._pd;
      var ev = e.originalEvent;
      var items = [];

      // If ≥2 things are selected, surface bulk delete first.
      if (selectedItems.length >= 2 && _selectionContains(pd)) {
        items.push({
          label: 'Delete selected (' + selectedItems.length + ' items)',
          action: function() { deleteSelected(); }
        });
        items.push('sep');
      }

      // Group delete only if this plant belongs to a multi-plant group.
      if (pd.groupId && _groupSize(pd.groupId) >= 2) {
        items.push({
          label: 'Delete group (' + _groupSize(pd.groupId) + ' plants)',
          action: function() { deletePlantGroup(pd.groupId); }
        });
      }

      items.push({
        label: 'Remove this plant',
        action: function() { _removeSinglePlantMarker(pd.markerId); }
      });

      showContextMenu(ev.clientX, ev.clientY, items);
    }

    function _removeSinglePlantMarker(markerId, skipBridge) {
      var circle = plantMarkers[markerId];
      if (!circle) return;
      var pd = circle._pd;
      _clearSelectionEntry(markerId);
      plantLayerGroup.removeLayer(circle);
      if (plantLabels[markerId]) {
        map.removeLayer(plantLabels[markerId]);
        delete plantLabels[markerId];
      }
      delete plantMarkers[markerId];
      // skipBridge lets a batch caller (deleteSelected) collect all removals
      // and notify Python ONCE — a per-plant bridge call re-syncs the planning
      // panel (habitat recompute) each time, which is what made multi-delete lag.
      if (!skipBridge && bridge) bridge.onPlantRemoved(markerId, pd.plantId, pd.lat, pd.lng);
    }

    // Count how many existing markers share a group id.
    function _groupSize(groupId) {
      if (!groupId) return 0;
      var n = 0;
      var keys = Object.keys(plantMarkers);
      for (var i = 0; i < keys.length; i++) {
        var c = plantMarkers[keys[i]];
        if (c._pd && c._pd.groupId === groupId) n++;
      }
      return n;
    }

    // Count how many existing markers share a community-instance id.
    function _communitySize(communityId) {
      if (!communityId) return 0;
      var n = 0;
      var keys = Object.keys(plantMarkers);
      for (var i = 0; i < keys.length; i++) {
        var c = plantMarkers[keys[i]];
        if (c._pd && c._pd.communityId === communityId) n++;
      }
      return n;
    }

    // ── Drag-scope cycling ───────────────────────────────────────────────
    // A placed plant can belong to nested sets: the whole placement grouping
    // (a row/grid/circle of communities or singles), one community instance
    // within that grouping, and the single plant itself. Dragging moves one
    // scope at a time; clicking the plant narrows the scope (broadest first).
    //
    // _scopesFor returns the distinct, non-trivial scopes for a marker,
    // ordered broadest → narrowest. Scopes whose member set duplicates a
    // broader one (e.g. a lone community whose group == community) collapse
    // to a single level.
    function _scopesFor(pd) {
      var scopes = [];
      // Marquee selection (G1) wins first: dragging a plant that's part of a
      // multi-plant selection moves the whole selected set as a unit.
      if (_selectedPlantCount() >= 2 &&
          _selectionContains({ kind: 'plant', markerId: pd.markerId })) {
        scopes.push({ name: 'selection', size: _selectedPlantCount(),
                      label: 'selection' });
      }
      var gSize = pd.groupId ? _groupSize(pd.groupId) : 0;
      var cSize = pd.communityId ? _communitySize(pd.communityId) : 0;
      if (pd.groupId && gSize >= 2) {
        scopes.push({ name: 'group', size: gSize, label: 'whole grouping' });
      }
      // Community only when it is a proper, multi-plant subset of the group,
      // or the only multi-plant scope when there is no broader group.
      if (pd.communityId && cSize >= 2 && (cSize < gSize || gSize < 2)) {
        scopes.push({ name: 'community', size: cSize, label: 'this community' });
      }
      scopes.push({ name: 'plant', size: 1, label: 'this plant' });
      return scopes;
    }

    // Markers belonging to a given scope, relative to an anchor marker's _pd.
    function _markersInScope(pd, scopeName) {
      var out = [];
      var keys = Object.keys(plantMarkers);
      for (var i = 0; i < keys.length; i++) {
        var m = plantMarkers[keys[i]];
        if (!m._pd) continue;
        if (scopeName === 'plant') {
          if (m._pd.markerId === pd.markerId) out.push(m);
        } else if (scopeName === 'selection') {
          if (_selectionContains({ kind: 'plant', markerId: m._pd.markerId }))
            out.push(m);
        } else if (scopeName === 'community') {
          if (pd.communityId && m._pd.communityId === pd.communityId) out.push(m);
        } else if (scopeName === 'group') {
          if (pd.groupId && m._pd.groupId === pd.groupId) out.push(m);
        }
      }
      return out;
    }

    // Cycle state: which marker the scope cycle is anchored to, and where in
    // its scope list we are. A fresh marker starts at the broadest scope.
    var _dragScopeMarkerId = null;
    var _dragScopeIndex = 0;
    var _scopeHighlighted = [];   // markers currently restyled for feedback
    var _scopeAnchorId = null;    // marker whose tooltip shows the scope hint

    function _defaultPlantTooltip(commonName) {
      return escH(commonName) +
        '<br><span style="color:#78909c;font-size:10px">Right-click for options</span>';
    }

    function _clearScopeHighlight() {
      for (var i = 0; i < _scopeHighlighted.length; i++) {
        var m = _scopeHighlighted[i];
        if (m && m.setStyle) m.setStyle({ weight: 1.5, fillOpacity: 0.35 });
      }
      _scopeHighlighted = [];
      if (_scopeAnchorId) {
        var a = plantMarkers[_scopeAnchorId];
        if (a && a._pd && a.setTooltipContent) {
          a.setTooltipContent(_defaultPlantTooltip(a._pd.commonName));
        }
        _scopeAnchorId = null;
      }
    }

    function _applyScopeHighlight(pd, scope) {
      _clearScopeHighlight();
      if (!scope) return;
      var markers = _markersInScope(pd, scope.name);
      for (var i = 0; i < markers.length; i++) {
        if (markers[i].setStyle) {
          markers[i].setStyle({ weight: 3.5, fillOpacity: 0.6 });
        }
      }
      _scopeHighlighted = markers;
      // Name the active scope on the anchor marker's tooltip so the user can
      // see what a drag will move, and that further clicks narrow it.
      var anchor = plantMarkers[pd.markerId];
      if (anchor && anchor.setTooltipContent) {
        var more = _scopesFor(pd).length > 1 ? ' — click to narrow' : '';
        anchor.setTooltipContent(
          escH(pd.commonName) +
          '<br><span style="color:#78909c;font-size:10px">Move: ' +
          escH(scope.label) + ' (' + scope.size +
          (scope.size === 1 ? ' plant' : ' plants') + ')' + more + '</span>'
        );
        _scopeAnchorId = pd.markerId;
      }
    }

    // Advance the scope cycle for a clicked marker and refresh the highlight.
    function _cycleDragScope(pd) {
      var scopes = _scopesFor(pd);
      if (_dragScopeMarkerId === pd.markerId && scopes.length > 1) {
        _dragScopeIndex = (_dragScopeIndex + 1) % scopes.length;
      } else {
        _dragScopeMarkerId = pd.markerId;
        _dragScopeIndex = 0;
      }
      _applyScopeHighlight(pd, scopes[_dragScopeIndex]);
    }

    // ── Drag-to-reposition placed plants ─────────────────────────────────
    // Lazy-arms: a circle's mousedown sets up state but does NOT disable
    // map dragging until the cursor moves past a small pixel threshold.
    // That keeps a plain click → select / context menu working as before
    // and only "becomes a drag" once the user's intent is unambiguous.
    var _plantDragState = null;

    function _onPlantMouseDown(circle, e) {
      // Draggable when idle OR in Select mode (so a box-selected set can be
      // dragged as a unit — see _scopesFor's 'selection' scope).
      if (currentMode !== 'none' && currentMode !== 'select') return;
      var ev = e.originalEvent;
      if (ev && (ev.shiftKey || ev.ctrlKey || ev.metaKey)) return;
      // Left button only — middle/right shouldn't arm a drag.
      if (ev && ev.button !== undefined && ev.button !== 0) return;
      // Stop propagation so the map's panning handler doesn't also see
      // this mousedown. Don't call preventDefault — we still want the
      // click to fire if the user doesn't drag.
      L.DomEvent.stopPropagation(e);
      // L.DomEvent.stopPropagation on a *canvas-layer* Leaflet event only
      // sets originalEvent._stopped = true, which L.Draggable (the map's
      // pan handler) does NOT check — so without the explicit disable
      // below the map starts panning on the same mousedown and races the
      // marker move. Disable for the whole gesture; _onPlantDragEnd
      // re-enables unconditionally (even for a plain click that never
      // armed a drag).
      try { map.dragging.disable(); } catch (_) {}
      _plantDragState = {
        circle:   circle,
        startPx:  e.containerPoint || map.latLngToContainerPoint(e.latlng),
        armed:    false,
        mode:     null,
        groupId:  null,
      };
    }

    function _onPlantDragMove(e) {
      if (!_plantDragState) return;
      var st = _plantDragState;
      var px = e.containerPoint || map.latLngToContainerPoint(e.latlng);
      if (!st.armed) {
        var dx = px.x - st.startPx.x;
        var dy = px.y - st.startPx.y;
        if (dx * dx + dy * dy < 25) return;   // ≤5 px = still a click
        st.armed = true;
        map.dragging.disable();
        var pd = st.circle._pd;
        // Pick the active scope. A marker the user has been clicking uses the
        // cycled scope; a fresh marker starts at the broadest (group) scope.
        var scopes = _scopesFor(pd);
        if (_dragScopeMarkerId !== pd.markerId) {
          _dragScopeMarkerId = pd.markerId;
          _dragScopeIndex = 0;
        }
        if (_dragScopeIndex >= scopes.length) _dragScopeIndex = 0;
        var scope = scopes[_dragScopeIndex];
        st.scopeName = scope.name;
        st.groupId   = pd.groupId;
        // Capture the exact set of markers to move (by id, so the move loop
        // is stable while their positions change underneath it).
        st.memberIds = _markersInScope(pd, scope.name).map(function(m) {
          return m._pd.markerId;
        });
        _applyScopeHighlight(pd, scope);
        // Snapshot original positions so undo can restore them.
        st.originals = [];
        for (var i = 0; i < st.memberIds.length; i++) {
          var sm = plantMarkers[st.memberIds[i]];
          if (!sm || !sm._pd) continue;
          st.originals.push({
            markerId: sm._pd.markerId, plantId: sm._pd.plantId,
            lat: sm._pd.lat, lng: sm._pd.lng,
          });
        }
      }
      // Move every captured member by the same delta, anchored to the dragged
      // marker so it tracks the cursor exactly.
      var prev = st.circle.getLatLng();
      var dlat = e.latlng.lat - prev.lat;
      var dlng = e.latlng.lng - prev.lng;
      for (var j = 0; j < st.memberIds.length; j++) {
        var m = plantMarkers[st.memberIds[j]];
        if (!m || !m._pd) continue;
        var ll = m.getLatLng();
        var newLL = L.latLng(ll.lat + dlat, ll.lng + dlng);
        m.setLatLng(newLL);
        m._pd.lat = newLL.lat;
        m._pd.lng = newLL.lng;
        var lbl = plantLabels[m._pd.markerId];
        if (lbl) lbl.setLatLng(newLL);
      }
    }

    function _onPlantDragEnd(_e) {
      if (!_plantDragState) return;
      var st = _plantDragState;
      _plantDragState = null;
      // Always re-enable map panning — it was disabled in
      // _onPlantMouseDown for the whole gesture, so even a plain click
      // (never armed) must restore it here or the map would freeze.
      try { map.dragging.enable(); } catch (_) {}
      if (!st.armed) return;     // just a click, nothing to commit
      // A completed drag resets the scope cycle — the next fresh interaction
      // starts at the broadest scope again.
      _dragScopeMarkerId = null;
      _dragScopeIndex = 0;
      _clearScopeHighlight();
      // Build the per-marker payload Python needs to update its own state.
      // Mirror the originals list so the receiver can pair old/new positions
      // and push a single undo entry for the whole move.
      var moved = [];
      for (var i = 0; i < st.memberIds.length; i++) {
        var m = plantMarkers[st.memberIds[i]];
        if (!m || !m._pd) continue;
        moved.push({
          markerId: m._pd.markerId, plantId: m._pd.plantId,
          lat: m._pd.lat, lng: m._pd.lng,
        });
      }
      if (st.scopeName === 'selection') {
        // Marquee selection (G1): may span several placement groups, so persist
        // via the group-agnostic handler (matches by plant_id + old-coords).
        if (bridge && bridge.onSelectionMoved) {
          bridge.onSelectionMoved(
            JSON.stringify(st.originals), JSON.stringify(moved)
          );
        }
      } else if (st.memberIds.length >= 2) {
        // Group/community scope. All members share st.groupId, so the Python
        // handler matches each moved feature by plant_id + old-coords +
        // group_id — moving a community subset leaves the rest of the row put.
        if (bridge && bridge.onPlantGroupMoved) {
          bridge.onPlantGroupMoved(
            st.groupId,
            JSON.stringify(st.originals),
            JSON.stringify(moved)
          );
        }
      } else {
        var pd = st.circle._pd;
        if (bridge && bridge.onPlantMoved) {
          var orig = st.originals[0] || {};
          bridge.onPlantMoved(
            pd.markerId, pd.plantId,
            orig.lat || pd.lat, orig.lng || pd.lng,
            pd.lat, pd.lng
          );
        }
      }
    }

    // Delete every plant sharing the given group id. Emits onPlantRemoved
    // per marker so Python state stays consistent without a new bulk slot.
    function deletePlantGroup(groupId) {
      if (!groupId) return;
      var keys = Object.keys(plantMarkers);
      for (var i = 0; i < keys.length; i++) {
        var mid = keys[i];
        var c = plantMarkers[mid];
        if (c._pd && c._pd.groupId === groupId) {
          _removeSinglePlantMarker(mid);
        }
      }
    }

    // Called by Python after a single-click placement so the freshly created
    // marker — which doesn't know its group id at construction time — can be
    // tagged. Picks the most recent marker matching plantId/lat/lng.
    function setPlantGroupForLatest(plantId, lat, lng, groupId) {
      var keys = Object.keys(plantMarkers);
      for (var i = keys.length - 1; i >= 0; i--) {
        var c = plantMarkers[keys[i]];
        if (c._pd && c._pd.plantId === plantId
            && Math.abs(c._pd.lat - lat) < 1e-7
            && Math.abs(c._pd.lng - lng) < 1e-7
            && !c._pd.groupId) {
          c._pd.groupId = groupId;
          return;
        }
      }
    }

    // ── Pattern placement geometry ───────────────────────────────────────────
    // All position helpers return [[lat,lng], ...] arrays.  They are used both
    // by the live preview during placement and by the final commit. Keeping
    // them pure makes them easy to mirror in Python tests.

    // Reset pattern state and remove any preview layers.
    function _resetPatternState() {
      _patternStage = 0;
      _patternAnchors = [];
      if (_patternPreview) { map.removeLayer(_patternPreview); _patternPreview = null; }
    }

    // Build (or rebuild) the live preview layer for the pattern, given the
    // current cursor position. The preview shows where each plant will land
    // as small dashed circles, plus the framing line/rect/circle.
    function _drawPatternPreview(cursorLatLng) {
      if (!currentPlant || !currentPlant.pattern) return;
      var pat = currentPlant.pattern;
      var pp = pat.params || {};
      var s = currentPlant.spacing_m || 1.0;
      var canopyM = currentPlant.mature_canopy_m || (s * 1.5);
      var overlap = (pp.overlap || 0);
      // Reference width that the overlap slider acts against — defaults to
      // planting spacing; flips to mature canopy when the user ticks the
      // "Base on mature canopy" box.
      var ref = pp.use_canopy ? canopyM : s;
      var positions = [];
      var framing = null;

      if (_patternPreview) { map.removeLayer(_patternPreview); _patternPreview = null; }

      if (pat.kind === 'row' && _patternAnchors.length === 1 && cursorLatLng) {
        var a = _patternAnchors[0];
        positions = _rowPositions(a[0], a[1], cursorLatLng.lat, cursorLatLng.lng,
                                  ref, overlap, pp.count);
        framing = L.polyline([a, [cursorLatLng.lat, cursorLatLng.lng]],
                              { color: '#fdd835', weight: 2, dashArray: '4 4', opacity: 0.7 });
      } else if (pat.kind === 'grid' && _patternAnchors.length === 1 && cursorLatLng) {
        var a = _patternAnchors[0];
        positions = _gridPositions(a[0], a[1], cursorLatLng.lat, cursorLatLng.lng,
                                   ref, overlap, pp.rows, pp.cols, pp.stagger);
        var bnds = L.latLngBounds([a, [cursorLatLng.lat, cursorLatLng.lng]]);
        framing = L.rectangle(bnds, { color: '#fdd835', weight: 2, dashArray: '4 4',
                                       fill: false, opacity: 0.7 });
      } else if (pat.kind === 'circle' && _patternAnchors.length === 1 && cursorLatLng) {
        var c = _patternAnchors[0];
        var radiusM = _haversineM(c, [cursorLatLng.lat, cursorLatLng.lng]);
        positions = _circlePositions(c[0], c[1], radiusM, ref, overlap, pp.count, pp.fill);
        framing = L.circle(c, { radius: radiusM, color: '#fdd835', weight: 2,
                                 dashArray: '4 4', fill: false, opacity: 0.7 });
      }

      var preview = L.layerGroup();
      if (framing) framing.addTo(preview);
      // Two concentric ghost rings per position: inner = planting spacing
      // (yellow, dashed), outer = mature canopy width (green, sparser dash).
      // The outer ring shows how big each plant will be at maturity so the
      // user can see in advance whether neighbours will compete.
      var spacingRadius = Math.max(s / 2, 0.5);
      var canopyRadius = Math.max(canopyM / 2, spacingRadius);
      positions.forEach(function(p) {
        L.circle(p, { radius: canopyRadius, color: '#a5d6a7', weight: 1,
                      dashArray: '4 5', fill: false, opacity: 0.7,
                      interactive: false }).addTo(preview);
        L.circle(p, { radius: spacingRadius, color: '#fdd835', weight: 1,
                      dashArray: '2 3', fillColor: '#fdd835', fillOpacity: 0.15,
                      interactive: false }).addTo(preview);
      });
      // Floating count badge near the cursor while previewing.
      if (cursorLatLng && positions.length > 0) {
        var label = L.tooltip({ permanent: true, direction: 'right', offset: [10, 0],
                                 className: 'measure-label', opacity: 0.9 })
                     .setContent(positions.length + ' plants')
                     .setLatLng(cursorLatLng);
        label.addTo(preview);
      }
      preview.addTo(map);
      _patternPreview = preview;
    }

    // Handle a click in plant mode when a pattern is active. Each pattern
    // takes 2 clicks; the second click commits and emits onPatternPlaced.
    function _handlePatternClick(lat, lng) {
      if (!currentPlant || !currentPlant.pattern) return;
      var pat = currentPlant.pattern;
      var pp = pat.params || {};
      _patternAnchors.push([lat, lng]);
      _patternStage = _patternAnchors.length;

      if (_patternStage < 2) {
        // First click captured — preview will follow the cursor.
        return;
      }

      // Two anchors collected — compute final positions and commit.
      var s = currentPlant.spacing_m || 1.0;
      var canopyM = currentPlant.mature_canopy_m || (s * 1.5);
      var overlap = pp.overlap || 0;
      var ref = pp.use_canopy ? canopyM : s;
      var a = _patternAnchors[0], b = _patternAnchors[1];
      var positions = [];
      if (pat.kind === 'row') {
        positions = _rowPositions(a[0], a[1], b[0], b[1], ref, overlap, pp.count);
      } else if (pat.kind === 'grid') {
        positions = _gridPositions(a[0], a[1], b[0], b[1], ref, overlap,
                                   pp.rows, pp.cols, pp.stagger);
      } else if (pat.kind === 'circle') {
        var radiusM = _haversineM(a, b);
        positions = _circlePositions(a[0], a[1], radiusM, ref, overlap, pp.count, pp.fill);
      }

      _resetPatternState();

      if (positions.length > 0 && bridge) {
        bridge.onPatternPlaced(currentPlant.id, currentPlant.common_name,
                               currentPlant.spacing_m, currentPlant.plant_type,
                               currentPlant.custom_color || '',
                               JSON.stringify(positions), pat.kind);
      }
    }

    function _metersToLat(m) { return m / 111320; }
    function _metersToLng(m, lat) { return m / (111320 * Math.cos(lat * Math.PI / 180)); }

    function _haversineM(a, b) { return haversineMeters(a, b); }

    // Effective centre-to-centre spacing after applying overlap factor.
    // overlapFactor is in [-0.5..0.5]:
    //   negative = extra gap (sparser)
    //   zero     = centres exactly spacingM apart (canopies touch)
    //   positive = canopies overlap (denser)
    // Floors at 1cm to avoid div-by-zero / negative spacings.
    function _effectiveSpacing(spacingM, overlapFactor) {
      var s = (spacingM || 1.0) * (1.0 - (overlapFactor || 0));
      return Math.max(s, 0.01);
    }

    // Linear interpolation along a great-circle approximation between two
    // (lat,lng) anchors. Suitable for the ≤200m row lengths we care about.
    function _rowPositions(latA, lngA, latB, lngB, spacingM, overlapFactor, count) {
      var aLat = latA, aLng = lngA, bLat = latB, bLng = lngB;
      var len = _haversineM([aLat, aLng], [bLat, bLng]);
      var s = _effectiveSpacing(spacingM, overlapFactor);
      var n;
      if (count && count > 0) {
        n = Math.max(2, Math.floor(count));
      } else {
        n = Math.max(2, Math.floor(len / s) + 1);
      }
      var positions = [];
      if (n === 1) return [[aLat, aLng]];
      for (var i = 0; i < n; i++) {
        var t = i / (n - 1);
        positions.push([aLat + (bLat - aLat) * t, aLng + (bLng - aLng) * t]);
      }
      return positions;
    }

    // Grid filling the rectangle whose corners are (latA,lngA) and (latB,lngB).
    // If rows or cols are provided they override the spacing-derived count.
    // stagger=true offsets every other row by half the column step (hex pack).
    function _gridPositions(latA, lngA, latB, lngB, spacingM, overlapFactor, rows, cols, stagger) {
      var s = _effectiveSpacing(spacingM, overlapFactor);
      var minLat = Math.min(latA, latB), maxLat = Math.max(latA, latB);
      var minLng = Math.min(lngA, lngB), maxLng = Math.max(lngA, lngB);
      var midLat = (minLat + maxLat) / 2;
      var widthM  = _haversineM([midLat, minLng], [midLat, maxLng]);
      var heightM = _haversineM([minLat, minLng], [maxLat, minLng]);
      var nCols = (cols && cols > 0) ? Math.max(1, Math.floor(cols))
                                     : Math.max(1, Math.floor(widthM / s) + 1);
      var nRows = (rows && rows > 0) ? Math.max(1, Math.floor(rows))
                                     : Math.max(1, Math.floor(heightM / s) + 1);
      var positions = [];
      var dLat = nRows > 1 ? (maxLat - minLat) / (nRows - 1) : 0;
      var dLng = nCols > 1 ? (maxLng - minLng) / (nCols - 1) : 0;
      for (var r = 0; r < nRows; r++) {
        var rowLat = minLat + dLat * r;
        var offset = (stagger && (r % 2 === 1)) ? dLng / 2 : 0;
        for (var c = 0; c < nCols; c++) {
          var colLng = minLng + dLng * c + offset;
          if (colLng > maxLng + 1e-9) continue; // staggered last column may overflow
          positions.push([rowLat, colLng]);
        }
      }
      return positions;
    }

    // Plants arranged on (or inside) a circle of radius `radiusM`.
    //   fill=false → perimeter only (a single ring of `count` or
    //                spacing-derived plants).
    //   fill=true  → honeycomb hex-pack inside the disc: every plant
    //                has six equidistant neighbours at exactly `s`,
    //                packing density ~91% (vs ~78% for square grids).
    //                Centre plant is always first in the result.
    function _circlePositions(centerLat, centerLng, radiusM, spacingM, overlapFactor, count, fill) {
      var s = _effectiveSpacing(spacingM, overlapFactor);
      if (fill) {
        var disc = _hexPackedDisc(centerLat, centerLng, radiusM, s);
        // When the user supplies an explicit count, cap the disc to
        // exactly that many plants — closest-to-centre wins. Without
        // the cap, large radii at small spacings can produce thousands
        // of markers and stall the renderer.
        if (count && count > 0 && disc.length > count) {
          var n = Math.max(1, Math.floor(count));
          // disc is already centre-first then row-by-row, but we sort
          // by squared distance from centre so the truncated set is a
          // clean shrinking sub-disc rather than a chopped stripe.
          var cosLat = Math.cos(centerLat * Math.PI / 180);
          disc.sort(function (a, b) {
            var ax = (a[1] - centerLng) * 111320 * cosLat;
            var ay = (a[0] - centerLat) * 111320;
            var bx = (b[1] - centerLng) * 111320 * cosLat;
            var by = (b[0] - centerLat) * 111320;
            return (ax*ax + ay*ay) - (bx*bx + by*by);
          });
          return disc.slice(0, n);
        }
        return disc;
      }
      // Perimeter-only ring.
      var positions = [];
      var circumference = 2 * Math.PI * radiusM;
      var n = (count && count > 0) ? Math.max(3, Math.floor(count))
                                   : Math.max(3, Math.floor(circumference / s));
      for (var k = 0; k < n; k++) {
        var theta = (2 * Math.PI * k) / n;
        var dLat = _metersToLat(radiusM * Math.cos(theta));
        var dLng = _metersToLng(radiusM * Math.sin(theta), centerLat);
        positions.push([centerLat + dLat, centerLng + dLng]);
      }
      return positions;
    }

    // Honeycomb-style hex pack inside a disc of radius `radiusM`. Rows
    // are at y = r * s * sqrt(3)/2; odd rows shift x by s/2 so every
    // plant has six equidistant neighbours. The centre plant is
    // emitted first so callers (and tests) can rely on it being there.
    function _hexPackedDisc(centerLat, centerLng, radiusM, spacingM) {
      var s = spacingM;
      var rowSpacing = s * Math.sqrt(3) / 2;
      var maxRow = Math.ceil(radiusM / rowSpacing) + 1;
      var maxCol = Math.ceil(radiusM / s) + 1;
      var r2 = radiusM * radiusM + 1e-3;   // tolerance for boundary
      var positions = [[centerLat, centerLng]];
      for (var rIdx = -maxRow; rIdx <= maxRow; rIdx++) {
        var y = rIdx * rowSpacing;
        var rowOffset = (rIdx & 1) ? s / 2 : 0;
        for (var cIdx = -maxCol; cIdx <= maxCol; cIdx++) {
          var x = cIdx * s + rowOffset;
          if (x * x + y * y <= r2) {
            // Skip the (0, 0) cell — already added as the centre.
            if (Math.abs(x) < 1e-6 && Math.abs(y) < 1e-6) continue;
            positions.push([
              centerLat + _metersToLat(y),
              centerLng + _metersToLng(x, centerLat),
            ]);
          }
        }
      }
      return positions;
    }

    // Compute a hex burst pattern of `quantity` positions centred at
    // (lat, lng) with `spacing` metres between adjacent plants. Used by
    // the legacy Qty>1 single-click placement.
    function _hexBurstPositions(lat, lng, spacing, quantity) {
      var s = spacing || 1.0;
      var positions = [[lat, lng]];
      var ring = 0;
      while (positions.length < quantity) {
        ring++;
        for (var side = 0; side < 6; side++) {
          for (var step = 0; step < ring; step++) {
            if (positions.length >= quantity) break;
            var angle = (side * 60 + step * (60 / ring)) * Math.PI / 180;
            var dLat = (ring * s * Math.cos(angle)) / 111320;
            var dLng = (ring * s * Math.sin(angle)) / (111320 * Math.cos(lat * Math.PI / 180));
            positions.push([lat + dLat, lng + dLng]);
          }
        }
      }
      return positions.slice(0, quantity);
    }

    // ── Label management ──────────────────────────────────────────────────────
    function _addPermanentLabel(markerId, circle, name) {
      var label = L.tooltip({
        permanent: true,
        direction: 'top',
        offset: [0, -8],
        className: 'plant-marker-label',
        opacity: 0.9
      }).setContent(escH(name)).setLatLng(circle.getLatLng());
      label.addTo(map);
      plantLabels[markerId] = label;
    }

    function setLabelsVisible(visible) {
      labelsVisible = visible;
      updateLabelVisibility();
    }

    function updateLabelVisibility() {
      var zoom = map.getZoom();
      var shouldShow = labelsVisible && zoom >= 18;
      if (shouldShow) {
        // Add permanent labels to all existing markers
        Object.keys(plantMarkers).forEach(function(mid) {
          if (!plantLabels[mid]) {
            var c = plantMarkers[mid];
            _addPermanentLabel(mid, c, c._pd ? c._pd.commonName : '');
          }
        });
      } else {
        // Remove all permanent labels from map (keep refs if labels still toggled on)
        Object.keys(plantLabels).forEach(function(mid) {
          map.removeLayer(plantLabels[mid]);
        });
        if (!labelsVisible) plantLabels = {};
      }
    }

    // ── Update marker colour (called from Python) ─────────────────────────────
    function updateMarkerColor(plantId, newColor) {
      Object.keys(plantMarkers).forEach(function(mid) {
        var c = plantMarkers[mid];
        if (c._pd && c._pd.plantId === plantId) {
          c.setStyle({ color: newColor, fillColor: newColor });
          c._pd.customColor = newColor;
        }
      });
    }

    function metresToLng(metres, lat) {
      return (metres / 111320) / Math.cos(lat * Math.PI / 180);
    }

