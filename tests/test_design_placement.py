"""
tests/test_design_placement.py

V1.48 — site-precise, boundary-respecting generation. Covers:
  * geometry: point-in-polygon reuse + ring bbox
  * boundary clipping: every placed element lands inside the drawn boundary
  * trim-to-fit: a too-small boundary places <= capacity and warns
  * community fit: an oversized community is skipped, a fitting one placed
  * site-fit filters: search_plants soil_ph containment + moisture selector
  * site-filter derivation + rich prompt context
  * zoning (synthetic grid, no network): wet/dry classification + plant routing
  * shade (synthetic): a tall caster shades cells to its north

All zoning/shade tests use hand-built grids — never the network — so they are
deterministic and offline-safe. Temp-DB pattern; no Qt.
"""

import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.db.plants as _plants_mod  # noqa: E402

_TMP = tempfile.mkdtemp(prefix="permadesign_placement_test_")
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "t.db")

from src.db.plants import init_db, search_plants  # noqa: E402
import src.llm_design as llm  # noqa: E402
import src.zoning as zoning  # noqa: E402
import src.shade as shade  # noqa: E402
from src.geometry import point_in_polygon, ring_bbox  # noqa: E402

# A ~60 m square boundary near Edmonton, as (lat, lng) tuples.
_BOUNDARY = [(53.5000, -113.5000), (53.5000, -113.4991),
             (53.5006, -113.4991), (53.5006, -113.5000)]
_CENTER = (53.5003, -113.49955)


class _FakeClient:
    def __init__(self, spec):
        self._spec = spec
        self.endpoint = "fake://local"
        self.model = "fake"
        self.extra_hints_seen = []

    def generate_spec(self, prompt, context, extra_hints=None):
        self.extra_hints_seen.append(list(extra_hints or []))
        self._last_context = context
        return self._spec


