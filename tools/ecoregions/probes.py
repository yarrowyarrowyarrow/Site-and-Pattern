"""The point probes, and what each one is actually testing.

A city is cheap, unambiguous ground truth: if the polygon under Regina is not
Moist Mixed Grassland, the layer is wrong no matter how good the render looks.

Every entry traces to a specific defect in one of the two earlier attempts at
this map, named in ``tests``. Keeping the defect attached to the probe is the
point — a probe whose reason nobody remembers is the first one somebody relaxes
when it fails.

**These expectations are claims, and the first real run refuted five of them.**
The brief's probe table was written before anyone had seen the ELC attribute
table, and stage 4 reported, for each failure, which polygon the point actually
landed in. Each was then decided on the evidence and the reasoning recorded
below. That is the process the brief asked for — *"if a probe fails because my
expected value is wrong rather than the data, say so and show the evidence"* —
and it is the opposite of editing an expectation until the run goes green.

WHAT CHANGED ON 2026-08-17, AND WHY
-------------------------------------------------------------------------------
Four corrections and one point moved off a probe entirely:

* **Fort McMurray** was expected in Mid-Boreal Uplands; the data puts it in
  Wabasca Lowland. Both are Boreal Plains, and *Boreal Plains rather than
  Shield* is the whole thing this probe was defending. The purpose survives
  intact; only the recollected name was wrong.

* **Stony Rapids and Uranium City were the wrong way round.** Uranium City is on
  the **north** shore of Lake Athabasca and comes back Tazin Lake Upland, in the
  Taiga Shield. Stony Rapids is east of the lake and comes back Athabasca Plain,
  in the Boreal Shield. The brief assigned Athabasca Plain to the town on the
  north shore, which is the one place it cannot be — the Athabasca Plain is the
  sand plain south and east of the lake. Both ecozones are still proven at a
  point, just by the opposite towns.

* **Lethbridge is the one worth arguing about.** The brief expected Mixed
  Grassland and specifically faulted the second attempt for placing the
  Calgary-to-Lethbridge corridor in Moist Mixed Grassland, on the grounds that
  it is arid. The published ELC layer says Moist Mixed Grassland. On this one
  point the criticism was mistaken and the attempt it criticised agreed with the
  source. Recorded rather than smoothed over, because it is also the clearest
  case in the whole layer of the two frameworks genuinely disagreeing: Alberta's
  own classification calls the same ground Mixedgrass. Neither is wrong; they
  are drawn on different criteria. That disagreement is exactly why the
  harmonized layer carries both vocabularies on the same polygon instead of
  picking a winner.

* **Maple Creek is not on the Cypress Hills.** It is a town at the northern foot
  of them, and the data correctly returns Mixed Grassland. The unit itself is
  real and present — the layer resolves Cypress Upland — so proving it exists
  moved to ``REQUIRED_UNITS`` below, which asks the question directly instead of
  through a coordinate. Rather than guess a plateau coordinate and risk a second
  wrong expectation, the probe keeps the town and the honest answer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Probe:
    place: str
    lat: float
    lon: float
    #: Expected ELC ecoregion name, as verified against the real attribute
    #: table on 2026-08-17.
    ecoregion: str
    #: What this probe is here to catch.
    tests: str
    #: Expected ELC ecozone. Usually the probe's real purpose — most of these
    #: exist to prove a *system* is present, and the ecoregion is the detail.
    #: Asserted separately so a renamed or resplit ecoregion cannot quietly
    #: take the ecozone with it.
    ecozone: str = ""
    #: Expected Alberta subregion, where that is the thing under test.
    ab_subregion: str = ""


PROBES: tuple = (
    Probe("Prince Albert", 53.2033, -105.7531, "Boreal Transition",
          "parkland was pushed too far north in Saskatchewan",
          ecozone="Boreal Plains"),
    Probe("Fort McMurray", 56.7264, -111.3803, "Wabasca Lowland",
          "Boreal Plains, not Shield", ecozone="Boreal Plains"),
    Probe("Stony Rapids", 59.2553, -105.8342, "Athabasca Plain",
          "the Boreal Shield reaches the north-east",
          ecozone="Boreal Shield"),
    Probe("Uranium City", 59.5678, -108.6089, "Tazin Lake Upland",
          "the Taiga Shield exists at all", ecozone="Taiga Shield"),
    Probe("La Ronge", 55.1006, -105.2842, "Churchill River Upland",
          "the Boreal Shield exists at all", ecozone="Boreal Shield"),
    # No subregion expectation: Hinton sits near the Lower/Upper Foothills
    # boundary and I do not know which side without looking, which is the exact
    # thing this file is not for. The ecoregion and ecozone carry the point the
    # probe exists to make, which is that the Foothills are forest.
    Probe("Hinton", 53.4114, -117.5858, "Western Alberta Upland",
          "the Foothills are forest, not 'Foothills Grasslands'",
          ecozone="Boreal Plains"),
    Probe("Grande Prairie", 55.1707, -118.7947, "Peace Lowland",
          "the Peace River Parkland island", ecozone="Boreal Plains",
          ab_subregion="Peace River Parkland"),
    Probe("Edmonton", 53.5461, -113.4938, "Aspen Parkland",
          "the parkland arc", ecozone="Prairies",
          ab_subregion="Central Parkland"),
    Probe("Saskatoon", 52.1332, -106.6700, "Moist Mixed Grassland",
          "the moist grassland arc", ecozone="Prairies"),
    Probe("Regina", 50.4452, -104.6189, "Moist Mixed Grassland",
          "Regina belongs to the moist arc, not the dry unit",
          ecozone="Prairies"),
    Probe("Medicine Hat", 50.0405, -110.6764, "Mixed Grassland",
          "the driest ground in Canada is its own subregion",
          ecozone="Prairies", ab_subregion="Dry Mixedgrass"),
    Probe("Lethbridge", 49.6956, -112.8451, "Moist Mixed Grassland",
          "the southern grassland; see the module docstring, this one "
          "contradicts the brief and the source won",
          ecozone="Prairies"),
    Probe("Maple Creek", 49.9111, -109.4772, "Mixed Grassland",
          "a town at the foot of the Cypress Hills is on the plain, not the "
          "plateau; the plateau itself is checked by REQUIRED_UNITS",
          ecozone="Prairies"),
    Probe("Banff", 51.1784, -115.5708, "Northern Continental Divide",
          "the mountains are present and are their own ecozone",
          ecozone="Montane Cordillera"),
)

#: Units that must exist somewhere in the layer, asked directly rather than
#: through a coordinate.
#:
#: A point probe conflates two questions — "does this unit exist" and "is this
#: particular spot in it" — and Maple Creek showed what that costs: the Cypress
#: Upland probe failed while Cypress Upland was sitting in the output the whole
#: time, because the town is at the foot of the hills rather than on them. When
#: the question is really about presence, ask about presence.
REQUIRED_ECOREGIONS = (
    "Cypress Upland",           # the outlier plateau, absent from both attempts
    "Aspen Parkland",
    "Moist Mixed Grassland",
    "Mixed Grassland",
    "Peace Lowland",            # the Peace River parkland island
    "Boreal Transition",
)

#: The ecozones that have to be present. Attempt B drew northern Saskatchewan
#: and Alberta's north-east corner as undifferentiated boreal plain when they
#: are Precambrian bedrock, thin soils, jack pine and lichen. That was the
#: largest single error on that map, and this is the check that catches it.
REQUIRED_ECOZONES = (
    "Boreal Shield",
    "Taiga Shield",
    "Boreal Plains",
    "Prairies",
    "Montane Cordillera",
)

#: Alberta must resolve at least this many distinct grassland subregions. The
#: 2006 classification has exactly four: Dry Mixedgrass, Mixedgrass, Foothills
#: Fescue and Northern Fescue.
#:
#: The first real run found three, which was a defect in the pipeline rather
#: than in the data: subregions were attached by largest overlap, so with
#: twenty-one of them competing for twenty-four ELC polygons the small ones
#: never won and Northern Fescue vanished. Fixed by intersecting instead of
#: joining (``harmonize._split_by_subregion``). Worth leaving this comment
#: attached: the check did not catch bad data, it caught bad code, which is the
#: more common case and the easier one to explain away.
MIN_AB_GRASSLAND_SUBREGIONS = 4

#: Names that must not appear on any polygon. "Foothills Grasslands" is not a
#: unit in either framework; it was invented by the second attempt, merging
#: Alberta's *forested* Foothills natural region with a small southwestern
#: grassland subregion. The real source confirms the point: Alberta's NRNAME
#: has "Foothills" containing Lower and Upper Foothills, both forest.
FORBIDDEN_NAMES = ("Foothills Grasslands", "Foothills Grassland")
