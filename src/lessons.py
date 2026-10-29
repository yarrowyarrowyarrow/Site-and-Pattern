"""
lessons.py — three lessons, a first draft for the owner to rewrite (F88, V3.41).

Design principle P5 (perception is constructed — a guided sequence builds the
model the tool assumes) and P7 (generalist knowledge — the lessons cross
ecology, site and design) — see docs/DESIGN_PHILOSOPHY.md.

The owner, on the four lessons they found: "incredibly basic … unclear what
'teaches against your design' means … a novice doesn't know who Tallamy is …
four one-paragraph AI-sounding lessons. Group the current ones into
'designing for biodiversity'. Add 'Site factors to consider in design' (sun,
shade, moisture, contour …) and 'Aesthetic considerations' (wildscape,
formal/structured, functional/thematic layouts; height; flower and plant
colours). I can rewrite the text but you do a version first."

**All the words are here**, in :data:`LESSONS`, so a rewrite touches nothing
else (D6). Each page is a few short paragraphs, one *Look at it* pointer to a
place in the app, its sources, and the key of a **readout about a landscape
the reader chooses** (a walk, or one of their saved designs), computed by the
functions below. That replaces "your design", which in the Learn window meant
the walk's sandbox.

Rules for the text, kept by ``tests/test_lessons.py``: plain words (the
glossary's: wildflower, not forb); no place typed in (``{place}`` is the
region's name, filled in when shown, as every module must); and nothing about
how anyone uses plants (P12). The old four-step track
(``src.lesson_track``) stays for the scripting API.

Qt-free; every database read is injectable.
"""

from __future__ import annotations

from typing import Callable, Optional

