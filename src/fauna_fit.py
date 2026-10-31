"""
fauna_fit.py — has this animal been recorded near this yard? (F190, V3.37;
docs/plans/V3.37-animals-that-belong-here.md)

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

The animals carried no range. The three ptarmigans eat bearberry, bog
blueberry and alpine bistort, which grow in yards too, so the 3D preview drew
them in 28% of simulated Edmonton designs (V2.97). Plants gained a locality
check in V2.85 (``site_fit``); this is the animals' one, read from two GBIF
counts the region pack keeps for every catalogue animal
(``data/regions/<key>/animal_records.json``, written by
``scripts/derive_animals_here.py``): its records **within the pack's circle**
(50 km of downtown Edmonton, the circle the Edmonton plant list uses) and
**across the pack's province**.

Four answers:

* ``here``: recorded near the place.
* ``stray``: recorded near it, but a hundred times less often than its records
  across the province predict: the Calliope Hummingbird, 2 records near
  Edmonton and 25,977 in Alberta.
* ``elsewhere``: never recorded near the place, where that absence is telling:
  the White-tailed Ptarmigan, 1,955 Alberta records and none near Edmonton.
* ``unrecorded``: nothing worth reading either way. Few people record solitary
  bees, so a bee with none near Edmonton and 40 across Alberta is *unknown*,
  never *absent* (P9).

**What "predict" means.** An animal's province records times the share of its
group's province records that fall near the place: 11.8% of Alberta's bird
records are near Edmonton, so a bird with 1,000 Alberta records is expected
near Edmonton about 118 times. The shares are computed from the file, never
written down. Absence is telling when the expected count is at least
``ABSENT_EXPECTED``, or when the group is recorded so heavily near the place
that a regular visitor cannot go unrecorded (``SATURATED`` records an animal:
birds 15,888 near Edmonton, the next group 70). The second is what keeps the
Rock Ptarmigan out: three Alberta records, none near Edmonton, among 778,488
bird records there.

**A count is of records, not animals.** It measures where people look as well
as where animals live, which is why the rule compares an animal with its own
group, and why few records is never read as rare.

A yard outside every pack has no counts, and every animal reads
``unrecorded``: the app shows what it showed before rather than borrow another
place's numbers.

Qt-free.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional

HERE, STRAY, ELSEWHERE, UNRECORDED = "here", "stray", "elsewhere", "unrecorded"
BANDS = (HERE, STRAY, ELSEWHERE, UNRECORDED)
#: The answers the 3D preview draws an animal for: recorded near the place, or
#: not known either way (P9: unknown is not absent).
DRAWN = frozenset({HERE, UNRECORDED})

#: Never recorded near the place is *elsewhere* once the province's records
#: predict at least this many near it. Under even chance that would be no
#: record once in twenty thousand designs; records come in clumps (one survey,
#: one keen observer), so the margin is wide on purpose.
ABSENT_EXPECTED = 10.0
#: Recorded near the place less than this share of what its province records
#: predict is *stray*: a hundred times rarer here than across the province.
STRAY_SHARE = 0.01
#: A group with at least this many records near the place for each of its
#: catalogue animals is recorded so heavily that a regular visitor cannot be
#: missed: none near the place is *elsewhere* whatever the province count.
SATURATED = 1000.0

VERSION = 1


@dataclass(frozen=True)
class Records:
    """One pack's counts, and the rule over them."""
    key: str
    province: str
    radius_km: float
    fetched: str
    #: ``scientific_name -> (group, near, province)``.
    animals: Mapping[str, tuple] = field(default_factory=dict)

    @functools.cached_property
    def shares(self) -> dict:
        """``group -> share``: of the group's province records, the share that
        falls near the place."""
        near, prov = {}, {}
        for group, n, p in self.animals.values():
            near[group] = near.get(group, 0) + n
            prov[group] = prov.get(group, 0) + p
        return {g: (near[g] / prov[g] if prov[g] else 0.0) for g in near}

    @functools.cached_property
    def per_animal(self) -> dict:
        """``group -> records near the place for each catalogue animal``."""
        near, count = {}, {}
        for group, n, _p in self.animals.values():
            near[group] = near.get(group, 0) + n
            count[group] = count.get(group, 0) + 1
        return {g: near[g] / count[g] for g in near}

    @functools.cached_property
    def medians(self) -> dict:
        """``group -> the middle near count of its animals recorded here``."""
        counts: dict = {}
        for name, (group, n, _p) in self.animals.items():
            if self.band(name) == HERE:
                counts.setdefault(group, []).append(n)
        return {g: sorted(c)[len(c) // 2] for g, c in counts.items()}

    def familiar(self, name: str) -> bool:
        """Recorded near the place at least as often as the middle of its
        group's animals that are (F249's measure until the owner's list): how
        often somebody stopped to record it is what familiar means here."""
        row = self.animals.get((name or "").strip())
        return (row is not None and self.band(name) == HERE
                and row[1] >= self.medians.get(row[0], 0))

    def near(self, name: str) -> Optional[int]:
        """Records near the place, or ``None`` when the animal was not
        counted (a failure is not an absence)."""
        row = self.animals.get((name or "").strip())
        return None if row is None else row[1]

    def expected(self, name: str) -> float:
        """Records near the place that its province records predict."""
        row = self.animals.get((name or "").strip())
        if row is None:
            return 0.0
        group, _n, prov = row
        return prov * self.shares.get(group, 0.0)

    def band(self, name: str) -> str:
        row = self.animals.get((name or "").strip())
        if row is None:
            return UNRECORDED
        group, n, _prov = row
        expected = self.expected(name)
        if n == 0:
            if (expected >= ABSENT_EXPECTED
                    or self.per_animal.get(group, 0.0) >= SATURATED):
                return ELSEWHERE
            return UNRECORDED
        if n < STRAY_SHARE * expected:
            return STRAY
        return HERE

    def drawn(self, name: str) -> bool:
        return self.band(name) in DRAWN


def from_doc(doc: Mapping, key: str = "") -> Records:
    """:class:`Records` from a file's contents. Raises ``ValueError`` on a
    file this module did not write."""
    if not isinstance(doc, Mapping) or doc.get("version") != VERSION:
        raise ValueError(f"animal records must be version {VERSION}")
    animals = {}
    for name, row in (doc.get("animals") or {}).items():
        try:
            group, n, p = row["group"], int(row["near"]), int(row["province"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{name}: {exc}") from None
        if n < 0 or p < 0 or not group:
            raise ValueError(f"{name}: counts must be 0 or more, with a group")
        animals[name] = (str(group), n, p)
    return Records(key=key or str(doc.get("key") or ""),
                   province=str(doc.get("province") or ""),
                   radius_km=float(doc.get("radius_km") or 0),
                   fetched=str(doc.get("fetched") or ""), animals=animals)


def dumps(doc: Mapping) -> str:
    """The file's text, as ``derive_animals_here.py`` writes it."""
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


_override: Optional[dict] = None


def set_records(packs: Optional[dict]) -> None:
    """Tests: use ``packs`` (``{key: Records or None}``) instead of the
    shipped files; ``None`` goes back to the files."""
    global _override
    _override = None if packs is None else dict(packs)


@functools.lru_cache(maxsize=None)
def _shipped(key: str) -> Optional[Records]:
    from src import region                                   # noqa: PLC0415
    try:
        with open(region.animal_records_path(key), encoding="utf-8") as fh:
            return from_doc(json.load(fh), key)
    except FileNotFoundError:
        return None


def records(key: str) -> Optional[Records]:
    """The pack's counts, or ``None`` when it has none yet."""
    if _override is not None:
        return _override.get(key)
    return _shipped(key)


def for_point(lat=None, lng=None) -> Optional[Records]:
    """The counts for a yard: the pack holding the pin, the default pack with
    no pin (as ``design_native``), ``None`` anywhere else."""
    from src import region                                   # noqa: PLC0415
    cov = region.coverage(lat, lng)
    if cov.kind == region.REGION:
        return records(cov.region.key)
    if cov.kind == region.NO_PIN:
        return records(region.default().key)
    return None


def rule(lat=None, lng=None) -> Callable[[str], str]:
    """``scientific_name -> band`` for a yard at ``lat, lng``."""
    recs = for_point(lat, lng)
    if recs is None:
        return lambda _name: UNRECORDED
    return recs.band
