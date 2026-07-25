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
  names exist, per-unit triangle budgets hold (mirrors assetlib/conventions.py).

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
_TRI_BUDGETS = {"tree_tier0": 1500, "tree_tier1": 2200, "tree_tier2": 3500,
                "shrub": 2000, "herb": 1200, "layer": 900, "fauna": 1500,
                "structure": 1500}


def _assetlib_conventions():
    """assetlib.conventions, or None if it can't be imported.

    It is deliberately bpy-free (the whole generator↔viewer contract in one
    importable place), so the aspect targets can be read here without Blender.
    """
    try:
        sys.path.insert(0, os.path.join(_ROOT, "scripts", "blender"))
        from assetlib import conventions           # noqa: PLC0415
        return conventions
    except Exception:                              # noqa: BLE001
        return None


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


def _prim_tris(gltf, prim):
    if prim.get("mode", 4) != 4:                  # TRIANGLES
        return 0
    accessors = gltf.get("accessors", [])
    if "indices" in prim:
        return accessors[prim["indices"]]["count"] // 3
    return accessors[prim["attributes"]["POSITION"]]["count"] // 3


def _tri_count(gltf):
    """Total triangles across all mesh primitives (indexed or not)."""
    return sum(_prim_tris(gltf, prim)
               for mesh in gltf.get("meshes", [])
               for prim in mesh.get("primitives", []))


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


def _tri_count_under(gltf, root_idx):
    """Triangles in the meshes parented under one unit root.

    A tier or a variant is what the viewer instances, so the budget belongs to
    the unit; the whole file only bounds their sum, and a file holding eleven
    variants would let any one of them balloon unnoticed.
    """
    nodes = gltf.get("nodes", [])
    total = 0
    for i in _mesh_nodes_under(gltf, root_idx):
        if "mesh" not in nodes[i]:
            continue
        for prim in gltf["meshes"][nodes[i]["mesh"]].get("primitives", []):
            total += _prim_tris(gltf, prim)
    return total


def _unit_count(entry):
    """How many variant units a manifest entry declares — a plain count for the
    layer kinds, one per (blade class, grain class) for herbs and shrubs."""
    return entry.get("variants", 0) or len(entry.get("variant_keys", {}))


@unittest.skipUnless(os.path.isfile(_MANIFEST),
                     "no generated GLB assets yet (html/assets/models)")
class ModelAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mf = json.loads(_read(_MANIFEST))
        cls.gltf = {}
        for section in ("plants", "fauna", "structures"):
            for key, entry in cls.mf.get(section, {}).items():
                path = os.path.join(_MODELS, entry["file"])
                if os.path.isfile(path):
                    cls.gltf[entry["file"]] = parse_glb(path)

    # ── manifest ↔ files ────────────────────────────────────────────────────

    def test_manifest_version_and_files(self):
        self.assertEqual(self.mf.get("version"), 1)
        for section in ("plants", "fauna", "structures"):
            for key, entry in self.mf.get(section, {}).items():
                path = os.path.join(_MODELS, entry["file"])
                self.assertTrue(os.path.isfile(path),
                                f"{section}.{key}: missing {entry['file']}")

    def test_no_orphan_glbs(self):
        referenced = {e["file"] for s in ("plants", "fauna", "structures")
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

    def test_viewer_leaf_classifiers_match_the_generator(self):
        """The viewer picks a plant's baked archetype by (blade class, grain
        class); the generator decides which of those to bake. Two independent
        implementations of the same classification is the whole risk: drift one
        break and a species silently falls back to the neutral variant, losing
        exactly the identity this machinery exists to give it. So extract the
        viewer's real tables and compare, rather than restating them here.
        """
        conventions = _assetlib_conventions()
        if conventions is None:
            self.skipTest("assetlib.conventions not importable")
        src = _read(os.path.join(_SCENE3D, "02-plants.js"))

        def js_list(name):
            m = re.search(r"const " + name + r" = \[(.*?)\];", src, re.S)
            self.assertIsNotNone(m, f"02-plants.js: {name} not found")
            return re.findall(r"'([\w]+)'", m.group(1))

        self.assertEqual(js_list("BLADE_CLASSES"),
                         list(conventions.BLADE_CLASSES))
        # Each shape list feeds one class; walking them proves the whole mapping
        # agrees, including which shapes are absent (→ 'broad').
        for name, cls in (("_COMPOUND_SHAPES", "compound"),
                          ("_NARROW_SHAPES", "narrow"),
                          ("_CUT_SHAPES", "cut")):
            for shape in js_list(name):
                self.assertEqual(conventions.blade_class(shape), cls,
                                 f"{shape}: viewer says {cls}, generator "
                                 f"says {conventions.blade_class(shape)}")
        m = re.search(r"const GRAIN_LEAF_SCALE = \[([^\]]*)\]", src)
        self.assertIsNotNone(m, "02-plants.js: GRAIN_LEAF_SCALE not found")
        self.assertEqual([float(x) for x in m.group(1).split(",")],
                         list(conventions.GRAIN_LEAF_SCALE))
        m = re.search(r"const _GRAIN_BREAKS = \{(.*?)\};", src, re.S)
        self.assertIsNotNone(m, "02-plants.js: _GRAIN_BREAKS not found")
        breaks = {fam: (float(lo), float(hi)) for fam, lo, hi in re.findall(
            r"(\w+):\s*\[([\d.]+),\s*([\d.]+)\]", m.group(1))}
        self.assertEqual(breaks, {k: tuple(v) for k, v in
                                  conventions._GRAIN_BREAKS.items()})

    def test_each_blade_class_is_baked_as_a_typical_member(self):
        """A blade class stands for its species, so the outline it is baked with
        must be typical of them — specifically the member whose width/length sits
        at the class median.

        This is the check the aster regression needed. 'narrow' was baked as
        `linear` (width/length 0.06) while 65 of its 100 species are `lanceolate`
        (0.22) and only 22 truly linear, so the largest group of wildflowers drew
        leaves 3.7x too narrow — thick bare stems with invisible threads on them.
        Nothing caught it: the geometry was valid, budgeted, correctly
        proportioned overall, and the right variant was being selected. Only the
        blade WIDTH was wrong, and no test looked at width.
        """
        conventions = _assetlib_conventions()
        if conventions is None:
            self.skipTest("assetlib.conventions not importable")
        # LEAF_WIDTH_RATIO lives in the bpy-importing mesh_ops; read it as data
        # rather than dragging Blender into the ordinary suite.
        src = _read(os.path.join(_ROOT, "scripts", "blender", "assetlib",
                                 "mesh_ops.py"))
        blob = re.search(r"LEAF_WIDTH_RATIO = \{(.*?)\}", src, re.S)
        self.assertIsNotNone(blob, "mesh_ops.LEAF_WIDTH_RATIO not found")
        ratio = {k: float(v) for k, v in
                 re.findall(r'"(\w+)":\s*([\d.]+)', blob.group(1))}
        catalogue = json.loads(_read(os.path.join(_ROOT, "data",
                                                 "plants_master.json")))
        served = set()
        for types, _form_of in conventions.FAMILY_FORMS.values():
            served |= set(types)
        for cls in conventions.BLADE_CLASSES:
            members = [r.get("leaf_shape") for r in catalogue
                       if r.get("plant_type") in served
                       and conventions.blade_class(r.get("leaf_shape")) == cls]
            ratios = sorted(ratio[s] for s in members if s in ratio)
            if not ratios:
                continue
            median = ratios[len(ratios) // 2] if len(ratios) % 2 else (
                (ratios[len(ratios) // 2 - 1] + ratios[len(ratios) // 2]) / 2)
            baked = conventions.BLADE_SHAPE[cls]
            self.assertIn(baked, ratio, f"{cls}: baked shape {baked} has no ratio")
            self.assertAlmostEqual(
                ratio[baked], median, delta=0.08,
                msg=f"blade class '{cls}' is baked as '{baked}' "
                    f"(width/length {ratio[baked]}) but its {len(ratios)} "
                    f"species run {ratios[0]}–{ratios[-1]} with median {median} "
                    f"— the class is being drawn at the edge of its range "
                    f"instead of the middle of it.")

    def test_every_catalogue_species_resolves_to_a_baked_variant(self):
        """No herb or shrub in the shipped catalogue may ask for a variant the
        manifest doesn't carry. The generator reads the same catalogue, so this
        holds by construction — until someone adds a species and forgets to
        rebuild the assets, which is precisely when it should fail."""
        conventions = _assetlib_conventions()
        if conventions is None:
            self.skipTest("assetlib.conventions not importable")
        path = os.path.join(_ROOT, "data", "plants_master.json")
        catalogue = json.loads(_read(path))
        checked = 0
        for family, (types, form_of) in conventions.FAMILY_FORMS.items():
            for rec in catalogue:
                if rec.get("plant_type") not in types:
                    continue
                entry = self.mf["plants"].get(f"{family}.{form_of(rec)}")
                self.assertIsNotNone(entry, f"{family}.{form_of(rec)} missing")
                want = conventions.variant_key(
                    conventions.blade_class(rec.get("leaf_shape")),
                    conventions.grain_class(rec.get("leaf_size_cm"),
                                            rec.get("mature_height_m"), family))
                self.assertIn(
                    want, entry.get("variant_keys", {}),
                    f"{rec.get('scientific_name')}: no baked {want} variant "
                    f"for {family}.{form_of(rec)} — rebuild html/assets/models")
                checked += 1
        # 284 today (229 herbaceous + 55 shrubs). The grass/sedge/vine/aquatic/
        # groundcover types are deliberately outside this guard: they map to the
        # layer.* archetypes, which carry plain variants rather than morphology
        # ones. The floor only has to catch the lookup silently going empty.
        self.assertGreater(checked, 250, "catalogue stopped resolving")

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

    def _plant_bounds(self, key, entry):
        """(lo_y, hi_y, half_width) over every primitive in a plant GLB."""
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
        return lo_y, hi_y, half

    def test_plant_glbs_satisfy_unit_frame(self):
        for key, entry in self.mf["plants"].items():
            lo_y, hi_y, _half = self._plant_bounds(key, entry)
            # Catches metre- or centimetre-scale exports and off-origin assets.
            self.assertGreaterEqual(lo_y, -0.05, f"{key}: base below y=0")
            self.assertLessEqual(lo_y, 0.35, f"{key}: floats above ground")
            self.assertAlmostEqual(hi_y, 1.0, delta=0.1,
                                   msg=f"{key}: height {hi_y} != ~1.0")

    def test_plant_glbs_are_authored_at_their_species_aspect(self):
        """Each archetype's height ÷ width must match the real proportions of
        the species that map to it (assetlib.conventions).

        This is the guard the V2.29 fix needed and didn't have: assets were
        authored 1:1 and instanced by (canopy_m, height_m, canopy_m), so a
        3.3:1 spruce or 4.2:1 pine had every foliage clump stretched by that
        factor — and *every* existing check passed, because triangle counts,
        node names and materials were all still correct. Proportion is the
        thing a silhouette regression shows up in first.
        """
        conventions = _assetlib_conventions()
        if conventions is None:
            self.skipTest("assetlib.conventions not importable")
        checked = 0
        for key, entry in self.mf["plants"].items():
            target = conventions.aspect_for(key)
            if target is None:
                continue
            _lo, hi_y, half = self._plant_bounds(key, entry)
            got = hi_y / max(1e-6, 2 * half)
            # 35%: one archetype serves several species, and the builders shape
            # to the target rather than solving for it exactly. The failure this
            # guards against is a factor of 2–4, not a fifth.
            self.assertAlmostEqual(
                got / target, 1.0, delta=0.35,
                msg=f"{key}: aspect {got:.2f} vs {target:.2f} for its species "
                    f"— the archetype is being authored at the wrong "
                    f"proportions, which the instance transform will turn into "
                    f"stretched foliage")
            checked += 1
        self.assertGreater(checked, 20, "aspect targets stopped resolving")

    def test_manifest_half_widths_match_the_shipped_geometry(self):
        """The published half_width is what the viewer divides the canopy scale
        by, so a stale manifest silently mis-sizes every plant."""
        for key, entry in self.mf["plants"].items():
            declared = entry.get("half_width")
            if not declared:
                continue
            _lo, _hi, half = self._plant_bounds(key, entry)
            widest = max(declared.values())
            self.assertAlmostEqual(
                widest, half, delta=0.05,
                msg=f"{key}: manifest half_width {widest} != geometry {half} "
                    f"— regenerate the manifest with the GLBs")

    def _part_top(self, gltf, unit, part):
        """Highest y of one named part of one unit, or None if absent."""
        nodes = gltf.get("nodes", [])
        idx = {n.get("name", ""): i for i, n in enumerate(nodes)}
        i = idx.get(f"{unit}_{part}")
        if i is None or "mesh" not in nodes[i]:
            return None
        hi = None
        for prim in gltf["meshes"][nodes[i]["mesh"]].get("primitives", []):
            acc = gltf["accessors"][prim["attributes"]["POSITION"]]
            top = acc.get("max", [0, 0, 0])[1]
            hi = top if hi is None else max(hi, top)
        return hi

    def test_foliage_reaches_the_top_of_every_woody_unit(self):
        """A woody plant's leaves must clothe it to the tip.

        The regression a user's screenshot caught in V2.29: the rebuilt shrub
        builder hung leaves only on twigs and sprouted every twig from one node,
        so foliage stopped at 78% of a vase shrub's height and 54% of a spreading
        one — half the plant was naked cane in midsummer, reading as a dead bush.
        Every existing guard passed: triangle budgets, node names, unit-frame
        bounds, the manifest, and the authored ASPECT (which compares the plant's
        overall height to its overall width, and so is blind to *which part* is
        up there). The render gate was blind too — it measures the union of all
        parts, and the bark reached full height the whole time.

        So the missing check is per-part vertical coverage. Deliberately loose at
        90%: a bare lower cane is correct (that is what a vase shrub IS), and the
        topmost twig may sit slightly under the tallest stem. What it catches is
        a fifth or more of the plant going bare.
        """
        checked = 0
        for key, entry in self.mf["plants"].items():
            if "bark" not in entry.get("parts", []):
                continue                       # herbs/layers are one green part
            gltf, _ = self.gltf[entry["file"]]
            units = [f"tier{t}" for t in entry.get("tiers", [])]
            units += [f"v{v}" for v in range(_unit_count(entry))]
            for unit in units:
                foliage = self._part_top(gltf, unit, "foliage")
                bark = self._part_top(gltf, unit, "bark")
                if foliage is None or not bark:
                    continue
                self.assertGreaterEqual(
                    foliage, bark * 0.90,
                    f"{key}/{unit}: foliage tops out at {foliage:.2f} while the "
                    f"bark reaches {bark:.2f} — the upper "
                    f"{(1 - foliage / bark) * 100:.0f}% of this plant is bare "
                    f"wood in midsummer.")
                checked += 1
        self.assertGreater(checked, 20, "woody units stopped resolving")

    def test_declared_nodes_exist(self):
        for key, entry in self.mf["plants"].items():
            gltf, _ = self.gltf[entry["file"]]
            names = _node_names(gltf)
            for t in entry.get("tiers", []):
                self.assertIn(f"tier{t}", names, f"{key}: tier{t} missing")
                for part in entry["parts"]:
                    self.assertIn(f"tier{t}_{part}", names,
                                  f"{key}: tier{t}_{part} missing")
            for v in range(_unit_count(entry)):
                self.assertIn(f"v{v}", names, f"{key}: v{v} missing")
                # Every declared part, not just foliage: a shrub variant carries
                # its own canes, and _glbLoadPlant looks them up by exact name.
                for part in entry["parts"]:
                    self.assertIn(f"v{v}_{part}", names,
                                  f"{key}: v{v}_{part} missing")
            if not entry.get("tiers") and not _unit_count(entry):
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

    def test_structure_keys_match_catalogue(self):
        # The placeable ids are string literals in src/db/structures.py;
        # the existing_* ids use constants, so this regex excludes them.
        src = _read(os.path.join(_ROOT, "src", "db", "structures.py"))
        ids = set(re.findall(r'"id":\s*"(\w+)"', src))
        section = self.mf.get("structures", {})
        if not section:
            self.skipTest("manifest has no structures section yet")
        self.assertEqual(set(section), ids,
                         "manifest structure keys != placeable catalogue ids")
        for key, entry in section.items():
            self.assertIn(entry.get("scale_mode"), ("uniform", "footprint"),
                          f"structure.{key}: bad scale_mode")
            self.assertGreater(entry.get("size_m", 0), 0)
            self.assertGreater(entry.get("height_m", 0), 0)

    def test_structure_glbs_sane(self):
        for key, entry in self.mf.get("structures", {}).items():
            gltf, _ = self.gltf[entry["file"]]
            half_max = entry["size_m"] * 0.60      # authored long side / 2 + slack
            lo_y, hi_y, half = None, 0.0, 0.0
            for mesh in gltf.get("meshes", []):
                for prim in mesh.get("primitives", []):
                    attrs = prim.get("attributes", {})
                    self.assertIn("COLOR_0", attrs,
                                  f"structure.{key}: no baked AO")
                    acc = gltf["accessors"][attrs["POSITION"]]
                    mn, mx = acc["min"], acc["max"]
                    lo_y = mn[1] if lo_y is None else min(lo_y, mn[1])
                    hi_y = max(hi_y, mx[1])
                    half = max(half, abs(mn[0]), abs(mx[0]),
                               abs(mn[2]), abs(mx[2]))
            # Stones/berms seat INTO the ground by design — allow a
            # shallow burial, but catch a whole sunken asset.
            self.assertGreaterEqual(lo_y, -0.15, f"{key}: below ground")
            self.assertLessEqual(half, half_max,
                                 f"{key}: wider than authored size_m")
            self.assertLessEqual(hi_y, entry["height_m"] * 1.3 + 0.15,
                                 f"{key}: taller than authored height_m")
            self.assertLessEqual(_tri_count(gltf),
                                 _TRI_BUDGETS["structure"],
                                 f"structure.{key}: over triangle budget")

    def test_fauna_materials_present(self):
        for key, entry in self.mf["fauna"].items():
            gltf, _ = self.gltf[entry["file"]]
            names = {m.get("name", "") for m in gltf.get("materials", [])}
            for mat in entry["materials"]:
                self.assertIn(mat, names, f"fauna.{key}: material {mat}")

    def test_triangle_budgets(self):
        """Per unit, matching what the builder enforces (see _tri_count_under)."""
        for key, entry in self.mf["plants"].items():
            gltf, _ = self.gltf[entry["file"]]
            kind = key.split(".", 1)[0]
            idx = {n.get("name", ""): i
                   for i, n in enumerate(gltf.get("nodes", []))}
            units = [(f"tier{t}", _TRI_BUDGETS[f"tree_tier{t}"])
                     for t in entry.get("tiers", [])]
            units += [(f"v{v}", _TRI_BUDGETS[kind])
                      for v in range(_unit_count(entry))]
            if not units:                       # single-unit file
                self.assertLessEqual(_tri_count(gltf), _TRI_BUDGETS[kind],
                                     f"{key}: over triangle budget")
                continue
            for name, budget in units:
                self.assertIn(name, idx, f"{key}: unit {name} missing")
                self.assertLessEqual(
                    _tri_count_under(gltf, idx[name]), budget,
                    f"{key}/{name}: over triangle budget")
        for key, entry in self.mf["fauna"].items():
            gltf, _ = self.gltf[entry["file"]]
            budget = _TRI_BUDGETS["fauna"] * (2 if key == "fly" else 1)
            self.assertLessEqual(_tri_count(gltf), budget,
                                 f"fauna.{key}: over triangle budget")


if __name__ == "__main__":
    unittest.main()
