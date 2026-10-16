"""
plant_page_sections.py — what the plant page says in the simple app (PR-4,
V3.26; docs/homeowner/05-plants-that-lead.md §7).

Design principle P6 — see docs/DESIGN_PHILOSOPHY.md.

The page was three to four screens of nineteen sections, the longest of them
citations (§7.1). In the simple app it is now about a hundred words a person
can act on: the plant's band, why it is worth planting, what to know, how to
grow it, where to buy it, and whether it is native here. "Everything about
this plant" opens the rest in place, which is what the advanced app shows from
the start.

Every word comes from structured fields and the ranking
(``src.plant_priority``); the free-text notes are never shown on the desktop,
in either mode (decision L8, P12). Qt-free: the page draws what this returns.
"""

from __future__ import annotations

from typing import Mapping, Optional

#: Where the season bar goes in the simple page.
SEASON = "\x00season"
#: The heading under which the advanced sections open (WD-8).
MORE = "Everything about this plant"
#: The ID line (WD-8, W3): on the advanced page and in Help › About only.
ID_LINE = ("These photos help you choose plants. They are not a guide to "
           "identifying plants in the wild.")

_SUN = {"full sun": "Full sun", "full_sun": "Full sun",
        "part shade": "part shade", "partial shade": "part shade",
        "partial_shade": "part shade", "part_shade": "part shade",
        "full shade": "shade", "full_shade": "shade", "shade": "shade"}
_WATER = {"low": "dry", "medium": "average", "high": "moist"}


def _tokens(value) -> list:
    return [t.strip() for t in str(value or "").replace(";", ",").split(",")
            if t.strip()]


def growing_words(entry: Mapping) -> str:
    """"Full sun to part shade. Dry to average soil." in words."""
    sun = []
    for t in _tokens(entry.get("sun")):
        w = _SUN.get(t.lower())
        if w and w not in sun:
            sun.append(w)
    water = []
    for t in _tokens(entry.get("water")):
        w = _WATER.get(t.lower())
        if w and w not in water:
            water.append(w)
    water.sort(key=["dry", "average", "moist"].index)
    out = []
    if sun:
        s = sun[0] if len(sun) == 1 else f"{sun[0]} to {sun[-1]}"
        out.append(s[:1].upper() + s[1:] + ".")
    if water:
        w = water[0] if len(water) == 1 else f"{water[0]} to {water[-1]}"
        out.append(w[:1].upper() + w[1:] + " soil.")
    return " ".join(out)


def _num(value) -> Optional[float]:
    try:
        v = float(str(value).strip().rstrip("?"))
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def size_words(entry: Mapping) -> str:
    """"Grows to 5 m tall and 4.5 m wide in about 6 years. Plant 3 m apart."""
    h, w = _num(entry.get("mature_height_m")), _num(entry.get("mature_canopy_m"))
    years = _num(entry.get("years_to_maturity"))
    parts = []
    if h and w:
        parts.append(f"Grows to {h:g} m tall and {w:g} m wide")
    elif h:
        parts.append(f"Grows to {h:g} m tall")
    text = parts[0] if parts else ""
    if text and years:
        text += f" in about {years:g} year{'' if years == 1 else 's'}"
    if text:
        text += "."
    from src.planting_spacing import spacing_words           # noqa: PLC0415
    apart = spacing_words(entry.get("spacing_m"))    # one number (QF-9)
    if apart:
        text = (text + " " if text else "") + f"Plant {apart} apart."
    return text


def buying_words(entry: Mapping, place: str = "") -> str:
    from src import local_stock                              # noqa: PLC0415
    price = ((entry.get("sourcing") or {}).get("price") or "").strip()
    price = price.replace(" (estimate)", "").replace("per plant", "a plant")
    price = (price[:1].upper() + price[1:] + ".") if price else ""
    stock = local_stock.clause(entry.get("scientific_name") or "", place)
    return " ".join(p for p in (price, stock) if p)


