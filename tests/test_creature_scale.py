"""
How big the animals are, how their bout is shaped, and what they cannot fly
through (V2.46).

Three reports, one increment:

    *"the relative size of the bees, butterflies, birds to the person that
    walks the scene is all wrong. The calligrapher bee seems to be the only one
    rendered smaller/more correctly."*

    *"The butterfly wings flap now but it is too fast and unnatural. A butterfly
    will flap-flap-glide… As it is the flapping is visually distracting."*

    *"The guy doesn't go through trees or buildings now but the creatures still
    do."*

The first two are testable as numbers. The third is testable as a contract —
that the collision function exists, is height-aware, exempts the animal's own
destination, and is actually *called* from the travel branches, which is the
part that was missing before (``walkObstacles`` existed all along and nothing
consulted it for wildlife).
"""

import json
import os
import pathlib
import re
import struct
import unittest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCENE3D = _ROOT / "html" / "scene3d"


def _js(name: str) -> str:
    return (_SCENE3D / name).read_text(encoding="utf-8")


def _code(name: str) -> str:
    """The file with comment-only lines removed, so a grep cannot be satisfied
    by the prose explaining the thing it is looking for."""
    return "\n".join(ln for ln in _js(name).splitlines()
                     if not ln.lstrip().startswith("//"))


