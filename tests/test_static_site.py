"""
tests/test_static_site.py — the catalogue as a public website (V2.47).

F90 built the directory and shipped it inside a desktop installer. This is the
same pages as files. What these hold down:

  * **every internal link resolves to a file the build wrote.** A static site's
    characteristic failure is a 404 nobody clicks for six months, and the
    generator emits ~9,600 internal links;
  * **no photograph is published without its credit.** The licences the
    catalogue accepts oblige attribution, and publishing to the open web is not
    the moment to loosen the rule the 3D dossier already follows;
  * **the notes field stays off by default (P12).** ~43 rows describe
    traditional medicinal and plant-use practice; that is not ours to publish;
  * **the model is buildable with no database**, so the link graph can be
    asserted without a 4-second build;
  * **text is escaped** — a botanical name with an apostrophe has broken this
    project's JavaScript before (see the README's known limitations).
"""

import json
import os
import pathlib
import posixpath
import re
import sys
import tempfile
import unittest
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_site_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src import static_site                                # noqa: E402
from src import static_site_render as render               # noqa: E402

_LINK = re.compile(r'(?:href|src)="([^"]+)"')


# ── A model with no database behind it ───────────────────────────────────────

def _fake_plant(pid, name, sci, ptype="wildflower", colour="#f2c11e",
                bloom="June-July", attribution="(c) Someone, CC BY"):
    return {
        "id": pid, "common_name": name, "scientific_name": sci,
        "plant_type": ptype, "flower_color": colour, "bloom_period": bloom,
        "flower_form": "cluster" if colour else "none",
        "sun_requirement": "full_sun,partial_shade", "water_needs": "low",
        "mature_height_meters": 0.8, "native_to_alberta": 1,
        "native_provinces": "AB,SK", "ecoregion": "aspen_parkland",
        "perennial_or_annual": "perennial", "deciduous_evergreen": "herbaceous",
        "growth_rate": "moderate", "years_to_maturity": 2,
        "permaculture_uses": "pollinator", "availability_class": "garden_centre",
        "leaf_shape": "lanceolate",
        "image_url": "https://example.org/p.jpg" if attribution else "",
        "image_attribution": attribution, "image_license": "CC BY",
        "hardiness_zone_min": 3, "hardiness_zone_max": 6,
    }


_PLANTS = [
    _fake_plant(1, "Wild Bergamot", "Monarda fistulosa", colour="#8e6fc4"),
    _fake_plant(2, "Blue Grama Grass", "Bouteloua gracilis", "grass", "#cbbd80"),
    # An apostrophe in the name, and no photo credit — both traps.
    _fake_plant(3, "Bebb's Sedge", "Carex bebbii", "sedge", "#cbbd80",
                attribution=""),
    _fake_plant(4, "Yarrow", "Achillea millefolium", colour="#f2f2ea"),
]

_FAUNA = [
    {"id": 10, "common_name": "Monarch", "scientific_name": "Danaus plexippus",
     "taxon": "lepidoptera", "notes": ""},
    # An animal with no documented plants — must get no page.
    {"id": 11, "common_name": "Ghost Moth", "scientific_name": "Nobody knowsii",
     "taxon": "lepidoptera", "notes": ""},
]


def _fake_search(**kwargs):
    rows = list(_PLANTS)
    colours = kwargs.get("flower_colours")
    if colours:
        from src.flower_colour import classify
        rows = [r for r in rows if classify(r) in set(colours)]
    months = kwargs.get("bloom_months")
    if months:
        rows = [r for r in rows if 6 in [int(m) for m in months]]
    for flag in ("keystone_only", "host_plant_only", "bird_food_only",
                 "pollinator_only", "supports_specialist", "nfixer_only",
                 "edible_only", "pet_safe_only"):
        if kwargs.get(flag):
            rows = rows[:1]
    return rows


def _fake_entry(plant_id):
    plant = next(p for p in _PLANTS if p["id"] == plant_id)
    photos = []
    if plant["image_url"] and plant["image_attribution"]:
        photos = [{"slot": "habit", "url": plant["image_url"],
                   "attribution": plant["image_attribution"],
                   "license": "CC BY"}]
    return {
        "id": plant_id, "name": plant["common_name"],
        "scientific_name": plant["scientific_name"],
        "plant_type": plant["plant_type"], "badges": ["Pollinator plant"],
        "native": "AB,SK", "native_to_alberta": True,
        "sun": plant["sun_requirement"], "water": "low", "soil_ph": "pH 6–8",
        "zones": "zone 3–6", "mature_height_m": 0.8, "bloom": "Jun–Jul",
        "morphology": ["lance-shaped leaves"],
        "safety": ["Toxicity not assessed"],
        "sourcing": {"price": "about $8", "availability": "garden centre"},
        "edible_parts": "leaves,flowers",
        "notes": "Traditional cold remedy. Drought tolerant.",
        "photos": photos, "provenance": ["Flower detail: estimated"],
        "wildlife": {"total": 1, "specialists": 1,
                     "groups": [{"how": "nectar for",
                                 "items": [{"name": "Monarch",
                                            "scientific_name": "Danaus plexippus",
                                            "taxon": "lepidoptera",
                                            "taxon_label": "butterfly / moth",
                                            "specialist": True,
                                            "source": "acorn_sheldon"}]}]},
        "ranges": [{"key": "parkland", "name": "Aspen Parkland",
                    "where": "central AB", "occurrences": 12,
                    "confidence": "moderate", "source": "gbif"}],
        "calendar": [],
    }


