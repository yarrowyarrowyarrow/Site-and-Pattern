"""Author the ``inflorescence_form`` field for every grass, sedge and rush in
data/plants_master.json (V2.33, schema v52). Idempotent — re-running rewrites
the same values, so this file is both the tool and the provenance record.

    python scripts/seed_inflorescence_morphology.py [--check]

WHY THIS FIELD EXISTS
All 79 graminoids in the catalogue carry ``flower_form: "plume"`` and drew the
same generic feathery spray. But **a grass is identified by its seed head**, not
by its leaves: every blade in the catalogue is recorded ``linear``, so with one
plume shared between them there is nothing on screen that tells a big bluestem
from a blue grama from a wire rush. The sprite audit put it plainly —

    "a big bluestem's turkey-foot inflorescence is most of how it is identified
     in the field, and there is no geometry for it at all."

Big bluestem is *named* for its turkey-foot; blue grama is recognised across a
field by its one-sided comb; needle-and-thread by 10 cm awns. These are the
strongest field marks the graminoids have and the app was drawing none of them
(P5: make the invisible visible; P9: no false precision, but no false SAMENESS).

WHY NOT JUST EXTEND ``flower_form``
Because ``flower_form`` feeds pollinator logic — ``bee_habitat.tongue_form_fit``
and ``forage_calendar`` read it to decide which bees can work a flower. Grasses
are wind-pollinated and offer nothing to a bee; ``plume`` is the correct answer
there and must stay. This is a separate, renderer-only column, exactly as
``fruit_form`` sits beside ``fruit_color``.

THE FORMS
  turkey_foot       Two to four stiff finger-like racemes splayed from one point
                    at the culm tip — the bluestems, and the field mark big
                    bluestem is named for.
  one_sided_raceme  Spikelets combed onto ONE side of the axis: blue grama's
                    eyebrow, side-oats grama's row of pendant oats, cord grass.
  open_panicle      A wide airy branching spray you can see through: switchgrass,
                    tufted hairgrass, ticklegrass, prairie dropseed, manna grass.
  contracted_spike  Narrow, dense, held tight to the axis: the wheatgrasses and
                    wild ryes, fescues, June grass, muhly, saltgrass.
  nodding_raceme    A loose spray whose branches DROOP: the bromes, drooping
                    wood-reed, purple oat grass.
  bristly           Dominated by long awns or bristles rather than by the
                    spikelets: needle-and-thread, porcupine grass, green
                    needlegrass, and cotton-grass's white bristle tuft.
  sedge_cluster     Stalkless clustered spikes on a triangular culm — the
                    Carex/Scirpus/Bolboschoenus signature.
  rush_umbel        A lateral cluster that appears to burst from the side of a
                    round culm below a pointed tip: Juncus.
  cattail_spike     The brown felt cylinder: Typha (already drawn from
                    flower_form, listed here for completeness).

SOURCING (P9)
Inflorescence type is a primary diagnostic character in every grass flora and is
about as uncontested as botanical description gets — it is what the keys key on.
Values are TYPICAL for the species and the reference frame is the general
graminoid literature for the prairie provinces and boreal Canada catalogued in
docs/REFERENCES.md. Assignment is by genus except where a genus genuinely splits
(Bouteloua's two species share a one-sided habit; Eriocoma's two do not), which
is recorded in SPECIES_OVERRIDE below.

Horsetails (Equisetum, filed as `rush` in the catalogue) are left EMPTY on
purpose: they are spore-bearing and have a strobilus, not an inflorescence.
Drawing them one would be inventing a structure the plant does not have.

This encodes no traditional, cultural or Indigenous knowledge of these plants —
only the botanical description of the seed head (P12).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MASTER = os.path.join(_ROOT, "data", "plants_master.json")

FIELD = "inflorescence_form"
FORMS = ("turkey_foot", "one_sided_raceme", "open_panicle", "contracted_spike",
         "nodding_raceme", "bristly", "sedge_cluster", "rush_umbel",
         "cattail_spike")

# genus -> inflorescence_form
GENUS_FORM = {
    # the bluestems
    "Andropogon": "turkey_foot",
    "Schizachyrium": "turkey_foot",      # a slenderer one-sided version of it
    # combed to one side
    "Bouteloua": "one_sided_raceme",
    "Spartina": "one_sided_raceme",
    # wide airy sprays
    "Agrostis": "open_panicle",
    "Deschampsia": "open_panicle",
    "Panicum": "open_panicle",
    "Sporobolus": "open_panicle",
    "Glyceria": "open_panicle",
    "Poa": "open_panicle",
    "Danthonia": "open_panicle",
    "Calamovilfa": "open_panicle",
    "Piptatherum": "open_panicle",
    "Oryzopsis": "open_panicle",
    # narrow and dense
    "Elymus": "contracted_spike",
    "Leymus": "contracted_spike",
    "Pascopyrum": "contracted_spike",
    "Festuca": "contracted_spike",
    "Koeleria": "contracted_spike",
    "Muhlenbergia": "contracted_spike",
    "Distichlis": "contracted_spike",
    "Beckmannia": "contracted_spike",
    "Anthoxanthum": "contracted_spike",
    "Sphenopholis": "contracted_spike",
    "Avenula": "contracted_spike",
    "Calamagrostis": "contracted_spike",
    "Eleocharis": "contracted_spike",     # one terminal spikelet on a bare culm
    # drooping
    "Bromus": "nodding_raceme",
    "Cinna": "nodding_raceme",
    "Schizachne": "nodding_raceme",
    # awns and bristles are the whole silhouette
    "Hesperostipa": "bristly",
    "Nassella": "bristly",
    "Eriophorum": "bristly",              # the white perianth-bristle tuft
    # clustered spikes on a triangular culm
    "Carex": "sedge_cluster",
    "Scirpus": "sedge_cluster",
    "Bolboschoenus": "sedge_cluster",
    "Schoenoplectus": "sedge_cluster",
    # the lateral burst below a pointed culm tip
    "Juncus": "rush_umbel",
    # not a grass at all, but it is the aquatic the viewer already spikes
    "Typha": "cattail_spike",
}

# Where one genus is not one seed head.
SPECIES_OVERRIDE = {
    # Indian ricegrass is the wide-open airy one; Richardson's needlegrass is
    # named for its awns and belongs with the other bristly stipoids.
    "Eriocoma hymenoides": "open_panicle",
    "Eriocoma richardsonii": "bristly",
    # Side-oats grama hangs its spikelets in a row down one side of a straight
    # axis; blue grama's are combed onto one side of a curved "eyebrow". Both
    # one-sided, which is the character the geometry draws.
    "Bouteloua curtipendula": "one_sided_raceme",
    "Bouteloua gracilis": "one_sided_raceme",
}

# Spore-bearing, so no inflorescence exists to draw (see the module docstring).
NO_INFLORESCENCE = {
    "Equisetum hyemale": "a spore strobilus, not an inflorescence",
    "Equisetum variegatum": "a spore strobilus, not an inflorescence",
    "Equisetum arvense": "a spore strobilus, not an inflorescence",
    "Equisetum fluviatile": "a spore strobilus, not an inflorescence",
}

_GRAMINOID = ("grass", "sedge", "rush")


def form_for(rec):
    """The recorded form for one catalogue record, or None."""
    sci = (rec.get("scientific_name") or "").strip()
    if sci in NO_INFLORESCENCE:
        return None
    if sci in SPECIES_OVERRIDE:
        return SPECIES_OVERRIDE[sci]
    return GENUS_FORM.get(sci.split(" ")[0])


def apply(records, check=False):
    applied, uncovered = 0, []
    for rec in records:
        if rec.get("plant_type") not in _GRAMINOID \
                and (rec.get("scientific_name") or "").split(" ")[0] != "Typha":
            continue
        form = form_for(rec)
        if form is None:
            if (rec.get("scientific_name") or "").strip() not in NO_INFLORESCENCE:
                uncovered.append(rec.get("common_name"))
            continue
        if not check:
            rec[FIELD] = form
        applied += 1
    return applied, uncovered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report coverage without writing")
    args = ap.parse_args()

    bad = [k for k, v in list(GENUS_FORM.items()) + list(SPECIES_OVERRIDE.items())
           if v not in FORMS]
    if bad:
        print("values outside the vocabulary:", bad)
        return 1

    with open(_MASTER, encoding="utf-8") as fh:
        records = json.load(fh)
    total = sum(1 for r in records if r.get("plant_type") in _GRAMINOID)
    applied, uncovered = apply(records, check=args.check)

    if uncovered:
        print(f"graminoids still without an inflorescence_form ({len(uncovered)}):")
        for name in uncovered:
            print("   ", name)

    if args.check:
        print(f"check: {applied} of {total} graminoids covered")
        return 1 if uncovered else 0

    with open(_MASTER, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {_MASTER}: {applied} of {total} graminoids have an "
          f"inflorescence form")
    return 0


if __name__ == "__main__":
    sys.exit(main())
