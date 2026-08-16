#!/usr/bin/env python3
"""
scripts/ingest_fauna_edges.py — review and merge fetched edges (F125).

The other half of ``fetch_fauna_edges.py``. That one runs where there is
internet; this one runs in the repo, offline, over the file it produced.

    python3 scripts/ingest_fauna_edges.py            # report only, changes nothing
    python3 scripts/ingest_fauna_edges.py --apply    # write into the seed files

**Report first, apply second, and never the other way round.** An aggregator
returns what it has, not what is true here: a greenhouse observation from
Belgium, a species that does not occur in Alberta, a genus-level record dressed
as a species. Everything below is a gate, and the gates are the point — this
catalogue's confidence work only means anything if a `documented` edge is
genuinely documented.

Every gate reports a count, so a run tells you what was thrown away and why
rather than only what survived.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)          # so `src.` imports resolve when run as a script
_DATA = os.path.join(_ROOT, "data")
_FETCHED = os.path.join(_DATA, "fetched")

#: The schema's vocabularies. Restated here as a gate rather than imported, so
#: a candidate file that predates a schema change fails loudly instead of
#: writing a value the CHECK constraint will reject at seed time.
_RELATIONSHIPS = {"larval_host", "nectar", "pollen", "seed_food",
                  "fruit_food", "nesting", "cover"}
_TAXA = {"lepidoptera", "bird", "bee", "other_insect", "mammal"}

#: The citation key new edges are filed under. Registered in
#: data/sources_master.json by --apply if it is not already there.
_SOURCE_KEY = "globi"
#: The bibliography record, in the shape data/sources_master.json actually uses.
_SOURCE_RECORD = {
    "key": _SOURCE_KEY,
    "authors": "Poelen, J.H., Simons, J.D. and Miller, C.J.",
    "year": 2014,
    "title": ("Global Biotic Interactions: An open infrastructure to share and "
              "analyze species-interaction datasets"),
    "container": "Ecological Informatics",
    "publisher": "Elsevier",
    "kind": "database",
    "covers": "interactions",
    "record_confidence": "unverified",
    "record_note": (
        "An AGGREGATOR, not a primary work, and weaker evidence than a field "
        "guide. Each edge is checkable by querying GloBI for the same pair, "
        "which is why it counts as documented — but the specific paper behind "
        "it is not captured. Re-fetching with includeObservations=true would "
        "upgrade these in place."),
    "aliases": ["GloBI", "Global Biotic Interactions", "Poelen et al. 2014",
                "globalbioticinteractions.org"],
}


def _rows(path: str) -> list:
    with open(path, "r", encoding="utf-8") as fh:
        blob = json.load(fh)
    return blob if isinstance(blob, list) else next(
        v for v in blob.values() if isinstance(v, list))


def _load_seed() -> tuple:
    plants = {}
    plant_types = {}
    has_fruit = set()
    for name in ("plants_master.json", "garden_plants.json"):
        for r in _rows(os.path.join(_DATA, name)):
            if r.get("common_name"):
                key = r["common_name"].strip().lower()
                plants[key] = r["common_name"]
                plant_types[key] = (r.get("plant_type") or "").strip().lower()
                if (r.get("fruit_period") or "").strip() or \
                        (r.get("fruit_form") or "").strip():
                    has_fruit.add(key)
    fauna = {}
    for r in _rows(os.path.join(_DATA, "fauna_master.json")):
        if r.get("scientific_name"):
            fauna[r["scientific_name"].strip().lower()] = r
    edge_rows = _rows(os.path.join(_DATA, "plant_fauna_master.json"))
    existing = {(r["plant"].strip().lower(), r["fauna"].strip().lower(),
                 r.get("relationship", ""))
                for r in edge_rows if r.get("plant") and r.get("fauna")}
    return plants, fauna, edge_rows, existing, plant_types, has_fruit


def _bird_feeds() -> dict:
    """``scientific_name → set(feeds)`` from the curation table (F127a).

    Imported rather than restated so the nativity call and the feeding guild
    stay in one place. A bird that is not in the table has no entry, and
    ``_route_bird`` drops its edges — which is deliberate: an animal nobody has
    decided about must not arrive through a relationship record.
    """
    import importlib.util
    path = os.path.join(_ROOT, "scripts", "curate_birds.py")
    spec = importlib.util.spec_from_file_location("curate_birds", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    verdicts = {name: row[0] for name, row in mod.BIRDS.items()}
    return mod.feeds_map(), dict(mod.SYNONYMS), verdicts


def route_bird(rel: str, feeds: set, plant_has_fruit: bool) -> str:
    """The relationship a bird record actually supports, or ``""`` to drop it.

    **GloBI's ``eatenBy`` is not ``fruit_food``, and the fetcher assumed it
    was.** Of the 33 plants carrying a bird ``fruit_food`` edge, ten bear no
    fruit at all — Lodgepole Pine, White Spruce, Tamarack, Paper Birch,
    Trembling Aspen, Balsam Poplar, and four composites. A crossbill on a
    tamarack is eating seeds; a sapsucker on a birch is drinking sap, which the
    schema cannot express at all.

    And in the other direction, GloBI filed three ``flowersVisitedBy`` records
    for a White-crowned Sparrow. Sparrows do not nectar; the bird was at the
    flower gleaning insects.

    This is the Monarch bug again — an unspecific verb read as a specific
    claim — so it gets the same answer: refuse what the record cannot support
    rather than route it to the nearest available word.
    """
    if not feeds:
        return ""
    if rel in ("nectar", "pollen"):
        # Only a nectarivore nectars. Everything else at a flower is after
        # insects, and a visit is not a reward.
        return rel if "nectar" in feeds else ""
    if rel == "fruit_food":
        if "fruit" in feeds and plant_has_fruit:
            return "fruit_food"
        if "seeds" in feeds:
            return "seed_food"
        # Sap, buds and pure insectivory have no slot in the seven
        # relationships. Dropped rather than forced, exactly as mammal browse
        # was — and recoverable, since F128's observations re-fetch carries the
        # body part eaten.
        return ""
    return rel


def review(candidates: list) -> dict:
    """Run every gate. Returns counts plus the edges that survived."""
    plants, fauna, _edge_rows, existing, plant_types, has_fruit = _load_seed()
    from src.flower_colour import WIND_POLLINATED_TYPES
    bird_feeds, synonyms, bird_verdicts = _bird_feeds()
    kept, rejected = [], {}

    def drop(reason):
        rejected[reason] = rejected.get(reason, 0) + 1

    seen = set()
    for c in candidates:
        plant = (c.get("plant") or "").strip()
        animal = (c.get("fauna") or "").strip()
        rel = (c.get("relationship") or "").strip()
        # Resolve deprecated names onto the row the catalogue actually keys on
        # BEFORE anything else looks at the animal — otherwise `Picoides
        # pubescens` reads as a new species and gets written as a second Downy
        # Woodpecker beside `Dryobates pubescens`.
        animal = synonyms.get(animal, animal)

        if not plant or not animal or not rel:
            drop("incomplete record"); continue
        if rel not in _RELATIONSHIPS:
            drop(f"relationship not in the schema vocabulary ({rel})"); continue
        if (c.get("_taxon") or "") not in _TAXA:
            drop("taxon not in the schema vocabulary"); continue
        if plant.strip().lower() not in plants:
            drop("plant is not in this catalogue"); continue
        if " " not in animal:
            drop("animal is genus-level, not a species"); continue
        # Birds get re-read against what the species actually eats (F127a).
        # This runs BEFORE the key is built, because it can change the
        # relationship — a crossbill's `fruit_food` on a tamarack becomes
        # `seed_food`, and that is a different edge.
        if (c.get("_taxon") or "") == "bird":
            routed = route_bird(rel, bird_feeds.get(animal, set()),
                                plant.strip().lower() in has_fruit)
            if not routed:
                if animal in bird_feeds:
                    drop("bird record the species' diet does not support")
                elif animal in bird_verdicts:
                    drop(f"bird {bird_verdicts[animal]} by curation "
                         f"(not an Alberta/prairie species)")
                else:
                    drop("bird has not been assessed (F127a)")
                continue
            rel = routed
        key = (plant.lower(), animal.lower(), rel)
        if key in existing:
            drop("already seeded"); continue
        if key in seen:
            drop("duplicate within the candidate file"); continue
        # Provenance gate. Originally this demanded a named reporting study and
        # rejected all 14,111 candidates, because GloBI only fills `study_title`
        # when asked for observations rather than distinct interactions.
        #
        # The standard is now "a registered, checkable source", which GloBI is:
        # a peer-reviewed aggregator (Poelen, Simons & Miller 2014) where anyone
        # can look up this exact pair and see the underlying records. That is a
        # different and weaker claim than a named paper, and it is recorded as
        # such — the source key says `globi`, not a study. An edge with no
        # source at all is still refused; that would be an assertion.
        if not (c.get("source") or "").strip():
            drop("no source at all — cannot be filed as documented"); continue
        # A grass, sedge or rush has no nectar to offer. GloBI records a
        # hoverfly on a bulrush as `flowersVisitedBy`, which is a true
        # observation of a visit and a false statement about a reward — the
        # insect was after pollen or shelter. Reuses the app's own
        # wind-pollinated vocabulary so this and the flower-colour classifier
        # cannot disagree. `pollen` is deliberately NOT dropped: bees do
        # collect grass and sedge pollen.
        if (rel == "nectar"
                and plant_types.get(plant.strip().lower()) in WIND_POLLINATED_TYPES):
            drop("nectar claimed on a wind-pollinated plant"); continue
        # A larval host must come from GloBI's EXPLICIT `hostOf` verb.
        #
        # This gate exists because the first apply put 23 false Monarch host
        # edges into the seed — on goldenrod, aster, blazingstar, sunflower,
        # yarrow. Monarch caterpillars are obligate Asclepias specialists;
        # every one of those is an ADULT NECTARING record that GloBI files as
        # `eatenBy`, which the fetcher's "life stage unrecorded → larval_host"
        # default then promoted into a host claim. The repo's own
        # test_fauna.test_monarch_only_hosts_on_milkweed caught it.
        #
        # 107 of 120 candidate host edges come by that route, so this is a
        # heavy cut and it is the right one: telling somebody to plant
        # goldenrod to host monarch caterpillars is worse than telling them
        # nothing. A re-fetch with includeObservations=true carries the life
        # stage per record and would recover the real ones.
        if rel == "larval_host" and "hostOf" not in (c.get("notes") or ""):
            drop("larval_host not from GloBI's explicit hostOf verb"); continue
        seen.add(key)
        kept.append({
            "plant": plants[plant.strip().lower()],
            "fauna": animal,
            "relationship": rel,
            "source": _SOURCE_KEY,
            "notes": (c.get("notes") or "")[:300],
            # Kept when GloBI supplied one, so a later observations-mode run can
            # upgrade these in place rather than re-deriving them.
            **({"study": c["_citation"][:200]}
               if (c.get("_citation") or "").strip() else {}),
            "_new_fauna": animal.strip().lower() not in fauna,
            "_taxon": c.get("_taxon"),
        })
    return {"kept": kept, "rejected": rejected,
            "new_fauna": sorted({k["fauna"] for k in kept if k["_new_fauna"]})}


def _report(result: dict) -> None:
    kept = result["kept"]
    ready = [k for k in kept if not k["_new_fauna"]]
    print("=" * 64)
    print(f"  {len(kept)} edges survived every gate")
    print(f"    {len(ready)} ready now (animal already in fauna_master)")
    print(f"    {len(kept) - len(ready)} blocked on {len(result['new_fauna'])} "
          f"new animals")
    print(f"  {len({k['plant'] for k in ready})} plants would gain an edge")
    print("=" * 64)
    if result["rejected"]:
        print("\nrejected:")
        for reason, n in sorted(result["rejected"].items(),
                                key=lambda kv: -kv[1]):
            print(f"  {n:6d}  {reason}")
    by_rel: dict = {}
    for k in ready:
        by_rel[k["relationship"]] = by_rel.get(k["relationship"], 0) + 1
    if by_rel:
        print("\nready edges by relationship:")
        for rel, n in sorted(by_rel.items(), key=lambda kv: -kv[1]):
            print(f"  {n:6d}  {rel}")


def _apply(result: dict) -> None:
    """Write the ready edges into the seed file, and register the source.

    Only edges whose animal already exists are written. The rest wait for their
    fauna rows, which need a common name, a taxon and a nativity call — none of
    which an interaction record supplies, and all of which show up in the UI.
    """
    ready = [{k: v for k, v in e.items() if not k.startswith("_")}
             for e in result["kept"] if not e["_new_fauna"]]
    if not ready:
        print("nothing ready to write.")
        return

    path = os.path.join(_DATA, "plant_fauna_master.json")
    rows = _rows(path)
    rows.extend(ready)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1, ensure_ascii=False)
    print(f"wrote {len(ready)} edges into {os.path.relpath(path, _ROOT)}")

    # The bibliography is a structured record set, not a key→string map. The
    # first version appended {"key","citation"} — and worse, put it at the top
    # level rather than into the `sources` list — so data_quality rejected all
    # 2,546 edges for citing a work that was not in the bibliography. That guard
    # was right and is why this is caught here rather than by a user.
    src_path = os.path.join(_DATA, "sources_master.json")
    if os.path.exists(src_path):
        with open(src_path, "r", encoding="utf-8") as fh:
            blob = json.load(fh)
        rows = blob.get("sources") if isinstance(blob, dict) else None
        if rows is not None and not any(r.get("key") == _SOURCE_KEY
                                        for r in rows):
            rows.append(dict(_SOURCE_RECORD))
            with open(src_path, "w", encoding="utf-8") as fh:
                json.dump(blob, fh, indent=1, ensure_ascii=False)
            print(f"registered '{_SOURCE_KEY}' in sources_master.json")

    print("\nNEXT: bump _SCHEMA_VERSION in src/db/plants.py so existing "
          "installs reseed, then run the suite.")


def refit(write: bool = False) -> dict:
    """Re-run the current gates over edges a PREVIOUS run already wrote.

    A gate added after an ``--apply`` does not retroactively clean what that
    apply let through, and the bird routing was added exactly one increment
    late: V2.59 wrote 15 ``fruit_food`` edges on plants that bear no fruit —
    a goldfinch on Black-eyed Susan, a redpoll on Paper Birch, a chickadee on
    goldenrod. Every one is a seed record wearing the wrong word.

    So the applied data has to stay re-derivable. Only ``source == globi`` rows
    are touched; hand-authored edges are somebody's reading of a book and are
    not this script's to revise.
    """
    plants, fauna, edge_rows, _existing, plant_types, has_fruit = _load_seed()
    bird_feeds, synonyms, _verdicts = _bird_feeds()
    taxon_of = {k: (v.get("taxon") or "") for k, v in fauna.items()}

    changed, removed, kept = [], [], 0
    out, seen = [], set()
    for r in edge_rows:
        if not r.get("plant") or r.get("source") != _SOURCE_KEY:
            # Pass-through rows still claim their key. The first version only
            # tracked the rows it rewrote, and a re-route can land on top of a
            # HAND-AUTHORED edge: `Common Sunflower / Spinus tristis` was
            # already asserted with a Cornell citation, and the goldfinch's
            # GloBI `fruit_food` became a second `seed_food` beside it. Four
            # pairs like that survived. The better-cited row is the one to
            # keep, so claiming the key here also decides that correctly —
            # a `globi` duplicate of a real citation is pure noise.
            if r.get("plant") and r.get("fauna"):
                seen.add((r["plant"].strip().lower(),
                          r["fauna"].strip().lower(),
                          r.get("relationship", "")))
            out.append(r)
            continue
        animal = synonyms.get(r["fauna"].strip(), r["fauna"].strip())
        if taxon_of.get(animal.lower()) != "bird":
            out.append(r)
            continue
        routed = route_bird(r["relationship"],
                            bird_feeds.get(animal, set()),
                            r["plant"].strip().lower() in has_fruit)
        if not routed:
            removed.append((r["plant"], animal, r["relationship"]))
            continue
        key = (r["plant"].strip().lower(), animal.lower(), routed)
        if key in seen:
            removed.append((r["plant"], animal,
                            f"{r['relationship']}→{routed} (duplicate)"))
            continue
        seen.add(key)
        if routed != r["relationship"]:
            changed.append((r["plant"], animal, r["relationship"], routed))
            r = dict(r, relationship=routed, fauna=animal)
        else:
            kept += 1
        out.append(r)

    print(f"refit over {len(edge_rows)} rows: {kept} bird edges unchanged, "
          f"{len(changed)} re-routed, {len(removed)} removed")
    for p, a, old, new in changed:
        print(f"  {old:11s} → {new:11s}  {p} / {a}")
    for p, a, why in removed:
        print(f"  REMOVED ({why:22s})  {p} / {a}")
    if write and (changed or removed):
        path = os.path.join(_DATA, "plant_fauna_master.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, ensure_ascii=False)
        print(f"\nrewrote {os.path.relpath(path, _ROOT)}")
    elif not write:
        print("\n(report only — add --apply to write)")
    return {"changed": changed, "removed": removed, "kept": kept}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the ready edges into the seed files")
    ap.add_argument("--refit", action="store_true",
                    help="re-run the current gates over already-written edges")
    ap.add_argument("--file", default=os.path.join(
        _FETCHED, "fauna_edges_candidates.json"))
    args = ap.parse_args()

    if args.refit:
        refit(write=args.apply)
        return 0

    if not os.path.exists(args.file):
        print(f"no candidate file at {args.file}\n"
              f"Run scripts/fetch_fauna_edges.py on a machine with internet "
              f"first.")
        return 1
    with open(args.file, "r", encoding="utf-8") as fh:
        candidates = json.load(fh)
    print(f"reviewing {len(candidates)} candidates from "
          f"{os.path.relpath(args.file, _ROOT)}\n")

    result = review(candidates)
    _report(result)
    if args.apply:
        print()
        _apply(result)
    else:
        print("\n(report only — re-run with --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
