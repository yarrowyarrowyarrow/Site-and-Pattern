"""Save and load project files in .perma.geojson format."""
import json
import os
import tempfile
from datetime import datetime

from PyQt6.QtCore import QTimer


class ProjectManager:
    def __init__(self):
        self.file_path = None
        self.project_name = "Untitled"
        self.hardiness_zone = None
        self.notes = ""
        self.boundary_coords = None  # [[lng, lat], ...]
        self.placed_plants = []  # [{"plant_id", "common_name", "plant_type", "lat", "lng"}, ...]
        self.zone_center = None  # {"lat", "lng", "radii": [...]}
        self.placed_guilds = []  # [{"guild_data": {...}, "lat", "lng"}, ...]
        self.modified = False

        # Auto-save timer
        self._autosave_timer = QTimer()
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start(5 * 60 * 1000)  # 5 minutes

    def new_project(self):
        self.file_path = None
        self.project_name = "Untitled"
        self.hardiness_zone = None
        self.notes = ""
        self.boundary_coords = None
        self.placed_plants = []
        self.zone_center = None
        self.placed_guilds = []
        self.modified = False

    def to_geojson(self):
        features = []

        if self.boundary_coords:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [self.boundary_coords + [self.boundary_coords[0]]]
                },
                "properties": {"element_type": "property_boundary"}
            })

        for p in self.placed_plants:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [p["lng"], p["lat"]]
                },
                "properties": {
                    "element_type": "plant",
                    "plant_id": p["plant_id"],
                    "common_name": p["common_name"],
                    "plant_type": p.get("plant_type", ""),
                    "quantity": 1
                }
            })

        if self.zone_center:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [self.zone_center["lng"], self.zone_center["lat"]]
                },
                "properties": {
                    "element_type": "zone_center",
                    "zone_radii": self.zone_center["radii"]
                }
            })

        for g in self.placed_guilds:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [g["lng"], g["lat"]]
                },
                "properties": {
                    "element_type": "guild_placement",
                    "guild_name": g["guild_data"].get("name", ""),
                    "members": g["guild_data"].get("members", [])
                }
            })

        return {
            "type": "FeatureCollection",
            "properties": {
                "project_name": self.project_name,
                "created": datetime.now().isoformat(),
                "hardiness_zone": self.hardiness_zone,
                "notes": self.notes
            },
            "features": features
        }

    def save(self, path=None):
        if path:
            self.file_path = path
        if not self.file_path:
            return False

        data = self.to_geojson()
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.modified = False
        return True

    def load(self, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self.new_project()
        self.file_path = path

        props = data.get("properties", {})
        self.project_name = props.get("project_name", "Untitled")
        self.hardiness_zone = props.get("hardiness_zone")
        self.notes = props.get("notes", "")

        for feature in data.get("features", []):
            geom = feature.get("geometry", {})
            fprops = feature.get("properties", {})
            etype = fprops.get("element_type")

            if etype == "property_boundary" and geom.get("type") == "Polygon":
                coords = geom["coordinates"][0]
                # Remove closing duplicate point if present
                if coords and coords[0] == coords[-1]:
                    coords = coords[:-1]
                self.boundary_coords = coords

            elif etype == "plant" and geom.get("type") == "Point":
                lng, lat = geom["coordinates"]
                self.placed_plants.append({
                    "plant_id": fprops.get("plant_id"),
                    "common_name": fprops.get("common_name", ""),
                    "plant_type": fprops.get("plant_type", ""),
                    "lat": lat,
                    "lng": lng
                })

            elif etype == "zone_center" and geom.get("type") == "Point":
                lng, lat = geom["coordinates"]
                self.zone_center = {
                    "lat": lat, "lng": lng,
                    "radii": fprops.get("zone_radii", [5, 15, 30, 60, 120])
                }

            elif etype == "guild_placement" and geom.get("type") == "Point":
                lng, lat = geom["coordinates"]
                self.placed_guilds.append({
                    "guild_data": {
                        "name": fprops.get("guild_name", ""),
                        "members": fprops.get("members", [])
                    },
                    "lat": lat, "lng": lng
                })

        self.modified = False
        return True

    def _autosave(self):
        if not self.modified:
            return
        tmp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, "permadesign_autosave.perma.geojson")
        data = self.to_geojson()
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
