"""
static_site.py — the plant directory as a public website.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

F90 built the catalogue as a browsable reference work: thirteen filters, a
species page carrying its own evidence, every documented animal with the
specialists flagged. Then it shipped inside a 200 MB desktop installer for
Windows and macOS. We built the encyclopedia and made you install an `.exe` to
read it.

This module is the page **model**: which pages exist and what is on each. The
HTML lives in :mod:`src.static_site_render`, and the split is the usual one: a
model you can assert against in a test, a renderer you cannot.

**It writes no new knowledge and no second query layer.** Every species page is
:func:`src.plant_directory.species_entry`, the same call the desktop window
makes, so the web page and the desktop page are one page rendered twice and
cannot drift. The searchable axes come from :mod:`src.site_facets`, which is one
table driving the filter controls, the values baked into each index row, and the
landing pages generated per value.

**The URL shapes are conventional on purpose.** ``/plants/``,
``/plants/<slug>/`` and ``/plants/blooming-in/<month>/`` are what a plant
catalogue on the web looks like. Three axes are ours:

  * ``/plants/colour/<colour>/``, over a classifier that knows a grass has no
    bloom colour;
  * ``/plants/ecoregion/<region>/``, drawn as a map rather than listed;
  * ``/wildlife/<slug>/``, *which plants feed this animal*, over the documented
    edges. No other plant site has that page, because no other plant site holds
    the edges.

**P12:** the pages publish the fields the directory already surfaces, minus two
deliberate omissions recorded on the About page: the free-text notes column and
the ``medicinal`` use tag. No ethnobotanical content is added and no field is
relabelled to imply any. Publication tightens that rule rather than relaxing it:
a page on the open web is harder to withdraw than a panel in a desktop app.
"""

from __future__ import annotations

import datetime
import re
import unicodedata
from typing import Callable, Optional

from src.site_facets import FACETS, HUB_FACETS, index_row

_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")

#: Taxon key to plural heading, for the wildlife index.
TAXON_GROUPS: tuple = (
    ("bee", "Native bees"),
    ("lepidoptera", "Butterflies and moths"),
    ("bird", "Birds"),
    ("other_insect", "Other insects"),
    ("mammal", "Mammals"),
)

#: Headings where "<label> flowers" would read wrong. One entry, and it is
#: exactly the bucket that exists because those plants have no flower to speak
#: of: calling its page "Straw / green (grasses and sedges) flowers" would undo
#: the distinction the bucket was created to make.
COLOUR_PAGE_TITLES: dict = {
    "straw": "Grasses and sedges: straw and green seed heads",
}


def slugify(text: str) -> str:
    """A URL segment for a name.

    ASCII-folded (``Solidago × hybrida`` and the accented common names would
    otherwise emit percent-escapes into every link) and collapsed to
    ``lower-case-hyphens``. Never returns empty: an unnamed row would otherwise
    claim its parent directory's URL.
    """
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "unnamed"


def hub_slug(facet_key: str, value: str, label: str = "") -> str:
    """The URL segment for one value of a hub facet.

    **One function, called by both the page writer and every link**, because
    the first cut derived the slug from the label and linked to the raw value:
    ``plants/ecoregion/boreal-mixedwood-plain/`` was written and
    ``plants/ecoregion/boreal_mixedwood/`` was linked, 1,962 times. The link
    checker caught it, which is exactly the failure that check exists for.

    Bloom months are slugged by month name (``/blooming-in/june/`` reads better
    than ``/blooming-in/6/``); everything else slugs its stored value, so the
    URL matches what the data actually says.
    """
    if facet_key == "bloom":
        try:
            return _MONTHS[int(value) - 1].lower()
        except (TypeError, ValueError, IndexError):
            return slugify(label or value)
    return slugify(value)


def _unique_slugs(rows: list, key: str = "common_name") -> dict:
    """``{row id: slug}``, with collisions resolved deterministically.

    Two species sharing a common name is not hypothetical in a regional flora
    ("Stiff Goldenrod" is in this catalogue twice), and a static site resolves a
    collision by silently overwriting the earlier file. Suffixing by id keeps
    both pages and keeps the URL stable across rebuilds: a slug that renumbered
    when a row was added would break every inbound link.
    """
    seen: dict = {}
    for row in rows:
        seen.setdefault(slugify(row.get(key) or ""), []).append(row)
    out: dict = {}
    for slug, group in seen.items():
        if len(group) == 1:
            out[group[0]["id"]] = slug
            continue
        for row in sorted(group, key=lambda r: int(r.get("id") or 0)):
            out[row["id"]] = f"{slug}-{int(row['id'])}"
    return out


# ── The model ────────────────────────────────────────────────────────────────

