"""
member_colors.py — marker colour tables for plant-community members.

Vegetation layer is the primary signal — when a member has a layer set we
colour by that so the canopy structure reads at a glance on the map. Function
colours are used only when a member has no layer (i.e. functional-only roles
like "windbreak" or "nitrogen_fixer"). Legacy single-value `role` data falls
through to either table.

Qt-free and import-light on purpose: placement code paths (map event router,
area-fill controller) need a member's colour without dragging in the whole
``src.app`` module (whose import requires QtWebEngine to be set up first).
"""

from __future__ import annotations

LAYER_COLORS = {
    'overstory':           '#1b5e20',
    'understory':          '#388e3c',
    'shrub_layer':         '#4a8b3a',
    'groundcover':         '#66bb6a',
    'herbaceous':          '#9ccc65',
    'vine':                '#7cb342',
    'root':                '#8d6e63',
}

FUNCTION_COLORS = {
    'nitrogen_fixer':      '#43a047',
    'soil_builder':        '#2e7d32',
    'pest_deterrent':      '#7cb342',
    'pollinator':          '#aed581',
    'windbreak':           '#558b2f',
}

# Legacy aliases mapped through to the new tables so projects saved
# before the role rename still render.
LEGACY_ROLE_ALIASES = {
    'canopy':              ('overstory',      'layer'),
    'dynamic_accumulator': ('soil_builder',   'function'),
    'pest_repellent':      ('pest_deterrent', 'function'),
}

OTHER_COLOR = '#81c784'


def member_color(member: dict) -> str:
    """Pick a marker colour for a polyculture member.

    Resolution order:
      1. Explicit `layer` → LAYER_COLORS.
      2. First entry in `functions` → FUNCTION_COLORS.
      3. Legacy single `role` (with alias mapping) → either table.
      4. Fallback to OTHER_COLOR.
    """
    layer = (member.get('layer') or '').strip().lower()
    if layer in LAYER_COLORS:
        return LAYER_COLORS[layer]
    funcs = member.get('functions') or []
    if isinstance(funcs, list) and funcs:
        f0 = str(funcs[0]).strip().lower()
        if f0 in FUNCTION_COLORS:
            return FUNCTION_COLORS[f0]
    role = (member.get('role') or '').strip().lower()
    if role in LEGACY_ROLE_ALIASES:
        canonical, kind = LEGACY_ROLE_ALIASES[role]
        if kind == 'layer':
            return LAYER_COLORS.get(canonical, OTHER_COLOR)
        return FUNCTION_COLORS.get(canonical, OTHER_COLOR)
    if role in LAYER_COLORS:
        return LAYER_COLORS[role]
    if role in FUNCTION_COLORS:
        return FUNCTION_COLORS[role]
    return OTHER_COLOR
