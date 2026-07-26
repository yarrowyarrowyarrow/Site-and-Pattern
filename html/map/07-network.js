// html/map/07-network.js — the relationship web overlay (F5).
//
// Classic script, loaded after 06-overlays.js by map.html — same shared-global
// model as the rest of html/map/*.js (see the header of 01-core.js). Split into
// its own file rather than grown onto 06-overlays.js because that file is the
// terrain/shade/wind chunk and was already the largest of the six; the guard in
// tests/test_architecture_guard.py exists to make that the reflex.
//
// This renderer is deliberately dumb. Every position, bearing, ring radius,
// colour and weight arrives precomputed from src/relationship_graph.py — the
// map JS decides nothing about the ecology, it only draws what Python worked
// out. Payload shape: {nodes, edges, legend, ring, stats}.

    var relationshipLayer = null;     // L.layerGroup — edges + nodes
    var _relGraph = null;             // last payload (for hover recolouring)
    var _relEdgeLines = [];           // {line, a, b} parallel to payload.edges

    // Edges live in their own pane below markers so the web never swallows a
    // click meant for a plant.
    function _relPane() {
      if (!map.getPane('relationshipPane')) {
        var p = map.createPane('relationshipPane');
        p.style.zIndex = 385;
      }
      return 'relationshipPane';
    }

    function _relEdgeStyle(e, focused) {
      // Strength drives weight, evidence drives the dash: a derived link (two
      // plants that feed the same animal) must never look like a seeded record.
      var w = 1 + 3.2 * (typeof e.strength === 'number' ? e.strength : 0.5);
      return {
        color: e.color || '#8bc34a',
        weight: focused === false ? Math.max(0.8, w * 0.5) : w,
        opacity: focused === false ? 0.12 : (e.evidence === 'derived' ? 0.5 : 0.8),
        dashArray: e.evidence === 'derived' ? '4,5' : null,
        interactive: true,
        pane: _relPane()
      };
    }

    function _relNodeMarker(n) {
      if (n.type === 'fauna') {
        // An animal's spot is a diagram, not a location — drawn as a labelled
        // chip on the ring, visually unlike a planted thing. `anchor` (Python
        // side) hangs the label outward from the ring so the text does not
        // straddle the lines converging on its point.
        var named = !!n.named;
        var cls = 'rel-fauna-chip rel-anchor-' + (n.anchor === 'left' ? 'l' : 'r')
                + (n.specialist ? ' rel-specialist' : '')
                + (named ? '' : ' rel-compact');
        var html = '<span class="' + cls + '">' + (n.mark || '•') +
                   (named ? ' ' + escH(n.label || '') : '') +
                   (named && n.only_source ? ' <b>!</b>' : '') + '</span>';
        return L.marker([n.lat, n.lng], {
          icon: L.divIcon({ className: 'rel-fauna-icon', html: html,
                            iconSize: null }),
          interactive: true, keyboard: false, pane: _relPane()
        });
      }
      // A plant node is a halo around the marker already on the map — the
      // species' hub, sized by how many of it are planted.
      var r = 7 + Math.min(9, 1.6 * Math.sqrt(Math.max(1, n.count || 1)))
                + Math.min(8, 0.7 * (n.degree || 0));
      return L.circleMarker([n.lat, n.lng], {
        radius: r,
        color: (n.degree ? '#c5e1a5' : '#78909c'),
        weight: 2,
        fillColor: '#1b5e20',
        fillOpacity: n.degree ? 0.22 : 0.08,
        pane: _relPane()
      });
    }

    function _relNodeTooltip(n) {
      if (n.type === 'fauna') {
        var bits = [escH(n.label || '')];
        if (n.scientific_name) bits.push('<i>' + escH(n.scientific_name) + '</i>');
        bits.push(n.count + ' plant' + (n.count === 1 ? '' : 's') + ' here support it');
        if (n.specialist) bits.push('<b>specialist</b> — nowhere else to go');
        if (n.only_source) bits.push('<b>only one source in this design</b>');
        return bits.join('<br>');
      }
      var t = ['<b>' + escH(n.label || '') + '</b>'];
      if (n.count > 1) t.push(n.count + ' planted');
      t.push(n.degree ? n.degree + ' relationship' + (n.degree === 1 ? '' : 's')
                      : 'no recorded relationships yet');
      return t.join('<br>');
    }

    // Hovering a node fades everything it does not touch, so a single web
    // becomes readable one species at a time.
    function _relSetFocus(nodeId) {
      for (var i = 0; i < _relEdgeLines.length; i++) {
        var rec = _relEdgeLines[i];
        var on = !nodeId || rec.a === nodeId || rec.b === nodeId;
        rec.line.setStyle(_relEdgeStyle(rec.edge, nodeId ? on : true));
      }
    }

    function _relLegend(payload) {
      var el = document.getElementById('rel-web-legend');
      if (!payload) { if (el) el.style.display = 'none'; return; }
      if (!el) {
        el = document.createElement('div');
        el.id = 'rel-web-legend';
        el.style.cssText = 'position:absolute;right:10px;bottom:12px;z-index:1000;' +
          'max-width:250px;font-family:system-ui,sans-serif;font-size:11px;' +
          'color:#dcedc8;background:rgba(20,32,22,.94);border:1px solid #3e5c3e;' +
          'border-radius:8px;padding:7px 10px;line-height:1.6;' +
          'pointer-events:none;box-shadow:0 1px 6px rgba(0,0,0,.4);';
        document.body.appendChild(el);
      }
      var rows = (payload.legend || []).map(function(l) {
        return '<span style="display:inline-block;width:16px;height:0;' +
               'border-top:3px solid ' + l.color + ';vertical-align:middle;' +
               'margin-right:5px;"></span>' + escH(l.label) + ' <span ' +
               'style="color:#8fa68f;">' + l.count + '</span>';
      });
      var s = payload.stats || {};
      var foot = '<div style="margin-top:5px;padding-top:5px;' +
        'border-top:1px solid #3e5c3e;color:#a5c8a5;">' +
        'Animals sit on a ring — a diagram, not a place.';
      if (s.derived_edges) foot += '<br>Dashed = inferred, not a record.';
      if (s.dropped_fauna) {
        foot += '<br>' + s.dropped_fauna + ' more supported species not drawn.';
      }
      foot += '</div>';
      el.innerHTML = '<b>🕸 Relationship web</b><br>' + rows.join('<br>') + foot;
      el.style.display = 'block';
    }

    function _relEnsureStyles() {
      if (document.getElementById('rel-web-style')) return;
      var st = document.createElement('style');
      st.id = 'rel-web-style';
      st.textContent =
        '.rel-fauna-icon { background: none; border: none; }' +
        '.rel-fauna-chip { display:inline-block; white-space:nowrap;' +
        ' font-family:system-ui,sans-serif; font-size:11px; color:#e8f5e9;' +
        ' background:rgba(20,32,22,.92); border:1px solid #4a7a4a;' +
        ' border-radius:10px; padding:1px 7px;' +
        ' box-shadow:0 1px 3px rgba(0,0,0,.45); }' +
        '.rel-fauna-chip.rel-anchor-r { transform:translate(2px,-50%); }' +
        '.rel-fauna-chip.rel-anchor-l { transform:translate(-100%,-50%);' +
        ' margin-left:-2px; }' +
        '.rel-fauna-chip.rel-compact { padding:1px 4px; }' +
        '.rel-fauna-chip.rel-specialist { border-color:#ffb300; color:#fff8e1; }';
      document.head.appendChild(st);
    }

    // ── Entry points (src/map_js.py) ────────────────────────────────────────

    function drawRelationshipGraph(payload) {
      clearRelationshipGraph();
      if (!payload || !payload.nodes || !payload.nodes.length) return;
      _relEnsureStyles();
      _relGraph = payload;
      relationshipLayer = L.layerGroup().addTo(map);

      // The rings themselves, so "outside the planting" reads as deliberate.
      // A crowded design uses several concentric lanes so the chips do not
      // collide — Python decides how many.
      var ring = payload.ring;
      if (ring && ring.radius_m) {
        for (var k = 0; k < Math.max(1, ring.lanes || 1); k++) {
          L.circle([ring.lat, ring.lng], {
            radius: ring.radius_m + k * (ring.lane_step_m || 0),
            color: '#4a7a4a', weight: 1,
            opacity: 0.45 - 0.08 * k, fill: false, dashArray: '2,7',
            interactive: false, pane: _relPane()
          }).addTo(relationshipLayer);
        }
      }

      var edges = payload.edges || [];
      for (var i = 0; i < edges.length; i++) {
        var e = edges[i];
        var line = L.polyline([[e.a_lat, e.a_lng], [e.b_lat, e.b_lng]],
                              _relEdgeStyle(e, true));
        var tip = escH(e.phrase || e.label || '');
        if (e.specialist) tip += ' <b>(specialist)</b>';
        if (e.evidence === 'derived') tip += '<br><i>inferred, not a record</i>';
        if (e.detail && e.evidence === 'derived') tip += '<br>' + escH(e.detail);
        line.bindTooltip(tip, { sticky: true, direction: 'top' });
        line.addTo(relationshipLayer);
        _relEdgeLines.push({ line: line, edge: e, a: e.a, b: e.b });
      }

      var nodes = payload.nodes || [];
      for (var j = 0; j < nodes.length; j++) {
        var n = nodes[j];
        var m = _relNodeMarker(n);
        m.bindTooltip(_relNodeTooltip(n), { direction: 'top', sticky: true });
        (function(id) {
          m.on('mouseover', function() { _relSetFocus(id); });
          m.on('mouseout', function() { _relSetFocus(null); });
        })(n.id);
        m.addTo(relationshipLayer);
      }
      _relLegend(payload);
    }

    function setRelationshipGraphVisible(visible) {
      if (!relationshipLayer) return;
      if (visible) { relationshipLayer.addTo(map); _relLegend(_relGraph); }
      else { map.removeLayer(relationshipLayer); _relLegend(null); }
    }

    function clearRelationshipGraph() {
      if (relationshipLayer) { map.removeLayer(relationshipLayer); }
      relationshipLayer = null;
      _relEdgeLines = [];
      _relGraph = null;
      _relLegend(null);
    }
