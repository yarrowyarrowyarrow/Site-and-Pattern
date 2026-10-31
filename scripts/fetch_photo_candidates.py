#!/usr/bin/env python3
"""
fetch_photo_candidates.py — photographs of each plant to pick from (V3.35,
F251; docs/plans/V3.35-several-photos-a-plant.md).

Run on a computer with an internet connection (this project's cloud sessions
cannot reach iNaturalist):

    python scripts/fetch_photo_candidates.py --probe "Ratibida columnifera"
    python scripts/fetch_photo_candidates.py
    python scripts/fetch_photo_candidates.py --page-only

1. ``--probe NAME`` asks iNaturalist about one plant and prints what came back,
   query by query. **Run it first.** The fruit, no-flowers and winter queries
   and the taxon's own photo set have never been seen from here; the probe
   names any field this script reads that is not there.
2. With no options it works through every plant, the ones with no photograph
   first, then best picks first (``src.plant_priority.rank``, on a throwaway
   copy of the catalogue). For each it asks for research-grade observations
   whose photograph may ship (``src.photo_picks.LICENCES``, checked again on
   every photo), favourites first, Alberta and Saskatchewan before anywhere:
   in flower, in fruit, with no flowers (leaves and the whole plant), in winter
   for trees, shrubs and vines, and the photos on its own iNaturalist page. At
   most four of each kind, none under 500 px, two at most from one
   photographer. One request a second: about an hour for everything. It caches
   to ``data/fetched/photo_candidates.json``; stop it any time (Ctrl+C) and
   the next run carries on.
3. It then writes ``data/fetched/photo_review.html``. Open it in a browser,
   confirm or change each plant's picks, and press *Save my picks*.
   ``--page-only`` rewrites the page from the cache without asking anything.

Nothing here leaves the computer; ``data/fetched/`` is never in the installer
or on the website. The taxon ids come from ``data/fetched/open_photo_counts.json``
(the V3.34 count) or the colour review's cache, so most plants cost no lookup.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import colour_checks, photo_picks  # noqa: E402

import fetch_colour_evidence as inat  # noqa: E402

CANDIDATES = ROOT / "data" / "fetched" / "photo_candidates.json"
PAGE = ROOT / "data" / "fetched" / "photo_review.html"
COUNTS = ROOT / "data" / "fetched" / "open_photo_counts.json"

PER_GROUP = 4
MIN_SIDE = 500
PER_PHOTOGRAPHER = 2
PER_PAGE = 20
#: iNaturalist's Plant Phenology annotation (term 12): Flowering 13, Fruiting
#: 14, No Evidence of Flowering 21.
PHENOLOGY = {"flower": 13, "fruit": 14, "plant": 21}
WINTER_MONTHS = "11,12,1,2,3"
WOODY = frozenset({"tree", "shrub", "vine"})
#: The taxon's own photo set: at most this many.
CHOSEN = 3
#: What each kind is called on a thumbnail of the picking page.
TAGS = {"flower": "in flower", "plant": "leaves, plant", "fruit": "fruit",
        "winter": "winter", "chosen": "its page", "now": "has now"}


# ── Reading iNaturalist's answers ───────────────────────────────────────────

def candidate(photo: dict, *, group: str, where: str, obs: dict = None):
    """One photograph as the page shows it, or ``None`` if it may not ship,
    is not on the open-data store, or is smaller than :data:`MIN_SIDE`."""
    licence = (photo.get("license_code") or "").strip().lower()
    url = photo.get("url") or ""
    if licence not in photo_picks.LICENCES or photo_picks.OPEN_DATA_HOST not in url:
        return None
    dims = photo.get("original_dimensions") or {}
    side = max(int(dims.get("width") or 0), int(dims.get("height") or 0))
    if dims and side < MIN_SIDE:
        return None
    obs = obs or {}
    return {
        "photo": photo.get("id") or photo_picks.photo_id(url),
        "url": photo_picks.sized(url, "medium"),
        "thumb": photo_picks.sized(url, "small"),
        "license": licence,
        "attribution": " ".join((photo.get("attribution") or "").split()),
        "observation": obs.get("id"),
        "taken_on": str(obs.get("observed_on") or "")[:10],
        "place": obs.get("place_guess") or "",
        "faves": int(obs.get("faves_count") or 0),
        "user": ((obs.get("user") or {}).get("login") or ""),
        "where": where,
        "group": group,
        "size": side,
    }


def from_observations(observations: list, *, group: str, where: str) -> list:
    """The first photograph of each observation that may ship."""
    out = []
    for obs in observations or []:
        for photo in obs.get("photos") or []:
            cand = candidate(photo, group=group, where=where, obs=obs)
            if cand:
                out.append(cand)
                break
    return out


def _query(taxon_id, *, region: bool, extra: dict) -> dict:
    params = {"taxon_id": taxon_id, "quality_grade": "research",
              "photos": "true", "photo_license": ",".join(photo_picks.LICENCES),
              "order_by": "votes", "per_page": PER_PAGE}
    params.update(extra)
    if region:
        south, west, north, east = inat.PRAIRIES
        params.update(swlat=south, swlng=west, nelat=north, nelng=east)
    return params


def tries_for(group: str) -> list:
    """``[(region only, extra params), ...]`` in the order they are asked."""
    if group == "winter":
        extra = {"month": WINTER_MONTHS}
        return [(True, extra), (False, extra)]
    extra = {"term_id": 12, "term_value_id": PHENOLOGY[group]}
    tries = [(True, extra), (False, extra)]
    if group == "plant":
        tries.append((True, {}))       # few observations say "no flowers"
    return tries


def groups_for(plant_type: str) -> list:
    return ["flower", "plant", "fruit"] + (
        ["winter"] if plant_type in WOODY else [])


class Picker:
    """Collects one plant's candidates under its limits: per kind, per
    photographer, and no photograph twice."""

    def __init__(self):
        self.groups: dict = {}
        self.seen: set = set()
        self.by_user: dict = {}

    def add(self, cand: dict, limit: int) -> bool:
        group = self.groups.setdefault(cand["group"], [])
        if len(group) >= limit or cand["photo"] in self.seen:
            return False
        user = cand.get("user") or ""
        if user and self.by_user.get(user, 0) >= PER_PHOTOGRAPHER:
            return False
        group.append(cand)
        self.seen.add(cand["photo"])
        if user:
            self.by_user[user] = self.by_user.get(user, 0) + 1
        return True


def now_candidate(row: dict):
    """The photograph the plant has now, offered so it can be kept."""
    url = (row.get("image_url") or "").strip()
    if not url:
        return None
    return {"photo": photo_picks.photo_id(url), "url": url,
            "thumb": photo_picks.sized(url, "small"),
            "license": (row.get("image_license") or "").lower(),
            "attribution": " ".join((row.get("image_attribution") or "").split()),
            "observation": None, "taken_on": "", "place": "", "faves": 0,
            "user": "", "where": "", "group": "now", "size": 0}


def fetch_one(row: dict, taxon_id, *, delay: float) -> dict:
    """Everything the picking page shows for one plant."""
    entry = {"found": bool(taxon_id), "taxon": taxon_id, "fetched": inat._now(),
             "groups": {}, "note": ""}
    picker = Picker()
    now = now_candidate(row)
    if now and now["photo"]:
        picker.add(now, 1)
    if not taxon_id:
        entry["note"] = "iNaturalist has no taxon by this name"
        entry["groups"] = picker.groups
        return entry
    for group in groups_for(row.get("plant_type") or ""):
        for region, extra in tries_for(group):
            answer = inat.get("/observations",
                              _query(taxon_id, region=region, extra=extra))
            time.sleep(delay)
            where = "Alberta or Saskatchewan" if region else "elsewhere"
            for cand in from_observations(answer.get("results"), group=group,
                                          where=where):
                picker.add(cand, PER_GROUP)
            if len(picker.groups.get(group) or []) >= PER_GROUP:
                break
    detail = inat.get(f"/taxa/{taxon_id}", {})
    time.sleep(delay)
    for taxon in (detail.get("results") or [])[:1]:
        for tp in taxon.get("taxon_photos") or []:
            cand = candidate(tp.get("photo") or {}, group="chosen", where="")
            if cand:
                picker.add(cand, CHOSEN)
    entry["groups"] = picker.groups
    if not any(k != "now" for k in picker.groups):
        entry["note"] = "no photograph that may ship"
    return entry


# ── Finding each plant's taxon ──────────────────────────────────────────────

_ACCEPTED = re.compile(r"VASCAN: ([A-Z][a-z]+ [a-z-]+(?: (?:subsp\.|var\.) "
                       r"[a-z-]+)?)")


def known_taxa() -> dict:
    """``{scientific_name: taxon id}`` from the V3.34 count and the colour
    review's cache, so most plants need no lookup."""
    out = {}
    for path, key in ((inat.EVIDENCE, "taxon"), (COUNTS, "taxon")):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        for sci, entry in data.items():
            tid = entry.get(key)
            if isinstance(tid, dict):
                tid = tid.get("id")
            if tid and sci not in out:
                out[sci] = int(tid)
    return out


