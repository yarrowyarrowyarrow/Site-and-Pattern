"""
tests/test_leaf_light.py — how a leaf is lit (F186, V2.94).

From a person's height every tree crown rendered near-black. From above they
read green, which is how the V2.87 audit saw them. Three causes, each measured
by switching it alone (docs/plans/V2.94-leaves-let-light-through.md):

* an opaque leaf card seen from its shaded side took no sun at all, where a real
  leaf lets through about as much light as it reflects;
* the baked shade (a GLB's grey COLOR_0) multiplied the leaf's colour, so it
  dimmed the sun as well as the sky, and a sunlit leaf inside the crown was
  shaded twice, once by the shadow map and once by the bake;
* the bake put its ground at a crown's lowest leaf, because foliage is baked
  without its trunk, and buried nearly every interior leaf.

What the screen shows is pinned by tests/test_accuracy_render.py, which
photographs two crowns from their shaded side. This module holds what needs no
browser: the wiring, the three.js chunks the shader hooks into, the bake's
settings, and the shade baked into every shipped tree. Stdlib only; never skips.
"""

import ast
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_model_assets import _read_accessor, parse_glb  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HTML = os.path.join(_ROOT, "html")
_SCENE3D = os.path.join(_HTML, "scene3d")
_THREE = os.path.join(_HTML, "vendor", "three", "three.module.js")
_MODELS = os.path.join(_HTML, "assets", "models")
_ASSETLIB = os.path.join(_ROOT, "scripts", "blender", "assetlib")

#: The surface presets that are leaves (04-quality.js MAT_PRESETS).
_LEAF_PRESETS = {"crown", "shrubLeaf", "herbLeaf", "needle"}

#: A shipped crown's baked shade, averaged over its vertices, and the share of
#: vertices darker than 0.3. V2.93's trees averaged 0.17-0.46 (0.30 overall), 63%
#: of vertices under 0.3; V2.94's 0.46-0.71, at most 16% under 0.3.
MIN_CROWN_SHADE = 0.45
DARK_VERTEX = 0.3
MAX_DARK_SHARE = 0.20


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _js(name):
    return _read(os.path.join(_SCENE3D, name))


def _leaf_translucency():
    """LEAF_TRANSLUCENCY from 01c-leaves.js, as {preset: share}."""
    m = re.search(r"const LEAF_TRANSLUCENCY = \{([^}]*)\};", _js("01c-leaves.js"))
    if not m:
        raise AssertionError("01c-leaves.js: LEAF_TRANSLUCENCY moved or changed shape")
    return {k: float(v) for k, v in re.findall(r"(\w+)\s*:\s*([\d.]+)", m.group(1))}


class LeafLightWiringTest(unittest.TestCase):

    def test_the_chunk_loads_before_any_material_is_built(self):
        """Materials are built from 02-plants.js on; the chunk must be there by
        then, or plantMaterial calls an undefined applyLeafLight."""
        src = _read(os.path.join(_HTML, "scene3d.html"))
        files = re.findall(r"'scene3d/([\w-]+\.js)'", src)
        self.assertIn("01c-leaves.js", files, "scene3d.html does not load 01c-leaves.js")
        self.assertLess(files.index("01c-leaves.js"), files.index("02-plants.js"))

    def test_the_leaves_let_light_through_and_nothing_else_does(self):
        share = _leaf_translucency()
        self.assertEqual(set(share), _LEAF_PRESETS,
                         "LEAF_TRANSLUCENCY should name the four leaf presets and "
                         "nothing else: bark and grass blades are opaque")
        for k, v in share.items():
            with self.subTest(k):
                self.assertGreater(v, 0.0)
                self.assertLess(v, 1.0, f"{k}: a leaf passes on less than it catches")
        self.assertEqual(min(share, key=share.get), "needle",
                         "a needle is the thickest leaf here and lets through the least")
        presets = _js("04-quality.js")
        for k in _LEAF_PRESETS:
            with self.subTest(k):
                self.assertTrue(re.search(r"\b%s: \{ key: '%s'" % (k, k), presets),
                                f"04-quality.js MAT_PRESETS lost '{k}', so its "
                                f"leaves would be opaque again")

    def test_surface_materials_ask_for_it_by_preset(self):
        src = _js("01b-surface.js")
        body = src[src.index("function surfaceMaterial("):]
        body = body[:body.index("\n}\n")]
        self.assertIn("LEAF_TRANSLUCENCY[preset.key]", body,
                      "surfaceMaterial no longer reads the share by preset key")

    def test_a_translucent_leaf_does_not_share_a_program_with_an_opaque_one(self):
        """three.js reuses a compiled program by cache key. Without the share in
        the key, whichever material compiled first would light both."""
        src = _js("01b-surface.js")
        body = src[src.index("function plantMaterial("):]
        body = body[:body.index("\n}\n")]
        self.assertIn("applyLeafLight(shader, trans)", body)
        self.assertRegex(body, r"customProgramCacheKey[^;]*\n?[^;]*'\|t' \+ trans",
                         "plantMaterial's cache key does not name the share")

    def test_every_chunk_it_hooks_into_is_in_the_vendored_three_js(self):
        """applyLeafLight edits three.js's shader text with String.replace, and a
        replace that finds nothing does nothing. A three.js upgrade that renamed
        one of these would quietly bring back the opaque leaves."""
        three = _read(_THREE)
        hooks = re.findall(r"'(#include <\w+>)'", _js("01c-leaves.js"))
        self.assertEqual(len(set(hooks)), 4, f"expected four hooks, found {hooks}")
        for hook in set(hooks):
            with self.subTest(hook):
                self.assertIn(hook, three)
        # What the injected code calls or redefines, by name.
        for name in ("RE_Direct_Physical", "BRDF_Lambert", "getHemisphereLightIrradiance",
                     "hemisphereLights", "NUM_HEMI_LIGHTS", "RE_IndirectDiffuse",
                     "USE_COLOR_ALPHA", "reflectedLight.indirectDiffuse"):
            with self.subTest(name):
                self.assertIn(name, three)
        # The physical material's direct light is a macro, and the leaf light
        # redefines it. Tabs and newlines are escapes inside the JS string.
        self.assertRegex(three, r"#define RE_Direct(\\t| )+RE_Direct_Physical\b")


class CrownBakeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(_read(os.path.join(_ASSETLIB, "build_all.py")))

    def _crown_ao(self):
        for node in self.tree.body:
            if isinstance(node, ast.Assign) and any(
                    getattr(t, "id", "") == "CROWN_AO" for t in node.targets):
                return {k.arg: ast.literal_eval(k.value) for k in node.value.keywords}
        self.fail("build_all.py lost CROWN_AO")

    def _foliage_bakes(self):
        """(kind, keyword names) of each bake_ao call on PART_FOLIAGE, by the
        spec kind whose branch it sits in."""
        out = []
        for node in ast.walk(self.tree):
            if not (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)):
                continue
            kind = next((c.value for c in node.test.comparators
                         if isinstance(c, ast.Constant)), None)
            for call in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if (isinstance(call, ast.Call) and getattr(call.func, "id", "") == "bake_ao"
                        and "PART_FOLIAGE" in ast.dump(call.args[0])):
                    out.append((kind, call))
        return out

    def test_a_crown_is_baked_standing_on_the_ground(self):
        ao = self._crown_ao()
        self.assertEqual(ao.get("floor_z"), 0.0,
                         "a crown baked on its own takes its lowest leaf for the "
                         "ground unless it is told where the ground is")
        self.assertLessEqual(ao.get("max_dist", 1), 0.25,
                             "rays that reach across the crown bury its inside; "
                             "that depth is the shadow map's job")

    def test_the_trees_use_it_and_the_shrubs_do_not(self):
        """The viewer draws shrub foliage with vertex colours off, so a shrub's
        bake never reaches the screen (F188). Rebaking them would change the files
        and nothing visible; they keep the old bake until that is decided."""
        bakes = {kind: call for kind, call in self._foliage_bakes()}
        self.assertIn("tree", bakes)
        self.assertIn("shrub", bakes)
        self.assertTrue(any(k.arg is None and getattr(k.value, "id", "") == "CROWN_AO"
                            for k in bakes["tree"].keywords),
                        "the tree crowns are not baked with CROWN_AO")
        self.assertFalse(any(k.arg is None for k in bakes["shrub"].keywords),
                         "the shrubs were rebaked; see F188 first")

    def test_bake_ao_still_defaults_to_the_lowest_vertex(self):
        """Anything baked whole (a herb, a structure) sits on its own lowest
        vertex, so the default must not move: it would rebake every model."""
        fn = next(n for n in ast.walk(ast.parse(_read(os.path.join(_ASSETLIB, "ao_bake.py"))))
                  if isinstance(n, ast.FunctionDef) and n.name == "bake_ao")
        names = [a.arg for a in fn.args.args]
        defaults = dict(zip(names[len(names) - len(fn.args.defaults):],
                            (ast.literal_eval(d) for d in fn.args.defaults)))
        self.assertIsNone(defaults.get("floor_z", "missing"))
        self.assertEqual(defaults.get("gradient_floor"), 0.55)
        self.assertEqual(defaults.get("max_dist"), 0.6)
        self.assertEqual(defaults.get("strength"), 0.85)


def _unit(values, acc):
    """An accessor's components as 0..1 floats (normalised integers or floats)."""
    top = {5121: 255.0, 5123: 65535.0}.get(acc["componentType"])
    if top and acc.get("normalized"):
        return [v / top for v in values]
    return list(values)


@unittest.skipUnless(os.path.isfile(os.path.join(_MODELS, "manifest.json")),
                     "no generated GLB assets yet (html/assets/models)")
class ShippedCrownShadeTest(unittest.TestCase):

    def test_no_shipped_crown_is_baked_into_darkness(self):
        manifest = json.loads(_read(os.path.join(_MODELS, "manifest.json")))
        trees = {k: v for k, v in manifest["plants"].items() if k.startswith("tree.")}
        self.assertGreaterEqual(len(trees), 20)
        for key, entry in sorted(trees.items()):
            gltf, binary = parse_glb(os.path.join(_MODELS, entry["file"]))
            shade = []
            for node in gltf["nodes"]:
                if "mesh" not in node or not node.get("name", "").endswith("_foliage"):
                    continue
                for prim in gltf["meshes"][node["mesh"]]["primitives"]:
                    ci = prim["attributes"].get("COLOR_0")
                    if ci is None:
                        continue
                    acc = gltf["accessors"][ci]
                    shade += _unit((c[0] for c in _read_accessor(gltf, binary, ci)), acc)
            with self.subTest(key):
                self.assertTrue(shade, f"{key}: no baked shade on its foliage")
                mean = sum(shade) / len(shade)
                dark = sum(v < DARK_VERTEX for v in shade) / len(shade)
                self.assertGreaterEqual(
                    mean, MIN_CROWN_SHADE,
                    f"{key}: its crown's baked shade averages {mean:.2f}. Was it "
                    f"baked with CROWN_AO (build_all.py)?")
                self.assertLessEqual(
                    dark, MAX_DARK_SHARE,
                    f"{key}: {dark:.0%} of its crown is baked darker than "
                    f"{DARK_VERTEX}")


if __name__ == "__main__":
    unittest.main()
