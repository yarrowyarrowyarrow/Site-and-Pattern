"""
pending_species.py — plants ready for the catalogue but for one fact (V2.86).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

Why this exists
---------------
Since V2.80 the author's rule has been that a species' nativity is **read from
a flora** or the species does not ship: *"I do not want any inference being
made... only facts backed by data."* ``tests/test_nativity.py`` fails the build
on any catalogue row without ``native_provinces_source``, and the only thing
that writes that field is ``scripts/ingest_flora_nativity.py``, from VASCAN.

The cloud sessions that do most of the work here cannot reach VASCAN. So a
species found missing in such a session had two bad options: ship it
unsourced, which breaks the rule, or leave it unwritten, so the next session
re-derives the same list from nothing. V2.86 hit exactly this with seven native
trees (the Bur Oak replacements for Alberta).

The third option
----------------
The rows wait here, complete, in ``data/plants_pending_flora.json``. **Nothing
seeds from that file**: the app, the design generator and the website never
see a pending row. It is read by exactly three things:

* ``scripts/fetch_flora_nativity.py`` asks VASCAN about these names along with
  the catalogue's, so one archive run answers both.
* ``scripts/ingest_flora_nativity.py`` reports them in a ``promote`` bucket
  and, with ``--apply``, moves each one VASCAN confirms into
  ``plants_master.json`` with **VASCAN's** province list (not the one written
  here, which is only what the author of the row expected) and
  ``native_provinces_source = 'flora'``. Rows VASCAN does not confirm stay here
  with the reason printed.
* ``src/data_quality.py`` validates them by the catalogue's own rules, so a
  promoted row is already a clean one.

A pending row is never a claim. It is a question, written down in full so the
answer can be applied without anybody retyping the plant.
"""

from __future__ import annotations

import json
from pathlib import Path

PENDING_FILE = "plants_pending_flora.json"

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def path() -> Path:
    """Where the pending rows live. A function so a test can redirect it."""
    return _DATA_DIR / PENDING_FILE


def load() -> list[dict]:
    """The pending rows, or ``[]`` when there are none or no file."""
    try:
        rows = json.loads(path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("scientific_name")]


def names() -> list[str]:
    """The pending scientific names, sorted."""
    return sorted({r["scientific_name"].strip() for r in load()})


def save(rows: list[dict]) -> None:
    """Write the pending rows back, in the catalogue's own JSON style."""
    path().write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
