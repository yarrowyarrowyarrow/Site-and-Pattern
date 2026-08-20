"""
tests/test_ecoregion.py

Verifies the V1.36 ecoregion auto-detect via point-in-polygon against
the shipped ``data/ecoregions_canada.geojson``. Each test asserts a
real city's lat/lng resolves to the canonical ecoregion key the plant
filter expects.

The shipped starter polygon set is a rectangular partition of the
prairie provinces — Alberta west of the -110 meridian, Saskatchewan
east of it (V2.14) — and the city assertions below are calibrated
against that starter set. When a future revision replaces those
rectangles with real CEC polygons (via ``scripts/prepare_ecoregions.py``),
expect some of these assertions to need adjustment for boundary cases
like Calgary (which sits at the prairie-foothills transition).
"""

import html
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ecoregion import (  # noqa: E402
    lookup_ecoregion,
    lookup_ecoregions,
    label_for_key,
    _point_in_ring,
    _point_in_polygon,
    _load_features,
)


class TestLoadFeatures(unittest.TestCase):

    def test_shipped_geojson_loads(self):
        features = _load_features()
        self.assertGreaterEqual(len(features), 5,
                                "Expected at least 5 AB ecoregion features")

    def test_all_features_have_canonical_key(self):
        """Every feature's key must be in the filter's vocabulary, or the
        auto-detect result matches no option in the dropdown.

        The canonical set is read from the vocabulary rather than typed beside
        it: since V2.38 the polygon file *is* the vocabulary, so a literal list
        here would only ever be a second copy waiting to disagree with it."""
        from src.ecoregion import ecoregion_keys
        canonical = set(ecoregion_keys())
        for feat in _load_features():
            key = (feat.get("properties") or {}).get("key", "")
            self.assertIn(key, canonical,
                          f"Feature key {key!r} not in canonical set")


class TestPointInRing(unittest.TestCase):
    """Sanity-check the ray-casting primitive on a known unit square."""

    SQUARE = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]

    def test_inside_centre(self):
        self.assertTrue(_point_in_ring(0.5, 0.5, self.SQUARE))

    def test_outside_left(self):
        self.assertFalse(_point_in_ring(0.5, -1, self.SQUARE))

    def test_outside_right(self):
        self.assertFalse(_point_in_ring(0.5, 2, self.SQUARE))

    def test_outside_above(self):
        self.assertFalse(_point_in_ring(2, 0.5, self.SQUARE))

    def test_outside_below(self):
        self.assertFalse(_point_in_ring(-1, 0.5, self.SQUARE))

    def test_degenerate_ring(self):
        self.assertFalse(_point_in_ring(0.5, 0.5, [[0, 0], [1, 1]]))


class TestPolygonWithHole(unittest.TestCase):

    OUTER = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    HOLE  = [[3, 3], [7, 3], [7, 7], [3, 7], [3, 3]]

    def test_inside_outer_but_in_hole(self):
        self.assertFalse(_point_in_polygon(5, 5, [self.OUTER, self.HOLE]))

    def test_inside_outer_and_not_in_hole(self):
        self.assertTrue(_point_in_polygon(1, 1, [self.OUTER, self.HOLE]))


class TestAlbertaCityLookups(unittest.TestCase):
    """Real city coordinates → expected ecoregion key. Adjust if the
    polygon set changes."""

    def assertEco(self, lat: float, lng: float, expected_key: str):
        got = lookup_ecoregion(lat, lng)
        self.assertEqual(got, expected_key,
                         f"({lat}, {lng}) → got {got!r}, expected {expected_key!r}")

    def test_edmonton_is_aspen_parkland(self):
        # Edmonton centroid
        self.assertEco(53.5461, -113.4938, "aspen_parkland")

    def test_red_deer_is_aspen_parkland(self):
        self.assertEco(52.2681, -113.8112, "aspen_parkland")

    def test_fort_mcmurray_is_wabasca_lowland(self):
        """V2.67: the coarse "boreal_mixedwood" became the ELC ecoregion it
        actually is. Still Boreal Plains, which is what mattered."""
        self.assertEco(56.7264, -111.3803, "wabasca_lowland")

    def test_grande_prairie_is_peace_lowland(self):
        """The Peace River country is its own ecoregion, which the six-key
        vocabulary could not say."""
        self.assertEco(55.1707, -118.7947, "peace_lowland")

    def test_lethbridge_is_moist_mixed_grassland(self):
        """The one the rebuild brief argued about and the source won. See
        tools/ecoregions/probes.py for the evidence."""
        self.assertEco(49.6956, -112.8451, "moist_mixed_grassland")

    def test_medicine_hat_is_mixed_grassland(self):
        self.assertEco(50.0405, -110.6764, "mixed_grassland")

    def test_calgary_is_fescue_grassland_and_reaches_the_parkland(self):
        """Calgary was the change everyone predicted, and it is a better answer
        than the one it replaces twice over.

        The placeholder put it in ``fescue_foothills`` by fiat — its own comment
        admitted the key existed because Calgary sat in a hand-drawn band. The
        surveyed layer says Fescue Grassland, a real ELC unit, *and* puts the
        city within five kilometres of Aspen Parkland, which is what a reader
        standing there would tell you.
        """
        keys = lookup_ecoregions(51.0447, -114.0719)
        self.assertEqual(keys[0], "fescue_grassland")
        self.assertIn("aspen_parkland", keys)

    def test_banff_is_northern_continental_divide(self):
        self.assertEco(51.1784, -115.5708, "northern_continental_divide")

    def test_jasper_is_eastern_continental_ranges(self):
        """Banff and Jasper were one key before and are two ecoregions now,
        which is a real distinction the mountains have and the placeholder
        could not carry."""
        self.assertEco(52.8737, -118.0814, "eastern_continental_ranges")


