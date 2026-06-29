"""
wind_flow.py — orchestration for fetching site wind data (V1.67).

Free functions taking ``main`` (kept off MainWindow/controller, like
``building_flow``/``splat_flow``). Pulls the seasonal wind rose
(``wind.get_wind_summary``, DB-cached → offline after first fetch) plus the live
current reading off the UI thread, and hands them to the Analysis → Wind tab.
Falls back to a bundled regional approximation
(``data/wind_fallback_alberta.json``) when offline with nothing cached, mirroring
the rainfall/soil fallbacks.
"""

from __future__ import annotations

import json
import math

from src import wind


def _dist2(a, b) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _fallback_rose(lat: float, lng: float):
    """Synthesize an approximate rose from the nearest bundled regional
    prevailing wind, so a fully-offline first run still shows something useful."""
    from src.resources import resource_path
    try:
        with open(resource_path("data", "wind_fallback_alberta.json"),
                  encoding="utf-8") as f:
            entries = json.load(f)
    except Exception:  # noqa: BLE001
        return None
    if not entries:
        return None
    best = min(entries, key=lambda e: _dist2((lat, lng),
                                             tuple(e.get("centroid") or (0, 0))))
    deg = float(best.get("prevailing_deg", 270))
    spd = float(best.get("mean_speed_kmh", 14))
    # 10 hours/month at the regional prevailing dir/speed → a real rose shape.
    rows = [{"month": m, "dir_deg": deg, "speed": spd}
            for m in range(1, 13) for _ in range(10)]
    rose = wind.compute_wind_rose(rows)
    rose["cached"] = False
    rose["approximate"] = True
    rose["source"] = f"Regional approximation — {best.get('region', 'Alberta')}"
    return rose


def _site_latlng(main):
    sc = (main._project.get("properties", {}) or {}).get("site_config", {}) or {}
    lat, lng = sc.get("latitude"), sc.get("longitude")
    if lat is None or lng is None:
        c = getattr(main.map_widget, "_last_center", None)
        if c:
            lat, lng = c
    return lat, lng


def fetch_wind_for_site(main) -> None:
    """Fetch the wind rose + current reading for the site, off-thread, and push
    them into the Wind tab. No-op with a status note when no location is set."""
    lat, lng = _site_latlng(main)
    if lat is None or lng is None:
        main.analysis_panel.set_wind_status(
            "Drop a property pin or set a location first.")
        return
    main.analysis_panel.set_wind_status("Fetching wind data…")

    from PyQt6.QtCore import QThread
    thread = QThread(main)
    worker = _WindFetchWorker(lat, lng)
    worker.moveToThread(thread)
    main._wind_thread = thread
    main._wind_worker = worker

    def _apply(result):
        rose = result.get("rose")
        main.analysis_panel.set_wind_data(rose, result.get("current"))
        # Persist prevailing wind to the project + surface a windbreak hint.
        advice = wind.windbreak_advice(rose) if rose else None
        if rose:
            a = rose.get("annual") or {}
            sc = (main._project.setdefault("properties", {})
                  .setdefault("site_config", {}))
            sc["wind_prevailing_deg"] = a.get("prevailing_deg")
            sc["wind_mean_kmh"] = a.get("mean_speed")
            sc["wind_exposure"] = ("exposed" if (advice and advice["exposed"])
                                   else "moderate")
            try:
                main._mark_modified()
            except Exception:  # noqa: BLE001
                pass
        if advice:
            main.analysis_panel.set_wind_advice(advice["text"])

    def _done():
        worker.deleteLater()
        thread.deleteLater()
        main._wind_worker = None
        main._wind_thread = None

    thread.started.connect(worker.run)
    worker.done.connect(_apply)
    worker.done.connect(thread.quit)
    thread.finished.connect(_done)
    thread.start()


try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _HAVE_QT = True
except ImportError:  # pragma: no cover
    _HAVE_QT = False

if _HAVE_QT:
    class _WindFetchWorker(QObject):
        done = pyqtSignal(object)     # {"rose": dict|None, "current": dict|None}

        def __init__(self, lat, lng):
            super().__init__()
            self._lat = lat
            self._lng = lng

        def run(self):
            try:
                rose = wind.get_wind_summary(self._lat, self._lng)
            except Exception:  # noqa: BLE001
                rose = None
            if rose is None:
                rose = _fallback_rose(self._lat, self._lng)
            try:
                current = wind.fetch_current_wind(self._lat, self._lng)
            except Exception:  # noqa: BLE001
                current = None
            self.done.emit({"rose": rose, "current": current})