class TestHowBigTheyAre(unittest.TestCase):
    """Life size comes from morphology, and the viewer measures rather than
    assumes."""

    def test_the_measurements_are_real_ones(self):
        from src.scene_wildlife import _size_for
        # A leafcutter bee: 11 mm, along the body axis.
        s = _size_for({"taxon": "bee"}, {"kind": "bee"},
                      bee_m={"body_length_mm": 11.0})
        self.assertAlmostEqual(s["m"], 0.011, places=4)
        self.assertEqual(s["axis"], "z")
        # A swallowtail: the wingspan band's midpoint, across the wings.
        s = _size_for({"taxon": "lepidoptera"}, {"kind": "butterfly"},
                      lep_m={"wingspan_min_mm": 70, "wingspan_max_mm": 90})
        self.assertAlmostEqual(s["m"], 0.080, places=4)
        self.assertEqual(s["axis"], "x")
        # A chickadee: wingspan, across the wings.
        s = _size_for({"taxon": "bird"}, {"kind": "bird"},
                      bird_m={"wingspan_mm": 203})
        self.assertAlmostEqual(s["m"], 0.203, places=4)
        self.assertEqual(s["axis"], "x")

    def test_no_measurement_still_gets_an_honest_size(self):
        """A creature with no morphology must not fall back to *nothing* — a
        zero or a missing key would make the viewer divide by it. It gets its
        kind's fallback, which is still far closer to life than the constant
        this replaced."""
        from src.scene_wildlife import _size_for, _SIZE_FALLBACK_M
        for kind, expect in _SIZE_FALLBACK_M.items():
            s = _size_for({"taxon": ""}, {"kind": kind})
            self.assertEqual(s["m"], expect, kind)
            self.assertGreater(s["m"], 0.0, kind)
            self.assertIn(s["axis"], ("x", "y", "z"), kind)

    def test_nothing_is_drawn_at_a_wildly_wrong_size(self):
        """The property that actually matters, stated as a bound: every
        creature the app can place is between 5 mm and 1.5 m. The old constants
        put an 11 mm bee at 0.54 m — a cat — and this is what would have caught
        that."""
        from src.scene_wildlife import _size_for, _SIZE_FALLBACK_M
        for kind in _SIZE_FALLBACK_M:
            m = _size_for({"taxon": ""}, {"kind": kind})["m"]
            self.assertTrue(0.005 <= m <= 1.5, f"{kind} at {m} m")

    def test_the_viewer_measures_the_model_instead_of_trusting_a_table(self):
        """`scaleCritterToLife` divides the wanted size by the model's OWN
        bounding-box extent. That is what makes one code path correct for both
        the baked GLBs and the procedural fallbacks, and what keeps it correct
        if a model is ever re-exported at a different size."""
        code = _code("07-wildlife.js")
        self.assertIn("function scaleCritterToLife", code)
        self.assertIn("Box3", code,
                      "the scale must be measured from the built object")
        self.assertIn("scaleCritterToLife(obj, spec.size)", code,
                      "rebuildWildlife no longer scales its critters")

    def test_life_size_is_the_default_and_the_exaggeration_is_named(self):
        """The magnifier is a stated exaggeration, not a vibe.

        Three properties, all of them the difference between this control and
        the constants it replaced: life size is first (and therefore the
        default index), nothing offered is *below* life size, and every option
        says by how much.
        """
        from src.scene3d_toolbar import CREATURE_SCALES
        self.assertEqual(CREATURE_SCALES[0][1], 1.0)
        self.assertIn("Life size", CREATURE_SCALES[0][0])
        for label, mult in CREATURE_SCALES:
            self.assertGreaterEqual(mult, 1.0, label)
            if mult != 1.0:
                self.assertIn(str(int(mult)), label,
                              f"{label!r} does not say how much it magnifies")

    def test_both_windows_offer_the_same_magnifications(self):
        """A second list here would be two windows that disagree about how big
        a bee is — the exact failure the V2.44 toolbar extraction exists to
        prevent."""
        src = (_ROOT / "src" / "scene3d_window.py").read_text(encoding="utf-8")
        self.assertIn("CREATURE_SCALES as _CREATURE_SCALES", src,
                      "the 3D preview has grown its own scale list")
        ref = (_ROOT / "src" / "reference_ecosystem_window.py").read_text(
            encoding="utf-8")
        self.assertIn("creature_scale_changed", ref)

    def test_the_magnifier_never_shrinks_below_life_size(self):
        """The exaggeration is a control with a number on it, and its floor is
        the truth: 1x. A magnifier that could go below life size would be a
        second way to get the old bug."""
        code = _code("07-wildlife.js")
        m = re.search(r"permaSetCreatureScale = function \(mult\) \{\s*"
                      r"const k = Math\.max\(([\d.]+), Math\.min\(([\d.]+)",
                      code)
        self.assertIsNotNone(m, "permaSetCreatureScale changed shape")
        self.assertEqual(float(m.group(1)), 1.0)
        self.assertLessEqual(float(m.group(2)), 20.0)

    def test_every_creature_a_scene_emits_carries_a_size(self):
        """End to end, against the shipped catalogue: no creature reaches the
        viewer without one, or the viewer falls back to the constant."""
        from src.db.plants import init_db, get_connection
        from src.scene_wildlife import wildlife_for_scene
        init_db()
        conn = get_connection()
        ids = [r[0] for r in conn.execute(
            "SELECT plant_id, COUNT(*) n FROM plant_fauna "
            "GROUP BY plant_id ORDER BY n DESC LIMIT 6").fetchall()]
        if not ids:                                # pragma: no cover
            self.skipTest("no plant_fauna edges seeded")
        scene = {
            "plants": [{"plant_id": p, "id": p, "x": i * 2.0, "y": 0.0,
                        "height_m": 1.5, "canopy_m": 1.2,
                        "plant_type": "shrub", "common_name": f"p{i}"}
                       for i, p in enumerate(ids)],
            "bounds": {"min_x": -5, "max_x": 25, "min_y": -5, "max_y": 5},
            "month": 7, "is_night": False,
        }
        creatures = wildlife_for_scene(scene)
        self.assertTrue(creatures, "no wildlife for a well-connected scene")
        for c in creatures:
            size = c.get("size") or {}
            self.assertTrue(0.005 <= size.get("m", 0) <= 1.5,
                            f"{c.get('name')} at {size}")
            self.assertIn(size.get("axis"), ("x", "y", "z"), c.get("name"))

    #: Assembled extents of the shipped fauna GLBs, per build, as measured at
    #: V2.46 — the evidence ``_SIZE_AXIS`` was chosen from.
    #:
    #: The lep row is the clearest case for it: X runs 1.07 (skipper) → 1.72
    #: (swallowtail), which is exactly how those animals' *wingspans* compare,
    #: while Z barely moves. So X is the wingspan axis.
    _MEASURED = {
        "bee": {"round": (1.683, 2.790), "stout": (1.715, 2.824),
                "slender": (1.748, 2.851), "leafcutter": (1.726, 2.860)},
        "lep": {"butterfly": (1.564, 1.420), "moth": (1.433, 1.420),
                "skipper": (1.075, 1.420), "swallowtail": (1.722, 1.495)},
        "bird": {"passerine": (0.540, 0.826), "woodpecker": (0.540, 0.986),
                 "hummer": (0.540, 0.887)},
        "fly": {"hover": (0.524, 0.357), "darner": (0.860, 0.685)},
    }

    def test_the_models_still_have_the_shape_the_axis_was_chosen_from(self):
        """A characterisation test, and deliberately only that.

        ``_SIZE_AXIS`` is a *judgment* — "a bee's length runs down Z, a
        butterfly's wingspan across X" — read off these models. No assertion
        can re-derive that judgment from geometry (the skipper build is longer
        along Z than its own wingspan, and would fail a naive "the named axis
        is the longest" rule while still being correct). What a test *can* do
        is fail the moment the evidence changes: re-export a model at a
        different aspect and this says so, with a pointer to re-check the
        choice rather than silently drawing every butterfly by its body.
        """
        models = _ROOT / "html" / "assets" / "models"
        if not models.exists():                    # pragma: no cover
            self.skipTest("model assets not present in this checkout")
        drift = []
        for key, builds in self._MEASURED.items():
            glb = models / f"fauna_{key}.glb"
            if not glb.exists():                   # pragma: no cover
                continue
            got = _glb_variant_extents(glb)
            for build, (want_x, want_z) in builds.items():
                ext = got.get(build)
                if ext is None:
                    drift.append(f"fauna_{key}.glb lost its '{build}' build")
                    continue
                for axis, want in (("x", want_x), ("z", want_z)):
                    if abs(ext[axis] - want) > 0.02:
                        drift.append(
                            f"fauna_{key}.glb/{build} {axis}: {ext[axis]:.3f} "
                            f"was {want:.3f}")
        self.assertFalse(
            drift,
            "a fauna model was re-exported at a different shape — re-check "
            "src/scene_wildlife._SIZE_AXIS against it:\n  "
            + "\n  ".join(drift))

    def test_the_bird_is_measured_across_the_wings_not_along_the_tail(self):
        """Birds are the case where the long axis is the WRONG one.

        ``fauna_bird.glb`` is authored with a generous body-plus-tail down Z —
        longer than the wingspan across X. Scaling by the long axis would draw
        every songbird at its tail length, which is not a published
        measurement and not what ``bird_morphology.wingspan_mm`` means. So this
        pins the deliberate choice rather than letting it look like an
        oversight somebody should "fix"."""
        models = _ROOT / "html" / "assets" / "models"
        glb = models / "fauna_bird.glb"
        if not glb.exists():                       # pragma: no cover
            self.skipTest("model assets not present in this checkout")
        from src.scene_wildlife import _SIZE_AXIS
        self.assertEqual(_SIZE_AXIS["bird"], "x")
        variants = _glb_variant_extents(glb)
        self.assertTrue(variants, "fauna_bird.glb has no measurable variants")
        for name, ext in variants.items():
            # The wingspan axis must at least be a real span — not a token
            # width — even where the tail axis is longer.
            self.assertGreater(ext["x"], ext["y"],
                               f"{name}: X is not the span axis ({ext})")


