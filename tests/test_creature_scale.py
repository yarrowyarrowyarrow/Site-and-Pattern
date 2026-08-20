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


def _all_code() -> str:
    """Every viewer chunk's code, concatenated.

    For properties that are about *the viewer* rather than about a particular
    file — "the walker carries a net" is true regardless of which chunk builds
    him. Naming a file in those assertions makes them break on the next split
    for no reason, which is exactly what happened when the held net moved to
    ``20-walker.js``: two tests failed and neither had found a real defect.
    """
    return "\n".join(_code(p.name) for p in sorted(_SCENE3D.glob("*.js")))


class TestHowBigTheyAre(unittest.TestCase):
    """Life size comes from morphology, and the viewer measures rather than
    assumes."""

    def test_the_measurements_are_real_ones(self):
        """``true_m`` is the measurement, straight out of the morphology
        tables. (``m`` is what gets DRAWN — the visibility floor applied — and
        is checked separately below.)"""
        from src.scene_wildlife import _size_for
        # A leafcutter bee: 11 mm, along the body axis.
        s = _size_for({"taxon": "bee"}, {"kind": "bee"},
                      bee_m={"body_length_mm": 11.0})
        self.assertAlmostEqual(s["true_m"], 0.011, places=4)
        self.assertEqual(s["axis"], "z")
        # A swallowtail: the wingspan band's midpoint, across the wings.
        s = _size_for({"taxon": "lepidoptera"}, {"kind": "butterfly"},
                      lep_m={"wingspan_min_mm": 70, "wingspan_max_mm": 90})
        self.assertAlmostEqual(s["true_m"], 0.080, places=4)
        self.assertEqual(s["axis"], "x")
        # A chickadee: wingspan, across the wings — and drawn at it, because
        # a bird is already big enough to see.
        s = _size_for({"taxon": "bird"}, {"kind": "bird"},
                      bird_m={"wingspan_mm": 203})
        self.assertAlmostEqual(s["true_m"], 0.203, places=4)
        self.assertAlmostEqual(s["m"], 0.203, places=2)
        self.assertEqual(s["axis"], "x")

    def test_no_measurement_still_gets_an_honest_size(self):
        """A creature with no morphology must not fall back to *nothing* — a
        zero or a missing key would make the viewer divide by it. It gets its
        kind's fallback, which is still far closer to life than the constant
        this replaced."""
        from src.scene_wildlife import _size_for, _SIZE_FALLBACK_M
        for kind, expect in _SIZE_FALLBACK_M.items():
            s = _size_for({"taxon": ""}, {"kind": kind})
            self.assertEqual(s["true_m"], expect, kind)
            self.assertGreaterEqual(s["m"], s["true_m"], kind)
            self.assertIn(s["axis"], ("x", "y", "z"), kind)

    def test_nothing_is_drawn_at_a_wildly_wrong_size(self):
        """The property that actually matters, stated as a bound: every
        creature the app can place is between 5 mm and 1.5 m. The old constants
        put an 11 mm bee at 0.54 m — a cat — and this is what would have caught
        that."""
        from src.scene_wildlife import _size_for, _SIZE_FALLBACK_M
        for kind in _SIZE_FALLBACK_M:
            s = _size_for({"taxon": ""}, {"kind": kind})
            for key in ("m", "true_m"):     # drawn AND real, both bounded
                self.assertTrue(0.005 <= s[key] <= 1.5,
                                f"{kind} {key} at {s[key]} m")

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

    def test_birds_are_left_alone_and_the_small_things_are_lifted(self):
        """The V2.46c correction, stated as the author stated it.

            *"I don't want the birds changing size to x3 or more, they look
            ridiculous. The bugs are not visible unless x3."*

        Both halves at once, which is exactly what a global multiplier cannot
        do — and what a flat per-taxon boost cannot do either, since x3 on
        insects puts a swallowtail at 24 cm, which is a goldfinch.
        """
        from src.scene_wildlife import _drawn_size
        # Too small to see: lifted into visibility.
        for name, m, lo, hi in [("ladybeetle", 0.008, 3.0, 5.0),
                                ("leafcutter bee", 0.011, 2.5, 3.5),
                                ("hoverfly", 0.015, 2.0, 3.0)]:
            boost = _drawn_size(m) / m
            self.assertTrue(lo <= boost <= hi,
                            f"{name}: boosted x{boost:.2f}, wanted {lo}-{hi}")
        # Already visible: left alone. A goldfinch that grows by more than a
        # couple of percent is the thing being complained about.
        for name, m in [("chickadee", 0.203), ("goldfinch", 0.225),
                        ("northern flicker", 0.500), ("a bat", 0.250)]:
            boost = _drawn_size(m) / m
            self.assertLess(boost, 1.03,
                            f"{name} is being drawn x{boost:.2f} life size")

    def test_the_floor_never_shrinks_and_never_reorders(self):
        """Two properties a hard ``max(m, FLOOR)`` would break.

        Nothing may be drawn smaller than life, and a beetle must stay smaller
        than a bee smaller than a fly smaller than a butterfly — a hard floor
        collapses every small creature to one identical size, so the scene
        stops reading as different animals.
        """
        from src.scene_wildlife import _drawn_size
        ladder = [0.004, 0.008, 0.011, 0.015, 0.040, 0.079, 0.203, 0.5, 1.2]
        drawn = [_drawn_size(m) for m in ladder]
        for m, d in zip(ladder, drawn):
            self.assertGreaterEqual(d, m, f"{m} m was drawn smaller than life")
        self.assertEqual(drawn, sorted(drawn), "the floor reordered the animals")
        self.assertEqual(len(set(drawn)), len(drawn),
                         "two different animals collapsed to one drawn size")
        # And it decays: the exaggeration must vanish, not merely shrink.
        self.assertLess(_drawn_size(2.0) / 2.0, 1.001)

    def test_the_true_measurement_travels_with_the_drawn_one(self):
        """P9. A creature shown at three times life size has to be able to say
        so, or the app teaches that a leafcutter bee is walnut-sized."""
        from src.scene_wildlife import _size_for, size_sentence
        size = _size_for({"taxon": "bee"}, {"kind": "bee"},
                         bee_m={"body_length_mm": 11.0})
        self.assertAlmostEqual(size["true_m"], 0.011, places=4)
        self.assertGreater(size["m"], size["true_m"])
        # `boost` is rounded for the wire, so compare at the precision it
        # carries rather than to full float equality.
        self.assertAlmostEqual(size["boost"], size["m"] / size["true_m"], places=1)
        line = size_sentence(size)
        self.assertIn("11 mm", line)
        self.assertIn("3", line)
        self.assertIn("life size", line)
        # A bird says its size and claims no exaggeration.
        bird = _size_for({"taxon": "bird"}, {"kind": "bird"},
                         bird_m={"wingspan_mm": 225.0})
        self.assertNotIn("×", size_sentence(bird).replace("life size", ""))

    def test_the_viewer_no_longer_decides_and_the_dropdown_is_gone(self):
        """The control was removed rather than re-defaulted.

            *"I don't know if we need this size changing as a changeable drop
            down menu."*

        Correct: with the floor applied per animal there is nothing left to
        set. A leftover `permaSet*` hook the app never drives is dead code that
        tests/test_bridge_contract already rejects once, so this checks the
        whole path is gone, not just the combo.
        """
        code = _all_code()
        self.assertNotIn("CRITTER_MAGNIFY", code,
                         "the viewer still carries a global magnifier")
        self.assertNotIn("permaSetCreatureScale", code)
        for mod in ("scene3d_toolbar.py", "scene3d_window.py",
                    "reference_ecosystem_window.py", "map3d_js.py",
                    "map3d_widget.py"):
            src = (_ROOT / "src" / mod).read_text(encoding="utf-8")
            self.assertNotIn("creature_scale", src.lower(),
                             f"{mod} still wires the removed dropdown")

    def test_the_size_line_reaches_the_hover_tip(self):
        """The label is what the dropdown was actually for, so it has to be on
        screen — per creature, where you are already looking."""
        self.assertIn("size: _sizeLine(spec.size)", _code("07-wildlife.js"))
        self.assertIn("info.size", _code("01-core.js"),
                      "the hover tip does not show how big the creature is")


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


