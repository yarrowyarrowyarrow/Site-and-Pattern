"""
derived_edges.py — turning genus-level host records into species-level edges.

Design principle P3 (relationships matter more than components) and P9
(uncertainty is a feature — ship ranges and confidence, never false precision)
— see docs/DESIGN_PHILOSOPHY.md.

THE PROBLEM (measured in docs/DATA_AUDIT.md §6). The 361 documented plant↔fauna
edges reached 99 of 439 plants — 22.6% — and left 56 animals connected to
nothing. Every relationship feature in the app (habitat score, food-web score,
specialist spotlight, the relationship web) therefore ran on a
three-quarters-empty graph, and reported a plant as ecologically inert when the
truth was that nobody had written its edges yet. That is a false negative
dressed as a fact.

**V2.59 shrank the hole rather than closing it.** F125's GloBI sourcing took
documented coverage to 2,800 edges over 271 of 437 species, so this module is no
longer carrying most of the graph — but 166 species still have no documented
edge, and every argument below still applies to them. Real sourcing is *meant*
to shrink what this layer fills; when it covers everything, delete this file.

THE MATERIAL. The shipped attribute files already carry genus-level host records
the graph never read: ``floral_host_genera`` on 69 bees, ``nectar_flower_genera``
on 31 lepidoptera, both with work-level citations. ``src/bee_habitat.py`` has
been making exactly this inference at runtime for one panel the whole time.

WHY THIS IS NOT INVENTION. Pollinator host records are *published at genus
resolution*. "Andrena milwaukeensis visits Symphyotrichum" is the claim the
literature makes; it does not name the eleven species in a given yard. Expanding
that record onto the catalogue's members of the genus restates the claim at the
resolution it was made, and the derived row keeps the citation of the record it
came from. It does not manufacture a new observation.

WHAT IS DELIBERATELY *NOT* DONE HERE. ``src/db/relationships.py`` carries an
explicit standing rule — "Nothing is inferred from taxonomy or 'plants like this
usually…'". Congeneric transfer (taking a documented edge on one species and
copying it to its congeners) DOES break that rule, so it is not implemented,
only reserved in the schema's ``derivation`` vocabulary. See the module note at
the bottom for why, and docs/DATA_AUDIT.md §6 Lever B for the measurement.

Qt-free, dependency-free, pure functions over plain dicts.
"""

from __future__ import annotations

from typing import Iterable, Optional

# ── Taxonomic synonymy ────────────────────────────────────────────────────────
#
# A host record written against a 20th-century flora uses the genus name of its
# day. Matching those strings literally against a catalogue on current taxonomy
# silently loses real edges: the first run of this derivation reported fireweed
# absent from the catalogue because the bee records cite *Epilobium* while the
# catalogue — correctly — carries *Chamaenerion angustifolium*.
#
# These are SEGREGATE relationships, not equivalences. *Chamaenerion* was split
# out of a broadly-circumscribed *Epilobium*; a source saying "Epilobium" in the
# older broad sense may or may not have meant the fireweeds specifically. So a
# synonym match is real but weaker than a literal one, and costs a confidence
# band (see ``_confidence``). That asymmetry is the point — it keeps a defensible
# match from being presented as an exact one.
#
# Only genera actually cited by the shipped attribute files appear here. Adding
# a pair without a citation needing it is how this table stops being checkable.
GENUS_SYNONYMS: dict[str, tuple[str, ...]] = {
    # Epilobium s.l. → the fireweed segregate (Chamaenerion, also spelled
    # Chamerion). 7 references; the catalogue has 2 Chamaenerion species.
    "Epilobium": ("Chamaenerion", "Chamerion"),
    # Senecio s.l. → Packera, which took most North American ragworts/groundsels.
    "Senecio": ("Packera",),
    # Polygonum s.l. → the smartweed and bistort segregates.
    "Polygonum": ("Persicaria", "Bistorta", "Fallopia"),
    # Aster s.l. → the North American asters, moved out wholesale. NB the
    # catalogue's *Aster alpinus* is Aster s.str. and correctly retained, so this
    # is an addition to a literal match, never a replacement for one.
    "Aster": ("Symphyotrichum", "Eurybia"),
    # Haplopappus s.l. → its segregates. Listed for completeness; none of these
    # is currently in the catalogue, so these 3 references remain a genuine gap
    # rather than a matching failure (docs/DATA_AUDIT.md §6 Lever D).
    "Haplopappus": ("Pyrrocoma", "Stenotus", "Tonestus", "Oreochrysum"),
}

#: Relationship kind produced per fauna group. Bees are recorded by *floral
#: host*, which is a pollen-sourcing relationship — oligolecty is defined by it.
#: Lepidoptera records here are explicitly nectar sources, not larval hosts:
#: larval host records are species-specific and are never derived (see below).
_BEE_KIND = "pollen"
_LEP_KIND = "nectar"