class TestFlapFlapGlide(unittest.TestCase):
    """The bout, and the thing that makes a glide a glide."""

    def test_a_butterfly_gets_a_butterflys_bout_not_a_crows(self):
        """The fault: butterflies shared ``FLAP_GLIDE`` with corvids, so they
        got 3-8 beats and a quarter-second pause — a near-continuous flutter."""
        from src.flight_model import (lepidoptera_flight, FLAP_GLIDE,
                                      FLUTTER_GLIDE, SAIL)
        f = lepidoptera_flight(45, kind="butterfly", flight_style="fluttery")
        self.assertEqual(f["style"], FLUTTER_GLIDE)
        self.assertNotEqual(f["style"], FLAP_GLIDE)
        f = lepidoptera_flight(100, kind="butterfly", flight_style="gliding")
        self.assertEqual(f["style"], SAIL)

    def test_the_glide_is_longer_than_the_burst(self):
        """"Flap-flap-glide" is a claim about the RATIO, so that is what is
        tested: for every butterfly style, more of the cycle is spent gliding
        than beating."""
        from src.flight_model import lepidoptera_flight, animation_hz
        for style, span in (("fluttery", 45), ("erratic", 25),
                            ("bobbing", 70), ("gliding", 100)):
            f = lepidoptera_flight(span, kind="butterfly", flight_style=style)
            hz = animation_hz(f["hz"]["mid"])
            burst_s = f["burst_beats"]["mid"] / hz
            pause_s = f["pause_s"]["mid"]
            self.assertGreater(
                pause_s, burst_s,
                f"{style}: {burst_s:.2f}s of beating vs {pause_s:.2f}s glide "
                f"— that is a flutter, not a flap-flap-glide")

    def test_a_sailing_butterfly_beats_only_a_few_times(self):
        """Two to four beats, literally. A number this specific is worth
        pinning: it is the author's own description of the motion."""
        from src.flight_model import lepidoptera_flight
        f = lepidoptera_flight(100, kind="butterfly", flight_style="gliding")
        self.assertTrue(2 <= f["burst_beats"]["lo"] <= 4, f["burst_beats"])
        self.assertTrue(2 <= f["burst_beats"]["hi"] <= 5, f["burst_beats"])
        self.assertGreaterEqual(f["pause_s"]["hi"], 2.0,
                                "a monarch's glide is seconds, not tenths")

    def test_the_bird_bouts_are_untouched(self):
        """The lep split must not have moved a bird. A bounding chickadee's
        bout is measured and stays exactly where V2.45 put it."""
        from src.flight_model import bird_flight, BOUNDING
        f = bird_flight(11, 203, style=BOUNDING)
        self.assertEqual(f["style"], BOUNDING)
        self.assertEqual((f["burst_beats"]["lo"], f["burst_beats"]["hi"]),
                         (4, 9))

    def test_the_wings_go_still_in_the_glide_rather_than_trembling(self):
        """The other half of "too fast and unnatural".

        ``beatGain`` used to bottom out at 0.22 for gliding styles, which means
        the wings kept beating at 22% of full sweep **at full rate** — a rapid
        shiver, the least butterfly-like thing a butterfly can do. The V is now
        a HELD POSE (``fp.hold``), so a gain of 0 really is a stopped wing.
        """
        gain = _code("18-flight.js")
        self.assertNotIn("0.22", gain,
                         "beatGain is floor-ing the amplitude again instead "
                         "of holding a pose")
        wild = _code("07-wildlife.js")
        self.assertIn("fp.hold", wild,
                      "flapWings no longer interpolates toward a held pose")
        # And the held pose must be a shallow V *above* the bottom of the
        # stroke, not `base` — parking a sailing monarch at the bottom of its
        # downstroke reads as a dead butterfly.
        for name in ("06-fly.js", "09-models.js"):
            src = _code(name)
            for m in re.finditer(r"base:\s*(-?[\d.]+),\s*amp:\s*([\d.]+)"
                                 r"[^}]*hold:\s*(-?[\d.]+)", src):
                base, amp, hold = (float(g) for g in m.groups())
                self.assertGreater(hold, base,
                                   f"{name}: hold {hold} is at or below the "
                                   f"bottom of the stroke {base}")
                self.assertLessEqual(hold, base + amp,
                                     f"{name}: hold {hold} is outside the "
                                     f"stroke ({base}..{base + amp})")


