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

from tools.ecoregions.common import (CRS_PROJECTED, CRS_WGS84, OUT,
                                     REPO, require)
from tools.ecoregions.harmonize import GPKG
from tools.ecoregions.probes import (FORBIDDEN_NAMES,
                                     MIN_AB_GRASSLAND_SUBREGIONS, PROBES,
                                     REQUIRED_ECOREGIONS, REQUIRED_ECOZONES)

#: Combined area of Alberta and Saskatchewan, square kilometres, from Statistics
#: Canada: 661 848 + 651 036. The union of the classified polygons has to land
#: near this, which catches both a hole (the union comes in low) and
#: double-counting from overlapping polygons (it comes in high).
_SUBJECT_AREA_KM2 = 661_848 + 651_036
_AREA_TOLERANCE = 0.02          # 2 per cent

#: OKLab deltaE x100 under simulated colour-vision deficiency. The documented
#: floor for categorical fills, legal at this value only when a second channel
#: carries the same distinction - which is what the hatch is for.
_CVD_FLOOR = 8.0

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
    """Each probe asserts up to three things, and all three always run.

    The first version put the subregion check after a ``continue`` in the
    ecoregion success branch, so it only ever ran when the ecoregion had already
    failed — every subregion expectation on a passing probe was silently
    skipped. A check that only runs when another check fails is not a check.
    """
    from shapely.geometry import Point

    for probe in PROBES:
        point = Point(probe.lon, probe.lat)
        hits = regions[regions.geometry.contains(point)]
        if hits.empty:
            result.add(False, f"probe {probe.place}",
                       f"falls in no polygon at all\n"
                       f"expected {probe.ecoregion!r} ({probe.tests})")
            continue
        row = hits.iloc[0]

        got = str(row["ecoregion"])
        result.add(got == probe.ecoregion,
                   f"probe {probe.place} -> {got}",
                   "" if got == probe.ecoregion else
                   f"expected {probe.ecoregion!r}\n"
                   f"got      {got!r}\n"
                   f"tests    {probe.tests}\n"
                   f"This is either bad data or a bad expectation. Both are\n"
                   f"real possibilities; decide with the evidence, and if the\n"
                   f"expectation is wrong change it in probes.py and say why.")

        if probe.ecozone:
            zone = str(row.get("ecozone") or "")
            result.add(zone == probe.ecozone,
                       f"probe {probe.place} ecozone -> {zone or 'blank'}",
                       "" if zone == probe.ecozone else
                       f"expected ecozone {probe.ecozone!r}, got {zone!r}\n"
                       f"The ecozone is usually what a probe is really\n"
                       f"defending; a wrong one is a bigger deal than a wrong\n"
                       f"ecoregion inside the right system.")

        if probe.ab_subregion:
            sub = str(row.get("ab_subregion") or "")
            result.add(sub == probe.ab_subregion,
                       f"probe {probe.place} subregion -> {sub or 'blank'}",
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


def _check_required_units(regions, result: Result) -> None:
    """Does the layer contain these units at all.

    Separate from the point probes on purpose. A probe conflates "does this
    exist" with "is this spot in it", and the Cypress Upland probe failed on the
    second while the first was true the whole time — Maple Creek is a town at
    the foot of the hills, not on the plateau.
    """
    have_regions = {str(v) for v in regions["ecoregion"].dropna().unique()}
    missing = [n for n in REQUIRED_ECOREGIONS if n not in have_regions]
    result.add(not missing, "every required ecoregion is present",
               "" if not missing else
               f"absent from the layer: {missing}\n"
               f"present: {sorted(have_regions)}")

    have_zones = {str(v) for v in regions.get(
        "ecozone", regions["ecoregion"]).dropna().unique()}
    gone = [n for n in REQUIRED_ECOZONES if n not in have_zones]
    result.add(not gone, "every required ecozone is present",
               "" if not gone else
               f"absent from the layer: {gone}\n"
               f"present: {sorted(have_zones)}\n"
               f"A missing Shield ecozone is the largest single error the "
               f"earlier attempts made.")


def _check_colour_separation(regions, result: Result) -> None:
    """Two ecoregions that share a border must be tellable apart.

    The same rule ``tests/test_ecoregion.py`` holds for the website's six-key
    palette, applied to the ELC classification's twenty-four — and computed
    against the real adjacency graph rather than every possible pair, because
    Mixed Grassland and Selwyn Lake Upland are eight hundred kilometres apart
    and a separation budget spent on them is wasted.

    Failures here name the pairs. The fix is to re-step one of the two colours
    in ``ECOZONE_COLOUR``, or to add one of them to ``HATCHED`` - never to lower
    the floor.
    """
    import sys as _sys

    _sys.path.insert(0, str(REPO))
    from src.colour_distance import worst_cvd_delta_e            # noqa: PLC0415
    from src.ecoregion_palette import (HATCHED, elc_fill,        # noqa: PLC0415
                                       elc_zone_of)

    metric = regions.to_crs(CRS_PROJECTED)
    by_name: dict = {}
    for name, group in metric.groupby("ecoregion"):
        by_name[str(name)] = group.geometry.union_all()

    names = sorted(by_name)
    touching, thin, same_zone = [], [], []
    for i, one in enumerate(names):
        for two in names[i + 1:]:
            shared = by_name[one].intersection(by_name[two].buffer(50))
            if shared.is_empty or shared.area < 1e5:      # under 0.1 km2
                continue
            touching.append((one, two))
            # Two ecoregions in the SAME ecozone share a hue on purpose - that
            # is the hierarchy the palette encodes, and the step between them
            # cannot be widened without breaking a cross-ecozone boundary that
            # matters more (measured: 0.06 holds everything, 0.10 does not).
            # Inside one system the boundary stroke and the label do the work.
            if elc_zone_of(one) and elc_zone_of(one) == elc_zone_of(two):
                same_zone.append((one, two))
                continue
            gap = worst_cvd_delta_e(elc_fill(one), elc_fill(two))
            if gap < _CVD_FLOOR and one not in HATCHED and two not in HATCHED:
                thin.append((one, two, gap))

    result.add(bool(touching), "the adjacency graph is not empty",
               "" if touching else
               "no two ecoregions were found to share a border, so the colour "
               "check below proves nothing")
    result.add(not thin,
               f"bordering ecoregions in different ecozones separate by colour "
               f"or hatch ({len(touching)} shared borders, {len(same_zone)} of "
               f"them inside one ecozone)",
               "" if not thin else
               "\n".join(f"{a} / {b}: deltaE {g:.1f} under colour-vision "
                          f"deficiency, neither hatched" for a, b, g in thin) +
               "\nRe-step one colour in ECOZONE_COLOUR, or add one of the pair "
               "to HATCHED in src/ecoregion_palette.py.")


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
    _check_required_units(regions, result)
    _check_colour_separation(regions, result)
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