def _genus_of(scientific_name: str) -> str:
    """First word of a binomial. Empty for a blank or malformed name."""
    parts = (scientific_name or "").strip().split()
    return parts[0] if parts else ""


def build_genus_index(plants: Iterable[dict]) -> dict[str, list[dict]]:
    """Catalogue genus → the plant rows in it.

    Keyed on the genus as the catalogue spells it; synonym resolution happens on
    the *citing* side in :func:`match_genus`, so this index stays a plain fact
    about the catalogue.
    """
    index: dict[str, list[dict]] = {}
    for p in plants:
        g = _genus_of(p.get("scientific_name") or "")
        if g:
            index.setdefault(g, []).append(p)
    return index


def match_genus(cited: str, index: dict[str, list[dict]]) -> tuple[list[dict], bool]:
    """Resolve a cited genus against the catalogue.

    Returns ``(plant_rows, via_synonym)``. A literal hit wins and reports
    ``False``; otherwise the segregate genera in :data:`GENUS_SYNONYMS` are
    tried and a hit reports ``True`` so the caller can cost it a confidence
    band. Both are searched — a cited genus can legitimately match its own
    name *and* a segregate (``Aster`` does), and dropping either would lose
    real edges.
    """
    rows: list[dict] = list(index.get(cited, []))
    via_synonym = False
    for alt in GENUS_SYNONYMS.get(cited, ()):
        alt_rows = index.get(alt)
        if alt_rows:
            rows.extend(alt_rows)
            via_synonym = True
    # A literal match plus a synonym match is still a literal match for the
    # rows it found literally; the flag only downgrades when nothing literal hit.
    if cited in index:
        via_synonym = False
    return rows, via_synonym


def _confidence(n_congeners: int, *, specialist: bool, via_synonym: bool) -> str:
    """Coarse band for expanding one genus record onto ``n_congeners`` species.

    This is a statement about the EXPANSION, not about the underlying record —
    the record's own reliability is the citation's business. Never a probability
    (P9): the number that would look most precise here is the one we have least
    right to.

    The bands:

    * ``high``     — a pollen specialist's host genus (the record IS the animal's
                     defining trait, and an oligolege on a genus does use its
                     members), or a genus with ≤2 catalogue species, where there
                     is little ambiguity about which plant was meant.
    * ``moderate`` — 3–6 congeners.
    * ``low``      — 7+ congeners. The record is spread thin: *Carex* has 15 in
                     this catalogue, and "visits Carex" says much less about any
                     single one of them.

    A synonym match costs one band, because a segregate genus is a narrower thing
    than the name the source used.
    """
    if specialist or n_congeners <= 2:
        band = "high"
    elif n_congeners <= 6:
        band = "moderate"
    else:
        band = "low"
    if via_synonym:
        band = {"high": "moderate", "moderate": "low", "low": "low"}[band]
    return band


def _split_genera(field: Optional[str]) -> list[str]:
    return [g.strip() for g in (field or "").split(",") if g.strip()]


def genus_host_edges(*, plants: Iterable[dict],
                     fauna_attributes: Iterable[dict],
                     genera_field: str,
                     relationship: str,
                     default_source: str = "") -> tuple[list[dict], list[str]]:
    """Expand one attribute file's genus lists into derived edges.

    ``fauna_attributes`` rows need ``scientific_name``, the ``genera_field``
    comma list, and optionally ``pollen_specialist`` and ``source``.

    Returns ``(edges, unmatched_genera)``. The second value is not a diagnostic
    afterthought: an unmatched host genus means either a taxonomic name this
    module should know about or a plant the catalogue is missing, and both are
    findings. :func:`src.data_quality.validate_host_genus_coverage` reports them.
    """
    index = build_genus_index(plants)
    edges: list[dict] = []
    unmatched: list[str] = []
    seen: set[tuple[str, str, str]] = set()

    for attr in fauna_attributes:
        fauna_name = (attr.get("scientific_name") or "").strip()
        if not fauna_name:
            continue
        source = (attr.get("source") or default_source or "").strip()
        # ``pollen_specialist`` is a 0/1/NULL flag, not a genus name: it marks
        # the bee as an oligolege. Oligolecty is *defined* by a narrow host
        # list, so the flag qualifies every genus the record names — and in
        # practice each flagged bee names exactly one.
        specialist = bool(attr.get("pollen_specialist"))
        for cited in _split_genera(attr.get(genera_field)):
            rows, via_synonym = match_genus(cited, index)
            if not rows:
                unmatched.append(cited)
                continue
            band = _confidence(len(rows), specialist=specialist,
                               via_synonym=via_synonym)
            for p in rows:
                plant_name = p.get("common_name") or ""
                key = (plant_name, fauna_name, relationship)
                if not plant_name or key in seen:
                    continue
                seen.add(key)
                edges.append({
                    "plant": plant_name,
                    "fauna": fauna_name,
                    "relationship": relationship,
                    "derivation": "genus_host",
                    "basis": cited,
                    "confidence": band,
                    "source": source,
                })
    return edges, sorted(set(unmatched))


