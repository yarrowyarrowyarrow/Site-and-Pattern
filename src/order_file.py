"""
src/order_file.py — an order file a nursery accepts (F92, V2.57).

Design principle P8 (repair is more sophisticated than creation — a design that
never gets planted repairs nothing) — see docs/DESIGN_PHILOSOPHY.md.

F40 produces the buy list as prose and as a PDF page, which is the right thing
for a document somebody reads. It is the wrong thing for the next step, which is
not reading: it is **attaching a file to an email to a nursery**, or pasting it
into a purchase order. That last centimetre between a design and an actual
transaction has never existed, and it is the least glamorous and most load-
bearing part of the professional workflow.

Everything here is computed already and simply never joined:

* :func:`src.planting_map.build_planting_map` numbers the plants and gives each
  a botanical name, a form and a quantity — and the numbers are the **same
  numbers** as on the planting drawing, which is what makes the two documents
  usable together on site;
* :func:`src.sourcing.plant_price_range` gives the money;
* :func:`src.db.nurseries.nurseries_for_availability` matches a plant's
  ``availability_class`` to suppliers near the property, and
  :func:`src.db.nurseries.access_label` says how to reach each one.

**Grouped by where you can actually get it, not by "supplier".** The obvious
design is one sheet per supplier. The app cannot honestly produce that: there is
**no plant-to-nursery stock data anywhere in it** — no junction table, no feed,
nothing. What it does have is the ``availability_class`` enum, which the schema
introduced for exactly this ("so a supplier can be matched to a plant's
sourcing"): every plant is one of ``native_specialist``, ``seed_or_plug``,
``garden_centre``, ``big_box`` or ``rare``. So the file groups by channel and
names the real nurseries near the property that carry that channel — which is a
true statement, where "Supplier: Bow Point Nursery" would have been a guess
printed as a fact (P9).

**CSV, and deliberately not XLSX.** The backlog said "CSV/XLSX". CSV is stdlib,
opens in every spreadsheet and every nursery's system, and is what you attach to
an email. XLSX would mean adding ``openpyxl`` — not currently installed, not a
declared dependency, and a new runtime import is exactly the class of change
that has broken the frozen Windows build before. If a real user asks for
formatting the dependency can be added deliberately; guessing that they will is
not worth the packaging risk.

Qt-free: it builds rows and writes text, so the whole thing is testable without
a display and callable from the CLI or the agent API.
"""

from __future__ import annotations

import csv
import io
from typing import Callable, NamedTuple, Optional

#: Column order. Chosen to be read left-to-right by a human at a nursery
#: counter: what it is, how many, what it costs, where to get it.
COLUMNS = (
    "No.", "Botanical name", "Common name", "Form", "Qty",
    "Unit price low (CAD)", "Unit price high (CAD)",
    "Line total low (CAD)", "Line total high (CAD)",
    "Sourcing channel", "Where to try",
)

#: Human labels for the availability enum. The raw values are database tokens
#: and a nursery should never be sent one.
CHANNEL_LABELS = {
    "native_specialist": "Native plant nursery",
    "seed_or_plug": "Seed house / plug grower",
    "garden_centre": "Garden centre",
    "big_box": "Big-box garden department",
    "rare": "Rare — specialist or collector",
    "": "Sourcing channel not recorded",
}

#: Channels in the order they appear in the file: hardest to find first, so the
#: things that need a phone call are at the top rather than buried under the
#: things you can pick up on the way home.
CHANNEL_ORDER = ("rare", "native_specialist", "seed_or_plug",
                 "garden_centre", "big_box", "")


class OrderLine(NamedTuple):
    """One line of the order — one species, with its money and its channel."""
    number: int
    plant_id: int
    scientific_name: str
    common_name: str
    form: str
    qty: int
    unit_low: float
    unit_high: float
    channel: str

    @property
    def total_low(self) -> float:
        return round(self.unit_low * self.qty, 2)

    @property
    def total_high(self) -> float:
        return round(self.unit_high * self.qty, 2)


