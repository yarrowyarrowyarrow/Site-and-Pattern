"""
data_quality.py — Schema validation for the shipped plant JSON files.

Validates ``data/plants_master.json`` and ``data/garden_plants.json``
against the enum/range/reference invariants the rest of the app
implicitly relies on. Catches the class of bug where a hand-edit typo
("Augst" instead of "Aug", "moderete" instead of "moderate") silently
breaks a score because the parser sees an unrecognized value and
falls back to a default.

Design notes:
  * Pure Python, no PyQt6 — so the test suite (and any CI runner)
    can call ``validate_all()`` without a display.
  * Source of truth for the canonical permaculture_uses tags is
    ``src.db.plants._USE_DEFINITIONS`` — imported, not duplicated.
  * Source of truth for the canonical ecoregion keys is
    ``src.ecoregion`` — which itself reads them from the shipped polygon
    file plus the moisture-niche constant (V2.38), so adding a region to
    ``data/ecoregions_canada.geojson`` widens what this accepts and there
    is nothing else to remember. It used to be a list in
    ``src/plant_panel.py`` read out via ``ast.literal_eval`` on the source
    text, because that module imports PyQt6.
  * The enum allowlists for plant_type / water_needs / etc. match the
    set of values that *currently* appear in the data, not an
    aspirational tight set. This validator's job is to freeze the
    current shape so new typos can't slip in. Tightening (e.g.
    collapsing ``moderate`` → ``medium``) is a separate cleanup.

The CLI wrapper at ``scripts/check_plant_data.py`` exposes this as a
standalone command. The test wrapper at ``tests/test_data_quality.py``
asserts ``validate_all()`` returns no errors against the live data.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable

from src.plant_conditions import condition_tokens

# Condition fields that may hold a comma-delimited list of enum values when a
# plant tolerates a range of conditions (V1.84). Each token is validated
# against the enum independently.
_MULTI_VALUE_ENUM_FIELDS = {"sun_requirement", "water_needs"}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR     = PROJECT_ROOT / "data"

# ── Two output channels: errors vs warnings ─────────────────────────────────
#
# The validator distinguishes between hard failures (typos / out-of-range
# numbers / missing required fields — things the running app actively
# misbehaves on) and soft drift (data debt that's known and gracefully
# handled). Tests assert ``errors == []``; warnings surface so the
# cleanup backlog stays visible without breaking CI.
#
# The split was calibrated against the V1.31 shipped data:
#   * ``native_to_alberta`` has ``'1?'`` markers handled by
#     ``polyculture_panel._truthy_int`` — warning, not error.
#   * ``permaculture_uses`` carries informal tags like ``overstory`` and
#     ``food_forest`` that aren't (yet) in ``_USE_DEFINITIONS`` — warning.
#     Future release can promote them to canonical entries and the
#     warning disappears.
#   * Two scientific-name duplicates exist with ``NOTE: DUPLICATE ENTRY``
#     and ``FLAG:`` markers in the record's own notes — warning.
#
# Promoting a warning to an error in a future release means cleaning the
# matching data first; doing it here would expand V1.34's scope past
# "dev infrastructure".

# ── Strict enum allowlists (drift here is an ERROR) ─────────────────────────
# These are the fields where the running app does NOT have a known
# escape hatch for unexpected values. A typo here silently mis-parses.

SUN_REQUIREMENTS  = {"full_sun", "partial_shade", "full_shade"}
WATER_NEEDS       = {"low", "medium", "high", "moderate"}
PLANT_TYPES       = {"tree", "shrub", "herb", "wildflower", "groundcover",
                     "vine", "grass", "sedge", "rush", "fern", "aquatic"}
LIFE_CYCLES       = {"perennial", "annual", "biennial"}
DECIDUOUSNESS     = {"deciduous", "evergreen", "herbaceous", "semi-evergreen"}
GROWTH_RATES      = {"slow", "moderate", "fast"}
# Safety + spread (schema v18). Empty string = unassessed, always allowed.
TOXICITY_LEVELS   = {"none", "low", "high"}
SPREAD_HABITS     = {"clumping", "slow_spreader",
                     "aggressive_rhizomatous", "self_seeding"}
# Sourcing (schema v19). Empty string = unassessed, always allowed.
AVAILABILITY_CLASSES = {"big_box", "garden_centre", "native_specialist",
                        "seed_or_plug", "rare"}
# Flower form (schema v31) — drives the 3D viewer's flower sprite. 'none' = no
# showy flower; empty string is also tolerated (treated as 'none').
FLOWER_FORMS      = {"daisy", "rays", "spike", "plume", "umbel", "globe",
                     "cluster", "bell", "trumpet", "cattail", "pea", "whorl",
                     "star", "cross", "lily", "none"}
# Fruit SHAPE (schema v49) — the companion to fruit_color, authored in
# scripts/seed_fruit_morphology.py. Empty on dry-fruited species, which draw no
# fruit at all; '' is therefore valid and means "nothing to draw".
FRUIT_FORMS       = {"berry", "strig", "raceme", "cherry", "pome", "hip",
                     "strawberry", "aggregate", "flat_cluster", ""}
# Botanical morphology (schema v47) — authored for the woody species in
# scripts/seed_woody_morphology.py; empty everywhere else, hence no "missing"
# error, only a check that what IS there is spelled canonically.
LEAF_SHAPES       = {"needle", "awl", "scale", "linear", "lanceolate",
                     "elliptic", "ovate", "obovate", "orbicular", "cordate",
                     "lobed", "trifoliate", "compound_pinnate",
                     "compound_palmate",
                     # Herbaceous profiles (v48): the woody set had no way to
                     # say "spoon-shaped basal rosette" (pussytoes, fleabane),
                     # "kidney-shaped" (violets, marsh marigold), "arrowhead"
                     # (balsamroot, arrowhead), "deeply cut but not compound"
                     # (prairie crocus, thistle) or "twice-divided" (yarrow,
                     # meadow rue) — between them a large share of the flora.
                     "spatulate", "reniform", "sagittate", "pinnatifid",
                     "bipinnate"}
LEAF_ARRANGEMENTS = {"alternate", "opposite", "whorled", "fascicled", "basal"}
BRANCHING_HABITS  = {"excurrent", "decurrent", "multi_stem", "suckering",
                     "arching", "prostrate", "rosette"}
# Herbaceous habit (schema v48). Kept separate from BRANCHING_HABITS, which
# describes woody architecture: a plant has one or the other, not both. The
# first seven mirror the viewer's herb archetypes (03-herbs.js HERB_FORMS) so
# the data can select the 3D form directly instead of a genus table guessing it.
GROWTH_FORMS      = {"erect", "ferny", "rosette", "clump", "grassy", "mat",
                     "fern", "vining", "tussock", "emergent", "floating",
                     "cushion", "succulent", "sprawling"}
# Surface character (schema v52). What a species' bark and foliage look like
# close up — the 3D viewer's procedural grain (html/scene3d/01b-surface.js).
# Empty is meaningful and common: a per-genus bark default and a matte leaf.
BARK_TEXTURES     = {"smooth", "furrowed", "papery", "shaggy", "scaly"}
LEAF_SURFACES     = {"matte", "glossy", "pubescent", "glaucous"}
# The graminoid field mark (schema v52) — separate from flower_form, which
# stays 'plume' for every grass because that column feeds pollinator logic.
INFLORESCENCE_FORMS = {"turkey_foot", "open_panicle", "contracted_spike",
                       "nodding_raceme", "one_sided_raceme", "bristly",
                       "sedge_cluster", "rush_umbel", "cattail_spike"}

# Flower morphology (schema v53). These four lived in
# scripts/seed_flower_morphology.py — the only place that wrote them — which
# meant the data-quality gate never checked them and the tuning bench had to
# retype them into its HTML. They belong here with the rest of the enums: one
# definition, validated on every record, and served to the bench over the API.
# Drawn, term by term, in html/botany/diagrams.js. Ordered tuples rather than
# sets — membership tests read the same, but these four are shown to a person
# in a dropdown and in a comparison chart, and the order is the order the terms
# make sense in (one flower → many, simple → compound) rather than alphabetical.
FLOWER_ARCHITECTURES = ("solitary", "raceme", "spike", "panicle", "corymb",
                        "umbel", "head", "cyme", "whorl")
FLOWER_SYMMETRIES = ("radial", "bilateral")
PETAL_SHAPES      = ("narrow", "oval", "notched", "tubular", "lipped")
STEM_BRANCHINGS   = ("unbranched", "branched_above", "branched_throughout")

# ── Fauna morphology (schema v58, V2.36) ────────────────────────────────────
# The animals were where the plants were before V2.33: every creature's look was
# computed in src/scene_wildlife.py from SUBSTRINGS OF ITS COMMON NAME — a
# 12-genus table and seventeen `if "azure" in name` tests — so 69 bees collapsed
# into 12 appearances (29 bumblebees pixel-identical) and 31 lepidoptera into 16
# (Polyphemus, Cecropia and Isabella Tiger Moth rendered as one moth). None of
# it was in the database, sourced, or correctable without editing code.
#
# Ordered tuples for the same reason as the flower four: these are shown to a
# person in a dropdown and in a comparison chart, and the order teaches.
# Drawn, term by term, in html/botany/fauna.js.

# How a lepidopteran flies. A real, documented character — and the one that
# drives the 3D flight animation (html/scene3d/07-wildlife.js _FLIGHT_STYLE),
# so recording it makes a skipper dart and a monarch sail instead of every
# species sharing one generic wobble.
FLIGHT_STYLES     = ("fluttery", "erratic", "darting", "gliding", "bobbing",
                     "hovering")
# Wing outline. `tailed` is the swallowtail mark; `falcate` the hooked forewing
# of the marbles and some sphinxes.
WING_SHAPES       = ("rounded", "broad", "narrow", "angular", "falcate", "tailed")
# What is ON the wing. Ordered plain → most structured.
WING_PATTERNS     = ("plain", "veined", "spotted", "banded", "checkered",
                     "mottled", "eyespots")
# How the wings are held at rest — behavioural AND visual, and the thing you
# actually see on a perched animal. Butterflies close them over the back
# (`wings_up`), most moths tent or wrap them, satyrs bask flat.
RESTING_POSTURES  = ("wings_up", "wings_flat", "tent", "wrapped", "swept")

# Bee body plan. Mirrors assetlib/fauna_variants.BEE_VARIANTS — the mesh the
# viewer picks — with `leafcutter` kept because a Megachile's broad head and
# flat scopa-bearing abdomen is what a non-specialist actually notices.
BEE_BUILDS        = ("round", "stout", "slender", "leafcutter")
# Where a female carries pollen. Diagnostic and cheap to see: Megachile carry it
# under the abdomen, most others on the hind leg, cuckoo bees not at all —
# which is *why* they are hairless, so this doubles as the cuckoo field mark.
SCOPA_POSITIONS   = ("hind_leg", "abdomen", "none")
WING_TINTS        = ("clear", "smoky", "amber")

# Bumblebee colour banding — the single highest-value field in this whole set.
# 29 of the catalogue's 69 bees are Bombus and they currently render as one
# animal; every bumblebee key in existence works by naming the colour of the
# thorax and each abdominal tergite in turn, so this is both what makes them
# distinguishable and exactly what you are already reading off the page.
#
# `band_pattern` is a comma-separated list of these tokens, thorax first then
# T1…T6 (e.g. "yellow,yellow,yellow,black,orange,orange,black"). Named tokens
# rather than hex because that is how the keys are written; the token→hex table
# lives beside them so there is one definition.
BAND_COLOURS = ("black", "yellow", "orange", "red", "white", "buff", "brown",
                "grey")
BAND_COLOUR_HEX = {
    "black":  "#26211c",
    "yellow": "#f2c12e",
    "orange": "#d8722a",
    "red":    "#b5462e",
    "white":  "#e8e4da",
    "buff":   "#d8cbb0",
    "brown":  "#6b5138",
    "grey":   "#9a9186",
}
# thorax + T1..T6. Fewer is allowed (many keys only describe as far as T4);
# more is a typo.
BAND_SEGMENTS_MAX = 7


def band_pattern_tokens(value) -> list:
    """`band_pattern` as a list of colour tokens, or [] if unset.

    Split-and-strip in one place so the seeder, the gate, the bench and the
    viewer cannot disagree about whether spaces are allowed.
    """
    return [t.strip().lower() for t in str(value or "").split(",") if t.strip()]


# ── Soft enum allowlists (drift here is a WARNING) ──────────────────────────

GROWTH_CURVES     = {"slow_start", "steady", "fast_early"}
# Calendar status — matches the schema.sql CHECK on planting_calendar.status.
CALENDAR_STATUS   = {"dormant", "start_indoors", "direct_sow", "transplant",
                     "growing", "harvest", "pruning"}
# native_to_alberta is documented as 0/1 but the data carries '1?' for
# uncertain-native records; the code handles it via _truthy_int.
NATIVE_TO_ALBERTA = {0, 1, "0", "1", "1?", "0?"}

# Canadian province/territory codes accepted in the native_provinces field
# (V2.15). The app's coverage is the prairies (AB, SK) with neighbours allowed
# for provenance completeness.
PROVINCE_CODES = {"AB", "SK", "MB", "BC", "ON", "QC", "NB", "NS", "PE", "NL",
                  "YT", "NT", "NU"}

# Month tokens for bloom_period / fruit_period. Short forms are the
# preferred output of the existing parser at
# src/analysis_panel.py:759 et al; long forms are accepted on input.
_MONTH_SHORT = {"Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"}
_MONTH_LONG  = {"January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"}
MONTH_TOKENS = _MONTH_SHORT | _MONTH_LONG

_CALENDAR_KEYS = [f"cal_{m.lower()}" for m in
                  ("jan", "feb", "mar", "apr", "may", "jun",
                   "jul", "aug", "sep", "oct", "nov", "dec")]


# ── Canonical references loaded from other modules ──────────────────────────

def _load_use_keys() -> set[str]:
    """Canonical permaculture_uses tags from src/db/plants.py."""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from src.db.plants import _USE_DEFINITIONS  # noqa: WPS433
    return {key for key, *_ in _USE_DEFINITIONS}


def _load_ecoregion_keys() -> set[str]:
    """The canonical ecoregion keys — the vocabulary this validator accepts.

    Read from ``src.ecoregion``, which is Qt-free and reads them from the
    shipped polygon file plus the moisture-niche constant (V2.38). Adding a
    region to ``data/ecoregions_canada.geojson`` therefore widens what the
    validator accepts, with nothing else to remember.

    Before V2.38 the vocabulary lived in ``plant_panel`` and this had to
    AST-parse that file rather than import PyQt6 to read a list of strings.
    That parser is **gone**, and deliberately: it matched a list literal, and
    ``_ECOREGION_CHOICES`` is now a comprehension, so it would have quietly
    returned nothing — and an empty vocabulary makes this validator accept
    every ecoregion token in the catalogue without complaint. A silent pass is
    worse than a loud failure in a data gate.
    """
    from src.ecoregion import ecoregion_keys            # noqa: PLC0415
    keys = set(ecoregion_keys())
    if not keys:
        raise RuntimeError(
            "No ecoregion vocabulary — data/ecoregions_canada.geojson is "
            "missing or unreadable. Refusing to validate against an empty "
            "key set, which would accept anything.")
    return keys


# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_month_period(s: str) -> tuple[bool, str]:
    """Return ``(ok, error_message)``. Empty / dash / hyphen are treated
    as 'no value' and pass. A non-empty value must split on commas, each
    part being either a single month token or a range ``A-B`` /
    ``A–B`` / ``A—B`` of month tokens."""
    s = (s or "").strip()
    if not s or s in ("—", "-", "–"):
        return True, ""
    # Normalize en/em dashes.
    norm = s.replace("–", "-").replace("—", "-")
    for part in (p.strip() for p in norm.split(",")):
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            a, b = a.strip(), b.strip()
            if a not in MONTH_TOKENS or b not in MONTH_TOKENS:
                return False, f"unrecognized month in range {part!r}"
        else:
            if part not in MONTH_TOKENS:
                return False, f"unrecognized month {part!r}"
    return True, ""


def _to_float(value) -> float | None:
    """Return ``float(value)`` or ``None`` for blank / non-numeric input.
    Plant JSON has many numeric fields stored as strings."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_SCI_NAME_RE = re.compile(r"^[A-Z][a-zA-Z\-]+(?:\s+[a-zA-Z×\.\-]+)+(?:\s+.+)?$")


