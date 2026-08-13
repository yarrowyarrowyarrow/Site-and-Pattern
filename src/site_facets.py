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
    return _tokens(plant, "ecoregion")


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


def _availability(plant: dict) -> list:
    """Where you can buy it, corrected for how native plants are actually sold.

    Reported: *"where to buy is incorrectly generous of the big box store and
    greenhouse as they will likely have less natives. Any natives should also
    be listed in native nursery as even if they are sold at the bigger stores
    this does not mean the local nursery would not have it."*

    Both halves are right and they are one fix. ``availability_class`` is a
    single value naming the *easiest* place to find a species, which is a
    reasonable thing to record and the wrong thing to filter on: it says
    "Saskatoon berry is at the big-box store" and thereby says "Saskatoon berry
    is not at the native nursery", which is false. A specialist grower stocks
    the natives whether or not Canadian Tire does.

    So a native plant now carries ``native_specialist`` in addition to
    whatever tier it was assigned. The filter widens rather than moves: asking
    for big-box still returns the big-box list.
    """
    tier = (plant.get("availability_class") or "").strip()
    out = [tier] if tier else []
    native = (plant.get("native_to_alberta")
              or (plant.get("native_provinces") or "").strip())
    if native and "native_specialist" not in out:
        out.append("native_specialist")
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
    "ornamental": "Ornamental",
}

#: Use tags the desktop exposes and the **website does not** (P12). ``medicinal``
#: is a generic permaculture tag rather than sourced traditional knowledge, but a
#: public, indexed "medicinal native plants" landing page is the same act as
#: publishing the traditional-use notes, which V2.47 decided against. Filtered
#: out of the role vocabulary rather than silently absent: see the About page.
WITHHELD_ROLES = ("medicinal",)


def _ecoregion_options() -> tuple:
    from src.ecoregion import ecoregions                     # noqa: PLC0415
    return tuple((key, name) for key, name, _where in ecoregions())


FACETS: tuple = (
    # First, because it is the one filter used as a worklist rather than as a
    # plant character, and the author asked for it near the top.
    Facet("photo", "Photograph",
          (("photo", "Has a photograph"), ("no-photo", "No photograph yet")),
          _photo, group="Looks",
          note="323 of 434 species have an openly-licensed photograph we can "
               "credit. The rest are the gap."),
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
          note="Every plant here is a prairie native, so every one of them is "
               "listed under a native nursery: a specialist grower stocks it "
               "whether or not the big-box store does. The other tiers are "
               "the useful ones, and they say where else you might find it."),
    Facet("province", "Native to",
          (("AB", "Alberta"), ("SK", "Saskatchewan"), ("MB", "Manitoba")),
          lambda p: _tokens(p, "native_provinces"), group="Site"),
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
