"""
site_prep.py — what to do to the ground BEFORE anything gets planted (F43).

Design principle P8 (repair is more sophisticated than creation — the ground is
the first thing being repaired, and the prep sequence is part of the design, not
a footnote), P9 (uncertainty is a feature — the app's soil figure is usually a
*regional estimate*, and a sheet that spends the user's money off a regional
estimate is lying with numbers) and P11 (drive the user outside — most of this
is decided by a jar of soil and your hands, not by the screen) — see
docs/DESIGN_PHILOSOPHY.md.

Two things make this sheet different from generic garden advice.

**It usually tells you not to amend.** The reflex — dig in compost, add
topsoil, fertilise — is imported from vegetable gardening and is actively wrong
for a native planting. Prairie and parkland natives evolved in these soils; a
fertility spike favours the weeds that outcompete them, and rich topsoil over a
compacted base gives roots a shallow layer to circle in. The default here is
*decompact, don't enrich*, which is the well-supported restoration position and
also the one that saves the user money.

**It says how sure it is.** ``fetch_soil`` returns pH and texture from a
downloaded raster where the pack is installed, and from a *regional
approximation* otherwise — and the `source` field says which. A sheet that turns
a regional guess into "add 5 cm of compost over 88 m²" has invented precision
worth real dollars. Where the reading is regional this sheet says so and points
at the two things that settle it: a jar test you can do this afternoon, and a
lab test for the price of one shrub.

Qt-free, dependency-injectable, JSON-serialisable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

# ── Texture → what it means for planting ─────────────────────────────────────
# Keyed off the USDA classes src.property_data._texture_class emits. The advice
# is about STRUCTURE (drainage, compaction, root penetration), not fertility —
# see the module docstring on why fertility advice is mostly wrong here.
_TEXTURE_ADVICE = {
    "Clay": ("heavy clay",
             "Holds water and compacts hard. Loosen the top 20–30 cm with a "
             "fork — lever, don't turn the soil over — and plant when it "
             "crumbles rather than smears. Avoid working it wet.",
             ("dry_out", "deep_loosen")),
    "Silty clay": ("heavy clay", None, ("dry_out", "deep_loosen")),
    "Sandy clay": ("clay", None, ("deep_loosen",)),
    "Clay loam": ("clay loam",
                  "Good structure once loosened. Fork the top 15–20 cm where "
                  "it's been driven or walked on; otherwise leave it be.",
                  ("deep_loosen",)),
    "Silty clay loam": ("clay loam", None, ("deep_loosen",)),
    "Sandy clay loam": ("sandy clay loam", None, ()),
    "Loam": ("loam",
             "The easy case. Loosen only where it's compacted; no amendment "
             "needed for natives.", ()),
    "Silt loam": ("silt loam", None, ()),
    "Silt": ("silt", None, ("crust",)),
    "Sandy loam": ("sandy loam", None, ("drought",)),
    "Loamy sand": ("sandy",
                   "Drains fast and dries out fast. Do NOT dig in compost to "
                   "'improve' it — choose drought-tolerant natives instead and "
                   "mulch the surface to slow evaporation.", ("drought",)),
    "Sand": ("sand", None, ("drought",)),
}

_TEXTURE_FALLBACK = (
    "unknown texture",
    "Do the jar test below before deciding anything — texture is the single "
    "fact that changes the prep.",
    (),
)

# Mulch depth, in centimetres — a range, because it depends on the material and
# how weedy the ground was.
MULCH_DEPTH_CM = (5, 8)

#: Lawn-removal methods, with their honest time cost. Ordered by how well they
#: serve the planting, not by speed.
LAWN_METHODS = (
    {
        "key": "sheet",
        "title": "Sheet mulch (smother)",
        "detail": "Mow low, water, overlap plain cardboard with no tape or "
                  "glossy print, and top with 8–10 cm of wood chip. Cut "
                  "planting holes straight through it.",
        "timing": "Lay in fall to plant the next spring, or allow 3–6 months",
        "why": "Keeps the soil structure and the fungal network intact, and "
               "the sod feeds the bed as it breaks down. The best result for "
               "the least work — if you can wait.",
    },
    {
        "key": "sod_cut",
        "title": "Cut and lift the sod",
        "detail": "Rent a sod cutter, or slice and roll by hand. Compost the "
                  "turf face-down somewhere out of the way.",
        "timing": "Plant the same week",
        "why": "The fast route when you want to plant now. Costs you the "
               "topsoil that leaves with the sod, and exposes the weed seed "
               "bank, so expect a weedier first year.",
    },
    {
        "key": "solarize",
        "title": "Solarise",
        "detail": "Clear plastic pinned tight over mown, watered turf through "
                  "the hottest part of summer.",
        "timing": "6–10 weeks of real summer heat",
        "why": "Only worth it for tough perennial weeds like quackgrass. It "
               "cooks soil life along with the weeds, so it is the last "
               "choice, not the first.",
    },
)


@dataclass
class PrepStep:
    """One thing to do, in order, before planting."""
    order: int
    title: str
    detail: str
    when: str = ""
    #: 'measured' — from real data for this site; 'regional' — from a regional
    #: approximation; 'general' — true anywhere in the app's range. The sheet
    #: never hides which it is (P9).
    basis: str = "general"


@dataclass
class SitePrep:
    steps: list = field(default_factory=list)
    soil_line: str = ""
    soil_basis: str = "unknown"        # measured | regional | unknown
    ph_line: str = ""
    ph_mismatch: list = field(default_factory=list)   # species that won't like it
    lawn_line: str = ""
    mulch_m3_low: float = 0.0
    mulch_m3_high: float = 0.0
    caveats: list = field(default_factory=list)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["steps"] = [asdict(s) if not isinstance(s, dict) else s
                      for s in self.steps]
        return d


# ── Reading the site ─────────────────────────────────────────────────────────

def _soil_basis(site_config: dict) -> str:
    """How much the soil figures can be trusted.

    ``fetch_soil`` sets ``fallback: True`` and a ``source`` naming the regional
    atlas when it could not sample a real raster. That distinction is the whole
    basis of this sheet's honesty, so it is read explicitly rather than assumed.
    """
    soil = (site_config or {}).get("soil") or {}
    if not soil:
        # The flat fields are written by soil_flow from whatever source ran; with
        # no cached dict to check we cannot claim a measurement.
        if (site_config or {}).get("soil_texture") or \
                (site_config or {}).get("soil_ph") is not None:
            return "regional"
        return "unknown"
    if soil.get("fallback"):
        return "regional"
    return "measured"


def _texture_of(site_config: dict) -> str:
    sc = site_config or {}
    texture = (sc.get("soil_texture") or "").strip()
    if texture:
        return texture
    summary = ((sc.get("soil") or {}).get("summary") or {})
    return (summary.get("texture_class") or "").strip()


def _ph_of(site_config: dict) -> Optional[float]:
    sc = site_config or {}
    ph = sc.get("soil_ph")
    if ph is None:
        ph = ((sc.get("soil") or {}).get("summary") or {}).get("ph_top")
    try:
        return float(ph) if ph is not None else None
    except (TypeError, ValueError):
        return None


def ph_mismatches(placed_plants: list, ph: Optional[float],
                  get_plant: Optional[Callable] = None,
                  tolerance: float = 0.5) -> list[str]:
    """Species in the design whose recorded pH bracket doesn't contain ``ph``.

    Uses the same slack the plant search does (``_SOIL_PH_TOLERANCE``) — a
    regional pH estimate is coarse, and flagging a species over 0.1 of a pH unit
    would be noise dressed as advice. Species with no recorded bracket are not
    flagged: silence in the data is not evidence of a problem.
    """
    if ph is None:
        return []
    if get_plant is None:
        from src.db.plants import get_plant as _gp             # noqa: PLC0415
        get_plant = _gp
    out: list[str] = []
    seen = set()
    for p in placed_plants or []:
        pid = p.get("plant_id")
        if pid is None or pid in seen:
            continue
        seen.add(pid)
        plant = get_plant(pid) or {}
        lo, hi = plant.get("soil_ph_min"), plant.get("soil_ph_max")
        if lo is None or hi is None:
            continue
        try:
            lo, hi = float(lo), float(hi)
        except (TypeError, ValueError):
            continue
        if not (lo - tolerance) <= ph <= (hi + tolerance):
            name = plant.get("common_name") or p.get("common_name") or "?"
            out.append(f"{name} (prefers pH {lo:g}–{hi:g})")
    return sorted(out)


# ── The sheet ────────────────────────────────────────────────────────────────

def build_site_prep(site_config: dict, placed_plants: Optional[list] = None, *,
                    bed_area_m2: float = 0.0,
                    lawn_summary: Optional[dict] = None,
                    get_plant: Optional[Callable] = None) -> SitePrep:
    """Assemble the do-this-first sheet for a site and its design."""
    sc = site_config or {}
    basis = _soil_basis(sc)
    texture = _texture_of(sc)
    ph = _ph_of(sc)
    prep = SitePrep(soil_basis=basis)

    label, advice, flags = _TEXTURE_ADVICE.get(texture, (None, None, None)) \
        if texture else (None, None, None)
    if label is None:
        label, advice, flags = _TEXTURE_FALLBACK
    if advice is None:
        # A class that shares its advice with a neighbour (e.g. Silty clay →
        # heavy clay): reuse the sibling's text rather than duplicating it.
        for _cls, (lbl, adv, _f) in _TEXTURE_ADVICE.items():
            if lbl == label and adv:
                advice = adv
                break
    prep.soil_line = (f"{texture} — {label}" if texture
                      else "Soil texture not known for this site yet")

    order = 1

    # 1. Removing what's there. This is the step that actually converts lawn to
    #    habitat, so it leads (P8).
    lawn_m2 = float((lawn_summary or {}).get("lawn_remaining_m2") or 0.0)
    converted_m2 = float((lawn_summary or {}).get("converted_m2") or 0.0)
    area = bed_area_m2 or (lawn_m2 + converted_m2)
    if lawn_m2 > 0 or converted_m2 > 0 or bed_area_m2 > 0:
        prep.lawn_line = (
            f"About {area:.0f} m² to clear"
            if area > 0 else "Area not measured yet")
        for method in LAWN_METHODS:
            prep.steps.append(PrepStep(
                order=order, title=f"Clear the ground — {method['title']}",
                detail=f"{method['detail']}  {method['why']}",
                when=method["timing"], basis="general"))
            order += 1
    else:
        prep.steps.append(PrepStep(
            order=order,
            title="Decide how the existing cover comes off",
            detail="Draw your conversion zones on the map first (Site → "
                   "Features) and this sheet will size the job. The three "
                   "methods are sheet mulch, cutting the sod, and solarising.",
            basis="general"))
        order += 1

    # 2. Structure, not fertility — the sheet's contrarian core.
    prep.steps.append(PrepStep(
        order=order,
        title="Loosen compaction — but do NOT enrich",
        detail=(f"{advice}  The instinct to dig in compost and topsoil comes "
                f"from vegetable growing and works against a native planting: "
                f"a fertility spike favours the weeds that outcompete young "
                f"natives, and these species are adapted to the soil you "
                f"already have. Compaction is the real enemy, not poverty."),
        when="Right before planting, when the soil is moist but not wet",
        basis="regional" if texture and basis != "measured" else
              ("measured" if texture else "general")))
    order += 1

    if "drought" in (flags or ()):
        prep.steps.append(PrepStep(
            order=order, title="Sandy ground — choose, don't amend",
            detail="Adding organic matter to sand is a treadmill; it burns off "
                   "in a season or two. Lean on drought-tolerant natives and "
                   "surface mulch instead, and water deeply through the first "
                   "summer only.",
            basis="general"))
        order += 1
    if "dry_out" in (flags or ()):
        prep.steps.append(PrepStep(
            order=order, title="Never work heavy clay wet",
            detail="Squeeze a handful: if it ribbons and smears, wait. Working "
                   "clay wet destroys its structure for years, and no amount "
                   "of amendment undoes it.",
            when="Test on the day, every day you plan to dig",
            basis="general"))
        order += 1

    # 3. Mulch — the one material worth buying, sized as a range.
    if area > 0:
        lo = area * MULCH_DEPTH_CM[0] / 100.0
        hi = area * MULCH_DEPTH_CM[1] / 100.0
        prep.mulch_m3_low, prep.mulch_m3_high = round(lo, 1), round(hi, 1)
        prep.steps.append(PrepStep(
            order=order, title="Mulch the surface after planting",
            detail=(f"{MULCH_DEPTH_CM[0]}–{MULCH_DEPTH_CM[1]} cm of wood chip "
                    f"over {area:.0f} m² — roughly {lo:.1f}–{hi:.1f} m³. Keep "
                    f"it off the stems. Arborist chip is usually free for the "
                    f"asking; skip dyed bark and landscape fabric, which stops "
                    f"the self-seeding this design depends on."),
            when="Immediately after planting, then top up every 2–3 years",
            basis="measured"))
        order += 1

    # 4. Ground-nesting bees need bare ground — the step every mulch guide
    #    forgets, and the app has the data to know it matters here.
    prep.steps.append(PrepStep(
        order=order, title="Leave some ground bare",
        detail="About 70% of native bees nest in bare, undisturbed soil. Leave "
               "a sunny, unmulched patch — even a square metre on a south-facing "
               "edge — and do not landscape-fabric it. Analysis → Bees names the "
               "species this serves in your design.",
        basis="general"))
    order += 1

    # ── pH ───────────────────────────────────────────────────────────────────
    if ph is not None:
        prep.ph_line = f"pH {ph:.1f}"
        prep.ph_mismatch = ph_mismatches(placed_plants or [], ph, get_plant)
        if prep.ph_mismatch:
            n = len(prep.ph_mismatch)
            prep.steps.append(PrepStep(
                order=order,
                title=f"{n} species may not suit this pH"
                      if n != 1 else "One species may not suit this pH",
                detail=("Swap them rather than treating the soil: shifting a "
                        "whole bed's pH is expensive, temporary, and works "
                        "against the plants that do suit it. "
                        + "; ".join(prep.ph_mismatch[:6])
                        + ("…" if len(prep.ph_mismatch) > 6 else "")),
                basis="regional" if basis != "measured" else "measured"))
            order += 1
    else:
        prep.ph_line = "pH not known for this site yet"

    # ── Honesty about the numbers above ──────────────────────────────────────
    if basis == "regional":
        prep.caveats.append(
            "The soil figures above are a REGIONAL approximation, not a "
            "measurement of your yard — they can be a full pH unit and a "
            "texture class out. Before spending money on amendment: do the jar "
            "test (a handful of soil in a jar of water, shaken and left to "
            "settle into sand/silt/clay bands overnight), and consider a lab "
            "test — about the price of one shrub, and it settles pH, texture "
            "and organic matter together.")
    elif basis == "unknown":
        prep.caveats.append(
            "No soil data for this site yet. Drop a property pin on the Site "
            "tab to fetch an estimate, and do the jar test — texture is the "
            "one fact that changes everything above.")
    else:
        prep.caveats.append(
            "Soil figures are sampled from the Gridded Soil Landscapes of "
            "Canada for your location — real data, but still a landscape-scale "
            "average. A jar test on your own ground takes ten minutes and "
            "beats it.")
    prep.caveats.append(
        "Everything here is about STRUCTURE, not fertility. If you take one "
        "thing outside: loosen compaction, mulch the surface, and leave the "
        "soil chemistry alone.")
    return prep


def render_prep_text(prep: SitePrep) -> str:
    """Plain-text section for the Planting Plan export."""
    lines = ["SITE PREP — DO THIS FIRST", "=" * 44, ""]
    lines.append(f"Soil:  {prep.soil_line}")
    if prep.ph_line:
        lines.append(f"       {prep.ph_line}")
    if prep.lawn_line:
        lines.append(f"Area:  {prep.lawn_line}")
    if prep.mulch_m3_low:
        lines.append(f"Mulch: {prep.mulch_m3_low:.1f}–{prep.mulch_m3_high:.1f} m³ "
                     f"of wood chip")
    lines.append("")
    for step in prep.steps:
        lines.append(f"{step.order}. {step.title}")
        for chunk in _wrap(step.detail, 68):
            lines.append(f"   {chunk}")
        if step.when:
            lines.append(f"   When: {step.when}")
        lines.append("")
    if prep.caveats:
        lines.append("HOW SURE IS THIS?")
        lines.append("-" * 44)
        for caveat in prep.caveats:
            for chunk in _wrap(caveat, 68):
                lines.append(f"  {chunk}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = (text or "").split(), [], ""
    for word in words:
        if cur and len(cur) + len(word) + 1 > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]
