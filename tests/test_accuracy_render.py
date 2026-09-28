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
#: V2.93: the succulents. Pads with the flowers on them, a spiny ball, the
#: yucca's swords and its flower stalks (and none in January), roseroot's leafy
#: stems, the stonecrop's mat.
_PADS, _SMALL_PADS = "Plains Prickly Pear Cactus", "Brittle Prickly-pear"
_BALL, _YUCCA = "Ball Cactus", "Soapweed Yucca"
_FLESHY, _STONECROP = "Roseroot", "Lance-leaved Stonecrop"
_SUCCULENTS = (_PADS, _SMALL_PADS, _BALL, _YUCCA, _FLESHY, _STONECROP)
_YUCCA_IN_WINTER = _YUCCA + " in January"
#: V2.94 (F186): broad-leaved crowns seen at a person's eye height from the side
#: away from the sun, under the scene's own default sun. V2.93 drew 38-41% of
#: their pixels near-black, and V2.94 about 2-6%.
_IN_LIGHT = ("Trembling Aspen", "Paper Birch")
MAX_SHADED_NEAR_BLACK = 0.15
MIN_SHADED_LUMA = 0.25
#: The sunny side stays the brighter one, and a blown-out leaf would read white.
MAX_SUNNY_LUMA = 0.6
#: V2.97 (F174): a bird of each body plan, with the plant the scene puts it on.
#: Every bird was drawn about 2.4 times its length until V2.97.
_BIRDS = (("American Robin", "Black Hawthorn"),
          ("Black-capped Chickadee", "Chokecherry"),
          ("Red-tailed Hawk", "Balsam Poplar"),
          ("Great Horned Owl", "Trembling Aspen"),
          ("Ruffed Grouse", "Bearberry"),
          ("Snow Goose", "Saltgrass"),
          ("Sandhill Crane", "Broad-leaved Arrowhead"))
