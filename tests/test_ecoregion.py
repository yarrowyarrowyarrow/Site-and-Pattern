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

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ecoregion import (  # noqa: E402
    lookup_ecoregion,
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
        """Every feature's `key` must be one of the canonical keys in
        plant_panel._AB_ECOREGION_CHOICES — otherwise the auto-detect
        result wouldn't match any combo option."""
        canonical = {
            "aspen_parkland", "mixedgrass_prairie", "moist_mixedgrass",
            "fescue_foothills", "boreal_mixedwood", "riparian", "wet_meadow",
            "subalpine_montane",
        }
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

    def test_fort_mcmurray_is_boreal_mixedwood(self):
        self.assertEco(56.7264, -111.3803, "boreal_mixedwood")

    def test_grande_prairie_is_boreal_mixedwood(self):
        self.assertEco(55.1707, -118.7947, "boreal_mixedwood")

    def test_lethbridge_is_mixedgrass_prairie(self):
        self.assertEco(49.6956, -112.8451, "mixedgrass_prairie")

    def test_medicine_hat_is_mixedgrass_prairie(self):
        self.assertEco(50.0405, -110.6764, "mixedgrass_prairie")

    def test_calgary_is_fescue_foothills(self):
        """Calgary at -114.07°W sits in the fescue band (-114.5 to -113.5)
        of the starter polygon set. Real CEC data may place Calgary
        in transition; that's a per-polygon revision, not a code change."""
        self.assertEco(51.0447, -114.0719, "fescue_foothills")

    def test_banff_is_subalpine_montane(self):
        self.assertEco(51.1784, -115.5708, "subalpine_montane")

    def test_jasper_is_subalpine_montane(self):
        self.assertEco(52.8737, -118.0814, "subalpine_montane")


class TestSaskatchewanCityLookups(unittest.TestCase):
    """SK city coordinates → expected ecoregion key (V2.14 expansion).
    SK polygons lie east of the -110 meridian (the AB/SK border)."""

    def assertEco(self, lat: float, lng: float, expected_key: str):
        got = lookup_ecoregion(lat, lng)
        self.assertEqual(got, expected_key,
                         f"({lat}, {lng}) → got {got!r}, expected {expected_key!r}")

    def test_regina_is_moist_mixedgrass(self):
        self.assertEco(50.4452, -104.6189, "moist_mixedgrass")

    def test_lumsden_is_moist_mixedgrass(self):
        self.assertEco(50.6500, -104.8700, "moist_mixedgrass")

    def test_saskatoon_is_moist_mixedgrass(self):
        self.assertEco(52.1332, -106.6700, "moist_mixedgrass")

    def test_north_battleford_is_aspen_parkland(self):
        self.assertEco(52.7575, -108.2861, "aspen_parkland")

    def test_battleford_is_aspen_parkland(self):
        self.assertEco(52.7368, -108.2967, "aspen_parkland")

    def test_swift_current_is_mixedgrass_prairie(self):
        self.assertEco(50.2881, -107.7939, "mixedgrass_prairie")


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

    #: Nordegg / Rocky Mountain House, where the foothills genuinely run into
    #: the parkland. V2.49 moved this point: it used to be (53.0, -114.8),
    #: which was an overlap of the *rectangles* rather than of anything on the
    #: ground, and the redrawn polygons put that coordinate squarely in the
    #: parkland alone. The behaviour under test is unchanged; only the place
    #: where two regions really do meet has moved to where it really is.
    TRANSITION = (52.0, -115.3)

    def test_the_foothills_overlap_reports_both(self):
        keys = _eco.lookup_ecoregions(*self.TRANSITION)
        self.assertIn("fescue_foothills", keys)
        self.assertIn("aspen_parkland", keys)

    def test_the_singular_shim_still_answers_one(self):
        self.assertEqual(_eco.lookup_ecoregion(*self.TRANSITION),
                         _eco.lookup_ecoregions(*self.TRANSITION)[0])

    def test_an_ordinary_site_reports_exactly_one(self):
        self.assertEqual(_eco.lookup_ecoregions(53.55, -113.49),
                         ["aspen_parkland"])          # Edmonton

    def test_two_lobes_of_one_region_count_once(self):
        """moist_mixedgrass ships as two rectangles. Being in one of them is
        being in the region once, not twice."""
        keys = _eco.lookup_ecoregions(52.13, -106.67)  # Saskatoon
        self.assertEqual(keys, ["moist_mixedgrass"])

    def test_outside_everything_is_empty_not_a_guess(self):
        self.assertEqual(_eco.lookup_ecoregions(49.28, -123.12), [])   # Vancouver
        self.assertEqual(_eco.lookup_ecoregions(None, None), [])

    def test_the_detection_payload_carries_every_match(self):
        from src.property_data import fetch_ecoregion
        data = fetch_ecoregion(*self.TRANSITION)
        self.assertEqual(data["keys"], _eco.lookup_ecoregions(*self.TRANSITION))
        self.assertEqual(data["key"], data["keys"][0])
        # The readout names both, so the user can see why two are checked.
        self.assertIn("Fescue", data["label"])
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
        from src.ecoregion_map import REGION_COLOUR, region_geometry
        drawn = set(region_geometry())
        self.assertTrue(drawn <= set(REGION_COLOUR), drawn - set(REGION_COLOUR))
        self.assertEqual(len(set(REGION_COLOUR.values())), len(REGION_COLOUR))

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
        the hand-placed anchor had drifted a degree east of its own strip,
        which nothing checked because nothing had ever drawn it in colour."""
        from src.ecoregion_map import _LABEL_POINT
        from src.ecoregion import lookup_ecoregions
        for key, (lon, lat, _angle) in _LABEL_POINT.items():
            self.assertIn(key, lookup_ecoregions(lat, lon),
                          f"{key} label at {lat},{lon} is not inside {key}")

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

    def test_the_caveat_says_the_outlines_are_not_boundaries(self):
        """The polygons are hand-traced. An outline without this caption is a
        claim about a boundary."""
        from src.ecoregion_map import CAVEAT
        self.assertIn("Approximate extents", CAVEAT)
        self.assertIn("not surveyed boundaries", CAVEAT)

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

    Pure-Python on purpose: the app has no shapely. The shipped polygons
    deliberately overlap by a fraction of a degree at their shared edges (so a
    site near a boundary reports both regions), which means "do these two
    share ground" is answerable by asking whether any vertex of one falls
    inside the other.
    """
    from src.geometry import point_in_polygon
    from src.ecoregion_map import _load, _rings

    shapes = {}
    for feature in _load():
        key = ((feature.get("properties") or {}).get("key") or "").strip()
        if key:
            shapes.setdefault(key, []).extend(
                _rings(feature.get("geometry") or {}))
    pairs = set()
    keys = sorted(shapes)
    for i, one in enumerate(keys):
        for two in keys[i + 1:]:
            hit = any(point_in_polygon(lat, lon, [ring])
                      for ring in shapes[two]
                      for lon, lat in shapes[one][0]) or \
                  any(point_in_polygon(lat, lon, [ring])
                      for ring in shapes[one]
                      for lon, lat in shapes[two][0])
            if hit:
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

    def test_bordering_regions_separate_by_colour_or_by_hatch(self):
        from src.ecoregion_palette import HATCHED, region_fill
        for one, two in _adjacent_pairs():
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
        from src.ecoregion_palette import HATCHED, region_fill
        needed = set()
        for one, two in _adjacent_pairs():
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