#: (key, title, pages). A page: title, paragraphs, a pointer, sources, and
#: the readout that says what the chosen landscape does.
LESSONS = (
    ("biodiversity", "Designing for biodiversity", (
        {"title": "Some plants feed far more than others",
         "text": (
             "Most of the animals in a yard are insects, and most insects eat "
             "plants. But not all plants are equal. A few kinds of native "
             "plant are food for most of the caterpillars of butterflies and "
             "moths: willows, poplars and aspen, birches, the native cherries, "
             "and among the wildflowers, the goldenrods and asters. In the "
             "records this app holds, a willow or an aspen is food for a "
             "dozen or more kinds of caterpillar, where many garden flowers "
             "are food for none.",
             "Doug Tallamy, an entomologist at the University of Delaware, "
             "spent years counting which plants feed which caterpillars. He "
             "calls the plants that feed the most keystone plants. His books, "
             "Bringing Nature Home and Nature's Best Hope, are where most "
             "people first meet the idea. A design with a few of them does "
             "more than one with many plants that feed little."),
         "look": ("In the walk, click a Trembling Aspen and read how many "
                  "caterpillars it is recorded as food for. Then click a "
                  "grass and compare."),
         "sources": ("Tallamy 2007", "Tallamy 2019"),
         "readout": "keystone"},
        {"title": "Plant, caterpillar, bird",
         "text": (
             "Even birds that eat seeds as adults raise their young on "
             "insects, mostly caterpillars, because a nestling needs soft, "
             "rich food. One brood of chickadees eats somewhere between 6,000 "
             "and 9,000 caterpillars before it leaves the nest.",
             "So a yard feeds birds twice: with berries and seeds through the "
             "year, and with the caterpillars its plants grow in spring and "
             "summer. A design that has berries but no plants for "
             "caterpillars draws birds that cannot nest there; one with "
             "caterpillars but no fruit or seed loses the birds after the "
             "nesting season. The chain needs both ends."),
         "look": ("In the walk, click a Chokecherry: its leaves feed "
                  "caterpillars, and its fruit feeds birds in late summer."),
         "sources": ("Tallamy 2019",),
         "readout": "food_web"},
        {"title": "One plant, many neighbours",
         "text": (
             "A plant is worth what it does for the things around it. Look "
             "at a plant's card in the walk and most of it is a list of "
             "animals: the bees at its flowers, the caterpillars on its "
             "leaves, the birds at its fruit.",
             "Some animals can use only one plant, or a few. The Monarch's "
             "caterpillars eat only milkweeds; pull the milkweed and the "
             "Monarch has nothing. Other animals use many plants, so losing "
             "one plant costs them little. A healthy planting has several "
             "plants doing each job, so that no animal hangs by a single "
             "thread."),
         "look": ("In the walk, click an animal on a plant's card and read "
                  "which plants it uses here, and which it uses that are not "
                  "here yet."),
         "sources": ("Tallamy 2019",),
         "readout": "neighbours"},
        {"title": "Plants change over time",
         "text": (
             "A planting is not finished on the day it goes in. Some plants "
             "start quickly: they flower in their first summer, cover bare "
             "ground, and then fade as slower plants fill in. Others take "
             "years: shrubs, trees, and many prairie grasses spend their "
             "first seasons growing roots. Gardeners say a native planting "
             "sleeps the first year, creeps the second and leaps the third.",
             "Design for the year it is planted and for ten years on. Mix a "
             "few quick starters with plants that last, so the ground is "
             "covered now and the planting still holds together as it "
             "grows."),
         "look": ("In the walk, move the year slider from 1 to 15 and watch "
                  "the shrubs and trees take over."),
         "sources": ("Rainer & West 2015",),
         "readout": "over_time"},
        {"title": "Places to shelter",
         "text": (
             "Animals need places to nest and to spend the winter as well as "
             "food. Most of the bees here nest in the ground, in bare, sunny "
             "soil that nobody digs. Many butterflies and moths spend the "
             "winter in fallen leaves. Woodpeckers and many other birds nest "
             "in standing dead trees. A brush pile shelters birds and small "
             "animals through the cold.",
             "Leaving the leaves on the beds in fall, a sunny patch of bare "
             "ground, a brush pile in a corner and a dead tree left standing "
             "where it is safe do more for wildlife than most things you can "
             "buy. A bee hotel helps some bees, but its tubes must be "
             "cleaned or replaced every year, or they spread parasites and "
             "disease."),
         "look": ("In a design, Placement › Structures has brush piles, bee "
                  "logs, rock piles and ponds to place."),
         "sources": ("Tallamy 2019", "MacIvor & Packer 2015"),
         "readout": "shelter"},
        {"title": "Ranges, not certainties",
         "text": (
             "Every number in this app is an estimate. A count of the "
             "animals a plant is recorded as food for comes from people who "
             "saw an animal at a plant somewhere in the prairie provinces; "
             "it does not promise that animal will come to your yard. A "
             "flowering time shifts with the spring. A chickadee brood needs "
             "6,000 to 9,000 caterpillars, not exactly 7,500.",
             "Treat the numbers as a guide to what is likely, and then go "
             "outside and look. What visits your plants in July is the real "
             "answer, and it is worth writing down."),
         "look": ("In a design, Site › Field Notes has a sheet to print and "
                  "take outside."),
         "sources": (),
         "readout": "ranges"},
    )),
    ("site", "Site factors to consider in design", (
        {"title": "Sun and shade",
         "text": (
             "Light decides more about what will grow than anything else. A "
             "plant labelled full sun needs about six hours of direct sun in "
             "summer; part shade means three to six; shade, less than three. "
             "Watch the yard at breakfast, at noon and late in the afternoon, "
             "and note where the shadows fall.",
             "The sun is higher in June than in April or September, so a "
             "spot can be sunny in summer and shaded in spring. Trees leaf "
             "out in May around {place}, so ground under them is sunny "
             "early in the season and shaded after. The north side of a house "
             "is in shade nearly all day."),
         "look": ("In a design, Site › Sun & Shade draws the shade of the "
                  "trees and buildings on your lot through the day."),
         "sources": (),
         "readout": "sun"},
        {"title": "Water",
         "text": (
             "Find out how fast your ground drains. Dig a hole about 30 cm "
             "deep, fill it with water, and see how long it takes to empty: "
             "within a day is well drained, longer means a wet spot. After a "
             "heavy rain, notice where the water stands.",
             "Roofs and driveways send water to particular places: the end "
             "of a downspout is a natural spot for plants that like it wet, "
             "while the strip under the eaves stays dry because the roof "
             "keeps the rain off. Put plants that like it dry where the "
             "water leaves, and plants that like it moist where it "
             "collects."),
         "look": ("In a design, Site › Site Info says how much rain falls in "
                  "a year at your pin."),
         "sources": (),
         "readout": "water"},
        {"title": "Soil",
         "text": (
             "Squeeze a handful of damp soil. If it feels gritty and falls "
             "apart, it is sandy and drains fast; if it is sticky and holds "
             "a shape, it is clay and holds water; most garden soil is in "
             "between.",
             "Most prairie wildflowers and grasses grew up in lean soil. "
             "Compost and fertiliser make them grow tall and floppy and help "
             "the weeds beat them, so leave the soil as it is unless it has "
             "been scraped down to subsoil. A soil test tells you the pH; "
             "most native plants here grow in a wide range of it."),
         "look": "In a design, Site › Site Info has a line on the soil.",
         "sources": (),
         "readout": "soil"},
        {"title": "Slope",
         "text": (
             "Water runs downhill, so the top of a slope dries out first and "
             "the bottom stays wet longest. Put plants that like it dry at "
             "the top and plants that like it moist at the bottom.",
             "On a steep slope, plant across it rather than up and down, so "
             "the roots and stems slow the water and hold the soil. Grasses "
             "and spreading plants with deep roots are good at this."),
         "look": ("In a design, with View › Advanced tools on, Site › Slope "
                  "draws the contours and the way the water runs."),
         "sources": (),
         "readout": "slope"},
        {"title": "Wind and snow",
         "text": (
             "Wind dries plants out and drops snow where it slows down: "
             "behind fences, shrubs and buildings. A deep drift is good for "
             "plants under it, because snow keeps the ground from freezing "
             "hard, but heavy, wet drifts can break shrubs.",
             "Think about where the snow goes when you shovel. The strip "
             "along a sidewalk or driveway gets heavy, salty snow all winter; "
             "plants that put up with salt, or a strip you leave for the "
             "snow, are better there than a bed you care about."),
         "look": ("In a design, with View › Advanced tools on, Site › Wind "
                  "shows which way the wind comes from in each season."),
         "sources": (),
         "readout": "wind"},
        {"title": "Frost and cold",
         "text": (
             "Around {place}, the last frost of spring and the first of fall "
             "leave a short growing season, and winters are cold. A plant "
             "native here is already fitted to that: it knows when to wake "
             "up and when to stop growing.",
             "Plant in spring after the last frost, or in early fall, when "
             "the soil is warm and the rain comes back. Water new plants "
             "through their first summer, while their roots are short."),
         "look": ("In a design, Site › Site Info gives the frost dates and "
                  "the hardiness zone at your pin."),
         "sources": (),
         "readout": "frost"},
        {"title": "What is already there",
         "text": (
             "Start from what the yard already has. A big tree shades the "
             "ground and drinks the water around it; dig gently under it, "
             "because most of its roots are in the top 30 cm. Note the paths "
             "people and dogs already walk, and keep them as paths.",
             "Before you dig anywhere, find the buried lines. In Alberta, a "
             "free locate from Utility Safety Partners (Click Before You Dig) "
             "marks gas, power and other lines a few days before you start."),
         "look": ("In a design, Site › Features finds the trees and buildings "
                  "on your lot, and Scan this area adds them."),
         "sources": (),
         "readout": "already"},
    )),
    ("looks", "Aesthetic considerations", (
        {"title": "Three ways to lay a bed out",
         "text": (
             "A wild bed mixes its plants the way a meadow does: grasses "
             "between the flowers, nothing in rows. A structured bed uses "
             "clear shapes: blocks of one plant, straight or curved edges, "
             "clipped shrubs. A themed bed is organised by what it does: a "
             "bed for pollinators, a rain garden, a bed of plants with "
             "berries.",
             "All three can be native. A wild bed suits a back yard or a "
             "large space; a structured one reads as tidy on a street where "
             "every lawn is cut. Many people put a structured edge around a "
             "wild middle."),
         "look": ("Placement › Communities has ready-made plantings of each "
                  "kind to try."),
         "sources": ("Rainer & West 2015",),
         "readout": "layout"},
        {"title": "Height",
         "text": (
             "When a bed is seen from one side, put the tall plants at the "
             "back and the short ones at the front. An island bed seen from "
             "all sides has its tallest plants in the middle.",
             "Some tall plants are see-through: a few airy stems with "
             "flowers at the top, like the asters and blazingstars. They can "
             "stand near the front without hiding what is behind them. Keep "
             "plants low where people need to see past them, at a corner or "
             "beside a driveway."),
         "look": ("In a design, View › 3D Preview shows the planting at its "
                  "height in any year."),
         "sources": (),
         "readout": "height"},
        {"title": "Layers and filling the ground",
         "text": (
             "Wild plantings have layers. A few tall, long-lived plants give "
             "the bed its shape all year: shrubs and the big grasses. Showy "
             "plants flower in their season. Low plants cover the ground "
             "between them, so weeds find no bare soil.",
             "Plant closer than you think you should. Bare ground between "
             "plants fills with weeds; ground covered by plants keeps itself. "
             "Each plant's page says how far apart to plant it."),
         "look": ("In a design, Design › Overview says how full the beds "
                  "will be once the plants are grown."),
         "sources": ("Rainer & West 2015",),
         "readout": "layers"},
        {"title": "Drifts and repetition",
         "text": (
             "One of each plant looks like a collection. Groups of three, "
             "five or seven of a plant, repeated through the bed, look like "
             "a place. The eye reads repetition as intention.",
             "In a real prairie a few grasses make most of the cover and the "
             "flowers come through them. A design can do the same: choose a "
             "few plants to repeat, and a few to stand out."),
         "look": ("In the walk, look at how the wildflowers stand in drifts "
                  "and the grasses fill the ground between."),
         "sources": ("Rainer & West 2015",),
         "readout": "drifts"},
        {"title": "Colour through the year",
         "text": (
             "Plan for something to look at in every month, not one burst "
             "in June. Prairie crocus flowers as the snow goes, golden bean "
             "in May, bergamot and blanketflower in July, asters and "
             "goldenrods into September.",
             "Colour is not only flowers. Red osier dogwood has red stems "
             "all winter; many shrubs turn red and orange in fall; grasses "
             "turn gold and stand up through the snow. Leave the stems and "
             "seed heads standing over winter: they feed birds, shelter "
             "insects, and catch the snow."),
         "look": ("The plant list's Colour and Flowers in filters find "
                  "plants by colour and month."),
         "sources": (),
         "readout": "colour"},
        {"title": "Showing it is on purpose",
         "text": (
             "A native planting can look untidy to a neighbour used to a cut "
             "lawn. Small signs of care tell them it is on purpose: a mown "
             "edge along the sidewalk, a path, a low fence, a bench, a bird "
             "bath, a small sign naming the planting.",
             "Joan Nassauer, a landscape architect, called this an orderly "
             "frame around a messy ecosystem. The frame is what lets the "
             "planting inside it be wild, and it is often what makes "
             "neighbours start their own."),
         "look": ("In a design, Draw › Shape draws a path, a fence or a "
                  "mown edge."),
         "sources": ("Nassauer 1995",),
         "readout": ""},
    )),
)