def accepted_name(sci: str) -> str:
    """The name VASCAN accepts for a row the catalogue keeps under another
    (``data_quality.KNOWN_NOMENCLATURE``), or ``""``."""
    from src.data_quality import KNOWN_NOMENCLATURE           # noqa: PLC0415
    m = _ACCEPTED.search(KNOWN_NOMENCLATURE.get(sci) or "")
    return m.group(1) if m else ""


def look_up(sci: str, *, delay: float):
    for name in filter(None, (sci, accepted_name(sci))):
        found = inat.get("/taxa", {"q": inat.query_name(name),
                                   "is_active": "true", "per_page": 10})
        time.sleep(delay)
        taxon = inat.pick_taxon(found.get("results"), name)
        if taxon:
            return taxon.get("id")
    return None


# ── The order of the list ───────────────────────────────────────────────────

def ranked_names() -> list:
    """Scientific names best picks first, from a throwaway copy of the
    catalogue (about ten seconds; nothing of yours is touched); ``[]`` if it
    cannot be built, and the list then runs by name."""
    where = tempfile.mkdtemp(prefix="photo_order_")
    try:
        from src.db import plants as db                       # noqa: PLC0415
        from src.plant_priority import rank                   # noqa: PLC0415
        db._DATA_DIR = where
        db._DB_PATH = os.path.join(where, "order.db")
        db.init_db()
        return [r["scientific_name"] for r in rank(db.search_plants())]
    except Exception as exc:                                  # noqa: BLE001
        print(f"  (could not rank the plants: {exc}; listing them by name)")
        return []
    finally:
        shutil.rmtree(where, ignore_errors=True)


