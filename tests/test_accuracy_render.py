"""
tests/test_accuracy_render.py — what the V2.88 fixes put on the screen.

Batch A of the V2.87 model audit (docs/plans/V2.88-reading-what-was-recorded.md)
was the viewer reading the wrong number: every flower in a raceme or panicle
drawn at the size of the whole cluster, a groundcover's flowers placed at its
real height above a body drawn at 18 cm, a duckweed floored to a 0.5 m reed, a
bee's recorded band colours never reaching the baked bee. Every part-level guard
passed throughout, because every part was built correctly; it was what the parts
were fed that was wrong.

So this boots the real viewer in headless Chromium (``html/accuracy_probe.html``),
pushes one catalogue plant at a time exactly as ``build_scene`` sends it, and
reads back what was built: each floret's drawn diameter, where the flowers top
out, how tall the plant is, and which rings the baked bee wears in which colours.
The cases go to the page in the URL fragment, so the page holds no copy of the
data to drift from the catalogue.

Self-skips without a Chromium binary, like the aspect gate in
``test_scene3d_render.py``, whose harness it shares. The source-level checks at
the bottom need no browser and never skip.
"""

import html
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.db.plants as _plants_mod  # noqa: E402
from src import pond_habit, scene_wildlife, vine_habit  # noqa: E402
from tests.test_scene3d_render import _Server, _find_chromium, _read_js  # noqa: E402

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_accuracy_test_")

#: Raceme, panicle and spike species whose florets the audit measured at 7-15x
#: their recorded size, and whose flowers topped the plant (Butte Primrose 3.4x).
_CLUSTERS = ("Scarlet Globemallow", "Canada Goldenrod", "Butte Primrose",
             "Harebell")
#: A head was already drawn at its true diameter. It is the control: if this
#: moves, the probe is measuring something other than the flower.
_HEAD = "Wild Bergamot"
_GROUNDCOVER = "Canada Anemone"            # 0.6 m recorded, drawn as an 18 cm mat
_SMALL_AQUATIC = "Ivy-leaved Duckweed"     # 2 cm recorded, drawn as a 0.5 m reed
_BANDED_BEE = "American Bumble Bee"        # thorax black, so it rendered solid black
#: V2.89: a vine beside a shrub climbs it; with nothing beside it, it lies low.
_CLIMBER, _HOST = "Wild Clematis", "Red Osier Dogwood"
_SPRAWLER = "Blue Clematis"
_HORSETAILS = ("Common Horsetail", "Swamp Horsetail", "Common Scouring-rush",
               "Variegated Horsetail")
#: V2.90: the pond. A floating leaf, a submerged plant, a broad leaf on a stalk,
#: and the plant most often mistaken for a horsetail.
_FLOATING, _SUBMERGED = "Yellow Pond-lily", "Sago Pondweed"
_BROADLEAF, _MARES_TAIL = "Broad-leaved Arrowhead", "Common Mare's-tail"
_IN_A_POND = _FLOATING + " in a pond"

#: A drawn floret may stand for several real ones: it covers the area that
#: n / drawn florets would, which for a goldenrod's 160 is up to 2.8x the single
#: flower. The defect was the reach of the WHOLE cluster, median 7.8x.
MAX_FLORET_OVER_RECORDED = 4.0
#: A recorded height is to the top of the flowers. A nodding floret may poke a
#: little past it; the defect put them up to 3.4x the plant.
MAX_TOP_OVER_HEIGHT = 1.15
TOP_SLACK_M = 0.02


def _bloom_month(p):
    """The middle of the plant's bloom window, so its flowers are open."""
    s, e = p.get("bloom_start") or 0, p.get("bloom_end") or 0
    if s and e and s <= e:
        return (s + e) // 2
    return s or 7


