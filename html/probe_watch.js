// Errors on a 3D probe page, written where the test can read them (V3.37).
//
// A probe writes its result into document.title when it finishes. A viewer that
// THROWS never finishes, so the title stayed empty, and the tests read an empty
// title as "no WebGL in this environment" and skipped. That is how
// buildStructures went missing from V3.22 to V3.37 under a green CI: three
// render gates skipped on every run with exactly that message.
//
// So every error is written into <pre id="probe-errors">, which `--dump-dom`
// carries out whatever the title says, and the tests fail on it
// (tests/test_scene3d_render.py:viewer_errors). A viewer that could not start
// for want of WebGL is not an error: it sets permaBootError (01-core.js), and
// the tests still skip. Load this right after the viewer's iframe, #v.
(function () {
  const box = document.createElement('pre');
  box.id = 'probe-errors';
  document.body.appendChild(box);
  const note = (where, what) => { box.textContent += where + ': ' + what + '\n'; };

  // The probe's own calls into the viewer (permaSetScene and the rest) throw
  // here, on the probe page, not in the frame.
  window.addEventListener('error', (e) => note('probe', e.message || e.error));
  window.addEventListener('unhandledrejection', (e) => {
    note('probe', (e.reason && e.reason.message) || e.reason);
  });

  // The viewer reports its own through _showViewerError (scene3d.html), from
  // its first script on, so wrap that as soon as the frame has one. The frame
  // is outside Qt here, so its qrc: script is missing, and that is not a fault.
  const frame = document.getElementById('v');
  (function wrap() {
    const w = frame.contentWindow;
    if (!w || typeof w._showViewerError !== 'function') { setTimeout(wrap, 20); return; }
    const shown = w._showViewerError;
    w._showViewerError = function (detail) {
      const d = String(detail);
      if (!w.permaBootError && !d.startsWith('failed to load qrc:')) note('viewer', d);
      return shown(detail);
    };
  })();
})();