class TestSaskatchewanCityLookups(unittest.TestCase):
    """SK city coordinates → expected ecoregion key (V2.14 expansion).
    SK polygons lie east of the -110 meridian (the AB/SK border)."""

    def assertEco(self, lat: float, lng: float, expected_key: str):
        got = lookup_ecoregion(lat, lng)
        self.assertEqual(got, expected_key,
                         f"({lat}, {lng}) → got {got!r}, expected {expected_key!r}")

    def test_regina_is_moist_mixed_grassland(self):
        self.assertEco(50.4452, -104.6189, "moist_mixed_grassland")

    def test_lumsden_is_moist_mixed_grassland(self):
        self.assertEco(50.6500, -104.8700, "moist_mixed_grassland")

    def test_saskatoon_is_moist_mixed_grassland(self):
        self.assertEco(52.1332, -106.6700, "moist_mixed_grassland")

    def test_north_battleford_is_aspen_parkland(self):
        self.assertEco(52.7575, -108.2861, "aspen_parkland")

    def test_battleford_is_aspen_parkland(self):
        self.assertEco(52.7368, -108.2967, "aspen_parkland")

    def test_swift_current_is_mixed_grassland(self):
        self.assertEco(50.2881, -107.7939, "mixed_grassland")


class TestOutsideCoverage(unittest.TestCase):
    """Points outside the shipped AB+SK polygon coverage return None — never
    raise. Winnipeg (east of the SK/MB border) and Vancouver stay uncovered."""

    def test_vancouver_outside(self):
        self.assertIsNone(lookup_ecoregion(49.2827, -123.1207))

    def test_winnipeg_outside(self):
        self.assertIsNone(lookup_ecoregion(49.8951, -97.1384))

    def test_arctic_outside(self):
        self.assertIsNone(lookup_ecoregion(75.0, -100.0))

    def test_none_inputs_safe(self):
        self.assertIsNone(lookup_ecoregion(None, None))
        self.assertIsNone(lookup_ecoregion(53.5, None))
        self.assertIsNone(lookup_ecoregion(None, -113.5))


class TestLabelForKey(unittest.TestCase):

    def test_known_key(self):
        self.assertIn("Aspen Parkland", label_for_key("aspen_parkland"))

    def test_unknown_key_returns_key_itself(self):
        self.assertEqual(label_for_key("not_real"), "not_real")

    def test_none_returns_dash(self):
        self.assertEqual(label_for_key(None), "—")


if __name__ == "__main__":
    unittest.main()


# ═══════════════════════════════════════════════════════════════════════════
#  V2.38 — two axes, and a site that is in more than one region
# ═══════════════════════════════════════════════════════════════════════════
#
# User feedback: "I'd prefer it breakdown into the individual ecoregions it
# exists in so when I add BC and other areas of turtle island we simply add
# more ecoregions." That only works if the vocabulary IS the polygon file, so
# adding a region is adding a polygon — which is what these hold down.

from src import ecoregion as _eco  # noqa: E402


class TestTheVocabularyIsTheFile(unittest.TestCase):
    """The geographic vocabulary is read from the shipped polygons, not from a
    list beside them that has to be remembered."""

    def test_every_polygon_key_is_offered_in_the_filter(self):
        from_file = {(f.get("properties") or {}).get("key")
                     for f in _load_features()}
        from_file.discard(None)
        self.assertTrue(from_file)
        self.assertTrue(from_file.issubset(set(_eco.geographic_keys())),
                        "a shipped polygon exists that no dropdown offers")

    def test_the_two_axes_are_separate(self):
        """Geographic regions are places; moisture niches are conditions that
        occur inside any of them. Mixing them is what made 'which ecoregion is
        my site in?' and 'is this spot wet?' one control."""
        geo = set(_eco.geographic_keys())
        wet = {k for k, _n, _w in _eco.MOISTURE_NICHES}
        self.assertEqual(geo & wet, set())
        self.assertEqual(set(_eco.ecoregion_keys()), geo | wet)
        for k in wet:
            self.assertTrue(_eco.is_moisture_niche(k))
        for k in geo:
            self.assertFalse(_eco.is_moisture_niche(k))

    def test_no_lookup_can_return_a_moisture_niche(self):
        """No lat/lng puts you in 'wet ground'. If a polygon ever claimed one,
        the site panel would assert a moisture condition from a map."""
        for f in _load_features():
            key = (f.get("properties") or {}).get("key")
            self.assertFalse(_eco.is_moisture_niche(key),
                             f"{key} is a condition, not a place")

    def test_name_and_place_stay_apart(self):
        """Packed into one label they elided mid-word in the dropdown."""
        for key, name, where in _eco.ecoregions():
            self.assertTrue(name, key)
            self.assertNotIn("(", name, f"{key}: place packed into the name")

    def test_the_fallback_matches_the_shipped_file(self):
        """The hard-coded list is only for a build whose resources are broken.
        If it drifts from the file, that build silently offers a different
        vocabulary than the one the polygons use."""
        self.assertEqual([k for k, _n, _w in _eco._FALLBACK_GEOGRAPHIC],
                         list(_eco.geographic_keys()))
        self.assertEqual(_eco._FALLBACK_GEOGRAPHIC,
                         list(_eco.geographic_ecoregions()))

    def test_display_order_is_stable_and_deduplicated(self):
        keys = _eco.geographic_keys()
        self.assertEqual(len(keys), len(set(keys)),
                         "a region drawn as two lobes was offered twice")

    def test_a_packed_legacy_label_still_splits(self):
        self.assertEqual(_eco._split_label("Aspen Parkland (central AB)"),
                         ("Aspen Parkland", "central AB"))
        self.assertEqual(_eco._split_label("Riparian"), ("Riparian", ""))
        # The last bracket wins, so a name with its own brackets survives.
        self.assertEqual(_eco._split_label("Boreal (mixedwood) Plain (north)"),
                         ("Boreal (mixedwood) Plain", "north"))


