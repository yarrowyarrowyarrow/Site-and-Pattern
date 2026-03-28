import json
import os

from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView


class MapBridge(QObject):
    """Bridge between JavaScript map and Python."""

    mapClicked = pyqtSignal(float, float)
    mouseMoved = pyqtSignal(float, float)
    boundaryCompleted = pyqtSignal(str)  # JSON coords
    plantPlaced = pyqtSignal(int, str, float, float)  # id, name, lat, lng
    guildPlaced = pyqtSignal(str, float, float)  # guild JSON, lat, lng
    zonesDrawn = pyqtSignal(float, float, str)  # lat, lng, radii JSON

    @pyqtSlot(float, float)
    def onMapClick(self, lat, lng):
        self.mapClicked.emit(lat, lng)

    @pyqtSlot(float, float)
    def onMouseMove(self, lat, lng):
        self.mouseMoved.emit(lat, lng)

    @pyqtSlot(str)
    def onBoundaryComplete(self, coords_json):
        self.boundaryCompleted.emit(coords_json)

    @pyqtSlot(int, str, float, float)
    def onPlantPlaced(self, plant_id, name, lat, lng):
        self.plantPlaced.emit(plant_id, name, lat, lng)

    @pyqtSlot(str, float, float)
    def onGuildPlaced(self, guild_json, lat, lng):
        self.guildPlaced.emit(guild_json, lat, lng)

    @pyqtSlot(float, float, str)
    def onZonesDrawn(self, lat, lng, radii_json):
        self.zonesDrawn.emit(lat, lng, radii_json)


class MapWidget(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bridge = MapBridge()
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.page().setWebChannel(self.channel)

        # Allow local HTML to load remote CDN resources (Leaflet tiles & JS)
        settings = self.page().settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        html_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "html", "map.html"
        )
        self.setUrl(QUrl.fromLocalFile(html_path))

    def run_js(self, js):
        self.page().runJavaScript(js)

    def set_drawing_mode(self, mode):
        self.run_js(f"setDrawingMode('{mode}')" if mode else "setDrawingMode(null)")

    def set_pending_plant(self, plant_id, name, plant_type):
        name_escaped = name.replace("'", "\\'")
        type_escaped = plant_type.replace("'", "\\'")
        self.run_js(f"setPendingPlant({plant_id}, '{name_escaped}', '{type_escaped}')")
        self.set_drawing_mode("plant")

    def set_pending_guild(self, guild_data):
        guild_json = json.dumps(guild_data).replace("'", "\\'")
        self.run_js(f"setPendingGuild('{guild_json}')")
        self.set_drawing_mode("guild")

    def clear_pending(self):
        self.run_js("clearPending()")

    def toggle_satellite(self):
        self.run_js("toggleSatellite()")

    def clear_all(self):
        self.run_js("clearAllMarkers()")

    def draw_zone_circles(self, lat, lng, radii):
        radii_json = json.dumps(radii)
        self.run_js(f"drawZoneCircles({lat}, {lng}, {radii_json})")

    def load_boundary(self, coords):
        self.run_js(f"loadBoundary('{json.dumps(coords)}')")

    def load_plant(self, plant_id, name, plant_type, lat, lng):
        name_escaped = name.replace("'", "\\'")
        type_escaped = plant_type.replace("'", "\\'")
        self.run_js(f"loadPlant({plant_id}, '{name_escaped}', '{type_escaped}', {lat}, {lng})")

    def load_zones(self, lat, lng, radii):
        self.run_js(f"loadZones({lat}, {lng}, '{json.dumps(radii)}')")

    def load_guild(self, guild_data, lat, lng):
        guild_json = json.dumps(guild_data).replace("'", "\\'")
        self.run_js(f"loadGuild('{guild_json}', {lat}, {lng})")

    def fit_to_boundary(self):
        self.run_js("fitToBoundary()")