def _build_cases():
    """Every case through the real pipeline: DB record → build_scene → the plant
    dict the viewer receives; the bee's appearance bag from the fauna tables."""
    from src.db.plants import get_connection, init_db
    from src.project_store import plant_feature
    from src.scene_contract import build_scene

    init_db()
    conn = get_connection()
    try:
        ids = {r["common_name"]: r["id"] for r in conn.execute(
            "SELECT id, common_name FROM plants")}
        bees = [r["id"] for r in conn.execute(
            "SELECT id FROM fauna WHERE taxon = 'bee' ORDER BY id")]
        banded = conn.execute("SELECT id FROM fauna WHERE common_name = ?",
                              (_BANDED_BEE,)).fetchone()["id"]
    finally:
        conn.close()

    def feature(name, dx_m=0.0):
        return plant_feature({"plant_id": ids[name], "common_name": name,
                              "lat": 51.05, "lng": -114.07 + dx_m / 70000.0})

    def scene_of(*features):
        return build_scene({"type": "FeatureCollection",
                            "properties": {"site_config": {}},
                            "features": list(features)}, year=0, wind=False)

    def built(*features):
        return scene_of(*features)["plants"]

    plants = []
    for name in _CLUSTERS + (_HEAD, _GROUNDCOVER, _SMALL_AQUATIC,
                             _SPRAWLER) + _HORSETAILS + (
                                 _FLOATING, _SUBMERGED, _BROADLEAF, _MARES_TAIL):
        plant = built(feature(name))[0]
        plants.append({"name": name, "month": _bloom_month(plant),
                       "plant": plant})
    # The climber beside its host, a quarter-metre outside the crown edge.
    host = built(feature(_HOST))[0]
    pair = built(feature(_HOST), feature(_CLIMBER, host["canopy_m"] / 2 + 0.25))
    plants.append({"name": _CLIMBER, "month": 7, "plants": pair})
    # The pond-lily on a pond's water (V2.90).
    from src.db.structures import get_structure
    pond = scene_of({"type": "Feature",
                     "geometry": {"type": "Point", "coordinates": [-114.07, 51.05]},
                     "properties": {"element_type": "structure",
                                    "struct_def": dict(get_structure("pond"))}},
                    feature(_FLOATING))
    plants.append({"name": _IN_A_POND, "month": 7, "plants": pond["plants"],
                   "structures": pond["structures"]})

    # The control bee: one whose look has generic bands and no recorded
    # tergites, so the three baked shells must still be doing the job.
    plain = None
    for fid in bees:
        app = scene_wildlife.appearance_for_fauna(fid)
        if app and not app.get("band_colours") and app.get("bands"):
            plain = (fid, app)
            break
    bee_cases = [{"name": _BANDED_BEE,
                  "app": scene_wildlife.appearance_for_fauna(banded)}]
    if plain:
        bee_cases.append({"name": "plain bee %d" % plain[0], "app": plain[1]})
    return {"plants": plants, "bees": bee_cases}


@unittest.skipIf(_find_chromium() is None,
                 "no Chromium binary (set CHROME= to run this gate)")
