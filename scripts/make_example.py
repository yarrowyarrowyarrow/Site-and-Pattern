#!/usr/bin/env python3
"""
scripts/make_example.py — a design becomes the worked example (F254, V3.38;
docs/plans/V3.38-the-learn-side-and-the-example.md).

The owner, testing V3.37: *"When I hit 'open an example yard' it opens to a
space on a street in downtown Edmonton where no design belongs. Either choose
a better location for this layout or let me make a design that will be the
example design."* No session can see map imagery, so the lot is the owner's
to choose. This turns the design they make into the pack's ``example``:

    python scripts/make_example.py "<design>.perma.geojson"           # report only
    python scripts/make_example.py "<design>.perma.geojson" --write   # write it

``--write`` replaces the ``example`` block of
``data/regions/<pack>/region.json`` (``--pack``, default the app's default
pack) and leaves the rest of the file as it was. Then run the tests
(``tests/test_region_packs.py`` and ``tests/test_onboarding.py`` check the
example) and commit the file. No schema bump: the pack is read from file.

**What it keeps**, as metres from the plot's south-west corner: the yard
outline, the beds, paths and other drawn shapes, buildings and trees,
structures, and every plant by its name (plant ids are not stable across a
reseed). The design's Site › Notes become the example's notes.

**What it refuses**: a design with no yard outline or no plants; a plant the
pack's reviewed list does not call native around the place, because the
example is the app's demonstration of planting native here; and notes using
words that would mean they carry plant-use knowledge (P12).

**What it never carries**: the address (the pin's label) or the design's own
name, which is often its address. ``--name`` names the example.

**The lot ships in every copy of the app**, and everyone who opens the
example sees it on satellite imagery. Use a lot you have the right to show:
your own if you are comfortable with that, a friend's with their permission,
or a public lawn. Not a stranger's house.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import region  # noqa: E402
from src.projection import metres_per_deg  # noqa: E402

CATALOGUE = PROJECT_ROOT / "data" / "plants_master.json"

#: The example's name unless ``--name`` says otherwise: never the design's.
DEFAULT_NAME = "Example — Front Yard Lawn Conversion"

#: Words that would mean the notes carry plant-use knowledge (P12), refused
#: as the plant directory's guard refuses them on screen.
P12_WORDS = ("indigenous", "traditional use", "ethnobotan", "first nations",
             "medicine wheel", "ceremonial", "medicinal", "remedy",
             "poultice", "tea from")

_KINDS = {**region.EXAMPLE_POLYGONS, **region.EXAMPLE_POINTS}

#: The report's words for each kind.
_WORDS = {"custom_shape": "drawn areas (beds, paths, lawn)",
          "canopy_footprint": "buildings or drawn canopies",
          "existing_tree": "existing trees",
          "existing_building": "existing buildings (as points)",
          "structure": "structures"}


class Refused(ValueError):
    """The design cannot become the example, and the message says why."""


def _catalogue() -> dict:
    with open(CATALOGUE, encoding="utf-8") as fh:
        return {r["common_name"]: r for r in json.load(fh)}


def _native(scientific_name: str, pack_key: str) -> bool:
    from src import native_here
    return native_here.native_around(scientific_name, pack_key)


def _kind(feature: dict) -> str:
    return (feature.get("properties") or {}).get("element_type") or ""


def _ring(feature: dict) -> list:
    """The polygon's corners as ``(lat, lng)``, without the closing repeat."""
    ring = ((feature.get("geometry") or {}).get("coordinates") or [[]])[0]
    pts = [(float(p[1]), float(p[0])) for p in ring]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def _point(feature: dict) -> tuple:
    c = (feature.get("geometry") or {}).get("coordinates") or []
    return (float(c[1]), float(c[0]))


def _struct_props(props: dict) -> dict:
    sd = props.get("struct_def") or {}
    out = {"struct_id": props.get("struct_id") or sd.get("id") or "",
           "name": props.get("name") or sd.get("name") or ""}
    size = props.get("size_m") or sd.get("size_m")
    if size:
        out["size_m"] = float(size)
    return out


def _notes(design: dict, plants: int, kinds: int, place: str) -> str:
    notes = str(((design.get("properties") or {}).get("notes")) or "").strip()
    low = notes.lower()
    used = [w for w in P12_WORDS if w in low]
    if used:
        raise Refused("the design's notes use " + ", ".join(repr(w) for w in used)
                      + ": the example does not carry plant-use knowledge "
                      "(P12). Rewrite Site › Notes and run this again.")
    if notes:
        return notes
    return ("This is a worked example, not a recommendation for your yard.\n\n"
            f"It holds {plants} plants of {kinds} kinds, every one native "
            f"around {place}. Design → Overview says what it feeds, when it "
            "flowers and how full it is.")


