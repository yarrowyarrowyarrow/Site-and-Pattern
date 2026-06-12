"""
src/project_store.py — single write path for placed-plant state (V1.62).

Placed plants live in two structures that MUST stay in sync:

  * ``project["features"]`` — the canonical GeoJSON FeatureCollection that
    save/load, the habitat score, exclusion zones, and the generator all
    read. One Point feature per plant.
  * ``placed_plants`` — a denormalized plants-only index used by the
    planning/analysis panels and plant-count badges, kept because scanning
    it is much cheaper than filtering the mixed-type feature list on every
    UI refresh.

Historically every placement gesture (single click, pattern, community,
area fill, generated design, undo, redo, drag) appended/removed/moved
entries in BOTH structures by hand, in eight-plus call sites. A missed
update in any one of them silently desynced the map, the saved file, and
the analytics. This module centralizes those mutations:

  * ``ProjectStore`` owns both structures and exposes the only supported
    mutation methods: ``add_plant`` / ``remove_plant`` /
    ``remove_plants_batch`` / ``remove_polyculture`` / ``move_plant``.
  * ``plant_feature`` / ``plant_record_from_feature`` are the one
    record↔feature converter pair, so the two shapes can't drift.
  * ``check_consistency`` rebuilds the index from the features and reports
    any mismatch — tests/test_project_store.py asserts it stays empty
    through a scripted editing session, and greps the source tree so no
    new direct ``_placed_plants.append`` call sites appear.

Qt-free on purpose: the map widget / panel side effects stay at the call
sites; the store only guarantees the two data structures agree.
"""

from __future__ import annotations

from typing import Iterable, Optional

# Coordinate tolerance for matching a plant by position. 1e-7 deg ≈ 1 cm —
# tight enough to distinguish neighbouring plants, loose enough to absorb
# float noise from the JS round-trip (Leaflet hands coordinates back through
# JSON). The same value the scattered hand-written matchers used.
COORD_TOL_DEG = 1e-7

# Record/property fields that are only present when meaningful — omitted
# (not written as ""/None) so saved files keep the shape the hand-written
# call sites produced.
_OPTIONAL_FIELDS = (
    "polyculture_name",
    "polyculture_center_lat",
    "polyculture_center_lng",
    "placement_group_id",
)


def _close(a: float, b: float, tol: float = COORD_TOL_DEG) -> bool:
    return abs(float(a) - float(b)) < tol


def _key(plant_id, lat, lng) -> tuple:
    """Multiset key for batch matching: id + coords rounded to the same
    precision COORD_TOL_DEG implies."""
    return (int(plant_id), round(float(lat), 7), round(float(lng), 7))


def plant_feature(record: dict, *, pattern_kind: str = "",
                  quantity: int = 1) -> dict:
    """Build the canonical GeoJSON Feature for a placed-plant ``record``.

    ``record`` must have ``plant_id``, ``common_name``, ``lat``, ``lng``;
    the optional polyculture/group fields are copied across when set.
    ``pattern_kind`` / ``quantity`` are feature-only metadata (how the
    plant was placed; how many it represents in a generated design).
    """
    props: dict = {
        "element_type": "plant",
        "plant_id": record["plant_id"],
        "common_name": record.get("common_name", ""),
    }
    for k in _OPTIONAL_FIELDS:
        v = record.get(k)
        if v not in (None, ""):
            props[k] = v
    if pattern_kind:
        props["pattern_kind"] = pattern_kind
    props["quantity"] = quantity
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [record["lng"], record["lat"]],
        },
        "properties": props,
    }


def plant_record_from_feature(feature: dict) -> Optional[dict]:
    """Inverse of ``plant_feature`` — the placed-plants index entry for a
    plant Point feature, or None for any other feature."""
    props = feature.get("properties", {}) or {}
    geom = feature.get("geometry", {}) or {}
    if props.get("element_type") != "plant" or geom.get("type") != "Point":
        return None
    coords = geom.get("coordinates") or []
    if len(coords) < 2:
        return None
    record = {
        "plant_id": props.get("plant_id", 0),
        "common_name": props.get("common_name", ""),
        "lat": coords[1],
        "lng": coords[0],
    }
    for k in _OPTIONAL_FIELDS:
        v = props.get(k)
        if v not in (None, ""):
            record[k] = v
    return record