# ── Per-record validation ───────────────────────────────────────────────────

def validate_plant(
    record: dict,
    source_label: str,
    idx: int,
    *,
    use_keys: set[str],
    ecoregion_keys: set[str],
) -> tuple[list[str], list[str]]:
    """Validate one plant record. Returns ``(errors, warnings)``.

    ``errors`` are typos / out-of-range numbers / missing required
    fields — things the running app actively misbehaves on. Test suite
    asserts these are empty.

    ``warnings`` are known data drift — things the app handles
    gracefully but that should be cleaned up over time. Surfaced for
    visibility but don't fail the build.
    """
    errors: list[str] = []
    warnings: list[str] = []
    name = record.get("common_name") or f"#{idx}"

    def err(msg: str) -> None:
        errors.append(f"{source_label}: {name}: {msg}")

    def warn(msg: str) -> None:
        warnings.append(f"{source_label}: {name}: {msg}")

    # ── Required identity fields ─────────────────────────────────────────
    if not record.get("common_name"):
        err("missing common_name")
    sci = (record.get("scientific_name") or "").strip()
    if not sci:
        err("missing scientific_name")
    elif not _SCI_NAME_RE.match(sci):
        err(f"scientific_name {sci!r} doesn't look binomial "
            "(expect e.g. 'Genus species')")
    if not (record.get("plant_type") or "").strip():
        err("missing plant_type")

    # ── Strict enums (deviations = error) ────────────────────────────────
    for field, allowed in (
        ("plant_type",          PLANT_TYPES),
        ("sun_requirement",     SUN_REQUIREMENTS),
        ("water_needs",         WATER_NEEDS),
        ("perennial_annual",    LIFE_CYCLES),
        ("deciduous_evergreen", DECIDUOUSNESS),
        ("growth_rate",         GROWTH_RATES),
        ("toxicity_pets",       TOXICITY_LEVELS),
        ("toxicity_humans",     TOXICITY_LEVELS),
        ("spread_habit",        SPREAD_HABITS),
        ("availability_class",  AVAILABILITY_CLASSES),
        ("flower_form",         FLOWER_FORMS),
        ("fruit_form",          FRUIT_FORMS),
        ("leaf_shape",          LEAF_SHAPES),
        ("leaf_arrangement",    LEAF_ARRANGEMENTS),
        ("branching",           BRANCHING_HABITS),
        ("growth_form",         GROWTH_FORMS),
        ("bark_texture",        BARK_TEXTURES),
        ("leaf_surface",        LEAF_SURFACES),
        ("inflorescence_form",  INFLORESCENCE_FORMS),
        ("flower_arch",         FLOWER_ARCHITECTURES),
        ("flower_symmetry",     FLOWER_SYMMETRIES),
        ("petal_shape",         PETAL_SHAPES),
        ("stem_branching",      STEM_BRANCHINGS),
    ):
        if field in _MULTI_VALUE_ENUM_FIELDS:
            for tok in condition_tokens(record.get(field)):
                if tok not in allowed:
                    err(f"{field} value {tok!r} not in {sorted(allowed)}")
            continue
        val = (record.get(field) or "").strip()
        if val and val not in allowed:
            err(f"{field}={val!r} not in {sorted(allowed)}")

    # flower_color: empty (no showy flower) or a #rrggbb hex (schema v31).
    fc = (record.get("flower_color") or "").strip()
    if fc and not re.fullmatch(r"#[0-9a-fA-F]{6}", fc):
        err(f"flower_color={fc!r} is not a #rrggbb hex")

    # fruit_color: empty (dry-fruited / non-fruiting) or a #rrggbb hex (v35).
    frc = (record.get("fruit_color") or "").strip()
    if frc and not re.fullmatch(r"#[0-9a-fA-F]{6}", frc):
        err(f"fruit_color={frc!r} is not a #rrggbb hex")

    # bark_color / fall_color: empty or #rrggbb (schema v47). An empty
    # fall_color is meaningful — an evergreen, or a species that doesn't colour
    # up — so it is never filled in with a guess.
    for field in ("bark_color", "fall_color"):
        val = (record.get(field) or "").strip()
        if val and not re.fullmatch(r"#[0-9a-fA-F]{6}", val):
            err(f"{field}={val!r} is not a #rrggbb hex")

    # leaf_size_cm: a positive length when present. The upper bound catches a
    # millimetre/centimetre unit slip, which would silently change 3D grain.
    leaf_cm = _to_float(record.get("leaf_size_cm"))
    if record.get("leaf_size_cm") not in (None, "") and leaf_cm is None:
        err(f"leaf_size_cm={record.get('leaf_size_cm')!r} is not a number")
    elif leaf_cm is not None and not (0.1 <= leaf_cm <= 120):
        err(f"leaf_size_cm={leaf_cm} out of range 0.1–120 cm")

    # ── Soft enums (deviations = warning) ────────────────────────────────
    val = (record.get("growth_curve") or "").strip()
    if val and val not in GROWTH_CURVES:
        warn(f"growth_curve={val!r} not in canonical {sorted(GROWTH_CURVES)}")

    nta = record.get("native_to_alberta")
    if nta is not None and nta not in NATIVE_TO_ALBERTA:
        warn(f"native_to_alberta={nta!r} not in canonical "
             f"{sorted(NATIVE_TO_ALBERTA, key=str)}")

    for key in _CALENDAR_KEYS:
        val = (record.get(key) or "").strip()
        if val and val not in CALENDAR_STATUS:
            warn(f"{key}={val!r} not in {sorted(CALENDAR_STATUS)}")

    # ── Numeric range coherence (deviations = error) ─────────────────────
    ph_min = _to_float(record.get("soil_ph_min"))
    ph_max = _to_float(record.get("soil_ph_max"))
    if ph_min is not None and ph_max is not None and ph_min > ph_max:
        err(f"soil_ph_min ({ph_min}) > soil_ph_max ({ph_max})")
    for label, val in (("soil_ph_min", ph_min), ("soil_ph_max", ph_max)):
        if val is not None and not (0.0 <= val <= 14.0):
            err(f"{label}={val} outside valid pH range [0, 14]")

    z_min = _to_float(record.get("hardiness_zone_min"))
    z_max = _to_float(record.get("hardiness_zone_max"))
    if z_min is not None and z_max is not None and z_min > z_max:
        err(f"hardiness_zone_min ({z_min}) > hardiness_zone_max ({z_max})")

    for field, max_val in (("spacing_m", 50.0), ("mature_height_m", 80.0)):
        v = _to_float(record.get(field))
        if v is not None and (v < 0 or v > max_val):
            err(f"{field}={v} outside [0, {max_val}]")

    # ── Bloom / fruit period (deviations = warning) ──────────────────────
    # The data uses uncertainty markers like "August?" in places — those
    # are intentional curator notes, not silent typos, so a warning is
    # the right level. The bloom-continuity parser at analysis_panel.py
    # ignores unrecognized tokens gracefully.
    for field in ("bloom_period", "fruit_period"):
        ok, msg = _parse_month_period(record.get(field, ""))
        if not ok:
            warn(f"{field} {record.get(field)!r}: {msg}")

    # ── Tag-table references (deviations = warning) ──────────────────────
    # Unknown use tags are likely either drift (e.g. "overstory" lacking
    # a canonical _USE_DEFINITIONS entry) or a typo. A warning surfaces
    # both without breaking CI on legitimate vocabulary expansion.
    uses_raw = record.get("permaculture_uses", "") or ""
    for token in (t.strip() for t in uses_raw.split(",")):
        if token and token not in use_keys:
            warn(f"unknown permaculture_uses tag {token!r}")

    # Accept the new province-neutral ``ecoregion`` key or the legacy
    # ``ab_ecoregion`` (V2.15 rename); the seed JSON still ships the latter.
    eco_raw = record.get("ecoregion") or record.get("ab_ecoregion", "") or ""
    if isinstance(eco_raw, list):
        eco_raw = ",".join(eco_raw)
    for token in (t.strip() for t in eco_raw.split(",")):
        if token and token not in ecoregion_keys:
            warn(f"unknown ecoregion key {token!r}")

    # native_provinces (V2.15): optional; warn on unknown province codes.
    np_raw = record.get("native_provinces") or ""
    if isinstance(np_raw, list):
        np_raw = ",".join(np_raw)
    for token in (t.strip().upper() for t in np_raw.split(",")):
        if token and token not in PROVINCE_CODES:
            warn(f"unknown native_provinces code {token!r}")

    return errors, warnings


