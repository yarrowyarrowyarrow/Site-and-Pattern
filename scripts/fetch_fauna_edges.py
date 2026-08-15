#!/usr/bin/env python3
"""
scripts/fetch_fauna_edges.py — fetch real plant↔animal records (F125).

**Run this on a machine with internet.** The development container's egress
policy denies GBIF, iNaturalist and GloBI, so this is the half of F125 that has
to happen on your side; ingestion, validation and seeding happen back in the
repo from the file this writes.

    python3 scripts/fetch_fauna_edges.py

Stdlib only — no pip install, no API key, no account. Python 3.8+.

WHY GloBI
---------
`Global Biotic Interactions <https://globalbioticinteractions.org>`_ is the
right source and GBIF is not. GBIF holds *occurrences* — "this species was seen
here" — which says nothing about who eats or pollinates whom. GloBI aggregates
**interaction** records from hundreds of published datasets, and critically for
this codebase, **every record carries the study that reported it**, so an edge
can arrive with a citation instead of an assertion. Data is CC0/CC-BY.

WHAT IT DOES
------------
For every plant in the shipped catalogue it asks GloBI "what interacts with
this?", keeps only the interaction types that map cleanly onto this app's seven
relationships, keeps only records from North America, and writes two files:

* ``data/fetched/fauna_edges_candidates.json`` — edges, each with its citation
* ``data/fetched/fauna_new_species.json``      — animals not yet in fauna_master

NOTHING IS MERGED AUTOMATICALLY. These are candidates for review. That is not
timidity: this catalogue's whole confidence discipline rests on documented edges
being genuinely documented, and an aggregator will happily return a greenhouse
observation from Belgium for a prairie shrub.

IT IS SAFE TO STOP AND RE-RUN
-----------------------------
Progress is checkpointed after every plant. Ctrl-C and run it again and it
resumes where it stopped. Expect roughly 437 requests at ~1/sec — about ten
minutes, most of it waiting politely.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA = os.path.join(_ROOT, "data")
_OUT_DIR = os.path.join(_DATA, "fetched")

_API = "https://api.globalbioticinteractions.org/interaction"
_UA = "Site-and-Pattern/2.59 (native plant habitat design; F125 data sourcing)"

#: Be a good citizen: GloBI is a free academic service.
_PAUSE_S = 1.0
_TIMEOUT_S = 45
_RETRIES = 3

#: North America, generously. GloBI is global and a bumblebee recorded visiting
#: Achillea in a New Zealand garden is not evidence about an Alberta yard.
_BBOX = "-170,25,-52,72"          # west,south,east,north

#: GloBI interaction types, asked from the PLANT's side, mapped onto this app's
#: `plant_fauna.relationship` vocabulary. Deliberately narrow: an interaction we
#: cannot map confidently is dropped rather than guessed into the nearest slot.
#: The raw GloBI verb travels through in `notes` so nothing is lost on review.
_INTERACTIONS = {
    "pollinatedBy":     "pollen",
    "flowersVisitedBy": "nectar",
    "eatenBy":          "",        # resolved by what part / who — see _relationship_for
    "hasHost":          "",        # plant hasHost animal is rare; skip unless clear
    "hostOf":           "larval_host",
}

#: GloBI taxon-path fragments → this app's five `fauna.taxon` values. First hit
#: wins, so order matters: Lepidoptera before the general Insecta catch-all.
_TAXA = (
    ("Lepidoptera", "lepidoptera"),
    ("Apoidea", "bee"),
    ("Anthophila", "bee"),
    ("Andrenidae", "bee"),
    ("Apidae", "bee"),
    ("Halictidae", "bee"),
    ("Megachilidae", "bee"),
    ("Colletidae", "bee"),
    ("Melittidae", "bee"),
    ("Aves", "bird"),
    ("Mammalia", "mammal"),
    ("Insecta", "other_insect"),
    ("Arachnida", "other_insect"),
)


# ── Reading what we already have ─────────────────────────────────────────────

def _rows(path: str) -> list:
    with open(path, "r", encoding="utf-8") as fh:
        blob = json.load(fh)
    if isinstance(blob, list):
        return blob
    return next(v for v in blob.values() if isinstance(v, list))


def load_catalogue() -> tuple:
    """``(plants, known_fauna, existing_edges)`` from the shipped seed files."""
    plants = []
    for name in ("plants_master.json", "garden_plants.json"):
        for r in _rows(os.path.join(_DATA, name)):
            sci = (r.get("scientific_name") or "").strip()
            com = (r.get("common_name") or "").strip()
            if sci and com:
                plants.append({"scientific_name": sci, "common_name": com})

    known = set()
    for r in _rows(os.path.join(_DATA, "fauna_master.json")):
        sci = (r.get("scientific_name") or "").strip()
        if sci:
            known.add(sci.lower())

    existing = set()
    for r in _rows(os.path.join(_DATA, "plant_fauna_master.json")):
        if r.get("plant") and r.get("fauna"):
            existing.add((r["plant"].strip().lower(),
                          r["fauna"].strip().lower(),
                          (r.get("relationship") or "").strip()))
    return plants, known, existing


# ── Talking to GloBI ─────────────────────────────────────────────────────────

def _get(url: str) -> dict:
    last = None
    for attempt in range(_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:                           # noqa: BLE001
            last = exc
            # Back off and try again: a free service under load is normal, and
            # a run that dies on the first hiccup wastes the whole session.
            time.sleep(_PAUSE_S * (attempt + 2))
    raise RuntimeError(f"GloBI request failed after {_RETRIES} tries: {last}")


def fetch_for_plant(scientific_name: str) -> list:
    """Raw GloBI rows for one plant, across every mapped interaction type."""
    params = {
        "sourceTaxon": scientific_name,
        "interactionType": "|".join(_INTERACTIONS),
        "bbox": _BBOX,
        "includeObservations": "true",
        "type": "json",
        "limit": "500",
        "fields": ("source_taxon_name,interaction_type,target_taxon_name,"
                   "target_taxon_path,study_citation,study_source_citation"),
    }
    data = _get(_API + "?" + urllib.parse.urlencode(params))
    cols = data.get("columns") or []
    return [dict(zip(cols, row)) for row in (data.get("data") or [])]


# ── Turning a GloBI row into one of our edges ────────────────────────────────

def _taxon_for(path: str) -> str:
    """Our five-value taxon from GloBI's taxonomic path, or ``""`` to skip."""
    blob = path or ""
    for needle, taxon in _TAXA:
        if needle in blob:
            return taxon
    return ""