_NIGHT_BIRDS = ("Great Horned Owl",)
#: V2.96 (F188): shrubs seen from above as drawn, against the same frame with
#: their leaves' colour attribute made white. Until V2.96 the two were the same
#: picture, because the shrub layer asked for its leaves with vertex colours off.
#: The shade takes about a quarter of the brightness from above; the old bake,
#: switched on as it was, took about half.
_SHADED_SHRUBS = ("Western Snowberry", "Red Osier Dogwood")
_FROM_ABOVE = " from above"
MAX_DRAWN_OVER_WHITE = 0.95
MIN_DRAWN_OVER_WHITE = 0.6

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
                                 _FLOATING, _SUBMERGED, _BROADLEAF,
                                 _MARES_TAIL) + _SUCCULENTS:
        plant = built(feature(name))[0]
        plants.append({"name": name, "month": _bloom_month(plant),
                       "plant": plant})
    plants.append({"name": _YUCCA_IN_WINTER, "month": 1,
                   "plant": built(feature(_YUCCA))[0]})
    # V2.94: each tree alone in July under the sun build_scene gives a scene
    # (21 June, 13:00), with bounds wide enough for the shadow map to cover it.
    # V2.96: the shrubs whose shade is photographed from above, the same way.
    def in_july(name, case_name, **flag):
        sc = scene_of(feature(name))
        plant = sc["plants"][0]
        half = max(6.0, plant["height_m"] * 1.3, plant["canopy_m"] * 1.3)
        plants.append(dict({"name": case_name, "month": 7, "year": 0,
                            "plant": plant, "sun": sc["sun"],
                            "bounds": {"min_x": -half, "min_y": -half,
                                       "max_x": half, "max_y": half}}, **flag))

    for name in _IN_LIGHT:
        in_july(name, name, light=True)
    for name in _SHADED_SHRUBS:
        in_july(name, name + _FROM_ABOVE, shade=True)
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

    # V2.97 (F174): each bird alone with a plant it is tied to, through
    # wildlife_for_scene; the probe gets the appearance and size it returns.
    from src.db.fauna import fauna_for_plants
    conn = get_connection()
    try:
        bird_ids = {r["common_name"]: r["id"] for r in conn.execute(
            "SELECT id, common_name FROM fauna WHERE taxon = 'bird'")}
    finally:
        conn.close()
    bird_cases = []
    for bird, plant_name in _BIRDS:
        sc = scene_of(feature(plant_name))
        sc["month"], sc["is_night"] = 7, bird in _NIGHT_BIRDS
        fid = bird_ids[bird]
        crit = scene_wildlife.wildlife_for_scene(
            sc, fauna_edges=lambda pids, fid=fid: [
                r for r in fauna_for_plants(pids) if r.get("id") == fid])[0]
        bird_cases.append({"name": bird, "app": crit["app"], "size": crit["size"]})
    return {"plants": plants, "bees": bee_cases, "birds": bird_cases}


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

    # ── V2.93: succulents and cacti ──────────────────────────────────────────

    def _drawn(self, name):
        return self._case(name)["plant"]["drawn"]

    def test_a_prickly_pear_is_pads_with_its_flowers_on_them(self):
        """Both were the groundcover mat's star of narrow blades, and Brittle
        Prickly-pear's flowers floated at 1.4x the plant."""
        for name in (_PADS, _SMALL_PADS):
            h = self._drawn(name)["height_m"]
            pads, spines = self._parts(name, "succ_pad"), self._parts(name, "succ_spine")
            with self.subTest(name):
                self.assertTrue(pads and spines,
                                f"{name}: drawn without its pads and spines")
                top = max(q["top"] for q in pads)
                self.assertGreaterEqual(top, 0.6 * h, f"{name}: pads reach "
                                        f"{top:.2f} m of {h} m")
                self.assertLessEqual(top, h, f"{name}: pads above the plant")
                fl = max(q["top"] for q in self._florets(name))
                self.assertLessEqual(
                    fl, MAX_TOP_OVER_HEIGHT * h + TOP_SLACK_M,
                    f"{name}: flowers at {fl:.2f} m over a {h} m plant")
                self.assertGreaterEqual(fl, 0.75 * top,
                                        f"{name}: the flowers are sunk in the clump")

    def test_a_ball_cactus_is_a_cluster_of_spiny_globes(self):
        d = self._drawn(_BALL)
        balls, spines = self._parts(_BALL, "succ_ball"), self._parts(_BALL, "succ_spine")
        self.assertTrue(balls and spines, f"{_BALL}: no spiny globes")
        self.assertEqual(sum(q["n"] for q in balls), d["stems"])
        top = max(q["top"] for q in balls)
        self.assertAlmostEqual(top / d["ball_m"], 1.0, delta=0.15)
        fl = max(q["top"] for q in self._florets(_BALL))
        self.assertLessEqual(fl, MAX_TOP_OVER_HEIGHT * d["height_m"] + TOP_SLACK_M)
        self.assertGreaterEqual(fl, 0.8 * top, f"{_BALL}: no flowers at the crown")

    def test_a_yucca_is_swords_with_its_flowers_on_stalks(self):
        """It was a leafy bush with its flowers scattered inside it."""
        d = self._drawn(_YUCCA)
        swords, stalks = self._parts(_YUCCA, "succ_sword"), self._parts(_YUCCA, "succ_stalk")
        self.assertTrue(swords and stalks, f"{_YUCCA}: no sword leaves or stalks")
        leaf_top = max(q["top"] for q in swords)
        self.assertGreaterEqual(leaf_top, 0.7 * d["leaf_m"])
        self.assertLessEqual(leaf_top, d["leaf_m"] + 0.02)
        self.assertAlmostEqual(max(q["top"] for q in stalks) / d["height_m"], 1.0,
                               delta=0.03)
        self.assertEqual(sum(q["n"] for q in stalks), d["stalks"])
        fl = self._florets(_YUCCA)
        self.assertLessEqual(max(q["top"] for q in fl),
                             1.05 * d["height_m"] + TOP_SLACK_M)
        self.assertGreaterEqual(min(q["base"] for q in fl), 0.6 * leaf_top,
                                f"{_YUCCA}: flowers down among the leaves")

    def test_in_january_the_yucca_has_no_flower_stalk(self):
        self.assertTrue(self._parts(_YUCCA_IN_WINTER, "succ_sword"),
                        f"{_YUCCA}: no leaves in January; it is evergreen")
        self.assertFalse(self._parts(_YUCCA_IN_WINTER, "succ_stalk"),
                         f"{_YUCCA}: a flower stalk standing in January")

    def test_roseroot_is_leafy_stems_with_the_flowers_on_top(self):
        d = self._drawn(_FLESHY)
        stems, leaves = self._parts(_FLESHY, "succ_stem"), self._parts(_FLESHY, "succ_leaf")
        self.assertTrue(stems and leaves, f"{_FLESHY}: no leafy stems")
        self.assertEqual(sum(q["n"] for q in stems), d["stems"])
        self.assertGreaterEqual(max(q["top"] for q in stems) / d["height_m"], 0.85)
        fl = max(q["top"] for q in self._florets(_FLESHY))
        self.assertGreaterEqual(fl, 0.9 * d["height_m"])
        self.assertLessEqual(fl, MAX_TOP_OVER_HEIGHT * d["height_m"] + TOP_SLACK_M)

    def test_a_stonecrop_is_a_mat_under_its_flowering_stems(self):
        d = self._drawn(_STONECROP)
        stems, leaves = self._parts(_STONECROP, "succ_stem"), self._parts(_STONECROP, "succ_leaf")
        self.assertTrue(stems and leaves, f"{_STONECROP}: no fleshy shoots")
        self.assertGreater(sum(q["n"] for q in stems), d["stems"],
                           f"{_STONECROP}: its flowering stems with no mat under them")
        self.assertGreaterEqual(max(q["w"] for q in leaves), 0.8 * d["canopy_m"],
                                f"{_STONECROP}: the mat covers a sliver of its ground")

    # ── V2.94: a crown seen from its shaded side is not a silhouette ────────

    def _light(self, name):
        if not self.result["models"]:
            self.skipTest("the baked models did not load in this browser, and "
                          "the thresholds were set on the baked crowns")
        light = self._measured(name).get("light")
        self.assertIsNotNone(light, f"{name}: the probe took no light reading")
        return light

    def test_a_crown_seen_from_its_shaded_side_is_not_a_silhouette(self):
        """A leaf card faces the sky, so from a path you see undersides. Until
        V2.94 an underside took no sun, and the bake darkened what light it had
        twice over: more than half of every crown was near-black from 1.6 m,
        green from above, which is how the audit saw it."""
        for name in _IN_LIGHT:
            shaded = self._light(name)["shaded"]
            with self.subTest(name):
                self.assertGreater(shaded["px"], 2000,
                                   f"{name}: the crown barely shows in the frame")
                self.assertLess(
                    shaded["dark"], MAX_SHADED_NEAR_BLACK,
                    f"{name}: {shaded['dark']:.0%} of the crown is near-black "
                    f"from the side away from the sun. Are the leaves letting "
                    f"light through (01c-leaves.js), and is the bake on the sky "
                    f"only?")
                self.assertGreater(shaded["luma"], MIN_SHADED_LUMA,
                                   f"{name}: the crown averages "
                                   f"{shaded['luma']:.2f} from its shaded side")

    def test_the_sunny_side_is_still_the_brighter_one(self):
        """Light through a leaf is less than light on it, and a leaf that lets
        light through must not glow white."""
        for name in _IN_LIGHT:
            light = self._light(name)
            with self.subTest(name):
                self.assertGreater(light["sunny"]["luma"], light["shaded"]["luma"],
                                   f"{name}: brighter from the shaded side than "
                                   f"from the sunny one")
                self.assertLess(light["sunny"]["luma"], MAX_SUNNY_LUMA,
                                f"{name}: the sunlit crown averages "
                                f"{light['sunny']['luma']:.2f}, washed out")

    # ── V2.96: a shrub draws the shade baked into it ─────────────────────────

    def test_a_shrub_draws_the_shade_baked_into_it(self):
        """Every shrub model carries a baked shade, and until V2.96 none was
        drawn: the shrub layer asked for its leaf material with vertex colours
        off, so whitening the colours changed nothing on screen (F188). Seen
        from above, where a flat-lit shrub reads as a cut-out."""
        if not self.result["models"]:
            self.skipTest("the baked models did not load in this browser, and "
                          "the bounds were set on the baked shrubs")
        for name in _SHADED_SHRUBS:
            shade = self._measured(name + _FROM_ABOVE).get("shade")
            with self.subTest(name):
                self.assertIsNotNone(shade, f"{name}: the probe took no shade reading")
                drawn, white = shade["drawn"], shade["white"]
                self.assertGreater(drawn["px"], 2000,
                                   f"{name}: the shrub barely shows in the frame")
                ratio = drawn["luma"] / white["luma"]
                self.assertLessEqual(
                    ratio, MAX_DRAWN_OVER_WHITE,
                    f"{name}: {drawn['luma']:.3f} as drawn, {white['luma']:.3f} "
                    f"with its colours whitened, so its shade is not drawn. Does "
                    f"the shrub layer ask surfaceMaterial for vertex colours?")
                self.assertGreaterEqual(
                    ratio, MIN_DRAWN_OVER_WHITE,
                    f"{name}: its shade takes {1 - ratio:.0%} of its brightness "
                    f"from above. Is it baked with CROWN_AO (build_all.py)?")

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

    # ── V2.97 (F174): a bird is drawn at its own size ────────────────────────

    def _bird(self, name):
        if not self.result["models"]:
            self.skipTest("the baked models did not load in this browser, and "
                          "the builds are the baked birds")
        for b in self.result.get("birds", []):
            if b["name"] == name:
                self.assertTrue(b["built"], f"{name}: glbCritter built nothing")
                return b
        self.fail(f"{name}: the probe did not report it")

    def test_a_bird_is_as_wide_as_its_recorded_wingspan(self):
        for case in self.cases["birds"]:
            want = case["size"]["m"]
            with self.subTest(case["name"]):
                self.assertAlmostEqual(
                    self._bird(case["name"])["span_m"], want, delta=0.02 * want,
                    msg="the scaling no longer measures the spread wings")

    def test_a_bird_is_drawn_near_its_published_length(self):
        """The number V2.46 never checked: the length that comes with the width
        it set. The robin was 52 cm, the crane three metres."""
        from tests.test_bird_body_plan import (PUBLISHED_LENGTH_CM,
                                               PUBLISHED_STANDING_CM, SLACK)
        for name, _plant in _BIRDS:
            b = self._bird(name)
            lo, hi = PUBLISHED_LENGTH_CM[name]
            with self.subTest(name):
                cm = b["length_m"] * 100
                if name in PUBLISHED_STANDING_CM:     # upright: its height
                    lo, hi = PUBLISHED_STANDING_CM[name]
                    cm = b["height_m"] * 100
                self.assertGreaterEqual(cm, lo * (1 - SLACK),
                                        f"{name} drawn {cm:.1f} cm")
                self.assertLessEqual(cm, hi * (1 + SLACK),
                                     f"{name} drawn {cm:.1f} cm (published "
                                     f"{lo}-{hi} cm)")

    def test_a_settled_bird_folds_its_wings(self):
        for name, _plant in _BIRDS:
            with self.subTest(name):
                self.assertTrue(self._bird(name)["folded"],
                                f"{name}: the spread wings still show at rest, "
                                f"or the folded pair is missing")


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
