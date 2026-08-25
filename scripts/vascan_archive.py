#!/usr/bin/env python3
"""
scripts/vascan_archive.py — read VASCAN's published checklist, not its API.

Why the API could not answer
----------------------------
VASCAN attaches distribution to the **lowest accepted taxon**. A species with
accepted varieties carries none on its own record, which left 173 of 434
species undetermined (V2.79, F148). Reaching their distribution means reading
their children, and three probes established that the API cannot enumerate
them:

    Amelanchier alnifolia                   matched, no distribution
    Amelanchier alnifolia var. alnifolia    AB, SK, MB native
    Amelanchier alnifolia var               numMatches: 0
    Amelanchier alnifolia subsp             numMatches: 0

``search.json`` is exact-name only and ``parentNameUsageID`` points the wrong
way, so a child cannot be found from its parent.

**The autonym shortcut is a trap and is deliberately not implemented.** Guessing
``<species> var. <epithet>`` resolves *Amelanchier alnifolia var. alnifolia*
and misses *Alnus incana* completely, whose Alberta taxon is
``subsp. tenuifolia`` rather than the autonym ``subsp. incana``. A rule that
answers some species and silently skips others produces a result that looks
complete and is not, which is the exact fault this whole increment exists to
correct.

So: read the Darwin Core Archive, which carries every taxon at every rank with
its parent and its distribution. One file, no per-species requests, and the
children question stops needing to be asked.

What it does NOT do
-------------------
**It does not download anything.** The project's sessions cannot reach
``data.canadensys.net``, and this follows the rule already written down in
``tools/ecoregions/fetch.py``: when a host is unreachable, print exactly what
to fetch and where to put it, and never substitute a different dataset or
write a placeholder. A wrong archive that parses is worse than no archive.
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

#: Darwin Core terms this reader needs, each with the bare and full-URI
#: spellings an archive may use in its header row.
_TERMS = {
    "taxonID": ("taxonID", "http://rs.tdwg.org/dwc/terms/taxonID"),
    # An extension file does not repeat `taxonID`. It references the core row
    # by the column `meta.xml` declares as `<coreid>`, which by convention --
    # and in the published VASCAN archive -- is called `id`. Read against a
    # synthetic archive that used `taxonID` throughout, this reader refused the
    # real distribution.txt outright:
    #     the distribution file has no taxonID column; header was
    #     ['id', 'locationID', 'locality', 'countryCode', ...]
    # `taxonID` is still tried first, so an archive that does repeat it wins.
    "coreID": ("taxonID", "id", "http://rs.tdwg.org/dwc/terms/taxonID"),
    "parentNameUsageID": (
        "parentNameUsageID",
        "http://rs.tdwg.org/dwc/terms/parentNameUsageID"),
    "acceptedNameUsageID": (
        "acceptedNameUsageID",
        "http://rs.tdwg.org/dwc/terms/acceptedNameUsageID"),
    "scientificName": (
        "scientificName", "http://rs.tdwg.org/dwc/terms/scientificName"),
    "taxonRank": ("taxonRank", "http://rs.tdwg.org/dwc/terms/taxonRank"),
    "taxonomicStatus": (
        "taxonomicStatus", "http://rs.tdwg.org/dwc/terms/taxonomicStatus"),
    "locationID": ("locationID", "http://rs.tdwg.org/dwc/terms/locationID"),
    "locality": ("locality", "http://rs.tdwg.org/dwc/terms/locality"),
    "occurrenceStatus": (
        "occurrenceStatus", "http://rs.tdwg.org/dwc/terms/occurrenceStatus"),
    "establishmentMeans": (
        "establishmentMeans",
        "http://rs.tdwg.org/dwc/terms/establishmentMeans"),
}


class ArchiveProblem(RuntimeError):
    """The archive is not what this reader needs, and says which part."""


def _column(header: list, term: str):
    """Index of ``term`` in a header row, or ``None``.

    Accepts the bare Darwin Core term and its full URI, because archives are
    published both ways and guessing one would fail on half of them.
    """
    wanted = _TERMS.get(term, (term,))
    lowered = [(h or "").strip().lower() for h in header]
    for spelling in wanted:
        if spelling.lower() in lowered:
            return lowered.index(spelling.lower())
    return None


def _rows(text: str):
    """Header plus rows from a Darwin Core text file (tab-separated)."""
    reader = csv.reader(io.StringIO(text), delimiter="\t",
                        quoting=csv.QUOTE_NONE)
    rows = list(reader)
    if not rows:
        raise ArchiveProblem("a Darwin Core file in the archive is empty")
    return rows[0], rows[1:]


def _read_member(source, needle: str) -> str:
    """The first file whose name contains ``needle``, as text.

    ``source`` is a ``.zip`` or an already-unpacked directory; both are
    accepted because unzipping first is a reasonable thing for a person to
    have done.
    """
    source = Path(source)
    if source.is_dir():
        for path in sorted(source.rglob("*")):
            if path.is_file() and needle in path.name.lower():
                return path.read_text(encoding="utf-8", errors="replace")
        raise ArchiveProblem(
            f"no file named like '{needle}' in {source}")
    try:
        with zipfile.ZipFile(source) as zf:
            for name in zf.namelist():
                if needle in Path(name).name.lower():
                    return zf.read(name).decode("utf-8", errors="replace")
    except zipfile.BadZipFile as exc:
        raise ArchiveProblem(f"{source} is not a readable zip: {exc}") from exc
    raise ArchiveProblem(f"no file named like '{needle}' inside {source}")


def read_taxa(source) -> dict:
    """``{taxonID: {name, parent, rank, status, accepted_id}}``."""
    header, rows = _rows(_read_member(source, "taxon"))
    idx = {term: _column(header, term) for term in
           ("taxonID", "parentNameUsageID", "acceptedNameUsageID",
            "scientificName", "taxonRank", "taxonomicStatus")}
    if idx["taxonID"] is None or idx["scientificName"] is None:
        raise ArchiveProblem(
            "the taxon file has no taxonID or scientificName column; header "
            f"was {header[:8]}")

    def cell(row, term):
        i = idx[term]
        return (row[i].strip() if i is not None and i < len(row) else "")

    out = {}
    for row in rows:
        if not row:
            continue
        tid = cell(row, "taxonID")
        if not tid:
            continue
        out[tid] = {
            "name": cell(row, "scientificName"),
            "parent": cell(row, "parentNameUsageID"),
            "accepted_id": cell(row, "acceptedNameUsageID"),
            "rank": cell(row, "taxonRank").lower(),
            "status": cell(row, "taxonomicStatus").lower(),
        }
    if not out:
        raise ArchiveProblem("the taxon file parsed to zero rows")
    return out


def read_distribution(source, provinces) -> dict:
    """``{taxonID: {province code: establishment means}}``.

    The means is lowercased and may be ``""`` -- a province listed with no
    establishment word is the absence of a claim about origin, never a claim
    of nativeness (the rule `src/confidence.py` states as *absent is not
    estimated*). ``occurrenceStatus`` is used when ``establishmentMeans`` is
    empty, because VASCAN carries "excluded" and "extirpated" there.
    """
    header, rows = _rows(_read_member(source, "distribution"))
    idx = {term: _column(header, term) for term in
           ("locationID", "locality", "occurrenceStatus",
            "establishmentMeans")}
    # `coreID`, not `taxonID`: this is an extension file. See `_TERMS`.
    idx["taxonID"] = _column(header, "coreID")
    if idx["taxonID"] is None:
        raise ArchiveProblem(
            f"the distribution file has no taxonID or id column to join on; "
            f"header was {header[:8]}")

    def cell(row, term):
        i = idx[term]
        return (row[i].strip() if i is not None and i < len(row) else "")

    wanted = {str(p).upper() for p in provinces}
    out: dict = {}
    for row in rows:
        if not row:
            continue
        tid = cell(row, "taxonID")
        if not tid:
            continue
        where = (cell(row, "locationID") or cell(row, "locality")).upper()
        code = where.split("-")[-1].strip()
        if code not in wanted:
            continue
        means = (cell(row, "establishmentMeans")
                 or cell(row, "occurrenceStatus")).strip().lower()
        out.setdefault(tid, {})[code] = means
    return out


def descendants(taxa: dict, root_id: str) -> set:
    """``root_id`` and every accepted taxon beneath it.

    Synonyms are excluded: a synonym's distribution is the accepted taxon's,
    counted twice, and including them would let a name VASCAN has superseded
    vote on where the plant grows.
    """
    children: dict = {}
    for tid, row in taxa.items():
        if row["parent"]:
            children.setdefault(row["parent"], []).append(tid)
    seen, stack = set(), [root_id]
    while stack:
        tid = stack.pop()
        if tid in seen or tid not in taxa:
            continue
        status = taxa[tid]["status"]
        if tid != root_id and status and "accepted" not in status:
            continue
        seen.add(tid)
        stack.extend(children.get(tid, ()))
    return seen


def _canonical(name: str) -> str:
    """A scientific name reduced to the words a catalogue binomial would use.

    VASCAN writes `Amelanchier alnifolia (Nuttall) Nuttall ex M. Roemer`; the
    catalogue writes `Amelanchier alnifolia`. Dropping the authorship is the
    whole job, and taking the first two words does it for a binomial while
    keeping `var.`/`subsp.` handling out of a place that does not need it.
    """
    return " ".join((name or "").split()[:2])


def lookup(taxa: dict, dist: dict, name: str, provinces) -> dict:
    """The same shape ``fetch_flora_nativity.lookup`` returns, from the archive.

    Distribution is **rolled up**: a species inherits from every accepted taxon
    beneath it, because a species occurs natively in Alberta if any of its
    accepted varieties does. Where a parent and a child disagree, the stronger
    claim wins -- a real `native` beats a sibling's `excluded`, since one
    variety being absent says nothing about the species.
    """
    out = {"matched": False, "accepted_name": "", "is_synonym": False,
           "taxonomic_status": "", "provinces": {}, "raw_matches": 0,
           "has_distribution": False, "taxon_rank": ""}
    target = _canonical(name).lower()
    hits = [tid for tid, row in taxa.items()
            if _canonical(row["name"]).lower() == target]
    if not hits:
        return out
    out["raw_matches"] = len(hits)

    # Prefer an accepted taxon at species rank; a synonym pointing at one is
    # followed rather than reported, because the catalogue asked about a plant
    # and not about a name.
    def rank_key(tid):
        row = taxa[tid]
        return (0 if "accepted" in (row["status"] or "") else 1,
                0 if row["rank"] == "species" else 1)

    tid = sorted(hits, key=rank_key)[0]
    row = taxa[tid]
    if "accepted" not in (row["status"] or "") and row["accepted_id"] in taxa:
        tid = row["accepted_id"]
        row = taxa[tid]

    out["matched"] = True
    out["accepted_name"] = row["name"]
    out["taxonomic_status"] = row["status"]
    out["is_synonym"] = "synonym" in (row["status"] or "")
    out["taxon_rank"] = row["rank"]

    merged: dict = {}
    for member in descendants(taxa, tid):
        for code, means in (dist.get(member) or {}).items():
            if code not in merged or _stronger(means, merged[code]):
                merged[code] = means
    out["provinces"] = merged
    out["has_distribution"] = bool(merged)
    return out


#: Establishment words, best claim first. A species is native somewhere if any
#: accepted taxon beneath it is native there, so `native` outranks the rest.
_ORDER = ("native", "", "introduced", "ephemeral", "extirpated", "excluded",
          "doubtful")


def _stronger(candidate: str, current: str) -> bool:
    def rank(word):
        word = (word or "").strip().lower()
        for i, known in enumerate(_ORDER):
            if known and known in word:
                return i
        return _ORDER.index("")
    return rank(candidate) < rank(current)


def explain(taxa: dict, dist: dict, name: str, provinces) -> str:
    """Why one species got the answer it did, as text for a person.

    Added V2.80. The real archive resolved *Amelanchier alnifolia* but left
    nine species with no distribution at all -- fireweed, stinging nettle and
    wild mint among them, which are not plants anybody doubts are in Alberta.
    A verdict that is wrong about those is a bug in this reader, not a finding
    about the flora, and the difference is only visible from inside the
    archive: which taxon the name matched, which accepted taxa hang under it,
    and what distribution rows each of those carries.

    Prints every candidate the name matched, not just the winner, because
    picking the wrong one of several is the failure this cannot otherwise
    distinguish from the archive simply having no rows.
    """
    target = _canonical(name).lower()
    hits = [tid for tid, row in taxa.items()
            if _canonical(row["name"]).lower() == target]
    out = [f"=== {name} ===",
           f"canonical: {target!r}",
           f"{len(hits)} taxa in the checklist share that binomial:"]
    for tid in sorted(hits, key=lambda t: taxa[t]["name"]):
        row = taxa[tid]
        rows = dist.get(tid) or {}
        out.append(f"  [{tid}] {row['name']}")
        out.append(f"        rank={row['rank'] or '-'} "
                   f"status={row['status'] or '-'} "
                   f"parent={row['parent'] or '-'} "
                   f"accepted_id={row['accepted_id'] or '-'}")
        out.append(f"        distribution in {'/'.join(provinces)}: "
                   f"{rows or '(none)'}")
    if not hits:
        out.append("  (none -- the checklist does not carry this binomial)")
        return "\n".join(out)

    got = lookup(taxa, dist, name, provinces)
    chosen = [tid for tid in hits
              if taxa[tid]["name"] == got["accepted_name"]]
    root = chosen[0] if chosen else None
    if root is None:
        for tid, row in taxa.items():
            if row["name"] == got["accepted_name"]:
                root = tid
                break
    out.append("")
    out.append(f"rolled up from [{root}] {got['accepted_name']}")
    kin = sorted(descendants(taxa, root), key=lambda t: taxa[t]["name"]) \
        if root else []
    out.append(f"{len(kin)} accepted taxa at or beneath it:")
    for tid in kin:
        rows = dist.get(tid) or {}
        mark = "  <-- has distribution" if rows else ""
        out.append(f"  [{tid}] {taxa[tid]['name']} "
                   f"({taxa[tid]['rank'] or '-'}) {rows or ''}{mark}")
    out.append("")
    out.append(f"result: provinces={got['provinces'] or '(none)'}")
    if not got["provinces"]:
        # The two shapes this can take, so the reader knows which they have.
        childless = len(kin) <= 1
        out.append(
            "  NOTHING FOUND. " + (
                "The roll-up found no accepted taxa beneath this one, so "
                "either the archive links infraspecific taxa to their species "
                "some other way than parentNameUsageID, or there genuinely "
                "are none."
                if childless else
                "Accepted taxa were found beneath it and none carries a row "
                "for these provinces -- so the distribution really is absent "
                "from the archive for this lineage."))
    return "\n".join(out)
