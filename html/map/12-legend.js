// html/map/12-legend.js — the legend names what is on the map, at the detail
// asked for (F217, V3.11).
//
// Classic script, loaded last by map.html: the shared-global model of
// html/map/*.js (see the header of 01-core.js). Nothing here runs at load but
// declarations, so node can load it (tests/test_legend.py).
//
// Until V3.11 the legend was a fixed list: every entry showed whether or not
// anything of its kind was drawn, the plant section named all eleven types, and
// the Structures section was not true (category colours no structure is drawn
// in, and an "Animal" category that no longer exists). The owner: "hiding
// anything from the legend that does not appear on the map", and two degrees of
// detail: boundaries simple or by the names they are given, plants by type or
// by species.
//
// Three parts:
//   legendModel(snap, detail)  what to say, from a plain snapshot      (pure)
//   legendHtml(sections)       how it reads                             (pure)
//   legendSnapshot()           the map, read into that snapshot
// then the page's side: the switches, a click that names boundaries, and the
// species numbers drawn on the plants while the legend is open in Species.

    var legendDetail = { plants: 'type', boundaries: 'simple' };
    var _legendTimer = null;
    var _legendTargets = [];      // what each Named boundary line names
    var _speciesNumberLayer = null;
    var _numberFollow = [];       // [circle, handler]: numbers follow a drag

    var _LEGEND_SWITCHES = {
      plants: [['type', 'Type'], ['species', 'Species']],
      boundaries: [['simple', 'Simple'], ['named', 'Named']]
    };
    var _HEDGE_WORDS = { hedge: 'Hedge', fence: 'Fence',
                         living_fence: 'Living fence', windbreak: 'Windbreak' };
    // A number is drawn on a plant only when the plant is at least this wide on
    // screen; smaller, the number would hide it. Zoom in to read them.
    var _NUMBER_MIN_RADIUS_PX = 7;

    // Text and attribute escaping without the DOM, so node can run it.
    function _esc(s) {
      return String(s === null || s === undefined ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    // A colour from a design file goes into a style attribute, so only a
    // colour gets through: #hex or a plain word.
    function _colour(c) {
      c = String(c || '');
      return /^#[0-9a-fA-F]{3,8}$/.test(c) || /^[a-zA-Z]{3,20}$/.test(c) ? c : '#888888';
    }

    // The printed planting plan's numbers (src/planting_map.py _numbering, and
    // so the buy list's): by common name, lower-cased, then plant id. A test
    // runs this against Python's.
    function speciesNumbers(plants) {
      var names = {}, ids = [];
      plants.forEach(function (p) {
        if (Object.prototype.hasOwnProperty.call(names, p.id)) return;
        names[p.id] = String(p.name || '').toLowerCase();
        ids.push(p.id);
      });
      ids.sort(function (a, b) {
        if (names[a] !== names[b]) return names[a] < names[b] ? -1 : 1;
        return a < b ? -1 : (a > b ? 1 : 0);
      });
      var out = {};
      ids.forEach(function (id, i) { out[id] = i + 1; });
      return out;
    }

    function _uniqBy(list, key) {
      var seen = {};
      return list.filter(function (x) {
        var k = key(x);
        if (seen[k]) return false;
        seen[k] = true;
        return true;
      });
    }

    function _plantItems(snap, how) {
      var plants = snap.plants || [], items = [];
      if (how === 'species') {
        var nums = speciesNumbers(plants), first = {}, count = {};
        plants.forEach(function (p) {
          if (!first[p.id]) first[p.id] = p;
          count[p.id] = (count[p.id] || 0) + 1;
        });
        Object.keys(first).sort(function (a, b) { return nums[a] - nums[b]; })
          .forEach(function (id) {
            items.push({ swatch: { kind: 'plant', colour: first[id].colour },
                         label: first[id].name, num: nums[id], count: count[id] });
          });
      } else {
        var typed = {}, own = [];
        plants.forEach(function (p) {
          if (p.custom) own.push(p);
          else if (!typed[p.type]) typed[p.type] = p.colour;
        });
        TYPE_WORDS.forEach(function (pair) {               // 10-plant-key.js
          if (!typed[pair[0]]) return;
          items.push({ swatch: { kind: 'plant', colour: typed[pair[0]] }, label: pair[1] });
          delete typed[pair[0]];
        });
        Object.keys(typed).forEach(function (t) {          // a type it does not name
          items.push({ swatch: { kind: 'plant', colour: typed[t] }, label: t || 'Plant' });
        });
        // A colour you gave a plant is explained by no type: its name says it.
        _uniqBy(own, function (p) { return p.name + '|' + p.colour; }).forEach(function (p) {
          items.push({ swatch: { kind: 'plant', colour: p.colour }, label: p.name });
        });
      }
      if (items.length && snap.canopy) {
        items.push({ swatch: { kind: 'ring', colour: '#a5d6a7' },
                     label: 'Mature spread (Canopy view)' });
      }
      return items;
    }

    function _boundaryItems(list, how) {
      if (!list.length) return [];
      if (how !== 'named') {
        // One line for any number of boundaries, a swatch per colour in use.
        return [{ swatches: _uniqBy(list, function (b) { return b.colour; })
                    .map(function (b) { return { kind: 'area', colour: b.colour }; }),
                  label: 'Boundary' }];
      }
      // A line per colour and name; a click on one names every boundary on it.
      var lines = {}, order = [];
      list.forEach(function (b) {
        var k = b.colour + '|' + (b.name || '');
        if (!lines[k]) {
          lines[k] = { swatch: { kind: 'area', colour: b.colour },
                       label: b.name || 'Boundary', name: b.name || '', ids: [] };
          order.push(k);
        }
        lines[k].ids.push(b.id);
      });
      return order.map(function (k) { return lines[k]; });
    }

    // What the legend says. `snap` is plain data (legendSnapshot, or a test):
    //   plants      [{id, name, type, colour, custom}], one per drawn plant
    //   canopy      the Canopy view's rings are drawn
    //   boundaries  [{id, name, colour}], shown ones, in drawing order
    //   structures  [{name, icon, stroke, fill, round}]
    //   hedgerows   [{label, colour, dashed}]
    //   shapes      [{label, stroke, fill, dashed, casts}]
    //   measurements  how many are shown
    //   analysis    {sun, shade, contour (its colour), wind}
    // Sections in order, each {key, title, items, options?, value?}; empty ones
    // are left out, so nothing is named that is not drawn.
    function legendModel(snap, detail) {
      snap = snap || {};
      detail = detail || legendDetail;
      var out = [];
      function add(key, title, items, sw) {
        if (!items.length) return;
        var s = { key: key, title: title, items: items };
        if (sw) { s.options = _LEGEND_SWITCHES[key]; s.value = detail[key]; }
        out.push(s);
      }
      add('plants', 'Plants', _plantItems(snap, detail.plants), true);
      add('boundaries', 'Boundaries', _boundaryItems(snap.boundaries || [], detail.boundaries), true);
      add('structures', 'Structures', _uniqBy(snap.structures || [], function (s) {
        return s.icon + s.name + '|' + s.fill + '|' + s.stroke;
      }).map(function (s) {
        return { swatch: { kind: s.round ? 'dot' : 'area', colour: s.fill, edge: s.stroke },
                 label: (s.icon ? s.icon + ' ' : '') + s.name };
      }));
      var other = _uniqBy(snap.hedgerows || [], function (h) {
        return h.label + '|' + h.colour + '|' + h.dashed;
      }).map(function (h) {
        return { swatch: { kind: 'line', colour: h.colour, dashed: h.dashed }, label: h.label };
      }).concat(_uniqBy(snap.shapes || [], function (s) {
        return s.label + '|' + s.stroke + '|' + s.fill + '|' + s.casts;
      }).map(function (s) {
        return { swatch: { kind: 'area', colour: s.fill, edge: s.stroke, dashed: s.dashed },
                 label: s.casts ? s.label + ', casts shade' : s.label };
      }));
      if (snap.measurements) {
        other.push({ swatch: { kind: 'line', colour: '#fdd835', dashed: true }, label: 'Measurement' });
      }
      add('other', 'Other', other);
      var a = snap.analysis || {}, an = [];
      if (a.sun) an.push({ swatch: { kind: 'dot', colour: '#ffb300' }, label: 'Sun path' });
      if (a.shade) an.push({ swatch: { kind: 'dot', colour: '#455a64' }, label: 'Shadow' });
      if (a.contour) an.push({ swatch: { kind: 'line', colour: a.contour }, label: 'Contour' });
      if (a.wind) an.push({ swatch: { kind: 'dot', colour: '#42a5f5' }, label: 'Wind' });
      add('analysis', 'Analysis', an);
      return out;
    }

    function _swatchHtml(sw) {
      var c = _colour(sw.colour), edge = sw.edge ? _colour(sw.edge) : c;
      var line = sw.dashed ? 'dashed' : 'solid', cls = 'legend-swatch', st;
      if (sw.kind === 'plant') {
        st = 'background:' + c + ';border:2px solid ' + markerEdge(c);   // 10-plant-key.js
      } else if (sw.kind === 'ring') {
        cls += ' outline-only'; st = 'border-color:' + c;
      } else if (sw.kind === 'line') {
        cls += ' legend-line'; st = 'border-top:3px ' + line + ' ' + c;
      } else if (sw.kind === 'area') {
        cls += ' legend-area';
        st = 'background:' + (/^#[0-9a-fA-F]{6}$/.test(c) ? c + '59' : c) +
             ';border:2px ' + line + ' ' + edge;
      } else {
        st = 'background:' + c + ';border:2px solid ' + edge;
      }
      return '<span class="' + cls + '" style="' + st + '"></span>';
    }

    // The legend's body, from legendModel's sections. A Named boundary line is
    // a button carrying `data-item`, its index in `targets` (filled here).
    function legendHtml(sections, targets) {
      targets = targets || [];
      if (!sections.length) return '<div class="legend-note">Nothing on the map yet.</div>';
      return sections.map(function (s) {
        var h = '<div class="legend-section" data-section="' + s.key + '">' +
                '<div class="legend-section-title"><span>' + _esc(s.title) + '</span>';
        if (s.options) {
          h += '<span class="legend-switch" role="group" aria-label="' +
               _esc(s.title + ' in the legend') + '">';
          s.options.forEach(function (o) {
            h += '<button type="button" data-legend="' + s.key + '" data-value="' + o[0] +
                 '" aria-pressed="' + (o[0] === s.value) + '">' + o[1] + '</button>';
          });
          h += '</span>';
        }
        h += '</div>';
        s.items.forEach(function (it) {
          var sw = (it.swatches || [it.swatch]).map(_swatchHtml).join('');
          var text = (it.num ? '<b class="legend-num">' + it.num + '</b> ' : '') +
                     _esc(it.label) +
                     (it.count ? ' <span class="legend-count">×' + it.count + '</span>' : '');
          if (it.ids) {
            targets.push({ ids: it.ids, name: it.name });
            h += '<button type="button" class="legend-item legend-name" data-item="' +
                 (targets.length - 1) + '" title="Name it" aria-label="' +
                 _esc('Name it: ' + it.label) + '">' + sw + '<span>' + text +
                 '</span><span class="legend-edit" aria-hidden="true">✎</span></button>';
          } else {
            h += '<div class="legend-item">' + sw + '<span>' + text + '</span></div>';
          }
        });
        return h + '</div>';
      }).join('');
    }

    // ── The page's side ─────────────────────────────────────────────────────

    function _shown(layer) { return !!layer && map.hasLayer(layer); }

    function _firstColour(group) {
      var c = null;
      if (group && group.eachLayer) {
        group.eachLayer(function (l) {
          if (!c && l.options && l.options.color) c = l.options.color;
          if (!c && l.eachLayer) c = _firstColour(l);
        });
      }
      return c;
    }

    // What is on the map now, and shown, as legendModel's plain snapshot.
    function legendSnapshot() {
      var s = { plants: [], canopy: false, boundaries: [], structures: [],
                hedgerows: [], shapes: [], measurements: 0, analysis: {} };
      if (_shown(plantLayerGroup)) {
        Object.keys(plantMarkers).forEach(function (mid) {
          var pd = plantMarkers[mid]._pd;
          if (!pd) return;
          var colour = plantColour(pd), typed = plantColour({ plantType: pd.plantType });
          s.plants.push({ id: pd.plantId, name: pd.commonName || '', type: pd.plantType || '',
                          colour: colour, custom: colour.toLowerCase() !== typed.toLowerCase() });
        });
        s.canopy = !!canopyVisible && _shown(canopyGroup);
      }
      boundaries.forEach(function (b) {
        if (!_shown(b.layer)) return;
        s.boundaries.push({ id: b.id, name: b.name || '',
                            colour: (BOUNDARY_COLORS[b.color] || BOUNDARY_COLORS.green).stroke });
      });
      Object.keys(structureMarkers).forEach(function (k) {
        if (!_shown(structureMarkers[k])) return;
        structureMarkers[k].eachLayer(function (l) {
          if (!l._struct) return;
          var o = l.options, name = l._struct.name, icon = l._struct.icon || '';
          if (l._struct.structId === 'existing_tree') {       // 05-features.js
            ['evergreen', 'deciduous'].forEach(function (f) {
              if (o.fillColor !== _FOLIAGE_STYLE[f].fill) return;
              icon = _FOLIAGE_STYLE[f].icon;
              name += f === 'evergreen' ? ', coniferous' : ', deciduous';
            });
          }
          s.structures.push({ name: name, icon: icon, stroke: o.color,
                              fill: o.fillColor || o.color, round: !!l.getRadius });
        });
      });
      Object.keys(hedgerowLayers).forEach(function (k) {
        if (!_shown(hedgerowLayers[k])) return;
        hedgerowLayers[k].eachLayer(function (l) {
          var h = l._hedge;
          if (h) s.hedgerows.push({ label: _HEDGE_WORDS[h.style] || 'Hedgerow', colour: h.color,
                                    dashed: h.style === 'fence' || h.style === 'living_fence' });
        });
      });
      Object.keys(shapeLayers).forEach(function (k) {
        if (!_shown(shapeLayers[k])) return;
        shapeLayers[k].eachLayer(function (l) {
          var sh = l._shape;
          if (!sh) return;
          var casts = sh.heightM > 0;
          s.shapes.push({ label: sh.label || (sh.shapeType && sh.shapeType !== 'Custom'
                                              ? sh.shapeType : 'Shape'),
                          stroke: sh.strokeColor, fill: sh.fillColor, casts: casts,
                          dashed: casts || !!sh.dashArray });
        });
      });
      s.measurements = measureVisible ? measureLayers.length : 0;
      var contour = null;
      contourLayers.forEach(function (g) { if (!contour && _shown(g)) contour = _firstColour(g); });
      if (!contour && _shown(autoContourLayer)) contour = _firstColour(autoContourLayer) || '#44cc00';
      s.analysis = {
        sun: _shown(sunPathLayer),
        shade: _shown(shadeOverlayLayer) || _shown(shadowPolyLayer) || _shown(shadeZonesLayer),
        contour: contour,
        wind: _shown(windLayer) || _shown(windShadowLayer) || _shown(windGhostLayer)
      };
      return s;
    }

    function _legendOpen() {
      var el = document.getElementById('map-legend');
      return !!el && el.classList.contains('visible');
    }

    // Rebuild soon: Leaflet adds and removes layers in bursts (a pattern, an
    // undo's redraw, a boundary's labels on every frame of a drag).
    function scheduleLegend() {
      if (!_legendOpen()) { _clearSpeciesNumbers(); return; }
      if (_legendTimer) clearTimeout(_legendTimer);
      _legendTimer = setTimeout(refreshLegend, 60);
    }

    function refreshLegend() {
      if (_legendTimer) { clearTimeout(_legendTimer); _legendTimer = null; }
      var body = document.getElementById('legend-body');
      if (!body || !map || !map.hasLayer) return;
      _legendTargets = [];
      body.innerHTML = legendHtml(legendModel(legendSnapshot(), legendDetail), _legendTargets);
      _drawSpeciesNumbers();
    }

    function _clearSpeciesNumbers() {
      _numberFollow.forEach(function (f) { f[0].off('move', f[1]); });
      _numberFollow = [];
      if (_speciesNumberLayer) map.removeLayer(_speciesNumberLayer);
      _speciesNumberLayer = null;
    }

    // In Species, each plant carries its number, so the legend's 7 can be
    // found on the map, as on the printed planting plan.
    function _drawSpeciesNumbers() {
      _clearSpeciesNumbers();
      if (legendDetail.plants !== 'species' || !_legendOpen() || !_shown(plantLayerGroup)) return;
      var circles = Object.keys(plantMarkers).map(function (k) { return plantMarkers[k]; })
        .filter(function (c) { return c && c._pd; });
      var nums = speciesNumbers(circles.map(function (c) {
        return { id: c._pd.plantId, name: c._pd.commonName };
      }));
      _speciesNumberLayer = L.layerGroup();
      _speciesNumberLayer._spLegendOwn = true;
      circles.forEach(function (c) {
        var mk = L.marker(c.getLatLng(), { interactive: false, keyboard: false,
          icon: L.divIcon({ className: 'sp-species-num', html: String(nums[c._pd.plantId]),
                            iconSize: [24, 16], iconAnchor: [12, 8] }) });
        mk._spLegendOwn = true;
        mk._spCircle = c;
        var follow = function (ev) { mk.setLatLng(ev.latlng); };
        c.on('move', follow);
        _numberFollow.push([c, follow]);
        _speciesNumberLayer.addLayer(mk);
      });
      _speciesNumberLayer.addTo(map);
      _fitSpeciesNumbers();
    }

    // A plant's radius on screen now, from its radius in metres. Not the
    // circle's own pixel radius: on zoomend this runs before the plants
    // re-project (it was hooked first), and read that it showed every number.
    function _pixelRadius(c) {
      var ll = c.getLatLng();
      var a = map.latLngToContainerPoint(ll);
      var b = map.latLngToContainerPoint([ll.lat + c.getRadius() / 111320, ll.lng]);
      return Math.abs(a.y - b.y);
    }

    function _fitSpeciesNumbers() {
      if (!_speciesNumberLayer) return;
      _speciesNumberLayer.eachLayer(function (mk) {
        mk.setOpacity(_pixelRadius(mk._spCircle) >= _NUMBER_MIN_RADIUS_PX ? 1 : 0);
      });
    }

    function setLegendDetail(plants, boundaries) {
      if (_LEGEND_SWITCHES.plants.some(function (o) { return o[0] === plants; })) {
        legendDetail.plants = plants;
      }
      if (_LEGEND_SWITCHES.boundaries.some(function (o) { return o[0] === boundaries; })) {
        legendDetail.boundaries = boundaries;
      }
      scheduleLegend();
    }

    function _onLegendClick(ev) {
      var b = ev.target && ev.target.closest ? ev.target.closest('button') : null;
      if (!b) return;
      if (b.dataset.legend) {
        setLegendDetail(b.dataset.legend === 'plants' ? b.dataset.value : legendDetail.plants,
                        b.dataset.legend === 'boundaries' ? b.dataset.value : legendDetail.boundaries);
        refreshLegend();
        var again = document.querySelector('#map-legend button[data-legend="' +
          b.dataset.legend + '"][data-value="' + b.dataset.value + '"]');
        if (again) again.focus();                // the rebuild took the old one
        if (bridge && bridge.onLegendDetailChanged) {
          bridge.onLegendDetailChanged(legendDetail.plants, legendDetail.boundaries);
        }
      } else if (b.dataset.item !== undefined) {
        var t = _legendTargets[+b.dataset.item];
        if (t) askBoundaryName(t.ids, t.name);               // 02-boundary.js
      }
    }

    // Moved here from 06-overlays.js (V3.11): opening the legend builds it.
    function toggleLegend() {
      setLegendVisible(!_legendOpen());
    }

    function setLegendVisible(visible) {
      var legend = document.getElementById('map-legend');
      var btn    = document.getElementById('legend-toggle');
      legend.classList.toggle('visible', !!visible);
      btn.classList.toggle('active', !!visible);
      if (visible) refreshLegend(); else _clearSpeciesNumbers();
    }

    // From initMap (01-core.js): every layer the map gains or loses may change
    // what the legend says. Not its own numbers, and not a hover's tooltip.
    function initLegend() {
      map.on('layeradd layerremove', function (e) {
        var l = e.layer;
        if (!l || l._spLegendOwn || l instanceof L.DivOverlay) return;
        scheduleLegend();
      });
      map.on('zoomend', _fitSpeciesNumbers);
      var el = document.getElementById('map-legend');
      if (el) el.addEventListener('click', _onLegendClick);
    }