# ── File-level + cross-record validation ────────────────────────────────────

def validate_records(
    records: Iterable[dict],
    source_label: str,
    *,
    use_keys: set[str] | None = None,
    ecoregion_keys: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Validate a sequence of records (a parsed plant JSON file).
    Returns ``(errors, warnings)``. Cross-record checks (duplicate
    scientific names) live at this level; per-record checks are
    delegated to ``validate_plant``."""
    if use_keys is None:
        use_keys = _load_use_keys()
    if ecoregion_keys is None:
        ecoregion_keys = _load_ecoregion_keys()

    errors: list[str] = []
    warnings: list[str] = []
    seen_scientific: dict[str, int] = {}
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(
                f"{source_label}: record {idx} is not an object "
                f"(got {type(record).__name__})"
            )
            continue
        e, w = validate_plant(
            record, source_label, idx,
            use_keys=use_keys,
            ecoregion_keys=ecoregion_keys,
        )
        errors.extend(e)
        warnings.extend(w)
        sci = (record.get("scientific_name") or "").strip()
        if sci:
            if sci in seen_scientific:
                # Duplicate sci names — warning, not error. The known
                # duplicates carry NOTE: / FLAG: markers in their own
                # notes field acknowledging the issue.
                warnings.append(
                    f"{source_label}: duplicate scientific_name {sci!r} "
                    f"(records {seen_scientific[sci]} and {idx})"
                )
            else:
                seen_scientific[sci] = idx
    return errors, warnings


def validate_file(path: Path) -> tuple[list[str], list[str]]:
    """Validate one plant JSON file at ``path``. Returns
    ``(errors, warnings)``. Missing-file / parse-error / bad-shape
    failures land in ``errors`` since they prevent any further validation."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"{path.name}: not found"], []
    try:
        records = json.loads(text)
    except json.JSONDecodeError as e:
        return [f"{path.name}: JSON parse error: {e}"], []
    if not isinstance(records, list):
        return [
            f"{path.name}: top-level should be a list, "
            f"got {type(records).__name__}"
        ], []
    return validate_records(records, path.name)


def validate_all() -> tuple[list[str], list[str]]:
    """Validate every shipped data file the app reseeds from. Returns
    ``(errors, warnings)``. Adding a new shipped data file means
    appending it here (and adding it to the reseed wipe list in
    plants.py per CLAUDE.md).

    Covers the plant catalogues plus the fauna data spine: the bee
    attributes (F37) and the fauna photo-licence compliance (A1) run in
    the central gate too, not only in an isolated bee test."""
    files = [
        DATA_DIR / "plants_master.json",
        DATA_DIR / "garden_plants.json",
    ]
    # Load canonical references once, share across files.
    use_keys = _load_use_keys()
    ecoregion_keys = _load_ecoregion_keys()
    errors: list[str] = []
    warnings: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
            records = json.loads(text)
        except FileNotFoundError:
            errors.append(f"{path.name}: not found")
            continue
        except json.JSONDecodeError as e:
            errors.append(f"{path.name}: JSON parse error: {e}")
            continue
        if not isinstance(records, list):
            errors.append(
                f"{path.name}: top-level should be a list, "
                f"got {type(records).__name__}"
            )
            continue
        e, w = validate_records(
            records, path.name,
            use_keys=use_keys,
            ecoregion_keys=ecoregion_keys,
        )
        errors.extend(e)
        warnings.extend(w)

    # Fauna data spine: the bee attributes (F37) and fauna photo-licence
    # compliance (A1). Both read shipped data/*.json the app reseeds from.
    for validate_fauna in (validate_bee_attributes, validate_fauna_images,
                           validate_fauna_morphology):
        e, w = validate_fauna()
        errors.extend(e)
        warnings.extend(w)

    # Photo COVERAGE, not just licence compliance (F70). Everything above has an
    # opinion about whether a photo is licensed correctly and none at all about
    # whether it exists — which is how 111 plants and 62 of 69 bees came to ship
    # with no photograph without anything ever saying so.
    e, w = validate_photo_coverage()
    errors.extend(e)
    warnings.extend(w)

    e, w = validate_morphology_provenance()
    errors.extend(e)
    warnings.extend(w)

    # Biological sourcing (V2.42). The relationships file had never been read by
    # this gate at all; plant photo credits and safety provenance were enforced
    # only by the care of whoever last edited them. docs/DATA_AUDIT.md.
    for validate_provenance in (validate_sources, validate_plant_fauna,
                                validate_plant_images,
                                validate_safety_provenance,
                                validate_host_genus_coverage):
        e, w = validate_provenance()
        errors.extend(e)
        warnings.extend(w)
    return errors, warnings


def validate_morphology_provenance() -> tuple[list[str], list[str]]:
    """A claimed source has to name itself (schema v56, extended v57).

    `flower_data_source` says a number was read in a flora or measured with a
    ruler. That is a *stronger* claim than `estimated`, and an unnamed source is
    not one — a species reading `flora` with a blank `flower_data_citation` says
    "somebody looked this up" and gives nobody a way to check it, which is worse
    than the honest `estimated` it replaced.

    An ERROR rather than a warning, and the asymmetry is deliberate: a missing
    photograph is work nobody has done yet, but an uncheckable citation is a
    claim the catalogue is already making. It is also trivially fixable — the
    bench fills the field in automatically on the `flora` path.

    v57 applies the same rule to the LEAF AND HABIT pair, which needs it more:
    the flower columns are blank until somebody describes a species, but
    `leaf_shape`, `leaf_size_cm`, `growth_form` and `mature_height_m` were
    seeded with a genus-level estimate for every one of the 434 records, so a
    guess there is invisible rather than absent.
    """
    errors: list[str] = []
    warnings: list[str] = []
    claimed = {"flora", "measured", "photo"}
    records = _load_json_list(DATA_DIR / "plants_master.json")
    for kind, src_field, cite_field in (
        ("flower", "flower_data_source", "flower_data_citation"),
        ("leaf", "leaf_data_source", "leaf_data_citation"),
    ):
        n_claimed = 0
        for rec in records:
            src = (rec.get(src_field) or "").strip().lower()
            if src not in claimed:
                continue
            n_claimed += 1
            if not (rec.get(cite_field) or "").strip():
                name = rec.get("scientific_name") or rec.get("common_name") or "?"
                errors.append(
                    f"{kind} provenance: {name}: source is {src!r} but no "
                    f"citation — name the flora, the photo or the date you "
                    f"measured it")
        if not n_claimed:
            warnings.append(
                f"{kind} provenance: no species has been verified yet — every "
                f"{kind} value is the seeder's genus default "
                f"(see docs/DATA_GAPS.md)")
    return errors, warnings


# The v56 name, kept so anything importing it keeps working. The function grew
# a second field pair in v57 and "flower" stopped being the whole story.
validate_flower_provenance = validate_morphology_provenance


def validate_fauna_morphology() -> tuple[list[str], list[str]]:
    """What the animals look like, checked (schema v58).

    Until v58 an animal's appearance was Python keyed off its common name, so
    there was nothing to validate — and nothing to correct. Now that it is data
    it gets the same treatment the plants get: enum values inside their
    vocabulary, ranges the right way round, and a claimed source that names
    itself.

    `band_pattern` earns its own checks. It is the bumblebee character — thorax
    then T1..T6 — and its failure mode is quiet: a mistyped colour renders as a
    default grey segment rather than raising, and a pattern one segment too long
    silently loses its tail.
    """
    errors: list[str] = []
    warnings: list[str] = []

    def _records(name):
        try:
            rows = json.loads((DATA_DIR / name).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            errors.append(f"{name}: {exc}")
            return []
        # Both files lead with a metadata record carrying no species.
        return [r for r in rows if isinstance(r, dict) and r.get("scientific_name")]

    bees = _records("bee_attributes_master.json")
    leps = _records("lepidoptera_attributes_master.json")

    def enum(rec, field, allowed, kind):
        val = (rec.get(field) or "").strip()
        if val and val not in allowed:
            errors.append(f"{kind} morphology: {rec['scientific_name']}: "
                          f"{field}={val!r} not in {sorted(allowed)}")

    for r in bees:
        enum(r, "build", BEE_BUILDS, "bee")
        enum(r, "scopa_position", SCOPA_POSITIONS, "bee")
        enum(r, "wing_tint", WING_TINTS, "bee")
        toks = band_pattern_tokens(r.get("band_pattern"))
        if len(toks) > BAND_SEGMENTS_MAX:
            errors.append(
                f"bee morphology: {r['scientific_name']}: band_pattern has "
                f"{len(toks)} segments, max is {BAND_SEGMENTS_MAX} "
                f"(thorax + T1..T6) — the extra ones are silently dropped")
        for t in toks:
            if t not in BAND_COLOURS:
                errors.append(
                    f"bee morphology: {r['scientific_name']}: band colour "
                    f"{t!r} not in {sorted(BAND_COLOURS)}")
        n = r.get("body_length_mm")
        if n is not None and not (2 <= float(n) <= 40):
            warnings.append(f"bee morphology: {r['scientific_name']}: "
                            f"body_length_mm {n} is outside 2-40 mm")

    for r in leps:
        enum(r, "wing_shape", WING_SHAPES, "lepidoptera")
        enum(r, "wing_pattern", WING_PATTERNS, "lepidoptera")
        enum(r, "resting_posture", RESTING_POSTURES, "lepidoptera")
        enum(r, "flight_style", FLIGHT_STYLES, "lepidoptera")
        lo, hi = r.get("wingspan_min_mm"), r.get("wingspan_max_mm")
        if (lo is None) != (hi is None):
            errors.append(f"lepidoptera morphology: {r['scientific_name']}: "
                          f"half a wingspan range ({lo}, {hi}) — give both or "
                          f"neither")
        elif lo is not None:
            if float(hi) < float(lo):
                errors.append(f"lepidoptera morphology: {r['scientific_name']}: "
                              f"wingspan range is backwards ({lo} > {hi})")
            elif not (8 <= float(lo) <= 200):
                warnings.append(f"lepidoptera morphology: "
                                f"{r['scientific_name']}: wingspan {lo} mm is "
                                f"outside 8-200 mm")
        eyes = r.get("eyespot_count")
        if eyes is not None and not (0 <= int(eyes) <= 8):
            errors.append(f"lepidoptera morphology: {r['scientific_name']}: "
                          f"eyespot_count {eyes} outside 0-8")

    # Provenance, same rule as the plants': a claimed source has to name itself.
    claimed = {"flora", "measured", "photo"}
    for kind, rows in (("bee", bees), ("lepidoptera", leps)):
        n_claimed = 0
        for r in rows:
            src = (r.get("morph_data_source") or "").strip().lower()
            if src not in claimed:
                continue
            n_claimed += 1
            if not (r.get("morph_data_citation") or "").strip():
                errors.append(
                    f"{kind} morphology: {r['scientific_name']}: source is "
                    f"{src!r} but no citation — name the guide, the photo or "
                    f"the date you measured it")
        if rows and not n_claimed:
            warnings.append(
                f"{kind} morphology: nothing verified yet — every value is the "
                f"seeder's estimate (see docs/DATA_GAPS.md)")
    return errors, warnings


# ── Bee attributes (F37) ──────────────────────────────────────────────────────

_BEE_NESTING = {
    "ground", "cavity", "pithy_stem", "social_ground", "cleptoparasite", "unknown",
}
_BEE_TONGUE = {"short", "medium", "long", "unknown"}


def validate_bee_attributes() -> tuple[list[str], list[str]]:
    """Validate ``data/bee_attributes_master.json`` against the schema-v39
    ``bee_attributes`` invariants and its cross-reference into
    ``fauna_master.json``. Returns ``(errors, warnings)``.

    Checks: valid JSON list; unique ``scientific_name``; each name resolves to a
    ``taxon='bee'`` fauna row; ``nesting_habit`` / ``tongue_length`` in their
    enums; ``pollen_specialist`` in {0, 1, null}; and the honesty invariant that
    a graded tongue length is only asserted for *Bombus* (the only genus the
    source characterises)."""
    errors: list[str] = []
    warnings: list[str] = []
    bee_path = DATA_DIR / "bee_attributes_master.json"
    fauna_path = DATA_DIR / "fauna_master.json"
    try:
        records = json.loads(bee_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"{bee_path.name}: not found"], []
    except json.JSONDecodeError as e:
        return [f"{bee_path.name}: JSON parse error: {e}"], []
    if not isinstance(records, list):
        return [f"{bee_path.name}: top-level should be a list"], []

    # Build the set of bee scientific names from the fauna file.
    try:
        fauna = json.loads(fauna_path.read_text(encoding="utf-8"))
        bee_names = {
            e["scientific_name"] for e in fauna
            if e.get("taxon") == "bee" and "scientific_name" in e
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        return [f"{fauna_path.name}: could not load bee names ({e})"], []

    seen: set[str] = set()
    for rec in records:
        name = rec.get("scientific_name")
        if not name:
            errors.append("bee_attributes: record missing scientific_name")
            continue
        if name in seen:
            errors.append(f"bee_attributes: duplicate scientific_name {name!r}")
        seen.add(name)
        if name not in bee_names:
            errors.append(
                f"bee_attributes: {name!r} has no matching taxon='bee' row in "
                f"{fauna_path.name}")
        nh = rec.get("nesting_habit")
        if nh is not None and nh not in _BEE_NESTING:
            errors.append(f"bee_attributes: {name}: bad nesting_habit {nh!r}")
        tl = rec.get("tongue_length")
        if tl is not None and tl not in _BEE_TONGUE:
            errors.append(f"bee_attributes: {name}: bad tongue_length {tl!r}")
        ps = rec.get("pollen_specialist")
        if ps not in (0, 1, None):
            errors.append(f"bee_attributes: {name}: pollen_specialist must be 0/1/null")
        # P9 honesty: only Bombus carries a graded tongue length.
        if tl in ("short", "medium", "long") and not str(name).startswith("Bombus "):
            errors.append(
                f"bee_attributes: {name}: graded tongue_length {tl!r} is only "
                f"documented for Bombus (use 'unknown' elsewhere)")
    return errors, warnings


# Bees use only commercial-safe CC licences (F37 A1 decision: CC0 + CC-BY).
_BEE_IMAGE_LICENSES = {"", "cc0", "cc-by"}

#: Plant photos take the whole CC whitelist. Bees are held to the stricter
#: CC0/CC-BY bar above because bee imagery is the app's most-reused asset;
#: SA on a plant photo is fine where it is only ever displayed with its credit.
_PLANT_IMAGE_LICENSES = {"cc0", "cc-by", "cc-by-sa"}


def validate_fauna_images() -> tuple[list[str], list[str]]:
    """Validate bee photo licences in ``data/fauna_master.json`` (F37 A1): a bee
    photo must be CC0 or CC-BY (no NC/SA — commercial-safe), and any non-CC0
    licensed photo must carry a non-empty attribution (CC-BY needs a visible
    credit). Non-bee taxa are not constrained here. Returns ``(errors, warnings)``."""
    errors: list[str] = []
    warnings: list[str] = []
    path = DATA_DIR / "fauna_master.json"
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"{path.name}: not found"], []
    except json.JSONDecodeError as e:
        return [f"{path.name}: JSON parse error: {e}"], []
    for rec in records:
        if rec.get("taxon") != "bee" or not (rec.get("image_url") or ""):
            continue
        name = rec.get("scientific_name", "?")
        lic = (rec.get("image_license") or "").lower().strip()
        if lic not in _BEE_IMAGE_LICENSES:
            errors.append(
                f"fauna image: {name}: bee photo licence {lic!r} is not CC0/CC-BY")
        if lic and lic != "cc0" and not (rec.get("image_attribution") or "").strip():
            errors.append(
                f"fauna image: {name}: {lic} photo needs a non-empty attribution")
    return errors, warnings


# ── Biological sourcing (V2.42) ───────────────────────────────────────────────
#
# The gate had never opened plant_fauna_master.json. That all 361 edges carried
# a real citation was an accident of how they were authored, not an invariant —
# nothing would have caught the next bulk import arriving bare, and the seeder
# dropped unresolvable names silently on top of that. These four checks make the
# sourcing an enforced property. See docs/DATA_AUDIT.md.

def _load_source_keys() -> tuple[set, dict]:
    """Canonical bibliography keys + alias→key map from sources_master.json."""
    path = DATA_DIR / "sources_master.json"
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return set(), {}
    keys, aliases = set(), {}
    for rec in blob.get("sources", []):
        key = (rec.get("key") or "").strip()
        if not key:
            continue
        keys.add(key)
        for alias in rec.get("aliases", []):
            aliases[alias.strip()] = key
    return keys, aliases


def validate_sources() -> tuple[list[str], list[str]]:
    """The bibliography itself: keys unique, required fields present, and the
    record_confidence vocabulary respected. An entry may be ``unverified`` — that
    is the honest state for most of them — but it may not be silently missing."""
    errors: list[str] = []
    warnings: list[str] = []
    path = DATA_DIR / "sources_master.json"
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"{path.name}: not found"], []
    except json.JSONDecodeError as e:
        return [f"{path.name}: JSON parse error: {e}"], []

    seen: set = set()
    unverified = 0
    for rec in blob.get("sources", []):
        key = (rec.get("key") or "").strip()
        if not key:
            errors.append("sources: a record has no key")
            continue
        if key in seen:
            errors.append(f"sources: duplicate key {key!r}")
        seen.add(key)
        # A NOT_A_WORK entry is a holding pen for edges whose original source
        # string named no work (see unattributed_prairie_pollination). It has no
        # authors by definition; requiring them would force somebody to invent
        # one, which is the failure this whole file exists to prevent. It is
        # surfaced as a warning below instead of being quietly exempted.
        is_work = (rec.get("kind") or "").strip() != "NOT_A_WORK"
        required = ("authors", "title") if is_work else ("title",)
        for field in required:
            if not (rec.get(field) or "").strip():
                errors.append(f"sources: {key}: missing {field}")
        if not is_work:
            warnings.append(
                f"bibliography: {key} is a placeholder, not a work — every "
                "edge citing it is effectively uncited and needs re-sourcing")
        conf = (rec.get("record_confidence") or "").strip()
        if conf not in ("verified", "unverified"):
            errors.append(
                f"sources: {key}: record_confidence {conf!r} not "
                "'verified'/'unverified'")
        if conf == "unverified":
            unverified += 1
    if unverified:
        warnings.append(
            f"bibliography: {unverified} of {len(seen)} source records are "
            "unverified — real works with genuine citations, but their "
            "bibliographic details have not been checked against the works "
            "(see data/sources_master.json)")
    return errors, warnings


def validate_plant_fauna() -> tuple[list[str], list[str]]:
    """The relationships file the gate never used to read.

    Enforces the four things that make an edge checkable rather than merely
    present: it names a plant and an animal that exist, it declares a
    relationship in the schema's vocabulary, it carries a source, and that
    source resolves to a work in the canonical bibliography.

    Name resolution is the one that matters most operationally. ``_seed_fauna``
    resolves these names at seed time and used to drop a miss with a bare
    ``continue`` — an edge deleted by a typo, with no error anywhere. Failing
    here means that can no longer reach a build."""
    errors: list[str] = []
    warnings: list[str] = []
    path = DATA_DIR / "plant_fauna_master.json"
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"{path.name}: not found"], []
    except json.JSONDecodeError as e:
        return [f"{path.name}: JSON parse error: {e}"], []

    plant_names: set = set()
    for cat in ("plants_master.json", "garden_plants.json"):
        try:
            for r in json.loads((DATA_DIR / cat).read_text(encoding="utf-8")):
                if isinstance(r, dict) and r.get("common_name"):
                    plant_names.add(r["common_name"])
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    fauna_names: set = set()
    try:
        for r in json.loads(
                (DATA_DIR / "fauna_master.json").read_text(encoding="utf-8")):
            if isinstance(r, dict) and r.get("scientific_name"):
                fauna_names.add(r["scientific_name"])
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    source_keys, aliases = _load_source_keys()
    valid_rel = {"larval_host", "nectar", "pollen", "seed_food",
                 "fruit_food", "nesting", "cover"}
    no_notes = 0
    for rec in records:
        if not isinstance(rec, dict) or "plant" not in rec or "fauna" not in rec:
            continue                      # metadata header
        plant, animal = rec.get("plant", "?"), rec.get("fauna", "?")
        label = f"plant_fauna: {plant} ↔ {animal}"
        if plant_names and plant not in plant_names:
            errors.append(f"{label}: plant name does not resolve — edge would "
                          "be dropped silently at seed time")
        if fauna_names and animal not in fauna_names:
            errors.append(f"{label}: fauna name does not resolve — edge would "
                          "be dropped silently at seed time")
        rel = (rec.get("relationship") or "").strip()
        if rel not in valid_rel:
            errors.append(f"{label}: relationship {rel!r} not in the schema "
                          "vocabulary")
        spec = (rec.get("specificity") or "").strip()
        if spec and spec not in ("specialist", "generalist"):
            errors.append(f"{label}: specificity {spec!r} not "
                          "'specialist'/'generalist'")
        source = (rec.get("source") or "").strip()
        if not source:
            errors.append(f"{label}: no source — every ecological claim this "
                          "app ships has to say where it came from")
        elif source_keys:
            # A claim may rest on more than one work — the bee attributes cite
            # three. A comma-separated key list is the canonical form for that;
            # every member has to resolve.
            unknown = [part for part in
                       (p.strip() for p in source.split(",")) if part
                       and part not in source_keys and part not in aliases]
            if unknown:
                errors.append(
                    f"{label}: source {', '.join(repr(u) for u in unknown)} is "
                    "not in the canonical bibliography "
                    "(data/sources_master.json) — add the work or use one of "
                    "its recorded aliases")
        if not (rec.get("notes") or "").strip():
            no_notes += 1
    if no_notes:
        warnings.append(
            f"plant_fauna: {no_notes} of {len(records) - 1} edges carry no "
            "notes — the citation says which book, nothing says what the book "
            "actually reported")
    return errors, warnings