def _relationship_for(interaction: str, taxon: str) -> str:
    """Our seven-value relationship, or ``""`` when it cannot be mapped.

    ``eatenBy`` is the ambiguous one, and it is resolved only where the eater
    settles it: a bird eating a plant is taken as fruit forage, a caterpillar
    eating one as a larval host.

    Everything else is dropped, including **mammals**. The seven relationships
    have no slot for browse — a deer stripping willow is neither `fruit_food`
    nor `cover`, and `cover` in particular means the plant *shelters* the
    animal, which is a different claim entirely. Other insects go the same way:
    "eats" covers leaf miners, gall wasps and sap suckers. Forcing any of these
    into the nearest available word would put a statement in front of the user
    that the record does not support, which is the whole failure V2.58 was
    spent undoing.
    """
    direct = _INTERACTIONS.get(interaction, "")
    if direct:
        return direct
    if interaction == "eatenBy":
        if taxon == "bird":
            return "fruit_food"
        if taxon == "lepidoptera":
            return "larval_host"
    return ""


def to_edges(plant: dict, rows: list, known_fauna: set,
             existing: set) -> tuple:
    """``(edges, new_species)`` for one plant, deduplicated."""
    edges, new_species, seen = [], [], set()
    for row in rows:
        target = (row.get("target_taxon_name") or "").strip()
        if not target or " " not in target:
            # Genus-only or higher: not a species, so not an edge we can key on.
            continue
        taxon = _taxon_for(row.get("target_taxon_path") or "")
        if not taxon:
            continue
        rel = _relationship_for(
            (row.get("interaction_type") or "").strip(), taxon)
        if not rel:
            continue
        key = (plant["common_name"].lower(), target.lower(), rel)
        if key in existing or key in seen:
            continue
        seen.add(key)
        citation = (row.get("study_citation")
                    or row.get("study_source_citation") or "").strip()
        edges.append({
            "plant": plant["common_name"],
            "plant_scientific": plant["scientific_name"],
            "fauna": target,
            "relationship": rel,
            "source": "globi",
            "notes": f"GloBI {row.get('interaction_type', '')}"
                     + (f" — {citation[:200]}" if citation else ""),
            "_citation": citation,
            "_taxon": taxon,
            "_known_fauna": target.lower() in known_fauna,
        })
        if target.lower() not in known_fauna:
            new_species.append({"scientific_name": target, "taxon": taxon,
                                "seen_with": plant["common_name"]})
    return edges, new_species


