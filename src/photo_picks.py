"""
photo_picks.py — several photographs a plant, picked by the owner (V3.35, F251).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.

311 of 424 plants had one photograph and 113 had none, because the old fetch
(``scripts/fetch_inaturalist_images.py``) read only the short photo set on a
species' own iNaturalist page and gave up when none of those was openly
licensed. V3.34 measured the observations behind them: every plant iNaturalist
knows has five or more whose photograph may ship, and the 112 of those 113 it
knows have three or more. So the gap is
filled the way the colour review was: candidates fetched on the owner's PC
(``scripts/fetch_photo_candidates.py``), picked on a page in the browser, and
folded in by a session (``scripts/fold_photo_picks.py``).

This module is the rule all three share, and the app and the website read:

- :data:`LICENCES` is the bar, the data gate's (a test keeps them equal): CC0,
  CC BY and CC BY-SA. Non-commercial is out, on the V2.79 reasoning and the
  V3.34 measurement that showed it buys nothing here;
- :data:`GROUPS` are what the candidates are fetched as, each with the slot a
  pick from it is filed under;
- :func:`prepick` is the page's suggestion (decision D3): the most-liked
  flower first (D2), then one of each other kind;
- :func:`validate` refuses a pick that could not ship, and :func:`apply`
  writes the picks into the seed files, the first pick leading everywhere.

Qt-free and free of the database, like ``src.colour_checks``.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

#: The licences a plant photograph may ship under (= the data gate's set).
LICENCES = ("cc0", "cc-by", "cc-by-sa")
#: Where iNaturalist keeps its openly licensed photographs.
OPEN_DATA_HOST = "inaturalist-open-data.s3.amazonaws.com"
#: At most this many photographs a plant: what the colour review showed.
MAX_PICKS = 6

#: ``(key, heading on the picking page, slot a pick from it is filed under)``,
#: in the order the page shows them.
GROUPS = (
    ("flower", "In flower", "flower"),
    ("plant", "Leaves and the whole plant", "habit"),
    ("fruit", "Fruit or seed", "fruit"),
    ("winter", "In winter", "winter"),
    ("chosen", "From its iNaturalist page", "flower"),
    ("now", "The photo it has now", "flower"),
)
GROUP_SLOT = {key: slot for key, _words, slot in GROUPS}

#: What each slot shows, as the app and the website say it ("Photo 2 of 5: in
#: fruit"). The slots themselves are ``src.db.plants.PHOTO_SLOTS``.
SLOT_WORDS = {
    "flower": "in flower",
    "habit": "the whole plant",
    "leaf": "leaves",
    "fruit": "fruit or seed",
    "bark_stem": "bark or stems",
    "winter": "in winter",
    "seedling": "a seedling",
}

#: The lead is taken from the first of these groups that has a candidate
#: (D2: the flower leads); then one more from each kind.
_LEAD_ORDER = ("flower", "now", "chosen", "plant", "fruit", "winter")
_EXTRAS = ("plant", "fruit", "winter")

_PHOTO_ID = re.compile(r"/photos/(\d+)/")
_SIZE = re.compile(r"/(square|thumb|small|medium|large|original)\.")


def photo_id(url: str) -> Optional[int]:
    """The iNaturalist photo id in ``url``, or ``None``."""
    m = _PHOTO_ID.search(url or "")
    return int(m.group(1)) if m else None


def photo_page(url: str) -> str:
    """The photograph's own page on iNaturalist, which shows it with its
    licence and links to its observation: where a credit links to. ``""`` for
    a photograph that is not one of iNaturalist's."""
    pid = photo_id(url) if OPEN_DATA_HOST in (url or "") else None
    return f"https://www.inaturalist.org/photos/{pid}" if pid else ""


def sized(url: str, size: str) -> str:
    """``url`` at another of iNaturalist's sizes (``small`` is 240 px,
    ``medium`` 500, ``large`` 1024)."""
    return _SIZE.sub(f"/{size}.", url or "", count=1)


def prepick(candidates: dict) -> list:
    """The page's suggestion for one plant: photo ids, the lead first.

    ``candidates`` is ``{group: [candidate, ...]}``, each list best first.
    The most-liked photograph in flower leads (D2); a plant with none leads
    with the photo it has now, then iNaturalist's own pick, then a whole-plant
    shot. Then the first of each other kind, so the suggestion shows the
    plant through the year rather than four flowers."""
    picked: list = []

    def first(group: str):
        for cand in candidates.get(group) or []:
            pid = cand.get("photo")
            if pid and pid not in picked:
                return pid
        return None

    for group in _LEAD_ORDER:
        pid = first(group)
        if pid:
            picked.append(pid)
            break
    for group in _EXTRAS:
        pid = first(group)
        if pid and len(picked) < MAX_PICKS:
            picked.append(pid)
    return picked


