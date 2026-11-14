#!/usr/bin/env python3
"""
model_references.py — reference photographs beside each plant's 3D model, for
the region's native plants (V3.47; docs/plans/V3.47-reference-photos-for-the-models.md).

Run in a session (the photographs are on iNaturalist's open-data store, which a
cloud session can reach; iNaturalist's API is not, so the candidate list comes
from the owner's PC):

    python scripts/model_references.py status
    python scripts/model_references.py fetch            # photographs, ~5 min
    python scripts/model_references.py render           # the models, ~10 min
    python scripts/model_references.py sheets           # one sheet a plant
    python scripts/model_references.py all --only "Monarda fistulosa"

``fetch`` reads ``data/fetched/photo_candidates.json`` (written on the owner's
PC by ``scripts/fetch_photo_candidates.py``, then committed) and downloads each
plant's candidates at 500 px: in flower, leaves and the whole plant, fruit,
winter, its iNaturalist page's own photos, and the one it has now. A plant the
candidates file does not hold falls back to the photographs the catalogue
ships (``data/plant_photos.json``, else ``image_url``), and says so.

``render`` draws each plant's model through the app's real viewer
(``html/yard_probe.html``'s shots mode, the scene from
``html/sprite_gallery_scenes.json``), from the side at eye level and from
above at 45 degrees, July, fully grown. Re-run it after changing the viewer;
re-run ``scripts/make_gallery_scene.py`` first after changing plant data.

``sheets`` puts the two renders and the photographs on one JPEG per plant,
each photograph labelled with what it shows, where it was taken and its
credit, and writes ``INDEX.md`` listing every plant by its model group.

Everything goes to ``data/fetched/model_refs/`` (ignored by git, never shipped).
The photographs are CC0, CC BY or CC BY-SA and keep their credits in
``manifest.json``; they are references for modelling, not app content.

The plants are the region pack's reviewed native list (``native_here``); pass
``--place`` for another pack, ``--only`` for named plants, ``--all-plants``
for the whole catalogue.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import native_here, photo_picks  # noqa: E402
from src.http_utils import user_agent  # noqa: E402

CANDIDATES = ROOT / "data" / "fetched" / "photo_candidates.json"
MASTER = ROOT / "data" / "plants_master.json"
SHIPPED_PHOTOS = ROOT / "data" / "plant_photos.json"
SCENES = ROOT / "html" / "sprite_gallery_scenes.json"
OUT = ROOT / "data" / "fetched" / "model_refs"

#: The order a sheet shows the kinds in, and what each is called on it.
GROUPS = ("flower", "plant", "fruit", "winter", "chosen", "now", "shipped")
WORDS = {"flower": "in flower", "plant": "leaves / whole plant",
         "fruit": "fruit", "winter": "winter", "chosen": "its iNaturalist page",
         "now": "the app's photo now", "shipped": "the app's photo"}
RENDER_PX = 640
BATCH = 24          # plants per headless browser run
DELAY = 0.25        # seconds between downloads


def slug(sci: str) -> str:
    """``Monarda fistulosa`` -> ``monarda_fistulosa``, the gallery's key."""
    return re.sub(r"[^a-z0-9]+", "_", sci.lower()).strip("_")


