#!/usr/bin/env python3
"""
scripts/tag_prairie_provenance.py — stamp province-neutral provenance onto the
plant catalogue for the Saskatchewan expansion (V2.16). Re-runnable and
idempotent (recomputes from the ecoregion tags + native flag each run),
mirroring scripts/apply_sourcing_data.py.

WHAT IT DOES, per native record in data/plants_master.json:
  1. Adds the ``moist_mixedgrass`` ecoregion token (the SK Regina/Saskatoon
     belt) to any plant already documented from ``mixedgrass_prairie`` or
     ``aspen_parkland`` — the two ecoregions that flank the Moist Mixed
     Grassland and share its flora.
  2. Writes ``native_provinces`` (comma province codes, e.g. "AB,SK"), the
     province-neutral generalization of ``native_to_alberta`` (schema v42).

PROVENANCE HEURISTIC (honest by design — P9): Saskatchewan native status is
inferred from **ecoregion continuity**, not a per-species range map. The Aspen
Parkland, Mixed / Moist Mixed Grassland, Boreal Plain, riparian and wet-meadow
ecoregions run unbroken across the -110° AB/SK border, so a species documented
from any of them in Alberta is native to the same ecoregion in Saskatchewan.
Rocky-Mountain / foothills endemics (``fescue_foothills``, ``subalpine_montane``
only) do NOT extend into SK and stay Alberta-only. This is a coarse, transparent
inference; a future revision can replace it with curated per-species ranges.

Run from the project root:  python scripts/tag_prairie_provenance.py
"""

from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FILE = os.path.join(_ROOT, "data", "plants_master.json")

# Ecoregions that run continuously across the AB/SK border → shared SK flora.
_SK_SHARED = {
    "aspen_parkland", "mixedgrass_prairie", "moist_mixedgrass",
    "boreal_mixedwood", "riparian", "wet_meadow",
}
# The grassland/parkland pair that flanks the Moist Mixed Grassland belt.
_MOIST_TRIGGERS = {"mixedgrass_prairie", "aspen_parkland"}


def _is_native(record: dict) -> bool:
    return str(record.get("native_to_alberta", 0)).strip() in ("1", "1?")


def _ecoregion_tokens(record: dict) -> list[str]:
    raw = record.get("ecoregion") or record.get("ab_ecoregion") or ""
    if isinstance(raw, list):
        return [t.strip() for t in raw if t.strip()]
    return [t.strip() for t in raw.split(",") if t.strip()]


def _retag(record: dict) -> None:
    tokens = _ecoregion_tokens(record)
    token_set = set(tokens)

    # 1. Add the moist_mixedgrass belt token where the flanking ecoregions occur,
    #    preserving order and avoiding duplicates.
    if token_set & _MOIST_TRIGGERS and "moist_mixedgrass" not in token_set:
        tokens.append("moist_mixedgrass")
        token_set.add("moist_mixedgrass")
    # Write back into whichever ecoregion key the record already uses.
    eco_str = ",".join(tokens)
    if "ecoregion" in record:
        record["ecoregion"] = eco_str
    else:
        record["ab_ecoregion"] = eco_str

    # 2. Province provenance. AB and SK are recomputed authoritatively; any other
    #    curated codes already present (e.g. MB for a species native east of SK)
    #    are preserved so a re-run never drops hand-set provenance.
    existing = {c.strip().upper()
                for c in (record.get("native_provinces") or "").split(",")
                if c.strip()}
    inferred: set[str] = set()
    if _is_native(record):
        inferred.add("AB")
    # plants_master.json is the native catalogue, so an ecoregion tag implies the
    # plant is native to that ecoregion; if it reaches SK, so is the plant.
    if token_set & _SK_SHARED:
        inferred.add("SK")
    preserved = existing - {"AB", "SK"}
    order = ["AB", "SK", "MB", "BC", "ON", "QC", "NB", "NS", "PE", "NL",
             "YT", "NT", "NU"]
    codes = inferred | preserved
    record["native_provinces"] = ",".join(c for c in order if c in codes)


def main() -> int:
    with open(_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)

    sk = 0
    moist = 0
    for r in records:
        before_moist = "moist_mixedgrass" in ",".join(_ecoregion_tokens(r))
        _retag(r)
        if "SK" in r.get("native_provinces", ""):
            sk += 1
        if not before_moist and "moist_mixedgrass" in ",".join(_ecoregion_tokens(r)):
            moist += 1

    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"tag_prairie_provenance: {len(records)} records; "
          f"{sk} tagged native to SK; {moist} gained the moist_mixedgrass token.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
