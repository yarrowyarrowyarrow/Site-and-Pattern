"""
src/pattern_language.py — communities as Christopher Alexander patterns (F4).

Design principle P1 (a generative pattern language — communities as reusable,
site-responsive patterns) and P7 (generalist knowledge: the architect's pattern
language carried into ecological design) — see docs/DESIGN_PHILOSOPHY.md.

A plant community is presented the way *A Pattern Language* presents a pattern:

    Problem → Context → Forces → Solution → Related patterns

The editorial halves (problem / context / forces / solution) are *authored* and
stored on the ``polycultures`` row (seeded in :mod:`src.db.polycultures`). The
*measured* halves — the site envelope (sun, moisture, ecoregion, zone, size) and
the ecological forces (keystone / host / food-web / bloom / nitrogen) — are
derived **here, live, from the member plants**, so they stay true as the
catalogue grows and reinforce the same relationships the Habitat Value Score
teaches. Related patterns come from the ``parent_id`` hierarchy and the shared
centre plant.

Pure Python: ``get_plant`` and the habitat score are reached through the DB but
both are injectable, so the builder is unit-testable and Qt-free. The GUI
(:mod:`src.polyculture_panel`) renders :func:`pattern_card_html`; a future PDF
exporter can reuse the same :func:`build_pattern` result.
"""

from __future__ import annotations

import html
from typing import Callable, Optional

# Member-data → human language ---------------------------------------------------

_SUN_ORDER = ["full_sun", "partial_shade", "full_shade"]
_SUN_LABEL = {"full_sun": "full sun", "partial_shade": "part shade",
              "full_shade": "full shade"}

_WATER_ORDER = ["low", "medium", "high"]
_WATER_LABEL = {"low": "dry", "medium": "moist", "high": "wet"}

_ECOREGION_LABEL = {
    "aspen_parkland": "aspen parkland",
    "mixedgrass_prairie": "mixedgrass prairie",
    "fescue_foothills": "fescue foothills",
    "boreal_mixedwood": "boreal mixedwood",
    "riparian": "riparian",
    "wet_meadow": "wet meadow",
    "subalpine_montane": "subalpine/montane",
}

_MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _first_sentence(text: str) -> str:
    """First sentence of ``text`` (fallback when no authored problem exists)."""
    text = (text or "").strip()
    if not text:
        return ""
    idx = text.find(". ")
    return text[:idx + 1] if idx != -1 else text


def _range_phrase(values: set, order: list, labels: dict) -> str:
    """Compress a set of ordinal values into a 'low to high' phrase."""
    present = [v for v in order if v in values]
    if not present:
        return ""
    lo, hi = present[0], present[-1]
    return labels[lo] if lo == hi else f"{labels[lo]} to {labels[hi]}"


def _month_span(months: list) -> str:
    """Summarise bloom months (4–10) as an 'Apr–Sep' span."""
    months = [m for m in (months or []) if 1 <= m <= 12]
    if not months:
        return ""
    lo, hi = min(months), max(months)
    return _MONTH_ABBR[lo] if lo == hi else f"{_MONTH_ABBR[lo]}–{_MONTH_ABBR[hi]}"


def _context_facts(plant_rows: list, footprint_m: float) -> list[str]:
    """Derived site-envelope bullets from the member plant rows."""
    facts: list[str] = []
    suns = {(r.get("sun_requirement") or "").strip() for r in plant_rows}
    waters = {(r.get("water_needs") or "").strip() for r in plant_rows}

    sun = _range_phrase(suns, _SUN_ORDER, _SUN_LABEL)
    if sun:
        facts.append(sun[0].upper() + sun[1:])
    moisture = _range_phrase(waters, _WATER_ORDER, _WATER_LABEL)
    if moisture:
        facts.append(moisture)

    ecoregions: list[str] = []
    for r in plant_rows:
        for tag in (r.get("ab_ecoregion") or "").split(","):
            tag = tag.strip()
            label = _ECOREGION_LABEL.get(tag)
            if label and label not in ecoregions:
                ecoregions.append(label)
    if ecoregions:
        facts.append(", ".join(ecoregions[:3]))

    zone = _zone_window(plant_rows)
    if zone:
        facts.append(zone)

    if footprint_m and footprint_m > 0:
        facts.append(f"~{footprint_m:.0f} m across" if footprint_m >= 1.5
                     else "small patch")

    heights = [float(r["mature_height_meters"]) for r in plant_rows
               if r.get("mature_height_meters")]
    if heights:
        tall = max(heights)
        facts.append(f"to {tall:.0f} m tall" if tall >= 1.5
                     else "stays low (<1.5 m)")

    natives = [r for r in plant_rows if r.get("native_to_alberta")]
    if plant_rows:
        pct = round(100 * len(natives) / len(plant_rows))
        if pct >= 100:
            facts.append("all Alberta natives")
        elif pct:
            facts.append(f"{pct}% native")
    return facts


