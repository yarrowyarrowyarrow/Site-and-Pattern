"""
tests/test_photo_picks.py — several photographs a plant (V3.35, F251): the
rules, the candidate fetch with iNaturalist replaced, the picking page driven
in headless Chromium, the fold, and the website's gallery.
"""

import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from src import data_quality, photo_picks as pp  # noqa: E402

import fetch_photo_candidates as fetch  # noqa: E402
import fold_photo_picks as fold  # noqa: E402

OPEN = "https://inaturalist-open-data.s3.amazonaws.com/photos"


def _pick(pid, slot="flower", licence="cc-by", credit="(c) A, some rights "
          "reserved (CC BY)"):
    return {"photo": pid, "url": f"{OPEN}/{pid}/medium.jpg", "slot": slot,
            "attribution": credit, "license": licence, "observation": 9,
            "taken_on": "2024-06-01"}


def _cand(pid, group):
    return {"photo": pid, "url": f"{OPEN}/{pid}/medium.jpg",
            "thumb": f"{OPEN}/{pid}/small.jpg", "license": "cc-by",
            "attribution": f"(c) user{pid}, some rights reserved (CC BY)",
            "observation": pid * 10, "taken_on": "2024-06-01", "place": "",
            "faves": 3, "user": f"user{pid}", "where": "elsewhere",
            "group": group, "size": 1024}


class TheRules(unittest.TestCase):

    def test_the_bar_is_the_data_gates(self):
        self.assertEqual(set(pp.LICENCES), data_quality._PLANT_IMAGE_LICENSES)

    def test_every_group_files_under_a_real_slot(self):
        for _key, _words, slot in pp.GROUPS:
            self.assertIn(slot, data_quality.PHOTO_SLOTS)
        self.assertEqual(set(pp.SLOT_WORDS), set(data_quality.PHOTO_SLOTS))

    def test_ids_pages_and_sizes(self):
        url = f"{OPEN}/123/square.jpg"
        self.assertEqual(pp.photo_id(url), 123)
        self.assertEqual(pp.photo_page(url),
                         "https://www.inaturalist.org/photos/123")
        self.assertEqual(pp.sized(url, "medium"), f"{OPEN}/123/medium.jpg")
        self.assertEqual(pp.photo_page("/home/me/mine.jpg"), "")

    def test_the_suggestion_leads_with_a_flower_then_one_of_each_kind(self):
        groups = {"chosen": [_cand(1, "chosen")],
                  "flower": [_cand(2, "flower"), _cand(3, "flower")],
                  "plant": [_cand(4, "plant")], "fruit": [_cand(5, "fruit")],
                  "winter": [_cand(6, "winter")], "now": [_cand(7, "now")]}
        self.assertEqual(pp.prepick(groups), [2, 4, 5, 6])

    def test_with_no_flower_the_photo_it_has_leads(self):
        self.assertEqual(pp.prepick({"now": [_cand(7, "now")],
                                     "plant": [_cand(4, "plant")]}), [7, 4])
        self.assertEqual(pp.prepick({"plant": [_cand(4, "plant")]}), [4])
        self.assertEqual(pp.prepick({}), [])

    def test_problems_are_named_and_a_good_answer_passes(self):
        good = {"Aster a": {"picks": [_pick(1), _pick(2, "habit")]},
                "Aster b": {"verdict": "keep"}}
        self.assertEqual(pp.validate(good, ["Aster a", "Aster b"]), [])
        bad = pp.validate({
            "Nope": {"picks": [_pick(1)]},
            "Aster a": {"picks": [_pick(1, licence="cc-by-nc")]},
            "Aster b": {"picks": [_pick(3), _pick(3)]},
            "Aster c": {"picks": [dict(_pick(4), url="https://example.com/x.jpg")]},
            "Aster d": {"picks": [_pick(5, credit="")]},
            "Aster e": {"picks": [_pick(i) for i in range(10, 17)]},
            "Aster f": {"picks": []},
            "Aster g": {"picks": [_pick(6, slot="petal")]},
        }, ["Aster a", "Aster b", "Aster c", "Aster d", "Aster e", "Aster f",
            "Aster g"])
        text = "\n".join(bad)
        for needle in ("Nope: not in the catalogue", "'cc-by-nc' may not ship",
                       "picked twice", "not one of iNaturalist's open",
                       "no credit", "more than 6", "Aster f: no photographs",
                       "unknown slot 'petal'"):
            self.assertIn(needle, text)

    def test_apply_replaces_a_plants_rows_and_the_lead_becomes_its_photo(self):
        master = [{"scientific_name": "Aster a", "image_url": "old"},
                  {"scientific_name": "Aster b", "image_url": "keep"}]
        photos = [{"scientific_name": "Aster a", "slot": "habit", "url": "old",
                   "rank": 0},
                  {"scientific_name": "Aster b", "slot": "flower",
                   "url": "keep", "rank": 0}]
        answers = {"Aster a": {"picks": [_pick(2, "habit"), _pick(1)]},
                   "Aster b": {"verdict": "keep"}}
        done = pp.apply(answers, master, photos)
        self.assertEqual(done, {"picked": 1, "kept": 1, "photographs": 2})
        a = [p for p in photos if p["scientific_name"] == "Aster a"]
        self.assertEqual([(p["url"], p["rank"], p["slot"]) for p in a],
                         [(f"{OPEN}/2/medium.jpg", 0, "habit"),
                          (f"{OPEN}/1/medium.jpg", 1, "flower")])
        self.assertEqual(master[0]["image_url"], f"{OPEN}/2/medium.jpg")
        self.assertEqual(master[0]["image_license"], "cc-by")
        self.assertEqual(master[1]["image_url"], "keep")
        again = [dict(p) for p in photos]
        pp.apply(answers, master, photos)
        self.assertEqual(photos, again, "folding twice changes nothing")

    def test_a_caption_says_what_the_photo_shows(self):
        self.assertEqual(pp.caption({"slot": "fruit"}, 2, 5),
                         "Photo 2 of 5: fruit or seed")