class TestASiteCanBeInTwo(unittest.TestCase):
    """``lookup_ecoregion`` returned the first match and stopped. A property
    near a boundary belongs to both, and the second one is exactly the species
    list that was going missing."""

    #: Calgary, where the fescue grassland runs into the aspen parkland.
    #:
    #: This point has moved twice, and each move says something about the data
    #: underneath it. It began at (53.0, -114.8), an overlap of two *rectangles*
    #: rather than of anything on the ground. V2.49 moved it to Nordegg when the
    #: redrawn polygons put that coordinate squarely in the parkland alone.
    #: V2.67 moved it here, because the surveyed layer **tiles** — real
    #: ecoregions do not overlap, that is what makes them a classification — so
    #: two regions are reported where a site is inside one and within five
    #: kilometres of another. Calgary genuinely is.
    #:
    #: The behaviour under test has never changed. What changed is that it is
    #: now produced by a measured distance rather than by how wide somebody drew
    #: an overlap.
    TRANSITION = (51.0447, -114.0719)

    def test_a_boundary_site_reports_both(self):
        keys = _eco.lookup_ecoregions(*self.TRANSITION)
        self.assertIn("fescue_grassland", keys)
        self.assertIn("aspen_parkland", keys)

    def test_the_region_the_site_is_actually_in_comes_first(self):
        """Containing regions sort ahead of merely-near ones, so the singular
        shim keeps answering with the region the site is in rather than one it
        is beside."""
        self.assertEqual(_eco.lookup_ecoregions(*self.TRANSITION)[0],
                         "fescue_grassland")

    def test_the_singular_shim_still_answers_one(self):
        self.assertEqual(_eco.lookup_ecoregion(*self.TRANSITION),
                         _eco.lookup_ecoregions(*self.TRANSITION)[0])

    def test_an_ordinary_site_reports_exactly_one(self):
        self.assertEqual(_eco.lookup_ecoregions(53.55, -113.49),
                         ["aspen_parkland"])          # Edmonton

    def test_two_pieces_of_one_region_count_once(self):
        """A region is drawn as many polygons — the surveyed layer splits each
        one again by Alberta subregion — and being inside one piece is being in
        the region once, not once per piece."""
        keys = _eco.lookup_ecoregions(52.13, -106.67)  # Saskatoon
        self.assertEqual(keys, ["moist_mixed_grassland"])

    def test_outside_everything_is_empty_not_a_guess(self):
        self.assertEqual(_eco.lookup_ecoregions(49.28, -123.12), [])   # Vancouver
        self.assertEqual(_eco.lookup_ecoregions(None, None), [])

    def test_the_detection_payload_carries_every_match(self):
        from src.property_data import fetch_ecoregion
        data = fetch_ecoregion(*self.TRANSITION)
        self.assertEqual(data["keys"], _eco.lookup_ecoregions(*self.TRANSITION))
        self.assertEqual(data["key"], data["keys"][0])
        # The readout names both, so the user can see why two are checked.
        self.assertIn("Fescue Grassland", data["label"])
        self.assertIn("Aspen Parkland", data["label"])

    def test_no_pin_no_payload(self):
        from src.property_data import fetch_ecoregion
        self.assertIsNone(fetch_ecoregion(49.28, -123.12))


class TestOneVocabularyEverywhere(unittest.TestCase):
    """Every list of ecoregions in the app must be the same list.

    Before V2.38 there were four hand-kept copies — the plant filter, the data
    validator, the community-library habitat labels, and the polygon file — and
    a key missing from one of them did not fail. It went quiet: an ecoregion
    with no label silently read "Generalist", which is how `moist_mixedgrass`,
    the commonest tag in the catalogue at 246 plants, went unlabelled for two
    minor versions.
    """

    def test_the_validator_accepts_exactly_the_vocabulary(self):
        from src.data_quality import _load_ecoregion_keys
        self.assertEqual(_load_ecoregion_keys(), set(_eco.ecoregion_keys()))

    def test_the_validator_refuses_an_empty_vocabulary(self):
        """A silent pass is worse than a loud failure in a data gate: an empty
        key set makes every ecoregion token in the catalogue valid."""
        import src.ecoregion as mod
        from src.data_quality import _load_ecoregion_keys
        original = mod.ecoregion_keys
        mod.ecoregion_keys = lambda: []
        try:
            with self.assertRaises(RuntimeError):
                _load_ecoregion_keys()
        finally:
            mod.ecoregion_keys = original

    def test_the_community_habitat_labels_cover_the_vocabulary(self):
        from src.db import polycultures
        self.assertEqual(set(polycultures.ECOREGION_LABELS),
                         set(_eco.ecoregion_keys()))
        for key, name, _where in _eco.ecoregions():
            self.assertEqual(polycultures.ECOREGION_LABELS[key], name)

    def test_the_plant_filter_offers_the_vocabulary(self):
        """AST-only for ``plant_panel`` (it imports PyQt6, and this must hold
        on a bare container too); a real import for the facet module, which is
        Qt-free precisely so that a test like this can just read it.

        V2.46: the facet vocabularies moved to ``src/plant_facets.py`` when the
        architecture guard fired on ``plant_panel``. What matters is unchanged —
        the choices are still *derived* from the one shared vocabulary and are
        not a second list — so the assertion follows the code rather than
        pinning the old address.
        """
        import ast
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent
        facets = (root / "src" / "plant_facets.py").read_text(encoding="utf-8")
        built_from_shared = any(
            isinstance(n, ast.ImportFrom)
            and n.module == "src.ecoregion"
            and any(a.name == "ECOREGIONS" for a in n.names)
            for n in ast.walk(ast.parse(facets)))
        self.assertTrue(built_from_shared,
                        "plant_facets no longer builds its choices from the "
                        "shared vocabulary — that is a second list to keep")
        # …and the panel still gets them from there rather than re-declaring.
        panel = (root / "src" / "plant_panel.py").read_text(encoding="utf-8")
        re_exports = any(
            isinstance(n, ast.ImportFrom) and n.module == "src.plant_facets"
            and any(a.name == "_ECOREGION_CHOICES" for a in n.names)
            for n in ast.walk(ast.parse(panel)))
        self.assertTrue(re_exports,
                        "plant_panel has grown its own ecoregion choices back")
        from src.plant_facets import _ECOREGION_CHOICES
        self.assertEqual({k for _lbl, k in _ECOREGION_CHOICES if k},
                         set(_eco.ecoregion_keys()))

    def test_every_key_appears_in_the_habitat_facet_choices(self):
        from src.db import polycultures
        choices = polycultures.facet_filter_choices()["habitat"]
        for _key, name, _where in _eco.ecoregions():
            self.assertIn(name, choices)


