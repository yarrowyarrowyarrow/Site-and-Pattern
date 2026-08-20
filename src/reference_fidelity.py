"""
reference_fidelity.py — how close is this design to the natural community of
its place? (F13)

Design principle P2 (the best designs disappear into their context) and P6
(make ecological value legible) — see docs/DESIGN_PHILOSOPHY.md.

F50 shipped the reference community you can *walk*:
:func:`src.reference_ecosystem.resolve_reference_community` returns the
characteristic genera per structural layer for an ecoregion, resolved against
the live catalogue. This is the number that goes with it — "walk your design,
then walk the reference" gets a score, so the comparison is available without
launching a 3D window.

**Three decisions, each of which changes what the number means.**

*It scores STRUCTURE, not species.* Matching the reference species-for-species
is neither possible on a suburban lot nor desirable — the reference is a
hectare of parkland and the design is a front yard. What transfers is the
*shape*: is there a canopy, is there a shrub ring, is the ground a forb-grass
matrix rather than mulch. So the score is built from per-layer presence and
proportion, and sharing one of the reference's own species inside a layer is a
capped bonus rather than the basis — and a bonus is never allowed to lift a
design into a band whose wording its layer counts contradict.

*It is reported as a band, never a percentage.* The inputs are a hand-curated
community spec and a catalogue with known gaps; three significant figures over
that would be exactly the false precision P9 forbids. :mod:`src.confidence`
owns the bands so this one and the establishment band can be read against each
other.

*Low is not a failure.* A design can be deliberately unlike its reference — a
rain garden, a pollinator strip, a hedgerow — and the blurb says so. A score
that only ever scolds teaches nothing, and this app is not in the business of
telling somebody their yard is wrong.

Qt-free, injectable, and it never touches the DB directly: the caller passes
placed plants and the resolver, exactly like :mod:`src.reference_ecosystem`.
"""

from __future__ import annotations

from typing import Callable, Optional

from src.confidence import FIDELITY_HIGH, Band, fidelity_band

#: Which plant types stand in for each structural layer. Mirrors
#: ``reference_ecosystem._LAYER_TYPES`` — asserted equal by the tests, because
#: two layer maps that drift apart would make the fidelity score and the
#: walkable reference disagree about the same design.
LAYER_TYPES: dict[str, set] = {
    "canopy": {"tree"},
    "shrub": {"shrub"},
    "grass": {"grass", "graminoid", "sedge"},
    "forb": {"wildflower", "forb", "herb", "groundcover", "vine"},
}

#: A layer counts as *present* once it holds this share of the reference's own
#: count for that layer. Deliberately low: four aspens is a canopy on a suburban
#: lot even though the reference grove has forty, and the alternative is a score
#: that says "no canopy" about a yard with trees in it.
PRESENCE_FRACTION = 0.25


def _layer_of(plant: dict) -> str:
    """The structural layer a placed plant belongs to, or ``""``."""
    ptype = (plant.get("plant_type") or "").strip().lower()
    for layer, types in LAYER_TYPES.items():
        if ptype in types:
            return layer
    return ""


def _tokens(name: str) -> set:
    """Comparable forms of one plant name: the whole name and its first word.

    **This is not cosmetic.** ``resolve_reference_community`` returns whichever
    of common or scientific name a resolved row carries — in practice the
    *common* name ("Saskatoon Berry"), while a placed plant is matched on its
    scientific name ("Amelanchier alnifolia"). A first pass compared the first
    token of each and therefore matched nothing at all, on a design built
    entirely out of the reference community's own species. It passed its unit
    test because the test's fixture used scientific names on both sides, which
    is the failure mode a fixture that encodes the author's assumption always
    has. An end-to-end probe against the real seeded catalogue caught it.
    """
    n = (name or "").strip().lower()
    if not n:
        return set()
    return {n, n.split(" ")[0]}


