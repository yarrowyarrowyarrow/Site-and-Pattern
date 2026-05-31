"""
shade_zones.py — Storage helper for the derived shade-tag cache (V1.53).

Caches the OUTPUT of the cast-shade analysis: a shade tag
(``full_sun`` / ``partial_shade`` / ``full_shade``) per planting zone, keyed by
project + zone id, so the placement UI and analysis panel can read a project's
shade classification without recomputing the grid.

Per CLAUDE.md the global SQLite DB must never hold project *geometry* — footprint
polygons and heights live in the per-project ``.perma.geojson`` file. This module
stores only the derived tag and the fraction it came from. ``project_key`` is a
stable id derived from the project file path (a sha1 of the absolute path), never
geometry.

Mirrors the ``get_cached_climate`` / ``store_cached_climate`` helper style in
``src/db/plants.py`` and uses the same ``get_connection()`` convention.
"""

from __future__ import annotations

import hashlib
import os
from typing import Optional

from src.db.plants import get_connection

# Shade-fraction → tag thresholds. Single source of truth, aligned with the
# _SHADE_RAMP buckets in src/shade.py and zoning's 0.4 SHADED threshold:
#   < 0.15  → full_sun       (essentially lit)
#   < 0.40  → partial_shade  (light/dappled)
#   >= 0.40 → full_shade     (meaningfully shaded most of the day)
_FULL_SUN_BELOW = 0.15
_PARTIAL_BELOW = 0.40

# The catalogue's sun_requirement vocabulary these tags align with.
SHADE_TAGS = ("full_sun", "partial_shade", "full_shade")


def tag_for_fraction(frac: float) -> str:
    """Map a season-average shade fraction (0..1) to a sun_requirement-aligned
    tag. The boundaries match ``src/shade.py``'s ramp and ``src/zoning.py``."""
    if frac < _FULL_SUN_BELOW:
        return "full_sun"
    if frac < _PARTIAL_BELOW:
        return "partial_shade"
    return "full_shade"


def project_key_for(path: Optional[str]) -> str:
    """Stable cache key for a project. Derived from the absolute project file
    path (sha1) so it is short, filesystem-safe, and — importantly — carries NO
    geometry. Unsaved projects (no path) get the sentinel ``"__unsaved__"``."""
    if not path:
        return "__unsaved__"
    norm = os.path.abspath(os.path.expanduser(str(path)))
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def store_zone_tags(project_key: str, rows: list) -> int:
    """Persist (or overwrite) shade tags for a project. ``rows`` is an iterable
    of dicts with keys ``zone_id``, ``shade_tag`` and optional ``shade_frac``,
    ``centroid_lat``, ``centroid_lng``. Returns the number of rows written.

    Callers typically ``clear_zone_tags`` first for a clean recompute, but this
    uses ``INSERT OR REPLACE`` so re-storing the same zone_id is also safe."""
    conn = get_connection()
    written = 0
    try:
        for row in rows:
            tag = row["shade_tag"]
            if tag not in SHADE_TAGS:
                raise ValueError(f"invalid shade_tag {tag!r}")
            conn.execute(
                "INSERT OR REPLACE INTO shade_zone_cache "
                "(project_key, zone_id, shade_tag, shade_frac, "
                " centroid_lat, centroid_lng, computed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (
                    project_key,
                    str(row["zone_id"]),
                    tag,
                    row.get("shade_frac"),
                    row.get("centroid_lat"),
                    row.get("centroid_lng"),
                ),
            )
            written += 1
        conn.commit()
    finally:
        conn.close()
    return written


def clear_zone_tags(project_key: str) -> None:
    """Remove all cached shade tags for one project (scoped by project_key)."""
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM shade_zone_cache WHERE project_key = ?",
            (project_key,),
        )
        conn.commit()
    finally:
        conn.close()


def get_zone_tags(project_key: str) -> dict:
    """Return ``{zone_id: {shade_tag, shade_frac, centroid_lat, centroid_lng}}``
    for a project. Empty dict on miss."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT zone_id, shade_tag, shade_frac, centroid_lat, centroid_lng "
            "FROM shade_zone_cache WHERE project_key = ?",
            (project_key,),
        ).fetchall()
        return {
            r["zone_id"]: {
                "shade_tag":    r["shade_tag"],
                "shade_frac":   r["shade_frac"],
                "centroid_lat": r["centroid_lat"],
                "centroid_lng": r["centroid_lng"],
            }
            for r in rows
        }
    finally:
        conn.close()


def tag_counts(project_key: str) -> dict:
    """Convenience: ``{tag: count}`` for a project's cached zones — for a
    read-only breakdown in the analysis panel without recomputing."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT shade_tag, COUNT(*) AS n FROM shade_zone_cache "
            "WHERE project_key = ? GROUP BY shade_tag",
            (project_key,),
        ).fetchall()
        out = {t: 0 for t in SHADE_TAGS}
        for r in rows:
            out[r["shade_tag"]] = r["n"]
        return out
    finally:
        conn.close()
