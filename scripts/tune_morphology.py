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

...BUT MOST OF THEM DO NOT NEED A PLANT IN FRONT OF YOU
Nobody is going to grow 434 species, and the photo pane is why they don't have
to. Petal count, symmetry, petal shape, architecture, disc colour, basal rosette
and branching are all readable off a good photograph; flowering stems and bloom
height come off a habit shot. Only **diameter in cm** genuinely needs a ruler or
a published description. So the photographs are the bottleneck, which is why the
strip does three jobs: it shows the 323 pictures the catalogue already ships
(as `unsorted`, because nobody has judged them yet), it files them into named
slots on one click, and it will fetch the species' wider openly-licensed set
when a slot is empty.

Provenance travels with the numbers: `flower_data_source` says what KIND of
source a value came from and `flower_data_citation` says which one. See
docs/DATA_SOURCES.md — including for why `--flora-fetch` is off by default.

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
          "flowering_stems", "flower_data_source", "flower_data_citation")

# Where a number can come from, weakest first. The bench's job is to move
# species UP this list; the seeder can only ever write the bottom one.
DATA_SOURCES = ("estimated", "photo", "flora", "measured")

PHOTO_SLOTS = ("habit", "flower", "leaf", "fruit", "bark_stem", "winter",
               "seedling")

# An eighth, synthetic bucket: a photograph the catalogue already HAS but that
# nobody has looked at and judged. Never written to disk — a photo leaves this
# bucket by being assigned to a real slot.
UNSORTED = "unsorted"

_PHOTOS_JSON = os.path.join(_ROOT, "data", "plant_photos.json")
_PHOTO_DIR = os.path.join(_ROOT, "data", "photos")

# Reading numbers off a published description is OFF unless somebody turns it
# on, and it is a module-level switch rather than a UI toggle so that turning it
# on is a decision made at the command line by a person who has read the site's
# terms. See src/flora_read.py for why the whole design is shaped this way.
FLORA_FETCH = False


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
               "notes": (rec.get("notes") or "")[:400],
               "photos": photos_by_slot(rec.get("scientific_name") or "", rec),
               "links": lookup_links(rec.get("scientific_name") or "")}
        for f in FIELDS:
            row[f] = rec.get(f)
        out.append(row)
    out.sort(key=lambda r: r["common_name"].lower())
    return out


def _rec_for(sci: str, records=None) -> dict:
    """One species' record out of `plants_master.json`, or `{}`."""
    sci = (sci or "").strip()
    for r in (records if records is not None else _load()):
        if (r.get("scientific_name") or "") == sci:
            return r
    return {}


def _photo_index() -> dict:
    """`data/plant_photos.json`, grouped by species. Read fresh on every request
    so an import shows up without a restart."""
    if not os.path.exists(_PHOTOS_JSON):
        return {}
    try:
        with open(_PHOTOS_JSON, encoding="utf-8") as fh:
            rows = json.load(fh)
    except (OSError, ValueError):
        return {}
    out: dict = {}
    for i, e in enumerate(rows):
        e = dict(e)
        e["_i"] = i
        out.setdefault((e.get("scientific_name") or "").strip(), []).append(e)
    return out


def photos_by_slot(sci: str, rec: dict | None = None) -> dict:
    """`{slot: [photo, …]}` for one species, for the bench's photo strip.

    Two sources, and the second one is why this function exists in this shape.
    ``data/plant_photos.json`` holds photographs somebody has *judged* — this is
    a habit shot, that is a leaf. But 323 species already carry a photograph in
    ``plants_master.json:image_url``, fetched by ``fetch_inaturalist_images.py``
    and nobody's judgement about anything. When the seven-slot strip replaced the
    single reference image in V2.35, all 323 of them stopped being drawn: the
    strip reads the JSON, and the JSON was empty. That is the regression this
    fixes.

    They come back in an eighth bucket, ``unsorted``, rather than as ``flower``.
    The database's back-fill *does* guess ``flower`` for these
    (``src/db/plants.py:_seed_plant_photos``) and the guess is usually right —
    iNaturalist's leading photo is nearly always a flower macro. But repeating
    the guess here would make the bench report "323 flower photographs" when the
    honest number is "323 photographs, none of them looked at", and the whole
    point of the strip is to find out which slots are actually covered (P9).
    A count that starts at zero and climbs as you sort means something.

    Assigning one writes a real row, and the seeder's dedupe key is
    ``(scientific_name, url)`` — so a slot you choose here beats the back-fill's
    guess on the next reseed rather than colliding with it.
    """
    rows = _photo_index().get((sci or "").strip(), [])
    by: dict = {s: [] for s in PHOTO_SLOTS}
    by[UNSORTED] = []
    seen = set()
    for e in rows:
        if e.get("slot") in by:
            by[e["slot"]].append(e)
        seen.add((e.get("url") or "").strip())
    url = ((rec or {}).get("image_url") or "").strip()
    if url and url not in seen:
        by[UNSORTED].append(_unsorted_photo(sci, rec or {}))
    return by


