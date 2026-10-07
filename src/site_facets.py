"""
site_facets.py — everything about a plant you can search the website by.

Design principle P5 and P6 — see docs/DESIGN_PHILOSOPHY.md.

The catalogue holds 68 columns per species. V2.47's website published them and
let you filter on four. This module is the answer to "what else is in there that
somebody would actually search by", held as **data** so three things stay in
step automatically: the facet controls, the values baked into each row of the
browse index, and the hub pages generated per value.

Adding a facet here adds the control, the index field and the landing pages at
once. Nothing downstream enumerates facets by hand.

**Why the website's facets are not ``search_plants`` parameters.** The query
layer already takes thirty-odd and is shared with the desktop; bolting twenty
more on to serve a static site would make every desktop query carry them. The
site filters client-side over a JSON index instead, so a facet here costs one
derivation function and a few bytes per species, and the query layer is
untouched.

**A plant that records nothing for a facet matches no value in it**, the rule
``_month_filter`` set for bloom windows. Absence is never rendered as a value
(P9), so filters narrow honestly and the "not recorded" count is knowable.
"""

from __future__ import annotations

from typing import Callable

from src.flower_colour import COLOURS, classify
from src.local_flora import MIN_COLLECTIONS as _MIN, PLACES as _PLACES

_EDMONTON = _PLACES["edmonton"]

_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")


# ── Derivations ──────────────────────────────────────────────────────────────

# The derivations moved to src/site_facet_values.py (V3.12); imported back
# so every name this module exported still resolves here.
from src.site_facet_values import (  # noqa: F401
    SUBJECT_PROVINCES, _ALSO_SOLD_BY, _around, _availability,
    _band, _behaviour, _ecoregions, _edible,
    _flowers, _height, _maturity, _months,
    _photo, _provinces, _safety, _single,
    _tokens, _zones,
)


def _uses(plant: dict) -> list:
    return [u for u in _tokens(plant, "permaculture_uses")
            if u not in WITHHELD_ROLES]


# ── The vocabulary ───────────────────────────────────────────────────────────

class Facet:
    """One searchable axis.

    ``group`` decides which panel of the filter sidebar it appears in;
    ``hub`` marks the axes that also get generated landing pages, which is not
    all of them (nobody searches for "/plants/leaf-shape/oblanceolate/").
    """

    def __init__(self, key, label, options, derive, *, group="Plant",
                 hub=False, hub_dir="", swatches=None, blurb="", note="",
                 combine="any"):
        self.key = key
        self.label = label
        self.options = options            # ((value, label), ...)
        self.derive = derive
        self.group = group
        self.hub = hub
        self.hub_dir = hub_dir
        self.swatches = swatches or {}
        self.blurb = blurb
        self.note = note
        #: How several ticked values in THIS facet combine.
        #:
        #: ``any`` (the default) is what a colour or a month means: yellow OR
        #: blue. ``all`` is what safety means, and getting that wrong was a
        #: reported bug: ticking "no known pet toxicity" gave 388 plants and
        #: adding "no known human toxicity" gave **404**, because the union of
        #: two safety claims is larger than either. Somebody ticking both wants
        #: a plant that is safe around the dog *and* the kids, so the count has
        #: to fall. Roles are ``all`` for the same reason and to match
        #: ``search_plants``, which has ANDed use tags since V1.85.
        self.combine = combine

    def values(self, plant: dict) -> list:
        try:
            return [str(v) for v in (self.derive(plant) or [])]
        except Exception:                                    # noqa: BLE001
            return []


def _from_db(column: str, labels: dict) -> tuple:
    return tuple((value, label) for value, label in labels.items())


_TYPE = {
    "tree": "Tree", "shrub": "Shrub", "vine": "Vine", "wildflower": "Wildflower",
    "herb": "Herb / foliage", "groundcover": "Groundcover", "grass": "Grass",
    "sedge": "Sedge", "rush": "Rush", "fern": "Fern",
    "aquatic": "Aquatic / wetland",
}
_ROLES = {
    "keystone_species": "Keystone species", "host_plant": "Caterpillar host",
    "pollinator": "Pollinator support", "bird_food": "Bird food",
    "nesting_material": "Nesting material", "wildlife_habitat": "Wildlife habitat",
    "nitrogen_fixer": "Nitrogen fixer", "soil_builder": "Soil builder",
    "early_successional": "Pioneer", "canopy_layer": "Canopy layer",
    "windbreak": "Windbreak", "hedge": "Hedge", "groundcover": "Groundcover",
    "erosion_control": "Erosion control",
    "aquatic": "Aquatic", "riparian_filter": "Riparian filter",
    "ornamental": "Ornamental", "medicinal": "Medicinal",
}