def simple(entry: Mapping, row: Optional[Mapping] = None, *,
           place: str = "") -> list:
    """``[(heading, body), …]`` for the simple page; ``(SEASON, "")`` marks
    where the season bar goes. ``row`` is the catalogue row (read when not
    given); ``place`` the region (the edition's when empty)."""
    from src import native_here, plant_priority, region     # noqa: PLC0415
    if row is None:
        from src.db.plants import get_plant                  # noqa: PLC0415
        row = get_plant(int(entry.get("id") or 0)) or {}
    home = region.regions().get(place) if place else region.default()
    home = home or region.default()
    a = plant_priority.assess(row, place=home.key)
    good = list(a.cautions)
    if not (row.get("toxicity_pets") or row.get("toxicity_humans")):
        good.append("Not checked for poison")
    # An off-list plant's band is said by the last line instead.
    sections = [(a.band if a.band != plant_priority.AWAY else "", ""),
                ("Why this plant", _sentences(a.reasons)),
                ("Good to know", _sentences(good)),
                ("Growing it", " ".join(p for p in (growing_words(entry),
                                                    size_words(entry)) if p)),
                (SEASON, ""),
                ("Buying it", buying_words(entry, home.key))]
    try:
        native = native_here.native_around(row, home.key)
    except ValueError:
        native = None
    if native is not None:
        sections.append((f"Native around {home.short}." if native else
                         f"Not native around {home.short}.", ""))
    # A heading with nothing under it is dropped, except the band and the
    # native line, which are whole sentences on their own.
    lone = {a.band, f"Native around {home.short}.",
            f"Not native around {home.short}."}
    return [(h, b) for h, b in sections
            if h == SEASON or (h and (b or h in lone))]


def _sentences(items) -> str:
    return " ".join(i.rstrip(".") + "." for i in items if i)


def word_count(sections) -> int:
    return sum(len(f"{h} {b}".split()) for h, b in sections if h != SEASON)


# ── The advanced page's words (moved from species_page.py, V3.26) ──────────

def _conditions(entry: dict) -> str:
    """Sun and water as words. The raw fields are comma-delimited snake_case
    ("full_sun,partial_shade"); `labels_csv` is the renderer the list rows use,
    so the two cannot disagree about what a condition is called."""
    from src.plant_list_view import _SUN_LABELS, _WATER_LABELS, labels_csv
    sun = labels_csv((entry.get("sun") or "").replace(" ", "_"), _SUN_LABELS)
    water = labels_csv(entry.get("water") or "", _WATER_LABELS)
    out = []
    if sun and sun != "—":
        out.append(sun)
    if water and water != "—":
        out.append(f"{water} water")
    return " · ".join(out)


def _bloom_colour_line(entry: dict) -> str:
    """"Purple flowers (not verified, a genus-level estimate)" (V2.48). The
    provenance rides along because the colour was seeded per genus."""
    label = (entry.get("bloom_colour_label") or "").strip()
    if not label:
        return ""
    note = (entry.get("bloom_colour_note") or "").strip()
    # The grasses' label is already a full phrase.
    head = label if entry.get("bloom_colour") == "straw" else f"{label} flowers"
    return head + (f" ({note})" if note else "")


def _colour_word(value, what: str) -> str:
    """Colour fields hold a name or a hex triplet; the hex drives the 3D bloom
    and is meaningless on a page. Print names, drop codes."""
    text = (value or "").strip()
    if not text or text.startswith("#"):
        return ""
    return f"{text} {what}"


def _metres(value, word: str) -> str:
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        return ""
    return f"{v:g} m {word}" if v else ""


def _apart(value) -> str:
    """The spacing in the words the buy list and the planting map's key use
    (V3.19, QF-9): one number, printed one way."""
    from src.planting_spacing import spacing_words           # noqa: PLC0415
    words = spacing_words(value)
    return f"{words} apart" if words else ""


def _years(value) -> str:
    try:
        v = int(value or 0)
    except (TypeError, ValueError):
        return ""
    return f"mature in {v} year{'s' if v != 1 else ''}" if v else ""
