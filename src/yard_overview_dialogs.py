"""
yard_overview_dialogs.py — the two dialogs behind the Overview's buttons
(OV-9, OV-10; V3.27; docs/homeowner/06-yard-overview.md §6.3).

Design principle P8 — see docs/DESIGN_PHILOSOPHY.md.

**Fill the gaps** says how much ground the grown plants will leave bare and
offers three equal answers (O3): plant low plants 60 cm apart, with the count
and the cost said before anything is placed; keep the gaps mulched, which costs
least and is how the care calendar already expects years 2 to 4 to look; or
outline only the beds being planted. **Swap** offers plants that do a similar
job and are native where the pin is, and replaces every one of the plant where
it stands. Each change is one undo step.

Every dialog goes through ``_exec``, which tests replace, so nothing waits.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

_TEXT = "color: #c8e6c9; font-size: 13px;"
_HEAD = "color: #e8f5e9; font-size: 15px; font-weight: bold;"


def _exec(dialog) -> int:
    return dialog.exec()


def _label(text: str, style: str = _TEXT) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(style)
    return label


def _choice(dialog, col, text: str, button: str, answer: str):
    row = QHBoxLayout()
    row.addWidget(_label(text), 1)
    b = QPushButton(button)
    b.setAccessibleName(button)
    b.clicked.connect(lambda: (setattr(dialog, "answer", answer),
                               dialog.accept()))
    row.addWidget(b)
    col.addLayout(row)
    dialog.buttons[answer] = b


def _dialog(main, title: str) -> tuple:
    from src.ui_style import WINDOW_STYLE
    dialog = QDialog(main)
    dialog.setWindowTitle(title)
    dialog.setStyleSheet(WINDOW_STYLE)
    dialog.setMinimumWidth(460)
    dialog.answer = ""
    dialog.buttons = {}
    return dialog, QVBoxLayout(dialog)


def _cancel(dialog, col) -> None:
    row = QHBoxLayout()
    row.addStretch()
    b = QPushButton("Cancel")
    b.clicked.connect(dialog.reject)
    row.addWidget(b)
    col.addLayout(row)
    dialog.buttons["cancel"] = b


# ── Fill the gaps (OV-9) ────────────────────────────────────────────────────

def fill_dialog(main, plan: dict) -> QDialog:
    from src.sourcing import format_cost
    dialog, col = _dialog(main, "Fill the gaps")
    col.addWidget(_label("Fill the gaps", _HEAD))
    col.addWidget(_label(
        f"About {plan['bare_m2']:.0f} m² of the area you outlined will still "
        "be bare when the plants are grown."))
    if plan["records"]:
        names = " and ".join(r.get("common_name") or "" for r in
                             plan["fillers"])
        n = len(plan["records"])
        _choice(dialog, col,
                f"Plant low plants 60 cm apart: about {n} more plants "
                f"({names}), {format_cost(*plan['cost'])} at nursery prices. "
                "They fill in over two or three summers.",
                "Plant them", "plant")
    _choice(dialog, col,
            "Keep the gaps mulched and let your plants spread. Cheapest; "
            "expect to weed the gaps for two to four years.",
            "Keep them mulched", "mulch")
    _choice(dialog, col,
            "Only planting part of it? Outline your beds and only they will "
            "be counted.", "Outline my beds", "outline")
    _cancel(dialog, col)
    return dialog


def fill_gaps(main) -> str:
    """Show the dialog and do what it is answered with. Returns the answer."""
    from src.yard_overview import fill_plan
    plan = fill_plan(main._project)
    dialog = fill_dialog(main, plan)
    _exec(dialog)
    if dialog.answer == "plant" and plan["records"]:
        with main._persistence.checkpoint("fill the gaps"):
            main._area_fill._place_plant_records(plan["records"])
    elif dialog.answer == "outline":
        from src.yard_overview_flow import run_action
        run_action(main, "shape:Garden Bed")
    return dialog.answer


# ── Swap for a local native (OV-10), or any plant from its page (V3.32) ─────

def swap_choices(main, plant_id: int, limit: int = 3) -> list:
    from src import substitution
    site = ((main._project.get("properties") or {}).get("site_config")
            or {})
    return substitution.substitutes(plant_id, limit=limit, site_config=site,
                                    native_only=True)


def swap_dialog(main, plant_id: int, choices: list) -> QDialog:
    from src import design_native
    from src.db.plants import get_plant
    from src.phenology_bar import parse_period
    from src.sourcing import describe
    from src.what_it_feeds import span
    site = ((main._project.get("properties") or {}).get("site_config")
            or {})
    row0 = get_plant(plant_id) or {}
    name = row0.get("common_name") or "This plant"
    dialog, col = _dialog(main, f"Swap {name}")
    # From the plant page any plant can be swapped (V3.32); only one that is
    # not native is said to be.
    col.addWidget(_label(
        f"Instead of {name}" if design_native.is_native(row0, site)
        else f"{name} is not {design_native.words(site)}.", _HEAD))
    if not choices:
        col.addWidget(_label("Nothing native here does a similar job, as far "
                             "as the records go. Keep it, or choose another "
                             "plant from the plant list."))
    else:
        col.addWidget(_label("These do a similar job here:"))
    for swap in choices:
        row = get_plant(swap.plant_id) or {}
        months = parse_period(row.get("bloom_period") or "")
        bits = [f"flowers {span(months)}" if months else ""]
        sold = describe(_sourcing(row))[0]
        if sold:
            bits.append(sold[0].lower() + sold[1:].rstrip("."))
        text = swap.common_name + (": " + "; ".join(b for b in bits if b)
                                   if any(bits) else "")
        _choice(dialog, col, text + ".", "Swap", str(swap.plant_id))
    count = sum(1 for p in main._store.placed_plants
                if p.get("plant_id") == plant_id)
    col.addWidget(_label(
        f"A swap replaces {'the' if count == 1 else 'all ' + str(count)} "
        f"{name} where {'it stands' if count == 1 else 'they stand'}. Undo "
        f"puts {'it' if count == 1 else 'them'} back."))
    _cancel(dialog, col)
    return dialog


def _sourcing(row: dict) -> dict:
    from src.scene_dossier import _sourcing as sourcing_of
    try:
        return sourcing_of(row)
    except Exception:                                      # noqa: BLE001
        return {}


def swap(main, plant_id: int) -> int:
    """Show the swap dialog; on a choice, replace every ``plant_id`` where it
    stands, in one undo step. Returns the plant swapped in, or 0."""
    dialog = swap_dialog(main, plant_id, swap_choices(main, plant_id))
    _exec(dialog)
    if not dialog.answer.isdigit():
        return 0
    new_id = int(dialog.answer)
    replace(main, plant_id, new_id)
    return new_id


def replace(main, old_id: int, new_id: int) -> int:
    """Every ``old_id`` becomes ``new_id`` at the same spot; one undo step."""
    from src.db.plants import get_plant
    store = main._store
    spots = [(p["plant_id"], p["lat"], p["lng"]) for p in store.placed_plants
             if p.get("plant_id") == old_id]
    if not spots:
        return 0
    name = (get_plant(new_id) or {}).get("common_name") or ""
    with main._persistence.checkpoint("swap plant"):
        store.remove_plants_batch(spots)
        for _pid, lat, lng in spots:
            store.add_plant(new_id, name, lat, lng)
        main._persistence.redraw()
        try:
            main.plant_panel.on_plants_removed_batch([old_id] * len(spots))
            main.plant_panel.on_plants_placed_batch([(new_id, name)]
                                                    * len(spots))
        except Exception:                                  # noqa: BLE001
            pass
        main._mark_modified()
        main._sync_planning_panel()
    return len(spots)