class TestCreaturesHitThings(unittest.TestCase):
    """"The guy doesn't go through trees or buildings now but the creatures
    still do." """

    def test_there_is_a_critter_obstacle_list_and_it_has_heights(self):
        code = _code("08-modes.js")
        self.assertIn("function buildCritterObstacles", code)
        self.assertIn("top:", code,
                      "critter obstacles need a height — a bird over the roof "
                      "is not colliding with it")
        self.assertIn("pos.y > o.top", code,
                      "the height gate is gone: everything now bounces off "
                      "buildings it is legitimately above")

    def test_a_creature_can_still_reach_the_plant_it_was_sent_to(self):
        """The trap this fix could have walked into: a chickadee's whole route
        is *perch in that tree*. Blanket collision would push it out of every
        tree it was sent to and leave it circling the trunk forever."""
        code = _code("08-modes.js")
        self.assertIn("if (target)", code,
                      "resolveCritterCollision no longer exempts the "
                      "creature's own destination")

    def test_the_travel_branches_actually_call_it(self):
        """The bug was never a missing function — ``walkObstacles`` existed all
        along. It was that nothing in ``animateWildlife`` consulted it. Both
        travel branches must call the resolver, or half the animals still fly
        through the house."""
        code = _code("07-wildlife.js")
        self.assertEqual(
            code.count("resolveCritterCollision(c.pos"), 2,
            "expected the perch branch AND the generic branch to resolve "
            "collisions against the path")

    def test_the_obstacles_are_rebuilt_outside_walk_mode_too(self):
        """`buildWalkObstacles` is called only while walking, which is right
        for the walker and wrong for the wildlife: the animals fly in the orbit
        view, and that is where you watch them."""
        code = _code("05-flowers.js")
        self.assertIn("buildCritterObstacles()", code)
        self.assertNotIn("if (walkMode) buildCritterObstacles", code,
                         "the critter obstacles are gated on walk mode again")


