"""Stage 4 — turn every correction into a test. Failures are blocking.

    python -m tools.ecoregions.validate

Runs the point probes and the structural checks against ``out/ecoregions.gpkg``
and exits non-zero on any failure.

WHY FAILURES ARE BLOCKING
-------------------------------------------------------------------------------
Because the layer this replaces looked fine. Both earlier attempts produced maps
that a reader would have trusted — the second one especially, which had a
hillshade, a legend and city labels sitting on top of geometry that was invented.
Polish is not evidence. These checks are the evidence, and a check that can be
relaxed to make a run go green is not one.

If a probe fails, this reports which polygon the point actually landed in and
stops. It never rewrites the expectation. The expectation might well be the
thing that is wrong — the brief's own probe list was written before anybody had
seen the real attribute table — but that is a decision for a human looking at
the evidence, not something a pipeline should quietly do to itself.
"""

from __future__ import annotations

import argparse
import sys

from tools.ecoregions.common import CRS_PROJECTED, CRS_WGS84, OUT, require
from tools.ecoregions.harmonize import GPKG
from tools.ecoregions.probes import (FORBIDDEN_NAMES,
                                     MIN_AB_GRASSLAND_SUBREGIONS, PROBES)

#: Combined area of Alberta and Saskatchewan, square kilometres, from Statistics
#: Canada: 661 848 + 651 036. The union of the classified polygons has to land
#: near this, which catches both a hole (the union comes in low) and
#: double-counting from overlapping polygons (it comes in high).
_SUBJECT_AREA_KM2 = 661_848 + 651_036
_AREA_TOLERANCE = 0.02          # 2 per cent

#: Words that mark a grassland subregion in Alberta's 2006 vocabulary.
_GRASSLAND_TOKENS = ("grassland", "mixedgrass", "fescue", "grass")


class Result:
    """Accumulates checks so one run reports everything, not just the first."""

    def __init__(self) -> None:
        self.rows: list = []

    def add(self, ok: bool, name: str, detail: str = "") -> None:
        self.rows.append((ok, name, detail))

    @property
    def failed(self) -> list:
        return [r for r in self.rows if not r[0]]

    def report(self) -> None:
        for ok, name, detail in self.rows:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
            if detail:
                for line in detail.splitlines():
                    print(f"         {line}")


def _check_probes(regions, result: Result) -> None:
    from shapely.geometry import Point

    for probe in PROBES:
        point = Point(probe.lon, probe.lat)
        hits = regions[regions.geometry.contains(point)]
        if hits.empty:
            result.add(False, f"probe {probe.place}",
                       f"falls in no polygon at all\n"
                       f"expected {probe.ecoregion!r} ({probe.tests})")
            continue
        got = str(hits.iloc[0]["ecoregion"])
        if got == probe.ecoregion:
            result.add(True, f"probe {probe.place} -> {got}")
            continue
        result.add(False, f"probe {probe.place}",
                   f"expected {probe.ecoregion!r}\n"
                   f"got      {got!r}\n"
                   f"tests    {probe.tests}\n"
                   f"This is either bad data or a bad expectation. Both are\n"
                   f"real possibilities; decide with the evidence, and if the\n"
                   f"expectation is wrong change it in probes.py and say why.")
        if probe.ab_subregion:
            sub = str(hits.iloc[0].get("ab_subregion") or "")
            result.add(sub == probe.ab_subregion,
                       f"probe {probe.place} subregion",
                       "" if sub == probe.ab_subregion else
                       f"expected {probe.ab_subregion!r}, got {sub!r}")


def _check_coverage(regions, result: Result) -> None:
    metric = regions.to_crs(CRS_PROJECTED)
    union_km2 = metric.geometry.union_all().area / 1e6
    sum_km2 = metric.geometry.area.sum() / 1e6
    drift = abs(union_km2 - _SUBJECT_AREA_KM2) / _SUBJECT_AREA_KM2
    result.add(
        drift <= _AREA_TOLERANCE,
        "coverage matches Alberta + Saskatchewan",
        "" if drift <= _AREA_TOLERANCE else
        f"union is {union_km2:,.0f} km2, expected about "
        f"{_SUBJECT_AREA_KM2:,.0f} km2 ({drift:.1%} out)\n"
        f"low means a hole somewhere, high means the clip let something in")
    overlap = sum_km2 - union_km2
    result.add(
        overlap / union_km2 <= 0.005, "polygons do not overlap each other",
        "" if overlap / union_km2 <= 0.005 else
        f"the parts sum to {sum_km2:,.0f} km2 but their union is "
        f"{union_km2:,.0f} km2, so {overlap:,.0f} km2 is claimed twice.\n"
        f"A point in two ecoregions is a topology defect, not a result.")


def _check_topology(regions, result: Result) -> None:
    from shapely.validation import explain_validity

    bad = [(str(row["ecoregion"]), explain_validity(row.geometry))
           for _, row in regions.iterrows() if not row.geometry.is_valid]
    result.add(not bad, "every polygon is topologically valid",
               "" if not bad else
               "\n".join(f"{name}: {why}" for name, why in bad[:8]))


def _check_names(regions, result: Result) -> None:
    names = {str(v) for v in regions["ecoregion"].dropna().unique()}
    offenders = [n for n in names
                 if any(bad.lower() in n.lower() for bad in FORBIDDEN_NAMES)]
    result.add(not offenders, "no invented unit names",
               "" if not offenders else
               f"{offenders} is not a unit in either framework")

    if "ab_subregion" not in regions.columns:
        return
    subs = {str(v) for v in regions["ab_subregion"].dropna().unique() if str(v)}
    grass = {s for s in subs
             if any(t in s.lower() for t in _GRASSLAND_TOKENS)}
    result.add(
        len(grass) >= MIN_AB_GRASSLAND_SUBREGIONS,
        f"Alberta resolves at least {MIN_AB_GRASSLAND_SUBREGIONS} "
        f"grassland subregions",
        "" if len(grass) >= MIN_AB_GRASSLAND_SUBREGIONS else
        f"found {len(grass)}: {sorted(grass)}\n"
        f"Collapsing Dry Mixedgrass, Mixedgrass, Foothills Fescue and\n"
        f"Northern Fescue into one unit loses the distinction that decides\n"
        f"which grasses belong on a site in Brooks versus one in Camrose.")


def _check_crs(regions, result: Result) -> None:
    result.add(regions.crs is not None and regions.crs.to_string() == CRS_WGS84,
               f"stored in {CRS_WGS84}",
               "" if regions.crs is not None else "no CRS on the layer")


def run() -> int:
    require("geopandas", "shapely")
    import geopandas as gpd

    if not GPKG.exists():
        raise SystemExit(
            f"{GPKG} does not exist.\n"
            "  Run:  python -m tools.ecoregions.harmonize")
    regions = gpd.read_file(GPKG, layer="ecoregions")

    print("=" * 74)
    print("  VALIDATION - failures here are blocking")
    print("=" * 74)
    print()
    result = Result()
    _check_crs(regions, result)
    _check_topology(regions, result)
    _check_coverage(regions, result)
    _check_names(regions, result)
    _check_probes(regions, result)
    result.report()

    print()
    if result.failed:
        print(f"{len(result.failed)} of {len(result.rows)} checks failed. "
              f"Nothing downstream should use this build.")
        print("Fix the data. Do not relax the test.")
        return 1
    print(f"All {len(result.rows)} checks passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.parse_args(argv)
    return run()


if __name__ == "__main__":
    sys.exit(main())