#: The works the pages cite, in full (also in docs/REFERENCES.md).
SOURCES = {
    "Tallamy 2007": ("Doug Tallamy, Bringing Nature Home: How You Can Sustain "
                     "Wildlife with Native Plants (Timber Press, 2007)"),
    "Tallamy 2019": ("Doug Tallamy, Nature's Best Hope: A New Approach to "
                     "Conservation That Starts in Your Yard (Timber Press, "
                     "2019)"),
    "Rainer & West 2015": ("Thomas Rainer and Claudia West, Planting in a "
                           "Post-Wild World (Timber Press, 2015)"),
    "Nassauer 1995": ("Joan Iverson Nassauer, Messy Ecosystems, Orderly "
                      "Frames, Landscape Journal 14(2), 161–170 (1995)"),
    "MacIvor & Packer 2015": ("J. Scott MacIvor and Laurence Packer, 'Bee "
                              "Hotels' as Tools for Native Pollinator "
                              "Conservation: A Premature Verdict?, PLOS ONE "
                              "10(3): e0122126 (2015)"),
}


def lesson_keys() -> list[str]:
    return [key for key, _t, _p in LESSONS]


def lesson(key: str) -> dict:
    """``{key, title, pages}`` with ``{place}`` filled in."""
    for k, title, pages in LESSONS:
        if k == key:
            place = _place()
            return {"key": k, "title": title,
                    "pages": [dict(p, text=tuple(t.replace("{place}", place)
                                                 for t in p["text"]))
                              for p in pages]}
    raise KeyError(key)