class TestTheEcoregionMap(unittest.TestCase):
    """V2.48. The maps the author asked for, and the caveat that has to travel
    with every one of them."""

    def test_it_draws_every_region_in_the_vocabulary_that_has_a_polygon(self):
        from src.ecoregion_map import region_geometry
        from src.ecoregion import geographic_keys
        drawn = set(region_geometry())
        self.assertEqual(drawn, set(geographic_keys()))

    def test_several_polygons_under_one_key_merge(self):
        """A region may be drawn as more than one polygon, and a caller asking
        to draw it means all of them.

        Asserted against a synthetic file rather than the shipped one: the
        V2.48 version of this test read the shipped parkland's two rectangles,
        and V2.49 redrew it as a single arc, so the test was measuring the
        drawing rather than the merge."""
        import src.ecoregion_map as em
        box = lambda x: {"type": "Feature",
                         "properties": {"key": "aspen_parkland"},
                         "geometry": {"type": "Polygon",
                                      "coordinates": [[[x, 0], [x + 1, 0],
                                                       [x + 1, 1], [x, 1],
                                                       [x, 0]]]}}
        real = em._load
        em._load = lambda: [box(0), box(5)]
        try:
            self.assertEqual(len(em.region_geometry()["aspen_parkland"]), 2)
        finally:
            em._load = real

    def test_a_highlighted_region_is_drawn_differently_from_an_absent_one(self):
        from src.ecoregion_map import map_svg
        plain = map_svg({})
        marked = map_svg({"aspen_parkland": "high"})
        self.assertNotEqual(plain, marked)
        self.assertIn("high confidence", marked)
        self.assertIn("not recorded", marked)

    def test_confidence_changes_the_fill(self):
        """Three occurrence records must not look like three hundred (P9)."""
        from src.ecoregion_map import map_svg
        high = map_svg({"aspen_parkland": "high"})
        low = map_svg({"aspen_parkland": "low"})
        self.assertNotEqual(high, low)