def validate_plant_images() -> tuple[list[str], list[str]]:
    """Plant photo credits — the check docs/DATA_SOURCES.md already claimed the
    gate performed. It credited ``validate_fauna_images`` with covering
    ``plants.image_url``; that function filters ``taxon != 'bee'`` over
    fauna_master.json and never touches plants. The plant photos happen to be
    clean (323/323 attributed and licensed), which is exactly how a missing
    check stays missing."""
    errors: list[str] = []
    warnings: list[str] = []
    for name in ("plants_master.json", "garden_plants.json"):
        path = DATA_DIR / name
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        for rec in records:
            if not isinstance(rec, dict) or not (rec.get("image_url") or ""):
                continue
            who = rec.get("common_name") or rec.get("scientific_name") or "?"
            lic = (rec.get("image_license") or "").lower().strip()
            if not lic:
                errors.append(f"plant image: {who}: photo has no licence")
            elif lic not in _PLANT_IMAGE_LICENSES:
                errors.append(
                    f"plant image: {who}: licence {lic!r} is not in the "
                    f"permitted set {sorted(_PLANT_IMAGE_LICENSES)}")
            if lic and lic != "cc0" and not (
                    rec.get("image_attribution") or "").strip():
                errors.append(
                    f"plant image: {who}: {lic} photo needs a non-empty "
                    "attribution")
    return errors, warnings