class TheFetch(unittest.TestCase):
    """iNaturalist replaced: what the script keeps of an answer."""

    def _photo(self, pid, licence="cc-by", host=OPEN, side=2048):
        return {"id": pid, "url": f"{host}/{pid}/square.jpg",
                "license_code": licence, "attribution": f"(c) p{pid}",
                "original_dimensions": {"width": side, "height": side // 2}}

    def test_a_photo_that_may_not_ship_or_is_small_is_left_out(self):
        keep = fetch.candidate(self._photo(1), group="flower", where="x")
        self.assertEqual(keep["url"], f"{OPEN}/1/medium.jpg")
        self.assertEqual(keep["thumb"], f"{OPEN}/1/small.jpg")
        for bad in (self._photo(2, "cc-by-nc"), self._photo(3, None),
                    self._photo(4, host="https://static.inaturalist.org/photos"),
                    self._photo(5, side=400)):
            self.assertIsNone(fetch.candidate(bad, group="flower", where="x"))

    def test_an_observation_gives_its_first_photo_that_may_ship(self):
        obs = [{"id": 1, "faves_count": 4, "user": {"login": "a"},
                "photos": [self._photo(10, "cc-by-nc"), self._photo(11)]},
               {"id": 2, "photos": [self._photo(12, "cc-by-nd")]}]
        got = fetch.from_observations(obs, group="fruit", where="x")
        self.assertEqual([(c["photo"], c["faves"], c["user"]) for c in got],
                         [(11, 4, "a")])

    def test_the_limits_per_kind_and_per_photographer(self):
        picker = fetch.Picker()
        for pid in range(1, 4):
            picker.add(dict(_cand(pid, "flower"), user="same"), 4)
        picker.add(_cand(9, "flower"), 4)
        picker.add(_cand(9, "plant"), 4)
        self.assertEqual([c["photo"] for c in picker.groups["flower"]],
                         [1, 2, 9], "two from one photographer, none twice")
        self.assertNotIn(9, [c["photo"] for c in picker.groups.get("plant", [])])

    def test_one_plant_asks_each_kind_and_its_own_page(self):
        asked = []

        def fake_get(path, params):
            asked.append((path, dict(params)))
            if path.startswith("/taxa/"):
                return {"results": [{"taxon_photos": [
                    {"photo": self._photo(900)}]}]}
            base = 100 * (len(asked))
            return {"results": [{"id": base + i, "user": {"login": f"u{base + i}"},
                                 "photos": [self._photo(base + i)]}
                                for i in range(5)]}

        row = {"scientific_name": "Rosa woodsii", "plant_type": "shrub",
               "image_url": f"{OPEN}/7/medium.jpg", "image_license": "cc-by",
               "image_attribution": "(c) now"}
        with mock.patch.object(fetch.inat, "get", fake_get):
            entry = fetch.fetch_one(row, 42, delay=0)
        groups = entry["groups"]
        self.assertEqual(sorted(groups),
                         ["chosen", "flower", "fruit", "now", "plant", "winter"])
        self.assertEqual([len(groups[g]) for g in ("flower", "plant", "fruit",
                                                   "winter")], [4, 4, 4, 4])
        obs = [p for path, p in asked if path == "/observations"]
        self.assertTrue(all(p["photo_license"] == "cc0,cc-by,cc-by-sa"
                            for p in obs))
        self.assertEqual(len(obs), 4, "each kind filled from the provinces "
                                      "alone asks nothing more")
        self.assertEqual([o.get("term_value_id") for o in obs],
                         [13, 21, 14, None])
        self.assertTrue(all("swlat" in o for o in obs), "the provinces first")
        self.assertEqual(obs[-1]["month"], fetch.WINTER_MONTHS)
        self.assertEqual(groups["now"][0]["photo"], 7)

    def test_a_herb_is_not_asked_about_winter(self):
        self.assertNotIn("winter", fetch.groups_for("wildflower"))
        self.assertIn("winter", fetch.groups_for("tree"))

    def test_the_name_vascan_accepts_is_tried_when_the_catalogues_is_not(self):
        self.assertEqual(fetch.accepted_name("Hedysarum mackenziei"),
                         "Hedysarum boreale subsp. mackenziei")
        tried = []

        def fake_get(path, params):
            tried.append(params["q"])
            return {"results": [{"id": 5, "name": "Hedysarum boreale mackenziei"}]}

        with mock.patch.object(fetch.inat, "get", fake_get):
            self.assertEqual(fetch.look_up("Hedysarum mackenziei", delay=0), 5)
        self.assertEqual(tried, ["Hedysarum mackenziei",
                                 "Hedysarum boreale mackenziei"])

    def test_plants_with_no_photo_come_first_then_best_picks(self):
        rows = [{"scientific_name": "A", "common_name": "Zed", "image_url": "u"},
                {"scientific_name": "B", "common_name": "Bee", "image_url": ""},
                {"scientific_name": "C", "common_name": "Cee", "image_url": "u"},
                {"scientific_name": "D", "common_name": "Dee"}]
        order = [i["scientific_name"] for i in fetch.worklist(rows, ["C", "A", "D"])]
        self.assertEqual(order, ["D", "B", "C", "A"])

    def test_the_taxa_already_known_are_read_from_the_count(self):
        taxa = fetch.known_taxa()
        self.assertGreater(len(taxa), 400,
                           "data/fetched/open_photo_counts.json is the source")


def _page(items, candidates):
    return fetch.build_page(items, candidates, made="2026-10-20T00:00:00Z")


class ThePage(unittest.TestCase):

    def test_the_data_is_embedded_and_cannot_close_the_script(self):
        items = [{"scientific_name": "Rosa woodsii", "common_name": "Woods' Rose",
                  "plant_type": "shrub", "has_photo": False}]
        cands = {"Rosa woodsii": {"groups": {"flower": [
            dict(_cand(2, "flower"), attribution="</script><b>x")]}}}
        page = _page(items, cands)
        self.assertNotIn("</script><b>", page)
        data = json.loads(re.search(r"const DATA = (\{.*?\});\n", page, re.S)
                          .group(1).replace("<\\/", "</"))
        self.assertEqual(data["items"][0]["prepick"], [2])
        self.assertEqual(data["max"], pp.MAX_PICKS)


def _chromium():
    try:
        from tests.test_scene3d_render import _find_chromium  # noqa: PLC0415
        return _find_chromium()
    except Exception:                                         # noqa: BLE001
        return None


@unittest.skipIf(_chromium() is None, "no Chromium binary")
class ThePageInABrowser(unittest.TestCase):
    """The page's own buttons, pressed; what it saves is what the fold takes."""

    def test_what_the_page_saves_folds_in(self):
        items = [
            {"scientific_name": "Rosa woodsii", "common_name": "Woods' Rose",
             "plant_type": "shrub", "has_photo": True},
            {"scientific_name": "Rosa acicularis", "common_name": "Prickly Rose",
             "plant_type": "shrub", "has_photo": True},
            {"scientific_name": "Rosa arkansana", "common_name": "Prairie Rose",
             "plant_type": "shrub", "has_photo": True},
            {"scientific_name": "Rosa blanda", "common_name": "Smooth Rose",
             "plant_type": "shrub", "has_photo": False},
        ]
        cands = {
            "Rosa woodsii": {"groups": {"flower": [_cand(2, "flower")],
                                        "fruit": [_cand(3, "fruit")]}},
            "Rosa acicularis": {"groups": {"flower": [_cand(4, "flower")],
                                           "plant": [_cand(5, "plant")]}},
            "Rosa arkansana": {"groups": {"flower": [_cand(6, "flower")]}},
            "Rosa blanda": {"groups": {"flower": [_cand(7, "flower")],
                                       "fruit": [_cand(8, "fruit")]}},
        }
        drive = """<script>
const cs = document.querySelectorAll('section.card');
const b = (card, text) => [...card.querySelectorAll('button')].find(x => x.textContent === text);
b(cs[0], 'Use these').click();
const shots = cs[1].querySelectorAll('button.shot');
shots[0].click(); shots[0].click();
b(cs[1], 'Use these').click();
b(cs[2], 'Keep the photo it has').click();
b(cs[3], 'Lead').click();
b(cs[3], 'Use these').click();
document.title = 'MEASURED ' + exported();
</script></body>"""
        page = _page(items, cands).replace("</body>", drive)
        where = tempfile.mkdtemp(prefix="photo_page_")
        self.addCleanup(shutil.rmtree, where, True)
        path = os.path.join(where, "page.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)
        try:
            proc = subprocess.run(
                [_chromium(), "--headless", "--no-sandbox",
                 "--host-resolver-rules=MAP * ~NOTFOUND",
                 "--virtual-time-budget=5000", "--dump-dom",
                 Path(path).as_uri()],
                capture_output=True, text=True, timeout=120, encoding="utf-8")
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise unittest.SkipTest(f"Chromium would not run: {exc}")
        m = re.search(r"MEASURED (\{.*?\})</title>", proc.stdout, re.S)
        # Chromium ran, so a page that never reports threw: that is a bug in
        # the page (the first draft of this test found one in itself).
        self.assertIsNotNone(m, f"the page never reported: {proc.stderr[-800:]}")
        saved = json.loads(html.unescape(m.group(1)))
        answers = saved["answers"]
        self.assertEqual([p["photo"] for p in answers["Rosa woodsii"]["picks"]],
                         [2, 3], "the suggestion, confirmed")
        self.assertEqual([p["photo"] for p in answers["Rosa acicularis"]["picks"]],
                         [5, 4], "taken out and put back, it goes last")
        self.assertEqual(answers["Rosa arkansana"], {"verdict": "keep"})
        self.assertEqual([(p["photo"], p["slot"]) for p in
                          answers["Rosa blanda"]["picks"]],
                         [(8, "fruit"), (7, "flower")],
                         "Lead moves a pick to the front, slot and all")
        self.assertEqual(pp.validate(answers, list(answers)), [])


class TheFold(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="fold_photos_"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.master = self.dir / "plants_master.json"
        self.photos = self.dir / "plant_photos.json"
        self.master.write_text(json.dumps(
            [{"scientific_name": "Aster a", "image_url": "old"}]), encoding="utf-8")
        self.photos.write_text("[]", encoding="utf-8")

    def _run(self, answers, write):
        return fold.fold({"answers": answers}, write=write,
                         master=self.master, photos_path=self.photos)

    def test_checking_writes_nothing_and_a_bad_pick_stops_everything(self):
        self.assertEqual(self._run({"Aster a": {"picks": [_pick(1)]}}, False), 0)
        self.assertEqual(self.photos.read_text(encoding="utf-8"), "[]")
        self.assertEqual(self._run({"Aster a": {"picks": [
            _pick(1, licence="cc-by-nc")]}}, True), 1)
        self.assertEqual(self.photos.read_text(encoding="utf-8"), "[]")

    def test_writing_folds_the_picks_in(self):
        self.assertEqual(self._run({"Aster a": {"picks": [_pick(1), _pick(2, "fruit")]}},
                                   True), 0)
        rows = json.loads(self.photos.read_text(encoding="utf-8"))
        self.assertEqual([r["rank"] for r in rows], [0, 1])
        master = json.loads(self.master.read_text(encoding="utf-8"))
        self.assertEqual(master[0]["image_url"], f"{OPEN}/1/medium.jpg")


class TheWebsiteGallery(unittest.TestCase):

    def test_the_lead_then_the_rest_each_credited_and_linked(self):
        from src.static_site_gallery import NO_PHOTO, gallery_html  # noqa: PLC0415
        photos = [dict(_pick(1), url=f"{OPEN}/1/medium.jpg"),
                  dict(_pick(2, "fruit")), dict(_pick(3, credit="")),
                  dict(_pick(4, "winter"))]
        out = gallery_html({"name": "Woods' Rose", "photos": photos}, 2,
                           {f"{OPEN}/2/medium.jpg": "assets/photos/rose-2.jpg"})
        self.assertEqual(out.count('<li><a href="'), 2,
                         "the uncredited photo is not shown")
        self.assertIn('href="../../assets/photos/rose-2.jpg"', out)
        self.assertIn('<ol class="photo-credits" start="2">', out)
        self.assertEqual(out.count("https://www.inaturalist.org/photos/"), 3)
        self.assertIn("photo 2: fruit or seed", out)
        self.assertNotIn("—", out)
        self.assertEqual(gallery_html({"photos": []}, 2, {}), NO_PHOTO)
        one = gallery_html({"name": "X", "photos": photos[:1]}, 2, {})
        self.assertNotIn("photo-strip", one)


if __name__ == "__main__":
    unittest.main()
