"""
tests/test_colour_checks.py — flower colours checked against photographs
(V3.33, F172): the list to look at, the answers, and the fold-in.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from src import colour_checks as cc  # noqa: E402
from src import flower_colour  # noqa: E402

import fetch_colour_evidence as fetch  # noqa: E402
import fold_colour_answers as fold  # noqa: E402


def _row(sci, common, hexval="", source="", ptype="wildflower", colours=""):
    return {"scientific_name": sci, "common_name": common, "plant_type": ptype,
            "flower_color": hexval, "flower_colour_source": source,
            "flower_colours": colours}


ROWS = [
    _row("Ratibida columnifera", "Prairie Coneflower", "#8e6fc4", "flora"),
    _row("Solidago a", "Goldenrod A", "#f2c11e", "estimated"),
    _row("Solidago b", "Goldenrod B", "#f2c11e", "estimated"),
    _row("Aster c", "Aster C", "#8e6fc4", "estimated"),
    _row("Aquilegia flavescens", "Yellow Columbine", "#f2c11e", "epithet"),
    _row("Picea glauca", "White Spruce", "", "", "tree"),
    _row("Bouteloua gracilis", "Blue Grama", "#cbbd80", "estimated", "grass"),
    _row("Geum triflorum", "Prairie Smoke", "#e58fb0", "flora"),
    _row("Asclepias ovalifolia", "Oval-leaf Milkweed", "#f2f2ea", "checked"),
]


class TheList(unittest.TestCase):

    def test_each_answer_colour_reads_back_as_itself(self):
        for key, hexval in cc.HEX.items():
            self.assertEqual(flower_colour.classify_hex(hexval), key)
        self.assertNotIn("straw", cc.ANSWER_COLOURS)

    def test_order_and_who_is_left_off(self):
        names = [i["scientific_name"] for i in cc.worklist(ROWS)]
        self.assertEqual(names[0], "Ratibida columnifera", "flagged first")
        self.assertNotIn("Bouteloua gracilis", names, "a grass has no bloom")
        self.assertNotIn("Asclepias ovalifolia", names, "already checked")
        self.assertEqual(names[1:3], ["Solidago a", "Solidago b"],
                         "the most shared guess next")
        self.assertLess(names.index("Aquilegia flavescens"),
                        names.index("Picea glauca"))
        self.assertEqual(names[-1], "Geum triflorum", "flora last")
        self.assertNotIn("Geum triflorum", [
            i["scientific_name"] for i in cc.worklist(ROWS,
                                                     include_flora=False)])

    def test_an_answer_takes_a_plant_off_unless_it_was_cant_tell(self):
        checks = {"Solidago a": {"colours": ["yellow"]},
                  "Solidago b": {"verdict": cc.CANT_TELL}}
        names = [i["scientific_name"] for i in cc.worklist(ROWS, checks)]
        self.assertNotIn("Solidago a", names)
        self.assertIn("Solidago b", names)

    def test_a_flagged_plant_once_looked_at_leaves_the_list(self):
        """With or without the checks file: the row's own ``photo`` says so."""
        rows = ROWS + [_row("Silene acaulis", "Moss Campion", "#e58fb0",
                            "photo")]
        self.assertNotIn("Silene acaulis",
                         [i["scientific_name"] for i in cc.worklist(rows)])

    def test_every_flowering_plant_in_the_catalogue_was_looked_at(self):
        """V3.34 folded in the owner's 343 answers: nothing is left to look
        at. A plant added later with a guessed colour reappears here, which
        is the list working, not this test breaking: its message names it."""
        left = [i["scientific_name"] for i in cc.worklist(cc.load_master())]
        self.assertEqual(left, [], "not yet looked at in photographs")


class TheAnswers(unittest.TestCase):
    LISTED = {"Solidago a", "Aster c", "Picea glauca"}

    def test_problems_are_named(self):
        bad = cc.validate({
            "Nope nope": {"colours": ["yellow"]},
            "Solidago a": {"colours": ["yellow"], "verdict": cc.CANT_TELL},
            "Aster c": {"colours": ["mauve"]},
            "Picea glauca": {"verdict": "maybe"},
        }, self.LISTED)
        self.assertEqual(len(bad), 4, bad)
        self.assertEqual(cc.validate({"Aster c": {"colours": ["purple",
                                                              "white"]}},
                                     self.LISTED), [])

    def test_apply_record_and_agree(self):
        rows = json.loads(json.dumps(ROWS))
        answers = {
            "Ratibida columnifera": {"colours": ["yellow", "red"],
                                     "observations": [11, 12]},
            "Solidago a": {"verdict": cc.LOOKS_RIGHT},
            "Picea glauca": {"verdict": cc.LOOKS_RIGHT},
            "Aster c": {"verdict": cc.NO_SHOWY_FLOWER},
            "Solidago b": {"verdict": cc.CANT_TELL},
        }
        checks = cc.record(answers, made="2026-10-18", rows=rows)
        self.assertEqual(checks["Ratibida columnifera"]["was"], "flora")
        self.assertEqual(checks["Ratibida columnifera"]["observations"],
                         [11, 12])
        self.assertEqual(checks["Solidago a"]["colours"], ["yellow"])
        self.assertEqual(checks["Picea glauca"]["verdict"],
                         cc.NO_SHOWY_FLOWER)
        cc.apply(rows, checks)
        by = {r["scientific_name"]: r for r in rows}
        rat = by["Ratibida columnifera"]
        self.assertEqual((rat["flower_color"], rat["flower_colours"],
                          rat["flower_colour_source"]),
                         (cc.HEX["yellow"], "yellow,red", "photo"))
        self.assertEqual(flower_colour.colours(rat), ("yellow", "red"))
        self.assertEqual(by["Solidago a"]["flower_colour_source"], "photo")
        self.assertEqual(by["Aster c"]["flower_color"], "")
        self.assertEqual(by["Solidago b"]["flower_colour_source"],
                         "estimated", "can't tell changes nothing")
        self.assertEqual(cc.agrees(rows, checks), [])
        by["Ratibida columnifera"]["flower_colours"] = ""
        self.assertTrue(cc.agrees(rows, checks), "a hand edit is caught")


