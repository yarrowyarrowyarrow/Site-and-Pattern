"""
static_site_around.py — the website's page for a native-area list: what the
list rests on, counted from the list itself, and what it leaves off (F220).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

Split out of :mod:`src.static_site_regions` in V3.13. That module sat at 318 of
its 320 lines when the owner's answers made one of this page's sentences false.
It said "49 left off on review despite their specimens", but most of the 49
had one collection or none: the sentence dated from when only a documented
species could be ruled out. The regions module draws places. This one states
a list's evidence, and it will grow with a second place before they do.
"""

from __future__ import annotations

from src.static_site_render import _esc, _up


def around_extra(hub: dict, page: dict, model: dict) -> str:
    """What the list rests on, and the species it cannot settle yet, by name.

    The cards below are what the evidence or a review puts on the list. What
    it leaves out is not all foreign to the place: pin cherry has one collection
    and 189 observations. Naming those is the difference between a list and a
    claim about everything that is not on it (P9).
    """
    from src.local_flora import is_native                    # noqa: PLC0415
    from src.native_here import entry, places                # noqa: PLC0415
    place = places().get(page["value"])
    if not place:
        return ""
    up = _up(hub["dir"].count("/") + 2)
    count = dict.fromkeys(("listed", "review_in", "review_out",
                           "out_documented", "unrecorded"), 0)
    waiting = []
    for e in model["species"]:
        got = entry(e["row"].get("scientific_name") or "", page["value"])
        ruled_out = got.get("ruling") == "not_native"
        count["listed"] += is_native(got)
        count["review_in"] += got.get("ruling") == "native"
        count["review_out"] += ruled_out
        count["out_documented"] += ruled_out and got.get("tier") == "documented"
        count["unrecorded"] += got.get("tier") == "unrecorded"
        if got.get("tier") in ("thin", "observed") and not got.get("ruling"):
            waiting.append(f'<a href="{up}plants/{_esc(e["slug"])}/">'
                           f'{_esc(e["name"])}</a>')
    radius = f'{float(place["radius_km"]):g} km'
    floor = place["min_collections"]
    parts = [f'{count["listed"] - count["review_in"]} documented by at least '
             f'{floor} herbarium collections within {radius}']
    if count["review_in"]:
        parts.append(f'{count["review_in"]} confirmed on review')
    text = f'{count["listed"]} species on this list: {"; ".join(parts)}.'
    if count["review_out"]:
        text += f' {count["review_out"]} more were left off on review'
        if count["out_documented"]:
            text += (f', {count["out_documented"]} of them despite at least '
                     f'{floor} collections')
        text += '.'
    text += (f' {count["unrecorded"]} species native elsewhere in Alberta have '
             f'no record within {radius} at all.')
    lines = [f'<p>{text}</p>']
    if waiting:
        lines.append(f'<details><summary>{len(waiting)} recorded around '
                     f'{_esc(place["short"])} too thinly to settle, waiting '
                     f'for review</summary><p>{", ".join(waiting)}</p>'
                     '</details>')
    lines.append(f'<p><a href="{up}method/#around">How this list is '
                 'decided</a></p>')
    return "\n".join(lines)