def build_model(*, search_fn: Optional[Callable] = None,
                entry_fn: Optional[Callable] = None,
                list_fauna_fn: Optional[Callable] = None,
                plants_for_fauna_fn: Optional[Callable] = None,
                progress: Optional[Callable] = None) -> dict:
    """The whole site, as data. No HTML, no filesystem.

    Every collaborator is injectable, so the model, including the link graph a
    test walks for dead ends, can be built with no database at all.
    """
    if search_fn is None:
        from src.db.plants import search_plants as search_fn     # noqa: PLC0415
    if entry_fn is None:
        from src.plant_directory import species_entry as entry_fn  # noqa: PLC0415
    if list_fauna_fn is None:
        from src.db.fauna import list_fauna as list_fauna_fn     # noqa: PLC0415
    if plants_for_fauna_fn is None:
        from src.db.fauna import (                               # noqa: PLC0415
            plants_for_fauna as plants_for_fauna_fn)
    say = progress or (lambda _m: None)

    plants = sorted(search_fn(), key=lambda p: (p.get("common_name") or "").lower())
    slugs = _unique_slugs(plants)
    say(f"{len(plants)} species")

    species = []
    for i, plant in enumerate(plants, 1):
        entry = entry_fn(plant["id"]) or {}
        if not entry:
            continue
        entry["slug"] = slugs[plant["id"]]
        entry["row"] = plant
        entry["facets"] = index_row(plant)
        entry["brief"] = _brief(plant, slugs)
        species.append(entry)
        if i % 100 == 0:
            say(f"  ... {i} species pages built")

    briefs = {e["id"]: e["brief"] for e in species}

    model = {
        "built": datetime.date.today().isoformat(),
        "species": species,
        "slugs": slugs,
        "hubs": _hub_pages(species),
        "wildlife": _wildlife_pages(list_fauna_fn, plants_for_fauna_fn,
                                    slugs, briefs),
        "total_fauna": len(list_fauna_fn() or []),
        "stats": {},
    }
    model["stats"] = _stats(model)
    say(f"{len(model['wildlife'])} animals with documented plants")
    return model


def _brief(plant: dict, slugs: dict) -> dict:
    """One species as it appears in a listing: the smallest row that still says
    something useful, because these get embedded as JSON in the browse page."""
    from src.flower_colour import classify                      # noqa: PLC0415
    url, credit = photo_credit(plant)
    return {
        "id": plant.get("id"),
        "slug": slugs.get(plant.get("id"), ""),
        "name": plant.get("common_name") or "",
        "sci": plant.get("scientific_name") or "",
        "type": plant.get("plant_type") or "",
        "colour": classify(plant),
        "bloom": plant.get("bloom_period") or "",
        "height": plant.get("mature_height_meters"),
        "image": url,
        "credit": credit,
    }


def photo_credit(plant: dict) -> tuple:
    """``(url, credit line)`` for a plant row's photograph, or ``("", "")``.

    The single gate every thumbnail on the site passes through. Returns nothing
    at all when the attribution is missing: the licences the catalogue accepts
    (CC0 / CC BY / CC BY-SA) oblige credit, the 3D dossier already refuses on
    the same grounds, and publishing to the open web is not the moment to
    loosen it.
    """
    url = (plant.get("image_url") or "").strip()
    attribution = (plant.get("image_attribution") or "").strip()
    if not url or not attribution:
        return "", ""
    from src.image_cache import credit_line                     # noqa: PLC0415
    return url, credit_line(attribution, plant.get("image_license") or "")


def _hub_pages(species: list) -> list:
    """Landing pages for every facet marked ``hub``.

    One loop over :data:`src.site_facets.HUB_FACETS`, so an axis added there
    gains its pages here with no further wiring. A value nothing matches gets no
    page rather than an empty one, because an empty page is a URL that reads as
    a fact about the flora when it is a fact about the catalogue.
    """
    hubs = []
    for facet in HUB_FACETS:
        pages = []
        for value, label in facet.options:
            matched = [e for e in species if value in (e["facets"].get(facet.key) or [])]
            if not matched:
                continue
            pages.append({
                "slug": hub_slug(facet.key, value, label),
                "value": value,
                "name": label,
                "title": _hub_title(facet, value, label),
                "swatch": facet.swatches.get(value, ""),
                "intro": facet.blurb,
                "note": facet.note,
                "plants": [e["brief"] for e in matched],
            })
        if pages:
            hubs.append({"key": facet.key, "label": facet.label,
                         "dir": facet.hub_dir, "blurb": facet.blurb,
                         "note": facet.note, "pages": pages})
    return hubs


def _hub_title(facet, value: str, label: str) -> str:
    if facet.key == "colour":
        return COLOUR_PAGE_TITLES.get(value, f"{label} flowers")
    if facet.key == "bloom":
        return f"Plants blooming in {label}"
    if facet.key == "type":
        return f"Native {label.lower()}s of Alberta and the prairies"
    if facet.key == "ecoregion":
        return f"Plants of the {label}"
    return label


