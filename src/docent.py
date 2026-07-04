"""
docent.py — the docent / presentation-mode script (F52).

Turns a finished design into a short **narrated tour** you can walk a neighbour,
an HOA board, or a class through. It scripts a sequence of *beats* — each a
camera + season/year state plus a narration line generated from the design's own
facts (habitat score, species supported, food-web status, keystone plants,
seasonal bloom, the chickadee-brood story) — so the tour is always true to the
project in front of you, never boilerplate.

The beats carry the camera/season state a 3D flyover could sync to; the shipped
UI walks them as an on-screen guided tour, and the same script can feed an
offscreen-capture booklet later.

Design principle P5 (perception is constructed — a narrated sequence teaches a
viewer to *see* the ecology) — see docs/DESIGN_PHILOSOPHY.md.

Qt-free and dependency-injectable: the presentation widget renders it, the
scripting layer and the tests share one definition.
"""

from __future__ import annotations

from typing import Callable, Optional

_MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def build_docent_script(placed_plants: Optional[list[dict]],
                        structures: Optional[list[dict]] = None, *,
                        name: Optional[str] = None,
                        score=None, chickadee: Optional[dict] = None,
                        forage: Optional[dict] = None,
                        get_plant: Optional[Callable] = None) -> dict:
    """Return the narrated docent script for a design.

    ``score`` / ``chickadee`` / ``forage`` are injectable (else computed from the
    live modules). See the module docstring for the result shape.
    """
    placed = placed_plants or []
    structures = structures or []
    label = name or "this design"

    if score is None:
        try:
            from src.habitat_score import compute_habitat_score
            score = compute_habitat_score(placed, structures)
        except Exception:      # noqa: BLE001
            score = None
    if chickadee is None:
        try:
            from src.chickadee_scenario import chickadee_provision
            chickadee = chickadee_provision(placed)
        except Exception:      # noqa: BLE001
            chickadee = None
    if forage is None:
        try:
            from src.forage_calendar import build_forage_calendar
            forage = build_forage_calendar(placed)
        except Exception:      # noqa: BLE001
            forage = None

    n_plants = _distinct_count(placed)
    beats: list[dict] = []
    beats.append(_beat_opening(label, score, n_plants))
    if n_plants:
        beats.append(_beat_score(score))
        beats.append(_beat_food_web(score))
        beats.append(_beat_species(score))
        sb = _beat_season(forage)
        if sb:
            beats.append(sb)
        cb = _beat_brood(chickadee)
        if cb:
            beats.append(cb)
    beats.append(_beat_close(label, n_plants))

    return {
        "title": f"A guided tour of {label}",
        "subtitle": _subtitle(score, n_plants),
        "beats": beats,
        "n_beats": len(beats),
    }


def _distinct_count(placed: list[dict]) -> int:
    return len({p.get("plant_id") for p in placed if p.get("plant_id") is not None})


def _total(score) -> int:
    return int(getattr(score, "total", 0) or 0) if score else 0


def _subtitle(score, n_plants: int) -> str:
    if not n_plants:
        return "An empty canvas — place some natives and the tour writes itself."
    return (f"{n_plants} native species · Habitat Value {_total(score)}/100 · "
            f"a lawn replaced by a living system.")


def _beat(bid: str, title: str, narration: str, *, year: int = 0,
          season_month: int = 6, camera: str = "overview") -> dict:
    return {"id": bid, "title": title, "narration": narration,
            "year": year, "season_month": season_month, "camera": camera}


def _beat_opening(label: str, score, n_plants: int) -> dict:
    if not n_plants:
        return _beat("opening", "Welcome",
                     f"{label.capitalize()} is still a blank slate. Place a few "
                     f"native plants and this tour will show what they build.",
                     camera="overview")
    native = getattr(score, "native_species", n_plants) if score else n_plants
    pct = int(round(100 * (getattr(score, "native_ratio", 1.0) or 1.0))) if score else 100
    return _beat(
        "opening", "Where a lawn used to be",
        f"Welcome. What you're looking at began as lawn — mowed, thirsty, and "
        f"nearly lifeless for wildlife. Today it's {n_plants} species, {pct}% of "
        f"them native to this place. Let me show you what that changes.",
        year=0, camera="overview")


def _beat_score(score) -> dict:
    total = _total(score)
    return _beat(
        "score", f"Habitat value: {total} out of 100",
        f"We can put a number on it. This design scores {total} out of 100 for "
        f"habitat value — where the lawn it replaced scored close to zero. That "
        f"gap is the wildlife this ground can now feed and shelter.",
        year=3, camera="orbit")