class TestTheNetIsHeld(unittest.TestCase):
    """"I want to be able to … catch a bug in a net the guy holds." """

    def test_the_walker_carries_one(self):
        code = _code("08-modes.js")
        self.assertIn("function makeNet", code)
        self.assertIn("g.userData.net", code,
                      "the net is not attached to the walker")
        self.assertIn("rightArm.pivot.add(net)", code,
                      "the net must hang off the ARM PIVOT so the walk cycle "
                      "carries it for free")

    def test_it_has_a_reach_and_the_miss_is_reported(self):
        """A held net has a reach — that is the whole difference between a net
        and a cursor. A miss has to reach the user, or the click just looks
        broken."""
        code = _code("08-modes.js")
        m = re.search(r"NET_REACH_M = ([\d.]+)", code)
        self.assertIsNotNone(m, "the net's reach is gone")
        self.assertTrue(1.0 <= float(m.group(1)) <= 5.0,
                        "an arm's reach with a net is metres, not tens")
        edit = _code("16-editing.js")
        self.assertIn("outOfReach", edit,
                      "a swing that misses says nothing to the user")

    def test_the_bridge_carries_the_miss(self):
        """The JS calls ``bridge.outOfReach``; the slot has to exist under
        exactly that name or the call is a silent no-op (QWebChannel does not
        raise for a missing slot from a guarded call)."""
        src = (_ROOT / "src" / "map3d_widget.py").read_text(encoding="utf-8")
        self.assertIn("def outOfReach(", src)
        self.assertIn("out_of_reach = pyqtSignal(str)", src)

    def test_the_net_survives_the_walker_being_built_late(self):
        """The walker is created lazily on entering walk mode, so the Net verb
        can be switched on before he exists. Re-reading the verb at that point
        is what stops an invisible net."""
        code = _code("08-modes.js")
        self.assertIn("__permaEditVerb", code,
                      "enterWalkMode no longer re-reads the edit verb, so a "
                      "net armed before walking will not appear")


class TestTheDesignCanBeEditedToo(unittest.TestCase):
    """"I want the 3D view and the tour a reference ecosystem to have the same
    functionality." """

    def test_the_design_window_has_the_same_three_verbs(self):
        from src.scene3d_edit_flow import _TOOLS
        self.assertEqual([t[0] for t in _TOOLS], ["plant", "pull", "net"])

    def test_a_design_edit_goes_through_the_undo_stack_and_the_store(self):
        """The reason this is a separate module from ``reference_edit_flow``:
        a sandbox edit is a throwaway, a design edit is the user's real
        project. It must be undoable, must go through ``ProjectStore`` (the
        single write path), and must redraw the map."""
        src = (_ROOT / "src" / "scene3d_edit_flow.py").read_text(
            encoding="utf-8")
        for needle in ("_push_undo", "store_for(main)",
                       "render_project_to_map", "_sync_planning_panel"):
            self.assertIn(needle, src, f"a design edit skips {needle}")

    def test_a_removal_reverses_through_a_snapshot_not_a_made_up_action(self):
        """`_do_undo` dispatches on ``entry["action"]`` through a registered
        handler table. ``place_plant`` is in it; a removal is not — it reverses
        through the generic before/after snapshot that ``@undoable`` uses.

        Pushing an unregistered action name would look right in the code, put
        an entry on the stack, enable the Undo menu item, and then undo
        *nothing* when pressed. This is the test that would catch that."""
        from src.controllers.persistence import PersistenceController
        handlers = getattr(PersistenceController, "_HANDLERS", {})
        self.assertIn("place_plant", handlers)
        src = (_ROOT / "src" / "scene3d_edit_flow.py").read_text(
            encoding="utf-8")
        for m in re.finditer(r'_push_undo\(\{\s*\n?\s*"action":\s*"([^"]+)"',
                             src):
            self.assertIn(m.group(1), handlers,
                          f"{m.group(1)!r} has no undo handler — that entry "
                          f"would enable Undo and then do nothing")
        self.assertIn('_checkpoint(main, "remove plant")', src,
                      "the removal no longer takes a snapshot checkpoint")

    def test_it_does_not_carry_a_second_species_picker(self):
        """Picking a plant in one place and planting it in another is one
        decision. Two pickers that can disagree is how somebody plants a
        species they did not choose."""
        src = (_ROOT / "src" / "scene3d_window.py").read_text(encoding="utf-8")
        self.assertIn("plant_panel.selected_plant()", src)
        from src.plant_panel import PlantPanel
        self.assertTrue(callable(getattr(PlantPanel, "selected_plant", None)),
                        "PlantPanel.selected_plant() is the public accessor "
                        "the 3D window depends on")

    def test_editing_degrades_when_there_is_no_bridge(self):
        """The web3d/dist fork build has no QWebChannel. Editing must disable
        itself rather than raise — the window still previews the design, which
        is what it did before V2.46."""
        import types
        from src import scene3d_edit_flow as flow
        win = types.SimpleNamespace(viewer=types.SimpleNamespace(bridge=None))
        self.assertFalse(flow.connect_bridge(win))

    def test_a_click_with_no_scene_origin_declines_rather_than_guessing(self):
        import types
        from src import scene3d_edit_flow as flow
        self.assertIsNone(flow.scene_center(types.SimpleNamespace()))
        self.assertIsNone(flow.scene_center(
            types.SimpleNamespace(_last_origin={"lat": None})))


