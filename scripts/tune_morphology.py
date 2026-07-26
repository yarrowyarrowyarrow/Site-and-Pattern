#!/usr/bin/env python3
"""tune_morphology.py — tune a species' flower against a reference photo, live.

    python scripts/tune_morphology.py          # → http://127.0.0.1:8756

WHY THIS EXISTS
The 3D preview's remaining fidelity gap is not a code gap. It is roughly ten
characters × 434 species, and for most of them no single flora records all ten
in one place — flower diameter in cm, ray count, how far the bloom is held above
the foliage and how many flowering stems a mature plant carries are exactly the
numbers floras skip. The generator is only as good as those numbers.

So this is the authoring tool: the REAL viewer on the left rendering the species
as the app would draw it, the species' reference photograph on the right, eight
sliders between them, and `←` / `→` to page through the catalogue. Someone who
knows these plants can fix a wrong value in less time than it takes to look one
up — call it five minutes a species, an evening for twenty.

It follows the repo's own authoring-tool pattern (`make_gallery_scene.py` →
`sprite_gallery.html`): a small local server, no app dependency, writing
straight to `data/plants_master.json`. It is a DEV tool and not an app panel —
the seed catalogue is the project's, not the end user's.

WHAT IT WRITES
Only the schema-v53 flower columns, only for the species you touch, and it
rewrites `data/plants_master.json` in the same shape
`scripts/seed_flower_morphology.py` writes it (indent=2, ensure_ascii=False),
so the two are interchangeable and a tuned value survives a re-run of the
seeder only if you also record it there. **Values you tune here are yours, not
the seeder's** — see `--report`, which prints the diff so it can be folded back
into SPECIES_OVERRIDE.

THE FOUR NUMBERS WORTH GOING OUTSIDE FOR
Floras give ranges for height and skip these entirely, and they are the four the
generator most needs: **flower diameter in cm**, **petals or rays on one
floret**, **flowering stems on a mature plant**, and **how far the flowers sit
above the leaves**. A tape measure and a plant in bloom beat any amount of
reading.

P12: nothing here asks for or stores traditional, cultural or Indigenous
knowledge of a plant. It records the botanical description of a flower.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_MASTER = os.path.join(_ROOT, "data", "plants_master.json")
_HTML = os.path.join(_ROOT, "html")

# The columns this tool edits. Everything else in the record is left alone.
FIELDS = ("flower_arch", "flower_symmetry", "petal_shape", "petal_count",
          "florets_per_head", "flower_diameter_cm", "flower_center_color",
          "flower_height_frac", "stem_branching", "basal_rosette",
          "flowering_stems")


def _load():
    with open(_MASTER, encoding="utf-8") as fh:
        return json.load(fh)


def _save(records):
    with open(_MASTER, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _tunable(rec):
    """Species this tool can show: something that flowers and is not a grass
    (a graminoid's seed head is `inflorescence_form`, a different tool's job)."""
    if rec.get("plant_type") in ("grass", "sedge", "rush"):
        return False
    if rec.get("inflorescence_form"):
        return False
    return (rec.get("flower_form") or "none") != "none"


def _species_list(records):
    out = []
    for rec in records:
        if not _tunable(rec):
            continue
        row = {"scientific_name": rec.get("scientific_name") or "",
               "common_name": rec.get("common_name") or "",
               "plant_type": rec.get("plant_type") or "",
               "flower_color": rec.get("flower_color") or "",
               "flower_form": rec.get("flower_form") or "",
               "image_url": rec.get("image_url") or "",
               "image_attribution": rec.get("image_attribution") or "",
               "height_m": rec.get("mature_height_m"),
               "notes": (rec.get("notes") or "")[:400]}
        for f in FIELDS:
            row[f] = rec.get(f)
        out.append(row)
    out.sort(key=lambda r: r["common_name"].lower())
    return out


def _scene_for(sci, records):
    """The real Scene JSON for one species, built through the real build_scene —
    so the render on the left is exactly what the app draws, never a preview of
    a preview."""
    from src.scene_contract import build_scene              # noqa: PLC0415
    from src.sprite_gallery import _boundary, _fc, LAT0, LNG0, WHEN  # noqa: PLC0415
    from src.project_store import plant_feature             # noqa: PLC0415

    rec = next((r for r in records
                if (r.get("scientific_name") or "") == sci), None)
    if rec is None:
        return None
    row = dict(rec)
    row.setdefault("mature_height_meters", rec.get("mature_height_m"))
    if not row.get("mature_canopy_m") and rec.get("spacing_m"):
        row["mature_canopy_m"] = float(rec["spacing_m"]) * 1.5
    row.setdefault("years_to_maturity", 3)
    feats = [_boundary(LAT0, LNG0, 1.6),
             plant_feature({"plant_id": 1, "lat": LAT0, "lng": LNG0,
                            "common_name": rec.get("common_name") or ""})]
    # Year 6 and July: a tuned flower has to be judged on a grown plant in
    # bloom, which is also the only year anyone is designing FOR (P4).
    sc = build_scene(_fc(feats), year=6, when=WHEN,
                     get_plant=lambda _pid: row)
    xs = [p["x"] for p in sc["plants"]] or [0]
    ys = [p["y"] for p in sc["plants"]] or [0]
    pad = max(0.8, float(row.get("mature_height_meters") or 1) * 0.8)
    sc["bounds"] = {"min_x": min(xs) - pad, "max_x": max(xs) + pad,
                    "min_y": min(ys) - pad, "max_y": max(ys) + pad}
    return sc


class _Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):                                       # noqa: N802
        if self.path == "/api/species":
            return self._json(_species_list(_load()))
        if self.path.startswith("/api/scene/"):
            from urllib.parse import unquote                # noqa: PLC0415
            sci = unquote(self.path[len("/api/scene/"):])
            sc = _scene_for(sci, _load())
            return self._json(sc if sc else {}, 200 if sc else 404)
        if self.path in ("/", "/index.html"):
            self.path = "/tune_morphology.html"
        return super().do_GET()

    def do_POST(self):                                      # noqa: N802
        if not self.path.startswith("/api/species/"):
            return self._json({"error": "not found"}, 404)
        from urllib.parse import unquote                    # noqa: PLC0415
        sci = unquote(self.path[len("/api/species/"):])
        n = int(self.headers.get("Content-Length") or 0)
        try:
            patch = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._json({"error": "bad json"}, 400)
        records = _load()
        rec = next((r for r in records
                    if (r.get("scientific_name") or "") == sci), None)
        if rec is None:
            return self._json({"error": "unknown species"}, 404)
        changed = {}
        for f in FIELDS:
            if f not in patch:
                continue
            v = patch[f]
            if f in ("petal_count", "florets_per_head", "basal_rosette",
                     "flowering_stems"):
                v = None if v in ("", None) else int(v)
            elif f in ("flower_diameter_cm", "flower_height_frac"):
                v = None if v in ("", None) else round(float(v), 3)
            if rec.get(f) != v:
                changed[f] = v
                rec[f] = v
        if changed:
            _save(records)
        return self._json({"saved": bool(changed), "changed": changed})


def _report():
    """Which shipped values differ from what the family-first seeder would
    produce — i.e. everything a human has tuned by hand, ready to be folded back
    into SPECIES_OVERRIDE so it survives the next re-seed."""
    sys.path.insert(0, os.path.join(_ROOT, "scripts"))
    import seed_flower_morphology as seeder                 # noqa: PLC0415
    shipped = _load()
    fresh = json.loads(json.dumps(shipped))
    for r in fresh:
        for f in FIELDS:
            r.pop(f, None)
    seeder.apply(fresh)
    by_sci = {r.get("scientific_name"): r for r in fresh}
    n = 0
    for r in shipped:
        if not r.get("flower_arch"):
            continue
        want = by_sci.get(r.get("scientific_name")) or {}
        diff = {f: (want.get(f), r.get(f)) for f in FIELDS
                if want.get(f) != r.get(f)}
        if diff:
            n += 1
            print(f"{r.get('scientific_name')}:")
            for f, (a, b) in diff.items():
                print(f"    {f}: seeder {a!r} -> shipped {b!r}")
    print(f"\n{n} species differ from the family-first seeder. Fold them into "
          f"SPECIES_OVERRIDE in scripts/seed_flower_morphology.py or the next "
          f"re-run will overwrite them.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8756)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--report", action="store_true",
                    help="print hand-tuned values that the seeder would "
                         "overwrite, then exit")
    args = ap.parse_args()
    if args.report:
        return _report()

    httpd = ThreadingHTTPServer(("127.0.0.1", args.port),
                                partial(_Handler, directory=_HTML))
    url = f"http://127.0.0.1:{args.port}/tune_morphology.html"
    print(f"Tuning {len(_species_list(_load()))} flowering species.")
    print(f"  {url}")
    print("  ← / → page species · S saves · Ctrl-C to stop")
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:                                   # noqa: BLE001
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
