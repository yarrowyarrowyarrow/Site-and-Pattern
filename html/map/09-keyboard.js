// html/map/09-keyboard.js — the map without a mouse (F195, V3.02).
//
// Classic script, loaded after 08-footprint.js by map.html: the shared-global
// model of html/map/*.js (see the header of 01-core.js).
//
// Until V3.02 every tool on the map acted on a click, so a keyboard could pan
// the map (Leaflet's own handler) and do nothing else on it: not place a
// plant, not draw a boundary, not measure. Every tool acts through one
// function, onMapClick, so the keyboard needs one key rather than one per tool:
//
//   Enter        acts at the map's centre: places the plant, structure or
//                community, adds a boundary's or shape's next corner,
//                measures, pins a note.
//   Shift+Enter  finishes what a double-click finishes (finishDrawing).
//   Arrows, + -  pan and zoom: Leaflet's handler, listening while the map
//                container has focus.
//
// Enter counts only when the container itself has focus, so on a control
// inside the map (zoom, the legend) it presses that control as before.
// While a tool is active and the keyboard is in use, a mark shows the centre
// and the footprint and pattern previews follow it, so the spot Enter will act
// on is visible before it is pressed. A mouse press hands the map back to the
// mouse: the mark goes, and the previews follow the pointer again.
//
// The page draws the map's focus ring itself. The browser's own is an outline
// one pixel OUTSIDE the container (Leaflet's outline-offset), and the container
// fills the page, so it was clipped to nothing: on V3.02's first build the
// map was the one Tab stop with no visible focus. The window's ring
// (src/focus_ring.py) leaves the map alone, because focus moves between the
// page's own controls inside it and Qt sees one widget throughout.

    // Leaflet makes every marker a tab stop and, to a screen reader, a
    // "button" (keyboard: true by default), interactive or not, and this map
    // draws its labels as markers: Tab spent six presses on a boundary's
    // edge lengths before leaving the map. A marker that does something when
    // activated says so itself (the boundary's area label, which cycles units).
    if (typeof L !== 'undefined') L.Marker.mergeOptions({keyboard: false});

    var _kbInUse = false;
    // The tools Enter can act for. 'select' and 'terrain_rect' are drags.
    var _KEYBOARD_TOOLS = {
      plant: 1, polyculture: 1, structure: 1, boundary: 1, hedgerow: 1,
      shape: 1, fill: 1, contour: 1, measure: 1, annotate: 1, sun_anchor: 1
    };

    function _centreMark() {
      var el = document.getElementById('sp-centre-mark');
      if (!el) {
        el = document.createElement('div');
        el.id = 'sp-centre-mark';
        el.setAttribute('aria-hidden', 'true');
        map.getContainer().appendChild(el);
      }
      return el;
    }

    // Whether Enter would act now, and the mark should say where.
    function keyboardToolActive() {
      return _kbInUse && !!_KEYBOARD_TOOLS[currentMode];
    }

    function syncCentreMark() {
      if (!map) return;
      var on = keyboardToolActive();
      _centreMark().style.display = on ? 'block' : 'none';
      if (on) onMapMouseMove({latlng: map.getCenter()});
    }

    function _setKeyboardInUse(on) {
      if (_kbInUse === on) return;
      _kbInUse = on;
      if (map && map.getContainer().classList) {
        map.getContainer().classList.toggle('sp-keyboard', on);
      }
      syncCentreMark();
      if (!on && typeof hideCursorFootprint === 'function') hideCursorFootprint();
    }

    // The F6 key from the side panel (src/keyboard_help.py, PaneSwitch): the
    // map itself, not whichever of its controls had focus last, ring showing.
    function focusMapByKeyboard() {
      if (!map) return;
      _setKeyboardInUse(true);
      map.getContainer().focus();
    }

    // Enter's work, apart from the key: act at the centre with the active tool.
    // Returns whether anything was done.
    function actAtMapCentre() {
      if (!_KEYBOARD_TOOLS[currentMode]) return false;
      onMapClick({latlng: map.getCenter()});
      return true;
    }

    function initMapKeyboard() {
      var container = map.getContainer();
      // What a screen reader announces on arriving, and the role that tells it
      // to pass the arrow keys through to the map rather than read with them.
      container.setAttribute('role', 'application');
      container.setAttribute('aria-label',
        'Map. Arrow keys pan, plus and minus zoom. With a tool chosen, Enter ' +
        'acts at the centre of the map and Shift+Enter finishes a shape. ' +
        'F6 goes back to the side panel.');

      var style = document.createElement('style');
      style.textContent =
        '#sp-centre-mark { position: absolute; left: 50%; top: 50%; ' +
        '  width: 30px; height: 30px; margin: -15px 0 0 -15px; ' +
        '  pointer-events: none; z-index: 650; display: none; }' +
        '#sp-centre-mark::before, #sp-centre-mark::after { content: ""; ' +
        '  position: absolute; background: #ffe082; ' +
        '  box-shadow: 0 0 0 1px #1a2a1a; }' +
        '#sp-centre-mark::before { left: 14px; top: 0; width: 2px; height: 30px; }' +
        '#sp-centre-mark::after { top: 14px; left: 0; width: 30px; height: 2px; }' +
        // The focus ring: over the panes (z 400) and the controls (z 1000),
        // inside the edge, two tones like the window's ring.
        '.leaflet-container:focus-visible::after, ' +
        '.leaflet-container.sp-keyboard:focus::after { content: ""; ' +
        '  position: absolute; left: 0; top: 0; right: 0; bottom: 0; ' +
        '  border: 2px solid #ffe082; box-shadow: inset 0 0 0 1px #1a2a1a; ' +
        '  pointer-events: none; z-index: 1100; }';
      document.head.appendChild(style);

      document.addEventListener('keydown', function (ev) {
        if (document.activeElement !== container) return;
        _setKeyboardInUse(true);
        if (ev.key !== 'Enter') return;
        ev.preventDefault();
        if (ev.shiftKey) {
          finishDrawing();
        } else {
          actAtMapCentre();
        }
      });
      // Capture phase, so a press that a marker or a control stops still
      // counts as the mouse coming back.
      document.addEventListener('mousedown', function () {
        _setKeyboardInUse(false);
      }, true);
      map.on('move', function () {
        if (keyboardToolActive()) onMapMouseMove({latlng: map.getCenter()});
      });
    }
