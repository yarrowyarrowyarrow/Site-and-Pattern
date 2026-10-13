#!/usr/bin/env python3
"""A first-garden ranking for Edmonton's native list: IMPACT x FEASIBILITY.

Scratch prototype for the second-pass plan (not repository code). Run from the
repository root with HOME/XDG_DATA_HOME pointed at the sandbox DB:

    python3 <this> <outdir>

Writes ranking.csv, ranking.json and summary.txt to <outdir>.

IMPACT (0-11; 0-10 in variant A), what the plant does for local wildlife, documented edges only
(plant_fauna, not plant_fauna_derived), animals recorded in Alberta (ab_native):
  caterpillars  0-4  distinct Lepidoptera with a larval_host record:
                     0 ->0, 1-2 ->1, 3-5 ->2, 6-12 ->3, 13+ ->4.
                     A KEYSTONE_GENERA member gets at least 3 (genus claim,
                     Narango et al. 2020), because the species records are thin;
                     in variants B and C a WOODY keystone (oak, cherry, willow,
                     birch, poplar) gets 4, as in Tallamy & Shropshire 2009.
  specialist    0-1  a documented edge flagged specialist (nowhere else to go)
  birds         0-2  bird_food tag or 1+ documented bird edge ->1; 5+ birds ->2
  bees          0-3  distinct bees with a nectar/pollen record: 5+ ->1,
                     15+ ->2, 40+ ->3 (variant A: 0-2, 5+ ->1, 25+ ->2)
  shoulders     0-1  blooms in April-May or in September (the thin ends of an
                     Edmonton season)

FEASIBILITY (0-9; 0-8 in variant A), can a novice buy it, plant it and keep it in a city yard:
  buy           0-3  big_box/garden_centre 3, native_specialist 2,
                     seed_or_plug 1, rare 0, unrecorded 1
  dry ground    0-2  2 unless zoning.needs_standing_water
  fits          0-2  2 if not too big for a 100 m2 bed by the generator's own
                     rule (llm_design._too_big_for), 1 if it fits a 180 m2
                     back yard (400 m2 in variant A), else 0
  behaves      -2-0  spread_habit aggressive_rhizomatous -2, self_seeding -1,
                     branching suckering -1 (not cumulative beyond -2);
                     blank is "not assessed" and scores 0
  photo         0-1  has a photograph to recognise and buy it by
  perennial    -1-0  annual or biennial -1
  drought       0-1  copes with a dry spell (water_needs includes "low");
                     variants B and C only
  caps               too big for the back yard: at most 3; needs standing
                     water: at most 2 (variants B and C)

BANDS: Top pick (impact >= 6, feasibility >= 7), Good pick (impact >= 3,
feasibility >= 6), Easy to grow (impact <= 2, feasibility >= 6),
Needs the right spot (impact >= 3, feasibility < 6), For a pond or a
specialist (impact <= 2, feasibility < 6).
VARIANT env var: A = first draft (floor 3 for all keystones, fits vs 400 m2,
no caps, no drought term); B = data as shipped (default); C = B plus the
candidate spread review list SPREAD_REVIEW below.
ORDER: band, then LEAD = impact * feasibility, then impact, feasibility, name.
"""
from __future__ import annotations

import collections
import csv
import json
import os
import statistics
import sys

sys.path.insert(0, os.getcwd())

from src.data_quality import KEYSTONE_GENERA          # noqa: E402
from src.db.plants import get_all_plants, get_connection  # noqa: E402
from src.habitat_score import parse_month_range       # noqa: E402
from src.llm_design import _too_big_for               # noqa: E402
from src.native_here import around, native_around     # noqa: E402
from src.site_fit import locality                     # noqa: E402
from src.zoning import needs_standing_water           # noqa: E402

EDMONTON = (53.5461, -113.4938)
SMALL_BED_M2 = 100.0     # a front-yard bed
BIG_BED_M2 = 400.0 if os.environ.get("VARIANT") == "A" else 180.0  # a city back yard (15 m x 36 m lot)
WOODY_KEYSTONE = {"Quercus", "Prunus", "Salix", "Betula", "Populus"}
VARIANT = os.environ.get("VARIANT", "B")
#: Variant C: a CANDIDATE list of known spreaders for the owner's review (R11).
#: Horticultural judgment, not catalogue data. -2 runners/suckers that take
#: over a bed; -1 suckers or seeds about but is easily kept.
SPREAD_REVIEW = {
    "Populus tremuloides": -2, "Populus balsamifera": -2,
    "Prunus virginiana": -2, "Rubus idaeus": -2, "Symphoricarpos albus": -2,
    "Solidago gigantea": -2, "Solidago altissima": -2,
    "Euthamia graminifolia": -2, "Symphyotrichum lanceolatum": -2,
    "Helianthus nuttallii": -2, "Helianthus pauciflorus": -2,
    "Chamaenerion angustifolium": -2, "Anemonastrum canadense": -2,
    "Artemisia ludoviciana": -2, "Apocynum androsaemifolium": -2,
    "Thermopsis rhombifolia": -2, "Calamagrostis canadensis": -2,
    "Potentilla anserina": -2, "Typha latifolia": -2,
    "Pascopyrum smithii": -2, "Rosa acicularis": -1, "Prunus pensylvanica": -1,
    "Spiraea alba": -1, "Anaphalis margaritacea": -1,
    "Oenothera biennis": -1, "Agastache foeniculum": -1,
}


BAND_ORDER = ["Top pick", "Good pick", "Easy to grow",
              "Needs the right spot", "For a pond or a specialist"]


def cat_points(n: int) -> int:
    return 0 if n == 0 else 1 if n <= 2 else 2 if n <= 5 else 3 if n <= 12 else 4


def edges(plant_ids: set) -> dict:
    out = collections.defaultdict(lambda: {
        "lep": set(), "lep_regional": set(), "bees": set(), "birds": set(),
        "specialist": [], "animals": set()})
    conn = get_connection()
    try:
        for pid, rel, taxon, fid, spec, fname, src in conn.execute(
                "SELECT pf.plant_id, pf.relationship, f.taxon, f.id, "
                "pf.specificity, f.common_name, pf.source FROM plant_fauna pf "
                "JOIN fauna f ON f.id = pf.fauna_id WHERE f.ab_native = 1"):
            if pid not in plant_ids:
                continue
            e = out[pid]
            e["animals"].add(fid)
            if rel == "larval_host" and taxon == "lepidoptera":
                e["lep"].add(fid)
                if (src or "").startswith(("acorn_sheldon", "pohl_et_al")):
                    e["lep_regional"].add(fid)
            if rel in ("nectar", "pollen") and taxon == "bee":
                e["bees"].add(fid)
            if taxon == "bird":
                e["birds"].add(fid)
            if spec == "specialist":
                e["specialist"].append(f"{fname} ({rel.replace('_', ' ')})")
    finally:
        conn.close()
    return out


def score(p: dict, e: dict) -> dict:
    tags = {t.strip() for t in (p.get("permaculture_uses") or "").split(",")}
    genus = (p.get("scientific_name") or "").split()[0]
    keystone = genus in KEYSTONE_GENERA
    n_lep = len(e["lep"])
    floor = 0
    if keystone:
        floor = 3 if VARIANT == "A" else (4 if genus in WOODY_KEYSTONE else 3)
    cat = max(cat_points(n_lep), floor)
    special = 1 if e["specialist"] else 0
    n_birds = len(e["birds"])
    birds = 2 if n_birds >= 5 else 1 if (n_birds or "bird_food" in tags) else 0
    n_bees = len(e["bees"])
    if VARIANT == "A":
        bees = 2 if n_bees >= 25 else 1 if n_bees >= 5 else 0
    else:
        bees = 3 if n_bees >= 40 else 2 if n_bees >= 15 else 1 if n_bees >= 5 else 0
    months = set(parse_month_range(p.get("bloom_period") or ""))
    shoulders = 1 if (months & {4, 5} or 9 in months) else 0
    if VARIANT != "A" and p.get("plant_type") in ("grass", "sedge", "rush"):
        shoulders = 0       # wind-pollinated: its "bloom" feeds no bee
    impact = cat + special + birds + bees + shoulders

    avail = (p.get("availability_class") or "").strip()
    buy = {"big_box": 3, "garden_centre": 3, "native_specialist": 2,
           "seed_or_plug": 1, "rare": 0}.get(avail, 1)
    wet = needs_standing_water(p)
    dry = 0 if wet else 2
    fits = (2 if not _too_big_for(p, SMALL_BED_M2)
            else 1 if not _too_big_for(p, BIG_BED_M2) else 0)
    spread = (p.get("spread_habit") or "").strip()
    behave = {"aggressive_rhizomatous": -2, "self_seeding": -1}.get(spread, 0)
    if (p.get("branching") or "") == "suckering":
        behave = max(-2, behave - 1)
    if VARIANT == "C" and p["scientific_name"] in SPREAD_REVIEW:
        behave = min(behave, SPREAD_REVIEW[p["scientific_name"]])
        spread = spread or "review"
    photo = 1 if p.get("image_url") else 0
    life = (p.get("perennial_or_annual") or "").strip()
    perennial = -1 if life in ("annual", "biennial") else 0
    water = {t.strip() for t in (p.get("water_needs") or "").split(",")}
    drought = 1 if (VARIANT != "A" and "low" in water) else 0
    feas = max(0, buy + dry + fits + behave + photo + perennial + drought)
    # A plant too big for the yard, or one that needs a pond, can be at most
    # fair on feasibility however easy it is to buy (variants B and C).
    if VARIANT != "A":
        if fits == 0:
            feas = min(feas, 3)
        if wet:
            feas = min(feas, 2)

    reasons = []
    if n_lep:
        reasons.append(f"caterpillar host for {n_lep} moth or butterfly "
                       f"species on record")
    if keystone:
        reasons.append(f"a {genus} (one of the few plant groups that feed "
                       "most caterpillars)")
    if e["specialist"]:
        reasons.append("the only food or nest for " + ", ".join(
            sorted(set(e["specialist"]))[:2]))
    if birds:
        reasons.append(f"bird food ({n_birds} species on record)" if n_birds
                       else "bird food")
    if bees:
        reasons.append(f"{n_bees} native bee species on record")
    if shoulders:
        reasons.append("flowers at the thin end of the season")
    cautions = []
    if wet:
        cautions.append("needs standing water")
    elif "low" not in water and "high" in water:
        cautions.append("wants moist soil")
    if fits < 2:
        cautions.append(f"tall ({p.get('mature_height_meters')} m) for a small yard")
    if behave:
        cautions.append("spreads" if spread != "self_seeding" else "self-seeds")
    elif spread == "review":
        pass
    if avail == "rare":
        cautions.append("hard to buy")
    if avail == "seed_or_plug":
        cautions.append("sold as seed or plugs")
    if not photo:
        cautions.append("no photograph")
    if perennial:
        cautions.append(life)
    if not spread:
        cautions.append("spread not assessed")

    a = around(p)
    if impact >= 6 and feas >= 7:
        band = "Top pick"
    elif impact >= 3 and feas >= 6:
        band = "Good pick"
    elif impact >= 3:
        band = "Needs the right spot"
    elif feas >= 6:
        band = "Easy to grow"
    else:
        band = "For a pond or a specialist"
    return {
        "band": band,
        "id": p["id"], "common_name": p["common_name"],
        "scientific_name": p["scientific_name"], "type": p["plant_type"],
        "lead": impact * feas, "impact": impact, "feasibility": feas,
        "cat": cat, "n_lep": n_lep, "n_lep_regional": len(e["lep_regional"]),
        "keystone": keystone, "specialist": special, "birds": birds,
        "n_birds": n_birds, "bees": bees, "n_bees": n_bees,
        "shoulders": shoulders, "bloom": p.get("bloom_period") or "",
        "buy": buy, "availability": avail, "dry": dry, "fits": fits,
        "height_m": p.get("mature_height_meters"),
        "canopy_m": p.get("mature_canopy_m"), "behave": behave,
        "spread_habit": spread, "branching": p.get("branching") or "",
        "photo": photo, "perennial": perennial, "drought": drought,
        "water": p.get("water_needs") or "",
        "tox_pets": p.get("toxicity_pets") or "",
        "tox_humans": p.get("toxicity_humans") or "",
        "locality": locality(p["scientific_name"], *EDMONTON),
        "tier": a.get("tier", ""), "ruling": a.get("ruling", ""),
        "animals_documented": len(e["animals"]),
        "reasons": reasons, "cautions": cautions,
    }


def main(outdir: str) -> None:
    os.makedirs(outdir, exist_ok=True)
    plants = [p for p in get_all_plants() if native_around(p)]
    ids = {p["id"] for p in plants}
    ed = edges(ids)
    rows = [score(p, ed[p["id"]]) for p in plants]
    rows.sort(key=lambda r: (BAND_ORDER.index(r["band"]), -r["lead"],
                             -r["impact"], -r["feasibility"],
                             r["common_name"].lower()))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    with open(os.path.join(outdir, "ranking.json"), "w") as fh:
        json.dump(rows, fh, indent=1)
    cols = ["rank", "common_name", "scientific_name", "type", "lead",
            "impact", "feasibility", "cat", "n_lep", "n_lep_regional",
            "keystone", "specialist", "birds", "n_birds", "bees", "n_bees",
            "shoulders", "buy", "availability", "dry", "fits", "height_m",
            "behave", "spread_habit", "branching", "photo", "perennial",
            "tox_pets", "locality", "tier", "ruling", "animals_documented"]
    with open(os.path.join(outdir, "ranking.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    leads = [r["lead"] for r in rows]
    with open(os.path.join(outdir, "summary.txt"), "w") as fh:
        fh.write(f"n={len(rows)} lead median={statistics.median(leads)} "
                 f"mean={statistics.mean(leads):.1f} max={max(leads)}\n")
        fh.write("impact dist " + str(sorted(collections.Counter(
            r["impact"] for r in rows).items())) + "\n")
        fh.write("feas dist " + str(sorted(collections.Counter(
            r["feasibility"] for r in rows).items())) + "\n")
        fh.write("bands " + str(collections.Counter(r["band"] for r in rows).most_common()) + "\n")
        fh.write("lead dist (bands of 10) " + str(sorted(collections.Counter(
            r["lead"] // 10 * 10 for r in rows).items())) + "\n")
    print(open(os.path.join(outdir, "summary.txt")).read())


if __name__ == "__main__":
    main(sys.argv[1])
