"""
site_facet_values.py — what each of the website's facets reads off a plant.

Design principle P5 and P6 — see docs/DESIGN_PHILOSOPHY.md.

Split out of :mod:`src.site_facets` in V3.12, the extraction that module's
ceiling comment named: these are the pure ``plant dict -> list of values``
functions, and everything left there is the options and the table that pairs
each facet with its function. ``site_facets`` imports them back, so every name
it exported still resolves from it.

One stays behind on purpose: ``_uses`` reads ``site_facets.WITHHELD_ROLES`` at
call time, and the test of that mechanism patches the module it lives in.

V3.12 adds :func:`_around`, the first value that is not read off the row
itself: whether the species is native around Edmonton, from the one read side
the desktop uses (:mod:`src.native_here`), so the two cannot disagree.
"""

from __future__ import annotations

from typing import Callable

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


def _around(plant: dict) -> list:
    """``["edmonton"]`` when the species is native around Edmonton (F220,
    V3.12): native to Alberta by VASCAN and collected there at least three
    times, or confirmed on review. A species below that floor matches no value
    here, which is the facet module's rule for anything unrecorded, and is not
    a claim that it is foreign to Edmonton."""
    from src.native_here import EDMONTON, native_around      # noqa: PLC0415
    try:
        return [EDMONTON] if native_around(plant, EDMONTON) else []
    except ValueError:                  # no list shipped: say nothing
        return []
