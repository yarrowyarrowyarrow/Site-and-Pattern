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

_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")


# ── Derivations ──────────────────────────────────────────────────────────────

def _tokens(plant: dict, column: str) -> list:
    """A comma-delimited column as a clean list. Several columns hold a set
    rather than a value (a plant that tolerates sun *and* part shade)."""
    return [t.strip() for t in (plant.get(column) or "").split(",") if t.strip()]


#: The provinces this site is a catalogue OF. Not every province a plant may be
#: native to: `native_provinces` records what is true about the plant, and this
#: records what the site can answer questions about.
SUBJECT_PROVINCES = ("AB", "SK")


def _provinces(plant: dict) -> list:
    """``native_provinces``, clipped to what this site actually covers.

    V2.75: dropping Manitoba from the facet's *options* was not enough. One row
    in the catalogue carries ``SK,MB`` (a genuine eastern-prairie native), so
    the extractor kept emitting an ``MB`` value with no label behind it — and
    an unlabelled value renders as an empty checkbox, which is the silent
    failure `test_every_value_in_use_has_a_label` exists to catch. It caught it.

    Clipping here rather than editing the row, because the row is right: that
    plant *is* native to Manitoba. What is not true is that this catalogue can
    tell you anything about Manitoba, and a filter is a promise that it can.
    """
    return [t for t in _tokens(plant, "native_provinces")
            if t.upper() in SUBJECT_PROVINCES]


def _months(plant: dict, column: str) -> list:
    try:
        from src.habitat_score import parse_month_range      # noqa: PLC0415
        return sorted(parse_month_range(plant.get(column) or ""))
    except Exception:                                        # noqa: BLE001
        return []


def _zones(plant: dict) -> list:
    """Every zone between the recorded bounds. Filtering by zone means "will it
    survive here", so a plant rated 2 to 7 has to match a search for 4."""
    def _n(value):
        try:
            return int(float(str(value).rstrip("?").strip()))
        except (TypeError, ValueError):
            return None
    lo, hi = _n(plant.get("hardiness_zone_min")), _n(plant.get("hardiness_zone_max"))
    if lo is None and hi is None:
        return []
    lo = lo if lo is not None else hi
    hi = hi if hi is not None else lo
    return [str(z) for z in range(min(lo, hi), max(lo, hi) + 1)]


def _band(value, edges: tuple, keys: tuple) -> list:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return []
    for edge, key in zip(edges, keys):
        if n < edge:
            return [key]
    return [keys[-1]]


def _height(plant: dict) -> list:
    return _band(plant.get("mature_height_meters"),
                 (0.3, 1.0, 3.0, 10.0, float("inf")),
                 ("ankle", "knee", "head", "small-tree", "tall-tree"))


def _maturity(plant: dict) -> list:
    return _band(plant.get("years_to_maturity"), (3, 6, 16, float("inf")),
                 ("fast", "few-years", "decade", "generation"))


def _flowers(plant: dict) -> list:
    """Showy flower or not.

    Reported: *"showy flower seems incorrect as it includes sedges and other
    plants I'm assuming don't have showy flowers."* It did, and for the same
    reason the colour filter nearly filed the grasses under yellow: 81 grasses,
    sedges and rushes carry a hex and a ``flower_form`` of ``plume``, which the
    first version read as "has a flower, therefore showy". A wind-pollinated
    plant has no reason to advertise and does not; the plume is a seed head.

    So the wind-pollinated families are **never** showy, whatever their hex
    says, which is exactly the rule ``src.flower_colour`` already applies. A
    recorded ``flower_form`` of ``none`` is likewise a real botanical answer
    rather than a missing one, and a species with neither field recorded
    appears under neither value.
    """
    from src.flower_colour import WIND_POLLINATED_TYPES        # noqa: PLC0415
    form = (plant.get("flower_form") or "").strip().lower()
    colour = (plant.get("flower_color") or "").strip()
    if not form and not colour:
        return []
    if (plant.get("plant_type") or "") in WIND_POLLINATED_TYPES:
        return ["not-showy"]
    return ["showy"] if (colour and form != "none") else ["not-showy"]


def _uses(plant: dict) -> list:
    return [u for u in _tokens(plant, "permaculture_uses")
            if u not in WITHHELD_ROLES]


def _safety(plant: dict) -> list:
    """A DENYLIST, exactly as ``search_plants`` reads it. "Pet safe" means no
    *known* toxicity; a species nobody has assessed passes, and the label on the
    site says so rather than implying a clearance nobody issued."""
    out = []
    if (plant.get("toxicity_pets") or "") not in ("low", "high"):
        out.append("pet-safe")
    if (plant.get("toxicity_humans") or "") not in ("low", "high"):
        out.append("child-safe")
    if not plant.get("has_thorns"):
        out.append("thornless")
    return out