def _fake_plants_for_fauna(fauna_id, relationship=""):
    if fauna_id != 10:
        return []
    row = dict(_PLANTS[0])
    row["relationship"] = "nectar"
    row["specificity"] = "specialist"
    return [row]


def _model():
    return static_site.build_model(
        search_fn=_fake_search, entry_fn=_fake_entry,
        list_fauna_fn=lambda: list(_FAUNA),
        plants_for_fauna_fn=_fake_plants_for_fauna)


class TestTheModelNeedsNoDatabase(unittest.TestCase):

    def setUp(self):
        self.model = _model()

    def test_it_builds_a_page_per_species(self):
        self.assertEqual(len(self.model["species"]), len(_PLANTS))

    def test_slugs_are_url_safe(self):
        for entry in self.model["species"]:
            self.assertRegex(entry["slug"], r"^[a-z0-9-]+$")

    def test_an_animal_with_no_documented_plants_gets_no_page(self):
        """A page reading "0 plants support this species" publishes a fact
        about our coverage as though it were a fact about the animal (P9)."""
        names = {a["name"] for a in self.model["wildlife"]}
        self.assertIn("Monarch", names)
        self.assertNotIn("Ghost Moth", names)

    def _hub(self, key):
        return next(h for h in self.model["hubs"] if h["key"] == key)

    def test_an_empty_facet_value_gets_no_page(self):
        values = {p["value"] for p in self._hub("colour")["pages"]}
        self.assertIn("purple", values)
        self.assertNotIn("orange", values)   # no orange plant in the fixture

    def test_the_grasses_land_on_the_straw_page(self):
        straw = next(p for p in self._hub("colour")["pages"]
                     if p["value"] == "straw")
        self.assertEqual({p["name"] for p in straw["plants"]},
                         {"Blue Grama Grass", "Bebb's Sedge"})

    def test_every_hub_facet_produced_pages(self):
        """A hub axis that generated nothing is a facet whose derivation is
        broken, which looks identical to "the data has none of that"."""
        got = {h["key"] for h in self.model["hubs"]}
        self.assertEqual(got, {"type", "colour", "bloom", "ecoregion", "role"})

    def test_a_photo_without_attribution_is_not_offered(self):
        by_name = {e["name"]: e for e in self.model["species"]}
        self.assertEqual(static_site._first_photo(by_name["Bebb's Sedge"]), {})
        self.assertTrue(static_site._first_photo(by_name["Yarrow"]))


class TestSlugify(unittest.TestCase):

    def test_it_folds_to_ascii_hyphens(self):
        self.assertEqual(static_site.slugify("Bebb's Sedge"), "bebb-s-sedge")
        self.assertEqual(static_site.slugify("Solidago × hybrida"),
                         "solidago-hybrida")

    def test_it_never_returns_empty(self):
        """An empty slug would claim the parent directory's URL."""
        self.assertEqual(static_site.slugify(""), "unnamed")
        self.assertEqual(static_site.slugify("×××"), "unnamed")

    def test_colliding_names_keep_separate_stable_urls(self):
        rows = [{"id": 7, "common_name": "Wild Rose"},
                {"id": 3, "common_name": "Wild Rose"},
                {"id": 9, "common_name": "Yarrow"}]
        slugs = static_site._unique_slugs(rows)
        self.assertEqual(len(set(slugs.values())), 3)
        self.assertEqual(slugs[9], "yarrow")
        self.assertEqual(slugs[3], "wild-rose-3")
        self.assertEqual(slugs[7], "wild-rose-7")


