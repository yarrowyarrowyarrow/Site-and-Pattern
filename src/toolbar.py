from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QToolBar, QWidget


class MainToolBar(QToolBar):
    drawBoundary = pyqtSignal()
    drawZones = pyqtSignal()
    toggleSatellite = pyqtSignal()
    cancelDrawing = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Tools", parent)
        self.setMovable(False)

        self.boundary_action = self.addAction("Draw Boundary")
        self.boundary_action.triggered.connect(self.drawBoundary.emit)

        self.zones_action = self.addAction("Draw Zones")
        self.zones_action.triggered.connect(self.drawZones.emit)

        self.addSeparator()

        self.satellite_action = self.addAction("Toggle Satellite")
        self.satellite_action.triggered.connect(self.toggleSatellite.emit)

        self.addSeparator()

        self.cancel_action = self.addAction("Cancel Drawing")
        self.cancel_action.triggered.connect(self.cancelDrawing.emit)
