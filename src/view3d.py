"""
view3d.py — Three.js-based 3D visualisation of the current PermaDesign project.

Opens a resizable QDialog containing a QWebEngineView that loads html/view3d.html.
After the page loads, the current project GeoJSON is serialised and pushed to the
Three.js scene via runJavaScript so no QWebChannel round-trip is needed.

Plant and structure features must have coordinates in [lng, lat] order (standard
GeoJSON) and the following properties for accurate 3D rendering:
  - element_type : "plant" | "structure"
  - plant_type   : tree | shrub | herb | groundcover | vine | root
  - mature_height_meters / height_m : float
  - spacing_meters : float
  - common_name    : str
  - struct_id      : str  (for structures)
  - size_m         : float (for structures)
"""

from __future__ import annotations
import json
import os

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QDialog, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

from src.paths import resource_path


class View3DDialog(QDialog):
    """Floating 3D view window."""

    def __init__(self, project: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PermaDesign — 3D View")
        self.resize(1100, 700)
        self._project = project

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._view = QWebEngineView()
        s = self._view.page().settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        layout.addWidget(self._view)

        html_path = resource_path(os.path.join("html", "view3d.html"))
        self._view.load(QUrl.fromLocalFile(html_path))
        self._view.loadFinished.connect(self._on_load_finished)

    def _on_load_finished(self, ok: bool):
        if not ok:
            return
        # json.dumps the project dict to a JSON string, then json.dumps again to
        # produce a JS string literal that survives injection into runJavaScript.
        js_str_literal = json.dumps(json.dumps(self._project))
        self._view.page().runJavaScript(f"loadProjectData({js_str_literal});")
