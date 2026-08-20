#!/usr/bin/env python3
"""
scripts/tune_fauna.py — the fauna bench (V2.36).

    python scripts/tune_fauna.py            # → http://127.0.0.1:8757
    python scripts/tune_fauna.py --report   # what differs from the seeder

The companion to `tune_morphology.py`, for the animals. Same shape: a species
list with triage filters, the characters, a drawn vocabulary beside every
dropdown, and provenance that travels with the values. Writes straight to
`data/bee_attributes_master.json` and `data/lepidoptera_attributes_master.json`.

WHY IT IS A SECOND SCRIPT
    The two benches share a skeleton and not one field. The flora tool is
    already 700 lines about flowers and leaves; folding four fauna taxa into it
    would make both worse to read and to change. What is genuinely identical —
    loading and saving a master JSON, the provenance vocabulary, the
    coerce-and-reject loop — lives in `scripts/_bench_common.py`. Nothing else
    is abstracted on two examples.

WHAT IT EDITS
    Bees          body length, build, hair + integument colour, metallic,
                  scopa position, wing tint, and the per-tergite BAND PATTERN.
    Lepidoptera   wingspan range, three wing colours, wing shape, wing pattern,
                  eyespot count, resting posture, and FLIGHT STYLE.

`band_pattern` is the one to spend time on. 29 of the catalogue's 69 bees are
Bombus and they rendered as a single animal; the pattern is written the way
every bumblebee key is written — thorax, then T1 to T6 — and the bench draws the
bee as you type it, so you can hold the drawing against the plate.

`flight_style` is the other. It is a real character and it also drives the 3D
flight animation, so recording it makes a skipper dart and a monarch sail.

A DEV tool, not an app panel: the seed catalogue is the project's, not the end
user's.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

from _bench_common import (                                 # noqa: E402
    DATA_SOURCES, coerce_field, load_json, save_json)

_HTML = os.path.join(_ROOT, "html")
_FAUNA = os.path.join(_ROOT, "data", "fauna_master.json")
_BEES = os.path.join(_ROOT, "data", "bee_attributes_master.json")
_LEPS = os.path.join(_ROOT, "data", "lepidoptera_attributes_master.json")

# The columns this tool edits, per taxon. Everything else in the record — the
# ecological block (nesting, flight season, hosts) and its own `source` — is
# left alone: it was gathered from different places and is not what this bench
# is for.
BEE_FIELDS = ("body_length_mm", "build", "hair_colour", "integument_colour",
              "metallic", "scopa_position", "wing_tint", "band_pattern",
              "morph_data_source", "morph_data_citation")
LEP_FIELDS = ("wingspan_min_mm", "wingspan_max_mm", "forewing_colour",
              "hindwing_colour", "margin_colour", "wing_shape", "wing_pattern",
              "eyespot_count", "resting_posture", "flight_style",
              "morph_data_source", "morph_data_citation")
FIELDS = tuple(dict.fromkeys(BEE_FIELDS + LEP_FIELDS))

PROVENANCE = ("morph_data_source", "morph_data_citation")
_INT_FIELDS = ("metallic", "eyespot_count")
_FLOAT_FIELDS = ("body_length_mm", "wingspan_min_mm", "wingspan_max_mm")


def _vocabularies() -> dict:
    """Every enum-valued field this tool edits, read from src/data_quality.py
    and served at /api/vocab.

    The HTML holds NO copy — the same rule the flora bench arrived at after its
    three hand-typed lists went stale. A dropdown built from the gate's own
    allowlist cannot offer a value the gate will reject.
    """
    from src import data_quality as dq                      # noqa: PLC0415
    def L(v):
        return list(v) if isinstance(v, tuple) else sorted(v)
    return {
        "build":            L(dq.BEE_BUILDS),
        "scopa_position":   L(dq.SCOPA_POSITIONS),
        "wing_tint":        L(dq.WING_TINTS),
        "wing_shape":       L(dq.WING_SHAPES),
        "wing_pattern":     L(dq.WING_PATTERNS),
        "resting_posture":  L(dq.RESTING_POSTURES),
        "flight_style":     L(dq.FLIGHT_STYLES),
        "morph_data_source": list(DATA_SOURCES),
        # Not a dropdown — the band editor's palette. Served so the HTML has no
        # copy of the colour names either.
        "_band_colours":    L(dq.BAND_COLOURS),
        "_band_hex":        dict(dq.BAND_COLOUR_HEX),
        "_band_max":        dq.BAND_SEGMENTS_MAX,
    }


VOCABULARIES = _vocabularies()
# Only the plain enum fields are membership-checked on save; the two underscore
# entries above are palette data, not vocabularies for a field.
_ENUM_FIELDS = {k: v for k, v in VOCABULARIES.items() if not k.startswith("_")}


def _attr_path(taxon: str) -> str:
    return _BEES if taxon == "bee" else _LEPS


def _species_list() -> list:
    """Every bee and lepidopteran, with its morphology and a `taxon`.

    Birds, other insects and mammals are deliberately absent: their appearance
    is still the name-keyed table in src/scene_wildlife.py (24 birds → 16 looks)
    and giving them controls here would imply a schema that does not exist yet.
    """
    fauna = load_json(_FAUNA)
    attrs = {}
    for taxon, path in (("bee", _BEES), ("lepidoptera", _LEPS)):
        for rec in load_json(path):
            if rec.get("scientific_name"):
                attrs[(taxon, rec["scientific_name"])] = rec

    out = []
    for f in fauna:
        taxon = f.get("taxon")
        if taxon not in ("bee", "lepidoptera"):
            continue
        sci = f.get("scientific_name") or ""
        a = attrs.get((taxon, sci), {})
        row = {
            "scientific_name": sci,
            "common_name": f.get("common_name") or "",
            "taxon": taxon,
            "genus": sci.split(" ")[0] if sci else "",
            "kind": a.get("kind") or ("bee" if taxon == "bee" else "butterfly"),
            "icon": f.get("icon") or "",
            "image_url": f.get("image_url") or "",
            "image_attribution": f.get("image_attribution") or "",
            "described": bool(a),
            "notes": (a.get("notes") or f.get("description") or "")[:400],
            "links": lookup_links(sci, taxon),
        }
        for k in FIELDS:
            row[k] = a.get(k)
        out.append(row)
    out.sort(key=lambda r: (r["taxon"], r["common_name"].lower()))
    return out


def lookup_links(sci: str, taxon: str) -> list:
    """Where to go and read this animal up, freest-to-reuse first.

    Same ordering argument as the flora bench: this is not a quality ranking,
    it is a licence one. A fact read off any of these and typed in here is a
    fact; see docs/DATA_SOURCES.md.
    """
    if not sci:
        return []
    from urllib.parse import quote                          # noqa: PLC0415
    q = quote(sci)
    out = [
        {"name": "iNaturalist", "url": f"https://www.inaturalist.org/search?q={q}",
         "why": "photographs, openly licensed, and range maps"},
        {"name": "BugGuide", "url": f"https://bugguide.net/index.php?q=search&keys={q}",
         "why": "North American identification, with the field marks named"},
    ]
    if taxon == "bee":
        out.append({"name": "Bumble Bees of North America (Williams et al.)",
                    "url": "https://www.leifrichardson.org/bbna.html",
                    "why": "THE bumblebee colour-pattern key — band by band"})
        out.append({"name": "Discover Life bee guide",
                    "url": f"https://www.discoverlife.org/mp/20q?search={q}",
                    "why": "genus-level keys for the non-Bombus bees"})
    else:
        out.append({"name": "Moth Photographers Group",
                    "url": f"https://mothphotographersgroup.msstate.edu/Fastsearch.php?Text={q}",
                    "why": "plates for the moths, arranged by family"})
        out.append({"name": "Butterflies of Canada",
                    "url": f"https://www.cbif.gc.ca/eng/species-bank/butterflies-of-canada/?id=1370403265515&search={q}",
                    "why": "wingspan and flight period for the Canadian fauna"})
    return out


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=_HTML, **kw)

    def log_message(self, *a, **k):      # quiet
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return None

    def do_GET(self):                                       # noqa: N802
        if self.path == "/api/fauna":
            return self._json(_species_list())
        if self.path == "/api/vocab":
            return self._json(VOCABULARIES)
        if self.path in ("/", "/index.html"):
            self.path = "/tune_fauna.html"
        return super().do_GET()

    def do_POST(self):                                      # noqa: N802
        if not self.path.startswith("/api/fauna/"):
            return self._json({"error": "not found"}, 404)
        from urllib.parse import unquote                    # noqa: PLC0415
        sci = unquote(self.path[len("/api/fauna/"):])
        n = int(self.headers.get("Content-Length") or 0)
        try:
            patch = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._json({"error": "bad json"}, 400)

        taxon = patch.pop("_taxon", "")
        if taxon not in ("bee", "lepidoptera"):
            return self._json({"error": "unknown taxon"}, 400)
        path = _attr_path(taxon)
        records = load_json(path)
        rec = next((r for r in records if r.get("scientific_name") == sci), None)
        if rec is None:
            return self._json({"error": "unknown species"}, 404)

        allowed = BEE_FIELDS if taxon == "bee" else LEP_FIELDS
        changed = {}
        for f in allowed:
            if f not in patch:
                continue
            try:
                v = coerce_field(f, patch[f], _INT_FIELDS, _FLOAT_FIELDS)
            except (TypeError, ValueError):
                return self._json({"error": f"{f}: not a number"}, 400)
            if f in _ENUM_FIELDS and v not in ("", None):
                if v not in _ENUM_FIELDS[f]:
                    return self._json(
                        {"error": f"{f}={v!r} is not in the vocabulary"}, 400)
            if f == "band_pattern" and v:
                bad = _bad_band_tokens(v)
                if bad:
                    return self._json(
                        {"error": f"band colour(s) not in the palette: "
                                  f"{', '.join(bad)}"}, 400)
            old = rec.get(f)
            if f in _FLOAT_FIELDS and old is not None and v is not None:
                try:
                    if float(old) == float(v):
                        continue          # numerically unchanged; no churn
                except (TypeError, ValueError):
                    pass
            if old != v:
                changed[f] = v
                rec[f] = v

        # A wingspan range has to stay a range. Caught here rather than at the
        # data-quality gate, where the person who typed it has moved on.
        lo, hi = rec.get("wingspan_min_mm"), rec.get("wingspan_max_mm")
        if lo is not None and hi is not None and float(hi) < float(lo):
            return self._json({"error": f"wingspan {lo}–{hi} is backwards"}, 400)

        if changed:
            save_json(path, records)
        return self._json({"saved": bool(changed), "changed": changed})


def _bad_band_tokens(value) -> list:
    from src.data_quality import BAND_COLOURS, BAND_SEGMENTS_MAX  # noqa: PLC0415
    from src.data_quality import band_pattern_tokens             # noqa: PLC0415
    toks = band_pattern_tokens(value)
    bad = [t for t in toks if t not in BAND_COLOURS]
    if len(toks) > BAND_SEGMENTS_MAX:
        bad.append(f"{len(toks)} segments (max {BAND_SEGMENTS_MAX})")
    return bad


def _report() -> int:
    """Which shipped values differ from what the seeder would write — i.e.
    everything a person has corrected by hand, and would lose if
    `seed_fauna_morphology.py` were re-run."""
    import seed_fauna_morphology as seeder                  # noqa: PLC0415
    n = 0
    for taxon, path, keys in (("bee", _BEES, BEE_FIELDS),
                              ("lepidoptera", _LEPS, LEP_FIELDS)):
        for rec in load_json(path):
            sci = rec.get("scientific_name")
            if not sci:
                continue
            want = (seeder.bee_morphology(sci) if taxon == "bee"
                    else seeder.lep_morphology(sci, rec.get("kind")))
            diff = {k: (want.get(k), rec.get(k)) for k in want
                    if k in keys and want.get(k) != rec.get(k)}
            if diff:
                n += 1
                print(f"{sci}:")
                for k, (a, b) in diff.items():
                    print(f"    {k}: seeder {a!r} -> shipped {b!r}")
    print(f"\n{n} species differ from the seeder. Fold them into "
          f"scripts/seed_fauna_morphology.py or a re-run will overwrite them.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8757)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--report", action="store_true",
                    help="print hand-tuned values the seeder would overwrite")
    args = ap.parse_args()
    if args.report:
        return _report()

    url = f"http://127.0.0.1:{args.port}/"
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    rows = _species_list()
    bees = sum(1 for r in rows if r["taxon"] == "bee")
    print(f"fauna bench on {url}  ({bees} bees, {len(rows) - bees} lepidoptera)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