def _load(path: Path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


# ── which plants ────────────────────────────────────────────────────────────

def plants(args) -> list:
    """Catalogue rows for the plants asked for, in catalogue order."""
    rows = _load(MASTER, [])
    if args.only:
        want = {n.lower() for n in args.only}
        return [r for r in rows if r["scientific_name"].lower() in want
                or r["common_name"].lower() in want]
    if args.all_plants:
        return rows
    names = native_here.native_names(args.place) if args.place \
        else native_here.native_names()
    return [r for r in rows if r["scientific_name"] in names]


def photos_for(row: dict, candidates: dict, shipped: dict) -> tuple:
    """``(photos, source)`` for one plant: the candidates file's when it holds
    the plant, else what the catalogue ships."""
    sci = row["scientific_name"]
    entry = candidates.get(sci)
    out, seen = [], set()
    if entry and entry.get("groups"):
        for group in GROUPS:
            for c in entry["groups"].get(group, []):
                if c.get("url") and c["url"] not in seen:
                    seen.add(c["url"])
                    out.append({**c, "group": group})
        return out, "candidates"
    for p in shipped.get(sci, []):
        if p.get("url") and p["url"] not in seen:
            seen.add(p["url"])
            out.append({"url": p["url"], "group": "shipped",
                        "attribution": p.get("attribution", ""),
                        "license": p.get("license", ""), "place": "",
                        "taken_on": p.get("taken_on", "")})
    url = (row.get("image_url") or "").strip()
    if url and url not in seen:
        out.append({"url": url, "group": "shipped",
                    "attribution": row.get("image_attribution", ""),
                    "license": row.get("image_license", ""), "place": "",
                    "taken_on": ""})
    return out, "shipped"


def _shipped_index() -> dict:
    by = {}
    for p in _load(SHIPPED_PHOTOS, []):
        by.setdefault(p["scientific_name"], []).append(p)
    return by


# ── fetch ───────────────────────────────────────────────────────────────────

def fetch(rows: list) -> dict:
    candidates = _load(CANDIDATES, {})
    shipped = _shipped_index()
    manifest = _load(OUT / "manifest.json", {})
    got = failed = 0
    for n, row in enumerate(rows, 1):
        sci = row["scientific_name"]
        folder = OUT / "photos" / slug(sci)
        folder.mkdir(parents=True, exist_ok=True)
        photos, source = photos_for(row, candidates, shipped)
        kept = []
        for i, p in enumerate(photos):
            pid = photo_picks.photo_id(p["url"]) or i
            name = f"{GROUPS.index(p['group']):d}_{p['group']}_{pid}.jpg"
            path = folder / name
            if not path.exists():
                try:
                    req = urllib.request.Request(
                        p["url"], headers={"User-Agent": user_agent()})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        path.write_bytes(resp.read())
                    got += 1
                    time.sleep(DELAY)
                except Exception as exc:              # noqa: BLE001
                    failed += 1
                    print(f"    could not fetch {p['url']}: {exc}")
                    continue
            kept.append({"file": f"photos/{slug(sci)}/{name}",
                         "group": p["group"], "url": p["url"],
                         "attribution": p.get("attribution", ""),
                         "license": p.get("license", ""),
                         "place": p.get("place", ""),
                         "taken_on": p.get("taken_on", ""),
                         "observation": p.get("observation")})
        manifest[sci] = {"common_name": row["common_name"],
                         "plant_type": row.get("plant_type", ""),
                         "source": source, "photos": kept}
        print(f"  {n:3d}/{len(rows)} {row['common_name']}: {len(kept)} "
              f"photographs ({'candidates' if source == 'candidates' else 'catalogue only'})")
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"Downloaded {got}, failed {failed}. Manifest: {OUT / 'manifest.json'}")
    return manifest


# ── render ──────────────────────────────────────────────────────────────────

def views(plant: dict) -> dict:
    """The two cameras, in the viewer's axes (y up), framed on the plant."""
    h = max(float(plant.get("height_m") or 0.3), 0.3)
    r = max(float(plant.get("canopy_m") or 0.3), 0.3) / 2
    s = max(h, 2 * r)
    return {"side": {"at": [0, h * 0.5, s * 1.35], "looks_at": [0, h * 0.5, 0]},
            "high": {"at": [s * 0.9, h * 0.5 + s * 0.9, s * 0.9],
                     "looks_at": [0, h * 0.45, 0]}}


