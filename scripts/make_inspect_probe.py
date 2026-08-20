"""Generate html/inspect_probe_data.json for the click-to-inspect smoke probe.

Builds a real multi-species scene through the real contracts —
src.scene_contract.build_scene, src.scene_dossier.build_dossier and
src.scene_wildlife — so html/inspect_probe.html can never drift from what the
app actually pushes (the make_gallery_scene.py precedent).

    python scripts/make_inspect_probe.py
    python -m http.server 8123 --directory html
    # browser: http://127.0.0.1:8123/inspect_probe.html
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# A cross-section of the archetypes: a shrub, a keystone tree, three herb forms
# and a conifer, each planted three times so the scene reads as a small design.
SPECIES = ["Saskatoon Berry", "Wild Bergamot", "Showy Milkweed", "White Spruce",
           "Canada Goldenrod", "Common Yarrow", "Wild Blue Flax",
           "Trembling Aspen"]
YEAR = 8


def main():
    from src.db.plants import init_db, search_plants
    from src.scene_contract import build_scene
    from src.scene_dossier import build_dossier
    from src.scene_wildlife import support_by_taxon, wildlife_for_scene

    init_db()
    features = []
    for i, name in enumerate(SPECIES):
        rows = search_plants(query=name)
        if not rows:
            print(f"  (skipped, not in the seed data: {name})")
            continue
        for k in range(3):
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [
                    -114.07 + (i * 3 + k) * 0.00004, 51.05 + k * 0.00003]},
                "properties": {"element_type": "plant",
                               "plant_id": rows[0]["id"],
                               "common_name": rows[0]["common_name"]}})
    project = {"type": "FeatureCollection", "features": features,
               "properties": {"site_config": {"latitude": 51.05,
                                              "longitude": -114.07}}}
    scene = build_scene(project, year=YEAR)
    pids = [p["plant_id"] for p in scene["plants"] if p.get("plant_id")]
    out = {"scene": scene,
           "dossier": build_dossier(scene),
           "wildlife": wildlife_for_scene(scene),
           "support": support_by_taxon(pids)}
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "html", "inspect_probe_data.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print(f"wrote {path}: {len(scene['plants'])} plants, "
          f"{len(out['dossier']['plants'])} species dossiers, "
          f"{len(out['wildlife'])} creatures")


if __name__ == "__main__":
    main()