class TheCatalogueAgrees(unittest.TestCase):

    def test_every_check_is_in_the_catalogue(self):
        self.assertEqual(cc.agrees(cc.load_master(), cc.load_checks()), [])

    def test_a_name_read_never_undoes_a_check(self):
        import seed_flower_colour as seed
        rows = [_row("Aquilegia flavescens", "Yellow Columbine",
                     cc.HEX["cream"], "photo")]
        with mock.patch.object(cc, "load_checks",
                               return_value={"Aquilegia flavescens": {}}):
            seed.apply(rows)
        self.assertEqual(rows[0]["flower_color"], cc.HEX["cream"])
        self.assertEqual(rows[0]["flower_colour_source"], "photo")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TheFoldIn(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.master = os.path.join(self.dir, "plants_master.json")
        self.checks = os.path.join(self.dir, "checks.json")
        with open(self.master, "w", encoding="utf-8") as f:
            json.dump(ROWS, f)

    def _fold(self, answers, write):
        from pathlib import Path
        with mock.patch("builtins.print"):
            return fold.fold({"made": "2026-10-18T20:00:00Z",
                              "answers": answers}, write=write,
                             master=Path(self.master),
                             checks_path=Path(self.checks))

    def test_check_writes_nothing_and_write_is_repeatable(self):
        answers = {"Aster c": {"colours": ["white"]}}
        before = _read(self.master)
        self.assertEqual(self._fold(answers, False), 0)
        self.assertEqual(_read(self.master), before)
        self.assertFalse(os.path.exists(self.checks))
        self.assertEqual(self._fold(answers, True), 0)
        once = _read(self.master)
        self.assertEqual(self._fold(answers, True), 0)
        self.assertEqual(_read(self.master), once)
        saved = json.loads(_read(self.checks))["checks"]
        self.assertEqual(saved["Aster c"]["colours"], ["white"])

    def test_one_bad_answer_writes_nothing(self):
        before = _read(self.master)
        self.assertEqual(self._fold({"Aster c": {"colours": ["white"]},
                                     "Nope nope": {"colours": ["red"]}},
                                    True), 1)
        self.assertEqual(_read(self.master), before)


class TheFetchAndThePage(unittest.TestCase):
    """The API's shape is assumed here, as the script assumes it; --probe is
    what checks it against the real thing (the V2.79 lesson)."""

    def test_names(self):
        self.assertEqual(fetch.query_name("Oxytropis campestris var. gracilis"),
                         "Oxytropis campestris gracilis")
        results = [{"name": "Ratibida columnifera", "id": 1},
                   {"name": "Ratibida tagetes", "id": 2}]
        self.assertEqual(fetch.pick_taxon(results, "Ratibida columnifera")["id"],
                         1)
        renamed = [{"name": "Symphyotrichum ericoides", "id": 3,
                    "matched_term": "Aster ericoides"}]
        self.assertEqual(fetch.pick_taxon(renamed, "Aster ericoides")["id"], 3)
        self.assertEqual(fetch.pick_taxon(results, "Nope nope"), {})

    def test_one_plant_with_a_stubbed_service(self):
        obs = [{"id": i, "uri": f"https://inat/obs/{i}", "observed_on": "2024-06-01",
                "place_guess": "Edmonton",
                "photos": [{"url": f"https://img/{i}/square.jpg",
                            "license_code": "cc-by", "attribution": "(c) x"}]}
               for i in range(1, 4)]

        def get(path, params, **_k):
            if path == "/taxa":
                return {"results": [{"name": "Ratibida columnifera", "id": 9,
                                     "preferred_common_name": "Prairie coneflower"}]}
            return {"results": obs}
        with mock.patch.object(fetch, "get", get):
            entry = fetch.fetch_one("Ratibida columnifera", delay=0)
        self.assertTrue(entry["found"])
        self.assertEqual(len(entry["photos"]), 3)
        self.assertEqual(entry["photos"][0]["url"], "https://img/1/medium.jpg")
        self.assertTrue(entry["photos"][0]["flowering"])
        self.assertEqual(entry["photos"][0]["where"], "Alberta and Saskatchewan")

    def test_the_page_carries_every_plant_and_its_script_parses(self):
        items = cc.worklist(ROWS)
        page = fetch.build_page(items, {"Aster c": {"photos": [
            {"url": "https://img/1/medium.jpg", "page": "https://x",
             "observation": 1, "flowering": True, "where": "anywhere"}]}},
            made="2026-10-18T00:00:00Z")
        data = json.loads(re.search(r"const DATA = (\{.*?\});\n", page,
                                    re.S).group(1))
        self.assertEqual([i["scientific_name"] for i in data["items"]],
                         [i["scientific_name"] for i in items])
        self.assertEqual(len(data["colours"]), len(cc.HEX))
        self.assertIn("Save my answers", page)
        script = page.split("<script>", 1)[1].split("</script>", 1)[0]
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not installed")
        path = os.path.join(tempfile.mkdtemp(), "page.js")
        with open(path, "w", encoding="utf-8") as f:
            f.write(script)
        done = subprocess.run([node, "--check", path], capture_output=True,
                              text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
