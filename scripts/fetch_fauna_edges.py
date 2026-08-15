#!/usr/bin/env python3
"""
scripts/fetch_fauna_edges.py — fetch real plant↔animal records (F125).

**Run this on a machine with internet.** The development container's egress
policy denies GBIF, iNaturalist and GloBI, so this is the half of F125 that has
to happen on your side; ingestion, validation and seeding happen back in the
repo from the file this writes.

    python3 scripts/fetch_fauna_edges.py --probe    # 4 requests, ~5 seconds
    python3 scripts/fetch_fauna_edges.py            # the real run

Run ``--probe`` first. It tries a handful of query forms against one plant and
reports which the API accepts and what columns come back, which takes seconds
and is the difference between a good run and 437 identical failures.

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

def _get(url: str, *, retries: int = _RETRIES) -> dict:
    """GET and parse, surfacing the server's own explanation on failure.

    The first version swallowed the response body, so a run that failed on every
    single plant reported only "HTTP Error 500" — which reads like an outage and
    was actually a malformed query. An HTTP error body from GloBI usually names
    the offending parameter, and that is the whole diagnosis. Never discard it.
    """
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")[:400].strip()
            except Exception:                              # noqa: BLE001
                pass
            last = f"HTTP {exc.code}" + (f" — {body}" if body else "")
            # A 4xx/5xx from a bad query will be identical every time; retrying
            # it just wastes the user's evening.
            if exc.code < 500:
                break
        except Exception as exc:                           # noqa: BLE001
            last = str(exc)
        if attempt < retries - 1:
            time.sleep(_PAUSE_S * (attempt + 2))
    raise RuntimeError(f"{last}")


#: Candidate query forms, richest first. The first version sent one hand-built
#: query and every request 500'd — a malformed request, not an outage, and the
#: user found that out 55 plants in. Two things almost certainly caused it: a
#: `fields=` parameter that `/interaction` does not accept, and pipe-joining
#: `interactionType` where GloBI wants the parameter repeated.
#:
#: Rather than guess again from a container that cannot reach the API, the
#: script now probes: it tries these in order against one plant, keeps the first
#: that answers, and says which. Richest first, because the extra parameters are
#: filtering we want — bbox especially, since GloBI is global.
_FORMS = (
    ("typed+bbox", lambda taxon: [
        ("sourceTaxon", taxon), ("type", "json"), ("limit", "500"),
        ("bbox", _BBOX),
    ] + [("interactionType", k) for k in _INTERACTIONS]),
    ("typed", lambda taxon: [
        ("sourceTaxon", taxon), ("type", "json"), ("limit", "500"),
    ] + [("interactionType", k) for k in _INTERACTIONS]),
    ("bbox only", lambda taxon: [
        ("sourceTaxon", taxon), ("type", "json"), ("limit", "500"),
        ("bbox", _BBOX),
    ]),
    ("minimal", lambda taxon: [
        ("sourceTaxon", taxon), ("type", "json"),
    ]),
)

#: Set by :func:`probe` once a working form is found.
_FORM = None


def _url(form_builder, taxon: str) -> str:
    return _API + "?" + urllib.parse.urlencode(form_builder(taxon))


def probe(sample: str = "Monarda fistulosa", *, verbose: bool = True) -> str:
    """Find a query form GloBI actually accepts. Returns its name.

    Also prints the **columns** that came back, because the mapping downstream
    depends on ``target_taxon_path`` being present — and if it is not, every
    record would be silently dropped for having no recognisable taxon, which
    would look exactly like "GloBI has no data for these plants".
    """
    global _FORM
    # Reachability first, so "the API rejected my query" and "this machine
    # cannot reach the host at all" are never confused — they need completely
    # different fixes, and the first run of this script conflated them.
    # NB: this deliberately does NOT json-parse. The first version called _get
    # here, which does, and GloBI's /ping answers in plain text — so a perfectly
    # reachable host reported "unreachable: Expecting value: line 1 column 1"
    # directly above a query form that had just succeeded. A diagnostic that
    # contradicts the result printed under it is worse than no diagnostic.
    try:
        req = urllib.request.Request(
            "https://api.globalbioticinteractions.org/ping",
            headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            ok = resp.status < 400
        if verbose:
            print(f"  reachable   {'✓' if ok else '✗'}  "
                  f"api.globalbioticinteractions.org answers")
    except Exception as exc:                               # noqa: BLE001
        if verbose:
            print(f"  reachable   ?  {exc}")
            print("               → could not confirm; the form probe below "
                  "is the real answer.")

    for name, builder in _FORMS:
        try:
            data = _get(_url(builder, sample), retries=1)
        except Exception as exc:                           # noqa: BLE001
            if verbose:
                print(f"  {name:12s} ✗  {exc}")
            continue
        cols = data.get("columns") or []
        n = len(data.get("data") or [])
        if verbose:
            print(f"  {name:12s} ✓  {n} records, {len(cols)} columns")
            print(f"               columns: {', '.join(cols) or '(none)'}")
            missing = [c for c in ("target_taxon_name", "interaction_type",
                                   "target_taxon_path") if c not in cols]
            if missing:
                print(f"               ⚠ missing what the mapping needs: "
                      f"{', '.join(missing)}")
        _FORM = (name, builder)
        return name
    raise RuntimeError(
        "No query form worked. Paste the errors above and the fetcher can be "
        "corrected — that output is the diagnosis.")


#: Records per request, and how many pages to walk before giving up on one
#: plant. The probe came back with *exactly* 500 rows for Monarda fistulosa —
#: which is the page size, i.e. the answer was truncated and there was more.
#: A well-studied plant silently losing records would look like a thin
#: catalogue, which is the very thing this whole exercise is meant to fix.
_PAGE = 500
_MAX_PAGES = 12


def fetch_for_plant(scientific_name: str) -> list:
    """Every GloBI row for one plant, following pagination to the end."""
    if _FORM is None:
        probe(verbose=False)
    _name, builder = _FORM
    out: list = []
    for page in range(_MAX_PAGES):
        params = builder(scientific_name)
        params = [(k, v) for k, v in params if k != "limit"]
        params += [("limit", str(_PAGE)), ("offset", str(page * _PAGE))]
        data = _get(_API + "?" + urllib.parse.urlencode(params))
        cols = data.get("columns") or []
        rows = data.get("data") or []
        out.extend(dict(zip(cols, r)) for r in rows)
        if len(rows) < _PAGE:
            break
        time.sleep(_PAUSE_S)       # another page is another request
    return out


# ── Turning a GloBI row into one of our edges ────────────────────────────────

def _taxon_for(path: str) -> str:
    """Our five-value taxon from GloBI's taxonomic path, or ``""`` to skip."""
    blob = path or ""
    for needle, taxon in _TAXA:
        if needle in blob:
            return taxon
    return ""


