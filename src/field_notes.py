"""
src/field_notes.py — site-walk field notes (F6).

Design principle P11 (the body and the site know things the screen does not —
drive the user outside) — see docs/DESIGN_PHILOSOPHY.md.

Knowledge lives in hands, soil, wind and direct observation, not only in fetched
datasets. This module captures what the *site* knows as a structured block on the
project FeatureCollection's ``properties`` (no DB schema bump): a prompted
checklist of the things a designer should walk the ground to notice — where water
pools, where snow drifts, where soil compacts, where wind funnels — each with a
free-text observation, plus a free-text catch-all.

It is deliberately Qt-free and persistence-only so the Site panel, the project
save/load path, the exporters and the tests all share one definition. The prompts
are McHarg's overlay method turned into a walking checklist (P5/P11); a later
slice can pin individual observations to map points and feed them into generation
as soft constraints (roadmap F6 "pinned" + brainstorm steering).
"""

from __future__ import annotations

from datetime import datetime, timezone


# The walking checklist: (key, prompt). Keys are stable storage handles; prompts
# are the questions the user answers on site. Ordered roughly as you'd walk a
# yard — water and snow first (they shape everything), then soil, wind, light,
# life, and finally the embodied "just stand here and notice".
FIELD_PROMPTS: list[tuple[str, str]] = [
    ("water_pools",   "Where does water pool, run, or stay soggy after rain or melt?"),
    ("snow_drifts",   "Where does snow pile up or linger latest into spring?"),
    ("soil_feel",     "Where is the soil hard, compacted, bare, or eroding?"),
    ("wind",          "Where does wind funnel through or dry things out?"),
    ("frost_pockets", "Where are the cold spots and frost pockets?"),
    ("hot_dry",       "Where is it hottest and driest in mid-summer?"),
    ("volunteers",    "What is already thriving here on its own?"),
    ("foot_traffic",  "Where do people and pets actually walk?"),
    ("sun_shade",     "Where does the sun fall in the morning vs. afternoon?"),
    ("senses",        "Standing on the site — what do you see, hear, smell, feel?"),
]

_PROMPT_KEYS = {k for k, _ in FIELD_PROMPTS}


def _utc_now_iso() -> str:
    """Naive-UTC ISO timestamp (matches project.py's convention)."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def empty_field_notes() -> dict:
    """A fresh, empty field-notes block."""
    return {"observations": {}, "free_text": "", "updated": ""}


def normalize(notes) -> dict:
    """Return a clean field-notes dict from whatever is stored (tolerant of
    missing keys, legacy shapes, or ``None``).

    ``observations`` maps a prompt key → ``{"checked": bool, "note": str}``;
    unknown keys are dropped so a renamed prompt can't accumulate orphans."""
    notes = notes if isinstance(notes, dict) else {}
    obs_in = notes.get("observations") or {}
    observations: dict[str, dict] = {}
    if isinstance(obs_in, dict):
        for key, val in obs_in.items():
            if key not in _PROMPT_KEYS:
                continue
            val = val if isinstance(val, dict) else {}
            note = str(val.get("note") or "").strip()
            checked = bool(val.get("checked")) or bool(note)
            if checked or note:
                observations[key] = {"checked": checked, "note": note}
    return {
        "observations": observations,
        "free_text": str(notes.get("free_text") or "").strip(),
        "updated": str(notes.get("updated") or ""),
    }


def is_empty(notes) -> bool:
    """True when there is nothing worth saving / showing."""
    n = normalize(notes)
    return not n["observations"] and not n["free_text"]


def get_field_notes(project) -> dict:
    """The project's normalized field-notes block (never raises; empty when
    absent)."""
    props = (project or {}).get("properties", {}) if isinstance(project, dict) else {}
    return normalize(props.get("field_notes"))


def set_field_notes(project, notes) -> dict:
    """Store ``notes`` on the project's ``properties.field_notes`` (stamping
    ``updated``), or drop the block entirely when empty. Mutates ``project`` in
    place and returns the stored (normalized) dict — ``{}`` when cleared."""
    props = project.setdefault("properties", {})
    if is_empty(notes):
        props.pop("field_notes", None)
        return {}
    clean = normalize(notes)
    clean["updated"] = _utc_now_iso()
    props["field_notes"] = clean
    return clean


def format_field_notes(notes) -> str:
    """Human-readable readout (for export / display), or ``""`` when empty.

    One line per answered prompt (its question + the observation), then the
    free-text block."""
    n = normalize(notes)
    if is_empty(n):
        return ""
    prompt_text = dict(FIELD_PROMPTS)
    lines = ["SITE-WALK FIELD NOTES", ""]
    for key, _q in FIELD_PROMPTS:
        entry = n["observations"].get(key)
        if not entry:
            continue
        note = entry.get("note") or ""
        lines.append(f"• {prompt_text[key]}")
        if note:
            lines.append(f"    {note}")
    if n["free_text"]:
        if len(lines) > 2:
            lines.append("")
        lines.append("Other observations:")
        lines.append(n["free_text"])
    return "\n".join(lines).rstrip() + "\n"
