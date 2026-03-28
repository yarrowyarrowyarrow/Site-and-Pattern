"""
permapeople.py — Client for the Permapeople plant API.

API base : https://permapeople.org/api
Auth     : x-permapeople-key-id  +  x-permapeople-key-secret  headers
Search   : GET /plants/search?q=<term>
Single   : GET /plants/<id>

All network calls run inside PerpapeopleWorker (QThread) so the UI never
blocks.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

_BASE_URL = "https://permapeople.org/api"


# ── Low-level request helper ──────────────────────────────────────────────────

def _get(path: str, key_id: str, key_secret: str,
         params: Optional[dict] = None) -> dict | list:
    """Make a GET request and return parsed JSON."""
    url = _BASE_URL + path
    if params:
        query = "&".join(
            f"{k}={urllib.request.quote(str(v))}" for k, v in params.items()
        )
        url = url + "?" + query

    req = urllib.request.Request(url, method="GET")
    req.add_header("x-permapeople-key-id",    key_id)
    req.add_header("x-permapeople-key-secret", key_secret)
    req.add_header("Accept",                   "application/json")
    req.add_header("User-Agent",               "PermaDesign/1.0")
    return _execute(req)


def _post(path: str, key_id: str, key_secret: str,
          body: dict) -> dict | list:
    """Make a POST request with a JSON body and return parsed JSON."""
    url = _BASE_URL + path
    data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("x-permapeople-key-id",    key_id)
    req.add_header("x-permapeople-key-secret", key_secret)
    req.add_header("Content-Type",             "application/json")
    req.add_header("Accept",                   "application/json")
    req.add_header("User-Agent",               "PermaDesign/1.0")
    return _execute(req)


def _execute(req: urllib.request.Request) -> dict | list:
    """Execute a prepared request and return parsed JSON."""
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"HTTP {exc.code} from Permapeople API: {body[:200]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Network error contacting Permapeople: {exc.reason}"
        ) from exc


# ── Field mapping ─────────────────────────────────────────────────────────────

def _normalize_plant(raw: dict) -> dict:
    """
    Map a Permapeople API plant object to our internal schema dict.
    Unknown / absent fields are left as None so callers can decide defaults.
    """
    # Permapeople uses 'data' sub-key for extended attributes (must be a dict)
    _data_raw = raw.get("data")
    data = _data_raw if isinstance(_data_raw, dict) else {}

    def _get(*keys):
        """Try each key in order, return first non-None / non-empty value."""
        for k in keys:
            v = raw.get(k) or data.get(k)
            if v not in (None, "", [], {}):
                return v
        return None

    # Map permaculture functions to our internal tags
    raw_functions = _get("functions", "permaculture_functions", "uses") or []
    if isinstance(raw_functions, str):
        raw_functions = [f.strip() for f in raw_functions.split(",")]
    perm_uses = _map_functions(raw_functions)

    # Map sun requirement
    sun_raw = (_get("sun", "sun_requirements", "light") or "").lower()
    sun = _map_sun(sun_raw)

    # Map water needs
    water_raw = (_get("water", "water_requirements", "moisture") or "").lower()
    water = _map_water(water_raw)

    # Map plant type
    type_raw = (_get("type", "plant_type", "category", "life_form") or "").lower()
    plant_type = _map_type(type_raw)

    # Spacing / height — Permapeople often gives these in cm or m
    spacing = _parse_measure(_get("spacing", "plant_spacing", "spacing_meters"))
    height  = _parse_measure(_get("height", "mature_height", "max_height"))

    return {
        # Identity
        "permapeople_id":  _get("id", "slug"),
        "common_name":     _get("name", "common_name", "title") or "Unknown Plant",
        "scientific_name": _get("latin_name", "scientific_name", "binomial"),
        # Classification
        "plant_type":      plant_type or "herb",
        "sun_requirement": sun,
        "water_needs":     water,
        "permaculture_uses": perm_uses,
        "native_region":   _get("native_range", "origin", "native_region"),
        # Size
        "spacing_meters":      spacing,
        "mature_height_meters": height,
        # New schema fields
        "bloom_period":         _get("bloom_time", "flowering_period", "bloom_period"),
        "fruit_period":         _get("harvest_time", "fruiting_period", "fruit_period"),
        "edible_parts":         _normalize_edible(_get("edible_parts", "edible")),
        "deciduous_evergreen":  _map_deciduous(_get("deciduous_evergreen", "foliage")),
        "perennial_or_annual":  _map_lifecycle(_get("life_cycle", "lifecycle")),
        # Hardiness
        "hardiness_zone_min":   _parse_zone(_get("hardiness", "usda_zone", "zone_min")),
        "hardiness_zone_max":   _parse_zone(_get("zone_max", "hardiness_max")),
        # Notes
        "notes": _get("description", "notes", "summary") or "",
        # Always mark as non-native since sourced from external API
        "native_to_alberta": 0,
    }


def _map_functions(raw_functions: list) -> str:
    mapping = {
        "nitrogen fixer":      "nitrogen_fixer",
        "nitrogen-fixer":      "nitrogen_fixer",
        "dynamic accumulator": "dynamic_accumulator",
        "pollinator":          "pollinator",
        "windbreak":           "windbreak",
        "food":                "food_forest",
        "edible":              "food_forest",
        "medicine":            "medicine",
        "medicinal":           "medicine",
        "wildlife":            "wildlife_habitat",
        "pioneer":             "pioneer",
        "biomass":             "biomass",
        "groundcover":         "groundcover",
        "ground cover":        "groundcover",
        "pest repellent":      "pest_repellent",
    }
    tags: set[str] = set()
    for item in raw_functions:
        if isinstance(item, dict):
            item = item.get("name", item.get("value", ""))
        item_lower = str(item).lower().strip()
        for key, tag in mapping.items():
            if key in item_lower:
                tags.add(tag)
    return ",".join(sorted(tags)) if tags else "food_forest"


def _map_sun(raw: str) -> str:
    if any(w in raw for w in ("full sun", "full_sun", "high light")):
        return "full_sun"
    if any(w in raw for w in ("shade", "low light", "full_shade")):
        return "full_shade"
    return "partial_shade"


def _map_water(raw: str) -> str:
    if any(w in raw for w in ("low", "dry", "drought", "xeric")):
        return "low"
    if any(w in raw for w in ("high", "moist", "wet", "aquatic")):
        return "high"
    return "medium"


def _map_type(raw: str) -> str:
    if any(w in raw for w in ("tree", "timber")):
        return "tree"
    if any(w in raw for w in ("shrub", "bush")):
        return "shrub"
    if any(w in raw for w in ("vine", "climber", "creeper")):
        return "vine"
    if any(w in raw for w in ("ground", "groundcover")):
        return "groundcover"
    if any(w in raw for w in ("root", "bulb", "tuber")):
        return "root"
    return "herb"


def _map_deciduous(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    raw = raw.lower()
    if "evergreen" in raw:
        return "evergreen"
    if "deciduous" in raw:
        return "deciduous"
    return "herbaceous"


def _map_lifecycle(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    raw = raw.lower()
    if "annual" in raw:
        return "annual"
    if "biennial" in raw:
        return "biennial"
    return "perennial"


def _normalize_edible(raw) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, list):
        return ",".join(
            (i.get("name", str(i)) if isinstance(i, dict) else str(i)).lower().strip()
            for i in raw if i
        ) or None
    return str(raw).strip().lower() or None


def _parse_measure(raw) -> Optional[float]:
    """Parse a spacing or height value that might be a number or a string like '1.5m' or '150cm'."""
    if raw is None:
        return None
    try:
        val = float(raw)
        # Values > 30 are probably in cm
        return round(val / 100, 2) if val > 30 else round(val, 2)
    except (TypeError, ValueError):
        s = str(raw).strip().lower().replace(",", ".")
        try:
            if s.endswith("cm"):
                return round(float(s[:-2]) / 100, 2)
            if s.endswith("m"):
                return round(float(s[:-1]), 2)
            # Try extracting first number
            import re
            m = re.search(r"[\d.]+", s)
            if m:
                return round(float(m.group()), 2)
        except ValueError:
            pass
    return None


def _parse_zone(raw) -> Optional[int]:
    if raw is None:
        return None
    try:
        return int(float(str(raw).strip().lstrip("Zz")))
    except ValueError:
        return None


# ── QThread worker ────────────────────────────────────────────────────────────

class PermapeopleWorker(QObject):
    """
    Runs Permapeople API calls in a background thread.

    Usage:
        self._thread = QThread()
        self._worker = PermapeopleWorker(key_id, key_secret)
        self._worker.moveToThread(self._thread)
        self._worker.results_ready.connect(self._on_results)
        self._worker.error_occurred.connect(self._on_error)
        self._thread.started.connect(lambda: self._worker.search(query))
        self._thread.start()
    """

    results_ready  = pyqtSignal(list)    # list of normalized plant dicts
    error_occurred = pyqtSignal(str)     # error message string
    finished       = pyqtSignal()

    def __init__(self, key_id: str, key_secret: str, parent=None):
        super().__init__(parent)
        self._key_id     = key_id
        self._key_secret = key_secret
        self._query      = ""

    def set_query(self, query: str):
        self._query = query

    def search(self):
        try:
            # Permapeople API: POST /api/search  {"q": "<term>"}
            raw = _post("/search", self._key_id, self._key_secret,
                        body={"q": self._query})

            # Response may be {plants: [...]} or a bare list
            if isinstance(raw, dict):
                items = (raw.get("plants")
                         or raw.get("data")
                         or raw.get("results")
                         or [])
            else:
                items = raw if isinstance(raw, list) else []

            plants = [_normalize_plant(p) for p in items if isinstance(p, dict)]
            self.results_ready.emit(plants)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            self.finished.emit()