#: Use tags the desktop exposes and the website does not.
#:
#: **Empty since V2.50, on the author's decision.** V2.48 withheld ``medicinal``
#: on the reasoning that a public, indexed "medicinal native plants" page is the
#: same act as publishing the traditional-use notes. The author has since ruled
#: that the tag itself is a generic horticultural category rather than sourced
#: traditional knowledge, and can be published.
#:
#: The mechanism stays, because the distinction it draws is still the right one
#: and the next tag may not be so easy. **The free-text ``notes`` column remains
#: withheld** either way: a use *category* is not the same artefact as a
#: paragraph describing how a plant was prepared and for what (P12).
WITHHELD_ROLES: tuple = ()


def _ecoregion_options() -> tuple:
    """Ecozone, then its ecoregions, then the moisture niches.

    The desktop draws this vocabulary as a collapsible tree; the website's
    sidebar is a flat list of checkboxes, so the hierarchy survives here as
    *order* — each ecozone immediately followed by what is inside it. Alberta's
    subregions are deliberately left out: 21 more checkboxes would double the
    control to serve one province, and no species is tagged at that level.

    The ecozones are not decoration. 304 species carry `zone_prairies` and
    nothing finer, and without an option they rendered as an unlabelled value —
    which is a blank line in the sidebar, not an error anyone would notice.
    """
    from src.ecoregion import MOISTURE_NICHES                # noqa: PLC0415
    from src.ecoregion_tree import tree                      # noqa: PLC0415

    out = []
    for zone_key, zone_name, _lvl, regions in tree():
        out.append((zone_key, zone_name))
        out.extend((key, name) for key, name, _l, _subs in regions)
    out.extend((key, name) for key, name, _where in MOISTURE_NICHES)
    return tuple(out)