class TestBirdsFlyLikeBirds(unittest.TestCase):
    """*"The birds do not look real when they fly. They look like a perched
    bird... the bobbing up and down in the air also looks rather
    unrealistic."*"""

    def test_the_body_pitches_with_the_flight(self):
        """`o.rotation.x` was never touched, so a perched pose — nose up, tail
        down — translated through the air and rose and fell inside it like a
        lift. The pitch must be MEASURED off the animal's own vertical speed,
        not tuned, so it cannot disagree with the physics driving the bounce."""
        code = _code("07-wildlife.js")
        self.assertIn("function _birdAttitude", code)
        self.assertIn("_birdAttitude(c, o,", code,
                      "the attitude is computed and never applied")
        self.assertIn("Math.atan2(vy, vh)", code,
                      "the pitch is not derived from the bird's own motion")
        self.assertIn("_PERCH_PITCH", code,
                      "a perched bird has no distinct pose from a flying one")

    def test_a_flying_bird_uses_its_own_height_not_its_destination(self):
        """The bug underneath the unrealistic bobbing: the travel branch climbs
        `c.pos.y` toward the next perch and this branch then threw it away and
        used `tgt.y`, so a bird flew the whole way at its DESTINATION's height
        with only the bound offset moving it."""
        code = _code("07-wildlife.js")
        self.assertNotIn("o.position.y = tgt.y + Math.sin(t * 0.003 + ph) * mv.bob;",
                         code, "the flying bird is pinned to its target's height")
        self.assertIn("flying ? c.pos.y : tgt.y", code)

    def test_the_dip_is_still_derived_and_not_a_tuned_wobble(self):
        """"Are we basing their flight path on anything?" — yes, and it has to
        stay that way: the bound dip comes from the pause by s = 1/4 g t^2."""
        from src.flight_model import bird_flight
        f = bird_flight(mass_g=11.0, span_mm=203.0, style="bounding")
        dip = f.get("bound_dip_m") or {}
        pause = f.get("pause_s") or {}
        self.assertGreater(dip.get("mid", 0), 0.0,
                           "a bounding bird with no dip is a zipline")
        # The BAND ends are what s = 1/4 g t^2 is applied to — the mid is the
        # midpoint of the two derived dips, not the dip of the mid pause, and
        # those are different numbers (0.248 vs 0.206 for a chickadee).
        for end in ("lo", "hi"):
            t = pause[end]
            self.assertAlmostEqual(dip[end], 0.25 * 9.81 * t * t, places=2,
                                   msg=f"the {end} dip is not derived from its "
                                       f"own pause")
        self.assertTrue(dip["lo"] <= dip["mid"] <= dip["hi"])
        dip = dip["mid"]
        # And it is a real bird's amplitude, not a cartoon's.
        self.assertTrue(0.05 <= dip <= 0.40, f"chickadee bound dip {dip} m")


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
        # Chunk-agnostic on purpose: which file builds him is a housekeeping
        # decision (he moved to 20-walker.js at V2.46b); that he carries a
        # net on the arm pivot is the actual claim.
        code = _all_code()
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
        code = _all_code()
        m = re.search(r"NET_REACH_M = ([\d.]+)", code)
        self.assertIsNotNone(m, "the net's reach is gone")
        self.assertTrue(1.0 <= float(m.group(1)) <= 5.0,
                        "an arm's reach with a net is metres, not tens")
        edit = _code("16-editing.js")
        self.assertIn("outOfReach", edit,
                      "a swing that misses says nothing to the user")

    def test_you_swing_the_net_you_do_not_click_the_animal(self):
        """The V2.46c correction.

            *"Catching the bugs is impossible with the way it is set up… If I
            am within range of a bug and click while holding the net, not
            clicking on the bug because it is tiny and too kind of too fast
            moving."*

        V2.46 required a raycast HIT on the creature. Making the sizes honest
        then shrank that target fourfold — the two changes were in tension and
        only one of them shipped. In walk mode with the net out, the click must
        resolve through *reach*, not through the cursor.
        """
        code = _all_code()
        self.assertIn("function critterInReach", code,
                      "nothing resolves the catch by proximity")
        edit = _code("16-editing.js")
        # `netTarget()` is `critterInReach()` plus the latch (V2.46d); either
        # is a proximity resolve, and naming the specific one here is what made
        # this test break when the latch landed without a defect behind it.
        self.assertRegex(edit, r"(netTarget|critterInReach)\(\)",
                         "the net click still depends on hitting the creature")
        # And the proximity path must be tried BEFORE the aimed one, or the
        # forgiving branch is unreachable whenever the cursor happens to miss.
        self.assertLess(re.search(r"(netTarget|critterInReach)\(\)", edit).start(),
                        edit.index("critterObjectAt("),
                        "the aim-and-click path still wins over reach")

    def test_the_ring_and_the_click_ask_the_same_question(self):
        """The race that made it miss (V2.46d).

            *"I caught a bird once but often the circle shows up and I click to
            swing but I don't catch anything."*

        The ring asked `critterInReach()` every frame and the click asked it
        AGAIN — two independent queries about an animal moving at a metre or
        two a second, a few hundred milliseconds apart. The ring must LATCH its
        target and the click must take that one.
        """
        code = _all_code()
        self.assertIn("function netTarget", code, "nothing latches the target")
        self.assertIn("_reachOn", code)
        # The keep radius has to be wider than the reach, or the latch adds
        # nothing: a creature that drifted out is exactly the failing case.
        keep = float(re.search(r"NET_KEEP_M = ([\d.]+)", code).group(1))
        reach = float(re.search(r"NET_REACH_M = ([\d.]+)", code).group(1))
        self.assertGreater(keep, reach,
                           "the latch grace is not wider than the reach, so it "
                           "cannot rescue the drift it exists for")

    def test_the_net_gesture_is_looser_than_the_trowel(self):
        """Planting is a precise act on a static point; swinging a net is not.
        A deliberate click that took a second was being discarded in silence,
        which looks exactly like a broken button."""
        edit = _code("16-editing.js")
        self.assertIn("_editMode === 'net'", edit)
        m = re.search(r"const hold = netting \? (\d+) : (\d+);", edit)
        self.assertIsNotNone(m, "the net no longer gets its own press window")
        self.assertGreater(int(m.group(1)), int(m.group(2)),
                           "the net's press window is not longer than the "
                           "trowel's")

    def test_you_can_see_what_you_would_catch(self):
        """The other half of "impossible": with no feedback you cannot tell
        whether you are close enough, so a click that does nothing is
        indistinguishable from a broken button."""
        code = _all_code()
        self.assertIn("function updateReachRing", code)
        self.assertIn("updateReachRing()", _code("08-modes.js"),
                      "the ring is never updated from the walk step")
        self.assertIn("typeof updateReachRing === 'function'", _code("08-modes.js"),
                      "20-walker.js loads after 08-modes.js, so this call has "
                      "to be guarded — see TestTheRenderLoopSurvivesItself")

    def test_a_swing_that_finds_nothing_still_says_so(self):
        """An empty name means "nothing in reach at all", which is a different
        sentence from "that one is too far" and must not be silence."""
        edit = _code("16-editing.js")
        self.assertIn("outOfReach('')", edit.replace('"', "'"),
                      "a swing at empty air reports nothing to the user")
        from src.scene3d_edit_flow import MISS_HINT
        self.assertTrue(MISS_HINT.strip())
        ref = (_ROOT / "src" / "reference_ecosystem_window.py").read_text(
            encoding="utf-8")
        self.assertIn("MISS_HINT", ref,
                      "the sandbox window has its own wording for the miss")

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