class TestTheRenderedSite(unittest.TestCase):
    """Renders the whole fixture site to a temp directory and inspects it."""

    @classmethod
    def setUpClass(cls):
        cls.model = _model()
        cls.out = pathlib.Path(tempfile.mkdtemp(prefix="site_render_"))
        cls.summary = render.write_site(cls.model, str(cls.out),
                                        base_url="https://example.org",
                                        copy_photos=False)
        # `.as_posix()`, not `str()` — **this set is compared against URLs.**
        # `expected_paths` builds "plants/<slug>/index.html" with forward
        # slashes, and the dead-link check resolves hrefs with `posixpath`.
        # `str(Path)` uses the NATIVE separator, so on Windows every entry here
        # came out "plants\\<slug>\\index.html" and matched nothing: four tests
        # failed at once, reporting 249 dead links on a site whose links are
        # fine. The generator was never wrong — only this comparison was, and
        # it passed on Linux for the accidental reason that os.sep == "/".
        cls.files = {p.relative_to(cls.out).as_posix()
                     for p in cls.out.rglob("*") if p.is_file()}

    def test_it_wrote_every_page_the_model_promised(self):
        expected = static_site.expected_paths(self.model)
        self.assertEqual(expected - self.files, set())

    def test_the_file_index_is_url_shaped_not_os_shaped(self):
        """Guards the `.as_posix()` in setUpClass, which is invisible on Linux.

        This set is compared against hrefs and against `expected_paths`, both
        of which are URLs. Built with `str(Path)` it picks up the platform
        separator, and on Windows four tests then fail together and report 249
        dead links on a site that has none — a failure that reads like a broken
        generator rather than a broken comparison. Trivially true on Linux;
        it exists to fail on Windows the moment someone writes `str()` again.
        """
        offenders = sorted(f for f in self.files if "\\" in f)
        self.assertEqual(offenders, [], f"OS separators in a URL set: {offenders}")

    def test_every_internal_link_resolves(self):
        dead = []
        for page in self.out.rglob("*.html"):
            # Feeds `posixpath.join` below, so it has to be posix here too.
            base = page.parent.relative_to(self.out).as_posix()
            for link in _LINK.findall(page.read_text(encoding="utf-8")):
                if link.startswith(("http://", "https://", "#", "mailto:",
                                    "data:")):
                    continue
                target = urllib.parse.unquote(link.split("#")[0].split("?")[0])
                if not target:
                    continue
                norm = posixpath.normpath(posixpath.join(base, target))
                norm = "" if norm == "." else norm
                candidates = [norm, posixpath.join(norm, "index.html")
                              if norm else "index.html"]
                if not any(c in self.files for c in candidates):
                    dead.append(f"{page.relative_to(self.out)} -> {link}")
        self.assertEqual(dead, [])

    def test_no_image_is_published_without_a_credit(self):
        offenders = []
        for page in self.out.rglob("*.html"):
            html = page.read_text(encoding="utf-8")
            for tag in re.findall(r"<img[^>]*>", html):
                alt = re.search(r'alt="([^"]*)"', tag)
                title = re.search(r'title="([^"]*)"', tag)
                credited = bool(
                    (alt and alt.group(1).strip())
                    or (title and title.group(1).strip())
                    or 'class="credit"' in html)
                if not credited:
                    offenders.append(f"{page.relative_to(self.out)}: {tag[:60]}")
        self.assertEqual(offenders, [])

    def test_the_unattributed_photo_is_absent_entirely(self):
        page = (self.out / "plants" / "bebb-s-sedge" / "index.html").read_text(
            encoding="utf-8")
        self.assertNotIn("<img", page)
        self.assertIn("credit the photographer", page)

    def test_notes_are_withheld_by_default(self):
        """P12. ~43 seeded rows describe traditional medicinal and plant-use
        practice; the open web is not where that gets published without free,
        prior and informed consent."""
        for page in self.out.rglob("plants/*/index.html"):
            self.assertNotIn("Traditional cold remedy",
                             page.read_text(encoding="utf-8"))

    def test_notes_can_be_opted_into(self):
        out = pathlib.Path(tempfile.mkdtemp(prefix="site_notes_"))
        render.write_site(self.model, str(out), copy_photos=False,
                          include_notes=True)
        page = (out / "plants" / "wild-bergamot" / "index.html").read_text(
            encoding="utf-8")
        self.assertIn("Traditional cold remedy", page)

    def test_the_p12_statement_is_on_every_page(self):
        for page in self.out.rglob("*.html"):
            self.assertIn("no Indigenous ecological knowledge",
                          page.read_text(encoding="utf-8"),
                          str(page.relative_to(self.out)))

    def test_apostrophes_and_ampersands_are_escaped(self):
        page = (self.out / "plants" / "bebb-s-sedge" / "index.html").read_text(
            encoding="utf-8")
        self.assertIn("Bebb&#x27;s Sedge", page)
        self.assertNotIn("&amp;amp;", page)

    def test_the_json_index_is_valid_and_complete(self):
        rows = json.loads((self.out / "assets" / "catalogue.json").read_text(
            encoding="utf-8"))
        self.assertEqual(len(rows), len(_PLANTS))
        self.assertEqual({r["slug"] for r in rows},
                         {e["slug"] for e in self.model["species"]})

    def test_the_browse_page_can_find_its_own_cards(self):
        """The client-side filter looks cards up by their ``href``. If the card
        renderer and the script disagree about the prefix, every filter hides
        everything — silently, because the page still draws."""
        html = (self.out / "plants" / "index.html").read_text(encoding="utf-8")
        rows = json.loads(re.search(
            r'<script id="catalogue" type="application/json">(.*?)</script>',
            html, re.S).group(1))
        hrefs = set(re.findall(r'<a class="card" href="([^"]+)"', html))
        self.assertEqual(len(rows), len(_PLANTS))
        for row in rows:
            self.assertIn(f"../plants/{row['s']}/", hrefs)

    def test_the_embedded_json_cannot_close_its_own_script_block(self):
        """The index is built from free-text database columns. A `</script>` in
        one of them would spill JSON into the document."""
        html = (self.out / "plants" / "index.html").read_text(encoding="utf-8")
        payload = re.search(
            r'<script id="catalogue" type="application/json">(.*?)</script>',
            html, re.S).group(1)
        self.assertNotIn("<", payload)
        json.loads(payload)          # still valid JSON after the escaping

    def test_no_em_dash_reaches_a_page(self):
        """On the author's instruction, and enforced rather than remembered:
        most of the prose here comes out of the database, where whoever wrote a
        safety note cannot be asked to know a house style set afterwards."""
        offenders = []
        for page in self.out.rglob("*"):
            if page.is_file() and page.suffix in (".html", ".css", ".js",
                                                  ".json", ".xml", ".txt"):
                text = page.read_text(encoding="utf-8")
                if "—" in text:
                    where = text.index("—")
                    offenders.append(f"{page.relative_to(self.out)}: "
                                     f"...{text[max(0, where - 40):where + 40]}...")
        self.assertEqual(offenders, [])

    def test_the_dash_normaliser_leaves_ranges_alone(self):
        """An en dash joining a range is a different mark doing a different
        job. "Jun-Jul" and "pH 5.5-7" must survive."""
        self.assertEqual(render._nodash("Jun–Jul"), "Jun–Jul")
        self.assertEqual(render._nodash("pH 5.5–7"), "pH 5.5–7")
        self.assertEqual(render._nodash("a — b"), "a, b")
        self.assertEqual(render._nodash("a—b"), "a, b")

    def test_every_species_page_carries_its_range_map(self):
        page = (self.out / "plants" / "wild-bergamot" / "index.html").read_text(
            encoding="utf-8")
        self.assertIn("<svg", page)
        self.assertIn("Approximate extents", page)

    def test_the_map_page_exists_and_is_linked_from_every_header(self):
        self.assertIn("map/index.html", self.files)
        for page in self.out.rglob("*.html"):
            self.assertIn('href="', page.read_text(encoding="utf-8"))

    def test_the_sitemap_lists_only_pages_that_exist(self):
        xml = (self.out / "sitemap.xml").read_text(encoding="utf-8")
        locs = re.findall(r"<loc>https://example\.org/([^<]*)</loc>", xml)
        self.assertGreater(len(locs), 5)
        for loc in locs:
            self.assertIn(f"{loc}index.html" if loc else "index.html",
                          self.files)

    def test_no_external_resource_is_referenced(self):
        """No CDN, no webfont, no analytics. The map and the 3D viewer already
        follow this; a page that phones home would be the first."""
        allowed = ("https://github.com/", "https://example.org/p.jpg")
        for page in self.out.rglob("*.html"):
            for link in _LINK.findall(page.read_text(encoding="utf-8")):
                if link.startswith(("http://", "https://")):
                    self.assertTrue(link.startswith(allowed), link)

    def test_the_summary_counts_what_was_written(self):
        self.assertEqual(self.summary["files"], len(self.files))
        self.assertEqual(self.summary["pages"], len(self.files))
        self.assertEqual(self.summary["species"], len(_PLANTS))

    def test_the_wildlife_index_admits_what_it_left_out(self):
        """56 of 142 animals have no documented plant and get no page. The
        index has to say so, or the omission reads as "these are all the
        animals there are"."""
        html = (self.out / "wildlife" / "index.html").read_text(encoding="utf-8")
        self.assertIn("1 more animals are in the catalogue", html)

    def test_it_writes_into_a_directory_without_emptying_it(self):
        """A generator that deletes the directory it was pointed at is one bad
        argument away from removing something else."""
        out = pathlib.Path(tempfile.mkdtemp(prefix="site_keep_"))
        (out / "CNAME").write_text("plants.example.org", encoding="utf-8")
        render.write_site(self.model, str(out), copy_photos=False)
        self.assertTrue((out / "CNAME").exists())


if __name__ == "__main__":
    unittest.main()
