"""
design_api.py — Programmatic interface for generating landscape designs.

Intended for use by AI agents, automation scripts, or future API endpoints.
Accepts site configuration and priorities, returns a complete project dict
that can be saved via project.save_project().

This is the foundational scaffolding for v1.5 — not yet connected to any
AI model, but establishes the interface a future auto-generation system
would use.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from src.project import new_project, SCHEMA_VERSION
from src.db.plants import get_plant, search_plants, get_companions
from src.db.guilds import get_guild_by_id, get_all_guilds


class DesignGenerator:
    """
    Programmatic interface for generating landscape designs without UI.

    Usage:
        gen = DesignGenerator({"latitude": 53.5, "longitude": -113.5, ...})
        gen.set_boundary([(53.55, -113.50), (53.55, -113.49), ...])
        gen.add_plant(plant_id=1, lat=53.551, lng=-113.495)
        gen.add_guild(guild_id=1, center_lat=53.552, center_lng=-113.496)
        gen.add_structure("pond", lat=53.553, lng=-113.497)
        project = gen.get_project()
    """

    def __init__(self, site_config: Optional[dict] = None):
        name = (site_config or {}).get("name", "Generated Design")
        self.project = new_project(name)
        if site_config:
            sc = self.project["properties"]["site_config"]
            for key in ("latitude", "longitude", "area_m2", "hardiness_zone",
                        "soil_type", "sun_exposure", "wind_exposure", "priorities"):
                if key in site_config:
                    sc[key] = site_config[key]

    def set_boundary(self, coords: list[tuple[float, float]],
                     color: str = "green") -> None:
        """Set the property boundary. coords: list of (lat, lng) tuples."""
        import uuid
        # Remove any existing boundary with the same id (or old singleton entries)
        self.project["features"] = [
            f for f in self.project["features"]
            if f.get("properties", {}).get("element_type") != "property_boundary"
        ]
        ring = [[lng, lat] for lat, lng in coords]
        if ring and ring[0] != ring[-1]:
            ring.append(ring[0])
        self.project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "element_type": "property_boundary",
                "boundary_id": "b_api_" + uuid.uuid4().hex[:8],
                "color": color,
                "show_lengths": True,
                "show_area": True,
            }
        })

    def add_plant(self, plant_id: int, lat: float, lng: float,
                  guild_name: str = "", quantity: int = 1) -> None:
        """Place a plant at the given coordinates."""
        plant = get_plant(plant_id)
        common_name = plant["common_name"] if plant else f"Plant #{plant_id}"
        self.project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": "plant",
                "plant_id": plant_id,
                "common_name": common_name,
                "guild_name": guild_name,
                "quantity": quantity,
            }
        })

    def add_guild(self, guild_id: int, center_lat: float, center_lng: float) -> None:
        """Place a full guild at the given center coordinates."""
        guild = get_guild_by_id(guild_id)
        if not guild:
            return
        guild_name = guild["name"]
        members = guild.get("members", [])

        for m in members:
            lat_offset = (m.get("offset_y", 0)) / 111320
            lng_offset = (m.get("offset_x", 0)) / (
                111320 * math.cos(center_lat * math.pi / 180))
            mlat = center_lat + lat_offset
            mlng = center_lng + lng_offset
            self.add_plant(m["plant_id"], mlat, mlng, guild_name=guild_name)

    def add_structure(self, struct_id: str, lat: float, lng: float,
                      struct_def: Optional[dict] = None) -> None:
        """Place a structure at the given coordinates."""
        self.project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": "structure",
                "struct_def": struct_def or {"id": struct_id},
            }
        })

    # ── Query / discovery helpers ─────────────────────────────────────────────

    def search_plants(self, **kwargs) -> list[dict]:
        """Search the plant catalogue. Accepts all search_plants() kwargs."""
        return search_plants(**kwargs)

    def get_plant_details(self, plant_id: int) -> Optional[dict]:
        """Return full plant record with companion relationships."""
        plant = get_plant(plant_id)
        if plant is None:
            return None
        return {"plant": plant, "companions": get_companions(plant_id)}

    def list_guilds(self) -> list[dict]:
        """Return all seeded polyculture guilds (top-level only)."""
        return get_all_guilds(top_level_only=True)

    def get_guild_details(self, guild_id: int) -> Optional[dict]:
        """Return a guild with its full member list."""
        return get_guild_by_id(guild_id)

    def list_saved_recipes(self) -> list[dict]:
        """Return user-saved polyculture mixes from settings (empty if Qt unavailable)."""
        try:
            from src.settings import get_polyculture_recipes
            return get_polyculture_recipes()
        except ImportError:
            return []

    # ── Project output ────────────────────────────────────────────────────────

    def add_zone_center(self, lat: float, lng: float) -> None:
        """Set the permaculture zone center point."""
        self.project["features"] = [
            f for f in self.project["features"]
            if f.get("properties", {}).get("element_type") != "zone_center"
        ]
        self.project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {"element_type": "zone_center"}
        })

    def get_project(self) -> dict:
        """Return the complete project dict, ready for save_project()."""
        return self.project

    def validate(self) -> list[dict]:
        """Return structured issues about the generated design.

        Each entry: {"type": str, "message": str, "severity": "warning"|"error"}
        """
        issues = []

        has_boundary = any(
            f.get("properties", {}).get("element_type") == "property_boundary"
            for f in self.project["features"]
        )
        if not has_boundary:
            issues.append({"type": "no_boundary", "message": "No property boundary defined", "severity": "warning"})

        plant_count = sum(
            1 for f in self.project["features"]
            if f.get("properties", {}).get("element_type") == "plant"
        )
        if plant_count == 0:
            issues.append({"type": "no_plants", "message": "No plants placed", "severity": "warning"})

        sc = self.project["properties"].get("site_config", {})
        if not sc.get("latitude") or not sc.get("longitude"):
            issues.append({"type": "no_coordinates", "message": "Site coordinates not set in site_config", "severity": "error"})
        if not sc.get("hardiness_zone"):
            issues.append({"type": "no_zone", "message": "Hardiness zone not set", "severity": "warning"})

        return issues
