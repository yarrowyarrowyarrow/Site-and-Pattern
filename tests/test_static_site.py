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
from src import static_site_method as method              # noqa: E402
from src import static_site_range as rangemod             # noqa: E402

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
    # The description opens by restating the common name, as roughly a third of
    # the real rows do. Under an <h1> that already says it, that is a stutter.
    {"id": 10, "common_name": "Monarch", "scientific_name": "Danaus plexippus",
     "taxon": "lepidoptera", "notes": "",
     "description": "Monarch. A migratory milkweed butterfly.",
     "image_url": "https://example.org/monarch.jpg",
     "image_attribution": "(c) Someone, CC BY", "image_license": "CC BY"},
    # An animal with no documented plants — must get no page.
    {"id": 11, "common_name": "Ghost Moth", "scientific_name": "Nobody knowsii",
     "taxon": "lepidoptera", "notes": ""},
    # A photograph with no attribution: the same trap as Bebb's Sedge, on the
    # animal side of the site. It must publish no picture at all rather than an
    # uncredited one (V2.71, when animal photographs started being published).
    {"id": 12, "common_name": "Prairie Bee", "scientific_name": "Andrena nulla",
     "taxon": "bee", "notes": "",
     "image_url": "https://example.org/bee.jpg",
     "image_attribution": "", "image_license": "CC BY"},
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
    if fauna_id == 12:
        row = dict(_PLANTS[1])
        row["relationship"] = "pollen"
        row["specificity"] = "generalist"
        return [row]
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

    #: Two species sharing a common name, plus one that does not. The ids are
    #: deliberately out of order — a reseed does not preserve them.
    _ROWS = [{"id": 7, "common_name": "Wild Rose",
              "scientific_name": "Rosa acicularis"},
             {"id": 3, "common_name": "Wild Rose",
              "scientific_name": "Rosa woodsii"},
             {"id": 9, "common_name": "Yarrow",
              "scientific_name": "Achillea millefolium"}]

    def test_colliding_names_get_separate_urls(self):
        slugs = static_site._unique_slugs(self._ROWS)
        self.assertEqual(len(set(slugs.values())), 3)
        self.assertEqual(slugs[9], "yarrow")
        self.assertEqual(slugs[3], "wild-rose-rosa-woodsii")
        self.assertEqual(slugs[7], "wild-rose-rosa-acicularis")

    def test_a_url_survives_a_reseed(self):
        """**The invariant this function exists for**, and the one its previous
        version got backwards while claiming otherwise.

        Row ids are not stable across a reseed — CLAUDE.md says so three times
        and `src/db/photos.py` keys on `scientific_name` to avoid it. Suffixing
        a collided slug with the id therefore renamed pages on a data change:
        the V2.68 publish silently retired four live URLs that way.

        So the test renumbers every row, as a reseed does, and asserts the URLs
        do not move."""
        before = static_site._unique_slugs(self._ROWS)
        reseeded = [dict(r, id=r["id"] * 1000 + 5) for r in self._ROWS]
        after = static_site._unique_slugs(reseeded)
        self.assertEqual(sorted(before.values()), sorted(after.values()),
                         "renumbering the rows changed a public URL")
        for row, reborn in zip(self._ROWS, reseeded):
            self.assertEqual(before[row["id"]], after[reborn["id"]],
                             f"{row['common_name']} moved")

    def test_a_true_duplicate_still_gets_two_pages(self):
        """Same common name AND same scientific name: nothing distinguishes
        them, so an ordinal is the best available and neither page may silently
        overwrite the other. The real fix is upstream — that is a row to merge."""
        rows = [{"id": 2, "common_name": "Twinflower",
                 "scientific_name": "Linnaea borealis"},
                {"id": 1, "common_name": "Twinflower",
                 "scientific_name": "Linnaea borealis"}]
        slugs = static_site._unique_slugs(rows)
        self.assertEqual(len(set(slugs.values())), 2)
        self.assertTrue(all(s.startswith("twinflower-linnaea-borealis")
                            for s in slugs.values()), slugs)


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

    def test_a_species_page_cites_a_work_not_a_database_key(self):
        """V2.65. Every relationship carries a source, and the site printed the
        raw slug — `globi_www_bumblebeewatch_org` — on 290 species pages, under
        prose promising "a documented record with a source". `src.citations`
        has held the bibliography since V2.42 and the website was the one
        surface never wired to it."""
        leaked = []
        for page in (self.out / "plants").rglob("index.html"):
            body = page.read_text(encoding="utf-8")
            for m in re.finditer(r'class="src"[^>]*>([^<]+)<', body):
                text = m.group(1).strip()
                if re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+){2,}", text):
                    leaked.append(f"{page.parent.name}: {text}")
        self.assertEqual(leaked[:5], [], f"{len(leaked)} raw source keys shown")

    def test_the_about_page_publishes_the_bibliography(self):
        """A citation the reader cannot look up is decoration. The works are
        listed, and `citations.disclaimer()` travels with them because these
        details were transcribed from source records rather than checked
        against the works themselves."""
        from src import citations
        page = (self.out / "about" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Where this data came from", page)
        self.assertIn("not been checked", page)
        for key in ("acorn_sheldon_butterflies_ab", "globi"):
            head = citations.format_citation(key).split(".")[0]
            self.assertIn(head, page, key)

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

    def test_a_custom_domain_is_written_into_the_published_folder(self):
        """GitHub Pages keeps the custom domain in a CNAME file at the root of
        the published branch, and the publish replaces that branch wholesale.

        So a domain set by hand in the Pages settings survives exactly until the
        next rebuild and then reverts to *.github.io with the custom domain
        404ing, with no error and nothing in the build output to notice. The
        file has to come out of the build."""
        import tempfile

        out = pathlib.Path(tempfile.mkdtemp(prefix="site_cname_"))
        render.write_site(self.model, str(out), copy_photos=False,
                          base_url="https://grownativeplants.ca/")
        cname = out / "CNAME"
        self.assertTrue(cname.exists(), "no CNAME: the domain would drop")
        self.assertEqual(cname.read_text(encoding="utf-8").strip(),
                         "grownativeplants.ca")

    def test_the_default_github_domain_writes_no_cname(self):
        """A CNAME naming *.github.io is GitHub pointing at itself. The absence
        is the correct output, not a missing feature."""
        import tempfile

        out = pathlib.Path(tempfile.mkdtemp(prefix="site_nocname_"))
        render.write_site(
            self.model, str(out), copy_photos=False,
            base_url="https://yarrowyarrowyarrow.github.io/Site-and-Pattern/")
        self.assertFalse((out / "CNAME").exists())

    def test_every_species_page_carries_its_range_map(self):
        """The drawing, and the caption that has to travel with it.

        The caption is checked by identity rather than by its opening words:
        this asserted the literal string "Approximate extents" and so kept
        passing after V2.67 replaced the hand-traced outlines with a surveyed
        layer, while the page went on calling them a diagram. Pinning
        `CAVEAT` itself means the wording can be corrected in one place and
        the test still guards the thing it cares about, which is that no map
        reaches a reader without its provenance."""
        page = (self.out / "plants" / "wild-bergamot" / "index.html").read_text(
            encoding="utf-8")
        self.assertIn("<svg", page)
        # V2.80: the map on a species page is the occurrence range map, not
        # the ecoregion map. `species_range.caption` is its provenance, and
        # this pins the caption rather than a literal string for the reason
        # the docstring above gives.
        self.assertIn(render._esc("unrecorded rather than empty"), page)
        self.assertIn("records per square", page)

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
        follow this; a page that phones home would be the first.

        The two ``example.org`` photographs are the fixture's own, left as
        links because this build passes ``copy_photos=False``; a real build
        stages them into ``assets/photos/``. V2.71 added an opt-in analytics
        beacon, which this build does not ask for and therefore must not have
        — `TestAnalyticsIsOptInAndDisclosed` covers both states.

        **The allowlist is a list of destinations, not of requests.** Every
        entry is an `<a href>` a reader may choose to follow; none is fetched
        while the page loads, which is the promise this test exists to keep.

        GBIF and iNaturalist joined it in V2.75 (F135). A species page's range
        is a snapshot of a database that changes daily, and an outside review
        asked how current it was; linking out is the honest answer.

        VASCAN joined in V2.80, when the nativity claim stopped being an
        inference and started citing a published checklist. A claim with a
        source the reader cannot reach is barely better than one without.

        That V2.75 docstring also said the coordinates were "not ours to
        republish". **That is no longer true and the note is corrected rather
        than left standing**: the licence rule was reconsidered per record kind
        (a coordinate is a fact about a place, a photograph is a work), and
        171,896 marks are now drawn on the species pages themselves. The rare
        taxa the old note worried about were raised explicitly and published
        on the author's decision.

        Three named hosts, still no third-party script, still nothing loaded.
        """
        allowed = ("https://github.com/", "https://example.org/p.jpg",
                   "https://example.org/monarch.jpg",
                   "https://www.gbif.org/", "https://www.inaturalist.org/",
                   "https://data.canadensys.net/")
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


class TestTheWildlifeIndexIsSearchable(unittest.TestCase):
    """V2.71. The index was 1,138 chips in five fixed taxon blocks, which is a
    list rather than a way to find anything, and the photographs the `fauna`
    table had carried since the iNaturalist fetch were not published at all."""

    @classmethod
    def setUpClass(cls):
        cls.model = _model()
        cls.out = pathlib.Path(tempfile.mkdtemp(prefix="site_wildlife_"))
        render.write_site(cls.model, str(cls.out), copy_photos=False)
        cls.html = (cls.out / "wildlife" / "index.html").read_text(
            encoding="utf-8")

    def _animal(self, name):
        return next(a for a in self.model["wildlife"] if a["name"] == name)

    def test_the_index_can_find_its_own_cards(self):
        """Same failure the plant page has: if the card renderer and the script
        disagree about the href, every filter hides everything and the page
        still draws. `browse.js` keys on the last path segment, so this is what
        proves the wildlife hrefs end in the slug the index rows carry."""
        rows = json.loads(re.search(
            r'<script id="catalogue" type="application/json">(.*?)</script>',
            self.html, re.S).group(1))
        hrefs = set(re.findall(r'<a class="card" href="([^"]+)"', self.html))
        self.assertEqual(len(rows), len(self.model["wildlife"]))
        for row in rows:
            self.assertIn(f"../wildlife/{row['s']}/", hrefs)

    def test_a_facet_offers_only_values_something_answers(self):
        """A checkbox that can only ever return nothing is worse than a missing
        one: the empty result reads as a fact about the prairie."""
        offered = set(re.findall(r'<input type="checkbox" data-f="taxon" '
                                 r'value="([^"]+)"', self.html))
        self.assertEqual(offered, {"lepidoptera", "bee"})

    def test_an_animal_with_no_photograph_answers_no_photo_filter(self):
        """P9 as the filter sees it: absent is absent, not a weak yes. Ticking
        "has a photograph" must drop it rather than keep it as an unknown."""
        from src.static_site_wildlife import facets_for

        self.assertIn("photo", facets_for(self._animal("Monarch"))["has"])
        self.assertNotIn("has", facets_for(self._animal("Prairie Bee")))

    def test_the_uncredited_animal_photo_is_absent_entirely(self):
        """The licences oblige attribution. An animal photograph with no
        credit is not published smaller or without a caption; it is not
        published."""
        bee = self._animal("Prairie Bee")
        self.assertEqual(bee["image"], "")
        page = (self.out / "wildlife" / bee["slug"] / "index.html").read_text(
            encoding="utf-8")
        # Not "no <img on the page": the plants it feeds on carry their own
        # thumbnails and those are properly credited. What must be absent is
        # this animal's picture and the figure that would hold it.
        self.assertNotIn("example.org/bee.jpg", page)
        self.assertNotIn("hero-photo", page)

    def test_the_credited_animal_photo_is_published_with_its_credit(self):
        monarch = self._animal("Monarch")
        page = (self.out / "wildlife" / monarch["slug"] /
                "index.html").read_text(encoding="utf-8")
        self.assertIn("example.org/monarch.jpg", page)
        self.assertIn("CC BY", page)

    def test_the_animal_description_is_published_without_its_own_name(self):
        """`fauna` has no `notes` column, so the model key that fed the animal
        page's prose block had been reading `None` on every row since it was
        written and the block had never rendered once. `description` is
        populated for all 1,156 rows and no page had shown a word of it."""
        monarch = self._animal("Monarch")
        self.assertEqual(monarch["description"],
                         "A migratory milkweed butterfly.")
        page = (self.out / "wildlife" / monarch["slug"] /
                "index.html").read_text(encoding="utf-8")
        self.assertIn("A migratory milkweed butterfly.", page)
        self.assertNotIn("Monarch. A migratory", page)

    def test_an_animal_with_no_description_still_renders(self):
        bee = self._animal("Prairie Bee")
        self.assertEqual(bee["description"], "")
        page = (self.out / "wildlife" / bee["slug"] / "index.html").read_text(
            encoding="utf-8")
        self.assertIn("1 documented plant relationship.", page)

    def test_the_relationship_facet_reads_the_raw_kind(self):
        """`groups` holds display phrases ("sips nectar at"). The facet has to
        key on the relationship itself, or the vocabulary drifts the first time
        a heading is reworded."""
        self.assertEqual(self._animal("Monarch")["kinds"], ["nectar"])
        self.assertEqual(self._animal("Prairie Bee")["kinds"], ["pollen"])


class TestAnalyticsIsOptInAndDisclosed(unittest.TestCase):
    """V2.71. The site made no external request of any kind; a beacon is a real
    change to that promise, so it is off by default, refuses a malformed token
    rather than pasting it into every page, and says so where a reader looks.

    V2.73 adds a second provider on the same terms. What is checked here is
    that both reach *every page* and that neither can leak into a later build;
    the validation table itself is in `tests/test_site_analytics.py`, where it
    does not cost a site render per case."""

    _UID = "0f8c1a2b-3d4e-5f60-7182-93a4b5c6d7e8"

    @classmethod
    def setUpClass(cls):
        cls.model = _model()

    def _build(self, **kw):
        out = pathlib.Path(tempfile.mkdtemp(prefix="site_analytics_"))
        summary = render.write_site(self.model, str(out), copy_photos=False,
                                    **kw)
        return out, summary

    def _assert_clean(self, out):
        for page in out.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertNotIn("cloudflareinsights", text, str(page))
            self.assertNotIn("umami", text.lower(), str(page))

    def test_no_beacon_unless_asked_for(self):
        out, summary = self._build()
        self.assertFalse(summary["analytics"])
        self.assertEqual(summary["analytics_providers"], ())
        self._assert_clean(out)

    def test_the_beacon_and_its_disclosure_land_on_every_page(self):
        token = "a" * 32
        out, summary = self._build(analytics_token=token)
        self.assertTrue(summary["analytics"])
        self.assertEqual(summary["analytics_providers"],
                         ("Cloudflare Web Analytics",))
        for page in out.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertIn(token, text, str(page))
            self.assertIn("sets no cookies", text, str(page))

    def test_umami_and_its_disclosure_land_on_every_page(self):
        """V2.73. Cloudflare's free tier answers "is anyone reading this" and
        keeps a short window; Umami is the one that keeps history."""
        out, summary = self._build(umami_website_id=self._UID)
        self.assertEqual(summary["analytics_providers"], ("Umami",))
        for page in out.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertIn(f'data-website-id="{self._UID}"', text, str(page))
            self.assertIn("cloud.umami.is/script.js", text, str(page))
            self.assertIn("sets no cookies", text, str(page))
            self.assertNotIn("cloudflareinsights", text, str(page))

    def test_both_providers_can_run_together(self):
        """The switchover case: the old numbers and the new ones side by side
        is how you find out the new one is recording before dropping the old."""
        token = "c" * 32
        out, summary = self._build(analytics_token=token,
                                   umami_website_id=self._UID)
        self.assertEqual(summary["analytics_providers"],
                         ("Cloudflare Web Analytics", "Umami"))
        for page in out.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertIn(token, text, str(page))
            self.assertIn(self._UID, text, str(page))
            self.assertIn("sets no cookies", text, str(page))

    def test_a_self_hosted_umami_url_is_what_gets_published(self):
        """`cloud.umami.is` is on the common blocklists, so serving the script
        from the site's own domain is a real migration, not a preference."""
        src = "https://grownativeplants.ca/u.js"
        out, _ = self._build(umami_website_id=self._UID, umami_src=src)
        text = (out / "index.html").read_text(encoding="utf-8")
        self.assertIn(f'src="{src}"', text)
        self.assertNotIn("cloud.umami.is", text)

    def test_a_malformed_token_is_refused(self):
        """It lands inside a quoted JSON attribute on 2,000 pages. A loose
        check here is markup injection across the whole site."""
        for bad in ('x" onload="alert(1)', "short", "has spaces in it",
                    "tok'en"):
            with self.assertRaises(ValueError, msg=bad):
                self._build(analytics_token=bad)
        for bad in ("not-a-uuid", 'x" onload="alert(1)'):
            with self.assertRaises(ValueError, msg=bad):
                self._build(umami_website_id=bad)

    def test_a_build_cannot_inherit_the_previous_one_s_token(self):
        """The configuration is module state for the length of one build, so
        the seam that matters is what a *later* build sees. It is assigned on
        the way in rather than restored on the way out, so neither a rejected
        value nor a build that raised half way can put a beacon on the next
        one's pages."""
        with self.assertRaises(ValueError):
            self._build(analytics_token="nope")
        self._build(analytics_token="b" * 32)
        self._build(umami_website_id=self._UID)
        out, summary = self._build()
        self.assertFalse(summary["analytics"])
        self._assert_clean(out)


class TestThePagesClaimTheGroundTheyActuallyCover(unittest.TestCase):
    """The site said "prairie" and covers more and less than that (V2.76).

    Two errors in one word, and the author caught both by reading the site.

    **Geographically it claimed too much.** "Alberta and the Canadian prairies"
    reads as including Manitoba, and the layer stops at the Saskatchewan
    border -- `tools/ecoregions/common.py` sets `SUBJECT_PROVINCES =
    ("Alberta", "Saskatchewan")`. V2.75 removed the Manitoba filter chip for
    exactly this reason and left the prose saying it anyway.

    **Biologically it claimed the wrong thing.** Of 420 species with ranges,
    381 are in the Prairies ecozone -- but 341 are in Boreal Plains and 339 in
    Montane Cordillera. A third of the catalogue is boreal or montane ground.
    Worst of all, the map page called all 24 regions "the prairie ecoregions"
    when roughly four of them are; the rest are boreal, taiga and cordilleran.

    `Prairies` as the ecozone's own name is a proper noun from the National
    Ecological Framework and stays.
    """

    @classmethod
    def setUpClass(cls):
        cls.out = pathlib.Path(tempfile.mkdtemp(prefix="site_scope_"))
        render.write_site(_model(), str(cls.out), copy_photos=False)

    #: The phrases that make the false claim. Banning the *word* is wrong and
    #: the first draft of this test did it: "Grande Prairie" is a city on the
    #: map, "Prairie Bee" is an animal's name, and the About page's own
    #: correction contains "not all prairie". What is forbidden is describing
    #: the CATALOGUE or the LAYER as prairie, which is the claim that is false.
    FALSE_CLAIMS = (
        "canadian prairies",
        "prairie ecoregion",
        "prairie natives",
        "prairie plants",
        "prairie animals",
        "prairie habitat",
        "and the prairies",
    )

    def _prose(self, text):
        return " ".join(re.sub(r"<[^>]+>", " ", text).split()).lower()

    def test_no_page_describes_the_catalogue_as_prairie(self):
        offenders = []
        for page in sorted(self.out.rglob("*.html")):
            prose = self._prose(page.read_text(encoding="utf-8"))
            for claim in self.FALSE_CLAIMS:
                if claim in prose:
                    offenders.append(
                        f"{page.relative_to(self.out).as_posix()}: {claim!r}")
        self.assertEqual(offenders, [], f"false scope claim: {offenders}")

    def test_the_word_itself_is_allowed_where_it_is_true(self):
        """Grande Prairie is a real city and Prairies is a real ecozone. A
        guard that banned the word would have to be worked around, and a guard
        people work around stops being read."""
        for legitimate in ("Grande Prairie", "Prairies"):
            self.assertNotIn(legitimate.lower(),
                             [c for c in self.FALSE_CLAIMS])

    def test_the_tagline_names_both_provinces_and_only_those(self):
        self.assertIn("Alberta and Saskatchewan", render.TAGLINE)
        self.assertNotIn("prairies", render.TAGLINE.lower())

    def test_the_about_page_states_the_limit_rather_than_implying_it(self):
        from src.static_site_about import render_about
        # `_prose` lowercases, so the needles must too.
        flat = self._prose(render_about(_model()))
        self.assertIn("stop at the saskatchewan border", flat)
        self.assertIn("boreal or montane ground", flat)


class TestNoEmDashReachesAPage(unittest.TestCase):
    """The rule CLAUDE.md said was guarded, and was not (V2.75).

    `_esc` normalises em dashes, and every string that passes through it is
    safe. What nothing checked is the *templates*: a dash written straight into
    an f-string in one of the six page modules never meets `_esc` and lands on
    the page. That is not hypothetical -- it is how this test came to exist,
    after the V2.75 range copy shipped an `&mdash;` in exactly that position and
    the suite stayed green.

    Both spellings, because the HTML entity is the one a normaliser looking for
    U+2014 will miss.
    """

    @classmethod
    def setUpClass(cls):
        cls.out = pathlib.Path(tempfile.mkdtemp(prefix="site_dashes_"))
        render.write_site(_model(), str(cls.out), copy_photos=False)

    def test_no_page_carries_one(self):
        offenders = []
        for page in sorted(self.out.rglob("*.html")):
            text = page.read_text(encoding="utf-8")
            if "\u2014" in text or "&mdash;" in text or "&#8212;" in text:
                offenders.append(page.relative_to(self.out).as_posix())
        self.assertEqual(offenders, [], f"em dash on: {offenders}")

    def test_the_normaliser_still_does_its_half(self):
        self.assertNotIn("\u2014", render._esc("a \u2014 b"))


class TestTheMethodPage(unittest.TestCase):
    """What a shaded region claims, in the reader's words (F135, V2.75).

    An outside botanical review asked five things the site could not answer
    from any page on it -- what a record is, as of when, where in the region,
    why a region with two records is missing, and what the shading means. Each
    answer already existed in the repo and reached no reader.

    The numbers here are computed, never written down. A page about honesty
    that had gone stale would be the worst one on the site to hand-type.
    """

    @classmethod
    def setUpClass(cls):
        cls.model = _model()
        cls.html = method.render_method(cls.model)

    def test_it_states_the_floor_from_the_module_that_owns_it(self):
        from src.ecoregion_ranges import MIN_RECORDS
        self.assertIn(f"{MIN_RECORDS} records", self.html)

    def test_the_bands_come_from_the_module_that_owns_them(self):
        from src.ecoregion_ranges import CONFIDENCE_BANDS
        for floor, label in CONFIDENCE_BANDS:
            self.assertIn(label, self.html)
            self.assertIn(str(floor), self.html)

    def test_it_says_unshaded_is_not_absent(self):
        self.assertIn("not absent", self.html.replace("\n", " "))

    def test_it_says_recorded_is_not_native(self):
        self.assertIn("not native", self.html.replace("\n", " "))

    # V2.80: two tests were REMOVED here, and this note is the record.
    #
    # They required this page to explain the V2.76 buffer correction and name
    # the sliver region that caused most of it -- 135 species to 15. Their
    # argument was good: a reader comparing this site against an earlier copy
    # sees the numbers move and is owed an explanation.
    #
    # The author's instruction after reading the page was the other way:
    # *"you don't have to explain all process getting from past iterations of
    # the site to this one."* At 1,743 words the page had become a changelog,
    # and a caveat nobody finishes reading protects nobody.
    #
    # What did NOT lapse: the corrections section still links the public
    # repository, where every derivation, its plan and its numbers live. Move
    # the disclosure, do not delete it -- that rule is why these tests existed
    # and it is still the rule. If a future correction moves the numbers
    # visibly again, it needs a line here, not a section.

    def test_it_does_not_claim_the_buffer_is_still_present(self):
        """The specific false sentence, pinned so it cannot come back by a
        copy-paste from an older draft."""
        flat = " ".join(self.html.split())
        self.assertNotIn("which has not happened yet in this build", flat)

    def test_it_names_what_is_not_filtered(self):
        self.assertIn("identification-verified", self.html)

    def test_it_is_reachable_from_the_nav(self):
        from src.static_site_about import render_about
        self.assertIn('href="../method/"', render_about(self.model))

    def test_the_build_emits_it(self):
        out = pathlib.Path(tempfile.mkdtemp(prefix="site_method_"))
        render.write_site(self.model, str(out), copy_photos=False)
        self.assertTrue((out / "method" / "index.html").exists())


    def test_it_discloses_the_overlap_at_shared_borders(self):
        """V2.78: 0.81% of in-region records fall in the sliver where two
        simplified polygons overlap and are counted for both. The author's call
        was to leave it and say so -- picking a side would assert which side of
        a line we know we drew imprecisely, which is the mistake the buffer
        correction was about."""
        # Flattened: the sentence wraps in the source, and a disclosure that
        # a test can only find when it happens to fit on one line is a test
        # about line width.
        flat = " ".join(self.html.split())
        self.assertIn("counted in both", flat)
        self.assertIn("eight records in a thousand", flat)
        self.assertIn("Calgary", flat)

    def test_the_simplification_distance_is_not_typed_here(self):
        """It comes out of `ecoregion_map.CAVEAT`, which is itself checked
        against the polygon file's provenance. V2.69 shipped a caveat that had
        become false and left it on 432 pages for a whole increment."""
        from src.ecoregion_map import CAVEAT
        from src.static_site_method import _simplification
        self.assertIn(_simplification(), CAVEAT)
        self.assertIn(_simplification(), self.html)

class TestTheRangeSectionSaysWhatItClaims(unittest.TestCase):
    """The copy an outside review quoted back (F135, V2.75)."""

    def _section(self, **over):
        entry = {"name": "Test Plant", "scientific_name": "Testus plantus",
                 "ranges": [{"key": "aspen_parkland", "name": "Aspen Parkland",
                             "where": "central AB / SK", "occurrences": 312,
                             "confidence": "high",
                             "source": "GBIF occurrence search, "
                                       "retrieved 2026-08-18"}]}
        entry.update(over)
        return rangemod.range_section(entry, {"hubs": []}, 2)

    def test_it_no_longer_calls_one_region_a_range(self):
        """"A range seen three times" used *range* to mean one region entry,
        where a range is the area a species is documented to occupy. The
        review quoted this line and asked for terms to be defined."""
        self.assertNotIn("A range seen", self._section())

    def test_it_prints_the_retrieval_date(self):
        """On the row since schema v59, printed by the desktop, dropped by the
        website -- against a source that changes daily."""
        self.assertIn("retrieved 2026-08-18", self._section())

    def test_a_range_with_no_source_says_nothing_rather_than_guessing(self):
        section = self._section(ranges=[{"key": "aspen_parkland",
                                         "name": "Aspen Parkland",
                                         "where": "central AB / SK",
                                         "occurrences": 5,
                                         "confidence": "low"}])
        self.assertNotIn("Source:", section)

    def test_it_says_a_count_is_for_the_whole_region(self):
        """V2.80 removed the ecoregion MAP from the species page -- shading a
        whole region because records fall somewhere inside it is the
        overstatement the review objected to -- and kept the counts, which are
        facts. So the sentence is no longer about shading."""
        self.assertIn("somewhere</em> in the region", self._section())

    def test_it_says_unshaded_is_not_absent(self):
        self.assertIn("not the same as the plant being absent",
                      " ".join(self._section().split()))

    def test_it_links_out_to_the_live_maps(self):
        """The review's own suggestion: our snapshot is one day old the day
        after it is taken, and these are always current."""
        section = self._section()
        self.assertIn("gbif.org/species/search", section)
        self.assertIn("inaturalist.org/taxa/search", section)
        self.assertIn("Testus+plantus", section)

    def test_a_species_with_no_name_gets_no_broken_links(self):
        self.assertNotIn("gbif.org",
                         self._section(scientific_name="", row={}))


class TestTheRecordToggle(unittest.TestCase):
    """F147, V2.80. The author asked for the range picture with a way to
    switch between the two kinds of record. It is three radios and CSS: no
    script, so it survives scripting being off, the page being saved to a
    file, and being printed."""

    def _fig(self):
        """No database: `occurrence_map` looks the species up in the two
        shipped files by scientific name, so an entry dict is enough."""
        from src.static_site_points import occurrence_map
        return occurrence_map({"scientific_name": "Opuntia polyacantha",
                               "name": "Plains Prickly Pear Cactus"}, 2)

    def test_it_offers_both_specimens_and_observations(self):
        fig = self._fig()
        for label in (">Both<", ">Specimens<", ">Observations<"):
            self.assertIn(label, fig)

    def test_both_is_the_default(self):
        self.assertRegex(self._fig(), r'class="rk rk-all"[^>]*checked')
        self.assertNotRegex(self._fig(), r'class="rk rk-s"[^>]*checked')

    def test_the_inputs_are_siblings_of_the_map_not_nested_in_the_labels(self):
        """A general-sibling combinator cannot climb out of a wrapper. With the
        inputs inside `.ranketoggle` the buttons highlighted correctly and hid
        nothing -- a control that looks like it works and does not."""
        fig = self._fig()
        self.assertLess(fig.index('class="rk rk-o"'),
                        fig.index('class="ranketoggle"'))
        self.assertLess(fig.index('class="ranketoggle"'),
                        fig.index('class="rangemapwrap"'))

    def test_the_radio_group_is_named_per_species(self):
        """Two maps in one document sharing one group name are one group, so
        checking either unchecks the other."""
        self.assertIn('name="rk-opuntia-polyacantha"', self._fig())

    def test_the_stylesheet_can_actually_reach_the_layers(self):
        """The rule and the markup have to agree; they are in different files
        and nothing else checks that they do."""
        css = (pathlib.Path(__file__).parent.parent / "html" / "site"
               / "site.css").read_text(encoding="utf-8")
        self.assertIn(".rk-s:checked ~ .rangemapwrap .rangemap .layer-obs",
                      css)
        self.assertIn(".rk-o:checked ~ .rangemapwrap .rangemap .layer-spec",
                      css)

    def test_a_species_with_no_records_draws_no_map_and_no_toggle(self):
        """Nothing recorded draws nothing (P9). An empty frame with a working
        toggle would assert we looked everywhere."""
        from src.static_site_points import occurrence_map
        self.assertEqual(occurrence_map({"scientific_name": "Nothing sp."}, 2),
                         "")



if __name__ == "__main__":
    unittest.main()