def worklist(rows: list, ranked: list) -> list:
    """Every plant: those with no photograph first, then best picks first."""
    place = {sci: i for i, sci in enumerate(ranked)}
    items = [{"scientific_name": r["scientific_name"],
              "common_name": r.get("common_name") or r["scientific_name"],
              "plant_type": r.get("plant_type") or "",
              "has_photo": bool((r.get("image_url") or "").strip())}
             for r in rows if (r.get("scientific_name") or "").strip()]
    items.sort(key=lambda i: (i["has_photo"],
                              place.get(i["scientific_name"], len(place)),
                              i["common_name"]))
    return items


# ── The probe ───────────────────────────────────────────────────────────────

def probe(sci: str) -> int:
    print(f"Asking iNaturalist about {sci!r} (every kind, the winter one too)"
          "\n")
    taxon_id = known_taxa().get(sci) or look_up(sci, delay=0)
    if not taxon_id:
        print("No taxon found, under this name or the one VASCAN accepts.")
        return 1
    print(f"Taxon {taxon_id}")
    bad = 0
    for group in groups_for("shrub"):
        region, extra = tries_for(group)[1]
        answer = inat.get("/observations",
                          _query(taxon_id, region=region, extra=extra))
        found = answer.get("results")
        print(f"\n{group}: total_results={answer.get('total_results')!r}")
        if not isinstance(found, list):
            print("  no 'results' list. Fields:", sorted(answer))
            return 1
        for obs in found[:3]:
            for p in (obs.get("photos") or [])[:1]:
                print(f"  observation {obs.get('id')} faves="
                      f"{obs.get('faves_count')!r} user="
                      f"{(obs.get('user') or {}).get('login')!r}\n"
                      f"    photo {p.get('id')} licence={p.get('license_code')!r}"
                      f" size={p.get('original_dimensions')!r}\n"
                      f"    url={p.get('url')!r}")
        shots = from_observations(found, group=group, where="elsewhere")
        print(f"  photographs this script would offer: {len(shots)}")
        if found and not shots:
            bad += 1
    detail = inat.get(f"/taxa/{taxon_id}", {})
    photos = [tp.get("photo") or {} for t in (detail.get("results") or [])[:1]
              for tp in t.get("taxon_photos") or []]
    print(f"\nIts own iNaturalist page: {len(photos)} photographs")
    for p in photos[:3]:
        print(f"  photo {p.get('id')} licence={p.get('license_code')!r} "
              f"url={p.get('url')!r}")
    if not photos:
        print("  no 'taxon_photos' in the answer: that group will be empty.")
    if bad:
        print(f"\n{bad} queries returned observations but no photograph this "
              "script would offer: a field is not where it expects. Send this "
              "output to a session.")
        return 1
    return 0


