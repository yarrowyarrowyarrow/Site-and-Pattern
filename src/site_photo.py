"""
src/site_photo.py — site/drone photo map underlay (F24).

Design principle P11 (the body and the site know things the screen does not) and
P5 (perception is constructed — make the real site legible under the design) —
see docs/DESIGN_PHILOSOPHY.md.

Qt-free maths + persistence for dropping a personal yard/drone photo onto the 2D
map as a georeferenced underlay (complementing the Gaussian-splat "yard photo").
The image itself is embedded as a data URL on a ``site_photo`` GeoJSON feature,
exactly like the splat backdrop's baked ``ortho_png`` — so the map plumbing
(``draw_*_overlay`` / opacity / visibility / clear) is the same and the overlay
reloads instantly with the project.

Placement is kept simple and honest: the photo is centred on a chosen point
(the property pin, or the current map centre) and scaled to a real-world
**width across** in metres, preserving the image's aspect ratio. Re-importing or
nudging the width recomputes the bbox here in Python, keeping the map JS thin
(a single ``L.imageOverlay`` at a lat/lng bbox). Markup over the photo reuses the
existing map annotation pins — no separate machinery.
"""

from __future__ import annotations

from typing import Optional

ELEMENT_TYPE = "site_photo"
_DEFAULT_OPACITY = 0.7
_DEFAULT_WIDTH_M = 30.0


def bbox_from_center(lat: float, lng: float, width_m: float,
                     aspect: float) -> dict:
    """Lat/lng bbox (``{south, north, west, east}``) for a photo of real-world
    ``width_m`` centred on ``(lat, lng)``.

    ``aspect`` is the image's height/width pixel ratio, so the on-ground height
    is ``width_m * aspect`` and the photo keeps its proportions on the map. Uses
    the same cosLat metric the rest of the app measures with."""
    from src.projection import metres_per_deg
    width_m = max(0.5, float(width_m))
    aspect = float(aspect) if aspect and aspect > 0 else 1.0
    height_m = width_m * aspect
    m_lat, m_lng = metres_per_deg(lat)
    half_dlng = (width_m / 2.0) / m_lng
    half_dlat = (height_m / 2.0) / m_lat
    return {
        "south": lat - half_dlat, "north": lat + half_dlat,
        "west":  lng - half_dlng, "east":  lng + half_dlng,
    }


def _bbox_ring(bbox: dict) -> list:
    """Closed lng/lat ring (GeoJSON order) for a lat/lng bbox."""
    s, n = bbox["south"], bbox["north"]
    w, e = bbox["west"], bbox["east"]
    return [[w, s], [e, s], [e, n], [w, n], [w, s]]


def build_feature(*, image: str, center: dict, width_m: float, aspect: float,
                  opacity: float = _DEFAULT_OPACITY,
                  name: str = "Site photo") -> dict:
    """A ``site_photo`` GeoJSON Feature persisting one placed photo.

    ``image`` is a ``data:image/...`` URL (embedded so the overlay reloads with
    the project); ``center`` is ``{"lat", "lng"}``; ``width_m`` the on-map width
    across; ``aspect`` the image height/width ratio (stored so a width change can
    recompute the bbox without re-reading the file). The geometry is the lat/lng
    footprint ring so the photo's extent survives even if the embedded image is
    ever stripped."""
    lat = float(center["lat"])
    lng = float(center["lng"])
    width_m = max(0.5, float(width_m))
    aspect = float(aspect) if aspect and aspect > 0 else 1.0
    bbox = bbox_from_center(lat, lng, width_m, aspect)
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [_bbox_ring(bbox)]},
        "properties": {
            "element_type": ELEMENT_TYPE,
            "name": name,
            "image": image,
            "center": {"lat": lat, "lng": lng},
            "width_m": width_m,
            "aspect": aspect,
            "bbox": {k: float(bbox[k]) for k in ("south", "north", "west", "east")},
            "opacity": float(opacity),
        },
    }


def feature_from_project(project: dict) -> Optional[dict]:
    """The project's site_photo feature (the latest wins), or ``None``."""
    found = None
    for f in (project or {}).get("features", []):
        if (f.get("properties", {}) or {}).get("element_type") == ELEMENT_TYPE:
            found = f
    return found


def set_feature(project: dict, feature: dict) -> None:
    """Replace any existing site_photo feature in ``project`` with ``feature``
    (one underlay at a time). Mutates ``project`` in place."""
    feats = [f for f in project.get("features", [])
             if (f.get("properties", {}) or {}).get("element_type") != ELEMENT_TYPE]
    feats.append(feature)
    project["features"] = feats


def clear_from_project(project: dict) -> bool:
    """Remove the site_photo feature. Returns True if one was present."""
    feats = project.get("features", [])
    kept = [f for f in feats
            if (f.get("properties", {}) or {}).get("element_type") != ELEMENT_TYPE]
    project["features"] = kept
    return len(kept) != len(feats)


def set_width(feature: dict, width_m: float) -> dict:
    """Recompute a feature's bbox for a new on-map ``width_m`` (keeping its
    centre + aspect). Mutates and returns the feature."""
    props = feature.setdefault("properties", {})
    center = props.get("center", {}) or {}
    aspect = float(props.get("aspect") or 1.0)
    width_m = max(0.5, float(width_m))
    bbox = bbox_from_center(float(center.get("lat", 0.0)),
                            float(center.get("lng", 0.0)), width_m, aspect)
    props["width_m"] = width_m
    props["bbox"] = {k: float(bbox[k]) for k in ("south", "north", "west", "east")}
    feature["geometry"] = {"type": "Polygon", "coordinates": [_bbox_ring(bbox)]}
    return feature


def set_opacity(feature: dict, opacity: float) -> dict:
    """Set a feature's stored overlay opacity (0..1). Mutates and returns it."""
    feature.setdefault("properties", {})["opacity"] = max(0.0, min(1.0, float(opacity)))
    return feature


def overlay_payload(feature: dict) -> Optional[dict]:
    """``{"image", "bbox", "opacity"}`` for the 2D map overlay, or ``None`` when
    the feature has no embedded image."""
    if not feature:
        return None
    props = feature.get("properties", {}) or {}
    image = props.get("image")
    if not image:
        return None
    return {
        "image": image,
        "bbox": props.get("bbox", {}),
        "opacity": float(props.get("opacity", _DEFAULT_OPACITY)),
    }
