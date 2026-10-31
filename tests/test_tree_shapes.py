"""
tests/test_tree_shapes.py — the trees the V2.87 audit found drawn as something
else (F178, V2.92).

The audit listed eleven: an elm and a box elder on the generic defaults, two
cottonwoods borrowing the trembling aspen (stretched 1.6x), Peach-leaved Willow
borrowing Bebb's, a juniper drawn as a spruce, water birch and Bebb's willow on a
single trunk though both are recorded ``multi_stem``, and both pines as bottle
brushes. Black Spruce, the eleventh, stays White Spruce's model on purpose
(02-plants.js carries the reason).

Every assertion here is a structural fact about the SHIPPED model, measured from
the GLB the way test_model_assets.py reads one (stdlib only: no Blender, no
three.js). Run against the models and viewer V2.91 shipped, all of them fail but
the ground-contact guard, which is here because a juniper built during V2.92 had
its youngest trunk standing on its own foliage:

* each species resolves, through the viewer's own tables, to an archetype of its
  own that is baked;
* a multi-stemmed tree leaves the ground as separate stems;
* the elm's trunk divides into leaders low down, which is the vase;
* the lodgepole's limbs come in whorls, storeys of wood with bare trunk between;
* the jack pine keeps dead stubs below its crown on a crooked trunk;
* the juniper is a cone foliated to the ground;
* and no tree stands clear of the ground (the first juniper did, at its
  youngest).

The last class runs the viewer's procedural generator in Node, because Stylised
draws these trees without the baked models, on purpose.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_model_assets import _read_accessor, parse_glb  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODELS = os.path.join(_ROOT, "html", "assets", "models")
_MANIFEST = os.path.join(_MODELS, "manifest.json")
_SCENE3D = os.path.join(_ROOT, "html", "scene3d")
_PLANTS = os.path.join(_ROOT, "data", "plants_master.json")

# Scientific name -> the archetype it is drawn with since V2.92.
_AUDIT_TREES = {
    "Ulmus americana": "elm",
    "Acer negundo": "boxelder",
    "Populus deltoides": "cottonwood",
    "Populus angustifolia": "cottonwood_narrow",
    "Salix amygdaloides": "willow_peach",
    "Juniperus scopulorum": "juniper",
    "Betula occidentalis": "birch_water",
    "Salix bebbiana": "willow",
    "Pinus contorta": "pine",
    "Pinus banksiana": "pine_jack",
}


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# ── geometry, read from a GLB ────────────────────────────────────────────────

def _part(gltf, binary, name):
    """(positions, triangles) of one named node, positions as (x, y, z) with y
    up. Triangles index the positions list."""
    idx = {n.get("name", ""): i for i, n in enumerate(gltf.get("nodes", []))}
    node = gltf["nodes"][idx[name]]
    pos, tris = [], []
    for prim in gltf["meshes"][node["mesh"]].get("primitives", []):
        base = len(pos)
        pos.extend(_read_accessor(gltf, binary, prim["attributes"]["POSITION"]))
        ind = [i[0] for i in _read_accessor(gltf, binary, prim["indices"])]
        tris.extend((base + ind[k], base + ind[k + 1], base + ind[k + 2])
                    for k in range(0, len(ind) - 2, 3))
    return pos, tris


def _pieces(pos, tris):
    """Group triangles into separate pieces of geometry.

    Vertices are merged by position first: the exporter splits a flat-shaded
    mesh into one vertex per face corner, so shared indices say nothing, but a
    branch's cone and the next one up the trunk meet at the same points.
    """
    key, parent = {}, []

    def vid(i):
        k = tuple(round(c, 5) for c in pos[i])
        if k not in key:
            key[k] = len(parent)
            parent.append(len(parent))
        return key[k]

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    ids = [tuple(vid(i) for i in t) for t in tris]
    for a, b, c in ids:
        for u, v in ((a, b), (b, c)):
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv
    groups = {}
    for t, (a, _b, _c) in zip(tris, ids):
        groups.setdefault(find(a), []).append(t)
    return list(groups.values())


def _slice(pos, tris, h):
    """How many separate pieces of wood a horizontal plane at ``h`` cuts."""
    cut = [t for t in tris
           if min(pos[i][1] for i in t) < h < max(pos[i][1] for i in t)]
    return len(_pieces(pos, cut)) if cut else 0


def _percentile(values, q):
    s = sorted(values)
    return s[min(len(s) - 1, int(len(s) * q))]


@unittest.skipUnless(os.path.isfile(_MANIFEST),
                     "no generated GLB assets yet (html/assets/models)")
class TreeShapesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mf = json.loads(_read(_MANIFEST))
        cls._units = {}

    def _unit(self, arch, tier):
        """(bark positions, bark tris, foliage positions, height) of one tier."""
        k = (arch, tier)
        if k not in self._units:
            entry = self.mf["plants"][f"tree.{arch}"]
            gltf, binary = parse_glb(os.path.join(_MODELS, entry["file"]))
            bp, bt = _part(gltf, binary, f"tier{tier}_bark")
            fp, _ft = _part(gltf, binary, f"tier{tier}_foliage")
            h = max(max(p[1] for p in bp), max(p[1] for p in fp))
            self._units[k] = (bp, bt, fp, h)
        return self._units[k]

    def _tiers(self, arch):
        return self.mf["plants"][f"tree.{arch}"].get("tiers", [0, 1, 2])

    # ── the viewer draws each of them as itself ─────────────────────────────

    def test_each_audit_tree_resolves_to_its_own_baked_model(self):
        """Through the viewer's own tables, not a copy of them: 02-plants.js
        looks a tree up by species, then by genus, then falls to a generic
        default chosen by its proportions. Before V2.92 the two cottonwoods
        landed on the aspen's genus row and Peach-leaved Willow on Bebb's, and
        the rest had no row at all."""
        src = _read(os.path.join(_SCENE3D, "02-plants.js"))
        prof = {}
        for m in re.finditer(r"^\s+(\w+):\s*\{\s*id:\s*'(\w+)'([^}]*)\}", src,
                             re.M):
            conifer = re.search(r"conifer:\s*'(\w+)'", m.group(3))
            prof[m.group(1)] = (m.group(2), conifer and conifer.group(1))
        block = re.search(r"const TREE_SPECIES_PROFILES = \{(.*?)\n\};", src,
                          re.S).group(1)
        species = dict(re.findall(r"'([a-z ]+)':\s*_PROF\.(\w+)", block))
        block = re.search(r"const TREE_PROFILES = \{(.*?)\n\};", src,
                          re.S).group(1)
        genus = dict(re.findall(r"(\w+):\s*_PROF\.(\w+)", block))

        catalogue = {r.get("scientific_name"): r
                     for r in json.loads(_read(_PLANTS))
                     if isinstance(r, dict)}
        seen = {}
        for name, want in _AUDIT_TREES.items():
            with self.subTest(species=name):
                self.assertIn(name, catalogue,
                              f"{name} is no longer in the catalogue; this "
                              f"list needs its new name")
                row = species.get(name.lower()) or genus.get(
                    name.split()[0].lower())
                self.assertIsNotNone(
                    row, f"{name} has no row in the viewer's tree tables, so "
                         f"it falls to a generic default")
                pid, conifer = prof[row]
                arch = conifer or pid
                self.assertEqual(arch, want,
                                 f"{name} is drawn as '{arch}', not '{want}'")
                self.assertIn(f"tree.{arch}", self.mf["plants"],
                              f"{name}: tree.{arch} is not baked, so the "
                              f"viewer would fall back to a default")
                seen.setdefault(arch, []).append(name)
        shared = {a: n for a, n in seen.items() if len(n) > 1}
        self.assertEqual(shared, {}, "audit trees sharing one model")

    # ── multiple stems ──────────────────────────────────────────────────────

    def _ground_stems(self, arch, tier):
        bp, bt, _fp, h = self._unit(arch, tier)
        low = [t for t in bt if max(bp[i][1] for i in t) < 0.01 * h]
        return len(_pieces(bp, low))

    def test_multi_stemmed_trees_leave_the_ground_as_separate_stems(self):
        """Water birch and Bebb's willow are recorded ``multi_stem``; box elder
        is described as often several-trunked. Until V2.92 the generator grew
        every tree from one walk, so no archetype could have a second stem."""
        for arch, least in (("birch_water", 3), ("willow", 3),
                            ("boxelder", 2)):
            for tier in self._tiers(arch):
                with self.subTest(arch=arch, tier=tier):
                    n = self._ground_stems(arch, tier)
                    self.assertGreaterEqual(
                        n, least, f"tree.{arch}/tier{tier} leaves the ground "
                                  f"as {n} stem(s)")

    def test_no_tree_stands_clear_of_the_ground(self):
        """Every tree's wood reaches y=0. The unit frame puts the LOWEST vertex
        at the ground, so foliage hanging below a trunk's base lifts the whole
        tree; the first juniper's youngest tier did exactly that."""
        for key in (k for k in self.mf["plants"] if k.startswith("tree.")):
            arch = key.split(".", 1)[1]
            for tier in self._tiers(arch):
                with self.subTest(arch=arch, tier=tier):
                    self.assertGreaterEqual(
                        self._ground_stems(arch, tier), 1,
                        f"{key}/tier{tier}: no wood within 1% of the ground; "
                        f"the trunk stands on its own foliage")

    # ── the elm's vase ──────────────────────────────────────────────────────

    def test_the_elm_divides_into_leaders_low_down(self):
        """The American Elm's vase is a short trunk forking low into several
        steep leaders. At 30% of its height the generic oval it used to borrow
        is still one trunk."""
        for tier in self._tiers("elm"):
            bp, bt, _fp, h = self._unit("elm", tier)
            with self.subTest(tier=tier):
                n = _slice(bp, bt, 0.30 * h)
                self.assertGreaterEqual(
                    n, 3, f"tree.elm/tier{tier}: {n} limb(s) at 30% of the "
                          f"height; a vase has divided into leaders by then")

    # ── the pines ───────────────────────────────────────────────────────────

    def _storeys(self, arch, tier, least=4):
        """Storeys of limbs in the live crown: runs of height where a slice
        cuts more than the trunk, each at its busiest cutting at least
        ``least`` pieces of wood, with bare trunk between them."""
        bp, bt, fp, h = self._unit(arch, tier)
        base = _percentile([p[1] for p in fp], 0.02)
        n, busiest, z = 0, 0, base
        while z < 0.98 * h:
            c = _slice(bp, bt, z)
            if c >= 2:
                busiest = max(busiest, c)
            else:
                n += busiest >= least
                busiest = 0
            z += 0.004 * h
        return n + (busiest >= least)

    def test_the_lodgepole_crown_is_storeyed_not_a_brush(self):
        """A pine is read by its limbs: whorls of them, foliage clustered at
        their ends, sky between the whorls. The builder V2.92 replaced spread
        one tuft per height evenly up the trunk, so a slice anywhere in the
        crown cut much the same wood, the audit's "bottle brush"."""
        for tier in self._tiers("pine"):
            with self.subTest(tier=tier):
                n = self._storeys("pine", tier)
                self.assertGreaterEqual(
                    n, 4, f"tree.pine/tier{tier}: {n} storeys of limbs in the "
                          f"crown")

    def test_the_jack_pine_keeps_dead_stubs_on_a_crooked_trunk(self):
        """Jack pine's field marks below the crown: dead branches it does not
        shed, on a trunk that wanders. The old builder drew a straight pole
        with nothing on it below the foliage."""
        for tier in self._tiers("pine_jack"):
            bp, bt, fp, h = self._unit("pine_jack", tier)
            base = _percentile([p[1] for p in fp], 0.02)
            stubs = 0
            for piece in _pieces(bp, bt):
                ys = [bp[i][1] for t in piece for i in t]
                if max(ys) >= base:
                    continue
                xs = [bp[i][0] for t in piece for i in t]
                zs = [bp[i][2] for t in piece for i in t]
                # Out sideways rather than up: a stub, not a length of trunk.
                if max(ys) - min(ys) < max(max(xs) - min(xs),
                                           max(zs) - min(zs)):
                    stubs += 1
            # The trunk is the piece that stands on the ground; stubs are cut
            # by the same slices, so they are left out of its centre line.
            trunk = min(_pieces(bp, bt),
                        key=lambda pc: min(bp[i][1] for t in pc for i in t))
            centres = []
            for f in (0.04, 0.08, 0.12, 0.16, 0.20, 0.24, 0.28):
                hh = f * h
                if hh >= base:
                    continue
                pts = []
                for t in trunk:
                    for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                        pa, pb = bp[a], bp[b]
                        if (pa[1] - hh) * (pb[1] - hh) < 0:
                            u = (hh - pa[1]) / (pb[1] - pa[1])
                            pts.append((pa[0] + (pb[0] - pa[0]) * u,
                                        pa[2] + (pb[2] - pa[2]) * u))
                centres.append((sum(p[0] for p in pts) / len(pts),
                                sum(p[1] for p in pts) / len(pts)))
            wander = max((((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
                          for a in centres for b in centres), default=0.0)
            with self.subTest(tier=tier):
                self.assertGreaterEqual(
                    stubs, 4, f"tree.pine_jack/tier{tier}: {stubs} dead "
                              f"stub(s) below the crown")
                self.assertGreaterEqual(
                    wander / h, 0.006, f"tree.pine_jack/tier{tier}: the trunk "
                                       f"wanders {wander / h:.4f} of the "
                                       f"height; it is a straight pole")

    # ── the juniper ─────────────────────────────────────────────────────────

    def test_the_juniper_is_a_cone_foliated_to_the_ground(self):
        """Rocky Mountain Juniper: a dense irregular cone, foliage nearly to
        the ground, widest low down. It was drawn as a spruce's tiers."""
        for tier in self._tiers("juniper"):
            _bp, _bt, fp, h = self._unit("juniper", tier)
            ys = [p[1] for p in fp]
            widths = []
            for k in range(10):
                band = [(p[0] ** 2 + p[2] ** 2) ** 0.5 for p in fp
                        if h * k / 10 <= p[1] < h * (k + 1) / 10]
                widths.append(_percentile(band, 0.95) if len(band) > 20
                              else 0.0)
            widest = max(range(10), key=lambda k: widths[k])
            with self.subTest(tier=tier):
                self.assertLessEqual(_percentile(ys, 0.02), 0.10 * h,
                                     "foliage does not reach near the ground")
                self.assertLess(widest, 4, f"widest at band {widest} of 10; "
                                           f"a cone is widest low down")
                self.assertLess(widths[9], 0.6 * widths[widest],
                                "the top is as broad as the base")


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def _lift(src, pattern, what):
    m = re.search(pattern, src, re.S | re.M)
    if not m:
        raise AssertionError(f"{what} is gone from the viewer; this test lifts "
                             f"it by name")
    return m.group(0)


@unittest.skipIf(_node() is None, "no node binary")
class ProceduralTreeArchitectureTest(unittest.TestCase):
    """Stylised draws trees with the viewer's own generator (03b-trees.js),
    not the baked models, so the architecture has to be there too: the clump
    of stems and the elm's first fork. Lifted out of the viewer and run in
    Node; the skeleton needs no three.js. Lifted from all the chunks at once,
    because which chunk holds a builder is housekeeping: 03-herbs.js held
    these until it outgrew its ceiling."""

    @classmethod
    def setUpClass(cls):
        viewer = "\n".join(_read(os.path.join(_SCENE3D, n))
                           for n in sorted(os.listdir(_SCENE3D))
                           if n.endswith(".js"))
        parts = [_lift(viewer, r"^function mulberry32\(.*?^\}", "mulberry32")]
        for name in ("DECID_CFG", "DECID_FORMS", "DECID_DEPTH", "_PROF",
                     "TREE_PROFILES", "TREE_SPECIES_PROFILES"):
            parts.append(_lift(viewer, rf"^const {name} = .*?;$", name))
        for fn in ("profileFor", "formOf", "treeFormFor", "decidCfg",
                   "generateClump", "generateDaVinciTree"):
            parts.append(_lift(viewer, rf"^function {fn}\(.*?^\}}", fn))
        trees = [
            {"species": "Betula occidentalis", "genus": "Betula",
             "height_m": 8, "canopy_m": 4.5, "branching": "multi_stem"},
            {"species": "Salix bebbiana", "genus": "Salix",
             "height_m": 8, "canopy_m": 4.5, "branching": "multi_stem"},
            {"species": "Acer negundo", "genus": "Acer",
             "height_m": 15, "canopy_m": 12, "branching": "decurrent"},
            {"species": "Ulmus americana", "genus": "Ulmus",
             "height_m": 25, "canopy_m": 15, "branching": "decurrent"},
            {"species": "Populus deltoides", "genus": "Populus",
             "height_m": 25, "canopy_m": 15, "branching": "decurrent"},
            {"species": "Populus tremuloides", "genus": "Populus",
             "height_m": 20, "canopy_m": 7.5, "branching": "excurrent"},
        ]
        script = "\n".join(parts) + """
const out = {};
for (const p of %s) {
  const prof = profileFor(p);
  const cfg = decidCfg(treeFormFor(p, prof), 2, prof);
  const root = generateDaVinciTree(0.06, 0.42, 0, cfg, mulberry32(1234));
  out[p.species] = { clump: !!root.clump, first: root.children.length };
}
console.log(JSON.stringify(out));
""" % json.dumps(trees)
        proc = subprocess.run([_node(), "-e", script], capture_output=True,
                              text=True, timeout=60, encoding="utf-8")
        if proc.returncode != 0:
            raise AssertionError(f"node failed: {proc.stderr}")
        cls.trees = json.loads(proc.stdout)

    def test_the_multi_stemmed_trees_are_clumps(self):
        for name, least in (("Betula occidentalis", 3), ("Salix bebbiana", 3),
                            ("Acer negundo", 2)):
            with self.subTest(species=name):
                t = self.trees[name]
                self.assertTrue(t["clump"], f"{name} grows one trunk")
                self.assertGreaterEqual(t["first"], least)

    def test_the_elm_and_the_cottonwood_fork_into_leaders(self):
        for name, least in (("Ulmus americana", 4), ("Populus deltoides", 3)):
            with self.subTest(species=name):
                t = self.trees[name]
                self.assertFalse(t["clump"])
                self.assertGreaterEqual(
                    t["first"], least, f"{name}'s trunk forks in "
                                       f"{t['first']}, not into leaders")

    def test_a_tree_without_the_architecture_is_unchanged(self):
        """The aspen has none of it: one trunk forking in twos and threes, as
        every tree did before V2.92."""
        t = self.trees["Populus tremuloides"]
        self.assertFalse(t["clump"])
        self.assertIn(t["first"], (2, 3))


if __name__ == "__main__":
    unittest.main()