# ── The run ──────────────────────────────────────────────────────────────────

def _load_checkpoint(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:                                  # noqa: BLE001
            pass
    return {"done": [], "edges": [], "new_species": []}


def _save(path: str, blob) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(blob, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path)          # atomic: a Ctrl-C never leaves half a file


def main() -> int:
    plants, known_fauna, existing = load_catalogue()
    print(f"catalogue: {len(plants)} plants, {len(known_fauna)} known animals, "
          f"{len(existing)} edges already seeded")

    ckpt_path = os.path.join(_OUT_DIR, "_checkpoint.json")
    ckpt = _load_checkpoint(ckpt_path)
    done = set(ckpt["done"])
    if done:
        print(f"resuming — {len(done)} plants already fetched")

    todo = [p for p in plants if p["scientific_name"] not in done]
    for i, plant in enumerate(todo, 1):
        label = f"[{i}/{len(todo)}] {plant['common_name']}"
        try:
            rows = fetch_for_plant(plant["scientific_name"])
        except Exception as exc:                           # noqa: BLE001
            print(f"{label}: FAILED ({exc}) — will retry on the next run")
            continue
        edges, new_sp = to_edges(plant, rows, known_fauna, existing)
        ckpt["edges"].extend(edges)
        ckpt["new_species"].extend(new_sp)
        ckpt["done"].append(plant["scientific_name"])
        _save(ckpt_path, ckpt)
        flag = f"  +{len(edges)} edges" if edges else ""
        print(f"{label}: {len(rows)} records{flag}")
        time.sleep(_PAUSE_S)

    # Deduplicate the new-species list, keeping one row per animal.
    uniq: dict = {}
    for s in ckpt["new_species"]:
        uniq.setdefault(s["scientific_name"], s)

    _save(os.path.join(_OUT_DIR, "fauna_edges_candidates.json"), ckpt["edges"])
    _save(os.path.join(_OUT_DIR, "fauna_new_species.json"),
          sorted(uniq.values(), key=lambda s: s["scientific_name"]))

    known_edges = [e for e in ckpt["edges"] if e["_known_fauna"]]
    print("\n" + "=" * 62)
    print(f"  {len(ckpt['edges'])} candidate edges")
    print(f"    {len(known_edges)} use animals already in the catalogue")
    print(f"    {len(ckpt['edges']) - len(known_edges)} need a new fauna row")
    print(f"  {len(uniq)} distinct new animals")
    print(f"  plants covered: "
          f"{len({e['plant'] for e in ckpt['edges']})} of {len(plants)}")
    print("=" * 62)
    print(f"\nwritten to {_OUT_DIR}/")
    print("Commit those two files (or send them over) and the ingest side "
          "takes it from there.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
