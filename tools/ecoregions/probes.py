"""The point probes, and what each one is actually testing.

A city is cheap, unambiguous ground truth: if the polygon under Regina is not
Moist Mixed Grassland, the layer is wrong no matter how good the render looks.

Every entry here traces to a specific defect in one of the two earlier attempts
at this map, named in the ``tests`` column. Keeping the defect attached to the
probe is the point — a probe whose reason nobody remembers is the first one
somebody relaxes when it fails.

**These expectations are claims, and stage 4 treats them as such.** If a probe
fails, the honest outcomes are "the data is wrong" or "this expectation is
wrong", and the validator reports which polygon it actually landed in so a human
can decide. It never edits the expectation to make the run go green; the brief
is explicit about that, and it is the exact failure mode that produced the map
this pipeline is replacing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Probe:
    place: str
    lat: float
    lon: float
    #: Expected ELC ecoregion name. Verified against the real attribute table in
    #: stage 2 before stage 4 is trusted.
    ecoregion: str
    #: What this probe is here to catch.
    tests: str
    #: Expected Alberta subregion, where the point is in Alberta and the
    #: subregion is the thing under test. Empty otherwise.
    ab_subregion: str = ""


PROBES: tuple = (
    Probe("Prince Albert", 53.2033, -105.7531, "Boreal Transition",
          "parkland was pushed too far north in Saskatchewan"),
    Probe("Fort McMurray", 56.7264, -111.3803, "Mid-Boreal Uplands",
          "Boreal Plains, not Shield"),
    Probe("Stony Rapids", 59.2553, -105.8342, "Selwyn Lake Upland",
          "the Taiga Shield exists at all"),
    Probe("Uranium City", 59.5678, -108.6089, "Athabasca Plain",
          "the Boreal Shield exists at all"),
    Probe("La Ronge", 55.1006, -105.2842, "Churchill River Upland",
          "the Boreal Shield exists at all"),
    Probe("Hinton", 53.4114, -117.5858, "Western Alberta Upland",
          "the Foothills are forest, not 'Foothills Grasslands'"),
    Probe("Grande Prairie", 55.1707, -118.7947, "Peace Lowland",
          "the Peace River Parkland island"),
    Probe("Edmonton", 53.5461, -113.4938, "Aspen Parkland",
          "the parkland arc"),
    Probe("Saskatoon", 52.1332, -106.6700, "Moist Mixed Grassland",
          "the moist grassland arc"),
    Probe("Regina", 50.4452, -104.6189, "Moist Mixed Grassland",
          "Regina belongs to the moist arc, not the dry unit"),
    Probe("Medicine Hat", 50.0405, -110.6764, "Mixed Grassland",
          "the driest ground in Canada is its own subregion",
          ab_subregion="Dry Mixedgrass"),
    Probe("Lethbridge", 49.6956, -112.8451, "Mixed Grassland",
          "the southern grassland"),
    Probe("Maple Creek", 49.9111, -109.4772, "Cypress Upland",
          "Cypress Hills is a real unit, not part of the surrounding plain"),
    Probe("Banff", 51.1784, -115.5708, "Northern Continental Divide",
          "the mountains are present and are their own ecozone"),
)

#: Alberta must resolve to at least this many distinct grassland subregions.
#: The 2006 classification has four: Dry Mixedgrass, Mixedgrass, Foothills
#: Fescue and Northern Fescue. An attempt that collapses them into one orange
#: blob has lost the distinction the layer exists to carry.
MIN_AB_GRASSLAND_SUBREGIONS = 4

#: Names that must not appear on any polygon. "Foothills Grasslands" is not a
#: unit in either framework; it was invented by the second attempt, merging
#: Alberta's *forested* Foothills natural region with a small southwestern
#: grassland subregion.
FORBIDDEN_NAMES = ("Foothills Grasslands", "Foothills Grassland")