class TestEveryRegionHasItsOwnColour(unittest.TestCase):
    """*"I would like the different ecoregions to be represented by different
    colours as well."* (V2.51)

    The constraint that makes this more than a palette swap: the fill was
    already carrying confidence, and confidence is not allowed to stop being
    visible (P9). Hue took over identity, lightness took over confidence.
    """

    def _fills(self, svg: str) -> list:
        import re
        return re.findall(r'fill="(#[0-9a-f]{6})"', svg)

    def test_the_reference_map_draws_six_different_colours(self):
        from src.ecoregion_map import map_svg, region_geometry
        fills = set(self._fills(map_svg(reference=True)))
        self.assertEqual(len(fills), len(region_geometry()))

    def test_every_region_in_the_vocabulary_has_a_colour_of_its_own(self):
        """Asked through ``region_fill`` rather than of ``REGION_COLOUR``.

        Since V2.67 the fill resolves through the ecozone scheme for the ELC
        vocabulary, so a literal-membership check would only be testing which
        dict a colour happens to live in. What has to be true is that every
        region the map draws gets a colour, and that no two get the same one.
        """
        from src.ecoregion_map import region_geometry
        from src.ecoregion_palette import _FALLBACK_COLOUR, region_fill
        drawn = sorted(region_geometry())
        fills = {key: region_fill(key, "high")[0] for key in drawn}
        uncoloured = [k for k, v in fills.items() if v == _FALLBACK_COLOUR]
        self.assertEqual(uncoloured, [],
                         "these regions fell through to the fallback colour, "
                         "so their fill asserts nothing")
        self.assertEqual(len(set(fills.values())), len(fills),
                         "two regions share a fill")

    def test_confidence_still_shows_inside_one_region_s_colour(self):
        """The whole risk of this change: spending the fill on identity and
        quietly dropping the confidence encoding."""
        from src.ecoregion_map import region_fill
        shades = [region_fill("aspen_parkland", b)[0]
                  for b in ("high", "medium", "low")]
        self.assertEqual(len(set(shades)), 3, shades)

    def test_a_faint_region_is_still_not_the_absent_grey(self):
        """The palest band has to stay recognisably its own hue, or "coloured
        means recorded" stops being readable at a glance."""
        from src.ecoregion_palette import ABSENT_FILL, region_fill
        for key in ("mixedgrass_prairie", "aspen_parkland"):
            fill = region_fill(key, "low")[0].lstrip("#")
            r, g, b = (int(fill[i:i + 2], 16) for i in (0, 2, 4))
            self.assertGreater(max(r, g, b) - min(r, g, b), 30,
                               f"{key} low band {fill} has no chroma left")
            self.assertNotEqual(fill, ABSENT_FILL[0].lstrip("#"))

    def test_the_reference_map_claims_no_confidence(self):
        """It is a key, not a range map. The old callers passed a fabricated
        "medium" for every region and got a tooltip saying so."""
        from src.ecoregion_map import map_svg
        svg = map_svg(reference=True)
        for phrase in ("confidence", "not recorded"):
            self.assertNotIn(phrase, svg)

    def test_the_legend_names_every_region_it_draws(self):
        from src.ecoregion_map import legend_html, region_geometry
        from src.ecoregion import ecoregion_display
        key = legend_html()
        for region in region_geometry():
            self.assertIn(ecoregion_display(region)[0], key)

    def test_the_legend_can_be_a_row_of_links(self):
        from src.ecoregion_map import legend_html
        linked = legend_html(lambda k: f"/plants/ecoregion/{k}/")
        self.assertIn('href="/plants/ecoregion/aspen_parkland/"', linked)
        self.assertNotIn("href", legend_html())

    def test_every_region_name_is_printed_inside_that_region(self):
        """The first coloured draft printed "Montane" in British Columbia:
        a hand-placed anchor had drifted a degree east of its own strip, which
        nothing checked because nothing had ever drawn it in colour.

        V2.67 removed the hand placements — twenty-four of them would go stale
        the first time a polygon moved — so this now checks the *computed*
        point for every region the map draws, which is a stronger claim than
        the six it used to make.
        """
        from src.ecoregion_map import _label_point, region_geometry
        from src.geometry import point_in_ring
        for key, rings in region_geometry().items():
            ring = max(rings, key=len)
            lon, lat, _angle = _label_point(key, ring)
            self.assertTrue(
                point_in_ring(lat, lon, ring),
                f"{key} label at {lat:.3f},{lon:.3f} is outside its own ring")

    def test_the_map_fills_its_frame(self):
        """A 760x470 box letterboxed a near-square map into its middle third,
        so a third of the figure was blank on each side and the drawing came
        out half the size it should have been. ``frame_height`` is the height
        that leaves no bars.

        Asserted against the projected window rather than the polygons: the
        window is deliberately half a degree wider than the shapes so nothing
        sits flush against the border, and that margin is not letterboxing.

        Measured over the window's whole *edge*, not its four corners. Under
        the equal-area conic V2.66 moved to, the corners are not the extremes:
        the cone curves, so the northern edge bows upward and its midpoint sits
        higher in the frame than either north corner. Checking the corners
        alone would report a letterbox that is not there, and would miss a real
        one along the top.
        """
        from src.ecoregion_map import _BOUNDS, _projector, frame_height
        width = 600
        height = frame_height(width)
        project = _projector(width, height)
        west, south, east, north = _BOUNDS
        xs, ys = [], []
        for i in range(201):
            f = i / 200.0
            lon, lat = west + (east - west) * f, south + (north - south) * f
            for point in ((lon, south), (lon, north), (west, lat), (east, lat)):
                x, y = project(*point)
                xs.append(x)
                ys.append(y)
        self.assertAlmostEqual(min(xs), 0, delta=0.6)
        self.assertAlmostEqual(min(ys), 0, delta=0.6)
        self.assertAlmostEqual(max(xs), width, delta=0.6)
        self.assertAlmostEqual(max(ys), height, delta=0.6)

    def test_the_old_landscape_frame_would_have_failed_that(self):
        """Guards the guard: 600x376 is the aspect the maps shipped at, and it
        has to be visibly wrong by this measure or the check above proves
        nothing."""
        from src.ecoregion_map import _BOUNDS, _projector
        project = _projector(600, 376)
        self.assertGreater(project(_BOUNDS[0], _BOUNDS[3])[0], 50)

    def test_every_point_lands_inside_the_viewport(self):
        import re
        from src.ecoregion_map import map_svg
        svg = map_svg({}, width=400, height=300)
        for points in re.findall(r'<polygon points="([^"]+)"', svg):
            for pair in points.split():
                x, y = (float(v) for v in pair.split(","))
                self.assertTrue(0 <= x <= 400, x)
                self.assertTrue(0 <= y <= 300, y)

    def test_it_never_reaches_outside_itself(self):
        """Self-contained SVG: no script, no external reference, no image.

        The `xmlns` is a namespace identifier rather than a URL anything
        fetches, so it is stripped before the check instead of being allowed
        to make the check vacuous.

        ``url(#id)`` is allowed and ``url(`` anything else is not. V2.66 gave
        the map a hatch pattern and a clip path, both of which are referenced
        the only way SVG can reference them: by fragment, into the same
        document. That fetches nothing. Forbidding the whole `url(` token would
        have meant either dropping the colour-vision safeguard or weakening the
        rule that actually matters, which is that a species page must not make
        a network request to draw a map."""
        import re
        from src.ecoregion_map import map_svg
        svg = map_svg({"aspen_parkland": "high"}).replace(
            'xmlns="http://www.w3.org/2000/svg"', "")
        for forbidden in ("<script", "http://", "https://", "<image"):
            self.assertNotIn(forbidden, svg)
        for ref in re.findall(r"url\(([^)]*)\)", svg):
            self.assertTrue(ref.startswith("#"),
                            f"url({ref}) leaves the document")

    def test_the_caveat_describes_the_polygons_that_actually_ship(self):
        """An outline without a caption is a claim about a boundary — but the
        caption has to match the file, in both directions.

        This test used to assert the words "not surveyed boundaries", and it
        passed for a whole increment after V2.67 made that false: the caption
        was still calling the surveyed layer a hand-traced diagram on 432
        public pages. So it now checks the claim against the polygon file's own
        provenance rather than against a remembered string, and fails whichever
        way the two drift apart."""
        import json

        from src.ecoregion_map import CAVEAT
        from src.resources import resource_path

        with open(resource_path("data", "ecoregions_canada.geojson"),
                  encoding="utf-8") as handle:
            provenance = (json.load(handle).get("comment") or "")

        surveyed = "digitised" in provenance.lower()
        self.assertIs(surveyed, "digitised" in CAVEAT.lower(),
                      "the caption and the file disagree about whether these "
                      "outlines come from a survey")
        if surveyed:
            self.assertIn("simplified", CAVEAT.lower(),
                          "the export simplifies; that is the one way the "
                          "drawing differs from its source and it must be said")
            for stale in ("hand-traced", "not surveyed", "is a diagram"):
                self.assertNotIn(stale, CAVEAT.lower(),
                                 f"{stale!r} understates a surveyed layer")

    def test_a_missing_polygon_file_degrades_to_nothing(self):
        """A map is an illustration. Losing it must not take a page down."""
        import src.ecoregion_map as em
        real = em._load
        em._load = lambda: []
        try:
            self.assertEqual(em.map_svg({"aspen_parkland": "high"}), "")
        finally:
            em._load = real


