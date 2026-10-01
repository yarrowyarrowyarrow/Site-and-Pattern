// html/map/10-plant-key.js — what a plant marker looks like, and the legend
// that says so (F195, V3.03).
//
// Classic script, loaded after 09-keyboard.js by map.html: the shared-global
// model of html/map/*.js (see the header of 01-core.js). Everything here is
// read at call time, after every script has loaded.
//
// Until V3.03 a marker was outlined in its own pale fill colour, so against
// the yard its edge measured 1.0:1 (grass) to 2.1:1 (shrub), and a
// community's members on their tree's canopy 1.0 to 1.8:1; WCAG 1.4.11 asks
// 3:1 of a graphic you need to read the design. Community members were
// coloured by layer in seven greens, but only until the design was reopened,
// when the loader drew them by type; and the legend listed six of the twelve
// types, with no purple for the wildflowers. Now every plant is coloured by
// its type, outlined in that colour darkened by 60% (the worst, grass, is
// 4.9:1 on the yard and the worst under a canopy 3.4:1), and the legend's
// plant section is built from the same tables. And a plant is drawn round:
// see roundCircles below.

    // Mirror of src/member_colors.py TYPE_COLORS; tests/test_plant_key.py
    // fails if the two differ.
    var TYPE_COLORS = {
      'tree':        '#2e7d32',
      'shrub':       '#558b2f',
      'wildflower':  '#ab47bc',
      'herb':        '#9ccc65',
      'groundcover': '#c6a817',
      'grass':       '#cddc39',
      'sedge':       '#8d6e63',
      'rush':        '#5d4037',
      'vine':        '#00838f',
      'fern':        '#33691e',
      'aquatic':     '#29b6f6',
      'root':        '#6d4c41'
    };

    // Mirror of src/plant_facets.py _TYPE_LABELS, in its order (the Type
    // filter's words). 'root' has no plants and no entry.
    var TYPE_WORDS = [
      ['tree', 'Tree'], ['shrub', 'Shrub'], ['vine', 'Vine'],
      ['wildflower', 'Wildflower'], ['herb', 'Herb / Foliage'],
      ['groundcover', 'Groundcover'], ['grass', 'Grass'], ['sedge', 'Sedge'],
      ['rush', 'Rush'], ['fern', 'Fern'], ['aquatic', 'Aquatic / Wetland']
    ];

    var MARKER_EDGE_DARKEN = 0.6;
    var MARKER_EDGE_WEIGHT = 2;
    var MARKER_FILL_OPACITY = 0.35;

    // The colour a plant is drawn in: the one you gave it, else its type's.
    function plantColour(pd) {
      return (pd && pd.customColor) || (pd && TYPE_COLORS[pd.plantType]) || '#66bb6a';
    }

    // A colour's outline: the same hue, 60% darker.
    function markerEdge(hex) {
      var h = String(hex || '').replace('#', '');
      if (h.length === 3) h = h.replace(/(.)/g, '$1$1');
      if (!/^[0-9a-fA-F]{6}$/.test(h)) return '#1b2a1b';
      var out = '#';
      for (var i = 0; i < 6; i += 2) {
        var v = Math.round(parseInt(h.substr(i, 2), 16) * (1 - MARKER_EDGE_DARKEN));
        out += ('0' + v.toString(16)).slice(-2);
      }
      return out;
    }

    // A plant marker's normal look, wherever one is drawn or restored.
    function plantMarkerStyle(colour) {
      return { color: markerEdge(colour), weight: MARKER_EDGE_WEIGHT,
               fillColor: colour, fillOpacity: MARKER_FILL_OPACITY };
    }

    function _swatch(colour) {
      return '<span class="legend-swatch" style="background:' + colour +
             ';border:2px solid ' + markerEdge(colour) + ';"></span>';
    }

    // The legend's plant section, from the tables above.
    function buildPlantLegend() {
      var el = document.getElementById('legend-plants');
      if (!el) return;
      var html = '<div class="legend-section-title">Plants, by type</div>';
      TYPE_WORDS.forEach(function (pair) {
        html += '<div class="legend-item">' + _swatch(TYPE_COLORS[pair[0]]) +
                ' ' + pair[1] + '</div>';
      });
      // The dashed ring is the Canopy view's (04-tools.js) and the footprint's
      // (08-footprint.js). V3.02's legend called it "Community outline", which
      // nothing on the map draws.
      html += '<div class="legend-item"><span class="legend-swatch outline-only"' +
              ' style="border-color:#a5d6a7;"></span> Mature spread, with Canopy on</div>' +
              '<div class="legend-note">A plant you gave its own colour keeps it.</div>';
      el.innerHTML = html;
    }

    // A circle in metres is a circle on screen. Leaflet 1.9 works out a
    // circle's width with an acos that loses its precision below about a
    // metre: at zoom 23 one 0.1 m plant was drawn 4.75 px wide and 8.42 tall,
    // the next 8.23 wide, so a meadow was ellipses leaning both ways. Its
    // height is a plain difference of two projected points and is right, and
    // Web Mercator is conformal, so at a yard's scale the width is the height.
    // Leaflet's click test reads the width alone: the top and bottom of a
    // drawn plant missed too. Every circle, so the footprint under the cursor
    // and the selection rings match the markers they stand for.
    function roundCircles(Lf) {
      var project = Lf.Circle.prototype._project;
      Lf.Circle.include({
        _project: function () {
          project.call(this);
          if (this._radiusY) {      // a map in metres; other CRSs set no height
            this._radius = this._radiusY;
            this._updateBounds();
          }
        }
      });
    }

    if (typeof L !== 'undefined' && L.Circle) roundCircles(L);
    if (typeof document !== 'undefined' && document.getElementById) buildPlantLegend();
