// html/scene3d/26-perf.js — how fast the 3D view is drawing (V3.43).
//
// Part of the Site & Pattern 3D viewer: a classic script sharing the global
// scope with its siblings (see any chunk's header). No ES import or export.
//
// No session has ever seen the preview on the laptop it is for: every render
// the reviews and the gates look at is drawn in software, where a frame takes
// seconds and says nothing about a graphics card. The V3.43 review counted 0.8
// to 1.5 million triangles a frame for a 365-plant yard and could not say
// whether that is 60 frames a second or 6. This is the number, on the screen,
// for a person to read off and send back, before any increment adds cost.
//
// Ctrl+Shift+F in the 3D window shows and hides it (an address flag cannot be
// typed in the app; ?perf=1 turns it on for a probe). It costs nothing while
// hidden: the render call is wrapped only while the readout is showing.
let _perfBox = null, _perfPlain = null;
const _perf = { frames: 0, since: 0, fps: 0, ms: 0, worst: 0, last: 0 };

function perfNow() {
  const i = renderer.info, sc = (typeof lastSceneObj !== 'undefined' && lastSceneObj) || {};
  return { fps: +_perf.fps.toFixed(1), frame_ms: +_perf.ms.toFixed(1),
           worst_ms: +_perf.worst.toFixed(1), triangles: i.render.triangles,
           calls: i.render.calls, plants: (sc.plants || []).filter(standing).length,
           detail: typeof QUALITY === 'undefined' ? null : QUALITY,
           pixels: renderer.domElement.width + ' x ' + renderer.domElement.height };
}
// Readable by a probe whether or not the box is showing.
window.permaPerf = perfNow;

function _perfText() {
  const p = perfNow(), names = ['Stylised', 'Balanced', 'Lifelike'];
  return p.fps + ' frames a second \u00b7 ' + p.frame_ms + ' ms a frame (worst '
    + p.worst_ms + ')<br>' + p.triangles.toLocaleString() + ' triangles \u00b7 '
    + p.calls + ' draw calls \u00b7 ' + p.plants + ' plants<br>'
    + (names[p.detail] || '') + ' \u00b7 ' + p.pixels + ' pixels'
    + '<br><span style="opacity:.7">Ctrl+Shift+F hides this</span>';
}

function setPerfReadout(on) {
  if (!!on === !!_perfBox) return;
  if (!on) {
    renderer.render = _perfPlain; _perfPlain = null;
    _perfBox.remove(); _perfBox = null;
    return;
  }
  _perfBox = document.createElement('div');
  _perfBox.id = 'perf-readout';
  _perfBox.style.cssText = 'position:absolute;left:10px;top:52px;z-index:7;'
    + 'font:13px/1.45 system-ui,sans-serif;color:#eef4ec;pointer-events:none;'
    + 'background:rgba(18,28,20,.86);border:1px solid #3a5a3a;border-radius:8px;'
    + 'padding:6px 10px';
  document.body.appendChild(_perfBox);
  _perf.frames = 0; _perf.worst = 0; _perf.since = _perf.last = performance.now();
  _perfPlain = renderer.render;
  renderer.render = function (s, c) {
    _perfPlain.call(renderer, s, c);
    // The main picture only: a snapshot or a shadow pass is not a frame.
    if (s !== scene || c !== camera) return;
    const t = performance.now();
    _perf.worst = Math.max(_perf.worst, t - _perf.last); _perf.last = t;
    if (++_perf.frames && t - _perf.since >= 1000) {
      _perf.fps = _perf.frames * 1000 / (t - _perf.since);
      _perf.ms = (t - _perf.since) / _perf.frames;
      _perfBox.innerHTML = _perfText();
      _perf.frames = 0; _perf.since = t; _perf.worst = 0;
    }
  };
  _perfBox.innerHTML = 'measuring\u2026';
}

addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.shiftKey && e.code === 'KeyF') { e.preventDefault(); setPerfReadout(!_perfBox); }
});
if (/[?&]perf=1(&|$)/.test(location.search)) setPerfReadout(true);
