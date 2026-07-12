"""
tests/test_model_assets.py

Guards the committed Blender-generated GLB assets (html/assets/models/)
against the viewer contract in html/scene3d/09-models.js — stdlib only, no
Blender, no Qt, no three.js:

- manifest.json parses, is version 1, references only files that exist, and
  every .glb in the directory is referenced (no orphans);
- asset keys stay in lockstep with the viewer's OWN archetype vocabularies,
  regex-extracted from the JS (the render_flower_sprites.py prior art:
  extract the real thing, don't duplicate it);
- every GLB is structurally sound via a ~40-line GLB/JSON-chunk parser:
  no textures/images, plant primitives carry POSITION + COLOR_0, POSITION
  bounds satisfy the unit frame, declared tier/variant/part and fauna node
  names exist, triangle budgets hold (mirrors assetlib/conventions.py).

Skips while html/assets/models/manifest.json does not exist (the plumbing
ships before the first generated assets do).
"""

import json
import os
import re
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODELS = os.path.join(_ROOT, "html", "assets", "models")
_MANIFEST = os.path.join(_MODELS, "manifest.json")
_SCENE3D = os.path.join(_ROOT, "html", "scene3d")

# Mirrors assetlib/conventions.py TRI_BUDGETS (comment there points here).
_TRI_BUDGETS = {"tree_tier0": 1200, "tree_tier1": 2200, "tree_tier2": 3500,
                "shrub": 2000, "herb": 1200, "layer": 900, "fauna": 1500}


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def parse_glb(path):
    """Minimal GLB v2 reader → (json_dict, has_binary_chunk)."""
    with open(path, "rb") as fh:
        blob = fh.read()
    magic, version, length = struct.unpack_from("<4sII", blob, 0)
    if magic != b"glTF":
        raise ValueError(f"{path}: not a GLB (magic {magic!r})")
    if version != 2:
        raise ValueError(f"{path}: glTF version {version} != 2")
    if length != len(blob):
        raise ValueError(f"{path}: declared length {length} != {len(blob)}")
    off, js, has_bin = 12, None, False
    while off < len(blob):
        chunk_len, chunk_type = struct.unpack_from("<I4s", blob, off)
        data = blob[off + 8:off + 8 + chunk_len]
        if chunk_type == b"JSON":
            js = json.loads(data.decode("utf-8"))
        elif chunk_type == b"BIN\x00":
            has_bin = True
        off += 8 + chunk_len
    if js is None:
        raise ValueError(f"{path}: no JSON chunk")
    return js, has_bin


def _tri_count(gltf):
    """Total triangles across all mesh primitives (indexed or not)."""
    total = 0
    accessors = gltf.get("accessors", [])
    for mesh in gltf.get("meshes", []):
        for prim in mesh.get("primitives", []):
            if prim.get("mode", 4) != 4:          # TRIANGLES
                continue
            if "indices" in prim:
                total += accessors[prim["indices"]]["count"] // 3
            else:
                total += accessors[prim["attributes"]["POSITION"]]["count"] // 3
    return total


def _node_names(gltf):
    return {n.get("name", "") for n in gltf.get("nodes", [])}


def _mesh_nodes_under(gltf, root_idx):
    """Depth-first node indices under (and including) root_idx."""
    out, stack = [], [root_idx]
    nodes = gltf.get("nodes", [])
    while stack:
        i = stack.pop()
        out.append(i)
        stack.extend(nodes[i].get("children", []))
    return out


@unittest.skipUnless(os.path.isfile(_MANIFEST),
                     "no generated GLB assets yet (html/assets/models)")
class ModelAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mf = json.loads(_read(_MANIFEST))
        cls.gltf = {}
        for section in ("plants", "fauna"):
            for key, entry in cls.mf.get(section, {}).items():
                path = os.path.join(_MODELS, entry["file"])
                if os.path.isfile(path):
                    cls.gltf[entry["file"]] = parse_glb(path)

    # ── manifest ↔ files ────────────────────────────────────────────────────

    def test_manifest_version_and_files(self):
        self.assertEqual(self.mf.get("version"), 1)
        for section in ("plants", "fauna"):
            for key, entry in self.mf.get(section, {}).items():
                path = os.path.join(_MODELS, entry["file"])
                self.assertTrue(os.path.isfile(path),
                                f"{section}.{key}: missing {entry['file']}")

    def test_no_orphan_glbs(self):
        referenced = {e["file"] for s in ("plants", "fauna")
                      for e in self.mf.get(s, {}).values()}
        on_disk = {f for f in os.listdir(_MODELS) if f.endswith(".glb")}
        self.assertEqual(on_disk - referenced, set(),
                         "GLBs on disk that the manifest never references")

    # ── key parity with the viewer's own vocabularies ───────────────────────

    def test_tree_keys_match_viewer_profiles(self):
        src = _read(os.path.join(_SCENE3D, "02-plants.js"))
        prof_ids = set(re.findall(r"id:\s*'(\w+)'", src))
        allowed = ({f"tree.{p}" for p in prof_ids if p != "def"}
                   | {"tree.def_conifer", "tree.def_slender",
                      "tree.def_oval", "tree.def_spreading"})
        tree_keys = {k for k in self.mf["plants"] if k.startswith("tree.")}
        self.assertTrue(tree_keys, "manifest has no tree.* keys")
        self.assertEqual(tree_keys - allowed, set(),
                         "tree keys the viewer would never look up")

    def test_shrub_and_herb_keys_match_viewer_forms(self):
        shrub_src = _read(os.path.join(_SCENE3D, "02-plants.js"))
        m = re.search(r"const SHRUB_FORMS = \{(.*?)\n\};", shrub_src, re.S)
        shrub_forms = set(re.findall(r"^\s{2}(\w+):", m.group(1), re.M))
        herb_src = _read(os.path.join(_SCENE3D, "03-herbs.js"))
        m = re.search(r"const HERB_FORMS = \{(.*?)\n\};", herb_src, re.S)
        herb_forms = set(re.findall(r"^\s{2}(\w+):", m.group(1), re.M))
        self.assertEqual(
            {k.split(".", 1)[1] for k in self.mf["plants"]
             if k.startswith("shrub.")}, shrub_forms)
        self.assertEqual(
            {k.split(".", 1)[1] for k in self.mf["plants"]
             if k.startswith("herb.")}, herb_forms)

    def test_layer_and_fauna_keys_match_viewer(self):
        layers = {k.split(".", 1)[1]: e for k, e in self.mf["plants"].items()
                  if k.startswith("layer.")}
        self.assertEqual(set(layers), {"grass", "aquatic", "vine",
                                       "groundcover"})
        self.assertEqual(layers["groundcover"].get("variants"), 2)
        for kind in ("grass", "aquatic", "vine"):
            self.assertEqual(layers[kind].get("variants"), 3)
        # Fauna keys must cover what 09-models.js maps critter kinds onto.
        src = _read(os.path.join(_SCENE3D, "09-models.js"))
        wanted = set(re.findall(r"key:\s*'(\w+)'", src))
        self.assertEqual(set(self.mf["fauna"]), wanted,
                         "manifest fauna keys != _GLB_CRITTER keys")

    # ── GLB structure ───────────────────────────────────────────────────────

    def test_glbs_have_no_textures(self):
        for fname, (gltf, _bin) in self.gltf.items():
            for bad in ("images", "textures", "samplers"):
                self.assertNotIn(bad, gltf, f"{fname} embeds {bad}")

    def test_plant_glbs_have_position_and_color(self):
        for key, entry in self.mf["plants"].items():
            gltf, _ = self.gltf[entry["file"]]
            for mesh in gltf.get("meshes", []):
                for prim in mesh.get("primitives", []):
                    attrs = prim.get("attributes", {})
                    self.assertIn("POSITION", attrs, f"{key}: no POSITION")
                    self.assertIn("COLOR_0", attrs,
                                  f"{key}: no COLOR_0 (AO) — vertexColors "
                                  f"materials would render black")

    def test_plant_glbs_satisfy_unit_frame(self):
        for key, entry in self.mf["plants"].items():
            gltf, _ = self.gltf[entry["file"]]
            lo_y, hi_y, half = None, None, 0.0
            for mesh in gltf.get("meshes", []):
                for prim in mesh.get("primitives", []):
                    acc = gltf["accessors"][prim["attributes"]["POSITION"]]
                    mn, mx = acc.get("min"), acc.get("max")
                    self.assertIsNotNone(mn, f"{key}: POSITION without min")
                    lo_y = mn[1] if lo_y is None else min(lo_y, mn[1])
                    hi_y = mx[1] if hi_y is None else max(hi_y, mx[1])
                    half = max(half, abs(mn[0]), abs(mx[0]),
                               abs(mn[2]), abs(mx[2]))
            # Loose bounds: the viewer re-normalises; this catches metre- or
            # centimetre-scale exports and off-origin assets outright.
            self.assertGreaterEqual(lo_y, -0.05, f"{key}: base below y=0")
            self.assertLessEqual(lo_y, 0.35, f"{key}: floats above ground")
            self.assertAlmostEqual(hi_y, 1.0, delta=0.1,
                                   msg=f"{key}: height {hi_y} != ~1.0")
            self.assertLessEqual(half, 0.75, f"{key}: wider than unit frame")

    def test_declared_nodes_exist(self):
        for key, entry in self.mf["plants"].items():
            gltf, _ = self.gltf[entry["file"]]
            names = _node_names(gltf)
            for t in entry.get("tiers", []):
                self.assertIn(f"tier{t}", names, f"{key}: tier{t} missing")
                for part in entry["parts"]:
                    self.assertIn(f"tier{t}_{part}", names,
                                  f"{key}: tier{t}_{part} missing")
            for v in range(entry.get("variants", 0)):
                self.assertIn(f"v{v}", names, f"{key}: v{v} missing")
                self.assertIn(f"v{v}_foliage", names,
                              f"{key}: v{v}_foliage missing")
            if "tiers" not in entry and "variants" not in entry:
                for part in entry["parts"]:
                    self.assertIn(part, names, f"{key}: part {part} missing")
        for key, entry in self.mf["fauna"].items():
            gltf, _ = self.gltf[entry["file"]]
            names = _node_names(gltf)
            prefixes = [""]
            if key == "fly":
                prefixes = ["hover_", "darner_"]
                names_ok = {"hover", "darner"} <= names
                self.assertTrue(names_ok, "fly: variant roots missing")
            for node in entry["nodes"]:
                if node in ("hover", "darner"):
                    continue
                found = any(p + node in names for p in prefixes)
                # Rear dragonfly wings exist only on the darner variant.
                if node in ("WingL2", "WingR2"):
                    found = any(p + node in names for p in ["darner_", ""])
                self.assertTrue(found, f"fauna.{key}: node {node} missing")

    def test_fauna_materials_present(self):
        for key, entry in self.mf["fauna"].items():
            gltf, _ = self.gltf[entry["file"]]
            names = {m.get("name", "") for m in gltf.get("materials", [])}
            for mat in entry["materials"]:
                self.assertIn(mat, names, f"fauna.{key}: material {mat}")

    def test_triangle_budgets(self):
        for key, entry in self.mf["plants"].items():
            gltf, _ = self.gltf[entry["file"]]
            kind = key.split(".", 1)[0]
            if kind == "tree":
                # Whole file = 3 tiers; bound by the sum of tier budgets.
                budget = sum(_TRI_BUDGETS[f"tree_tier{t}"]
                             for t in entry["tiers"])
            elif kind == "layer":
                budget = _TRI_BUDGETS["layer"] * entry.get("variants", 1)
            else:
                budget = _TRI_BUDGETS[kind]
            self.assertLessEqual(_tri_count(gltf), budget,
                                 f"{key}: over triangle budget")
        for key, entry in self.mf["fauna"].items():
            gltf, _ = self.gltf[entry["file"]]
            budget = _TRI_BUDGETS["fauna"] * (2 if key == "fly" else 1)
            self.assertLessEqual(_tri_count(gltf), budget,
                                 f"fauna.{key}: over triangle budget")


if __name__ == "__main__":
    unittest.main()
