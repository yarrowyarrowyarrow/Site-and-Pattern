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

import uuid
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
    "feature_id",
)


def _close(a: float, b: float, tol: float = COORD_TOL_DEG) -> bool:
    return abs(float(a) - float(b)) < tol


def _same_spot(pid_a, lat_a, lng_a, pid_b, lat_b, lng_b) -> bool:
    """One matcher for 'same plant at the same place', everywhere. Uses
    _close on both axes — the batch path used to round to 7 dp instead,
    so a pair straddling a rounding boundary (e.g. …45 vs …44, well
    inside tolerance) matched in single-remove but not batch-remove."""
    try:
        if int(pid_a) != int(pid_b):
            return False
    except (TypeError, ValueError):
        return False
    return _close(lat_a, lat_b) and _close(lng_a, lng_b)


def new_feature_id() -> str:
    """Mint a stable identity for one placed feature (project-file scoped).

    Identity-by-(plant_id, float coords) is ambiguous the moment area fill
    or a generated design drops duplicate species side by side; the id is
    what mutators should target. Legacy features without one keep working
    through the coordinate fallback."""
    return "pf_" + uuid.uuid4().hex[:12]


def plant_feature(record: dict, *, pattern_kind: str = "",
                  quantity: int = 1) -> dict:
    """Build the canonical GeoJSON Feature for a placed-plant ``record``.

    ``record`` must have ``plant_id``, ``common_name``, ``lat``, ``lng``;
    the optional polyculture/group fields are copied across when set.
    ``pattern_kind`` / ``quantity`` are feature-only metadata (how the
    plant was placed; how many it represents in a generated design).

    Mints a ``feature_id`` when the record has none, and writes it back
    into ``record`` — deliberate side effect, so the caller's index entry
    and the feature share one identity from birth.
    """
    if not record.get("feature_id"):
        record["feature_id"] = new_feature_id()
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

    def rebuild_index(self) -> None:
        """Rebuild the placed-plants index in place from the current
        features. Used by undo/redo snapshot restore, which swaps the whole
        ``features`` list at once (bypassing the per-plant mutators) and then
        needs the index brought back into agreement with it."""
        self._placed[:] = self.records_from_features()

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
                     newest_first: bool = False,
                     feature_id: str = "") -> Optional[dict]:
        """Remove ONE plant from both structures. With ``feature_id`` the
        match is exact (the feature's own coords then drive the index-side
        match, so duplicate-position plants are unambiguous); otherwise
        id + coords with ``newest_first`` picking the most recently placed
        match (undo semantics) or the oldest (right-click-delete semantics,
        the historical default). Returns the removed record, or None."""
        feats = self.features
        if feature_id:
            for i, f in enumerate(feats):
                props = f.get("properties", {})
                if (props.get("element_type") == "plant"
                        and props.get("feature_id") == feature_id):
                    coords = f.get("geometry", {}).get("coordinates", [0, 0])
                    feats.pop(i)
                    return self._pop_index_entry(
                        props.get("plant_id"), coords[1], coords[0],
                        feature_id=feature_id, newest_first=newest_first)
            # Unknown id (legacy feature / stale caller) → coordinate path.

        removed = self._pop_index_entry(plant_id, lat, lng,
                                        newest_first=newest_first)
        findices = range(len(feats) - 1, -1, -1) if newest_first \
            else range(len(feats))
        for i in findices:
            f = feats[i]
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            if (props.get("element_type") == "plant" and len(coords) >= 2
                    and _same_spot(props.get("plant_id"), coords[1], coords[0],
                                   plant_id, lat, lng)):
                feats.pop(i)
                break
        return removed

    def _pop_index_entry(self, plant_id, lat, lng, *, feature_id: str = "",
                         newest_first: bool = False) -> Optional[dict]:
        """Remove and return one index record — by feature_id when both
        sides carry one, else by id + coords tolerance."""
        indices = range(len(self._placed) - 1, -1, -1) if newest_first \
            else range(len(self._placed))
        if feature_id:
            for i in indices:
                if self._placed[i].get("feature_id") == feature_id:
                    return self._placed.pop(i)
            indices = range(len(self._placed) - 1, -1, -1) if newest_first \
                else range(len(self._placed))
        for i in indices:
            p = self._placed[i]
            if _same_spot(p["plant_id"], p["lat"], p["lng"],
                          plant_id, lat, lng):
                return self._placed.pop(i)
        return None

    def remove_plants_batch(self, keys: Iterable[tuple]) -> list[dict]:
        """Remove many plants in one pass. ``keys`` is an iterable of
        ``(plant_id, lat, lng)``; duplicate keys remove duplicate-position
        plants exactly once each (multiset semantics). Returns the removed
        records.

        Matching uses the same _close tolerance as every other mutator —
        this path historically rounded to 7 dp instead, so a JS round-trip
        pair straddling a rounding boundary silently failed to batch-remove."""
        keys = [(pid, lat, lng) for pid, lat, lng in keys]  # may be a generator
        pending = list(keys)

        def _take(pid, lat, lng) -> bool:
            for i, (wp, wlat, wlng) in enumerate(pending):
                if _same_spot(pid, lat, lng, wp, wlat, wlng):
                    pending.pop(i)
                    return True
            return False

        removed: list[dict] = []
        kept_plants = []
        for p in self._placed:
            if pending and _take(p["plant_id"], p["lat"], p["lng"]):
                removed.append(p)
            else:
                kept_plants.append(p)
        self._placed[:] = kept_plants

        pending = list(keys)
        kept_features = []
        for f in self.features:
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            if (props.get("element_type") == "plant" and len(coords) >= 2
                    and pending
                    and _take(props.get("plant_id"), coords[1], coords[0])):
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
                   group_id: Optional[str] = None,
                   feature_id: str = "") -> bool:
        """Move one plant to the new coords, in both structures. With
        ``feature_id`` the feature match is exact; otherwise id + old
        coords, with ``group_id`` additionally constraining the feature
        match (group drags pass it so identically-positioned plants in
        other groups stay put). Returns True when the index entry moved."""
        target_fid = feature_id
        feature = None
        for f in self.features:
            props = f.get("properties", {})
            if props.get("element_type") != "plant":
                continue
            coords = f.get("geometry", {}).get("coordinates", [])
            if target_fid:
                if props.get("feature_id") == target_fid:
                    feature = f
                    break
            elif (len(coords) >= 2
                    and (group_id is None
                         or props.get("placement_group_id") == group_id)
                    and _same_spot(props.get("plant_id"), coords[1], coords[0],
                                   plant_id, old_lat, old_lng)):
                feature = f
                target_fid = props.get("feature_id") or ""
                break
        if feature is not None:
            feature["geometry"]["coordinates"] = [new_lng, new_lat]

        # Index side: prefer the identity the feature carries, so duplicate-
        # position plants move the SAME entry the feature match picked.
        moved = False
        for p in self._placed:
            if target_fid and p.get("feature_id"):
                if p["feature_id"] != target_fid:
                    continue
            elif not _same_spot(p["plant_id"], p["lat"], p["lng"],
                                plant_id, old_lat, old_lng):
                continue
            p["lat"], p["lng"] = new_lat, new_lng
            moved = True
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
