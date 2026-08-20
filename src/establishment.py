"""
establishment.py — "does this species actually grow here?", banded (F14).

Design principle P9 (uncertainty is a feature — ship ranges and confidence,
never false precision) — see docs/DESIGN_PHILOSOPHY.md.

The roadmap card proposed bucketing ``placement_score.score_cell_for_plant``
into three bands. **That would have been a false readout**, and the reason is
worth writing down because it applies to every scoring function in this
codebase: ``score_cell_for_plant`` degrades to a neutral 0.5 on missing input —
its own docstring says so, and ``build_cell_env_map`` fills every grid it
cannot read with ``shade=0.5, elev=0.5, slope=0``. That is correct for
*ranking* cells against each other and meaningless as a *statement*, because on
a site with no DEM fetched every plant scores the same 0.5 and a naive bucket
prints "medium confidence" about nothing at all. That is the exact trap the
V2.51 ecoregion maps fell into.

So this reads the strongest evidence the app actually holds about whether a
species grows in a place: the **georeferenced occurrence records** seeded into
``plant_ecoregions`` at schema v59/v60, which already carry a count, a
confidence band and a source per (species, ecoregion). Saskatoon Berry's aspen
parkland claim has 312 records behind it; the thresholds belong to
:mod:`src.ecoregion_ranges` and the words to :mod:`src.confidence`.

**What "unknown" means here, and why it is not "no".** The catalogue cannot
distinguish a species that is absent from your ecoregion from one nobody has
collected there. Below the three-record floor both look identical, so both get
``UNKNOWN`` and a sentence saying which question is open. Printing "unlikely to
establish" over an under-collected region would invent a fact and, worse, steer
a real planting away from a species that belongs in it.

Qt-free and injectable; the caller supplies the range lookup so a test never
needs a database.
"""

from __future__ import annotations

from typing import Callable, Optional

from src.confidence import UNKNOWN, Band, band, establishment_band


def _placed_species(placed_plants: list) -> dict[int, dict]:
    """``{plant_id: {name, n}}`` — one entry per species, however many copies."""
    out: dict[int, dict] = {}
    for p in placed_plants or []:
        pid = p.get("plant_id") or p.get("id")
        if not pid:
            continue
        entry = out.setdefault(int(pid), {
            "name": p.get("common_name") or p.get("scientific_name") or "",
            "n": 0})
        entry["n"] += 1
        if not entry["name"]:
            entry["name"] = p.get("common_name") or p.get("scientific_name") or ""
    return out


def establishment_for_design(placed_plants: list,
                             ecoregion: Optional[str], *,
                             ranges_for: Optional[Callable] = None) -> dict:
    """Band every placed species by its occurrence record in ``ecoregion``.

    Returns ``{ecoregion, known, species: [...], counts: {band_key: n},
    lines: [...]}`` where each species entry is
    ``{plant_id, name, n, occurrences, band, source}``, strongest first.

    With no ecoregion — the site has no pin, or the pin falls outside every
    drawn polygon — the whole readout is ``known=False``. There is no
    "somewhere" to be well recorded in.
    """
    species = _placed_species(placed_plants)
    if not species:
        return _empty(ecoregion, "Nothing is placed yet.")
    if not ecoregion:
        return _empty(ecoregion,
                      "No ecoregion for this site yet — drop a property pin on "
                      "the Site tab and this fills in.")

    if ranges_for is None:
        from src.db.plants import ecoregion_ranges_for_ids     # noqa: PLC0415
        ranges_for = ecoregion_ranges_for_ids

    try:
        rows = ranges_for(list(species)) or {}
    except Exception:                                # noqa: BLE001
        # A range lookup that fails is a missing answer, not a wrong one.
        return _empty(ecoregion, "The occurrence records could not be read.")

    out = []
    counts: dict[str, int] = {}
    for pid, meta in species.items():
        here = None
        for r in rows.get(pid) or []:
            if (r.get("ecoregion") or "") == ecoregion:
                here = r
                break
        occ = int((here or {}).get("occurrences") or 0) if here else None
        band = establishment_band(occ)
        counts[band.key] = counts.get(band.key, 0) + 1
        out.append({
            "plant_id": pid,
            "name": meta["name"],
            "n": meta["n"],
            "occurrences": occ,
            "band": band,
            "source": (here or {}).get("source") or "",
        })

    out.sort(key=lambda e: (-(e["occurrences"] or 0), e["name"]))
    return {
        "ecoregion": ecoregion,
        "known": True,
        "species": out,
        "counts": counts,
        "lines": _lines(out, counts),
    }


def _empty(ecoregion: Optional[str], why: str) -> dict:
    return {"ecoregion": ecoregion or "", "known": False, "species": [],
            "counts": {}, "lines": [why]}


def summary_band(result: dict) -> Band:
    """One band for the whole design — the *weakest* well-evidenced rung.

    Deliberately not an average. A design is as established as its shakiest
    species, and averaging lets forty well-recorded natives hide the one nobody
    has ever collected here. Species with no record at all are counted
    separately rather than dragging the band down, because "unrecorded" is not
    "unsuitable" and this module refuses to conflate them.
    """
    counts = (result or {}).get("counts") or {}
    if not result.get("known"):
        return UNKNOWN
    for key in ("low", "medium", "high"):
        if counts.get(key):
            # Ask for the band by KEY. A first cut fed `establishment_band` a
            # fabricated occurrence count (3 / 8 / 20) to get the rung back,
            # which quietly restated the thresholds `ecoregion_ranges` owns —
            # the second source of truth this whole module was written to avoid.
            return band("establishment", key)
    return UNKNOWN


def _lines(species: list, counts: dict) -> list[str]:
    """Plain sentences, including the one about what we could not answer."""
    out = []
    known = [e for e in species if e["band"].known]
    unknown = [e for e in species if not e["band"].known]
    if known:
        best = known[0]
        out.append(
            f"{len(known)} of {len(species)} placed species have "
            f"georeferenced records in this ecoregion — "
            f"{best['name']} has the most, with {best['occurrences']}.")
    if counts.get("low"):
        thin = [e["name"] for e in known if e["band"].key == "low"]
        out.append(
            f"Thinly recorded here ({', '.join(thin[:4])}"
            f"{'…' if len(thin) > 4 else ''}) — present, but on the edge of "
            f"what the occurrence data supports.")
    if unknown:
        names = [e["name"] for e in unknown]
        out.append(
            f"No occurrence record in this ecoregion for {len(unknown)} "
            f"species ({', '.join(names[:4])}{'…' if len(names) > 4 else ''}). "
            f"That is a gap in the record, not evidence they will not grow — "
            f"under-collected and absent look identical from here.")
    return out