def _zone_window(plant_rows: list) -> str:
    """Hardiness window the whole community shares (max of mins → min of maxes)."""
    mins = [int(r["hardiness_zone_min"]) for r in plant_rows
            if r.get("hardiness_zone_min") is not None]
    maxs = [int(r["hardiness_zone_max"]) for r in plant_rows
            if r.get("hardiness_zone_max") is not None]
    if not mins or not maxs:
        return ""
    lo, hi = max(mins), min(maxs)
    if lo > hi:               # no clean shared window
        return f"Zone {max(mins)}"
    return f"Zone {lo}" if lo == hi else f"Zone {lo}–{hi}"


def _nitrogen_fixers(members: list) -> int:
    """Count members tagged as nitrogen fixers (function, layer, or legacy role)."""
    n = 0
    for m in members:
        funcs = m.get("functions") or []
        if ("nitrogen_fixer" in funcs
                or m.get("layer") == "nitrogen_fixer"
                or m.get("role") == "nitrogen_fixer"):
            n += 1
    return n


def _forces_facts(members: list, *, connection=None) -> list[str]:
    """Derived ecological forces — the *why these plants work together* line.

    Reuses :func:`src.habitat_score.compute_habitat_score` over the members so
    the pattern card and the Habitat tab agree, and so the F3 food-web (Tallamy
    chain) status surfaces here too. Best-effort: a DB hiccup yields the
    non-ecological forces (nitrogen fixers, member count) only."""
    facts: list[str] = []
    n_fix = _nitrogen_fixers(members)

    try:
        from src.habitat_score import compute_habitat_score
        placed = [{"plant_id": m["plant_id"]} for m in members
                  if m.get("plant_id") is not None]
        hs = compute_habitat_score(placed, [], connection=connection)
    except Exception:  # noqa: BLE001 — forces are a nicety, never break the card
        hs = None

    if hs is not None:
        if hs.keystone_species:
            facts.append(f"{len(hs.keystone_species)} keystone "
                         f"species anchor the food web")
        fw = hs.food_web or {}
        status = fw.get("status")
        if status == "complete":
            facts.append("hosts caterpillars and the birds that eat them "
                         "(food web complete)")
        elif status == "no_birds":
            n = fw.get("n_caterpillars") or len(hs.host_species)
            facts.append(f"hosts caterpillars ({n} species) but little bird "
                         f"food yet")
        elif status == "no_hosts":
            facts.append("feeds birds but no caterpillar host plants yet")
        span = _month_span(hs.bloom_months)
        if span:
            gap = " (with gaps)" if hs.gap_months else ""
            facts.append(f"nectar {span}{gap}")
        if len(hs.layers_present) >= 3:
            facts.append(f"{len(hs.layers_present)} vegetation layers")

    if n_fix:
        facts.append(f"{n_fix} nitrogen-fixer{'s' if n_fix != 1 else ''} "
                     f"feed{'s' if n_fix == 1 else ''} the planting")
    return facts


def _related(polyculture: dict, all_communities: Optional[list]) -> list[dict]:
    """Related patterns from the parent_id hierarchy + shared centre plant.

    Variations of this pattern, its base pattern (if this is a variation),
    sibling variations, and other communities anchored on the same centre plant.
    """
    me = polyculture.get("id")
    parent_id = polyculture.get("parent_id")
    center = polyculture.get("center_plant_id")
    rel: list[dict] = []
    seen = {me}
    for c in all_communities or []:
        cid = c.get("id")
        if cid in seen:
            continue
        relation = None
        if c.get("parent_id") == me:
            relation = "Variation"
        elif parent_id is not None and cid == parent_id:
            relation = "Base pattern"
        elif parent_id is not None and c.get("parent_id") == parent_id:
            relation = "Variation"
        elif center is not None and c.get("center_plant_id") == center:
            relation = "Same anchor plant"
        if relation:
            rel.append({"id": cid, "name": c.get("name") or "—",
                        "relation": relation})
            seen.add(cid)
    return rel