#: GloBI `target_specimen_life_stage` values that mean "not yet an adult".
#: Present in the response (confirmed by --probe), and decisive: a caterpillar
#: eating a leaf is a larval host record, an adult on a flower is nectar.
_IMMATURE = ("larva", "caterpillar", "nymph", "instar", "juvenile", "pupa")


def _relationship_for(interaction: str, taxon: str,
                      life_stage: str = "") -> str:
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
            # An ADULT lepidopteran "eating" a plant is nectaring, not
            # herbivory — adult butterflies and moths have no chewing
            # mouthparts. Recording that as a larval host would claim the plant
            # feeds caterpillars it may never host.
            stage = (life_stage or "").strip().lower()
            if stage and not any(w in stage for w in _IMMATURE):
                return "nectar"
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
            (row.get("interaction_type") or "").strip(), taxon,
            row.get("target_specimen_life_stage") or "")
        if not rel:
            continue
        key = (plant["common_name"].lower(), target.lower(), rel)
        if key in existing or key in seen:
            continue
        seen.add(key)
        # `study_title`, confirmed by --probe against the live API. The first
        # version read `study_citation`/`study_source_citation`, neither of
        # which `/interaction` returns — so every edge would have carried an
        # empty citation and been rejected wholesale by the ingester's
        # no-reporting-study gate. 500 records a plant, all silently binned,
        # looking exactly like "GloBI has nothing for these species".
        citation = (row.get("study_title") or "").strip()
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
    probe_only = "--probe" in sys.argv

    # Find a working query form before spending 437 requests on a broken one.
    print("probing the GloBI API for a query form it accepts…")
    try:
        form = probe()
    except Exception as exc:                               # noqa: BLE001
        print(f"\n{exc}")
        return 2
    print(f"using: {form}\n")
    if probe_only:
        print("(--probe: stopping here)")
        return 0

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