def _place() -> str:
    try:
        from src import region
        return region.default().short
    except Exception:                                       # noqa: BLE001
        return "here"


# ── The landscape a lesson talks about ──────────────────────────────────────

def landscape(placed: list[dict], *, structures: Optional[list] = None,
              site_config: Optional[dict] = None, features=None,
              name: str = "", get_plant: Optional[Callable] = None) -> dict:
    """What the readouts read: the placed plants, a row per kind of plant,
    the structures, the site and the features (a saved design's existing
    trees and buildings)."""
    if get_plant is None:
        from src.db.plants import get_plant
    rows: dict = {}
    for p in placed or []:
        pid = p.get("plant_id")
        if pid is None or pid in rows:
            continue
        rows[pid] = get_plant(pid) or dict(p)
    return {"name": name, "placed": list(placed or []),
            "rows": list(rows.values()),
            "structures": list(structures or []),
            "site": dict(site_config or {}),
            "features": list(features or [])}


def from_project(project: dict, *, name: str = "",
                 get_plant: Optional[Callable] = None) -> dict:
    """:func:`landscape` for a saved design or a walk's project."""
    from src.project_store import ProjectStore
    project = project or {}
    feats = project.get("features") or []
    structures = [(f.get("properties") or {}).get("struct_def") or {}
                  for f in feats
                  if (f.get("properties") or {}).get("element_type")
                  == "structure"]
    props = project.get("properties") or {}
    return landscape(ProjectStore(project).placed_plants,
                     structures=structures,
                     site_config=props.get("site_config") or {},
                     features=feats,
                     name=name or props.get("name") or "",
                     get_plant=get_plant)


