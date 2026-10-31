#!/usr/bin/env python3
"""
fetch_colour_evidence.py — photographs of each plant in flower, to check its
colour by (V3.33, F172; docs/plans/V3.33-flower-colours-from-photographs.md).

Run on a computer with an internet connection (this project's cloud sessions
cannot reach iNaturalist):

    python scripts/fetch_colour_evidence.py --probe "Ratibida columnifera"
    python scripts/fetch_colour_evidence.py
    python scripts/fetch_colour_evidence.py --page-only

1. ``--probe NAME`` asks iNaturalist about one plant and prints what came back,
   field by field. **Run it first.** This script was written without ever
   seeing an answer from the API; if a field it reads is missing, the probe
   says which, before anything is cached.
2. With no options it works through the plants to check
   (``src.colour_checks.worklist``: the audit's flagged plants, the genus
   guesses, the name reads, the blanks, then the flora reads), asks iNaturalist
   for each plant's taxon and up to six research-grade observations marked
   *flowering*, in Alberta and Saskatchewan first, and caches them in
   ``data/fetched/colour_evidence.json``. One request a second, under the
   app's own name; about fifteen minutes for everything. Stop it any time
   (Ctrl+C): the next run carries on where it stopped.
3. It then writes ``data/fetched/colour_review.html``. Open it in a browser,
   look at each plant, press its colours, and press *Save my answers*.
   ``--page-only`` rewrites the page from the cache without asking anything.

The photographs are fetched to look at, not to ship: nothing here leaves the
computer, and ``data/fetched/`` is never in the installer or the website.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import colour_checks  # noqa: E402

EVIDENCE = ROOT / "data" / "fetched" / "colour_evidence.json"
PAGE = ROOT / "data" / "fetched" / "colour_review.html"

API = "https://api.inaturalist.org/v1"
#: Alberta and Saskatchewan, as a box (south, west, north, east).
PRAIRIES = (49.0, -120.0, 60.0, -101.36)
#: iNaturalist's Plant Phenology annotation: term 12, value 13 is Flowering.
FLOWERING = {"term_id": 12, "term_value_id": 13}
PHOTOS_PER_PLANT = 6
ENOUGH = 3


class Refused(RuntimeError):
    """The service said no (429, 403, 5xx) after waiting: stop, keep the cache."""


def _user_agent() -> str:
    try:
        from src.http_utils import user_agent
        return user_agent()
    except Exception:                                      # noqa: BLE001
        return "SiteAndPattern/dev"


def _context():
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:                                      # noqa: BLE001
        return ssl.create_default_context()


def get(path: str, params: dict, *, tries: int = 3) -> dict:
    """GET ``API + path`` and return the JSON. Waits and tries again on a
    429 or a 5xx; raises :class:`Refused` when the service keeps refusing."""
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    wait = 30
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={
            "User-Agent": _user_agent(), "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30,
                                        context=_context()) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429 or exc.code >= 500:
                if attempt + 1 < tries:
                    print(f"  iNaturalist said {exc.code}; waiting {wait} s")
                    time.sleep(wait)
                    wait *= 2
                    continue
            raise Refused(f"HTTP {exc.code} for {url}") from exc
    raise Refused(f"no answer for {url}")


# ── Reading iNaturalist's answers ───────────────────────────────────────────

def query_name(scientific: str) -> str:
    """iNaturalist writes a variety as a trinomial with no rank word."""
    words = [w for w in scientific.split()
             if w not in ("var.", "subsp.", "ssp.", "f.", "x", "×")]
    return " ".join(words)


def pick_taxon(results: list, scientific: str) -> dict:
    """The taxon iNaturalist means by ``scientific``: the exact name, else
    the result whose ``matched_term`` is it (an older name), else nothing."""
    want = query_name(scientific).lower()
    for key in ("name", "matched_term"):
        for r in results or []:
            if str(r.get(key) or "").lower() == want:
                return r
    return {}


def _photo_url(photo: dict) -> str:
    url = str(photo.get("url") or "")
    return url.replace("/square.", "/medium.") if url else ""


def photos_from(observations: list, *, flowering: bool, where: str) -> list:
    """``[{url, page, attribution, license, observed_on, place, observation,
    flowering, where}]``: the first photograph of each observation."""
    out = []
    for obs in observations or []:
        photos = obs.get("photos") or []
        if not photos:
            continue
        url = _photo_url(photos[0])
        if not url:
            continue
        out.append({
            "url": url,
            "page": obs.get("uri") or
                    f"https://www.inaturalist.org/observations/{obs.get('id')}",
            "observation": obs.get("id"),
            "attribution": photos[0].get("attribution") or "",
            "license": photos[0].get("license_code") or "",
            "observed_on": obs.get("observed_on") or "",
            "place": obs.get("place_guess") or "",
            "flowering": flowering,
            "where": where,
        })
    return out


def fetch_one(scientific: str, *, delay: float) -> dict:
    """Everything the review page shows for one plant."""
    taxa = get("/taxa", {"q": query_name(scientific), "is_active": "true",
                         "per_page": 10})
    taxon = pick_taxon(taxa.get("results"), scientific)
    time.sleep(delay)
    if not taxon:
        return {"found": False, "fetched": _now(),
                "note": "iNaturalist has no taxon by this name"}
    entry = {
        "found": True, "fetched": _now(),
        "taxon": {"id": taxon.get("id"), "name": taxon.get("name"),
                  "common": taxon.get("preferred_common_name") or "",
                  "page": f"https://www.inaturalist.org/taxa/{taxon.get('id')}"},
        "photos": [], "note": "",
    }
    south, west, north, east = PRAIRIES
    box = {"swlat": south, "swlng": west, "nelat": north, "nelng": east}
    tries = (
        (dict(FLOWERING, **box), True, "Alberta and Saskatchewan"),
        (dict(FLOWERING), True, "anywhere"),
        (dict(box), False, "Alberta and Saskatchewan"),
    )
    seen = set()
    for extra, flowering, where in tries:
        params = {"taxon_id": taxon.get("id"), "quality_grade": "research",
                  "photos": "true", "per_page": 12, "order_by": "votes"}
        params.update(extra)
        found = get("/observations", params).get("results") or []
        time.sleep(delay)
        for photo in photos_from(found, flowering=flowering, where=where):
            if photo["observation"] in seen:
                continue
            seen.add(photo["observation"])
            entry["photos"].append(photo)
            if len(entry["photos"]) >= PHOTOS_PER_PLANT:
                break
        if len(entry["photos"]) >= ENOUGH:
            break
    if not entry["photos"]:
        entry["note"] = "no research-grade photographs"
    elif not any(p["flowering"] for p in entry["photos"]):
        entry["note"] = "none marked flowering: look for a flower in the shots"
    return entry


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── The probe ───────────────────────────────────────────────────────────────

def probe(scientific: str) -> int:
    print(f"Asking iNaturalist about {scientific!r} ({API})\n")
    taxa = get("/taxa", {"q": query_name(scientific), "is_active": "true",
                         "per_page": 5})
    results = taxa.get("results")
    if not isinstance(results, list):
        print("The answer has no 'results' list. Top-level fields:",
              sorted(taxa))
        return 1
    for r in results:
        print(f"  taxon {r.get('id')}: name={r.get('name')!r} "
              f"rank={r.get('rank')!r} matched_term={r.get('matched_term')!r} "
              f"common={r.get('preferred_common_name')!r}")
    taxon = pick_taxon(results, scientific)
    if not taxon:
        print("\nNo result matches the name exactly: this plant would show as "
              "'not found'.")
        return 1
    print(f"\nChosen: {taxon.get('id')} {taxon.get('name')}")
    obs = get("/observations", dict(
        FLOWERING, taxon_id=taxon.get("id"), quality_grade="research",
        photos="true", per_page=3, order_by="votes"))
    found = obs.get("results")
    if not isinstance(found, list):
        print("Observations: no 'results' list. Fields:", sorted(obs))
        return 1
    print(f"Observations marked flowering: total_results="
          f"{obs.get('total_results')!r}")
    for o in found:
        p = (o.get("photos") or [{}])[0]
        print(f"  observation {o.get('id')} {o.get('observed_on')!r} "
              f"{o.get('place_guess')!r}\n    photo url={p.get('url')!r}\n"
              f"    licence={p.get('license_code')!r} "
              f"attribution={p.get('attribution')!r}")
    shots = photos_from(found, flowering=True, where="anywhere")
    print(f"\nPhotographs this script would show: {len(shots)}")
    for s in shots:
        print("  ", s["url"])
    if found and not shots:
        print("Observations came back with no usable photo URL: the 'photos' "
              "or 'url' field is not where this script expects it.")
        return 1
    return 0


# ── The review page ─────────────────────────────────────────────────────────

def build_page(items: list, evidence: dict, *, made: str) -> str:
    """The review page: one card per plant, the colour buttons, and *Save my
    answers*. Self-contained: open the file in any browser."""
    data = []
    for item in items:
        ev = evidence.get(item["scientific_name"]) or {}
        data.append(dict(item, reason_words=colour_checks.REASON_WORDS.get(
            item["reason"], ""), evidence=ev))
    payload = json.dumps({
        "made": made, "items": data,
        "colours": [[k, colour_checks.LABELS[k], colour_checks.HEX[k]]
                    for k in colour_checks.ANSWER_COLOURS],
        "labels": {k: colour_checks.LABELS[k] for k in colour_checks.HEX},
    }, ensure_ascii=False).replace("</", "<\\/")
    return _PAGE.replace("/*DATA*/null", payload).replace(
        "{{COUNT}}", html.escape(str(len(data))))


_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Flower colour review</title>
<style>
:root { --bg:#f4f5f1; --card:#fff; --ink:#1f2a24; --muted:#5a665f;
  --line:#d6ddd7; --accent:#2f5d4a; --on:#2f5d4a; --warn:#9a6400; }
* { box-sizing:border-box; }
body { margin:0; font:16px/1.5 system-ui, "Segoe UI", sans-serif;
  background:var(--bg); color:var(--ink); }
header { position:sticky; top:0; z-index:5; background:var(--ink);
  color:#fff; padding:10px 16px; display:flex; gap:12px; flex-wrap:wrap;
  align-items:center; }
header h1 { font-size:18px; margin:0 12px 0 0; }
header .count { font-variant-numeric:tabular-nums; }
header button, header select { font:inherit; border-radius:6px;
  border:1px solid #fff4; background:#fff1; color:#fff; padding:6px 12px; }
header button.main { background:#fff; color:var(--ink); font-weight:700; }
main { max-width:1100px; margin:0 auto; padding:16px; display:flex;
  flex-direction:column; gap:16px; }
.intro { color:var(--muted); max-width:70ch; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:14px; display:flex; flex-direction:column; gap:10px; }
.card.done { border-color:var(--accent); }
.top { display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap; }
.name { font-weight:700; font-size:18px; }
.sci { font-style:italic; color:var(--muted); }
.now { display:flex; align-items:center; gap:8px; color:var(--muted); }
.sw { width:22px; height:22px; border-radius:50%; border:1px solid #0003;
  display:inline-block; vertical-align:middle; }
.why { color:var(--warn); font-size:14px; }
.photos { display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr));
  gap:8px; }
.photos a { display:block; position:relative; }
.photos img { width:100%; aspect-ratio:1; object-fit:cover; border-radius:6px;
  background:#e8ebe6; display:block; }
.photos .tag { position:absolute; left:4px; bottom:4px; background:#000a;
  color:#fff; font-size:12px; padding:1px 6px; border-radius:4px; }
.none { color:var(--muted); font-style:italic; }
.buttons { display:flex; flex-wrap:wrap; gap:6px; }
.buttons button { font:inherit; font-size:15px; display:flex; align-items:center;
  gap:6px; padding:6px 10px; border-radius:6px; border:1px solid var(--line);
  background:#fff; cursor:pointer; min-height:40px; }
.buttons button.on { border:2px solid var(--on); background:#e6f0ea;
  font-weight:700; }
.buttons .order { font-size:12px; color:var(--accent); }
.buttons .verdict { background:#f6f6f2; }
.answer { font-size:14px; color:var(--accent); min-height:1.2em; }
:focus-visible { outline:3px solid #b8860b; outline-offset:2px; }
</style></head><body>
<header>
  <h1>Flower colour review</h1>
  <span class="count" id="count"></span>
  <select id="show" aria-label="Show">
    <option value="todo">Still to look at</option>
    <option value="all">All plants</option>
    <option value="done">Answered</option>
  </select>
  <button class="main" id="save">Save my answers</button>
  <button id="copy">Copy answers</button>
</header>
<main>
  <p class="intro">For each plant: what colour does it look <b>in flower</b>?
  Press its colours, the main one first; a second press on a colour takes it
  back. <b>Looks right</b> keeps what the app says. Photographs open their
  iNaturalist page. Your answers are kept in this browser between visits.
  When you are done, or want to stop, press <b>Save my answers</b> and send
  the file it saves (colour_answers.json) to a session. {{COUNT}} plants.</p>
  <div id="cards"></div>
</main>
<script>
const DATA = /*DATA*/null;
const KEY = "site-and-pattern-colour-review-v1";
let answers = {};
try { answers = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
function keep() { try { localStorage.setItem(KEY, JSON.stringify(answers)); } catch (e) {} }
const LABEL = DATA.labels;
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
function words(a) {
  if (!a) return "";
  if (a.verdict === "looks_right") return "Looks right";
  if (a.verdict === "no_showy_flower") return "No showy flower";
  if (a.verdict === "cant_tell") return "Can't tell";
  return (a.colours || []).map((c, i) => (i ? "and sometimes " : "") + LABEL[c].toLowerCase()).join(", ");
}
function card(item) {
  const ev = item.evidence || {};
  const sci = item.scientific_name;
  const photos = (ev.photos || []).map(p => p.observation);
  const now = (item.colours || []).map(c => LABEL[c] || c).join(" and ") || "no colour";
  const answer = el("div", {class: "answer", "aria-live": "polite"});
  const root = el("section", {class: "card", "aria-label": item.common_name});
  const buttons = el("div", {class: "buttons"});
  function set(a) {
    if (a) answers[sci] = Object.assign(a, {observations: photos}); else delete answers[sci];
    keep(); paint(); counts();
  }
  function paint() {
    const a = answers[sci];
    root.classList.toggle("done", !!a);
    answer.textContent = a ? "Your answer: " + words(a) : "";
    for (const b of buttons.querySelectorAll("button")) {
      const c = b.dataset.colour, v = b.dataset.verdict;
      const on = a && ((c && (a.colours || []).includes(c)) || (v && a.verdict === v));
      b.classList.toggle("on", !!on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
      const o = b.querySelector(".order");
      if (o) o.textContent = c && a && a.colours && a.colours.indexOf(c) === 0 && a.colours.length > 1 ? "main" : "";
    }
  }
  for (const [key, label, hex] of DATA.colours) {
    buttons.append(el("button", {"data-colour": key, onclick: () => {
      const a = answers[sci] && answers[sci].colours ? answers[sci] : {colours: []};
      const list = a.colours.slice();
      const i = list.indexOf(key);
      if (i >= 0) list.splice(i, 1); else if (list.length < 3) list.push(key);
      set(list.length ? {colours: list} : null);
    }}, [el("span", {class: "sw", style: "background:" + hex}), label, el("span", {class: "order"})]));
  }
  for (const [v, label] of [["looks_right", "Looks right"], ["no_showy_flower", "No showy flower"], ["cant_tell", "Can't tell"]]) {
    buttons.append(el("button", {class: "verdict", "data-verdict": v, onclick: () => {
      set(answers[sci] && answers[sci].verdict === v ? null : {verdict: v});
    }}, label));
  }
  const grid = el("div", {class: "photos"});
  for (const p of ev.photos || []) {
    grid.append(el("a", {href: p.page, target: "_blank", rel: "noopener",
      title: (p.attribution || "") + (p.place ? " · " + p.place : "")}, [
      el("img", {src: p.url, alt: item.common_name + " photograph", loading: "lazy"}),
      el("span", {class: "tag", text: (p.flowering ? "flowering" : "not marked") + (p.where === "anywhere" ? " · elsewhere" : "")})]));
  }
  const taxon = ev.taxon ? el("a", {href: ev.taxon.page, target: "_blank", rel: "noopener", text: "More on iNaturalist"}) : null;
  root.append(
    el("div", {class: "top"}, [
      el("div", {}, [el("div", {class: "name", text: item.common_name}), el("div", {class: "sci", text: sci})]),
      el("div", {class: "now"}, [
        item.hex ? el("span", {class: "sw", style: "background:" + item.hex}) : null,
        "The app says " + now.toLowerCase() + " (" + item.reason_words + ")"])]),
    item.why ? el("div", {class: "why", text: "Why it is here: " + item.why}) : null,
    ev.photos && ev.photos.length ? grid : el("div", {class: "none", text: ev.note || "Not fetched yet: run the script again."}),
    taxon, buttons, answer);
  root.dataset.sci = sci;
  paint();
  return root;
}
const cards = document.getElementById("cards");
const all = DATA.items.map(card);
function counts() {
  const n = DATA.items.filter(i => answers[i.scientific_name]).length;
  document.getElementById("count").textContent = n + " of " + DATA.items.length + " answered";
  filter();
}
function filter() {
  const show = document.getElementById("show").value;
  for (const c of all) {
    const done = !!answers[c.dataset.sci];
    c.hidden = (show === "todo" && done) || (show === "done" && !done);
  }
}
for (const c of all) cards.append(c);
document.getElementById("show").addEventListener("change", filter);
function exported() {
  return JSON.stringify({version: 1, made: new Date().toISOString(), list_made: DATA.made, answers: answers}, null, 1);
}
document.getElementById("save").addEventListener("click", () => {
  const blob = new Blob([exported()], {type: "application/json"});
  const a = el("a", {href: URL.createObjectURL(blob), download: "colour_answers.json"});
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

def load_evidence() -> dict:
    try:
        with open(EVIDENCE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_evidence(evidence: dict) -> None:
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    tmp = EVIDENCE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=1, ensure_ascii=False)
    tmp.replace(EVIDENCE)


def write_page(items: list, evidence: dict) -> None:
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(build_page(items, evidence, made=_now()))
    print(f"Wrote {PAGE}: open it in a browser.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--probe", metavar="NAME",
                    help="ask about one plant and print the answer; cache "
                         "nothing")
    ap.add_argument("--page-only", action="store_true",
                    help="rewrite the review page from the cache; ask nothing")
    ap.add_argument("--no-flora", action="store_true",
                    help="leave out the plants read from Budd's flora (the "
                         "last and optional part of the list)")
    ap.add_argument("--limit", type=int, default=0,
                    help="ask about at most this many plants this run")
    ap.add_argument("--refresh", action="store_true",
                    help="ask again about plants already cached")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds between requests (default 1)")
    args = ap.parse_args(argv)

    if args.probe:
        try:
            return probe(args.probe)
        except Refused as exc:
            print(f"iNaturalist refused: {exc}")
            return 1
    rows = colour_checks.load_master()
    items = colour_checks.worklist(rows, colour_checks.load_checks(),
                                   include_flora=not args.no_flora)
    evidence = load_evidence()
    if not args.page_only:
        todo = [i for i in items
                if args.refresh or i["scientific_name"] not in evidence]
        if args.limit:
            todo = todo[:args.limit]
        print(f"{len(items)} plants on the list; asking about {len(todo)} "
              f"(about {len(todo) * 3 * args.delay / 60:.0f} minutes).")
        try:
            for n, item in enumerate(todo, 1):
                sci = item["scientific_name"]
                entry = fetch_one(sci, delay=args.delay)
                evidence[sci] = entry
                shown = len(entry.get("photos") or [])
                print(f"  {n:3d}/{len(todo)} {item['common_name']}: "
                      f"{shown} photographs"
                      + (f" ({entry['note']})" if entry.get("note") else ""))
                if n % 10 == 0:
                    save_evidence(evidence)
        except KeyboardInterrupt:
            print("\nStopped. What was fetched is kept; run again to carry on.")
        except Refused as exc:
            print(f"\niNaturalist kept refusing ({exc}). What was fetched is "
                  "kept; try again later.")
        finally:
            save_evidence(evidence)
    write_page(items, evidence)
    return 0


if __name__ == "__main__":
    sys.exit(main())
