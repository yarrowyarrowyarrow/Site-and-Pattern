"""
soil_flow.py — orchestration for the one-time soil-pack download (V1.67).

Free functions taking ``main`` (off MainWindow/controller, like
``building_flow``). Wires ``SoilDownloadWorker`` on a QThread to the site
panel's soil download button + status + cancel, mirroring the terrain/building
download flows. State lives on ``main``: ``_soil_dl_thread`` / ``_soil_dl_worker``.
"""

from __future__ import annotations


def start_soil_download(main) -> None:
    from PyQt6.QtCore import QThread
    from src.soil_downloader import SoilDownloadWorker

    main.site_panel.set_soil_download_status(
        "Downloading soil data (one-time)…", busy=True)

    thread = QThread(main)
    worker = SoilDownloadWorker()
    worker.moveToThread(thread)
    main._soil_dl_thread = thread
    main._soil_dl_worker = worker

    def _progress(done, total, text):
        main.site_panel.set_soil_download_status(text, busy=True)

    def _finished(n):
        main.site_panel.set_soil_download_status(
            f"Soil pack ready — {n} layer(s) cached offline. Re-drop the pin "
            "to use it.", busy=False)

    def _error(msg):
        main.site_panel.set_soil_download_status(msg, busy=False)

    def _done():
        try:
            main.site_panel._soil_cancel_btn.clicked.disconnect(worker.cancel)
        except Exception:  # noqa: BLE001
            pass
        main.site_panel.set_soil_download_status(None, busy=False)
        worker.deleteLater()
        thread.deleteLater()
        main._soil_dl_worker = None
        main._soil_dl_thread = None

    thread.started.connect(worker.run)
    worker.progress.connect(_progress)
    worker.finished.connect(_finished)
    worker.error.connect(_error)
    worker.finished.connect(thread.quit)
    worker.error.connect(thread.quit)
    thread.finished.connect(_done)
    main.site_panel._soil_cancel_btn.clicked.connect(worker.cancel)
    thread.start()