def render(rows: list) -> list:
    import render_yard as ry
    scenes = _load(SCENES, {})
    missing, todo = [], []
    for row in rows:
        key = f"species_{slug(row['scientific_name'])}"
        if key in scenes:
            todo.append((row, key, scenes[key]["scene"]))
        else:
            missing.append(row["scientific_name"])
    out = OUT / "model"
    out.mkdir(parents=True, exist_ok=True)
    for b in range(0, len(todo), BATCH):
        batch = todo[b:b + BATCH]
        routes, shots = {}, []
        for row, key, scene in batch:
            routes[f"/__yard/{key}.json"] = scene
            for name, view in views(scene["plants"][0]).items():
                shots.append({"name": f"{key}__{name}",
                              "scene": f"/__yard/{key}.json", "view": view})
        routes["/__yard/shots.json"] = {"width": RENDER_PX, "height": RENDER_PX,
                                        "shots": shots, "keep_shots": True}
        srv = ry.Server(routes)
        try:
            dom = ry.run_probe(srv.url("/yard_probe.html?shots=/__yard/shots.json"),
                               budget_ms=30000 + 4000 * len(shots))
        finally:
            srv.stop()
        pics = ry.images(dom, "shot")
        for name, data in pics.items():
            key, view = name.split("__")
            (out / f"{key[len('species_'):]}_{view}.jpg").write_bytes(data)
        print(f"  rendered {min(b + BATCH, len(todo))}/{len(todo)} plants "
              f"({len(pics)} of {len(shots)} pictures this batch)")
    if missing:
        print("No gallery scene (run scripts/make_gallery_scene.py): "
              + ", ".join(missing))
    return missing


# ── sheets ──────────────────────────────────────────────────────────────────

def _font(size: int):
    from PIL import ImageFont
    for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit(im, w, h):
    im = im.convert("RGB")
    im.thumbnail((w, h))
    return im


def _wrap(draw, text, font, width):
    lines, cur = [], ""
    for word in str(text).split():
        t = f"{cur} {word}".strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def facts(row: dict) -> str:
    bits = [row.get("plant_type", ""),
            f"{row['mature_height_m']} m tall" if row.get("mature_height_m") else "",
            f"blooms {row['bloom_period']}" if row.get("bloom_period") else "",
            f"flower {row['flower_color']}" if row.get("flower_color") else ""]
    return " · ".join(b for b in bits if b)