class AccuracyRenderTest(unittest.TestCase):
    cases = None
    result = None

    @classmethod
    def setUpClass(cls):
        # Other modules point the shared DB module at their own temp dirs at
        # import time; use ours for the seed and put theirs back afterwards.
        saved = (_plants_mod._DATA_DIR, _plants_mod._DB_PATH)
        _plants_mod._DATA_DIR = _TMP_DIR
        _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
        try:
            cls.cases = _build_cases()
        finally:
            _plants_mod._DATA_DIR, _plants_mod._DB_PATH = saved

        chrome = _find_chromium()
        try:
            server = _Server()
        except OSError as exc:                       # no loopback port
            raise unittest.SkipTest(f"cannot bind a local port: {exc}")
        payload = quote(json.dumps(cls.cases, separators=(",", ":")), safe="")
        try:
            url = f"http://127.0.0.1:{server.port}/accuracy_probe.html#{payload}"
            proc = subprocess.run(
                [chrome, "--headless", "--no-sandbox", "--disable-gpu-sandbox",
                 "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
                 "--virtual-time-budget=60000", "--dump-dom", url],
                capture_output=True, text=True, timeout=300, encoding="utf-8")
        except (OSError, subprocess.TimeoutExpired) as exc:
            server.stop()
            raise unittest.SkipTest(f"Chromium would not run headlessly: {exc}")
        server.stop()
        match = re.search(r"ACCURACY (\{.*\})</title>", proc.stdout, re.S)
        if not match:
            raise unittest.SkipTest(
                "the probe never reported — no WebGL in this environment "
                f"(chromium exit {proc.returncode})")
        cls.result = json.loads(html.unescape(match.group(1)))
        if "skip" in cls.result:
            raise unittest.SkipTest(cls.result["skip"])
        # A viewer that boots but never finishes loading is a real failure,
        # and the page says which function it was still waiting for.
        if "error" in cls.result:
            raise AssertionError("accuracy probe: " + cls.result["error"])

    # ── helpers ──────────────────────────────────────────────────────────────

    def _case(self, name):
        return next(c for c in self.cases["plants"] if c["name"] == name)

    def _measured(self, name):
        for p in self.result["plants"]:
            if p["name"] == name:
                return p
        self.fail(f"{name}: the probe did not report it")

    def _florets(self, name):
        parts = [q for q in self._measured(name)["parts"]
                 if q.get("part") == "floret"]
        self.assertTrue(
            parts, f"{name}: no florets were built in month "
                   f"{self._case(name)['month']} — is that inside its bloom "
                   f"window, and does it still carry a flower_arch?")
        return parts

    def _drawn_height(self, name):
        """How tall the viewer draws the body (04-quality.js bodyHeightOf)."""
        p = self._case(name)["plant"]
        h = p["height_m"]
        if p["plant_type"] == "groundcover":
            return min(h, scene_wildlife.GROUNDCOVER_DRAWN_MAX_M)
        return max(0.08, h)

    def _bee(self, name):
        if not self.result["models"]:
            self.skipTest("the baked models did not load in this browser, and "
                          "the bands are painted on the baked bee")
        for b in self.result["bees"]:
            if b["name"] == name:
                self.assertTrue(b["built"], f"{name}: glbCritter built nothing")
                return b
        self.fail(f"{name}: the probe did not report it")

    # ── A1: a flower in a cluster is the size of a flower ────────────────────

    def test_a_cluster_is_drawn_from_flowers_of_their_own_size(self):
        for name in _CLUSTERS:
            dia = self._case(name)["plant"]["flower_diameter_cm"] / 100
            drawn = max(q["s_med"] for q in self._florets(name))
            with self.subTest(name):
                self.assertLessEqual(
                    drawn / dia, MAX_FLORET_OVER_RECORDED,
                    f"{name}: each floret is drawn {drawn * 100:.1f} cm across "
                    f"against a recorded {dia * 100:.1f} cm — the floret is "
                    f"being scaled by the whole inflorescence again")
                self.assertGreaterEqual(
                    drawn / dia, 0.5,
                    f"{name}: florets drawn at {drawn * 100:.2f} cm, half the "
                    f"recorded flower or less")

    def test_a_head_is_still_its_recorded_diameter(self):
        dia = self._case(_HEAD)["plant"]["flower_diameter_cm"] / 100
        drawn = max(q["s_med"] for q in self._florets(_HEAD))
        self.assertAlmostEqual(
            drawn / dia, 1.0, delta=0.1,
            msg=f"{_HEAD}: a head drawn {drawn * 100:.1f} cm across against a "
                f"recorded {dia * 100:.1f} cm. Heads were right before V2.88; "
                f"if this moved, so did the unit the probe measures in")

    def test_the_flowers_do_not_top_the_plant(self):
        for name in _CLUSTERS + (_HEAD,):
            h = self._drawn_height(name)
            top = max(q["top"] for q in self._florets(name))
            with self.subTest(name):
                self.assertLessEqual(
                    top, MAX_TOP_OVER_HEIGHT * h + TOP_SLACK_M,
                    f"{name}: flowers reach {top:.2f} m on a plant drawn "
                    f"{h:.2f} m tall ({top / h:.1f}x); a recorded height is to "
                    f"the top of the flowers")

    # ── A6: the flowers and the body agree on how tall the plant is ──────────

    def test_groundcover_flowers_sit_on_the_mat(self):
        cap = scene_wildlife.GROUNDCOVER_DRAWN_MAX_M
        top = max(q["top"] for q in self._florets(_GROUNDCOVER))
        self.assertLessEqual(
            top, MAX_TOP_OVER_HEIGHT * cap + TOP_SLACK_M,
            f"{_GROUNDCOVER}: flowers at {top:.2f} m over a mat drawn at most "
            f"{cap} m tall — they are floating at the recorded height again")

    def test_a_small_aquatic_is_drawn_near_its_own_height(self):
        want = self._case(_SMALL_AQUATIC)["plant"]["height_m"]
        got = self._measured(_SMALL_AQUATIC)["height_m"]
        self.assertGreater(got, 0, f"{_SMALL_AQUATIC}: nothing was built")
        self.assertLessEqual(
            got, 0.10,
            f"{_SMALL_AQUATIC}: recorded {want} m, drawn {got} m tall — the "
            f"0.5 m reed floor is back")

    # ── V2.89: vines on what they climb, horsetails as jointed stems ─────────

    def _group(self):
        case = self._case(_CLIMBER)
        vine = next(p for p in case["plants"] if p["plant_type"] == "vine")
        host = next(p for p in case["plants"] if p["plant_type"] != "vine")
        return vine, host

    def test_a_vine_beside_a_shrub_climbs_onto_it(self):
        vine, host = self._group()
        self.assertEqual(vine["drawn"]["habit"], "climbing")
        leaves = [q for q in self._measured(_CLIMBER)["parts"]
                  if q.get("part") == "vine"]
        self.assertTrue(leaves, f"{_CLIMBER}: no vine leaves were drawn")
        reach = vine["drawn"]["height_m"]
        top = max(q["top"] for q in leaves)
        self.assertGreaterEqual(
            top, 0.6 * reach,
            f"{_CLIMBER}: leaves stop at {top:.2f} m of a {reach} m climb — it "
            f"is lying at the foot of the {_HOST} instead of on it")
        self.assertLessEqual(top, reach + 0.2,
                             f"{_CLIMBER}: leaves at {top:.2f} m, above its "
                             f"{reach} m reach")
        # ON the shrub: the leaves reach in over the host's crown, not only
        # round the vine's own root outside it.
        inner = min(q["x0"] for q in leaves)
        self.assertLess(
            inner, host["x"] + host["canopy_m"] / 2 * 0.9,
            f"{_CLIMBER}: its leaves never reach in over the {_HOST}'s crown")

    def test_with_nothing_to_climb_a_vine_lies_low(self):
        # Every part, not only those tagged 'vine': the column this replaced
        # carried no such tag, so a leaves-only check reported it as "nothing
        # drawn" instead of as the column coming back.
        parts = self._measured(_SPRAWLER)["parts"]
        self.assertTrue(parts, f"{_SPRAWLER}: nothing was drawn")
        top = max(q["top"] for q in parts)
        self.assertLessEqual(
            top, vine_habit.SPRAWL_HEIGHT_M + 0.12,
            f"{_SPRAWLER}: alone, it stands {top:.2f} m tall — the free-standing "
            f"column is back")

    def test_horsetails_stand_at_their_recorded_height(self):
        for name in _HORSETAILS:
            want = self._case(name)["plant"]["height_m"]
            got = self._measured(name)["height_m"]
            with self.subTest(name):
                self.assertGreaterEqual(got / want, 0.85,
                                        f"{name}: {got} m against {want} m")
                self.assertLessEqual(got / want, 1.25,
                                     f"{name}: {got} m against {want} m")

    def test_a_horsetail_is_one_body_and_no_flower(self):
        """Two of them wore grass plumes until V2.89. A horsetail makes spores
        in a cone; nothing but its jointed stems should be drawn."""
        for name in _HORSETAILS:
            parts = self._measured(name)["parts"]
            with self.subTest(name):
                self.assertEqual(len(parts), 1,
                                 f"{name}: {len(parts)} parts drawn, expected "
                                 f"its stems alone")

    # ── V2.90: the pond ───────────────────────────────────────────────────────

    def _parts(self, name, part):
        return [q for q in self._measured(name)["parts"] if q.get("part") == part]

    def test_a_floating_leaf_lies_flat_where_there_is_no_pond(self):
        pads = self._parts(_FLOATING, "pond_pad")
        self.assertTrue(pads, f"{_FLOATING}: no floating leaves were drawn")
        top = max(q["top"] for q in pads)
        self.assertLessEqual(top, 0.03,
                             f"{_FLOATING}: its leaves reach {top:.2f} m, standing "
                             f"in the air where they should lie flat")
        canopy = self._case(_FLOATING)["plant"]["canopy_m"]
        self.assertGreaterEqual(max(q["w"] for q in pads), 0.6 * canopy,
                                f"{_FLOATING}: its pads cover a sliver of its "
                                f"{canopy} m spread")

    def test_in_a_pond_the_leaves_float_on_the_water(self):
        pads = self._parts(_IN_A_POND, "pond_pad")
        self.assertTrue(pads, f"{_IN_A_POND}: no floating leaves were drawn")
        base = min(q["base"] for q in pads)
        self.assertGreaterEqual(
            base, pond_habit.WATER_SURFACE_M - 0.002,
            f"{_IN_A_POND}: its leaves are at {base:.3f} m, under the pond's "
            f"opaque water at {pond_habit.WATER_SURFACE_M} m, so nothing shows")
        self.assertLessEqual(max(q["top"] for q in pads),
                             pond_habit.WATER_SURFACE_M + 0.03)

    def test_a_submerged_plant_shows_only_what_reaches_the_surface(self):
        parts = self._measured(_SUBMERGED)["parts"]
        self.assertTrue(parts, f"{_SUBMERGED}: nothing was drawn")
        top = max(q["top"] for q in parts)
        self.assertLessEqual(
            top, pond_habit.SUBMERGED_ABOVE_M + 0.05,
            f"{_SUBMERGED}: it stands {top:.2f} m tall in the open air, "
            f"which a submerged plant never does")
        self.assertTrue([q for q in parts if q.get("part") == "pond_sprig"],
                        f"{_SUBMERGED}: no shoot tips at the surface")

    def test_an_arrowhead_holds_its_leaves_on_stalks(self):
        want = self._case(_BROADLEAF)["plant"]["height_m"]
        leaves = self._parts(_BROADLEAF, "pond_leaf")
        stalks = self._parts(_BROADLEAF, "pond_stalk")
        self.assertTrue(leaves and stalks,
                        f"{_BROADLEAF}: drawn without its broad leaves on stalks")
        top = max(q["top"] for q in leaves)
        self.assertGreaterEqual(top / want, 0.85, f"{_BROADLEAF}: {top} of {want} m")
        self.assertLessEqual(top / want, 1.1, f"{_BROADLEAF}: {top} of {want} m")
        self.assertLessEqual(min(q["base"] for q in stalks), 0.02,
                             f"{_BROADLEAF}: its stalks float off the ground")

    def test_mares_tail_is_not_drawn_as_a_horsetail(self):
        """Common Mare's-tail is the plant horsetails are mistaken for. It has
        its own unit, which a count of variants that stopped at three would
        wrap straight back onto the scouring-rush's."""
        want = self._case(_MARES_TAIL)["plant"]["height_m"]
        got = self._measured(_MARES_TAIL)
        self.assertGreaterEqual(got["height_m"] / want, 0.85)
        self.assertLessEqual(got["height_m"] / want, 1.25)
        body = lambda name: max(q["verts"] for q in                 # noqa: E731
                                self._measured(name)["parts"])
        self.assertNotEqual(body(_MARES_TAIL), body("Common Scouring-rush"),
                            "Common Mare's-tail is drawn with the "
                            "scouring-rush's banded stems")

    # ── A4: the baked bee wears the recorded bands ───────────────────────────

    def test_the_recorded_bands_ring_the_baked_bee(self):
        bee = self._bee(_BANDED_BEE)
        app = next(b["app"] for b in self.cases["bees"]
                   if b["name"] == _BANDED_BEE)
        want = app["band_colours"]
        got = [t["colour"] for t in bee["tergites"]]
        self.assertEqual(
            len(got), len(want),
            f"{_BANDED_BEE}: {len(want)} tergite colours recorded, "
            f"{len(got)} rings drawn")
        for i, (g, w) in enumerate(zip(got, want), 1):
            self.assertTrue(_same_colour(g, w),
                            f"{_BANDED_BEE}: T{i} drawn {g}, recorded {w}")
        self.assertTrue(all(t["on_abdomen"] and t["visible"]
                            for t in bee["tergites"]),
                        "a ring is not a visible child of the Abdomen node, so "
                        "the build's abdomen rescale would not carry it")
        self.assertTrue(bee["bands"], "the baked bee lost its Band shells")
        self.assertFalse(any(b["visible"] for b in bee["bands"]),
                         "the generic thorax-coloured shells still show over "
                         "the recorded rings")
        self.assertTrue(bee["tip"] and _same_colour(bee["tip"], want[-1]),
                        f"the tip is {bee['tip']}, not the last band {want[-1]}")

    def test_a_bee_without_recorded_bands_keeps_its_shells(self):
        plain = [b for b in self.cases["bees"] if b["name"] != _BANDED_BEE]
        if not plain:
            self.skipTest("no catalogue bee has generic bands and no recorded "
                          "tergites any more")
        bee = self._bee(plain[0]["name"])
        self.assertEqual(bee["tergites"], [],
                         "rings were invented for a bee with nothing recorded")
        n = plain[0]["app"]["bands"]
        for b in bee["bands"]:
            self.assertEqual(b["visible"], b["i"] < n,
                             f"Band{b['i']} visibility is wrong for bands={n}")


