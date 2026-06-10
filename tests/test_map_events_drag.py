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


class TestSelectionMove(unittest.TestCase):
    """G1 — a marquee selection may span several placement groups, so
    _on_selection_moved must match by plant_id + old-coords WITHOUT a
    group constraint (unlike _on_plant_group_moved)."""

    def _build(self):
        placed = [
            {"plant_id": 1, "common_name": "A", "lat": 53.50, "lng": -113.50,
             "placement_group_id": "g1"},
            {"plant_id": 2, "common_name": "B", "lat": 53.51, "lng": -113.51,
             "placement_group_id": "g2"},          # different group
            {"plant_id": 3, "common_name": "C", "lat": 53.52, "lng": -113.52,
             "placement_group_id": "g2"},          # not in the selection
        ]
        features = [
            _plant_feature(1, 53.50, -113.50, "g1", (53.50, -113.50)),
            _plant_feature(2, 53.51, -113.51, "g2", (53.51, -113.51)),
            _plant_feature(3, 53.52, -113.52, "g2", (53.52, -113.52)),
        ]
        return _FakeMain(placed, {"features": features})

    def test_moves_cross_group_selection_and_leaves_rest(self):
        main = self._build()
        router = MapEventRouter(main)
        originals = [
            {"markerId": "m1", "plantId": 1, "lat": 53.50, "lng": -113.50},
            {"markerId": "m2", "plantId": 2, "lat": 53.51, "lng": -113.51},
        ]
        moved = [
            {"markerId": "m1", "plantId": 1, "lat": 53.60, "lng": -113.60},
            {"markerId": "m2", "plantId": 2, "lat": 53.61, "lng": -113.61},
        ]
        router._on_selection_moved(json.dumps(originals), json.dumps(moved))

        p1 = next(p for p in main._placed_plants if p["plant_id"] == 1)
        p2 = next(p for p in main._placed_plants if p["plant_id"] == 2)
        p3 = next(p for p in main._placed_plants if p["plant_id"] == 3)
        self.assertEqual((p1["lat"], p1["lng"]), (53.60, -113.60))
        self.assertEqual((p2["lat"], p2["lng"]), (53.61, -113.61))     # other group
        self.assertEqual((p3["lat"], p3["lng"]), (53.52, -113.52))     # untouched
        # features updated for both moved plants (no group filter)
        f2 = next(f for f in main._project["features"]
                  if f["properties"]["plant_id"] == 2)
        self.assertEqual(f2["geometry"]["coordinates"], [-113.61, 53.61])
        self.assertEqual(main.undo_entries[0]["action"], "move_selection")


class TestBatchRemove(unittest.TestCase):
    """R2 — deleting a multi-plant selection removes them in one pass with a
    single planning re-sync (was a per-plant round-trip that recomputed the
    habitat score each time → lag)."""

    def _main(self):
        placed = [
            {"plant_id": 1, "lat": 53.50, "lng": -113.50},
            {"plant_id": 1, "lat": 53.50, "lng": -113.50},   # duplicate position
            {"plant_id": 2, "lat": 53.51, "lng": -113.49},
            {"plant_id": 3, "lat": 53.52, "lng": -113.48},
        ]
        features = [_plant_feature(1, 53.50, -113.50, "g", (0, 0)),
                    _plant_feature(1, 53.50, -113.50, "g", (0, 0)),
                    _plant_feature(2, 53.51, -113.49, "g", (0, 0)),
                    _plant_feature(3, 53.52, -113.48, "g", (0, 0))]
        m = _FakeMain(placed, {"features": features})
        m._sync_count = 0
        m._sync_planning_panel = lambda: setattr(m, "_sync_count",
                                                 m._sync_count + 1)
        m.plant_panel = type("PP", (), {
            "removed": [],
            "on_plants_removed_batch": lambda self, ids: self.removed.extend(ids),
        })()
        return m

    def test_batch_removes_and_syncs_once(self):
        main = self._main()
        router = MapEventRouter.__new__(MapEventRouter)
        router._main = main
        # Delete one of the duplicate id=1 plants and the id=3 plant.
        batch = json.dumps([
            {"plantId": 1, "lat": 53.50, "lng": -113.50},
            {"plantId": 3, "lat": 53.52, "lng": -113.48},
        ])
        router._on_plants_removed_batch(batch)

        ids = sorted(p["plant_id"] for p in main._placed_plants)
        self.assertEqual(ids, [1, 2])      # one duplicate id=1 survives
        feat_ids = sorted(f["properties"]["plant_id"]
                          for f in main._project["features"])
        self.assertEqual(feat_ids, [1, 2])
        self.assertEqual(main._sync_count, 1)         # ONE re-sync for the batch
        self.assertEqual(sorted(main.plant_panel.removed), [1, 3])

    def test_empty_batch_noops(self):
        main = self._main()
        router = MapEventRouter.__new__(MapEventRouter)
        router._main = main
        router._on_plants_removed_batch("[]")
        self.assertEqual(len(main._placed_plants), 4)
        self.assertEqual(main._sync_count, 0)


if __name__ == "__main__":
    unittest.main()
