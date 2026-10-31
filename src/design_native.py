"""
design_native.py — what "native" means for one design (V3.25, ED-9 and
ED-17; docs/homeowner/08-edmonton-edition.md §2, rows 28–30).

Design principle P2 — see docs/DESIGN_PHILOSOPHY.md.

Until V3.25 twelve modules asked ``native_to_alberta``, so a Regina design
scored nine Saskatchewan-only natives as not native and ninety-eight plants
native only west of the 110th meridian as native (EDF-6), and an Edmonton
design gave full credit to Canada Goldenrod, native to the province and not
to the city. The owner's answer E5: count the region's own list. So a design
asks here, with its site:

* a pin in a region pack, or no pin: native around that pack's place
  (``native_here.native_names``), the reviewed list the picker, the
  communities and the generator already use;
* a pin elsewhere in Alberta or Saskatchewan: native to that province, as
  VASCAN records it (``native_here.native_in``);
* a pin outside both: native to Alberta, the catalogue's own frame, because
  the app knows no list for the place and says so in Site Info.

Qt-free.
"""

from __future__ import annotations

from typing import Callable, Mapping, Optional

from src.native_here import PROVINCE_NAMES, native_in, native_names


def _where(site_config: Optional[Mapping]):
    from src import region                                   # noqa: PLC0415
    sc = site_config or {}
    cov = region.coverage(sc.get("latitude"), sc.get("longitude"))
    if cov.kind == region.REGION:
        return "place", cov.region
    if cov.kind == region.PROVINCE:
        return "province", cov.province
    if cov.kind == region.NO_PIN:
        return "place", region.default()
    return "province", "AB"


def rule(site_config: Optional[Mapping] = None) -> Callable[[Mapping], bool]:
    """``plant row -> bool``: whether the plant counts as native for a design
    at ``site_config``'s pin. A row needs ``scientific_name`` (for a region's
    list) or ``native_provinces`` (for a province)."""
    kind, where = _where(site_config)
    if kind == "place":
        try:
            names = native_names(where.key)
        except ValueError:
            names = None
        if names is not None:
            return lambda row: ((row or {}).get("scientific_name")
                                or "").strip() in names
        where = where.province
    province = where
    return lambda row: native_in(row or {}, province)


def is_native(plant: Mapping, site_config: Optional[Mapping] = None) -> bool:
    return rule(site_config)(plant)


def words(site_config: Optional[Mapping] = None) -> str:
    """How a page says it: "native around Edmonton", "native to
    Saskatchewan"."""
    kind, where = _where(site_config)
    if kind == "place":
        return f"native around {where.short}"
    return f"native to {PROVINCE_NAMES.get(where, where)}"
