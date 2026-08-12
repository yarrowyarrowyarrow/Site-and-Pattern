"""
static_site.py — the plant directory as a public website.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

F90 built the catalogue as a browsable reference work: thirteen filters, a
species page carrying its own evidence, every documented animal with the
specialists flagged. Then it shipped inside a 200 MB desktop installer for
Windows and macOS. We built the encyclopedia and made you install an `.exe` to
read it.

This module is the page **model** — which pages exist and what is on each. The
HTML lives in :mod:`src.static_site_render`, and the split is the usual one: a
model you can assert against in a test, a renderer you cannot.

**It writes no new knowledge and no second query layer.** Every species page is
:func:`src.plant_directory.species_entry` — the same call the desktop window
makes — so the web page and the desktop page are one page rendered twice and
cannot drift. The listing axes are `search_plants` filters that already existed.

**The URL shapes are conventional on purpose.** ``/plants/``,
``/plants/<slug>/`` and ``/plants/blooming-in/<month>/`` are what an ornamental
catalogue on the web looks like, and there is nothing to gain by inventing a
different vocabulary for the same pages. Two axes are ours:

  * ``/plants/colour/<colour>/`` — the V2.47 filter, and the cheapest possible
    proof it works;
  * ``/wildlife/<slug>/`` — *which plants feed this animal*, over the 361
    documented edges. This is the page no other plant site has, because no other
    plant site holds the edges.

**P12:** the pages publish exactly the fields the directory already surfaces —
horticultural and permaculture use tags, edible parts, documented ecological
relationships. No ethnobotanical content is added and no field is relabelled to
imply any. Publication tightens that rule rather than relaxing it: a page on the
open web is harder to withdraw than a panel in a desktop app.
"""

from __future__ import annotations

import datetime
import re
import unicodedata
from typing import Callable, Optional

from src.flower_colour import COLOURS

_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")

#: ``(slug, label, search_plants kwarg, blurb)`` — the role landing pages.
#: Drawn from the toggles the directory already exposes, narrowed to the ones
#: that answer a question somebody actually types into a search engine.
ROLES: tuple = (
    ("keystone", "Keystone species", {"keystone_only": True},
     "Tallamy's high-value genera — the plants that anchor a local food web. "
     "A small number of genera support most of the caterpillars."),
    ("larval-host", "Caterpillar host plants", {"host_plant_only": True},
     "Plants that feed caterpillars, which is what feeds nestling birds. "
     "A chickadee brood needs several thousand of them."),
    ("bird-food", "Bird food plants", {"bird_food_only": True},
     "Documented seed or fruit food for birds."),
    ("pollinator", "Pollinator plants", {"pollinator_only": True},
     "Documented nectar or pollen sources."),
    ("specialist-support", "Plants that feed a specialist",
     {"supports_specialist": True},
     "Supports at least one animal that has nowhere else to go. A generalist "
     "losing this plant finds another; a specialist does not."),
    ("nitrogen-fixer", "Nitrogen fixers", {"nfixer_only": True},
     "Feed the soil rather than needing it fed."),
    ("edible", "Edible plants", {"edible_only": True},
     "Species with parts recorded as edible for people. Identification is "
     "yours to confirm — this is a catalogue, not a foraging guide."),
    ("pet-safe", "Pet-safe plants", {"pet_safe_only": True},
     "No recorded toxicity to pets. Silence is not a guarantee: a species "
     "nobody has assessed passes this filter."),
)

#: Headings where "<label> flowers" would read wrong. One entry today, and it is
#: exactly the bucket that exists because those plants have no flower to speak
#: of — calling its page "Straw / green (grasses & sedges) flowers" would undo
#: the distinction the bucket was created to make.
COLOUR_PAGE_TITLES: dict = {
    "straw": "Grasses and sedges — straw and green seed heads",
}

#: Taxon key → plural heading, for the wildlife index.
TAXON_GROUPS: tuple = (
    ("bee", "Native bees"),
    ("lepidoptera", "Butterflies & moths"),
    ("bird", "Birds"),
    ("other_insect", "Other insects"),
    ("mammal", "Mammals"),
)