def validate_safety_provenance() -> tuple[list[str], list[str]]:
    """A toxicity rating must say where it came from.

    49 of 49 tagged plants comply today, by authorship rather than by rule. This
    is the one class of claim in the app where being wrong is not an academic
    matter, so it gets a hard check rather than a warning."""
    errors: list[str] = []
    for name in ("plants_master.json", "garden_plants.json"):
        path = DATA_DIR / name
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        for rec in records:
            if not isinstance(rec, dict):
                continue
            rated = ((rec.get("toxicity_pets") or "").strip()
                     or (rec.get("toxicity_humans") or "").strip())
            if rated and not (rec.get("safety_source") or "").strip():
                who = rec.get("common_name") or rec.get("scientific_name") or "?"
                errors.append(
                    f"safety: {who}: carries a toxicity rating with no "
                    "safety_source")
    return errors, []


def validate_host_genus_coverage() -> tuple[list[str], list[str]]:
    """Host genera the fauna cite that the plant catalogue cannot supply.

    Read one way this is a data-integrity check; read the other way round it is
    the most useful catalogue-gap finder in the repo — the animals are naming
    the plants we do not ship. It is a warning, not an error: an introduced
    species (*Melilotus*, *Taraxacum*) is correctly absent from a native
    catalogue, and only a human can tell that apart from a real omission."""
    warnings: list[str] = []
    try:
        from src.db.derived_edges import (            # noqa: PLC0415
            bee_genus_host_edges, lepidoptera_genus_host_edges)
        plants = []
        for cat in ("plants_master.json", "garden_plants.json"):
            plants += [r for r in json.loads(
                (DATA_DIR / cat).read_text(encoding="utf-8"))
                if isinstance(r, dict)]
        def _load(n):
            return [r for r in json.loads(
                (DATA_DIR / n).read_text(encoding="utf-8"))
                if isinstance(r, dict) and "_comment" not in r]
        bees = _load("bee_attributes_master.json")
        leps = _load("lepidoptera_attributes_master.json")
    except (FileNotFoundError, json.JSONDecodeError, ImportError):
        return [], []
    _, unmatched_b = bee_genus_host_edges(plants, bees)
    _, unmatched_l = lepidoptera_genus_host_edges(plants, leps)
    unmatched = sorted(set(unmatched_b) | set(unmatched_l))
    if unmatched:
        warnings.append(
            f"host genera: {len(unmatched)} genus/genera cited as hosts are "
            f"absent from the plant catalogue: {', '.join(unmatched)} — each is "
            "either a plant worth adding or a taxonomic synonym worth teaching "
            "src/db/derived_edges.GENUS_SYNONYMS")
    return [], warnings