def _beat_food_web(score) -> dict:
    fw = (getattr(score, "food_web", {}) if score else {}) or {}
    status = fw.get("status", "empty")
    n_cat = fw.get("n_caterpillars", 0)
    n_bird = fw.get("n_birds", 0)
    if status == "complete":
        narration = (f"Here's the heart of it: a working food web. {n_cat} kinds "
                     f"of caterpillar grow on these plants, and {n_bird} kinds of "
                     f"bird can eat them. Host plants feeding the birds that feed "
                     f"on them — the whole chain, closed.")
    elif status == "no_birds":
        narration = (f"These plants already grow {n_cat} kinds of caterpillar — "
                     f"but we've room to grow. Add a berry or seed plant and the "
                     f"birds that eat them arrive, closing the chain.")
    elif status == "no_hosts":
        narration = ("Birds visit here, but the caterpillar host plants that feed "
                     "their nestlings aren't in yet — the next planting closes "
                     "that gap.")
    else:
        narration = ("The food web is just beginning. As host plants and berry "
                     "sources go in, you'll watch the chain assemble itself.")
    return _beat("food_web", "A food web, not a flowerbed", narration,
                 year=5, camera="walk")


def _beat_species(score) -> dict:
    by_taxon = (getattr(score, "fauna_by_taxon", {}) if score else {}) or {}
    labels = {"lepidoptera": "butterflies & moths", "bird": "birds", "bee": "bees",
              "other_insect": "other insects", "mammal": "mammals"}
    parts = [f"{n} {labels.get(t, t)}" for t, n in by_taxon.items() if n]
    total = sum(by_taxon.values())
    if parts:
        listing = ", ".join(parts)
        narration = (f"All told, this design supports {total} documented wildlife "
                     f"species — {listing}. Every one is a relationship the lawn "
                     f"couldn't offer.")
    else:
        narration = ("As the plantings mature, the wildlife they support will show "
                     "up in the numbers here — species by species.")
    return _beat("species", "Who lives here now", narration,
                 year=8, camera="orbit")


def _beat_season(forage: Optional[dict]) -> Optional[dict]:
    if not forage or not forage.get("flowering_plants"):
        return None
    peak = forage.get("peak_month", 0)
    peak_name = _MONTHS[peak] if 1 <= peak <= 12 else "midsummer"
    cov = forage.get("covered_growing", 0)
    total = forage.get("growing_total", 7)
    gaps = forage.get("gap_months", [])
    if not gaps:
        tail = ("and something is in bloom in every month of the growing season — "
                "a continuous relay of nectar and pollen.")
    else:
        tail = (f"with forage across {cov} of {total} growing-season months; the "
                f"gaps are where the next planting goes.")
    return _beat(
        "season", "Through the year",
        f"Watch it move through the seasons. Bloom peaks around {peak_name}, {tail}",
        year=8, season_month=(peak if 1 <= peak <= 12 else 7), camera="orbit")


def _beat_brood(chickadee: Optional[dict]) -> Optional[dict]:
    if not chickadee:
        return None
    status = chickadee.get("status")
    lo = chickadee.get("caterpillars_low", 0)
    hi = chickadee.get("caterpillars_high", 0)
    if status == "clears":
        narration = (f"Here's a number that lands: a single chickadee brood needs "
                     f"6,000 to 9,000 caterpillars to fledge. These plants could "
                     f"produce roughly {lo:,}–{hi:,} — enough to raise a family of "
                     f"birds. That's what a yard becomes when you plant for it.")
    elif status in ("partway", "short"):
        narration = (f"One more number: a chickadee brood needs 6,000–9,000 "
                     f"caterpillars to fledge. This design is on its way at about "
                     f"{lo:,}–{hi:,} — a few more keystone host plants and it "
                     f"feeds a whole brood.")
    else:
        return None
    return _beat("brood", "Enough to raise a bird", narration,
                 year=10, camera="walk")


def _beat_close(label: str, n_plants: int) -> dict:
    if not n_plants:
        narration = ("That's the promise: every native you place turns a patch of "
                     "lawn into habitat. Start with one keystone plant and watch "
                     "the tour fill in.")
    else:
        narration = ("This is what 'grown, not designed' looks like — a piece of "
                     "the wild built back on purpose. Thank you for walking it "
                     "with me. Now go stand in it, and see what the numbers can't.")
    return _beat("close", "Grown, not designed", narration,
                 year=12, camera="overview")