def slugify(text: str) -> str:
    """A URL segment for a name.

    ASCII-folded (``Solidago × ...`` and the accented common names would
    otherwise emit percent-escapes into every link) and collapsed to
    ``lower-case-hyphens``. Never returns empty — an unnamed row would
    otherwise claim the parent directory's URL.
    """
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "unnamed"


def _unique_slugs(rows: list, key: str = "common_name") -> dict:
    """``{row id: slug}``, with collisions resolved deterministically.

    Two species sharing a common name is not hypothetical in a regional flora
    ("Wild Rose"), and a static site resolves a collision by silently
    overwriting the earlier file. Suffixing by id keeps both pages and keeps the
    URL stable across rebuilds — a slug that renumbers when a row is added would
    break every inbound link.
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

    Every collaborator is injectable, so the model — including the link graph a
    test walks for dead ends — can be built with no database at all.
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
        species.append(entry)
        if i % 100 == 0:
            say(f"  … {i} species pages built")

    by_id = {e["id"]: e for e in species}

    model = {
        "built": datetime.date.today().isoformat(),
        "species": species,
        "slugs": slugs,
        "months": _month_pages(search_fn, slugs),
        "colours": _colour_pages(search_fn, slugs),
        "roles": _role_pages(search_fn, slugs),
        "wildlife": _wildlife_pages(list_fauna_fn, plants_for_fauna_fn, slugs),
        # How many animals exist at all, so the wildlife index can say how many
        # it left out. Carried on the model rather than re-queried at render
        # time — everything else here is injectable and one un-injected DB call
        # in the renderer would make the fixture site disagree with itself.
        "total_fauna": len(list_fauna_fn() or []),
        "stats": {},
    }
    model["stats"] = _stats(model, by_id)
    say(f"{len(model['wildlife'])} animals with documented plants")
    return model


def _brief(plant: dict, slugs: dict) -> dict:
    """One species as it appears in a listing — the smallest row that still says
    something useful, because these get embedded as JSON in the browse page.

    The thumbnail goes through :func:`photo_credit` for the same reason the
    species page does: a CC BY photograph obliges attribution *wherever it is
    used*, and a listing card is a use. An unattributable photo yields no
    thumbnail rather than a bare one.
    """
    from src.flower_colour import classify
    url, credit = photo_credit(plant)
    return {
        "id": plant.get("id"),
        "slug": slugs.get(plant.get("id"), ""),
        "name": plant.get("common_name") or "",
        "scientific_name": plant.get("scientific_name") or "",
        "type": plant.get("plant_type") or "",
        "colour": classify(plant),
        "bloom": plant.get("bloom_period") or "",
        "sun": plant.get("sun_requirement") or "",
        "water": plant.get("water_needs") or "",
        "height_m": plant.get("mature_height_meters"),
        "native": bool(plant.get("native_to_alberta")),
        "image": url,
        "credit": credit,
    }


def photo_credit(plant: dict) -> tuple:
    """``(url, credit line)`` for a plant row's photograph, or ``("", "")``.

    The single gate every thumbnail on the site passes through. Returns nothing
    at all when the attribution is missing — the rule the 3D dossier already
    follows, and publishing to the open web is not the moment to loosen it.
    """
    url = (plant.get("image_url") or "").strip()
    attribution = (plant.get("image_attribution") or "").strip()
    if not url or not attribution:
        return "", ""
    from src.image_cache import credit_line                     # noqa: PLC0415
    return url, credit_line(attribution, plant.get("image_license") or "")


def _month_pages(search_fn: Callable, slugs: dict) -> list[dict]:
    out = []
    for month, name in enumerate(_MONTHS, 1):
        rows = search_fn(bloom_months=[month])
        out.append({
            "slug": name.lower(), "month": month, "name": name,
            "title": f"Plants blooming in {name}",
            "intro": (
                f"{len(rows)} species in the catalogue have a recorded bloom "
                f"window covering {name}. A species with no recorded window is "
                f"not listed — we do not know when it flowers, which is not the "
                f"same as knowing it does not flower in {name}."),
            "plants": [_brief(r, slugs) for r in
                       sorted(rows, key=lambda r: (r.get("common_name") or "").lower())],
        })
    return out


def _colour_pages(search_fn: Callable, slugs: dict) -> list[dict]:
    out = []
    for key, label, swatch, note in COLOURS:
        rows = search_fn(flower_colours=[key])
        if not rows:
            continue                     # an empty colour gets no page to 404 on
        out.append({
            "slug": key, "key": key, "name": label, "swatch": swatch,
            "title": COLOUR_PAGE_TITLES.get(key, f"{label} flowers"),
            "intro": note,
            "plants": [_brief(r, slugs) for r in
                       sorted(rows, key=lambda r: (r.get("common_name") or "").lower())],
        })
    return out


def _role_pages(search_fn: Callable, slugs: dict) -> list[dict]:
    out = []
    for slug, label, kwargs, blurb in ROLES:
        rows = search_fn(**kwargs)
        if not rows:
            continue
        out.append({
            "slug": slug, "name": label, "title": label, "intro": blurb,
            "plants": [_brief(r, slugs) for r in
                       sorted(rows, key=lambda r: (r.get("common_name") or "").lower())],
        })
    return out


def _wildlife_pages(list_fauna_fn: Callable, plants_for_fauna_fn: Callable,
                    slugs: dict) -> list[dict]:
    """One page per animal that has at least one documented plant.

    An animal with no edges gets no page: a page reading "0 plants support this
    species" would be published as a fact about the animal when it is a fact
    about our coverage (P9). The wildlife index says how many were omitted and
    why, which is the honest place for that number.
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
            brief = _brief(row, slugs)
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
            "groups": [{"how": how, "items": items}
                       for how, items in sorted(groups.items(),
                                                key=lambda kv: -len(kv[1]))],
        })
    out.sort(key=lambda a: (a["taxon"], a["name"].lower()))
    return out