def bee_genus_host_edges(plants, bee_attributes):
    """Derived pollen edges from ``floral_host_genera``."""
    return genus_host_edges(plants=plants, fauna_attributes=bee_attributes,
                            genera_field="floral_host_genera",
                            relationship=_BEE_KIND)


def lepidoptera_genus_host_edges(plants, lep_attributes):
    """Derived nectar edges from ``nectar_flower_genera``.

    Note the kind: these are adult nectar sources. ``larval_host_note`` on the
    same records is NOT expanded — see the module note below.
    """
    return genus_host_edges(plants=plants, fauna_attributes=lep_attributes,
                            genera_field="nectar_flower_genera",
                            relationship=_LEP_KIND)


# ── Fauna ↔ fauna: the cuckoo bees (Lever C) ──────────────────────────────────

#: Cuckoo-bee genera whose parasitism is on a *colony* rather than on individual
#: provisioned cells. Only the cuckoo bumblebees (formerly subgenus *Psithyrus*)
#: behave this way among the genera in this catalogue.
_SOCIAL_PARASITE_GENERA = frozenset({"Bombus"})


def cleptoparasite_edges(bee_attributes: Iterable[dict]) -> list[dict]:
    """Fauna→fauna edges from ``host_genus``.

    ``host_genus`` on a bee attribute row is *not a plant* — it is the host BEE
    genus. 24 of the catalogue's bees are cleptoparasites or social parasites
    (Nomada→Andrena, Triepeolus→Melissodes, Epeolus→Colletes,
    Melecta/Xeromelecta/Zacosmia→Anthophora, cuckoo Bombus→Bombus), and under a
    plant↔fauna-only model they were permanently orphaned: no plant data would
    ever connect an animal whose defining relationship is to another animal.

    The edge points parasite → host and is expanded against the fauna actually in
    the catalogue, so a host genus nobody ships produces nothing rather than a
    dangling reference.

    Evidence is ``derived``: the *genus*-level parasitism is a documented life
    history recorded in the attribute file, but which catalogue species is the
    host of which is this module's expansion, exactly as with the plant edges.
    """
    bees = list(bee_attributes)
    by_genus: dict[str, list[dict]] = {}
    for b in bees:
        g = (b.get("genus") or _genus_of(b.get("scientific_name") or "")).strip()
        if g:
            by_genus.setdefault(g, []).append(b)

    edges: list[dict] = []
    for b in bees:
        host_genus = (b.get("host_genus") or "").strip()
        parasite = (b.get("scientific_name") or "").strip()
        if not host_genus or not parasite:
            continue
        parasite_genus = (b.get("genus") or _genus_of(parasite)).strip()
        kind = ("social_parasite" if parasite_genus in _SOCIAL_PARASITE_GENERA
                else "cleptoparasite")
        # A parasite is not a host. This matters for the cuckoo bumblebees,
        # whose host genus is their OWN genus: without this filter every cuckoo
        # Bombus is emitted as a parasite of every other cuckoo Bombus, which
        # is not a thing that happens. Candidate hosts are the genus members
        # that are not themselves parasitic.
        candidates = [h for h in by_genus.get(host_genus, [])
                      if not (h.get("host_genus") or "").strip()
                      and (h.get("scientific_name") or "").strip() != parasite]
        band = _confidence(len(candidates), specialist=False, via_synonym=False)
        for host in candidates:
            edges.append({
                "fauna_a": parasite,
                "fauna_b": (host.get("scientific_name") or "").strip(),
                "relationship": kind,
                "evidence": "derived",
                "basis": host_genus,
                "confidence": band,
                "source": (b.get("source") or "").strip(),
                "notes": (b.get("notes") or "").strip(),
            })
    return edges


# ── Why congeneric transfer is not implemented ────────────────────────────────
#
# Copying a documented edge from one species to its congeners would add a further
# 633 defensible-looking edges and take plant coverage from 45.6% to 51.3%
# (docs/DATA_AUDIT.md §6 Lever B). It is not done, for two reasons that outrank
# the number:
#
# 1. It is taxonomic inference, which src/db/relationships.py explicitly forswears
#    — "Nothing is inferred from taxonomy or 'plants like this usually…'". Lever A
#    above does not break that rule (it restates a genus-level claim at the
#    resolution the source made it); Lever B does (it invents genus-level scope
#    for a claim the source made about one species). The distinction is the whole
#    argument, and the rule is worth more than the six points of coverage.
# 2. It is unsafe precisely where the app's ecology is most load-bearing.
#    Specialist herbivory is frequently species-specific, so transferring a
#    ``larval_host`` edge across a genus is exactly the false precision P9
#    forbids. Restricting the lever to forage kinds makes it survivable, not
#    correct.
#
# The ``congeneric_forage`` value is reserved in the schema's ``derivation`` CHECK
# so that a future increment can add it without a migration — but it needs the
# author's call on the philosophy rule first, not just an implementation.