def _unsorted_photo(sci: str, rec: dict) -> dict:
    """The legacy single photo, in the shape the strip draws.

    ``_i: None`` is load-bearing: it says "no row on disk yet", which is what
    disables the delete button on it. There is nothing to delete — the record it
    lives in is `plants_master.json`, which this pane does not own.
    """
    return {"scientific_name": sci,
            "slot": UNSORTED,
            "url": (rec.get("image_url") or "").strip(),
            "attribution": rec.get("image_attribution") or "",
            "license": rec.get("image_license") or "",
            "source": "inaturalist",
            "origin": "seed",
            "taken_on": "", "rank": 0, "notes": "",
            "_i": None}


def inat_candidates(sci: str, limit: int = 12) -> list:
    """Every openly-licensed iNaturalist photo of one species, for the picker.

    Triage alone cannot fill the `habit` slot. The catalogue's 323 photographs
    are the *first* redistributable photo per species, and on iNaturalist that
    is nearly always a flower macro — so sorting them honestly produces 323
    flower shots and zero habit shots. The wider photo set (usually ~12) does
    contain whole-plant photographs; somebody just has to look at them.

    All the hard parts already exist in `fetch_inaturalist_images.py`: the exact
    name match that stops a photo of the wrong species being attached, and the
    licence whitelist. This reuses both — one species at a time, on a click.
    """
    sys.path.insert(0, os.path.join(_ROOT, "scripts"))
    import fetch_inaturalist_images as inat                  # noqa: PLC0415

    taxon = inat._query_taxon(sci)
    if not taxon:
        return []
    detail = inat._fetch_taxon_detail(taxon.get("id")) or taxon
    out = []
    for url, credit, code in inat.open_candidates(inat.taxon_candidates(detail)):
        out.append({"url": url, "attribution": credit, "license": code,
                    "source": "inaturalist"})
        if len(out) >= limit:
            break
    return out


