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
  * Source of truth for the canonical Alberta ecoregion keys is
    ``_AB_ECOREGION_CHOICES`` in ``src/plant_panel.py``; that module
    imports PyQt6, so the constant is read out via ``ast.literal_eval``
    on the source text rather than via a real import.
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

import ast
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
                     "cluster", "bell", "trumpet", "none"}

# ── Soft enum allowlists (drift here is a WARNING) ──────────────────────────

GROWTH_CURVES     = {"slow_start", "steady", "fast_early"}
# Calendar status — matches the schema.sql CHECK on planting_calendar.status.
CALENDAR_STATUS   = {"dormant", "start_indoors", "direct_sow", "transplant",
                     "growing", "harvest", "pruning"}
# native_to_alberta is documented as 0/1 but the data carries '1?' for
# uncertain-native records; the code handles it via _truthy_int.
NATIVE_TO_ALBERTA = {0, 1, "0", "1", "1?", "0?"}

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
    """Canonical AB ecoregion keys, parsed out of plant_panel.py without
    importing it (the module pulls in PyQt6). Handles both annotated
    (``X: list[...] = [...]``) and plain (``X = [...]``) assignment
    forms — the current source uses the annotated form."""
    src = (PROJECT_ROOT / "src" / "plant_panel.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        target_name: str | None = None
        value_node = None
        if (isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            target_name = node.targets[0].id
            value_node = node.value
        elif (isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.value is not None):
            target_name = node.target.id
            value_node = node.value
        if target_name == "_AB_ECOREGION_CHOICES":
            literal = ast.literal_eval(value_node)
            return {key for _label, key in literal if key}
    raise RuntimeError("_AB_ECOREGION_CHOICES not found in plant_panel.py")


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

    eco_raw = record.get("ab_ecoregion", "") or ""
    for token in (t.strip() for t in eco_raw.split(",")):
        if token and token not in ecoregion_keys:
            warn(f"unknown ab_ecoregion key {token!r}")

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
    """Validate every shipped plant data file. Returns
    ``(errors, warnings)``. Adding a new shipped data file means
    appending it here (and adding it to the reseed wipe list in
    plants.py per CLAUDE.md)."""
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
    return errors, warnings