def build_pattern(polyculture: dict, *,
                  all_communities: Optional[list] = None,
                  get_plant: Optional[Callable] = None,
                  connection=None) -> dict:
    """Assemble the Alexander pattern view of ``polyculture``.

    ``polyculture`` is a :func:`src.db.polycultures.get_polyculture_by_id`
    result (carrying ``members`` and the authored problem/context/forces/
    solution). ``all_communities`` (a
    ``get_all_polycultures(top_level_only=False)`` list) drives the related
    patterns; ``get_plant`` is injectable for tests.

    Returns a dict with the five sections plus the derived ``context_facts`` and
    ``forces_facts`` lists and ``related``.
    """
    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp

    members = polyculture.get("members") or []
    description = polyculture.get("description") or ""

    plant_rows: list = []
    for m in members:
        pid = m.get("plant_id")
        if pid is None:
            continue
        row = get_plant(pid)
        if row:
            plant_rows.append(row)

    try:
        from src.db.polycultures import community_natural_radius
        footprint = community_natural_radius(polyculture) * 2.0
    except Exception:  # noqa: BLE001
        footprint = 0.0

    problem = (polyculture.get("problem") or "").strip() or _first_sentence(description)
    solution = (polyculture.get("solution") or "").strip() or description

    return {
        "id": polyculture.get("id"),
        "name": polyculture.get("name") or "—",
        "center": polyculture.get("center_plant_name") or "",
        "problem": problem,
        "context": (polyculture.get("context") or "").strip(),
        "context_facts": _context_facts(plant_rows, footprint),
        "forces": (polyculture.get("forces") or "").strip(),
        "forces_facts": _forces_facts(members, connection=connection),
        "solution": solution,
        "n_members": len(members),
        "related": _related(polyculture, all_communities),
    }


# ── Presentation (Qt-free HTML; QTextBrowser renders it) ────────────────────────

def _facts_html(facts: list[str]) -> str:
    if not facts:
        return ""
    joined = " · ".join(html.escape(f) for f in facts)
    return (f'<div style="color:#7fae7f; font-size:11px; margin:1px 0 6px 0;">'
            f'{joined}</div>')


def _section_html(heading: str, body: str, facts_html: str = "") -> str:
    parts = [f'<p style="margin:8px 0 1px 0;"><b style="color:#cfe8cf;">'
             f'{html.escape(heading)}</b></p>']
    if body:
        parts.append(f'<p style="margin:1px 0;">{html.escape(body)}</p>')
    if facts_html:
        parts.append(facts_html)
    return "".join(parts)


def pattern_card_html(pattern: dict, *, include_header: bool = True) -> str:
    """Render a :func:`build_pattern` result as the panel's pattern card.

    Related patterns are ``<a href="community:{id}">`` links so the panel can
    navigate to them (educational cross-linking between patterns).

    ``include_header`` controls the leading name + "Anchored on …" line. The GUI
    shows those separately above the members list and passes ``False`` so the
    card starts at Problem; the default ``True`` keeps the standalone card (e.g.
    a future PDF export) and the existing tests intact."""
    out: list[str] = []
    if include_header:
        name = html.escape(pattern.get("name") or "—")
        out.append(f'<h3 style="margin:2px 0 2px 0; color:#a5d6a7;">{name}</h3>')
        center = pattern.get("center")
        if center:
            out.append(f'<p style="margin:0 0 4px 0; color:#9e9e9e; '
                       f'font-size:11px;">Anchored on {html.escape(center)} · '
                       f'{pattern.get("n_members", 0)} plants</p>')

    out.append(_section_html("Problem", pattern.get("problem", "")))
    out.append(_section_html("Context (Where & When to Plant)",
                             pattern.get("context", ""),
                             _facts_html(pattern.get("context_facts") or [])))
    out.append(_section_html("Forces (Why These Plants Work Together)",
                             pattern.get("forces", ""),
                             _facts_html(pattern.get("forces_facts") or [])))
    out.append(_section_html("Solution", pattern.get("solution", "")))

    related = pattern.get("related") or []
    if related:
        links = " · ".join(
            f'<a href="community:{r["id"]}" style="color:#90caf9; '
            f'text-decoration:none;">{html.escape(r["name"])}</a> '
            f'<span style="color:#9e9e9e; font-size:10px;">'
            f'({html.escape(r["relation"])})</span>'
            for r in related
        )
        out.append(_section_html("Related patterns", ""))
        out.append(f'<p style="margin:1px 0;">{links}</p>')
    return "".join(out)
