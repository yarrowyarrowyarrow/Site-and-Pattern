"""Drag-scope move semantics for MapEventRouter._on_plant_group_moved.

The map's click-to-cycle drag lets the user move the whole placement
grouping, a single community instance within it, or one plant. A
community-instance move sends only that community's members in the payload
even though every member of the row shares one placement_group_id. This
guards that the handler moves exactly the supplied subset and leaves the
rest of the group put.
"""

import json
import unittest

from src.controllers.map_events import MapEventRouter


class _FakeStatusBar:
    def showMessage(self, *_a, **_k):
        pass


class _FakeMain:
    """Minimal stand-in for MainWindow exposing only what the handler uses."""

    def __init__(self, placed, project):
        self._placed_plants = placed
        self._project = project
        self.undo_entries = []

    def _push_undo(self, entry):
        self.undo_entries.append(entry)

    def _mark_modified(self):
        pass

    def statusBar(self):
        return _FakeStatusBar()


def _plant_feature(plant_id, lat, lng, group_id, center):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {
            "element_type": "plant",
            "plant_id": plant_id,
            "common_name": f"Plant {plant_id}",
            "placement_group_id": group_id,
            "polyculture_center_lat": center[0],
            "polyculture_center_lng": center[1],
            "quantity": 1,
        },
    }


class TestCommunitySubsetMove(unittest.TestCase):
    GROUP = "pg_row"
    CENTER_A = (53.0, -113.0)
    CENTER_B = (53.0, -113.001)

    def _build(self):
        # Two communities (A, B) sharing one placement group, three members each.
        placed = []
        features = []
        for idx, center in ((0, self.CENTER_A), (3, self.CENTER_B)):
            for k in range(3):
                pid = idx + k + 1
                lat = center[0] + k * 1e-5
                lng = center[1] + k * 1e-5
                placed.append({
                    "plant_id": pid, "common_name": f"Plant {pid}",
                    "lat": lat, "lng": lng,
                    "polyculture_center_lat": center[0],
                    "polyculture_center_lng": center[1],
                    "placement_group_id": self.GROUP,
                })
                features.append(_plant_feature(pid, lat, lng, self.GROUP, center))
        main = _FakeMain(placed, {"features": features})
        return main

    def test_moving_one_community_leaves_the_other_put(self):
        main = self._build()
        router = MapEventRouter(main)

        # Drag community A by a fixed delta; B is absent from the payload.
        dlat, dlng = 0.01, 0.02
        originals, moved = [], []
        for p in main._placed_plants:
            if p["polyculture_center_lat"] == self.CENTER_A[0] and \
               p["polyculture_center_lng"] == self.CENTER_A[1]:
                originals.append({
                    "markerId": f"m{p['plant_id']}", "plantId": p["plant_id"],
                    "lat": p["lat"], "lng": p["lng"],
                })
                moved.append({
                    "markerId": f"m{p['plant_id']}", "plantId": p["plant_id"],
                    "lat": p["lat"] + dlat, "lng": p["lng"] + dlng,
                })

        # Snapshot B's positions before the move (match the full centre — the
        # two communities deliberately share a latitude).
        b_before = {
            p["plant_id"]: (p["lat"], p["lng"])
            for p in main._placed_plants
            if (p["polyculture_center_lat"], p["polyculture_center_lng"])
            == self.CENTER_B
        }

        router._on_plant_group_moved(
            self.GROUP, json.dumps(originals), json.dumps(moved),
        )

        # Community A moved by the delta.
        for orig, mv in zip(originals, moved):
            pid = orig["plantId"]
            p = next(x for x in main._placed_plants if x["plant_id"] == pid)
            self.assertAlmostEqual(p["lat"], mv["lat"], places=7)
            self.assertAlmostEqual(p["lng"], mv["lng"], places=7)
            f = next(
                x for x in main._project["features"]
                if x["properties"]["plant_id"] == pid
            )
            self.assertAlmostEqual(f["geometry"]["coordinates"][0], mv["lng"], places=7)
            self.assertAlmostEqual(f["geometry"]["coordinates"][1], mv["lat"], places=7)

        # Community B is untouched.
        for p in main._placed_plants:
            if p["plant_id"] in b_before:
                self.assertEqual((p["lat"], p["lng"]), b_before[p["plant_id"]])

        # One grouped undo entry covering exactly the three moved members.
        self.assertEqual(len(main.undo_entries), 1)
        self.assertEqual(main.undo_entries[0]["action"], "move_plant_group")
        self.assertEqual(len(main.undo_entries[0]["originals"]), 3)


if __name__ == "__main__":
    unittest.main()