class TestBeeModeIsTheRightSizeToo(unittest.TestCase):
    """F110 — the same scale error, in the one view where it is most obvious.

        *"The fly as a bee/butterfly mode will need to be altered to be the
        appropriate size relative to the flora. Also I would like to see other
        fauna and maybe the human character walking the scene too when in bug
        mode."*
    """

    def test_the_flown_creature_carries_its_real_size(self):
        """Under ``real_size``, never ``size`` — ``app["size"]`` is already a
        relative style scalar the avatar builders multiply by, and overloading
        it would silently rescale every procedural body."""
        from src.scene_wildlife import _appearance_for, _size_for
        app = _appearance_for({"taxon": "bee", "common_name": "Leafcutter Bee",
                               "scientific_name": "Megachile sp."},
                              {"body_length_mm": 11.0})
        self.assertIsNotNone(app)
        # The style scalar is untouched and is NOT a measurement in metres.
        self.assertGreater(app.get("size", 1), 0.2)
        # …and the real one is a separate key.
        size = _size_for({"taxon": "bee"}, app, bee_m={"body_length_mm": 11.0})
        self.assertAlmostEqual(size["true_m"], 0.011, places=4)

    def test_the_avatar_is_scaled_and_stood_off_by_its_own_size(self):
        """Both numbers come from the animal, and the standoff is a MULTIPLE of
        its size — which is what makes it self-correcting across species
        without a per-species table."""
        fly = _code("06-fly.js")
        self.assertIn("function _sizeAvatarToLife", fly)
        self.assertIn("_sizeAvatarToLife()", fly,
                      "ensureAvatar never applies the life-size scaling")
        self.assertIn("Box3", fly, "the avatar's scale must be MEASURED, the "
                                   "same way the ambient creatures' is")
        self.assertIn("_AVATAR_STANDOFF", fly)
        # Whitespace-insensitive: this is a claim about the ARITHMETIC — the
        # standoff is the per-kind factor times the animal's own size — not
        # about how the line happens to be wrapped. (Pinning the formatting is
        # what broke this test when the standoff floor was added.)
        flat = re.sub(r"\s+", "", fly)
        self.assertIn("_AVATAR_STANDOFF[beeKind]||1.5)*m", flat,
                      "the standoff is not proportional to the creature")
        self.assertIn("Math.max(_AVATAR_MIN_STANDOFF,", flat,
                      "no floor under the standoff — the smallest leps will "
                      "sit through the near plane")
        # It uses LIFE size, not the ambient floor: you are the animal, and the
        # point is its proportion to the flower in front of it.
        self.assertIn("size.true_m", fly)

    def test_a_small_avatar_gets_a_near_plane_that_can_show_it(self):
        """A 13 mm body 34 mm from the eye does not survive a 0.1 m near plane.
        Per-mode, and restored on exit — a global change would cost the orbit
        view depth precision it has no reason to pay for."""
        fly = _code("06-fly.js")
        m = re.search(r"_BEE_NEAR = ([\d.]+), _BEE_FAR = ([\d.]+)", fly)
        self.assertIsNotNone(m, "bee mode has no near/far of its own")
        near, far = float(m.group(1)), float(m.group(2))
        # Small enough for the closest standoff in the catalogue (a 9 mm bee at
        # 2.6 body lengths is 23 mm), with room to fly right up to a petal.
        self.assertLess(near, 0.02, "the near plane will clip the avatar")
        self.assertGreater(near, 0.0005, "an absurdly small near plane throws "
                                         "away depth precision for nothing")
        # …and the depth ratio stays within an order of magnitude of default.
        self.assertLess(far / near, 1e6)
        self.assertIn("_setCameraRange(_ORBIT_NEAR, _ORBIT_FAR)", fly,
                      "exitBeeMode does not restore the camera range")

    def test_no_species_in_the_catalogue_clips_the_near_plane(self):
        """The numeric check the standoff floor exists for.

        Proportionality alone puts the smallest animals *through* the near
        plane: a Western Tailed-Blue is 22.5 mm across, so a strict 1.0x
        standoff parks its wingtips ~11 mm from the eye — 1 mm clear of a 10 mm
        near plane, with an idle bob bigger than that. This walks the real
        catalogue and demands a margin, rather than trusting three constants
        that were each reasonable on their own.
        """
        from src.db.plants import init_db, get_connection
        from src.scene_wildlife import appearance_for_fauna
        init_db()
        fly = _code("06-fly.js")
        near = float(re.search(r"_BEE_NEAR = ([\d.]+)", fly).group(1))
        floor = float(re.search(r"_AVATAR_MIN_STANDOFF = ([\d.]+)", fly).group(1))
        stand = dict(re.findall(r"(\w+): ([\d.]+)",
                                re.search(r"_AVATAR_STANDOFF = \{([^}]*)\}",
                                          fly).group(1)))
        rows = get_connection().execute(
            "SELECT id, common_name FROM fauna "
            "WHERE taxon IN ('bee', 'lepidoptera')").fetchall()
        self.assertGreater(len(rows), 20, "no fauna to check against")
        tightest = None
        for fid, name in rows:
            app = appearance_for_fauna(fid) or {}
            size = app.get("real_size")
            if not size:
                continue
            m = size["true_m"]
            off = max(floor, float(stand.get(app.get("kind", ""), 1.5)) * m)
            # Conservative: treat half the measured extent as body depth.
            nearest = off - m * 0.5
            if tightest is None or nearest < tightest[0]:
                tightest = (nearest, name, m, off)
        self.assertIsNotNone(tightest, "no species carried a real_size")
        nearest, name, m, off = tightest
        self.assertGreater(
            nearest, near * 1.5,
            f"{name} ({m * 1000:.1f} mm) sits {nearest * 1000:.1f} mm from a "
            f"{near * 1000:.0f} mm near plane — its wingtips will clip")

    def test_you_are_not_alone_down_there(self):
        """`wildlifeGroup.visible = false` on entering bee mode was right when
        the creatures were cat-sized and is wrong now they are honest."""
        fly = _code("06-fly.js")
        self.assertNotIn("wildlifeGroup.visible = false", fly,
                         "bee mode still hides the other animals")
        wild = _code("07-wildlife.js")
        self.assertNotIn("visible = !beeMode", wild,
                         "rebuildWildlife still hides the group in bee mode")

    def test_the_walker_stands_in_for_scale(self):
        """He is the only object of KNOWN size in the scene, which is what
        makes the new proportions legible rather than merely correct — the same
        argument as the V2.35 scale rule."""
        fly = _code("06-fly.js")
        self.assertIn("_showWalkerForScale(true)", fly)
        self.assertIn("_showWalkerForScale(false)", fly,
                      "the stand-in walker is never taken away again")
        # And he must not be yanked out from under walk mode if it owns him.
        self.assertIn("if (walkMode) return;", fly)