def _behaviour(plant: dict) -> list:
    habit = (plant.get("spread_habit") or "").strip()
    if not habit:
        return []
    return (["spreads"] if habit in ("aggressive_rhizomatous", "self_seeding")
            else ["well-behaved"])


def _ecoregions(plant: dict) -> list:
    """The plant's regions, plus every region **above** them.

    V2.68: the vocabulary gained two levels above the ecoregion (ecozone) and
    one below (Alberta natural subregion), and the migrated heuristic tags rest
    wherever the evidence put them — 304 species carry `zone_prairies` and
    nothing finer.

    Only the *upward* expansion is baked in, and the asymmetry is deliberate.
    Upward is definitional: a plant recorded in Mixed Grassland is in the
    Prairies, so ticking the ecozone must find it. Downward is not — writing
    every Prairies ecoregion into the row of a plant known only at the ecozone
    would put five specific claims on a species page where the evidence
    supports one general one, which is P9 failing in public. The desktop filter
    matches downward too because it is answering "what could I plant here?";
    a published page is making a statement about the species.
    """
    from src.ecoregion_tree import ancestors_of              # noqa: PLC0415

    out = _tokens(plant, "ecoregion")
    for key in list(out):
        for parent in sorted(ancestors_of(key)):
            if parent not in out:
                out.append(parent)
    return out


def _photo(plant: dict) -> list:
    """Has a credited photograph, or does not.

    Both values, on request: *"it should also have an option for no photo, so
    those can be filtered and I can easily see the ones that still need that."*
    This is the one facet whose *absence* is the useful query, because it is a
    worklist rather than a plant character.
    """
    has = ((plant.get("image_url") or "").strip()
           and (plant.get("image_attribution") or "").strip())
    return ["photo"] if has else ["no-photo"]


def _edible(plant: dict) -> list:
    return ["edible"] if (plant.get("edible_parts") or "").strip() else []


#: A plant's recorded tier, and the *other* shelves it should also appear on.
#: Read down: if the big-box store has it, so does a greenhouse, and so does a
#: specialist grower. The implication only runs one way, which is the whole
#: point of the table.
#:
#: Everything not listed here appears under its own tier alone:
#:
#: * ``seed_or_plug`` — the grasses, sedges and cattails, sold as seed or as
#:   plugs and not as a potted plant. The author's exclusion, and correct: a
#:   reader ticking "native nursery" wants to leave with something in a pot.
#: * ``rare`` — the lady's slipper, the gentians, the wood lily. A specialist
#:   is the likeliest place to find one *if anyone has one*, which is not the
#:   same as stocking it. Promising these on the nursery shelf would be the
#:   original bug pointed the other way.
#: * ``native_specialist`` — already the narrowest tier.
#:
#: This deliberately does NOT reuse ``db/nurseries.py:_AVAILABILITY_TO_SELLS``,
#: which answers a different question: *which shops do I list for this plant*,
#: where an extra shop costs the reader one line to skim. Here an extra plant
#: is a wrong answer, so the two tables are allowed to differ and the reason is
#: written down instead of the disagreement being tidied away.
_ALSO_SOLD_BY: dict = {
    "big_box":       ("garden_centre", "native_specialist"),
    "garden_centre": ("native_specialist",),
}


def _availability(plant: dict) -> list:
    """Where you can buy it, corrected for how native plants are actually sold.

    Reported first as *"where to buy is incorrectly generous of the big box
    store and greenhouse as they will likely have less natives. Any natives
    should also be listed in native nursery"*, then narrowed: *"the native
    nursery should have the 'common plants' of the big box store and greenhouse
    but not the plugs/seed only"*.

    ``availability_class`` records a single value naming the *easiest* place to
    find a species. That is a reasonable thing to record and the wrong thing to
    filter on directly: it says "Saskatoon berry is at the big-box store" and
    thereby says "Saskatoon berry is not at the native nursery", which is false.

    The first pass fixed that by adding ``native_specialist`` to every native,
    which is 437 of 437 rows — a filter that matches everything is not a filter.
    ``_ALSO_SOLD_BY`` replaces the blanket rule with the actual retail
    implication, and the 89 seed-only and rare species stay off the nursery
    shelf where they belong.
    """
    tier = (plant.get("availability_class") or "").strip()
    if not tier:
        return []
    out = [tier]
    out.extend(t for t in _ALSO_SOLD_BY.get(tier, ()) if t not in out)
    return out


def _single(column: str) -> Callable:
    def derive(plant: dict) -> list:
        value = (plant.get(column) or "").strip()
        return [value] if value else []
    return derive


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