def _wildlife_pages(list_fauna_fn: Callable, plants_for_fauna_fn: Callable,
                    slugs: dict, briefs: dict) -> list:
    """One page per animal that has at least one documented plant.

    An animal with no edges gets no page: "0 plants support this species" would
    be published as a fact about the animal when it is a fact about our
    coverage (P9). The wildlife index says how many were left out and why.
    """
    from src.scene_dossier import _REL_FROM_ANIMAL, _TAXON_LABEL  # noqa: PLC0415
    fauna = list_fauna_fn() or []
    fauna_slugs = _unique_slugs(fauna)
    out = []
    for animal in fauna:
        rows = plants_for_fauna_fn(animal["id"]) or []
        if not rows:
            continue
        groups: dict = {}
        specialists = 0
        for row in rows:
            how = _REL_FROM_ANIMAL.get(row.get("relationship") or "", "uses")
            specialist = row.get("specificity") == "specialist"
            specialists += 1 if specialist else 0
            brief = dict(briefs.get(row.get("id")) or _brief(row, slugs))
            brief["specialist"] = specialist
            groups.setdefault(how, []).append(brief)
        out.append({
            "slug": fauna_slugs[animal["id"]],
            "id": animal["id"],
            "name": animal.get("common_name") or "",
            "scientific_name": animal.get("scientific_name") or "",
            "taxon": animal.get("taxon") or "",
            "taxon_label": _TAXON_LABEL.get(animal.get("taxon"), ""),
            "notes": animal.get("notes") or "",
            "total": len(rows),
            "specialists": specialists,
            "groups": [{"how": how, "items": sorted(items,
                                                    key=lambda i: i["name"])}
                       for how, items in sorted(groups.items(),
                                                key=lambda kv: -len(kv[1]))],
        })
    out.sort(key=lambda a: (a["taxon"], a["name"].lower()))
    return out


def species_ecoregions(entry: dict) -> dict:
    """``{ecoregion key: confidence}`` for the species page's map.

    Reads the *derived* ranges assembled by ``plant_directory.species_entry``,
    which carry occurrence counts from GBIF. A region present only in the
    heuristic column arrives with ``occurrences = 0`` and no confidence band,
    and the map draws it at its weakest fill rather than pretending.
    """
    out: dict = {}
    for row in entry.get("ranges") or []:
        key = (row.get("key") or "").strip()
        if key:
            out[key] = (row.get("confidence") or "").strip()
    return out


def _stats(model: dict) -> dict:
    """The numbers the front page leads with. Counted, never estimated: the
    front page of a reference work is the worst place to round."""
    species = model["species"]
    return {
        "species": len(species),
        "with_photo": sum(1 for e in species if _first_photo(e)),
        "animals": len(model["wildlife"]),
        "edges": sum(int((e.get("wildlife") or {}).get("total") or 0)
                     for e in species),
        "specialist_edges": sum(
            int((e.get("wildlife") or {}).get("specialists") or 0)
            for e in species),
        "facets": len(FACETS),
        "natives": sum(1 for e in species if e.get("native_to_alberta")),
        "verified_colour": sum(
            1 for e in species
            if (e.get("row") or {}).get("flower_colour_source")
            in ("name", "epithet")),
    }


def _first_photo(entry: dict) -> dict:
    """The photo a page shows, or ``{}``.

    **A photograph we cannot attribute is not published.** See
    :func:`photo_credit` for why that rule lives in one place.
    """
    for photo in entry.get("photos") or []:
        if ((photo.get("url") or "").strip()
                and (photo.get("attribution") or "").strip()):
            return photo
    return {}


# ── The link graph, so a test can walk it ────────────────────────────────────

def expected_paths(model: dict) -> set:
    """Every file :mod:`src.static_site_render` will write, as site-root-relative
    paths. The dead-link test builds this and asserts the rendered ``href``\\ s
    are a subset: a static site's characteristic failure is a 404 nobody clicks
    for six months."""
    paths = {"index.html", "plants/index.html", "wildlife/index.html",
             "about/index.html", "map/index.html", "sitemap.xml", "robots.txt",
             "assets/site.css", "assets/browse.js", "assets/catalogue.json"}
    for entry in model["species"]:
        paths.add(f"plants/{entry['slug']}/index.html")
    for hub in model["hubs"]:
        paths.add(f"{hub['dir']}/index.html")
        for page in hub["pages"]:
            paths.add(f"{hub['dir']}/{page['slug']}/index.html")
    for page in model["wildlife"]:
        paths.add(f"wildlife/{page['slug']}/index.html")
    return paths