def _stats(model: dict, by_id: dict) -> dict:
    """The numbers the front page leads with. Counted, never estimated — the
    front page of a reference work is the worst place to round."""
    species = model["species"]
    edges = sum(int((e.get("wildlife") or {}).get("total") or 0) for e in species)
    return {
        "species": len(species),
        "with_photo": sum(1 for e in species if _first_photo(e)),
        "animals": len(model["wildlife"]),
        "edges": edges,
        "specialist_edges": sum(
            int((e.get("wildlife") or {}).get("specialists") or 0)
            for e in species),
        "colours": len(model["colours"]),
        "natives": sum(1 for e in species if e.get("native_to_alberta")),
        "by_id": len(by_id),
    }


def _first_photo(entry: dict) -> dict:
    """The photo a card shows, or ``{}``.

    **A photograph we cannot attribute is not published.** The licences the
    catalogue accepts (CC0 / CC BY / CC BY-SA) oblige credit, and the 3D dossier
    already refuses on the same grounds — putting the pages on the open web is
    not the moment to loosen it.
    """
    for photo in entry.get("photos") or []:
        if (photo.get("url") or "").strip() and (photo.get("attribution") or "").strip():
            return photo
    return {}


# ── The link graph, so a test can walk it ────────────────────────────────────

def expected_paths(model: dict) -> set:
    """Every file :mod:`src.static_site_render` will write, as site-root-relative
    paths. The dead-link test builds this and asserts the rendered ``href``\\ s
    are a subset — a static site's characteristic failure is a 404 nobody
    clicks for six months."""
    paths = {"index.html", "plants/index.html", "wildlife/index.html",
             "about/index.html", "sitemap.xml", "robots.txt",
             "assets/site.css", "assets/catalogue.json",
             # The three browse hubs. Every one is linked from the header of
             # every page, so they are written unconditionally — a header link
             # into an axis that happens to be empty is a sitewide dead link.
             "plants/blooming-in/index.html", "plants/colour/index.html",
             "plants/for/index.html"}
    for entry in model["species"]:
        paths.add(f"plants/{entry['slug']}/index.html")
    for page in model["months"]:
        paths.add(f"plants/blooming-in/{page['slug']}/index.html")
    for page in model["colours"]:
        paths.add(f"plants/colour/{page['slug']}/index.html")
    for page in model["roles"]:
        paths.add(f"plants/for/{page['slug']}/index.html")
    for page in model["wildlife"]:
        paths.add(f"wildlife/{page['slug']}/index.html")
    return paths