def sheet(row: dict, entry: dict) -> Path:
    from PIL import Image, ImageDraw
    sci = row["scientific_name"]
    s = slug(sci)
    tile, cols, pad, cap = 300, 5, 10, 58
    photos = entry.get("photos", []) if entry else []
    model = [OUT / "model" / f"{s}_{v}.jpg" for v in ("side", "high")]
    rows_n = 1 + (len(photos) + cols - 1) // cols
    width = pad + cols * (tile + pad)
    height = 90 + rows_n * (tile + cap + pad) + pad
    im = Image.new("RGB", (width, height), "#16201a")
    d = ImageDraw.Draw(im)
    d.text((pad, 10), f"{row['common_name']}  ({sci})", fill="#eaf1e6", font=_font(26))
    d.text((pad, 48), facts(row), fill="#9fb096", font=_font(16))
    small = _font(13)
    y = 90
    for i, path in enumerate(model):
        x = pad + i * (tile + pad)
        if path.exists():
            pic = _fit(Image.open(path), tile, tile)
            im.paste(pic, (x, y))
        else:
            d.rectangle([x, y, x + tile, y + tile], fill="#402020")
        d.text((x, y + tile + 4), ["MODEL: from the side", "MODEL: from above, 45°"][i],
               fill="#ffd27a", font=_font(15))
    d.text((pad + 2 * (tile + pad), y + 10),
           "Model: the app's viewer, July,\nfully grown, drawn in software.\n"
           "Photographs: iNaturalist,\nresearch grade, credits below\nand in manifest.json.",
           fill="#9fb096", font=_font(15))
    for i, p in enumerate(photos):
        x = pad + (i % cols) * (tile + pad)
        y = 90 + (1 + i // cols) * (tile + cap + pad)
        try:
            pic = _fit(Image.open(OUT / p["file"]), tile, tile)
            im.paste(pic, (x + (tile - pic.width) // 2, y + (tile - pic.height) // 2))
        except OSError:
            d.rectangle([x, y, x + tile, y + tile], fill="#402020")
        where = ", ".join(b for b in (p.get("place", "")[:40], p.get("taken_on", "")) if b)
        label = f"{i + 1}. {WORDS.get(p['group'], p['group'])}" + (f" · {where}" if where else "")
        lines = _wrap(d, label, small, tile)[:2] + _wrap(d, p.get("attribution", ""), small, tile)[:2]
        for k, line in enumerate(lines[:4]):
            d.text((x, y + tile + 2 + k * 14), line,
                   fill="#d6e8cd" if k < 2 else "#8a9a84", font=small)
    path = OUT / "sheets" / f"{s}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, quality=85)
    return path


def sheets(rows: list) -> None:
    manifest = _load(OUT / "manifest.json", {})
    scenes = _load(SCENES, {})
    by_group: dict = {}
    for row in rows:
        sheet(row, manifest.get(row["scientific_name"]))
        key = f"species_{slug(row['scientific_name'])}"
        group = (scenes.get(key) or {}).get("group", "No gallery scene")
        by_group.setdefault(group, []).append(row)
    lines = ["# Model reference sheets", "",
             "One sheet a plant: the 3D model (side, above) and its reference "
             "photographs. Written by `scripts/model_references.py`; not in git.",
             ""]
    for group in sorted(by_group):
        lines += [f"## {group}", "",
                  "| Plant | Scientific name | Photos | Source | Sheet |",
                  "|---|---|---|---|---|"]
        for row in by_group[group]:
            e = manifest.get(row["scientific_name"]) or {}
            lines.append(f"| {row['common_name']} | *{row['scientific_name']}* | "
                         f"{len(e.get('photos', []))} | {e.get('source', 'not fetched')} | "
                         f"`sheets/{slug(row['scientific_name'])}.jpg` |")
        lines.append("")
    (OUT / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(rows)} sheets and {OUT / 'INDEX.md'}")


# ── status ──────────────────────────────────────────────────────────────────

def status(rows: list) -> None:
    candidates = _load(CANDIDATES, {})
    scenes = _load(SCENES, {})
    held = [r for r in rows if (candidates.get(r["scientific_name"]) or {}).get("groups")]
    print(f"{len(rows)} plants asked for.")
    if not CANDIDATES.exists():
        print(f"No {CANDIDATES.relative_to(ROOT)}: commit it from the PC that ran "
              "scripts/fetch_photo_candidates.py. Until then only the catalogue's "
              "own photographs are used (usually one a plant).")
    else:
        print(f"Candidates file holds {len(held)} of them "
              f"({len(candidates)} plants in the file).")
        for r in rows:
            if r not in held:
                print(f"  not in the candidates file: {r['common_name']} ({r['scientific_name']})")
    no_scene = [r["scientific_name"] for r in rows
                if f"species_{slug(r['scientific_name'])}" not in scenes]
    if no_scene:
        print("No gallery scene: " + ", ".join(no_scene))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=("status", "fetch", "render", "sheets", "all"))
    ap.add_argument("--only", nargs="+", metavar="NAME",
                    help="scientific or common names")
    ap.add_argument("--place", help="a region pack's place (default: the default pack)")
    ap.add_argument("--all-plants", action="store_true",
                    help="the whole catalogue, not the native list")
    args = ap.parse_args(argv)
    rows = plants(args)
    if not rows:
        print("No plants matched.")
        return 1
    if args.step == "status":
        status(rows)
    if args.step in ("fetch", "all"):
        fetch(rows)
    if args.step in ("render", "all"):
        render(rows)
    if args.step in ("sheets", "all"):
        sheets(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