# ── Photo coverage (F70, V2.35) ───────────────────────────────────────────────

# The named slots, mirrored from src/db/plants.PHOTO_SLOTS. Kept as a literal so
# this module stays importable without the DB layer (it is run by the CLI gate
# and by tests that never open a database); tests/test_plant_photos.py asserts
# the two lists agree.
PHOTO_SLOTS = ("habit", "flower", "leaf", "fruit", "bark_stem", "winter",
               "seedling")


def photo_coverage() -> dict:
    """Coverage of the SHIPPED photo set, read straight from the seed files.

    Deliberately file-based rather than DB-based: this runs in the data gate
    before anything is seeded, and the question it answers is "what will we
    ship", not "what is on this machine".

    Counts a species as covered by a slot if `data/plant_photos.json` gives it
    one; the legacy single `plants.image_url` counts as a `flower`, which is
    what those photos overwhelmingly are.
    """
    plants = _load_json_list(DATA_DIR / "plants_master.json")
    shots = _load_json_list(DATA_DIR / "plant_photos.json")
    by_name: dict[str, set] = {}
    for e in shots:
        sci = (e.get("scientific_name") or "").strip()
        slot = (e.get("slot") or "").strip()
        if sci and slot in PHOTO_SLOTS:
            by_name.setdefault(sci, set()).add(slot)
    for rec in plants:
        sci = (rec.get("scientific_name") or "").strip()
        if sci and (rec.get("image_url") or "").strip():
            by_name.setdefault(sci, set()).add("flower")
    names = [(r.get("scientific_name") or "").strip() for r in plants]
    names = [n for n in names if n]
    return {
        "species": len(names),
        "with_any": sum(1 for n in names if by_name.get(n)),
        "by_slot": {s: sum(1 for n in names if s in by_name.get(n, ()))
                    for s in PHOTO_SLOTS},
        "missing": sorted(n for n in names if not by_name.get(n)),
    }