# ── Colour-vision safety ───────────────────────────────────────────────────
#
# The V2.51 palette varied in hue alone. Three of its six colours were greens
# within OKLab deltaE 8 of one another, which is indistinguishable under
# deuteranopia and close to it with full colour vision. Nothing caught that,
# because "are these colours far enough apart" had never been written down as
# something a test could answer. It is computable, so it is computed here.
#
# The maths is the standard one: sRGB to linear, linear to OKLab, Euclidean
# distance times 100, with Machado et al.'s colour-vision-deficiency matrices
# applied first. Reimplemented rather than imported because the app ships no
# colour-science dependency and this is thirty lines.

from src.colour_distance import (chroma as _chroma,  # noqa: E402
                                 delta_e as _delta_e,
                                 lightness as _lightness,
                                 worst_cvd_delta_e as _worst_cvd)


def _adjacent_pairs():
    """Region pairs that share ground, from the shipped polygons.

    Pure-Python on purpose: the app has no shapely. Two regions count as
    adjacent when a vertex of one falls inside the other, or when their
    boundaries pass within a few kilometres — which covers both the deliberate
    overlaps the placeholder used and the tiled edges the surveyed layer has.

    Bounding boxes are compared first. The surveyed layer is 115 polygons of
    real coastline rather than six rectangles, and testing every vertex of
    every polygon against every other took this from instant to most of a
    minute.
    """
    from src.geometry import point_in_ring
    from src.ecoregion_map import _load, _rings

    shapes: dict = {}
    for feature in _load():
        key = ((feature.get("properties") or {}).get("key") or "").strip()
        if not key:
            continue
        for ring in _rings(feature.get("geometry") or {}):
            if not ring:
                continue
            lons = [float(p[0]) for p in ring]
            lats = [float(p[1]) for p in ring]
            shapes.setdefault(key, []).append(
                (ring, (min(lons), min(lats), max(lons), max(lats))))

    #: Degrees of slack when comparing boxes. Roughly 11 km of latitude: two
    #: tiled regions touch exactly, and floating point plus simplification mean
    #: "exactly" needs a tolerance.
    pad = 0.1

    def boxes_meet(one, two):
        return not (one[2] + pad < two[0] or two[2] + pad < one[0]
                    or one[3] + pad < two[1] or two[3] + pad < one[1])

    def touches(a_pieces, b_pieces):
        for a_ring, a_box in a_pieces:
            for b_ring, b_box in b_pieces:
                if not boxes_meet(a_box, b_box):
                    continue
                for lon, lat in a_ring:
                    if point_in_ring(lat, lon, b_ring):
                        return True
                for lon, lat in b_ring:
                    if point_in_ring(lat, lon, a_ring):
                        return True
                # Tiled neighbours share an edge without either's vertices
                # falling strictly inside the other, so near-coincident
                # vertices count as contact.
                for lon, lat in a_ring[::4]:
                    for blon, blat in b_ring[::4]:
                        if abs(lon - blon) < 0.02 and abs(lat - blat) < 0.02:
                            return True
        return False

    pairs = set()
    keys = sorted(shapes)
    for i, one in enumerate(keys):
        for two in keys[i + 1:]:
            if touches(shapes[one], shapes[two]):
                pairs.add((one, two))
    return sorted(pairs)