def fidelity(placed_plants: list, ecoregion: Optional[str] = None, *,
             resolve: Optional[Callable] = None) -> dict:
    """Score a design against its ecoregion's reference community.

    Returns ``{band, score, known, reference, layers, matched_species,
    missing_layers, lines}`` where ``band`` is a :class:`~src.confidence.Band`
    and ``layers`` is per-layer ``{have, want, present}``.

    ``known`` is False — and the band is ``UNKNOWN`` — when there is nothing to
    compare: no plants placed, or a reference that resolved to nothing because
    the catalogue holds none of its genera. Scoring zero in that case would
    report a catalogue gap as a design failure.
    """
    if resolve is None:
        from src.reference_ecosystem import (                 # noqa: PLC0415
            resolve_reference_community)
        resolve = resolve_reference_community

    ref = resolve(ecoregion)
    ref_layers = (ref or {}).get("layers") or {}
    want = {layer: len(names) for layer, names in ref_layers.items()}
    # Both name forms on both sides — see `_tokens`.
    ref_tokens = {layer: set().union(*(_tokens(n) for n in names)) if names
                  else set()
                  for layer, names in ref_layers.items()}

    have: dict[str, int] = {layer: 0 for layer in LAYER_TYPES}
    matched: set = set()
    for p in placed_plants or []:
        layer = _layer_of(p)
        if not layer:
            continue
        have[layer] = have.get(layer, 0) + 1
        mine = _tokens(p.get("scientific_name") or "") | _tokens(
            p.get("common_name") or "")
        hit = mine & ref_tokens.get(layer, set())
        if hit:
            # Report the longest form we matched on, so the sentence reads
            # "Amelanchier" or "Saskatoon Berry" rather than "saskatoon".
            matched.add(max(hit, key=len))

    # Nothing to compare against — say so rather than scoring it (P9).
    scorable = {l: w for l, w in want.items() if w > 0}
    if not scorable or not any(have.values()):
        return {
            "band": fidelity_band(None, known=False),
            "score": None,
            "known": False,
            "reference": (ref or {}).get("name") or "",
            "layers": {}, "matched_species": [], "missing_layers": [],
            "lines": [_why_unknown(scorable, have)],
        }

    layers: dict[str, dict] = {}
    present_score = 0.0
    for layer, w in scorable.items():
        h = have.get(layer, 0)
        present = h >= max(1, round(w * PRESENCE_FRACTION))
        layers[layer] = {"have": h, "want": w, "present": present}
        if present:
            present_score += 1.0
        elif h:
            # Partial credit — a lone shrub is not a shrub ring, but it is not
            # a missing layer either, and rounding it to zero loses the
            # difference between "started" and "never considered".
            present_score += 0.5

    structure = present_score / len(scorable)
    # Species overlap is a bonus on top of structure, capped so a design cannot
    # score well on matching names while missing whole layers.
    species_bonus = min(0.15, 0.03 * len(matched))
    score = min(1.0, structure * 0.85 + species_bonus)

    missing = sorted(l for l, d in layers.items() if not d["present"])
    band = fidelity_band(score)
    # **The label has to be true to its own blurb.** "Close to the reference"
    # says *most of the layers are represented*, and the bonus alone could lift
    # a design over that threshold while three of its four layers were thin —
    # an end-to-end probe on a real six-plant parkland design did exactly that,
    # scoring 0.68 with only the canopy present. A band that contradicts the
    # sentence under it is worse than no band.
    if band.key == "high" and len(missing) > 1:
        score = min(score, FIDELITY_HIGH - 0.01)
        band = fidelity_band(score)
    # The clamp is applied to the reported score too, not just the band: a
    # caller reading `score: 0.68` beside `band: medium` would be reading a
    # contradiction, and the band is the answer this module stands behind.
    return {
        "band": band,
        "score": round(score, 2),
        "known": True,
        "reference": (ref or {}).get("name") or "",
        "layers": layers,
        "matched_species": sorted(matched),
        "missing_layers": missing,
        "lines": _lines(ref, layers, matched, missing),
    }


def _why_unknown(scorable: dict, have: dict) -> str:
    if not scorable:
        return ("No reference community resolved for this location, so there is "
                "nothing to compare against yet.")
    if not any(have.values()):
        return ("Nothing is placed yet — the comparison starts once the design "
                "has plants in it.")
    return "Not enough to compare."


_LAYER_WORD = {"canopy": "canopy trees", "shrub": "shrubs",
               "forb": "wildflowers", "grass": "grasses and sedges"}


def _lines(ref: dict, layers: dict, matched: set, missing: list) -> list[str]:
    """Plain sentences a panel can print without knowing the shape above."""
    name = (ref or {}).get("name") or "the reference community"
    out = [f"Compared with {name}."]
    if missing:
        words = ", ".join(_LAYER_WORD.get(l, l) for l in missing)
        out.append(f"Thin or absent here: {words}.")
    else:
        out.append("Every layer the reference community has is represented.")
    if matched:
        out.append(f"{len(matched)} of its characteristic species are in the "
                   f"design: {', '.join(sorted(matched)).title()}.")
    else:
        out.append("None of its characteristic species are in the design — the "
                   "structure can still match without them.")
    return out
