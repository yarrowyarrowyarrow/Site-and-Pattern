"""
tools/stock_review/build.py -- the page the owner keeps the stock on (V3.25).

The availability levels (``src/local_stock.py``) come from what the region's
native-plant nurseries actually stock. This session could not reach a single
nursery's site, so the evidence comes from the owner: on this page they paste
a nursery's published list (its website, its availability PDF) and mark the
plants they know: Available, Seed only or Hard to find (V3.26). The page
previews each plant's level as the app will rank it, keeps everything in its
own database, and ``scripts/merge_stock.py --merge`` brings it back.

    python -m tools.stock_review.build          # -> build/stock_review/<region>.html
    python -m tools.stock_review.build --out PATH

Dev-time, no network. Published as a claude.ai artifact (``README.md`` says
where), so the page has no doctype or head of its own.
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

from src import local_stock, native_here, region, stock_lists  # noqa: E402


def _load(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def doc_id(text: str) -> str:
    """A database id: the text, in the characters a path segment allows."""
    return re.sub(r"[^A-Za-z0-9_.~:@+-]", "_", text.replace(" ", "_"))


def page_data(key: str = "") -> dict:
    """Everything the page embeds."""
    r = region.regions()[key] if key else region.default()
    rows = _load(ROOT / "data" / "plants_master.json")
    by_name = {p["scientific_name"]: p for p in rows}
    natives = native_here.native_names(r.key)
    stock = _load(local_stock.path(r.key))
    table = stock_lists.name_table(rows)
    species = []
    for name in sorted(natives, key=lambda n: by_name[n]["common_name"]):
        p = by_name[name]
        species.append({
            "id": doc_id(name), "s": name, "c": p["common_name"],
            "t": p["plant_type"],
            "r": local_stock.restoration_plant(p),
            "o": native_here.entry(name, r.key).get("observations", 0),
        })
    return {
        "region": {"key": r.key, "name": r.name, "short": r.short,
                   "nurseries": list(r.nurseries)},
        "labels": local_stock.LABELS, "tips": local_stock.TIPS,
        "species": species,
        "lists": stock.get("lists") or [],
        "rulings": stock.get("rulings") or {},
        "names": {k: v for k, v in table.items()
                  if k != stock_lists.BINOMIALS},
        "binomials": sorted(table[stock_lists.BINOMIALS]),
    }


def render(data: dict) -> str:
    template = (HERE / "template.html").read_text(encoding="utf-8")
    marker = "/*__DATA__*/null"
    if template.count(marker) != 1:
        raise ValueError("template.html must hold the data marker exactly once")
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return template.replace(marker, blob.replace("</", "<\\/"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--region", default="")
    p.add_argument("--out", type=Path)
    args = p.parse_args(argv)
    data = page_data(args.region)
    out = args.out or ROOT / "build" / "stock_review" / f"{data['region']['key']}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data), encoding="utf-8")
    print(f"{len(data['species'])} species, {len(data['lists'])} lists, "
          f"{len(data['rulings'])} answers -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