FACETS: tuple = (
    # First, because it is the one filter used as a worklist rather than as a
    # plant character, and the author asked for it near the top.
    Facet("photo", "Photograph",
          (("photo", "Has a photograph"), ("no-photo", "No photograph yet")),
          _photo, group="Looks",
          # {with_photo}/{species} rather than a written-down number (V2.75).
          # This said "323 of 434" while the About page computed the same
          # sentence from the catalogue, so two pages of one site disagreed --
          # and the true figure had been wrong since the last species was
          # added. Every count on this site is computed at build time; this
          # one had quietly opted out.
          note="{with_photo} of {species} species have an openly-licensed "
               "photograph we can credit. The rest are the gap."),
    Facet("type", "Plant type", tuple(_TYPE.items()), _single("plant_type"),
          group="Plant", hub=True, hub_dir="plants/type",
          blurb="The growth form, which is the first thing that decides where "
                "a plant can go."),
    Facet("colour", "Flower colour",
          tuple((key, label) for key, label, _s, _n in COLOURS),
          lambda p: [classify(p)] if classify(p) else [],
          group="Looks", hub=True, hub_dir="plants/colour",
          swatches={key: swatch for key, _l, swatch, _n in COLOURS},
          blurb="Grasses and sedges are grouped separately: they are "
                "wind-pollinated, so what you see is the seed head."),
    Facet("bloom", "Blooms in",
          tuple((str(i), m) for i, m in enumerate(_MONTHS, 1)),
          lambda p: [str(m) for m in _months(p, "bloom_period")],
          group="Season", hub=True, hub_dir="plants/blooming-in",
          blurb="A species with no recorded window is listed under no month."),
    Facet("fruit", "Fruits in",
          tuple((str(i), m) for i, m in enumerate(_MONTHS, 1)),
          lambda p: [str(m) for m in _months(p, "fruit_period")],
          group="Season"),
    Facet("flowers", "Showy flower",
          (("showy", "Has a showy flower"),
           ("not-showy", "No showy flower")),
          _flowers, group="Looks",
          note="Wind-pollinated plants flower without advertising. "
               "“No showy flower” is a fact about the plant, not a "
               "gap in the record."),
    Facet("sun", "Sun",
          (("full_sun", "Full sun"), ("partial_shade", "Partial shade"),
           ("full_shade", "Full shade")),
          lambda p: _tokens(p, "sun_requirement"), group="Site"),
    Facet("water", "Water",
          (("low", "Low"), ("medium", "Medium"), ("moderate", "Moderate"),
           ("high", "High")),
          lambda p: _tokens(p, "water_needs"), group="Site"),
    Facet("ecoregion", "Ecoregion", _ecoregion_options(), _ecoregions,
          group="Site", hub=True, hub_dir="plants/ecoregion",
          blurb="Where the species has been recorded. Occurrence counts and a "
                "confidence band travel with every region on the species "
                "page."),
    Facet("zone", "Hardiness zone",
          tuple((str(z), f"Zone {z}") for z in range(1, 11)), _zones,
          group="Site",
          note="Matches any plant whose recorded range covers the zone."),
    Facet("height", "Mature height",
          (("ankle", "Under 30 cm"), ("knee", "30 cm to 1 m"),
           ("head", "1 to 3 m"), ("small-tree", "3 to 10 m"),
           ("tall-tree", "Over 10 m")),
          _height, group="Plant"),
    Facet("lifecycle", "Life cycle",
          (("perennial", "Perennial"), ("annual", "Annual"),
           ("biennial", "Biennial")),
          _single("perennial_or_annual"), group="Plant"),
    Facet("foliage", "Foliage",
          (("deciduous", "Deciduous"), ("evergreen", "Evergreen"),
           ("herbaceous", "Herbaceous"), ("semi-evergreen", "Semi-evergreen")),
          _single("deciduous_evergreen"), group="Plant"),
    Facet("growth", "Growth rate",
          (("slow", "Slow"), ("moderate", "Moderate"), ("fast", "Fast")),
          _single("growth_rate"), group="Plant"),
    Facet("maturity", "Time to maturity",
          (("fast", "Under 3 years"), ("few-years", "3 to 5 years"),
           ("decade", "6 to 15 years"), ("generation", "16 years or more")),
          _maturity, group="Plant"),
    Facet("role", "Ecological role", tuple(_ROLES.items()), _uses,
          group="Ecology", hub=True, hub_dir="plants/for", combine="all",
          blurb="What the plant does, from the tags the catalogue records "
                "against it."),
    Facet("safety", "Safety",
          (("pet-safe", "No known pet toxicity"),
           ("child-safe", "No known human toxicity"),
           ("thornless", "No thorns")),
          _safety, group="Practical", combine="all",
          note="Ticking two narrows to plants that satisfy both. A denylist: "
               "a species nobody has assessed passes, so silence is not a "
               "clearance."),
    Facet("behaviour", "Spread",
          (("well-behaved", "Stays put"), ("spreads", "Spreads vigorously")),
          _behaviour, group="Practical",
          note="Only 19 species have an assessed spread habit; the rest "
               "appear under neither."),
    Facet("availability", "Where to buy",
          (("big_box", "Big-box store"), ("garden_centre", "Garden centre"),
           ("native_specialist", "Native nursery"),
           ("seed_or_plug", "Seed or plug only"), ("rare", "Rare")),
          _availability, group="Practical",
          note="Anything common enough for a big-box store or a greenhouse is "
               "also listed under the native nursery, because a specialist "
               "grower stocks it too. Seed-or-plug species and the rare ones "
               "are not: those you order, or go looking for."),
    # Manitoba was an option here and is not one any more (V2.75).
    #
    # An outside review asked why the prairie provinces stopped at two, which
    # is a fair question with a real answer: `tools/ecoregions/common.py` sets
    # `SUBJECT_PROVINCES = ("Alberta", "Saskatchewan")`, so no polygon, no
    # occurrence query and no species list has ever covered Manitoba. What
    # could not be defended is offering the filter anyway -- exactly ONE row
    # in the catalogue carries MB, so ticking it returned a single species and
    # implied a coverage that does not exist.
    #
    # Removing the chip is the honest half. Adding Manitoba for real is a
    # polygon rebuild plus a full re-fetch, and it is a backlog row.
    Facet("province", "Native to",
          (("AB", "Alberta"), ("SK", "Saskatchewan")),
          _provinces, group="Site",
          note="This catalogue covers Alberta and Saskatchewan. Manitoba "
               "shares several of these ecoregions and is not surveyed here "
               "yet."),
    # F220 (V3.12), the owner's "Edmonton specific native plants". Its own
    # facet rather than a third "Native to" value, because the two claims rest
    # on different evidence: VASCAN for a province, herbarium collections and
    # the owner's review for a place.
    Facet("around", "Native area", (("edmonton", "Edmonton region"),),
          _around, group="Site", hub=True, hub_dir="plants/native-area",
          blurb=(f"Native to Alberta as VASCAN records it, and collected at "
                 f"least {_MIN} times within {_EDMONTON['radius_km']:g} km of "
                 "downtown Edmonton (herbarium specimens), or confirmed on "
                 "review. Plants of the mountains and the dry south, native "
                 "elsewhere in Alberta, drop out."),
          note="A species collected fewer times is left out until it is "
               "reviewed, which is not the same as foreign to Edmonton. The "
               "Method page says how this is decided."),
    Facet("edible", "Edible", (("edible", "Has edible parts"),), _edible,
          group="Practical",
          note="Identification is yours to confirm. This is a catalogue, not "
               "a foraging guide."),
)

#: Sidebar panel order.
GROUPS: tuple = ("Looks", "Season", "Site", "Ecology", "Plant", "Practical")

FACETS_BY_KEY: dict = {f.key: f for f in FACETS}

#: The axes that also become browsable landing pages.
HUB_FACETS: tuple = tuple(f for f in FACETS if f.hub)


def index_row(plant: dict) -> dict:
    """``{facet key: [values]}`` for one plant, for the browse index."""
    return {f.key: f.values(plant) for f in FACETS}


def option_labels(key: str) -> dict:
    facet = FACETS_BY_KEY.get(key)
    return dict(facet.options) if facet else {}