class TestColoursSurviveColourBlindness(unittest.TestCase):
    """The rule: two ecoregions that share a border must be tellable apart.

    Enforced against whatever polygons are shipped, so when the real ELC
    polygons land with their dozen-odd regions this test names the pairs that
    need attention instead of leaving it to somebody's eye.
    """

    #: OKLab deltaE x100. The documented floor for categorical fills under
    #: simulated colour-vision deficiency, legal at this value only when a
    #: second channel carries the same distinction.
    FLOOR = 8.0

    def test_the_polygons_do_produce_adjacent_pairs(self):
        """Guards the guard. If the adjacency finder returned nothing, every
        assertion below would pass while checking nothing at all."""
        self.assertGreaterEqual(len(_adjacent_pairs()), 6)

    def test_a_focus_map_never_leaves_a_hole_at_the_provincial_border(self):
        """A subregion map draws its parent ecoregion underneath.

        Alberta publishes a natural subregion layer and Saskatchewan does not.
        On the page for an ecoregion that crosses the border, the Alberta half
        was covered by subregion polygons and the Saskatchewan half by nothing
        at all: inside the branch, so the grey context skipped it; no subregion,
        so the focus layer skipped it too. It fell through to the bare province
        wash and drew a hard line down the provincial boundary, which reads as
        *this ecoregion stops at the border* and is false about every one of
        them. Reported from a phone: "I notice this split at the AB SK border".
        """
        from src.ecoregion_map import map_svg
        from src.ecoregion_tree import SUBREGION, subregions_in

        crossing = [k for k, _n, where in _eco.geographic_ecoregions()
                    if "/" in where and subregions_in(k)]
        self.assertTrue(crossing, "no cross-border region has subregions")
        for key in crossing:
            svg = map_svg(width=420, height=280, reference=True,
                          level=SUBREGION, within=key, labels=False)
            self.assertIn("ecomap-parent", svg,
                          f"{key} draws no parent underlay, so its "
                          f"subregion-less half is a hole")

    def test_numbered_maps_and_their_legends_count_the_same(self):
        """The number on the map and the number in the key must be the same
        number. Two orderings kept in step by hand do not stay in step, and a
        region numbered 4 on one and 5 on the other is worse than no numbers
        at all because nothing about it looks wrong."""
        from src.ecoregion_map import map_svg, numbered_order
        from src.ecoregion_palette import legend_html
        from src.ecoregion_tree import ECOREGION, ecozones

        for zone, _name in ecozones():
            order = numbered_order(ECOREGION, zone)
            if len(order) < 2:
                continue
            svg = map_svg(width=460, height=310, reference=True,
                          level=ECOREGION, within=zone, labels=False,
                          numbered=True)
            self.assertEqual(svg.count("ecomap-num"), len(order), zone)
            key_html = legend_html(level=ECOREGION, within=zone, numbered=True)
            for position, region in enumerate(order, 1):
                name = _eco.ecoregion_display(region)[0]
                pip = f'<span class="ecokey-n">{position}</span>'
                self.assertIn(pip, key_html, f"{zone}: no pip {position}")
                # The pip and the name it belongs to must be adjacent in the
                # markup, which is what proves they are the same row.
                after = key_html.split(pip, 1)[1]
                self.assertLess(after.find(html.escape(name)), 400,
                                f"{zone}: pip {position} is not on {name}")

    def test_bordering_regions_separate_by_colour_or_by_hatch(self):
        """Same rule ``tools/ecoregions/validate.py`` holds on the printed map.

        Two regions in the SAME ecozone are exempt: they share a hue on
        purpose, and the lightness step between them cannot be widened without
        breaking a cross-ecozone boundary that matters more (measured in V2.66:
        0.06 holds everything, 0.10 does not). Inside one system the boundary
        stroke and the label do the work.
        """
        from src.ecoregion_palette import HATCHED, elc_zone_of, region_fill
        from src.ecoregion import ecoregion_display

        def zone_of(key):
            name, _where = ecoregion_display(key)
            return elc_zone_of(name)

        for one, two in _adjacent_pairs():
            if zone_of(one) and zone_of(one) == zone_of(two):
                continue
            gap = _worst_cvd(region_fill(one, "high")[0],
                             region_fill(two, "high")[0])
            if gap >= self.FLOOR:
                continue
            self.assertTrue(
                one in HATCHED or two in HATCHED,
                f"{one} and {two} share a border, are only deltaE {gap:.1f} "
                f"apart under colour-vision deficiency, and neither is "
                f"hatched. Re-step one of the two colours in REGION_COLOUR, "
                f"or add one of them to HATCHED.")

    def test_no_region_is_hatched_without_needing_it(self):
        """A hatch is visual noise; it has to be earned. If a colour change
        makes one unnecessary, this says so rather than letting it linger."""
        from src.ecoregion_palette import HATCHED, elc_zone_of, region_fill
        from src.ecoregion import ecoregion_display

        def zone_of(key):
            name, _where = ecoregion_display(key)
            return elc_zone_of(name)

        needed = set()
        for one, two in _adjacent_pairs():
            if zone_of(one) and zone_of(one) == zone_of(two):
                continue
            if _worst_cvd(region_fill(one, "high")[0],
                          region_fill(two, "high")[0]) < self.FLOOR:
                needed.update({one, two})
        for key in HATCHED:
            self.assertIn(key, needed,
                          f"{key} is hatched but every region it borders is "
                          f"already far enough away in colour.")

    def test_the_palette_varies_in_lightness_not_only_hue(self):
        """The specific V2.51 defect: six colours, one lightness band, three
        of them green."""
        from src.ecoregion_palette import REGION_COLOUR
        lightness = [_lightness(c) for c in REGION_COLOUR.values()]
        self.assertGreater(max(lightness) - min(lightness), 0.30)

    def test_every_confidence_band_still_reads_as_recorded(self):
        """Lightness carries confidence as well as identity, and the two
        channels compete. A low-confidence fill that has faded to within a
        whisker of the "not recorded here" grey has stopped saying what it
        means: the reader sees absence where the data says presence."""
        from src.ecoregion_palette import ABSENT_FILL, REGION_COLOUR, region_fill
        for key in REGION_COLOUR:
            for band in ("high", "medium", "low", ""):
                fill = region_fill(key, band)[0]
                gap = _delta_e(fill, ABSENT_FILL[0])
                self.assertGreater(
                    gap, 9.5,
                    f"{key} at {band or 'unstated'} confidence is only "
                    f"deltaE {gap:.1f} from the not-recorded grey.")

    def test_not_recorded_reads_as_grey_beside_every_fill(self):
        """The distance above is one channel; this is the other, and it is the
        one a reader actually uses. "Coloured means recorded" works because the
        absent fill has almost no chroma and every region fill has some."""
        from src.ecoregion_palette import ABSENT_FILL, REGION_COLOUR, region_fill

        neutral = _chroma(ABSENT_FILL[0])
        for key in REGION_COLOUR:
            for band in ("high", "medium", "low", ""):
                self.assertGreater(
                    _chroma(region_fill(key, band)[0]), neutral * 2.5,
                    f"{key} at {band or 'unstated'} confidence is barely more "
                    f"chromatic than the not-recorded grey.")