def lookup_links(sci: str) -> list:
    """Where to READ a number you cannot measure.

    You are not going to grow all 434 species, and you should not have to. The
    numbers this catalogue wants are published — Flora of North America gives
    ray counts and laminae lengths outright, and it is free to read. It is not
    free to bulk-copy, which is the whole reason this is a list of links and not
    an importer: a person reading a description and typing "13 rays" is
    recording a fact, and facts are not anybody's property.
    """
    sci = (sci or "").strip()
    if not sci:
        return []
    from urllib.parse import quote                          # noqa: PLC0415
    q = quote(sci)
    under = quote(sci.replace(" ", "_"))
    # Ordered by how freely the numbers on the far end may be reused, not by how
    # good the descriptions are. `read` marks the ones the --flora-fetch button
    # will offer to read for you; the rest are for your eyes only.
    return [
        {"name": "Budd's Flora (prairie provinces)",
         "why": "Gov-of-Canada publication, and the RIGHT region — start here",
         "url": f"https://www.google.com/search?q={q}+%22Budd%27s+Flora%22+"
                f"site%3Apublications.gc.ca+OR+site%3Aarchive.org"},
        {"name": "Wikipedia",
         "why": "CC BY-SA — freely reusable with credit; often has the numbers",
         "url": f"https://en.wikipedia.org/wiki/{under}", "read": True},
        {"name": "iNaturalist",
         "why": "many photographs — count the rays off one, no reading needed",
         "url": f"https://www.inaturalist.org/search?q={q}"},
        {"name": "Flora of N. America",
         "why": "the most precise descriptions — and copyrighted; read, don't copy",
         "url": f"http://www.efloras.org/browse.aspx?flora_id=1&name_str={q}",
         "read": True},
        {"name": "VASCAN",
         "why": "the accepted Canadian name, if this one has moved",
         "url": f"https://data.canadensys.net/vascan/search?q={q}"},
        {"name": "Minnesota Wildflowers",
         "why": "excellent plain-language descriptions for prairie forbs",
         "url": f"https://www.minnesotawildflowers.info/search?q={q}"},
    ]


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
        if self.path.startswith("/api/flora/"):
            from urllib.parse import unquote, urlparse       # noqa: PLC0415
            if not FLORA_FETCH:
                return self._json(
                    {"error": "reading from a flora is off — restart with "
                              "--flora-fetch, after reading the site's terms"}, 403)
            url = unquote(self.path[len("/api/flora/"):])
            if urlparse(url).scheme not in ("http", "https"):
                return self._json({"error": "not a http(s) url"}, 400)
            from src.flora_read import NotPermitted, read_species  # noqa: PLC0415
            try:
                reading = read_species(url)
            except NotPermitted as exc:
                return self._json({"error": str(exc)}, 403)
            except Exception as exc:                        # noqa: BLE001
                return self._json({"error": f"{type(exc).__name__}: {exc}"}, 502)
            return self._json({"patch": reading.as_patch(),
                               "matched": reading.matched})
        if self.path.startswith("/api/candidates/"):
            from urllib.parse import unquote                # noqa: PLC0415
            sci = unquote(self.path[len("/api/candidates/"):])
            try:
                return self._json({"candidates": inat_candidates(sci)})
            except Exception as exc:                        # noqa: BLE001
                return self._json({"error": f"{type(exc).__name__}: {exc}"}, 502)
        if self.path.startswith("/api/scene/"):
            from urllib.parse import unquote                # noqa: PLC0415
            sci = unquote(self.path[len("/api/scene/"):])
            sc = _scene_for(sci, _load())
            return self._json(sc if sc else {}, 200 if sc else 404)
        if self.path.startswith("/photos/"):
            # data/photos lives outside the served html/ root, so it needs its
            # own route rather than a symlink (which Windows would not have).
            from urllib.parse import unquote                # noqa: PLC0415
            name = os.path.basename(unquote(self.path[len("/photos/"):]))
            path = os.path.join(_PHOTO_DIR, name)
            if not os.path.isfile(path):
                self.send_error(404)
                return None
            self.send_response(200)
            self.send_header("Content-Type",
                             "image/png" if name.lower().endswith(".png")
                             else "image/jpeg")
            self.send_header("Content-Length", str(os.path.getsize(path)))
            self.end_headers()
            with open(path, "rb") as fh:
                self.wfile.write(fh.read())
            return None
        if self.path in ("/", "/index.html"):
            self.path = "/tune_morphology.html"
        return super().do_GET()

    def do_POST(self):                                      # noqa: N802
        if self.path.startswith("/api/photo/"):
            return self._photo_post()
        if self.path.startswith("/api/photo-assign/"):
            return self._photo_assign()
        if self.path.startswith("/api/photo-delete/"):
            return self._photo_delete()
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


    # ── photos ──────────────────────────────────────────────────────────────

    def _photo_post(self):
        """`POST /api/photo/<sci>/<slot>` — one raw image body, one photo added.

        Raw body rather than multipart: the browser can `fetch(file)` a File
        object directly, and parsing multipart by hand in a dev tool is a
        pointless place to spend correctness.
        """
        from urllib.parse import unquote                    # noqa: PLC0415
        parts = self.path[len("/api/photo/"):].split("/")
        if len(parts) != 2:
            return self._json({"error": "want /api/photo/<sci>/<slot>"}, 400)
        sci, slot = unquote(parts[0]), unquote(parts[1])
        if slot not in PHOTO_SLOTS:
            return self._json({"error": f"unknown slot {slot!r}"}, 400)
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return self._json({"error": "empty body"}, 400)
        blob = self.rfile.read(n)

        credit = unquote(self.headers.get("X-Credit", "")) or ""
        lic = self.headers.get("X-License", "cc-by-sa")

        import tempfile                                     # noqa: PLC0415
        from src.photo_import import import_photo           # noqa: PLC0415
        tmp = tempfile.NamedTemporaryFile(suffix=".img", delete=False)
        tmp.write(blob)
        tmp.close()
        try:
            res = import_photo(tmp.name, sci, slot, _PHOTO_DIR)
        except (OSError, ValueError) as exc:
            return self._json({"error": str(exc)}, 400)
        finally:
            os.unlink(tmp.name)

        rows = []
        if os.path.exists(_PHOTOS_JSON):
            with open(_PHOTOS_JSON, encoding="utf-8") as fh:
                rows = json.load(fh)
        rows.append({"scientific_name": sci, "slot": slot,
                     "url": "data/photos/" + res["filename"],
                     "attribution": credit or "© the project owner (own photograph)",
                     "license": lic, "source": "owner",
                     "taken_on": "", "rank": 0, "notes": ""})
        with open(_PHOTOS_JSON, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        return self._json({"ok": True, "filename": res["filename"],
                           "bytes": res["bytes"], "stripped": res["stripped"],
                           "note": res["note"],
                           "photos": photos_by_slot(sci, _rec_for(sci))})

    def _photo_assign(self):
        """`POST /api/photo-assign/<sci>/<slot>` with `{"url": …}` — say what an
        existing photograph actually is.

        The sorting half of the strip. No file moves and nothing is downloaded:
        the photo stays on somebody else's server exactly as the catalogue has
        always held it, and what gets written is the *judgement* — this URL is a
        habit shot. The credit and the licence travel with it verbatim, because
        they belong to the photograph and not to the row.
        """
        from urllib.parse import unquote                    # noqa: PLC0415
        parts = self.path[len("/api/photo-assign/"):].split("/")
        if len(parts) != 2:
            return self._json({"error": "want /api/photo-assign/<sci>/<slot>"}, 400)
        sci, slot = unquote(parts[0]), unquote(parts[1])
        if slot not in PHOTO_SLOTS:
            return self._json({"error": f"unknown slot {slot!r}"}, 400)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._json({"error": "bad json"}, 400)
        url = (body.get("url") or "").strip()
        rec = _rec_for(sci)
        if not rec:
            return self._json({"error": "unknown species"}, 404)
        if not url:
            return self._json({"error": "no url"}, 400)

        rows = []
        if os.path.exists(_PHOTOS_JSON):
            with open(_PHOTOS_JSON, encoding="utf-8") as fh:
                rows = json.load(fh)
        for e in rows:
            if ((e.get("scientific_name") or "") == sci
                    and (e.get("url") or "").strip() == url):
                # Re-slotting rather than duplicating: you looked again and
                # decided it was a leaf after all.
                e["slot"] = slot
                break
        else:
            rows.append({
                "scientific_name": sci, "slot": slot, "url": url,
                "attribution": (body.get("attribution")
                                or rec.get("image_attribution") or ""),
                "license": body.get("license") or rec.get("image_license") or "",
                "source": body.get("source") or "inaturalist",
                "taken_on": "", "rank": 0, "notes": ""})
        with open(_PHOTOS_JSON, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        return self._json({"ok": True, "slot": slot,
                           "photos": photos_by_slot(sci, rec)})

    def _photo_delete(self):
        """`POST /api/photo-delete/<index>` — drop one row and its file."""
        from urllib.parse import unquote                    # noqa: PLC0415
        try:
            idx = int(unquote(self.path[len("/api/photo-delete/"):]))
        except ValueError:
            return self._json({"error": "bad index"}, 400)
        if not os.path.exists(_PHOTOS_JSON):
            return self._json({"error": "no photo index"}, 404)
        with open(_PHOTOS_JSON, encoding="utf-8") as fh:
            rows = json.load(fh)
        if not 0 <= idx < len(rows):
            return self._json({"error": "out of range"}, 404)
        gone = rows.pop(idx)
        with open(_PHOTOS_JSON, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        # Only remove the FILE for a photo we imported ourselves; a URL row
        # points at somebody else's server and there is nothing local to delete.
        url = gone.get("url") or ""
        if url.startswith("data/photos/"):
            path = os.path.join(_ROOT, url)
            if os.path.isfile(path):
                os.unlink(path)
        sci = gone.get("scientific_name", "")
        return self._json({"ok": True,
                           "photos": photos_by_slot(sci, _rec_for(sci))})


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
    ap.add_argument("--flora-fetch", action="store_true",
                    help="enable the per-species 'read the numbers off this "
                         "page' button. Fetches ONE page per click, obeys "
                         "robots.txt, keeps only the four numbers and never "
                         "the prose. Read the site's terms of use first — "
                         "see docs/DATA_SOURCES.md.")
    args = ap.parse_args()
    if args.report:
        return _report()

    global FLORA_FETCH                                      # noqa: PLW0603
    FLORA_FETCH = bool(args.flora_fetch)

    httpd = ThreadingHTTPServer(("127.0.0.1", args.port),
                                partial(_Handler, directory=_HTML))
    url = f"http://127.0.0.1:{args.port}/tune_morphology.html"
    print(f"Tuning {len(_species_list(_load()))} flowering species.")
    print(f"  {url}")
    print("  ← / → page species · S saves · Ctrl-C to stop")
    if FLORA_FETCH:
        print("  flora reading is ON: one page per click, robots.txt obeyed,")
        print("  four numbers kept and no prose. You are responsible for having")
        print("  read that site's terms of use — see docs/DATA_SOURCES.md.")
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