def _slots() -> tuple:
    from src.data_quality import PHOTO_SLOTS                 # noqa: PLC0415
    return PHOTO_SLOTS


def check_photo(pick: dict) -> list:
    """What would stop one picked photograph shipping, as phrases."""
    problems = []
    url = (pick.get("url") or "").strip()
    if not url.startswith(f"https://{OPEN_DATA_HOST}/") or photo_id(url) is None:
        problems.append(f"not one of iNaturalist's open photographs: {url!r}")
    licence = (pick.get("license") or "").strip().lower()
    if licence not in LICENCES:
        problems.append(f"licence {licence!r} may not ship")
    if not " ".join((pick.get("attribution") or "").split()):
        problems.append("no credit")
    if (pick.get("slot") or "") not in _slots():
        problems.append(f"unknown slot {pick.get('slot')!r}")
    return problems


def validate(answers: dict, catalogue: Iterable[str]) -> list:
    """Every problem with ``answers`` (``{scientific_name: answer}``), as
    sentences; ``[]`` when all of them can be folded in. An answer is
    ``{"picks": [photo, ...]}``, the lead first, or ``{"verdict": "keep"}``."""
    names = set(catalogue)
    problems = []
    for sci, answer in sorted((answers or {}).items()):
        if sci not in names:
            problems.append(f"{sci}: not in the catalogue")
            continue
        if not isinstance(answer, dict):
            problems.append(f"{sci}: not an answer")
            continue
        picks = answer.get("picks")
        if answer.get("verdict") == "keep" and not picks:
            continue
        if not isinstance(picks, list) or not picks:
            problems.append(f"{sci}: no photographs picked and not kept as is")
            continue
        if len(picks) > MAX_PICKS:
            problems.append(f"{sci}: {len(picks)} photographs, more than "
                            f"{MAX_PICKS}")
        ids = [photo_id(p.get("url") or "") for p in picks
               if isinstance(p, dict)]
        if len(set(ids)) != len(ids):
            problems.append(f"{sci}: a photograph picked twice")
        for n, pick in enumerate(picks, 1):
            if not isinstance(pick, dict):
                problems.append(f"{sci}: photograph {n} is not a photograph")
                continue
            problems.extend(f"{sci}: photograph {n}: {p}"
                            for p in check_photo(pick))
    return problems


def rows_for(sci: str, picks: list) -> list:
    """The ``data/plant_photos.json`` rows for one plant's picks, ranked in
    the owner's order so the first leads (``src.db.plants.photo_order``)."""
    return [{
        "scientific_name": sci,
        "slot": pick["slot"],
        "url": sized(pick["url"].strip(), "medium"),
        "attribution": " ".join((pick.get("attribution") or "").split()),
        "license": pick["license"].strip().lower(),
        "source": "inaturalist",
        "taken_on": str(pick.get("taken_on") or "")[:10],
        "rank": rank,
        "notes": "",
    } for rank, pick in enumerate(picks)]


def apply(answers: dict, master: list, photos: list) -> dict:
    """Write ``answers`` into the seed rows in place: each picked plant's
    rows in ``photos`` (``data/plant_photos.json``) are replaced by its picks,
    and its ``plants_master.json`` row takes the lead as its one photograph,
    so every screen that shows one shows the same one. *Keep* changes
    nothing. Returns counts by what was done."""
    by_sci = {(r.get("scientific_name") or "").strip(): r for r in master}
    done = {"picked": 0, "kept": 0, "photographs": 0}
    for sci, answer in sorted(answers.items()):
        picks = answer.get("picks") or []
        if not picks:
            done["kept"] += 1
            continue
        new = rows_for(sci, picks)
        photos[:] = [r for r in photos
                     if (r.get("scientific_name") or "").strip() != sci] + new
        row = by_sci[sci]
        row["image_url"] = new[0]["url"]
        row["image_attribution"] = new[0]["attribution"]
        row["image_license"] = new[0]["license"]
        done["picked"] += 1
        done["photographs"] += len(new)
    photos.sort(key=lambda r: (r.get("scientific_name") or "",
                               int(r.get("rank") or 0)))
    return done


def caption(photo: dict, n: int, total: int) -> str:
    """"Photo 2 of 5: in fruit", for a thumbnail's accessible name."""
    words = SLOT_WORDS.get(photo.get("slot") or "", "")
    return f"Photo {n} of {total}" + (f": {words}" if words else "")