def example_from_design(design: dict, pack, *, name: str = DEFAULT_NAME,
                        own_place: bool = True,
                        catalogue: dict | None = None,
                        native=_native) -> dict:
    """The pack's ``example`` block made from ``design``. Raises
    :class:`Refused` with the reason when it cannot be."""
    feats = design.get("features") or []
    boundary = next((f for f in feats if _kind(f) == "property_boundary"
                     and (f.get("geometry") or {}).get("type") == "Polygon"),
                    None)
    if boundary is None:
        raise Refused("the design has no yard outline: draw it, then run "
                      "this again")
    plants = [f for f in feats if _kind(f) == "plant"]
    if not plants:
        raise Refused("the design has no plants")
    catalogue = _catalogue() if catalogue is None else catalogue

    names = [(f.get("properties") or {}).get("common_name") or ""
             for f in plants]
    unknown = sorted({n for n in names if n not in catalogue})
    if unknown:
        raise Refused("not in the catalogue by these names: "
                      + ", ".join(unknown))
    off_list = sorted({n for n in names
                       if not native(catalogue[n]["scientific_name"], pack.key)})
    if off_list:
        raise Refused(f"not on the {pack.short} native list: "
                      + ", ".join(off_list)
                      + ". The example shows planting native here; swap them")

    kept = [f for f in feats if _kind(f) in _KINDS]
    corners = _ring(boundary)
    for f in kept:
        if _kind(f) in region.EXAMPLE_POLYGONS:
            corners += _ring(f)
        else:
            corners.append(_point(f))
    corners += [_point(f) for f in plants]
    sw_lat = min(p[0] for p in corners)
    sw_lng = min(p[1] for p in corners)
    m_lat, m_lng = metres_per_deg(sw_lat)

    def off(lat, lng):
        return [round((lng - sw_lng) * m_lng, 2),
                round((lat - sw_lat) * m_lat, 2)]

    width = round(max(off(*p)[0] for p in corners), 2)
    depth = round(max(off(*p)[1] for p in corners), 2)
    centre = [round(sw_lat + depth / 2.0 / m_lat, 7),
              round(sw_lng + width / 2.0 / m_lng, 7)]

    features = []
    for f in kept:
        kind = _kind(f)
        props = f.get("properties") or {}
        if kind == "structure":
            keep = _struct_props(props)
        else:
            keep = {k: props[k] for k in _KINDS[kind] if k in props}
        item = {"kind": kind, "props": keep}
        if kind in region.EXAMPLE_POLYGONS:
            item["ring"] = [off(*p) for p in _ring(f)]
        else:
            item["at"] = off(*_point(f))
        features.append(item)

    example = {
        "centre": centre,
        "name": name,
        "width_m": width,
        "depth_m": depth,
        "planting": [[[n], off(*_point(f))] for n, f in zip(names, plants)],
        "own_place": bool(own_place),
        "outline": [off(*p) for p in _ring(boundary)],
        "features": features,
        "notes": _notes(design, len(plants), len(set(names)), pack.short),
    }
    errs = region.example_errors(example)
    if errs:
        raise Refused("; ".join(errs))
    return example


def report(example: dict, catalogue: dict | None = None) -> list[str]:
    """What the example holds, in lines: the numbers that said the old one
    was thin (19 plants covering 35% of its bed once grown)."""
    from collections import Counter
    from src import onboarding, yard_overview
    catalogue = _catalogue() if catalogue is None else catalogue
    ids = {name: i + 1 for i, name in enumerate(sorted(catalogue))}
    rows = {ids[n]: dict(catalogue[n], id=ids[n]) for n in ids}

    def lookup(name):
        return {"id": ids[name], "common_name": name} if name in ids else None

    project, missing = onboarding.build_example_project(
        lookup=lookup, example=example)
    planted = [candidates[0] for candidates, _ in example["planting"]]
    counts = Counter(planted)
    kinds = Counter(f["kind"] for f in example.get("features") or [])
    lines = [f"plot {example['width_m']:.1f} × {example['depth_m']:.1f} m, "
             f"centre {example['centre'][0]:.6f}, {example['centre'][1]:.6f}",
             f"{len(planted)} plants of {len(counts)} kinds; "
             f"{sum(1 for n in counts.values() if n == 1)} kinds are a "
             "single plant",
             "besides plants: " + (", ".join(
                 f"{n} {_WORDS.get(k, k)}" for k, n in sorted(kinds.items()))
                 or "nothing"),
             "opens " + ("on this lot, whatever the person's pin"
                         if example.get("own_place") else
                         "at the person's pin when it is in the pack")]
    cover = yard_overview.cover(project, get_plant=lambda pid: rows.get(pid))
    if cover:
        lines.append(f"planting area {cover['area_m2']:.0f} m², covered "
                     f"{100 * cover['share']:.0f}% once grown (Plan My Yard's "
                     "Fill it now aims at 70%)")
    if missing:
        lines.append("unresolved: " + ", ".join(missing))
    return lines


def write(example: dict, pack_key: str) -> Path:
    """Replace the pack's ``example`` and write region.json as it was
    formatted (two-space indent, UTF-8, a closing newline)."""
    path = PROJECT_ROOT / "data" / "regions" / pack_key / "region.json"
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    doc["example"] = example
    errs = region.validate(doc, pack_key)
    if errs:
        raise Refused("; ".join(errs))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("design", help="a saved design (.perma.geojson)")
    ap.add_argument("--pack", default="", help="region pack key (default: "
                    "the app's default pack)")
    ap.add_argument("--name", default=DEFAULT_NAME,
                    help="the example's name (never the design's)")
    ap.add_argument("--at-pin", action="store_true",
                    help="open at the person's pin, not on this lot")
    ap.add_argument("--write", action="store_true",
                    help="write it into the pack's region.json")
    args = ap.parse_args(argv)

    packs = region.regions()
    pack = packs.get(args.pack) if args.pack else region.default()
    if pack is None:
        print(f"no pack {args.pack!r}: one of {', '.join(sorted(packs))}")
        return 2
    with open(args.design, encoding="utf-8") as fh:
        design = json.load(fh)
    try:
        example = example_from_design(design, pack, name=args.name,
                                      own_place=not args.at_pin)
    except Refused as exc:
        print(f"Refused: {exc}")
        return 1
    for line in report(example):
        print(line)
    if not args.write:
        print("\nNothing written. Run again with --write to make this the "
              f"{pack.short} example.")
        return 0
    path = write(example, pack.key)
    print(f"\nWrote the example into {path.relative_to(PROJECT_ROOT)}.")
    print("It ships in every copy of the app and opens on this lot: check "
          "the lot is one you have the right to show.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