def validate_photo_coverage() -> tuple[list[str], list[str]]:
    """Report photo coverage as WARNINGS, never errors.

    A missing photograph is a gap in the work, not a defect in the data — the
    app renders perfectly well without one, and turning it into an error would
    make the gate red for a reason nobody can fix in a commit. What it must not
    be is invisible.
    """
    warnings: list[str] = []
    errors: list[str] = []
    try:
        cov = photo_coverage()
    except FileNotFoundError:
        return [], []
    n = cov["species"]
    if not n:
        return [], []
    missing = n - cov["with_any"]
    if missing:
        warnings.append(
            f"photo coverage: {missing} of {n} species have no photograph "
            f"at all")
    for slot in PHOTO_SLOTS:
        have = cov["by_slot"][slot]
        if have < n:
            warnings.append(
                f"photo coverage: slot {slot!r} covers {have} of {n} species")
    # Every photo we DO ship has to carry its credit, on the same rule the
    # single-column photos already follow.
    for e in _load_json_list(DATA_DIR / "plant_photos.json"):
        sci = e.get("scientific_name") or "?"
        slot = (e.get("slot") or "").strip()
        if slot not in PHOTO_SLOTS:
            errors.append(f"plant_photos: {sci}: unknown slot {slot!r}")
        lic = (e.get("license") or "").lower().strip()
        if lic and lic != "cc0" and not (e.get("attribution") or "").strip():
            errors.append(
                f"plant_photos: {sci}: {lic} photo needs a non-empty attribution")
        if not (e.get("url") or "").strip():
            errors.append(f"plant_photos: {sci}: empty url")
    return errors, warnings


def _load_json_list(path) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []
