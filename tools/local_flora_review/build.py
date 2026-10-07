"""
tools/local_flora_review/build.py -- the page the owner rules on (V3.12).

The Edmonton rule (``src/local_flora.py``) settles a species when herbaria hold
three collections of it within 50 km. 108 of the catalogue's species fall
short or deserve a second look, and settling those is a person's job. This
builds the page that person works on: one card per species with its evidence
(every collection's year and distance, observations, the nearest record, the
surrounding ecoregions' counts), a read from ``reads.py`` labelled as opinion,
and one question with a Yes and a No. The owner answers only where confident
and gives no reasons (their word, V3.12). The page keeps the answers in its own
database; ``scripts/derive_local_flora.py --merge`` brings them back.

    python -m tools.local_flora_review.build            # -> build/local_flora_review/edmonton.html
    python -m tools.local_flora_review.build --out PATH

Dev-time, no network. It is published as a claude.ai artifact (``README.md``
says where), which is why the page has no doctype or head of its own: the
artifact host supplies them.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from src.local_flora import PLACES, SPECIMEN, distance_km, inside  # noqa: E402
from tools.local_flora_review.reads import FLAGGED, READS  # noqa: E402

DEFAULT_OUT = ROOT / "build" / "local_flora_review" / "edmonton.html"
PLACE = "edmonton"

#: The ecoregions the 50 km circle overlaps (Aspen Parkland, with Boreal
#: Transition along its west and north edges).
ECO_NAMES = {"aspen_parkland": "Aspen Parkland",
             "boreal_transition": "Boreal Transition"}
#: Tier -> the page's group. "documented" appears only when flagged.
GROUP = {"thin": "thin", "observed": "observed", "no_data": "none"}
#: Names the cache still holds records under that belong to a catalogue row.
ALSO = {"Achillea borealis": "Achillea millefolium",
        "Solidago lepida": "Solidago canadensis",
        "Solidago glutinosa": "Solidago simplex"}
NO_READ = ("unsure", "No read written for this species yet.")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def doc_id(name: str) -> str:
    """The page's database id for a species: its name, in the characters a
    path segment allows."""
    return re.sub(r"[^A-Za-z0-9_.~:@+-]", "_", name.replace(" ", "_"))


def page_data(root: Path = ROOT) -> tuple[dict, list]:
    """``(data, species without a read)`` -- everything the page embeds."""
    place = PLACES[PLACE]
    shipped = _load(root / "data" / "local_flora.json")
    doc = shipped["places"][PLACE]
    entries = doc["species"]
    rows = {r["scientific_name"]: r
            for r in _load(root / "data" / "plants_master.json")}
    cache = _load(root / "data" / "fetched" / "plant_occurrences.json")
    eco = _load(root / "data" / "plant_ecoregions.json")["species"]
    basis = cache["basis"]

    def sheets(name):
        seen = {}
        for p in cache["species"].get(name) or ():
            if basis[p[4]] != SPECIMEN or not inside(p[0], p[1], p[2], place):
                continue
            key = (round(p[0], 2), round(p[1], 2), p[3])
            if key not in seen:
                seen[key] = [p[3], round(distance_km(place["centre"],
                                                     (p[0], p[1])))]
        return sorted(seen.values(), key=lambda s: (s[0] or 0, s[1]))

    species, unread = [], []
    for name, e in entries.items():
        if name in FLAGGED and e["tier"] == "documented":
            group = "flagged"
        elif e["tier"] in GROUP:
            group = GROUP[e["tier"]]
        else:
            continue
        if name not in READS:
            unread.append(name)
        read, why = READS.get(name, NO_READ)
        item = {
            "id": doc_id(name), "s": name, "c": rows[name]["common_name"],
            "t": rows[name]["plant_type"], "g": group,
            "n": e.get("collections", 0), "o": e.get("observations", 0),
            "k": e.get("nearest_km"), "sh": sheets(name),
            "eco": [[ECO_NAMES[x["ecoregion"]], x["occurrences"],
                     x["confidence"]]
                    for x in eco.get(name) or () if x["ecoregion"] in ECO_NAMES],
            "r": read, "w": why,
        }
        if name in ALSO:
            item["also"] = {"name": ALSO[name], "sh": sheets(ALSO[name])}
        species.append(item)

    unrecorded = sorted(
        ([rows[n]["common_name"], n, e.get("nearest_km")]
         for n, e in entries.items() if e["tier"] == "unrecorded"),
        key=lambda u: (u[2] if u[2] is not None else 9999, u[0]))
    outside = sorted([rows[n]["common_name"], n]
                     for n, e in entries.items()
                     if e["tier"] == "not_in_province")
    data = {
        "place": {"name": doc["name"], "short": doc["short"],
                  "centre": doc["centre"], "radius": doc["radius_km"],
                  "min": doc["min_collections"],
                  "generated": shipped["generated"],
                  "documented": sum(1 for e in entries.values()
                                    if e["tier"] == "documented")},
        "species": species, "unrecorded": unrecorded, "outside": outside,
    }
    return data, sorted(unread)


def render(data: dict) -> str:
    """The page: the template with ``data`` embedded where it says so."""
    template = (HERE / "template.html").read_text(encoding="utf-8")
    marker = "/*__DATA__*/null"
    if template.count(marker) != 1:
        raise ValueError("template.html must hold the data marker exactly once")
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return template.replace(marker, blob.replace("</", "<\\/"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args(argv)
    data, unread = page_data()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(data), encoding="utf-8")
    groups = {}
    for s in data["species"]:
        groups[s["g"]] = groups.get(s["g"], 0) + 1
    print(f"{len(data['species'])} species {groups} -> {args.out}")
    if unread:
        print(f"{len(unread)} with no read in reads.py: " + ", ".join(unread))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
