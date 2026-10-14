    /*
     * 11-map-furniture.js — the north arrow, the scale bar (F205, V3.06), and
     * the line that says when the map's ground cannot load (V3.19, QF-6).
     *
     * The map had neither, so a screenshot of a design or the map page of
     * Export PDF (a grab of this page) could not be read for direction or
     * distance. Both are drawn on the page itself, so whatever is on screen
     * is what an export carries.
     *
     * The map is Web Mercator and never rotates, so north is always up and
     * the arrow never turns. The scale is measured across the middle of the
     * map, as Leaflet's own scale control measures it, and redrawn as the
     * map moves: Mercator's metres per pixel change with latitude.
     *
     * Automatic by default since V3.19 (QF-18, R18; the owner's K1): metres
     * below 1 km, kilometres from 1 km, where V3.06's kilometres read
     * "0.005 km" across a yard. View → Scale Units fixes either unit; a click
     * on the bar fixes the other unit from the one shown, and the menu is the
     * way back to Automatic. Python remembers the choice.
     *
     * Placement: the arrow under the zoom buttons, where nothing else sits
     * (the placement bar takes the top edge, the plant page and the selection
     * badge the top right); the bar bottom centre, clear of the legend and
     * its button at the bottom left and the relationship web's key at the
     * bottom right. The bar is a <button> outside the map's container, so a
     * click or Enter on it never reaches the map as a click to place.
     */
    var _northArrowControl = null;
    var _scaleBarEl = null;
    var _scaleUnit = 'auto';
    var _scaleShown = 'm';                 // the unit drawn, Automatic resolved
    var _scaleWired = false;
    var SCALE_MAX_PX = 120;

    // The longest "round" length (1, 2 or 5 times a power of ten) in `unit`
    // that fits in `maxPx`, its width in pixels, its label and the unit it is
    // in. 'auto' is metres below 1 km and kilometres from 1 km. Pure, so a
    // test can run it in node without a map.
    function scaleBarFor(metresPerPixel, maxPx, unit) {
      if (unit !== 'm' && unit !== 'km') {
        var inMetres = scaleBarFor(metresPerPixel, maxPx, 'm');
        return inMetres && inMetres.length >= 1000
          ? scaleBarFor(metresPerPixel, maxPx, 'km') : inMetres;
      }
      var perUnit = unit === 'm' ? 1 : 1000;
      var maxLen = metresPerPixel * maxPx / perUnit;
      if (!(maxLen > 0) || !isFinite(maxLen)) return null;
      var exp = Math.floor(Math.log(maxLen) / Math.LN10 + 1e-9);
      var base = Math.pow(10, exp);
      var len = base;
      [5, 2, 1].some(function (s) {
        if (s * base <= maxLen * (1 + 1e-9)) { len = s * base; return true; }
        return false;
      });
      var label = len.toFixed(Math.max(0, -exp)) + ' ' + (unit === 'm' ? 'm' : 'km');
      return {px: Math.max(1, Math.round(len * perUnit / metresPerPixel)),
              length: len, label: label, unit: unit};
    }

    function _metresPerPixel() {
      var y = map.getSize().y / 2;
      var metres = map.distance(map.containerPointToLatLng([0, y]),
                                map.containerPointToLatLng([SCALE_MAX_PX, y]));
      return metres / SCALE_MAX_PX;
    }

    function _drawScaleBar() {
      if (!_scaleBarEl || _scaleBarEl.style.display === 'none') return;
      var s = scaleBarFor(_metresPerPixel(), SCALE_MAX_PX, _scaleUnit);
      if (!s) return;
      _scaleShown = s.unit;
      var other = s.unit === 'km' ? 'metres' : 'kilometres';
      _scaleBarEl.querySelector('.sp-scale-label').textContent = s.label;
      _scaleBarEl.querySelector('.sp-scale-bar').style.width = s.px + 'px';
      _scaleBarEl.title = 'Scale: ' + s.label + '. Click to show ' + other + '.';
      _scaleBarEl.setAttribute('aria-label', 'Scale: ' + s.label +
                               '. Show in ' + other);
    }

    // Python → JS: show or hide the scale, in 'auto', 'km' or 'm'.
    function setScaleBar(on, unit) {
      _scaleUnit = unit === 'm' || unit === 'km' ? unit : 'auto';
      if (!_scaleBarEl) {
        _scaleBarEl = document.createElement('button');
        _scaleBarEl.type = 'button';
        _scaleBarEl.id = 'sp-scale';
        _scaleBarEl.style.cssText = 'position:absolute;left:50%;bottom:10px;' +
          'transform:translateX(-50%);z-index:1000;cursor:pointer;' +
          'background:rgba(255,255,255,0.9);border:1px solid rgba(27,42,27,0.55);' +
          'border-radius:4px;padding:2px 8px 5px;color:#1b2a1b;' +
          'font:12px system-ui,"Segoe UI",Arial,sans-serif;line-height:1.4;' +
          'text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.3);';
        _scaleBarEl.innerHTML = '<div class="sp-scale-label"></div>' +
          '<div class="sp-scale-bar" style="height:6px;margin:0 auto;' +
          'border:2px solid #1b2a1b;border-top:none;"></div>';
        _scaleBarEl.addEventListener('click', function (ev) {
          ev.preventDefault();
          ev.stopPropagation();
          // The other unit from the one shown, Automatic's included.
          _scaleUnit = _scaleShown === 'km' ? 'm' : 'km';
          _drawScaleBar();
          if (bridge && bridge.onScaleUnitChanged) bridge.onScaleUnitChanged(_scaleUnit);
        });
        document.body.appendChild(_scaleBarEl);
      }
      if (!_scaleWired) {
        map.on('zoom moveend resize', _drawScaleBar);
        _scaleWired = true;
      }
      _scaleBarEl.style.display = on ? '' : 'none';
      _drawScaleBar();
    }

    // Python → JS: show or hide the north arrow.
    function setNorthArrow(on) {
      if (on && !_northArrowControl) {
        var NorthArrow = L.Control.extend({
          options: {position: 'topleft'},
          onAdd: function () {
            var el = L.DomUtil.create('div', 'sp-north-arrow');
            el.setAttribute('role', 'img');
            el.setAttribute('aria-label', 'North arrow: north is up');
            el.title = 'North is up';
            el.style.cssText = 'pointer-events:none;width:34px;height:46px;' +
              'background:rgba(255,255,255,0.9);border:1px solid rgba(27,42,27,0.55);' +
              'border-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,0.3);';
            el.innerHTML = '<svg width="34" height="46" viewBox="0 0 34 46" ' +
              'aria-hidden="true">' +
              '<text x="17" y="14" text-anchor="middle" font-size="13" ' +
              'font-weight="700" font-family="system-ui,Arial,sans-serif" ' +
              'fill="#1b2a1b">N</text>' +
              '<path d="M17 17 L25 41 L17 35 Z" fill="#1b2a1b"/>' +
              '<path d="M17 17 L9 41 L17 35 Z" fill="#ffffff" ' +
              'stroke="#1b2a1b" stroke-width="1.2" stroke-linejoin="round"/>' +
              '</svg>';
            return el;
          }
        });
        _northArrowControl = new NorthArrow();
        _northArrowControl.addTo(map);
      } else if (!on && _northArrowControl) {
        _northArrowControl.remove();
        _northArrowControl = null;
      }
    }

    // ── When the map's ground cannot load (V3.19, QF-6, R9) ─────────────────
    // Offline every base-map tile fails, and the map was a blank grey area
    // that said nothing. 01-core.js hands each base map and the satellite photo
    // to watchBaseTiles. When a screenful has answered with no tile drawn, a
    // base map that never drew one hands over to the next (a dead host, caught
    // sooner than 01-core.js's eight errors on a small map), and the last says
    // so mid-map until a tile draws. It takes no clicks (pointer-events: none).
    var OFFLINE_TEXT = 'The map needs an internet connection to load. ' +
                       'Your design is safe.';
    var _offlineEl = null;

    // 'ok' while any tile is drawn, 'next' to try another base map when this
    // one has never drawn one, else 'offline'. Pure, so node can run it.
    function basemapVerdict(drawn, everDrawn, another) {
      if (drawn > 0) return 'ok';
      return another && !everDrawn ? 'next' : 'offline';
    }

    function _showOffline(on) {
      if (!_offlineEl && on) {
        _offlineEl = document.createElement('div');
        _offlineEl.id = 'sp-offline';
        _offlineEl.setAttribute('role', 'status');          // read out when shown
        _offlineEl.style.cssText = 'position:absolute;left:50%;top:50%;z-index:1000;' +
          'transform:translate(-50%,-50%);pointer-events:none;width:340px;' +
          'max-width:calc(100% - 32px);box-sizing:border-box;padding:10px 14px;' +
          'background:rgba(255,255,255,0.95);border:1px solid rgba(27,42,27,0.55);' +
          'border-radius:6px;color:#1b2a1b;text-align:center;line-height:1.4;' +
          'font:14px system-ui,"Segoe UI",Arial,sans-serif;box-shadow:0 1px 4px rgba(0,0,0,0.3);';
        document.body.appendChild(_offlineEl);
      }
      if (!_offlineEl) return;
      _offlineEl.textContent = on ? OFFLINE_TEXT : '';
      _offlineEl.style.display = on ? '' : 'none';
    }

    // Watch one base tile layer; `next` tries the next base map, or is null.
    function watchBaseTiles(layer, next) {
      var everDrawn = false;
      layer.on('tileload', function () { everDrawn = true; _showOffline(false); });
      layer.on('load', function () {
        var box = layer.getContainer();
        var drawn = box ? box.querySelectorAll('.leaflet-tile-loaded').length : 0;
        var verdict = basemapVerdict(drawn, everDrawn, !!next);
        if (verdict === 'next') next(); else _showOffline(verdict === 'offline');
      });
    }