class TestGeometry(unittest.TestCase):
    def test_point_in_polygon_and_bbox(self):
        ring = [[-113.5000, 53.5000], [-113.4991, 53.5000],
                [-113.4991, 53.5006], [-113.5000, 53.5006], [-113.5000, 53.5000]]
        poly = [ring]
        self.assertTrue(point_in_polygon(53.5003, -113.49955, poly))
        self.assertFalse(point_in_polygon(53.4990, -113.49955, poly))
        min_lat, min_lng, max_lat, max_lng = ring_bbox(ring)
        self.assertAlmostEqual(min_lat, 53.5000)
        self.assertAlmostEqual(max_lng, -113.4991)

    def test_ecoregion_shim_matches(self):
        # the ecoregion back-compat shim must agree with the moved impl
        from src.ecoregion import _point_in_polygon
        ring = [[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]
        self.assertEqual(_point_in_polygon(0, 0, [ring]),
                         point_in_polygon(0, 0, [ring]))


class TestBoundaryClipping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def _poly(self):
        return llm._boundary_polygon(_BOUNDARY)

    def test_all_plants_inside_boundary(self):
        client = _FakeClient({"plants": [{"query": "willow", "quantity": 1}] * 25})
        proj = llm.generate_design("x", site_config={"latitude": _CENTER[0],
                                   "longitude": _CENTER[1]},
                                   boundary=_BOUNDARY, client=client,
                                   match_site=False)
        poly = self._poly()
        self.assertTrue(proj.placed_plants)
        for pp in proj.placed_plants:
            self.assertTrue(point_in_polygon(pp["lat"], pp["lng"], poly),
                            f"{pp['common_name']} escaped the boundary")

    def test_grid_cells_in_boundary_are_inside(self):
        cells = llm.grid_cells_in_boundary(_BOUNDARY)
        self.assertTrue(cells)
        poly = self._poly()
        self.assertTrue(all(point_in_polygon(la, ln, poly) for la, ln in cells))

    def test_fills_within_capacity_no_overflow(self):
        # V1.50: a tiny boundary fills up to (not beyond) its plantable
        # capacity — every plant stays inside, none spill out, even when the
        # spec asks for many. (Trim-to-fit was replaced by capacity-bounded,
        # density-driven fill.)
        tiny = [(53.5000, -113.50000), (53.5000, -113.49988),
                (53.50007, -113.49988), (53.50007, -113.50000)]
        client = _FakeClient({"plants": [{"query": "yarrow", "quantity": 5,
                                          "layout": "grid"}] * 4})
        proj = llm.generate_design("x",
                                   site_config={"latitude": 53.50003,
                                                "longitude": -113.49994},
                                   boundary=tiny, client=client,
                                   match_site=False, density="full")
        poly = self._poly_for(tiny)
        placed = proj.placed_plants
        self.assertTrue(placed)
        # The headline invariant: nothing spills outside the boundary, no
        # matter how dense or how many groups were requested.
        for pp in placed:
            self.assertTrue(point_in_polygon(pp["lat"], pp["lng"], poly),
                            "a plant spilled outside the tiny boundary")

    @staticmethod
    def _poly_for(boundary):
        return llm._boundary_polygon(boundary)

    def test_community_fits_guard(self):
        # A community larger than the boundary radius must be rejected.
        tiny = [(53.5000, -113.500000), (53.5000, -113.499970),
                (53.500018, -113.499970), (53.500018, -113.500000)]
        self.assertFalse(llm.community_fits(tiny, (53.500009, -113.499985), 2.69))
        self.assertTrue(llm.community_fits(tiny, (53.500009, -113.499985), 0.4))
        self.assertTrue(llm.community_fits(None, (53.5, -113.5), 99.0))


class TestV150Intelligence(unittest.TestCase):
    """Density-driven space fill, keep-out, and LLM-chosen layout (V1.50)."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def _gen(self, spec, **kw):
        client = _FakeClient(spec)
        return llm.generate_design(
            "x", site_config={"latitude": _CENTER[0], "longitude": _CENTER[1]},
            boundary=_BOUNDARY, client=client, match_site=False, **kw)

    def test_full_denser_than_sparse(self):
        spec = {"plants": [{"query": "yarrow", "quantity": 3}]}
        sparse = self._gen(dict(spec), density="sparse")
        full = self._gen(dict(spec), density="full")
        self.assertGreater(len(full.placed_plants), len(sparse.placed_plants))
        # Full should fill a good chunk of the ~60 m boundary.
        self.assertGreater(len(full.placed_plants), 20)

    def test_density_fill_stays_inside(self):
        proj = self._gen({"plants": [{"query": "yarrow", "quantity": 3}]},
                         density="full")
        poly = llm._boundary_polygon(_BOUNDARY)
        for pp in proj.placed_plants:
            self.assertTrue(point_in_polygon(pp["lat"], pp["lng"], poly))

    def test_keepout_blocks_planting_on_existing_tree(self):
        # Pre-mark a big existing tree at the centre; no plant may land inside
        # its canopy.
        from src.permadesign_api import Project
        proj = Project.create("t", site_config={"latitude": _CENTER[0],
                              "longitude": _CENTER[1]}, boundary=_BOUNDARY)
        tlat, tlng = _CENTER
        proj._gen.add_existing_tree(tlat, tlng, height_m=12.0,
                                    canopy_radius_m=10.0)
        from src.exclusion import keepout_circles
        keep = keepout_circles(proj.as_dict())
        yid = search_plants(query="yarrow")[0]["id"]
        items = llm._apply_density([(yid, 4, "scatter")], _BOUNDARY, "full", keep)
        llm._place_within_boundary(proj, items, [], [], _BOUNDARY, _CENTER,
                                   keepout=keep)
        cl = math.cos(tlat * math.pi / 180)

        def d(la, ln):
            return math.hypot((ln - tlng) * 111320 * cl, (la - tlat) * 111320)
        viol = [pp for pp in proj.placed_plants if d(pp["lat"], pp["lng"]) < 10.0]
        self.assertTrue(proj.placed_plants)
        self.assertEqual(viol, [])

    def test_layout_field_parsed_from_spec(self):
        from src.permadesign_api import query_plants
        items = llm._resolve_plants(
            [{"query": "yarrow", "quantity": 4, "layout": "row"}], query_plants)
        self.assertTrue(items)
        self.assertEqual(len(items[0]), 3)        # (id, qty, layout)
        self.assertEqual(items[0][2], "row")


class TestSiteFitFilters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_soil_ph_containment(self):
        # Containment now carries a tolerance margin (V2.18.1): a plant passes if
        # the site pH falls within its bracket widened by _SOIL_PH_TOLERANCE at
        # each end — so a coarse regional pH estimate doesn't wrongly drop woody
        # species at a 0.1 boundary (the Regina/Lumsden clay bug).
        from src.db.plants import _SOIL_PH_TOLERANCE as tol
        rows = search_plants(soil_ph=7.5)
        self.assertTrue(rows)
        for r in rows:
            lo, hi = r.get("soil_ph_min"), r.get("soil_ph_max")
            if lo not in (None, ""):
                self.assertLessEqual(float(lo), 7.5 + tol)
            if hi not in (None, ""):
                self.assertGreaterEqual(float(hi), 7.5 - tol)

    def test_moisture_wet_and_dry(self):
        wet = search_plants(moisture="wet")
        dry = search_plants(moisture="dry")
        self.assertTrue(any(p["plant_type"] == "aquatic" for p in wet))
        # water_needs may be comma-delimited (V1.84): a dry-ground plant tolerates
        # low water if "low" is among its values (e.g. "low" or "low,medium").
        self.assertTrue(all("low" in (p["water_needs"] or "").split(",")
                            for p in dry))

    def test_filters_in_allowlist(self):
        self.assertIn("soil_ph", llm._ALLOWED_FILTERS)
        self.assertIn("moisture", llm._ALLOWED_FILTERS)


class TestSiteContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    _SC = {"latitude": 53.5, "longitude": -113.5, "hardiness_zone": 3,
           "ecoregion_key": "aspen_parkland",
           "ecoregion_label": "Aspen Parkland (central AB)",
           "gdd5_mean": 1450, "frost_free_days": 120,
           "annual_rainfall_mm": 450, "slope_pct": 4, "aspect": "S",
           "soil_ph": 7.2, "soil_texture": "loam"}

    def test_site_filters_derived(self):
        f = llm._site_filters(self._SC)
        self.assertEqual(f["zone"], 3)
        self.assertEqual(f["ab_ecoregion"], "aspen_parkland")
        self.assertEqual(f["soil_ph"], 7.2)

    def test_conditions_line(self):
        line = llm._site_conditions_line(self._SC)
        for token in ("hardiness zone 3", "Aspen Parkland", "GDD5",
                      "frost-free", "rain", "slope", "pH"):
            self.assertIn(token, line)

    def test_prompt_carries_rich_context(self):
        client = _FakeClient({"plants": [{"query": "willow"}]})
        llm.generate_design("a garden", site_config=self._SC, client=client,
                            match_site=False)
        ctx = client._last_context
        msgs = llm._build_messages("a garden", ctx)
        sys_text = msgs[0]["content"]
        self.assertIn("SITE CONDITIONS", sys_text)
        self.assertIn("PLANT PALETTE", sys_text)
        self.assertIn("AVAILABLE COMMUNITIES", sys_text)
        # community digest carries a description, not just a name
        self.assertTrue(any(" — " in line for line in sys_text.splitlines()))


class TestZoning(unittest.TestCase):
    def _grid(self):
        # West (low c) = low elevation (wet); east (high c) = high + stepped (dry).
        rows = cols = 9
        grid = [[80.0 + c * 6.0 for c in range(cols)] for _ in range(rows)]
        return {"grid": grid, "rows": rows, "cols": cols,
                "bbox": {"north": 53.5006, "south": 53.5000,
                         "east": -113.4991, "west": -113.5000}}

    def test_classify_low_wet_high_dry(self):
        zones = zoning.classify_zones(self._grid())
        # west column cells (c==0) low → wet; east column (c==8) high+steep → dry
        self.assertEqual(zones[(4, 0)], zoning.WET)
        self.assertEqual(zones[(4, 8)], zoning.DRY)

    def test_plant_zone_mapping(self):
        self.assertEqual(zoning.preferred_zone_for_plant(
            {"plant_type": "aquatic"}), zoning.WET)
        self.assertEqual(zoning.preferred_zone_for_plant(
            {"water_needs": "low"}), zoning.DRY)
        self.assertEqual(zoning.preferred_zone_for_plant(
            {"sun_requirement": "full_shade"}), zoning.SHADED)
        self.assertEqual(zoning.preferred_zone_for_plant(
            {"ab_ecoregion": "wet_meadow,riparian"}), zoning.WET)

    def test_structure_zone_mapping(self):
        self.assertEqual(zoning.preferred_zone_for_structure("pond"),
                         zoning.WET)
        self.assertEqual(zoning.preferred_zone_for_structure("bee_hotel"),
                         zoning.NEUTRAL)

    def test_zone_positions_clipped_to_boundary(self):
        elev = self._grid()
        zones = zoning.classify_zones(elev)
        pos = zoning.zone_positions(elev, zones, _BOUNDARY)
        poly = llm._boundary_polygon(_BOUNDARY)
        for zlist in pos.values():
            for la, ln in zlist:
                self.assertTrue(point_in_polygon(la, ln, poly))

    def test_zoned_placement_routes_plants(self):
        init_db()
        elev = self._grid()
        zones = zoning.classify_zones(elev)
        aquatic = search_plants(plant_type="aquatic")[0]
        dry = search_plants(moisture="dry", plant_type="herb")[0]

        from src.permadesign_api import Project
        proj = Project.create("t", site_config={"latitude": _CENTER[0],
                              "longitude": _CENTER[1]}, boundary=_BOUNDARY)

        def pzone(pid):
            from src.db.plants import get_plant
            return zoning.preferred_zone_for_plant(get_plant(pid) or {})

        llm._place_within_boundary(
            proj, [(aquatic["id"], 1), (dry["id"], 1)], [], [], _BOUNDARY,
            _CENTER, elev=elev, zones=zones, plant_zone_for=pzone,
            structure_zone_for=zoning.preferred_zone_for_structure)

        placed = {p["plant_id"]: (p["lat"], p["lng"])
                  for p in proj.placed_plants}
        # wet cells are west (lower lng); the aquatic should sit west of the dry
        self.assertLess(placed[aquatic["id"]][1], placed[dry["id"]][1])


class TestShade(unittest.TestCase):
    def test_shadow_falls_north(self):
        # flat 9x9 grid, ~45 m, one 12 m tree at centre; N hemisphere → shade
        # accumulates to the north.
        n = 9
        bbox = {"north": 53.50020, "south": 53.49980,
                "east": -113.49966, "west": -113.50034}
        elev = {"grid": [[100.0] * n for _ in range(n)], "rows": n, "cols": n,
                "bbox": bbox}
        clat = (bbox["north"] + bbox["south"]) / 2
        clng = (bbox["east"] + bbox["west"]) / 2
        g = shade.shade_grid([{"lat": clat, "lng": clng, "height_m": 12.0,
                               "radius_m": 4.0}], elev)
        north = sum(g[r][c] for r in range(0, 4) for c in range(n))
        south = sum(g[r][c] for r in range(5, n) for c in range(n))
        self.assertGreater(north, south)
        self.assertGreater(north, 0.0)

    def test_no_casters_no_shade(self):
        elev = {"grid": [[100.0] * 3 for _ in range(3)], "rows": 3, "cols": 3,
                "bbox": {"north": 53.5006, "south": 53.5000,
                         "east": -113.4991, "west": -113.5000}}
        g = shade.shade_grid([], elev)
        self.assertTrue(all(v == 0.0 for row in g for v in row))

    def test_casters_from_project_reads_existing(self):
        proj = {"features": [
            {"geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
             "properties": {"element_type": "existing_tree", "height_m": 8.0,
                            "canopy_radius_m": 3.0}},
            {"geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
             "properties": {"element_type": "existing_building",
                            "height_m": 5.0, "canopy_radius_m": 4.0}},
        ]}
        casters = shade.casters_from_project(proj)
        self.assertEqual(len(casters), 2)
        self.assertEqual(casters[0]["height_m"], 8.0)


class TestExistingFeatureApi(unittest.TestCase):
    def test_add_existing_tree_and_building(self):
        from src.permadesign_api import Project
        proj = Project.create("t", site_config={"latitude": 53.5,
                              "longitude": -113.5})
        gen = proj._gen
        gen.add_existing_tree(53.5, -113.5, height_m=10.0, canopy_radius_m=4.0)
        gen.add_existing_building(53.5001, -113.5001, height_m=6.0)
        feats = proj.as_dict()["features"]
        ets = [f["properties"]["element_type"] for f in feats]
        self.assertIn("existing_tree", ets)
        self.assertIn("existing_building", ets)


if __name__ == "__main__":
    unittest.main()