class TestTheRenderLoopSurvivesItself(unittest.TestCase):
    """The regression that blanked the whole 3D window (V2.46b).

    Splitting ``19-roster.js`` out of ``07-wildlife.js`` moved
    ``stepSpotlight`` from a chunk that loads *before* ``08-modes.js`` to one
    that loads *after* it. The animation loop's unguarded call threw
    ``ReferenceError`` on the first frame — and three.js re-schedules its
    ``requestAnimationFrame`` **after** invoking the callback, so a throw does
    not skip a frame, it ends the loop forever.

    On screen that is a blank sky-coloured window with a completely correct
    HUD on top of it, because the HUD is DOM and was written before the loop
    ever ran. It reads like "the scene failed to build", which is the opposite
    of what happened, and it cost a whole release to spot.

    Two rules, both mechanical, so the next chunk split cannot repeat it.
    """

    #: Load order, from the bootstrap in ``html/scene3d.html``.
    @staticmethod
    def _order():
        html = (_ROOT / "html" / "scene3d.html").read_text(encoding="utf-8")
        return re.findall(r"'scene3d/([\w.\-]+\.js)'", html)

    @staticmethod
    def _loop_body():
        src = _js("08-modes.js")
        i = src.index("renderer.setAnimationLoop")
        return src[i:src.index("\n});", i)]

    def test_every_step_the_loop_calls_is_loaded_or_guarded(self):
        """The specific rule: a function called from the animation loop must
        either live in a chunk that loads BEFORE 08-modes.js, or be reached
        through a ``typeof … === 'function'`` guard."""
        order = self._order()
        self.assertIn("08-modes.js", order, "load order not parsed")
        cut = order.index("08-modes.js")

        # Where each top-level function/binding is declared.
        home = {}
        for name in order:
            path = _SCENE3D / name
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                m = re.match(r"^(?:function\s+([A-Za-z_$][\w$]*)"
                             r"|(?:let|const|var)\s+([A-Za-z_$][\w$]*))", line)
                if m:
                    home.setdefault(m.group(1) or m.group(2), name)

        body = self._loop_body()
        offenders = []
        for callee in sorted(set(re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", body))):
            chunk = home.get(callee)
            if chunk is None or chunk not in order:
                continue
            if order.index(chunk) <= cut:
                continue                       # already loaded — safe
            if f"typeof {callee} === 'function'" in body:
                continue                       # guarded — safe
            offenders.append(f"{callee}() lives in {chunk}, which loads after "
                             f"08-modes.js, and is called unguarded")
        self.assertEqual([], offenders, "\n".join(offenders))

    def test_the_loop_body_is_wrapped_so_one_throw_is_not_fatal(self):
        """The general rule. The guard above only catches the load-order
        version of this mistake; the wrapper catches every other one, and the
        cost of NOT having it is a permanently dead viewer."""
        body = self._loop_body()
        self.assertIn("try {", body,
                      "08-modes.js: the animation loop body is not wrapped — a "
                      "single throw in any step function will end the loop "
                      "permanently and blank the viewer")
        self.assertIn("_loopFault", body,
                      "08-modes.js: the loop catches but does not report; a "
                      "silent catch turns a dead animation into a mystery")

    def test_render_stays_outside_the_catch(self):
        """A broken step function should leave a scene that still DRAWS —
        frozen and inspectable — rather than a black window. That only holds
        if `renderer.render` is not inside the try."""
        body = self._loop_body()
        try_at = body.index("try {")
        catch_at = body.index("} catch")
        render_at = body.rindex("renderer.render(")
        self.assertFalse(try_at < render_at < catch_at,
                         "08-modes.js: renderer.render is inside the try — a "
                         "throw in a step would stop the scene being drawn at "
                         "all, which is the failure this wrapper exists to "
                         "prevent")


if __name__ == "__main__":                         # pragma: no cover
    unittest.main()