# ── The picking page ────────────────────────────────────────────────────────

def build_page(items: list, candidates: dict, *, made: str) -> str:
    """The picking page: one card per plant, its candidates by kind, the
    suggested picks, and *Save my picks*. Self-contained: open the file in
    any browser."""
    data = []
    for item in items:
        entry = candidates.get(item["scientific_name"]) or {}
        groups = entry.get("groups") or {}
        data.append(dict(item, note=entry.get("note") or (
            "" if entry else "Not fetched yet: run the script again."),
            groups=[[key, TAGS[key], slot, groups.get(key) or []]
                    for key, _words, slot in sorted(
                        photo_picks.GROUPS, key=lambda g: g[0] != "now")
                    if groups.get(key)],
            prepick=photo_picks.prepick(groups)))
    payload = json.dumps({
        "made": made, "items": data, "max": photo_picks.MAX_PICKS,
        "slots": [[s, w] for s, w in photo_picks.SLOT_WORDS.items()],
    }, ensure_ascii=False).replace("</", "<\\/")
    return _PAGE.replace("/*DATA*/null", payload).replace(
        "{{COUNT}}", html.escape(str(len(data))))


_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Photo picks</title>
<style>
:root { --bg:#f4f5f1; --card:#fff; --ink:#1f2a24; --muted:#5a665f;
  --line:#d6ddd7; --accent:#2f5d4a; --warn:#9a6400; }
* { box-sizing:border-box; }
body { margin:0; font:16px/1.5 system-ui, "Segoe UI", sans-serif;
  background:var(--bg); color:var(--ink); }
header { position:sticky; top:0; z-index:5; background:var(--ink); color:#fff;
  padding:10px 16px; display:flex; gap:12px; flex-wrap:wrap; align-items:center; }
header h1 { font-size:18px; margin:0 12px 0 0; }
header button, header select { font:inherit; border-radius:6px;
  border:1px solid #fff4; background:#fff1; color:#fff; padding:6px 12px; }
header button.main { background:#fff; color:var(--ink); font-weight:700; }
main { max-width:1150px; margin:0 auto; padding:16px; display:flex;
  flex-direction:column; gap:16px; }
.intro { color:var(--muted); max-width:75ch; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:14px; display:flex; flex-direction:column; gap:10px; }
.card.done { border-color:var(--accent); border-width:2px; }
.name { font-weight:700; font-size:18px; }
.sci { font-style:italic; color:var(--muted); }
.status { font-size:14px; color:var(--muted); }
.status.none { color:var(--warn); font-weight:600; }
h3 { font-size:14px; margin:6px 0 0; color:var(--muted); font-weight:600; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(128px,1fr));
  gap:8px; }
.shot { position:relative; border:2px solid transparent; border-radius:8px;
  padding:0; background:#e8ebe6; cursor:pointer; font:inherit; text-align:left; }
.shot img { width:100%; aspect-ratio:1; object-fit:cover; border-radius:6px;
  display:block; }
.shot.on { border-color:var(--accent); }
.shot .n { position:absolute; top:4px; left:4px; background:var(--accent);
  color:#fff; font-weight:700; font-size:13px; border-radius:12px;
  min-width:24px; height:24px; display:none; align-items:center;
  justify-content:center; padding:0 6px; }
.shot.on .n { display:flex; }
.shot .tag { position:absolute; left:4px; bottom:4px; background:#000a;
  color:#fff; font-size:12px; padding:1px 6px; border-radius:4px; }
.picks { display:flex; flex-wrap:wrap; gap:8px; min-height:40px; }
.pick { display:flex; flex-direction:column; gap:4px; width:136px;
  font-size:13px; }
.pick img { width:136px; height:96px; object-fit:cover; border-radius:6px; }
.pick .row { display:flex; gap:4px; flex-wrap:wrap; }
.pick button, .pick select { font:inherit; font-size:13px; min-height:28px;
  border:1px solid var(--line); border-radius:5px; background:#fff; }
.pick .lead { color:var(--accent); font-weight:700; }
.credit { font-size:12px; color:var(--muted); overflow-wrap:anywhere; }
.actions { display:flex; flex-wrap:wrap; gap:8px; }
.actions button { font:inherit; padding:6px 12px; border-radius:6px;
  border:1px solid var(--line); background:#fff; min-height:40px; cursor:pointer; }
.actions button.use { background:var(--accent); color:#fff; font-weight:700;
  border-color:var(--accent); }
.answer { font-size:14px; color:var(--accent); min-height:1.2em; }
a { color:var(--accent); }
:focus-visible { outline:3px solid #b8860b; outline-offset:2px; }
</style></head><body>
<header>
  <h1>Photo picks</h1>
  <span id="count"></span>
  <select id="show" aria-label="Show">
    <option value="todo">Still to do</option>
    <option value="all">All plants</option>
    <option value="done">Done</option>
  </select>
  <button class="main" id="save">Save my picks</button>
  <button id="copy">Copy picks</button>
</header>
<main>
  <p class="intro">Up to six photographs a plant, the first one leading
  everywhere: in the plant list, on its page and on the website. Each plant
  starts with a suggestion: the best-liked photo in flower first, then one of
  the whole plant, one of its fruit and one in winter where there is one.
  Each photo to pick from says what it shows, and "elsewhere" when it was
  taken outside Alberta and Saskatchewan. Click a photo to add it or take it
  out; <b>Lead</b> moves a pick to the
  front. Press <b>Use these</b> when a plant looks right, or <b>Keep the photo
  it has</b>. Every photo here may ship, with its credit. Plants with no photo
  yet come first. Your work is kept in this browser; press <b>Save my
  picks</b> to save a file to send to a session. {{COUNT}} plants.</p>
  <div id="cards"></div>
</main>
<script>
const DATA = /*DATA*/null;
const KEY = "site-and-pattern-photo-picks-v1";
let store = {drafts: {}, done: {}};
try { store = Object.assign(store, JSON.parse(localStorage.getItem(KEY) || "{}")); } catch (e) {}
function keep() { try { localStorage.setItem(KEY, JSON.stringify(store)); } catch (e) {} }
const SLOTS = DATA.slots;
function el(tag, attrs, kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "text") e.textContent = v; else if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const k of [].concat(kids || [])) if (k != null) e.append(k);
  return e;
}
function photoPage(c) { return "https://www.inaturalist.org/photos/" + c.photo; }
function card(item) {
  const sci = item.scientific_name;
  const byId = {};
  for (const [key, words, slot, cands] of item.groups)
    for (const c of cands) byId[c.photo] = Object.assign({slot: slot}, c);
  function draft() {
    if (!store.drafts[sci]) store.drafts[sci] = item.prepick.filter(id => byId[id]).map(id => ({photo: id, slot: byId[id].slot}));
    return store.drafts[sci];
  }
  const root = el("section", {class: "card", "aria-label": item.common_name});
  const picksBox = el("div", {class: "picks", "aria-label": "Your picks"});
  const answer = el("div", {class: "answer", "aria-live": "polite"});
  const shots = [];
  function touched() { delete store.done[sci]; keep(); paint(); counts(); }
  function toggle(id) {
    const d = draft(), i = d.findIndex(p => p.photo === id);
    if (i >= 0) d.splice(i, 1);
    else if (d.length < DATA.max) d.push({photo: id, slot: byId[id].slot});
    touched();
  }
  function paint() {
    const d = draft(), done = store.done[sci];
    root.classList.toggle("done", !!done);
    answer.textContent = done === "keep" ? "Done: keeps the photo it has" :
      done ? "Done: " + d.length + " photo" + (d.length === 1 ? "" : "s") : "";
    for (const b of shots) {
      const i = d.findIndex(p => p.photo === b.photo);
      b.node.classList.toggle("on", i >= 0);
      b.node.setAttribute("aria-pressed", i >= 0 ? "true" : "false");
      b.num.textContent = i >= 0 ? (i === 0 ? "1 ★" : String(i + 1)) : "";
    }
    picksBox.replaceChildren();
    if (!d.length) picksBox.append(el("span", {class: "credit", text: "No photos picked."}));
    d.forEach((p, i) => {
      const c = byId[p.photo]; if (!c) return;
      const sel = el("select", {"aria-label": "What photo " + (i + 1) + " shows", onchange: e => { p.slot = e.target.value; touched(); }},
        SLOTS.map(([s, w]) => { const o = el("option", {value: s, text: w}); if (s === p.slot) o.selected = true; return o; }));
      picksBox.append(el("div", {class: "pick"}, [
        el("img", {src: c.thumb, alt: item.common_name + ", pick " + (i + 1), loading: "lazy"}),
        el("div", {class: i === 0 ? "lead" : "", text: i === 0 ? "1 ★ leads" : String(i + 1)}),
        sel,
        el("div", {class: "row"}, [
          i ? el("button", {text: "Lead", onclick: () => { const d2 = draft(); d2.unshift(d2.splice(i, 1)[0]); touched(); }}) : null,
          i > 1 ? el("button", {text: "◀", "aria-label": "Move earlier", onclick: () => { const d2 = draft(); d2.splice(i - 1, 0, d2.splice(i, 1)[0]); touched(); }}) : null,
          el("button", {text: "Remove", onclick: () => toggle(p.photo)})]),
        el("a", {class: "credit", href: photoPage(c), target: "_blank", rel: "noopener", text: c.attribution})]));
    });
  }
  const parts = [
    el("div", {}, [el("div", {class: "name", text: item.common_name}),
                   el("div", {class: "sci", text: sci}),
                   el("div", {class: "status" + (item.has_photo ? "" : " none"),
                              text: item.has_photo ? "Has a photo now" : "No photo yet"})]),
    el("h3", {text: "Your picks (the first leads)"}), picksBox];
  if (item.note) parts.push(el("div", {class: "status none", text: item.note}));
  const grid = el("div", {class: "grid"});
  for (const [key, words, slot, cands] of item.groups) {
    for (const c of cands) {
      const num = el("span", {class: "n"});
      const tag = [words, c.where === "elsewhere" ? "elsewhere" : "", c.faves ? "♥ " + c.faves : ""].filter(Boolean).join(" · ");
      const node = el("button", {class: "shot", "aria-pressed": "false",
          title: c.attribution + (c.place ? " · " + c.place : ""),
          onclick: () => toggle(c.photo)},
        [el("img", {src: c.thumb, alt: item.common_name + ", " + words.toLowerCase(), loading: "lazy"}), num,
         tag ? el("span", {class: "tag", text: tag}) : null]);
      shots.push({photo: c.photo, node: node, num: num});
      grid.append(node);
    }
  }
  if (item.groups.length) parts.push(el("h3", {text: "To pick from"}), grid);
  parts.push(el("div", {class: "actions"}, [
    el("button", {class: "use", text: "Use these", onclick: () => { if (draft().length) { store.done[sci] = "picks"; keep(); paint(); counts(); } }}),
    item.has_photo ? el("button", {text: "Keep the photo it has", onclick: () => { store.done[sci] = "keep"; keep(); paint(); counts(); }}) : null,
    el("button", {text: "Start again", onclick: () => { delete store.drafts[sci]; touched(); }})]), answer);
  root.append(...parts);
  root.dataset.sci = sci;
  paint();
  return root;
}
const cards = document.getElementById("cards");
const all = DATA.items.map(card);
for (const c of all) cards.append(c);
function counts() {
  const n = DATA.items.filter(i => store.done[i.scientific_name]).length;
  document.getElementById("count").textContent = n + " of " + DATA.items.length + " done";
  const show = document.getElementById("show").value;
  for (const c of all) {
    const done = !!store.done[c.dataset.sci];
    c.hidden = (show === "todo" && done) || (show === "done" && !done);
  }
}
document.getElementById("show").addEventListener("change", counts);
function exported() {
  const answers = {};
  for (const item of DATA.items) {
    const sci = item.scientific_name, done = store.done[sci];
    if (!done) continue;
    if (done === "keep") { answers[sci] = {verdict: "keep"}; continue; }
    const byId = {};
    for (const g of item.groups) for (const c of g[3]) byId[c.photo] = c;
    answers[sci] = {picks: (store.drafts[sci] || []).filter(p => byId[p.photo]).map(p => {
      const c = byId[p.photo];
      return {photo: c.photo, url: c.url, slot: p.slot, attribution: c.attribution,
              license: c.license, observation: c.observation, taken_on: c.taken_on};
    })};
  }
  return JSON.stringify({version: 1, made: new Date().toISOString(), list_made: DATA.made, answers: answers}, null, 1);
}
document.getElementById("save").addEventListener("click", () => {
  const blob = new Blob([exported()], {type: "application/json"});
  const a = el("a", {href: URL.createObjectURL(blob), download: "photo_picks.json"});
  document.body.append(a); a.click(); a.remove();
});
document.getElementById("copy").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(exported()); alert("Copied. Paste it into a message to a session."); }
  catch (e) { prompt("Copy this:", exported()); }
});
counts();
</script></body></html>
"""


# ── The run ─────────────────────────────────────────────────────────────────

def load_candidates() -> dict:
    try:
        with open(CANDIDATES, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_candidates(candidates: dict) -> None:
    CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    tmp = CANDIDATES.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=1, ensure_ascii=False)
    tmp.replace(CANDIDATES)


def write_page(items: list, candidates: dict) -> None:
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(build_page(items, candidates, made=inat._now()))
    print(f"Wrote {PAGE}: open it in a browser.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--probe", metavar="NAME",
                    help="ask about one plant and print the answers; cache "
                         "nothing")
    ap.add_argument("--page-only", action="store_true",
                    help="rewrite the picking page from the cache; ask nothing")
    ap.add_argument("--limit", type=int, default=0,
                    help="ask about at most this many plants this run")
    ap.add_argument("--refresh", action="store_true",
                    help="ask again about plants already cached")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds between requests (default 1)")
    args = ap.parse_args(argv)

    try:
        if args.probe:
            return probe(args.probe)
    except inat.Refused as exc:
        print(f"iNaturalist refused: {exc}")
        return 1
    rows = colour_checks.load_master()
    by_sci = {r["scientific_name"]: r for r in rows}
    print("Putting the plants in order (best picks first)...")
    items = worklist(rows, ranked_names())
    candidates = load_candidates()
    if not args.page_only:
        taxa = known_taxa()
        todo = [i for i in items
                if args.refresh or i["scientific_name"] not in candidates]
        if args.limit:
            todo = todo[:args.limit]
        print(f"{len(items)} plants; asking about {len(todo)} (about "
              f"{len(todo) * 7 * args.delay / 60:.0f} minutes).")
        try:
            for n, item in enumerate(todo, 1):
                sci = item["scientific_name"]
                taxon = taxa.get(sci) or look_up(sci, delay=args.delay)
                entry = fetch_one(by_sci[sci], taxon, delay=args.delay)
                candidates[sci] = entry
                shown = sum(len(v) for k, v in entry["groups"].items()
                            if k != "now")
                print(f"  {n:3d}/{len(todo)} {item['common_name']}: {shown} "
                      f"photographs to pick from"
                      + (f" ({entry['note']})" if entry.get("note") else ""))
                if n % 10 == 0:
                    save_candidates(candidates)
        except KeyboardInterrupt:
            print("\nStopped. What was fetched is kept; run again to carry on.")
        except inat.Refused as exc:
            print(f"\niNaturalist kept refusing ({exc}). What was fetched is "
                  "kept; try again later.")
        finally:
            save_candidates(candidates)
    write_page(items, candidates)
    return 0


if __name__ == "__main__":
    sys.exit(main())