# ── Readouts ────────────────────────────────────────────────────────────────

def readout(key: str, land: dict, **kw) -> str:
    """One or two sentences on what the chosen landscape does, for the page's
    readout key, or ``""`` when there is nothing to say about it."""
    fn = _READOUTS.get(key)
    if fn is None or not land:
        return ""
    if not land.get("placed") and key not in ("frost",):
        return "Nothing is planted here yet."
    try:
        return fn(land, **kw)
    except Exception:                                       # noqa: BLE001
        return ""


def _n(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _keystone(land, *, get_keystone=None) -> str:
    if get_keystone is None:
        from src.db.fauna import keystone_rank_lepidoptera as get_keystone
    ranked = []
    for r in land["rows"]:
        n = int(get_keystone(r.get("id") or r.get("plant_id")) or 0)
        if n:
            ranked.append((n, r.get("common_name") or "a plant"))
    ranked.sort(reverse=True)
    if not ranked:
        return ("None of its plants is recorded as food for caterpillars. "
                "One willow, aspen, cherry, aster or goldenrod would change "
                "that.")
    top = ", ".join(f"{name} ({n})" for n, name in ranked[:3])
    return (f"The plants here recorded as food for the most kinds of "
            f"caterpillar: {top}.")


def _food_web(land, **_kw) -> str:
    from src.habitat_score import compute_habitat_score
    hs = compute_habitat_score(land["placed"], land["structures"])
    fw = (hs.food_web if hs else {}) or {}
    cats, birds = fw.get("n_caterpillars", 0), fw.get("n_birds", 0)
    status = fw.get("status")
    if status == "complete":
        return (f"Both ends are here: plants recorded as food for {cats} "
                f"kinds of caterpillar, and fruit or seed for {birds} kinds "
                "of bird.")
    if status == "no_birds":
        return (f"Food for {cats} kinds of caterpillar, but no fruit or seed "
                "recorded for birds. A berry or seed plant would close it.")
    if status == "no_hosts":
        return ("Fruit and seed for birds, but no plants recorded as food "
                "for caterpillars, so no food for their nestlings.")
    return "Not enough planted to say."


def _neighbours(land, *, fauna_edges=None) -> str:
    if fauna_edges is None:
        from src.db.fauna import fauna_for_plants as fauna_edges
    ids = sorted({r.get("id") or r.get("plant_id") for r in land["rows"]})
    users: dict = {}
    for e in fauna_edges(ids) or []:
        users.setdefault(e.get("id"), set()).add(e.get("plant_id"))
    if not users:
        return "No animal is recorded with these plants yet."
    one = sum(1 for ps in users.values() if len(ps) == 1)
    return (f"{len(users)} kinds of animal are recorded with its plants: "
            f"{one} with only one plant here, {len(users) - one} with two "
            "or more.")


def _over_time(land, **_kw) -> str:
    """How long its plants take to reach their size. Not ``succession``'s
    roles: those call a trembling aspen a pioneer, which it is in a forest's
    history and is not in a yard's first summers."""
    quick = middle = slow = 0
    for r in land["rows"]:
        try:
            years = float(r.get("years_to_maturity") or 0)
        except (TypeError, ValueError):
            years = 0.0
        if not years:
            continue
        if years <= 2:
            quick += 1
        elif years <= 5:
            middle += 1
        else:
            slow += 1
    return (f"Of its kinds of plant, {quick} reach their size in a year or "
            f"two, {middle} in three to five years, and {slow} take six "
            "years or more.")


def _shelter(land, **_kw) -> str:
    names = sorted({(s.get("name") or s.get("id") or "").strip()
                    for s in land["structures"]} - {""})
    if not names:
        return ("No shelter has been placed here. A brush pile or a "
                "patch of bare ground would be a start.")
    return "Placed here: " + ", ".join(names) + "."


def _ranges(land, **_kw) -> str:
    return (f"{len(land['placed'])} plants of {len(land['rows'])} kinds. "
            "Every count about them is a record, not a promise.")


def _share(land, field: str, words: dict) -> str:
    counts: dict = {}
    for r in land["rows"]:
        for v in str(r.get(field) or "").split(","):
            v = v.strip()
            if v in words:
                counts[v] = counts.get(v, 0) + 1
    if not counts:
        return ""
    parts = [f"{counts[k]} {w}" for k, w in words.items() if counts.get(k)]
    said = parts[0] if len(parts) == 1 else (
        ", ".join(parts[:-1]) + " and " + parts[-1])
    return (f"Of its {len(land['rows'])} kinds of plant, {said}; many take "
            "more than one.")


def _sun(land, **_kw) -> str:
    return _share(land, "sun_requirement", {
        "full_sun": "take full sun", "partial_shade": "part shade",
        "full_shade": "shade"})


def _water(land, **_kw) -> str:
    return _share(land, "water_needs", {
        "low": "take dry ground", "medium": "moist ground",
        "high": "wet ground"})


def _soil(land, **_kw) -> str:
    site = land["site"]
    for key in ("soil_texture", "soil_type", "soil"):
        if site.get(key):
            return f"The soil noted for this design: {site[key]}."
    if site.get("soil_ph"):
        return f"The soil pH noted for this design: {site['soil_ph']}."
    return ("No soil is noted for this landscape. In a design, Site › Site "
            "Info reads it for your pin.")


def _slope(land, **_kw) -> str:
    if land["site"].get("latitude") is None:
        return "A walk is drawn on flat ground."
    return "Site › Slope reads this design's slope from the elevation data."


def _wind(land, **_kw) -> str:
    if land["site"].get("latitude") is None:
        return ""
    return "Site › Wind reads this design's winds for its pin."


def _frost(land, **_kw) -> str:
    from src import region_climate
    dates = region_climate.frost_dates(land["site"])
    if not dates:
        return "No frost dates are known for this pin."
    return (f"Typical for the region: last frost {region_climate.date_words(dates['last'])}, "
            f"first frost {region_climate.date_words(dates['first'])}, about "
            f"{dates['free_days']} days between ({dates['label']}).")


def _already(land, **_kw) -> str:
    kinds = {"existing_tree": ("tree", "trees"),
             "existing_building": ("building", "buildings"),
             "canopy_footprint": ("tree crown", "tree crowns")}
    counts: dict = {}
    for f in land["features"]:
        k = (f.get("properties") or {}).get("element_type")
        if k in kinds:
            counts[k] = counts.get(k, 0) + 1
    if not counts:
        return ("Nothing that was already there is marked here: no trees "
                "or buildings.")
    return "Marked as already there: " + ", ".join(
        _n(n, *kinds[k]) for k, n in counts.items()) + "."


def _layout(land, **_kw) -> str:
    return ""


def _height(land, **_kw) -> str:
    low = mid = tall = 0
    for r in land["rows"]:
        try:
            h = float(r.get("mature_height_m") or r.get("mature_height_meters")
                      or 0)
        except (TypeError, ValueError):
            h = 0.0
        if not h:
            continue
        if h < 0.5:
            low += 1
        elif h <= 1.5:
            mid += 1
        else:
            tall += 1
    return (f"Grown, {low} of its kinds of plant stay under half a metre, "
            f"{mid} reach up to a metre and a half, and {tall} grow taller.")


def _layers(land, **_kw) -> str:
    words = {"tree": ("tree", "trees"), "shrub": ("shrub", "shrubs"),
             "wildflower": ("wildflower", "wildflowers"),
             "grass": ("grass", "grasses"), "sedge": ("sedge", "sedges"),
             "groundcover": ("groundcover", "groundcovers")}
    counts: dict = {}
    for r in land["rows"]:
        t = (r.get("plant_type") or "").lower()
        if t in words:
            counts[t] = counts.get(t, 0) + 1
    return "Its kinds of plant: " + ", ".join(
        _n(n, *words[t]) for t, n in counts.items()) + "."


def _drifts(land, **_kw) -> str:
    per: dict = {}
    for p in land["placed"]:
        per[p.get("plant_id")] = per.get(p.get("plant_id"), 0) + 1
    groups = sum(1 for n in per.values() if n >= 3)
    singles = sum(1 for n in per.values() if n == 1)
    return (f"{groups} of its plants are planted three or more times, and "
            f"{singles} only once.")


def _colour(land, **_kw) -> str:
    import calendar
    from src.habitat_score import parse_month_range
    months: dict = {}
    for r in land["rows"]:
        for m in parse_month_range(r.get("bloom_period") or ""):
            months[m] = months.get(m, 0) + 1
    season = [m for m in range(4, 11)]
    gaps = [calendar.month_name[m] for m in season if not months.get(m)]
    busiest = max(months, key=months.get) if months else 0
    out = ""
    if busiest:
        out = (f"Most in flower in {calendar.month_name[busiest]} "
               f"({months[busiest]} kinds).")
    if gaps:
        out += " Nothing recorded in flower in " + ", ".join(gaps) + "."
    else:
        out += " Something in flower every month from April to October."
    return out.strip()


_READOUTS = {
    "keystone": _keystone, "food_web": _food_web, "neighbours": _neighbours,
    "over_time": _over_time, "shelter": _shelter, "ranges": _ranges,
    "sun": _sun, "water": _water, "soil": _soil, "slope": _slope,
    "wind": _wind, "frost": _frost, "already": _already, "layout": _layout,
    "height": _height, "layers": _layers, "drifts": _drifts,
    "colour": _colour,
}