class TestMultiPolygonRegionsAreFound(unittest.TestCase):
    """A region drawn as several pieces is still one region.

    Before V2.67 the lookup tested ``type != "Polygon"`` and skipped, which was
    survivable only because the six shipped shapes were single rings. Every
    published ecoregion layer has MultiPolygons in it — a region with an island,
    or a lobe the far side of a river — and skipping them does not raise, it
    just answers "you are in no ecoregion at all", which reads as *we do not
    cover your area* rather than as a bug.
    """

    def setUp(self):
        import src.ecoregion as eco
        self._real = eco._load_features
        eco._load_features = lambda: [{
            "properties": {"key": "aspen_parkland", "name": "Aspen Parkland",
                           "where": "test", "sort": 0},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [[[-114.0, 53.0], [-113.0, 53.0], [-113.0, 54.0],
                      [-114.0, 54.0], [-114.0, 53.0]]],
                    [[[-110.0, 53.0], [-109.0, 53.0], [-109.0, 54.0],
                      [-110.0, 54.0], [-110.0, 53.0]]],
                ]},
        }]
        self.eco = eco
        eco._feature_index.cache_clear()
        eco.geographic_ecoregions.cache_clear()

    def tearDown(self):
        self.eco._load_features = self._real
        self.eco._feature_index.cache_clear()
        self.eco.geographic_ecoregions.cache_clear()

    def test_a_point_in_the_first_piece_is_found(self):
        self.assertEqual(self.eco.lookup_ecoregions(53.5, -113.5),
                         ["aspen_parkland"])

    def test_a_point_in_the_second_piece_is_found_too(self):
        self.assertEqual(self.eco.lookup_ecoregions(53.5, -109.5),
                         ["aspen_parkland"])

    def test_a_point_in_the_gap_between_them_is_not(self):
        self.assertEqual(self.eco.lookup_ecoregions(53.5, -111.5), [])

    def test_the_region_still_appears_in_the_vocabulary(self):
        self.eco.geographic_ecoregions.cache_clear()
        self.assertIn("aspen_parkland",
                      [k for k, _n, _w in self.eco.geographic_ecoregions()])


class TestTheVocabularyHasThreeLevels(unittest.TestCase):
    """ecozone -> ecoregion -> Alberta subregion (V2.67).

    Twenty-four ecoregions is too many for one dropdown, and the three levels
    were already in the data — the polygon file has carried the ecozone and the
    Alberta subregion on every feature since adoption, and nothing had ever
    offered them.
    """

    def setUp(self):
        from src import ecoregion_tree
        self.t = ecoregion_tree

    def test_the_top_level_is_six_not_twenty_four(self):
        """The whole point: the first choice a user makes is six-way."""
        self.assertEqual(len(self.t.ecozones()), 6)

    def test_every_ecoregion_hangs_off_exactly_one_ecozone(self):
        from src.ecoregion import geographic_keys
        placed = [key for zone, _n in self.t.ecozones()
                  for key, _rn in self.t.regions_in(zone)]
        self.assertEqual(sorted(placed), sorted(geographic_keys()))
        self.assertEqual(len(placed), len(set(placed)),
                         "a region was filed under two ecozones")

    def test_alberta_subregions_are_reachable(self):
        """Dry Mixedgrass and Northern Fescue have been in the data since
        adoption and in no dropdown ever."""
        names = {name for _z, _zn, _l, regions in
                 [(a, b, c, d) for a, b, c, d in self.t.tree()]
                 for _rk, _rn, _l2, subs in regions
                 for _sk, name in [(s[0], s[1]) for s in subs]}
        self.assertIn("Dry Mixedgrass", names)
        self.assertIn("Northern Fescue", names)

    def test_saskatchewan_regions_carry_no_subregions(self):
        """Alberta publishes a subregion layer and Saskatchewan does not. The
        asymmetry is honest; inventing the missing half would not be."""
        self.assertEqual(self.t.subregions_in("churchill_river_upland"), [])

    # ── the name collision the rebuild brief predicted ──────────────────
    def test_the_two_athabasca_plains_are_different_keys(self):
        """"Athabasca Plain" is an ELC ecoregion on the Boreal Shield AND an
        Alberta natural subregion, and they are different ground. The brief
        warned about this pair; the first version of this module collided them
        anyway by slugging both to the same string."""
        self.assertEqual(self.t.level_of("athabasca_plain"), self.t.ECOREGION)
        self.assertEqual(self.t.level_of("sub_athabasca_plain"),
                         self.t.SUBREGION)

    def test_a_lineage_never_leaves_its_own_ecozone(self):
        """The symptom the collision produced: asking for the lineage of a
        Boreal Plains ecoregion returned a Boreal Shield one, by walking down
        to a subregion and back up the wrong parent."""
        for key in ("mid_boreal_uplands", "wabasca_lowland", "peace_lowland"):
            zones = {k for k in self.t.lineage_keys(key)
                     if self.t.level_of(k) == self.t.ECOZONE}
            self.assertEqual(zones, {"zone_boreal_plains"},
                             f"{key} reached outside its own ecozone")

    # ── matching runs along a lineage, both ways ────────────────────────
    def test_a_region_matches_its_ecozone(self):
        self.assertIn("zone_boreal_plains",
                      self.t.lineage_keys("mid_boreal_uplands"))

    def test_an_ecozone_matches_the_regions_inside_it(self):
        keys = self.t.lineage_keys("zone_boreal_plains")
        self.assertIn("mid_boreal_uplands", keys)
        self.assertIn("peace_lowland", keys)

    def test_a_moisture_niche_passes_through_untouched(self):
        """`riparian` is a condition, not a place, so it has no lineage to
        walk and must not be silently dropped by the expansion."""
        self.assertEqual(self.t.expand_for_filter(["riparian"]), ["riparian"])

    def test_expansion_is_deduplicated(self):
        keys = self.t.expand_for_filter(["zone_boreal_plains",
                                         "mid_boreal_uplands"])
        self.assertEqual(len(keys), len(set(keys)))
