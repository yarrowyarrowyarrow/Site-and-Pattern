"""
citations.py — turning a source key into something a reader can act on.

Design principle P9 (uncertainty is a feature — ship ranges and confidence,
never false precision) — see docs/DESIGN_PHILOSOPHY.md.

The biological data has always been cited. All 361 plant↔fauna edges carry a
real bibliographic source, and have since they were written. **No screen in the
app has ever shown one.** ``plant_fauna.source`` survived the database, the
``relationship_edges`` view and the ``Edge`` record, and was dropped by every
widget that rendered a relationship — so the only citations a user could see
were photo credits, and the ecology itself appeared to come from nowhere.

That is the gap this module closes. It reads ``data/sources_master.json`` and
formats a key into a citation a reader can take to a library.

Two honesty rules it enforces at the render layer:

* **A placeholder is never rendered as a citation.** ``NOT_A_WORK`` entries
  (see ``unattributed_prairie_pollination``) say so in plain language instead.
* **An unverified bibliographic record is not dressed up.** Every entry
  currently reads ``unverified``, meaning the details were transcribed from the
  seed data rather than checked against the work. :func:`disclaimer` is the one
  line that should accompany any list of these, and it does not claim more than
  the data supports.

Qt-free and dependency-free so panels, the PDF export and the scripting API can
all use it.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Optional

from src.resources import resource_path


def _sources_path() -> str:
    return resource_path("data", "sources_master.json")


@lru_cache(maxsize=1)
def _registry() -> dict:
    """``{key: record}`` plus ``{alias: key}``, loaded once.

    Missing or malformed file degrades to empty: a citation that cannot be
    formatted falls back to showing the raw key, which is still more than the
    app showed before.
    """
    path = _sources_path()
    if not os.path.exists(path):
        return {"by_key": {}, "by_alias": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            blob = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"by_key": {}, "by_alias": {}}
    by_key, by_alias = {}, {}
    for rec in blob.get("sources", []):
        key = (rec.get("key") or "").strip()
        if not key:
            continue
        by_key[key] = rec
        for alias in rec.get("aliases", []):
            by_alias[alias.strip()] = key
    return {"by_key": by_key, "by_alias": by_alias}


def resolve(source: str) -> Optional[dict]:
    """The registry record for a key or a legacy alias, or None."""
    reg = _registry()
    s = (source or "").strip()
    if not s:
        return None
    if s in reg["by_key"]:
        return reg["by_key"][s]
    alias = reg["by_alias"].get(s)
    return reg["by_key"].get(alias) if alias else None


def is_placeholder(source: str) -> bool:
    """True when this 'source' names no actual work.

    Callers should not print it as a citation — say the claim is unattributed
    instead. Pretending a placeholder is a reference is the precise failure the
    bibliography exists to prevent.
    """
    rec = resolve(source)
    return bool(rec) and (rec.get("kind") or "").strip() == "NOT_A_WORK"


def format_citation(source: str, *, short: bool = False) -> str:
    """One source key → a human citation.

    ``short=True`` gives the author-year form for inline use ("Acorn & Sheldon
    2006"); the default gives the full reference. An unknown key returns itself
    rather than an empty string — showing something unresolved beats silently
    showing nothing, which is how the citations went missing in the first place.
    """
    s = (source or "").strip()
    if not s:
        return ""
    rec = resolve(s)
    if rec is None:
        return s
    if (rec.get("kind") or "") == "NOT_A_WORK":
        return "unattributed — no specific work recorded"

    authors = (rec.get("authors") or "").strip()
    year = rec.get("year")
    title = (rec.get("title") or "").strip()
    if short:
        if authors and year:
            return f"{_short_authors(authors)} {year}"
        return _short_authors(authors) or title or s

    bits = []
    # **Do not restate an author the title already carries** (V2.65). 17 of the
    # 114 records were parsed out of a GloBI study title, so `authors` is a
    # prefix of `title` rather than a separate field, and printing both gave
    # "Robertson, C (1929). Robertson, C. 1929. Flowers and insects: …". That
    # was invisible while the bibliography was unpublished and is the first
    # thing a reader sees now that it is on the About page.
    if authors and _title_restates(authors, title, year):
        bits.append(title)
    else:
        if authors:
            bits.append(f"{authors} ({year})" if year else authors)
        elif year:
            bits.append(str(year))
        if title:
            bits.append(title)
    container = (rec.get("container") or "").strip()
    if container:
        bits.append(f"in {container}")
    publisher = (rec.get("publisher") or "").strip()
    place = (rec.get("place") or "").strip()
    if publisher:
        bits.append(f"{publisher}, {place}" if place else publisher)
    url = (rec.get("url") or "").strip()
    if url:
        bits.append(url)
    return ". ".join(b.rstrip(".") for b in bits if b) + "."


def _title_restates(authors: str, title: str, year=None) -> bool:
    """True when the title already opens with the author string.

    Compared on letters only, because the two differ in punctuation exactly
    where they were split: `authors` is "Dorey, J.B., Fischer, E.E." and the
    title runs "Dorey, J.B., Fischer, E.E. A globally synthesised…". A prefix
    test on the raw strings misses those; on letters alone it catches them.

    Two ways to be sure, because one alone is not enough. If the title
    continues with the year, it is the "Authors. Year. Title." shape and there
    is no doubt — that is what catches *Small, E. 1976*, whose author string is
    six letters long. Failing that, fall back to length: a title that happens
    to begin with eight or more of the author's own letters by coincidence is
    not a case worth protecting against, while a short one might be (author
    "Li", title "Lichens of Alberta").
    """
    def letters(s):
        return "".join(ch for ch in s.lower() if ch.isalnum())
    a, t = letters(authors), letters(title)
    if not a or not t.startswith(a):
        return False
    return t[len(a):].startswith(str(year)) if year else len(a) >= 8


def _short_authors(authors: str) -> str:
    """"Acorn, J. and Sheldon, I." → "Acorn & Sheldon"; long lists → "et al."."""
    if not authors:
        return ""
    parts = [p.strip() for p in authors.replace(" and ", ", ").split(",")]
    surnames = []
    for p in parts:
        # "and Sheldon" → "Sheldon"; initials ("J.", "F.A.H.") are not surnames.
        if p.lower().startswith("and "):
            p = p[4:].strip()
        if p and not p.endswith(".") and p.lower() != "and" and len(p) > 2:
            surnames.append(p)
    if not surnames:
        return authors
    if len(surnames) == 1:
        return surnames[0]
    if len(surnames) == 2:
        return f"{surnames[0]} & {surnames[1]}"
    return f"{surnames[0]} et al."


def format_sources(source: str, *, short: bool = False) -> str:
    """A comma-separated key list → a readable citation string.

    A claim may rest on more than one work — the bee attributes cite three —
    which is stored as a comma-separated list of keys.
    """
    keys = [k.strip() for k in (source or "").split(",") if k.strip()]
    seen, out = set(), []
    for k in keys:
        text = format_citation(k, short=short)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return "; ".join(out) if short else " ".join(out)


def all_sources() -> list[dict]:
    """Every registry record, for a "where this data came from" screen."""
    return sorted(_registry()["by_key"].values(),
                  key=lambda r: ((r.get("kind") == "NOT_A_WORK"),
                                 (r.get("covers") or ""),
                                 (r.get("authors") or "")))


def disclaimer() -> str:
    """The sentence that has to travel with any list of these citations.

    Says two separate things, both of which are true and neither of which the
    app may skip: the bibliographic details are transcribed rather than checked,
    and nobody has confirmed that a cited work supports the specific claim
    citing it. Saying where a claim came from is not the same as certifying it.
    """
    return ("These are the works the data cites. Their bibliographic details "
            "were transcribed from the source records and have not been "
            "checked against the works themselves, and no one has verified "
            "that a given work supports every claim citing it — this tells you "
            "where a claim came from, not that it has been confirmed.")