def _normalized(record: dict) -> tuple:
    """Comparison key for consistency checks. Tolerates the two historical
    record shapes (optional keys omitted vs present-but-empty)."""
    return (
        int(record.get("plant_id", 0)),
        round(float(record.get("lat", 0.0)), 7),
        round(float(record.get("lng", 0.0)), 7),
        record.get("placement_group_id") or "",
        record.get("polyculture_name") or "",
    )


class ProjectStore:
    """Owns the project dict + placed-plants index and keeps them in sync.

    Can wrap externally-created structures (the controller tests build
    bare ``{"features": []}`` projects) — mutations are always in-place so
    callers holding the same references observe every change.
    """

    def __init__(self, project: Optional[dict] = None,
                 placed_plants: Optional[list] = None):
        self._project = project if project is not None else {
            "type": "FeatureCollection", "properties": {}, "features": [],
        }
        self._project.setdefault("features", [])
        if placed_plants is None:
            placed_plants = self.records_from_features()
        self._placed = placed_plants

    # ── access ────────────────────────────────────────────────────────────

    @property
    def project(self) -> dict:
        return self._project

    @property
    def placed_plants(self) -> list:
        return self._placed

    @property
    def features(self) -> list:
        return self._project["features"]

    # ── whole-state replacement (new / load) ─────────────────────────────

    def set_project(self, project: dict) -> None:
        """Adopt a new project dict (File → New / Open) and rebuild the
        placed-plants index from its features."""
        project.setdefault("features", [])
        self._project = project
        self._placed[:] = self.records_from_features()

    def replace_placed_plants(self, records: Iterable[dict]) -> None:
        """Replace the index in place (load paths that mint group ids while
        building richer records than the bare feature rebuild gives)."""
        self._placed[:] = list(records)

    # ── mutations ─────────────────────────────────────────────────────────

    def add_plant(self, plant_id: int, common_name: str,
                  lat: float, lng: float, *,
                  placement_group_id: str = "",
                  polyculture_name: str = "",
                  polyculture_center_lat=None,
                  polyculture_center_lng=None,
                  pattern_kind: str = "",
                  quantity: int = 1) -> dict:
        """Append one placed plant to both structures. Returns the index
        record (callers feed it to the map widget / panels)."""
        record = {
            "plant_id": plant_id, "common_name": common_name,
            "lat": lat, "lng": lng,
        }
        if polyculture_name:
            record["polyculture_name"] = polyculture_name
        if polyculture_center_lat is not None:
            record["polyculture_center_lat"] = polyculture_center_lat
        if polyculture_center_lng is not None:
            record["polyculture_center_lng"] = polyculture_center_lng
        if placement_group_id:
            record["placement_group_id"] = placement_group_id
        self._placed.append(record)
        self.features.append(
            plant_feature(record, pattern_kind=pattern_kind,
                          quantity=quantity))
        return record

    def remove_plant(self, plant_id: int, lat: float, lng: float, *,
                     newest_first: bool = False) -> Optional[dict]:
        """Remove ONE plant matching id + coords from both structures.
        ``newest_first`` removes the most recently placed match (undo
        semantics); the default removes the oldest (right-click-delete
        semantics, matching the historical handlers). Returns the removed
        record, or None if nothing matched."""
        indices = range(len(self._placed) - 1, -1, -1) if newest_first \
            else range(len(self._placed))
        removed = None
        for i in indices:
            p = self._placed[i]
            if (p["plant_id"] == plant_id and _close(p["lat"], lat)
                    and _close(p["lng"], lng)):
                removed = self._placed.pop(i)
                break

        feats = self.features
        findices = range(len(feats) - 1, -1, -1) if newest_first \
            else range(len(feats))
        for i in findices:
            f = feats[i]
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            if (props.get("element_type") == "plant"
                    and props.get("plant_id") == plant_id
                    and len(coords) >= 2
                    and _close(coords[1], lat) and _close(coords[0], lng)):
                feats.pop(i)
                break
        return removed

    def remove_plants_batch(self, keys: Iterable[tuple]) -> list[dict]:
        """Remove many plants in one pass. ``keys`` is an iterable of
        ``(plant_id, lat, lng)``; duplicate keys remove duplicate-position
        plants exactly once each (multiset semantics). Returns the removed
        records."""
        want: dict = {}
        for pid, lat, lng in keys:
            k = _key(pid, lat, lng)
            want[k] = want.get(k, 0) + 1

        removed: list[dict] = []
        kept_plants = []
        budget = dict(want)
        for p in self._placed:
            k = _key(p["plant_id"], p["lat"], p["lng"])
            if budget.get(k, 0) > 0:
                budget[k] -= 1
                removed.append(p)
            else:
                kept_plants.append(p)
        self._placed[:] = kept_plants

        budget = dict(want)
        kept_features = []
        for f in self.features:
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            if props.get("element_type") == "plant" and len(coords) >= 2:
                fk = _key(props.get("plant_id"), coords[1], coords[0])
                if budget.get(fk, 0) > 0:
                    budget[fk] -= 1
                    continue
            kept_features.append(f)
        self.features[:] = kept_features
        return removed

    def remove_polyculture(self, polyculture_name: str,
                           center_lat: float, center_lng: float) -> int:
        """Remove every member of one placed community instance, identified
        by the polyculture_center anchor it was tagged with at placement
        time. Returns the number of plants removed."""
        def _member(name, anchor_lat, anchor_lng) -> bool:
            if name != polyculture_name:
                return False
            if anchor_lat is None or anchor_lng is None:
                return False
            return (_close(anchor_lat, center_lat)
                    and _close(anchor_lng, center_lng))

        kept_plants = [
            p for p in self._placed
            if not _member(p.get("polyculture_name"),
                           p.get("polyculture_center_lat"),
                           p.get("polyculture_center_lng"))
        ]
        removed = len(self._placed) - len(kept_plants)
        self._placed[:] = kept_plants

        self.features[:] = [
            f for f in self.features
            if not (f.get("properties", {}).get("element_type") == "plant"
                    and _member(f["properties"].get("polyculture_name"),
                                f["properties"].get("polyculture_center_lat"),
                                f["properties"].get("polyculture_center_lng")))
        ]
        return removed

    def move_plant(self, plant_id: int, old_lat: float, old_lng: float,
                   new_lat: float, new_lng: float, *,
                   group_id: Optional[str] = None) -> bool:
        """Move one plant matching id + old coords to the new coords, in
        both structures. ``group_id`` additionally constrains the feature
        match (group drags pass it so identically-positioned plants in
        other groups stay put). Returns True when the index entry moved."""
        moved = False
        for p in self._placed:
            if (p["plant_id"] == plant_id and _close(p["lat"], old_lat)
                    and _close(p["lng"], old_lng)):
                p["lat"], p["lng"] = new_lat, new_lng
                moved = True
                break
        for f in self.features:
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            if (props.get("element_type") == "plant"
                    and props.get("plant_id") == plant_id
                    and (group_id is None
                         or props.get("placement_group_id") == group_id)
                    and len(coords) >= 2
                    and _close(coords[1], old_lat)
                    and _close(coords[0], old_lng)):
                f["geometry"]["coordinates"] = [new_lng, new_lat]
                break
        return moved

    # ── consistency ───────────────────────────────────────────────────────

    def records_from_features(self) -> list[dict]:
        """Derive the placed-plants index from the project features."""
        out = []
        for f in self._project.get("features", []):
            r = plant_record_from_feature(f)
            if r is not None:
                out.append(r)
        return out

    def check_consistency(self) -> list[str]:
        """Compare the maintained index against a rebuild from the
        features. Returns a list of human-readable mismatches — empty when
        the two structures agree."""
        problems: list[str] = []
        maintained = sorted(_normalized(r) for r in self._placed)
        derived = sorted(_normalized(r) for r in self.records_from_features())
        if len(maintained) != len(derived):
            problems.append(
                f"index has {len(maintained)} plants, features have "
                f"{len(derived)}")
        for m, d in zip(maintained, derived):
            if m != d:
                problems.append(f"index {m} != features {d}")
                break
        return problems


def store_for(main) -> ProjectStore:
    """The ProjectStore for a MainWindow — or, for the lightweight fake
    mains the controller tests build, a store wrapped around the fake's
    own ``_project`` / ``_placed_plants`` references (in-place mutation
    keeps the fake's attributes observing every change)."""
    store = getattr(main, "_store", None)
    if store is None:
        store = ProjectStore(main._project,
                             getattr(main, "_placed_plants", None))
        try:
            main._store = store
        except Exception:
            pass
    return store