def build_order_lines(placed_plants: list, project: Optional[dict] = None, *,
                      plan=None, get_plant: Optional[Callable] = None) -> list:
    """One :class:`OrderLine` per species, in planting-map order.

    The numbering comes from :func:`src.planting_map.build_planting_map` rather
    than being generated here, so line 7 on the order is plant 7 on the drawing.
    Two documents that number the same plants differently are worse than one.
    """
    from src.planting_map import build_planting_map
    from src.sourcing import plant_price_range

    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp

    pm = build_planting_map(placed_plants, project, plan=plan,
                            get_plant=get_plant)
    out = []
    for entry in pm.key:
        try:
            row = get_plant(entry.plant_id) or {}
        except Exception:                                  # noqa: BLE001
            row = {}
        low, high = plant_price_range(row)
        out.append(OrderLine(
            number=entry.number,
            plant_id=entry.plant_id,
            scientific_name=(entry.scientific_name
                             or row.get("scientific_name") or ""),
            common_name=entry.common_name or row.get("common_name") or "",
            form=entry.plant_type or row.get("plant_type") or "",
            qty=int(entry.qty or 0),
            unit_low=float(low),
            unit_high=float(high),
            channel=(row.get("availability_class") or "").strip(),
        ))
    return out


def group_by_channel(lines: list) -> list:
    """``[(channel, [line, …]), …]`` in :data:`CHANNEL_ORDER`.

    Channels with nothing in them are dropped — an empty "Big-box" heading tells
    a reader there is something to buy there.
    """
    buckets: dict = {}
    for line in lines:
        buckets.setdefault(line.channel if line.channel in CHANNEL_LABELS
                           else "", []).append(line)
    return [(ch, buckets[ch]) for ch in CHANNEL_ORDER if buckets.get(ch)]


def suppliers_for(channel: str, lat: Optional[float], lng: Optional[float], *,
                  limit: int = 3) -> list:
    """Real nurseries near the property that carry this channel.

    Empty without a property pin — which is honest rather than unhelpful: the
    whole point is *near you*, and a national list dressed up as a local one is
    the kind of false precision this codebase keeps removing.
    """
    if lat is None or lng is None:
        return []
    try:
        from src.db.nurseries import access_label, nurseries_for_availability
        rows = nurseries_for_availability(channel, float(lat), float(lng),
                                          limit=limit)
    except Exception:                                      # noqa: BLE001
        return []
    out = []
    for n in rows or []:
        name = n.get("name") or ""
        where = ""
        try:
            where = access_label(n)
        except Exception:                                  # noqa: BLE001
            pass
        out.append(f"{name} ({where})" if where else name)
    return out


def site_latlng(project: dict) -> tuple:
    """``(lat, lng)`` of the property pin, or ``(None, None)``."""
    try:
        sc = ((project or {}).get("properties") or {}).get("site_config") or {}
        return (sc.get("latitude"), sc.get("longitude"))
    except Exception:                                      # noqa: BLE001
        return (None, None)


def order_totals(lines: list) -> tuple:
    """``(qty, low, high)`` across every line."""
    return (sum(int(l.qty) for l in lines),
            round(sum(l.total_low for l in lines), 2),
            round(sum(l.total_high for l in lines), 2))


def write_csv(lines: list, project: Optional[dict] = None, *,
              stream=None) -> str:
    """The order as CSV text. Writes into ``stream`` when given.

    A blank row and a channel heading separate the groups. That is not
    decoration: it is what lets a designer delete the three groups they are not
    phoning today and send the rest.
    """
    buf = stream if stream is not None else io.StringIO()
    writer = csv.writer(buf)
    lat, lng = site_latlng(project or {})

    writer.writerow(COLUMNS)
    for channel, group in group_by_channel(lines):
        writer.writerow([])
        label = CHANNEL_LABELS.get(channel, CHANNEL_LABELS[""])
        suppliers = suppliers_for(channel, lat, lng)
        writer.writerow([label, "", "", "", "", "", "", "", "",
                         "", "; ".join(suppliers)])
        for line in group:
            writer.writerow([
                line.number, line.scientific_name, line.common_name,
                line.form, line.qty,
                f"{line.unit_low:.2f}", f"{line.unit_high:.2f}",
                f"{line.total_low:.2f}", f"{line.total_high:.2f}",
                label, "",
            ])
    qty, low, high = order_totals(lines)
    writer.writerow([])
    writer.writerow(["TOTAL", "", "", "", qty, "", "",
                     f"{low:.2f}", f"{high:.2f}", "", ""])
    # Said in the file rather than only in the app, because the file is what
    # travels: a price range is an estimate and the reader is about to spend
    # money against it (P9).
    writer.writerow([])
    writer.writerow(["Prices are Alberta retail estimates and vary by nursery, "
                     "year and pot size. Confirm before ordering."])
    return "" if stream is not None else buf.getvalue()


def write_order_file(path: str, lines: list,
                     project: Optional[dict] = None) -> str:
    """Write the CSV to ``path``. Returns the path.

    ``newline=""`` because the :mod:`csv` module does its own line endings, and
    without it every row is double-spaced on Windows — where most of this app's
    users are.
    """
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        write_csv(lines, project, stream=fh)
    return path