def _same_colour(a, b, tol=2):
    """Hex colours equal to within a unit or two per channel: three.js keeps
    material colours in linear space, so the sRGB round trip may drift by one."""
    a, b = a.lstrip("#"), b.lstrip("#")
    return all(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) <= tol
               for i in (0, 2, 4))


class DrawnHeightIsOneNumberTest(unittest.TestCase):
    """The heights the flowers, fruit and animals use must be the height the body
    is DRAWN at. The groundcover body has been capped at 18 cm for a long time;
    the flowers were not told, and nine groundcovers had their flowers floating
    above the mat (V2.88). No browser needed; never skipped."""

    def test_the_groundcover_cap_is_one_number_on_both_sides(self):
        src = _read_js("04-quality.js")
        table = re.search(r"const _BODY_H = \{(.*?)\};", src, re.S)
        self.assertIsNotNone(table, "04-quality.js: the _BODY_H table moved")
        cap = re.search(r"groundcover:\s*\[\s*[\d.]+\s*,\s*([\d.]+)\s*\]",
                        table.group(1))
        self.assertIsNotNone(cap, "_BODY_H has no groundcover row")
        self.assertEqual(
            float(cap.group(1)), scene_wildlife.GROUNDCOVER_DRAWN_MAX_M,
            "the viewer's groundcover cap and scene_wildlife's disagree, so the "
            "animals perch at one height and the plant is drawn at another")

    def test_the_vine_sprawl_height_is_one_number_on_both_sides(self):
        m = re.search(r"const _VINE_SPRAWL_H = ([\d.]+);", _read_js("04-quality.js"))
        self.assertIsNotNone(m, "04-quality.js lost _VINE_SPRAWL_H")
        self.assertEqual(float(m.group(1)), vine_habit.SPRAWL_HEIGHT_M,
                         "the viewer lays a vine lower or higher than the "
                         "animals visiting it think it is")

    def test_flowers_and_fruit_read_the_drawn_height(self):
        for name in ("05-flowers.js", "11-fruit.js", "15-florets.js"):
            with self.subTest(name):
                # assertTrue, not assertIn: a miss would print the whole file.
                self.assertTrue(
                    "bodyHeightOf(p)" in _read_js(name),
                    f"{name} no longer asks bodyHeightOf how tall the plant is "
                    f"drawn, so its flowers or fruit can float over a capped body")


if __name__ == "__main__":
    unittest.main()