def _glb_variant_extents(path: pathlib.Path) -> dict:
    """``{variant name: {'x','y','z'}}`` — each top-level node's ASSEMBLED
    bounding box, in the frame the viewer's ``Box3.setFromObject`` would
    measure.

    The node transforms are the whole point. A first cut of this unioned the
    raw accessor min/max and reported a bird 0.38 m across, because a wing's
    *geometry* is small and its span comes from the translation on its node.
    That would have "confirmed" the wrong axis. Multi-variant files also stack
    their builds in one document, so each root is measured separately or the
    union is a shape no animal has.
    """
    data = path.read_bytes()
    off, doc = 12, None
    while off < len(data):
        clen, ctype = struct.unpack_from("<II", data, off)
        if ctype == 0x4E4F534A:                    # 'JSON'
            doc = json.loads(data[off + 8:off + 8 + clen].decode("utf-8"))
            break
        off += 8 + clen + ((4 - clen % 4) % 4)
    if not doc:                                    # pragma: no cover
        return {}
    nodes = doc.get("nodes", [])
    accs = doc.get("accessors", [])
    meshes = doc.get("meshes", [])

    def trs(node):
        """The node's local matrix, row-major 4x4 as nested lists."""
        if "matrix" in node:                       # column-major in glTF
            m = node["matrix"]
            return [[m[0], m[4], m[8], m[12]], [m[1], m[5], m[9], m[13]],
                    [m[2], m[6], m[10], m[14]], [m[3], m[7], m[11], m[15]]]
        t = node.get("translation", [0, 0, 0])
        r = node.get("rotation", [0, 0, 0, 1])     # xyzw
        s = node.get("scale", [1, 1, 1])
        x, y, z, w = r
        rot = [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
        return [[rot[i][j] * s[j] for j in range(3)] + [t[i]] for i in range(3)] \
            + [[0, 0, 0, 1]]

    def mul(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
                for i in range(4)]

    def apply(m, p):
        return [m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3]
                for i in range(3)]

    out = {}
    for root_i in (doc.get("scenes") or [{}])[0].get("nodes", []):
        lo, hi = [float("inf")] * 3, [float("-inf")] * 3

        def walk(i, parent):
            node = nodes[i]
            m = mul(parent, trs(node))
            if "mesh" in node:
                for prim in meshes[node["mesh"]].get("primitives", []):
                    acc = accs[prim["attributes"]["POSITION"]]
                    a, b = acc["min"], acc["max"]
                    # All eight corners, because a rotation on the node makes
                    # the axis-aligned min/max wrong on their own.
                    for cx in (a[0], b[0]):
                        for cy in (a[1], b[1]):
                            for cz in (a[2], b[2]):
                                p = apply(m, [cx, cy, cz])
                                for k in range(3):
                                    lo[k] = min(lo[k], p[k])
                                    hi[k] = max(hi[k], p[k])
            for c in node.get("children", []):
                walk(c, m)

        ident = [[1 if i == j else 0 for j in range(4)] for i in range(4)]
        walk(root_i, ident)
        if lo[0] == float("inf"):                  # pragma: no cover
            continue
        out[nodes[root_i].get("name", f"node{root_i}")] = {
            "x": hi[0] - lo[0], "y": hi[1] - lo[1], "z": hi[2] - lo[2]}
    return out


if __name__ == "__main__":                         # pragma: no cover
    unittest.main()
