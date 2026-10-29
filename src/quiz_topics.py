"""
quiz_topics.py — Field Study by topic (F208, V3.40).

Design principle P5 (perception is constructed — retrieval practice builds the
mental model the tool is trying to teach) — see docs/DESIGN_PHILOSOPHY.md.

The owner, after a test run: the quiz is "very random right now", and they
wanted "more choice about the type of questions … plant ID general, grass ID,
flower ID, specialist, ecoregion focus … you can figure out the best way to
sort these questions". ``field_study.generate_quiz`` alternated photo
identification over the whole catalogue with ten specialist animals and one
design-gap question, with no choice of anything.

So the questions are sorted by what you are practising (the V3.38 plan):

- **Name the plant**, from a photograph, four names of the same kind (a grass
  among grasses): wildflowers; grasses, sedges and rushes; trees and shrubs;
  any plant.
- **Who uses whom**: the plant a butterfly's or moth's caterpillars eat; the
  fruit and seeds a bird is recorded eating; the flowers a bee is recorded at;
  the animals that depend on one or a few plants.
- **When and where**: which of these flowers in a month; which grows in a
  given sun and ground; the landscape you walked.

with a **focus** (every plant, the local list a person reviewed, or one of the
walks' communities) and a **length**. A topic that cannot make the questions
asked says how many it could, and never quietly asks about something else.
Every animal is named by its English name (WD-7): a question asking for the
plant of *Andrena salictaria* teaches nobody anything.

Questions are the same shape as ``field_study``'s, so one runner shows both.
Qt-free and deterministic: seed the generator and a quiz is reproducible.
Every source of data is injectable; by default they read the database.
"""

from __future__ import annotations

import calendar
import random
from typing import Callable, Optional

#: (group key, group words, ((topic key, topic words), ...)), in the order the
#: chooser lists them.
GROUPS = (
    ("name", "Name the plant", (
        ("wildflowers", "Wildflowers"),
        ("grasses", "Grasses, sedges and rushes"),
        ("woody", "Trees and shrubs"),
        ("any_plant", "Any plant"),
    )),
    ("uses", "Who uses whom", (
        ("caterpillars", "What caterpillars eat"),
        ("birds", "Birds and their fruit and seeds"),
        ("bees", "Bees and their flowers"),
        ("depends", "Animals that depend on a few plants"),
    )),
    ("when", "When and where", (
        ("flowering", "When it flowers"),
        ("growing", "Where it grows"),
        ("landscape", "The landscape you walked"),
    )),
)
TOPIC_WORDS = {key: words for _g, _gw, topics in GROUPS
               for key, words in topics}
#: The topics that ask about a photograph, and so need photos on this computer.
PHOTO_TOPICS = frozenset({"wildflowers", "grasses", "woody", "any_plant"})
LENGTHS = (5, 10, 20)

#: Which plant types each kind of plant covers. "Any plant" is all of them.
KINDS = {
    "wildflowers": frozenset({"wildflower", "herb", "groundcover"}),
    "grasses": frozenset({"grass", "sedge", "rush"}),
    "woody": frozenset({"tree", "shrub"}),
}

_SUN_WORDS = {"full_sun": "full sun", "partial_shade": "part shade",
              "full_shade": "shade"}
_WATER_WORDS = {"low": "dry", "medium": "moist", "high": "wet"}
_FOOD_PART = {"fruit_food": "fruit", "seed_food": "seeds"}

ALL = "all"
LOCAL = "local"


# ── data access (injectable) ─────────────────────────────────────────────────

def _default_plants() -> list[dict]:
    from src.db.plants import get_all_plants
    return get_all_plants()


def _default_edges() -> list[dict]:
    """Every documented plant↔animal record: ``{plant_id, fauna_id, name,
    scientific_name, taxon, relationship, specificity}``."""
    from src.db.plants import get_connection
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT pf.plant_id, f.id AS fauna_id, f.common_name AS name,
                      f.scientific_name, f.taxon, pf.relationship,
                      pf.specificity, pf.source
               FROM plant_fauna pf JOIN fauna f ON f.id = pf.fauna_id"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _default_image_ok(url: str) -> bool:
    from src.field_study import _default_image_available
    return _default_image_available(url)


# ── focus ────────────────────────────────────────────────────────────────────

def focus_options() -> list[tuple]:
    """``[(key, words)]``: every plant; the local list of the app's region;
    then each of the walks' communities."""
    out = [(ALL, "Every plant")]
    try:
        from src import region
        from src.native_here import places
        short = places().get(region.default().key, {}).get("short")
        if short:
            out.append((LOCAL, f"Native around {short}"))
    except Exception:                                       # noqa: BLE001
        pass
    try:
        from src.reference_ecosystem import REFERENCE_COMMUNITIES
        out += [(key, spec["name"]) for key, spec
                in REFERENCE_COMMUNITIES.items()]
    except Exception:                                       # noqa: BLE001
        pass
    return out


def _community_names(key: str) -> set:
    """The common names of a walk's community: its leads and its genera's
    species, as ``resolve_reference_community`` lists them."""
    from src.reference_ecosystem import resolve_reference_community
    r = resolve_reference_community(key)
    names = set()
    for part in ("leads", "layers"):
        for layer_names in (r.get(part) or {}).values():
            names.update(layer_names)
    return names


def focus_pool(focus: str, plants: list[dict], *,
               community: Optional[Callable] = None,
               local: Optional[Callable] = None) -> list[dict]:
    """The plants a focus covers, out of ``plants``."""
    if not focus or focus == ALL:
        return list(plants)
    if focus == LOCAL:
        if local is None:
            from src import region
            from src.native_here import native_names
            names = native_names(region.default().key)
        else:
            names = local()
        return [p for p in plants
                if (p.get("scientific_name") or "").strip() in names]
    names = (community or _community_names)(focus)
    return [p for p in plants if p.get("common_name") in names]


def _kind_of(plant: dict) -> str:
    ptype = (plant.get("plant_type") or "").lower()
    return next((k for k, types in KINDS.items() if ptype in types), "")


def _of_kind(plants: list[dict], topic: str) -> list[dict]:
    types = KINDS.get(topic)
    if types is None:
        return list(plants)
    return [p for p in plants if (p.get("plant_type") or "").lower() in types]


def _named(plants: list[dict]) -> list[dict]:
    """One row per common name: two rows sharing a name would be the same
    answer twice."""
    out, seen = [], set()
    for p in plants:
        name = (p.get("common_name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            out.append(p)
    return out


# ── photos ───────────────────────────────────────────────────────────────────

def photo_plants(topic: str, focus: str, plants: list[dict]) -> list[dict]:
    """The plants whose photographs a name-the-plant topic asks about."""
    if topic not in PHOTO_TOPICS:
        return []
    return [p for p in _named(_of_kind(focus_pool(focus, plants), topic))
            if (p.get("image_url") or "").strip()]


def photo_status(topic: str, focus: str, plants: list[dict],
                 image_ok: Callable[[str], bool]) -> tuple:
    """``(on this computer, with a photograph)`` for a topic and focus."""
    pool = photo_plants(topic, focus, plants)
    return sum(1 for p in pool if image_ok(p["image_url"])), len(pool)


# ── question builders ────────────────────────────────────────────────────────

def _mc(rng: random.Random, correct: str, distractors: list[str]) -> tuple:
    opts = [correct] + distractors
    rng.shuffle(opts)
    return opts, opts.index(correct)


def _others(rng, target: dict, pools: list[list[dict]], k: int = 3,
            avoid: frozenset = frozenset()) -> list[str]:
    """``k`` other plant names, from the first pool that has enough: the
    caller passes the fair pools first (the same kind of plant, the focus)."""
    for pool in pools:
        names = sorted({(p.get("common_name") or "").strip() for p in pool}
                       - {(target.get("common_name") or "").strip(), ""}
                       - set(avoid))
        if len(names) >= k:
            return rng.sample(names, k)
    return []


def _traits(p: dict) -> str:
    from src.field_study import _traits as traits
    return traits(p)


def _name_question(rng, topic, pool, catalogue, image_ok) -> Optional[dict]:
    """A photograph and four names of the same kind of plant."""
    shown = [p for p in _named(_of_kind(pool, topic))
             if (p.get("image_url") or "").strip() and image_ok(p["image_url"])]
    if not shown:
        return None
    target = rng.choice(shown)
    kind = KINDS.get(topic) or {(target.get("plant_type") or "").lower()}
    same = [p for p in pool if (p.get("plant_type") or "").lower() in kind]
    wider = [p for p in catalogue if (p.get("plant_type") or "").lower() in kind]
    distract = _others(rng, target, [same, wider, catalogue])
    if not distract:
        return None
    opts, idx = _mc(rng, target["common_name"], distract)
    sci = target.get("scientific_name") or ""
    return {
        "type": "identify", "subject": target["common_name"],
        "prompt": "Which plant is this?",
        "image_url": target.get("image_url", ""), "hint": _traits(target),
        "options": opts, "answer_index": idx,
        "explanation": (f"This is {target['common_name']}"
                        + (f" ({sci})" if sci else "")
                        + f": {_traits(target)}."),
    }


def _one_animal(e: dict) -> bool:
    """An animal with an English name that is one species: not a group the
    catalogue records at genus level ("Mining Bees", *Andrena spp.*), which a
    question cannot call "the" anything."""
    from src.yard_overview_items import english_name
    words = (e.get("scientific_name") or "").split()
    return (bool(english_name(e)) and len(words) >= 2
            and words[-1] not in ("sp.", "spp.", "sp", "spp"))


def _published(e: dict) -> list:
    """The record's sources that are published works, not a specimen or
    observation database (GloBI's keys all start ``globi``)."""
    return [k.strip() for k in str(e.get("source") or "").split(",")
            if k.strip() and not k.strip().startswith("globi")]


def _animals(edges: list[dict], taxon: str, relationships: frozenset,
             in_pool: dict, *, published: bool = False) -> dict:
    """``{animal name: {plant name: [relationships]}}`` for the animals of
    ``taxon`` with an English name, over the plants in the pool; only
    records from a published work when ``published``."""
    out: dict = {}
    for e in edges:
        if taxon and e.get("taxon") != taxon:
            continue
        if e.get("relationship") not in relationships:
            continue
        if published and not _published(e):
            continue
        plant = in_pool.get(e.get("plant_id"))
        if plant is None or not _one_animal(e):
            continue
        rels = out.setdefault(e["name"], {}).setdefault(
            plant["common_name"], [])
        if e["relationship"] not in rels:
            rels.append(e["relationship"])
    return out


def _all_used(edges: list[dict], name: str, by_id: dict,
              relationships: frozenset) -> set:
    """Every plant in the catalogue an animal is recorded using in these
    ways, so no wrong answer is in fact right."""
    return {by_id[e["plant_id"]]["common_name"] for e in edges
            if e.get("name") == name and e.get("relationship") in relationships
            and e.get("plant_id") in by_id}


#: topic: (group, records it asks about, only records from a published
#: work). A quiz marks every other answer wrong, so a caterpillar's food and a
#: bird's come from the guides (Acorn & Sheldon, the Pohl checklist, Birds of
#: the World): a specimen database's "host" is often only where the moth was
#: collected, which is how the Herald Moth's one record is a jack pine while
#: its caterpillars eat willow. A bee's flower is any record: there a database
#: entry is an observed visit.
_USE_QUESTIONS = {
    "caterpillars": ("lepidoptera", frozenset({"larval_host"}), True),
    "birds": ("bird", frozenset({"fruit_food", "seed_food"}), True),
    "bees": ("bee", frozenset({"nectar", "pollen", "larval_host"}), False),
}


def _cite(edges: list[dict], name: str, plant_id) -> str:
    """' (Acorn & Sheldon 2006)': the published works behind one record."""
    keys = []
    for e in edges:
        if e.get("name") == name and e.get("plant_id") == plant_id:
            keys += [k for k in _published(e) if k not in keys]
    if not keys:
        return ""
    try:
        from src.citations import format_sources
        text = format_sources(",".join(keys), short=True)
    except Exception:                                       # noqa: BLE001
        text = ""
    return f" ({text})" if text else ""


def _use_question(rng, topic, pool, catalogue, edges) -> Optional[dict]:
    """Which of these plants does an animal use: a caterpillar's food, a
    bird's fruit or seeds, a bee's flowers."""
    taxon, rels, published = _USE_QUESTIONS[topic]
    by_id = {p["id"]: p for p in catalogue if p.get("id") is not None}
    in_pool = {p["id"]: p for p in pool if p.get("id") is not None}
    animals = _animals(edges, taxon, rels, in_pool, published=published)
    if not animals:
        return None
    name = rng.choice(sorted(animals))
    plant_name = rng.choice(sorted(animals[name]))
    target = next(p for p in pool if p.get("common_name") == plant_name)
    used = _all_used(edges, name, by_id, rels)
    same = [p for p in pool if _kind_of(p) == _kind_of(target)]
    distract = _others(rng, target, [same, pool, catalogue],
                       avoid=frozenset(used))
    if not distract:
        return None
    opts, idx = _mc(rng, plant_name, distract)
    more = len(used) - 1
    also = (f", and {more} other plant{'s' if more != 1 else ''} in the "
            f"catalogue" if more > 0 else "")
    cite = _cite(edges, name, target.get("id")) if published else ""
    # Recorded, not "eats": no record of the others is not a record that they
    # are never eaten (P9).
    none = " There is no record of it at the others, which is not the same as never."
    if topic == "caterpillars":
        # A moth can be named for its caterpillar (Forest Tent Caterpillar).
        one = name.lower().endswith("caterpillar")
        young = f"the {name}" if one else f"{name} caterpillars"
        prompt = (f"Which of these plants {'is' if one else 'are'} {young} "
                  "recorded eating?")
        why = (f"{young[0].upper()}{young[1:]} {'is' if one else 'are'} "
               f"recorded eating {plant_name}{cite}{also}. A butterfly or moth "
               "lays its eggs only where its caterpillars can eat.")
    elif topic == "birds":
        part = " and ".join(sorted({_FOOD_PART[r] for r in
                                    animals[name][plant_name]}))
        prompt = f"Which of these is the {name} recorded eating?"
        why = (f"The {name} is recorded eating the {part} of "
               f"{plant_name}{cite}{also}.{none}")
    else:
        prompt = f"Which of these flowers is the {name} recorded at?"
        why = (f"The {name} is recorded at the flowers of {plant_name}{also}."
               f"{none}")
    return {"type": "uses", "subject": name, "prompt": prompt,
            "image_url": "", "hint": "",
            "options": opts, "answer_index": idx, "explanation": why}


def _depends_question(rng, pool, catalogue, edges) -> Optional[dict]:
    """An animal recorded as depending on one or a few plants, and one of
    them among plants it does not use."""
    by_id = {p["id"]: p for p in catalogue if p.get("id") is not None}
    in_pool = {p["id"]: p for p in pool if p.get("id") is not None}
    hosts: dict = {}
    for e in edges:
        if (e.get("specificity") == "specialist" and _one_animal(e)
                and e.get("plant_id") in in_pool):
            hosts.setdefault(e["name"], set()).add(
                in_pool[e["plant_id"]]["common_name"])
    if not hosts:
        return None
    name = rng.choice(sorted(hosts))
    plant_name = rng.choice(sorted(hosts[name]))
    target = next(p for p in pool if p.get("common_name") == plant_name)
    used = {by_id[e["plant_id"]]["common_name"] for e in edges
            if e.get("name") == name and e.get("plant_id") in by_id}
    distract = _others(rng, target, [pool, catalogue], avoid=frozenset(used))
    if not distract:
        return None
    opts, idx = _mc(rng, plant_name, distract)
    rest = sorted(hosts[name] - {plant_name})
    return {"type": "depends", "subject": name,
            "prompt": f"The {name} depends on one or a few plants. "
                      "Which of these is one?",
            "image_url": "", "hint": "", "options": opts, "answer_index": idx,
            "explanation": (f"The {name} is recorded depending on {plant_name}"
                            + (f" (and {', '.join(rest)})" if rest else "")
                            + ". Lose the plant and you lose the animal.")}


def _months(plant: dict) -> list:
    from src.habitat_score import parse_month_range
    return sorted(parse_month_range(plant.get("bloom_period") or ""))


def _span(months) -> str:
    from src.what_it_feeds import span
    return span(months)


def _flowering_question(rng, pool, catalogue) -> Optional[dict]:
    """Which of these flowers in a month: one that does, three with a
    recorded flowering time that does not include it."""
    timed = [p for p in _named(pool) if _months(p)]
    if not timed:
        return None
    target = rng.choice(timed)
    month = rng.choice(_months(target))
    def other(p):
        ms = _months(p)
        return bool(ms) and month not in ms
    same = [p for p in timed if other(p) and _kind_of(p) == _kind_of(target)]
    rest = [p for p in timed if other(p)]
    wider = [p for p in catalogue if other(p)]
    distract = _others(rng, target, [same, rest, wider])
    if not distract:
        return None
    opts, idx = _mc(rng, target["common_name"], distract)
    by_name = {p["common_name"]: p for p in catalogue + pool}
    said = "; ".join(f"{n}, {_span(_months(by_name[n]))}" for n in distract
                     if n in by_name)
    return {"type": "flowering", "subject": target["common_name"],
            "prompt": f"Which of these flowers in {calendar.month_name[month]}?",
            "image_url": "", "hint": "", "options": opts, "answer_index": idx,
            "explanation": (f"{target['common_name']} flowers "
                            f"{_span(_months(target))}. The others: {said}.")}


def _levels(value: str, words: dict) -> list:
    return [v.strip() for v in str(value or "").split(",")
            if v.strip() in words]


def _conditions(p: dict) -> str:
    sun = " or ".join(_SUN_WORDS[s] for s in _levels(p.get("sun_requirement"),
                                                      _SUN_WORDS))
    water = " or ".join(_WATER_WORDS[w] for w in
                        _levels(p.get("water_needs"), _WATER_WORDS))
    return f"{water or 'any'} ground, {sun or 'any light'}"


def _growing_question(rng, pool, catalogue) -> Optional[dict]:
    """Which of these grows in a given light and ground: one that does,
    three recorded as needing something else."""
    known = [p for p in _named(pool)
             if _levels(p.get("sun_requirement"), _SUN_WORDS)
             and _levels(p.get("water_needs"), _WATER_WORDS)]
    if not known:
        return None
    target = rng.choice(known)
    sun = rng.choice(_levels(target["sun_requirement"], _SUN_WORDS))
    water = rng.choice(_levels(target["water_needs"], _WATER_WORDS))
    def other(p):
        suns = _levels(p.get("sun_requirement"), _SUN_WORDS)
        waters = _levels(p.get("water_needs"), _WATER_WORDS)
        return bool(suns and waters) and (sun not in suns or water not in waters)
    same = [p for p in known if other(p) and _kind_of(p) == _kind_of(target)]
    distract = _others(rng, target, [same, [p for p in known if other(p)],
                                     [p for p in catalogue if other(p)]])
    if not distract:
        return None
    opts, idx = _mc(rng, target["common_name"], distract)
    by_name = {p["common_name"]: p for p in catalogue + pool}
    said = "; ".join(f"{n}, {_conditions(by_name[n])}" for n in distract
                     if n in by_name)
    return {"type": "growing", "subject": target["common_name"],
            "prompt": (f"Which of these grows in {_WATER_WORDS[water]} ground "
                       f"in {_SUN_WORDS[sun]}?"),
            "image_url": "", "hint": "", "options": opts, "answer_index": idx,
            "explanation": (f"{target['common_name']} takes "
                            f"{_conditions(target)}. The others: {said}.")}


def _landscape_questions(rng, walk: list[dict], catalogue, edges,
                         design_state) -> list:
    """About the landscape you walked: which plants grow in it, and who
    would lose the only plant there it is recorded with if one were pulled;
    and its food-web gap, when it has one."""
    by_id = {p["id"]: p for p in catalogue if p.get("id") is not None}
    here = _named([by_id[r.get("plant_id")] for r in walk
                   if r.get("plant_id") in by_id])
    out = []
    if not here:
        return out
    here_names = {p["common_name"] for p in here}
    target = rng.choice(here)
    distract = _others(rng, target, [
        [p for p in catalogue if p["common_name"] not in here_names
         and _kind_of(p) == _kind_of(target)],
        [p for p in catalogue if p["common_name"] not in here_names]])
    if distract:
        opts, idx = _mc(rng, target["common_name"], distract)
        out.append({"type": "landscape", "subject": target["common_name"],
                    "prompt": "Which of these grows in the landscape you walked?",
                    "image_url": "", "hint": "", "options": opts,
                    "answer_index": idx,
                    "explanation": (f"{target['common_name']} grows there. "
                                    "None of the others does.")})
    ids = {p["id"] for p in here}
    users: dict = {}
    for e in edges:
        if e.get("plant_id") in ids and _one_animal(e):
            users.setdefault(e["name"], set()).add(e["plant_id"])
    for plant in rng.sample(here, len(here)):
        mine = {n for n, ps in users.items() if plant["id"] in ps}
        only = sorted(n for n in mine if len(users[n]) == 1)
        shared = sorted(n for n in mine if len(users[n]) > 1)
        if only and len(shared) >= 3:
            answer = rng.choice(only)
            opts, idx = _mc(rng, answer, rng.sample(shared, 3))
            out.append({
                "type": "landscape", "subject": "pull " + plant["common_name"],
                "prompt": (f"Pull the {plant['common_name']}, and which of "
                           "these animals loses the only plant in the "
                           "landscape it is recorded with?"),
                "image_url": "", "hint": "", "options": opts,
                "answer_index": idx,
                "explanation": (f"The {answer} is recorded with the "
                                f"{plant['common_name']} and nothing else "
                                "there. The others use other plants there "
                                "too, which is what keeps a community "
                                "standing.")})
            break
    if design_state:
        from src.field_study import _gap_question
        gap = _gap_question(rng, design_state)
        if gap:
            out.append(gap)
    return out


# ── the quiz ─────────────────────────────────────────────────────────────────

def build_quiz(topic: str, *, focus: str = ALL, n: int = 10, seed: int = 0,
               plants: Optional[list[dict]] = None,
               edges: Optional[list[dict]] = None,
               image_ok: Optional[Callable[[str], bool]] = None,
               walk_plants: Optional[list[dict]] = None,
               design_state: Optional[dict] = None,
               community: Optional[Callable] = None,
               local: Optional[Callable] = None) -> list[dict]:
    """Up to ``n`` questions on ``topic`` about the plants ``focus`` covers.

    Fewer than ``n`` when the topic cannot make more (too few photos on this
    computer, too few plants in the focus): the caller says so; nothing from
    another topic stands in. ``walk_plants`` are the landscape the person
    walked (the "landscape" topic, which ignores the focus)."""
    if topic not in TOPIC_WORDS:
        raise ValueError(f"unknown topic {topic!r}")
    rng = random.Random(seed)
    catalogue = list(plants if plants is not None else _default_plants())
    pool = focus_pool(focus, catalogue, community=community, local=local)
    if topic in PHOTO_TOPICS:
        ok = image_ok or _default_image_ok
        build = lambda: _name_question(rng, topic, pool, catalogue, ok)  # noqa: E731
    elif topic in _USE_QUESTIONS or topic == "depends":
        rows = edges if edges is not None else _default_edges()
        if topic == "depends":
            build = lambda: _depends_question(rng, pool, catalogue, rows)  # noqa: E731
        else:
            build = lambda: _use_question(rng, topic, pool, catalogue, rows)  # noqa: E731
    elif topic == "flowering":
        build = lambda: _flowering_question(rng, pool, catalogue)  # noqa: E731
    elif topic == "growing":
        build = lambda: _growing_question(rng, pool, catalogue)  # noqa: E731
    else:
        rows = edges if edges is not None else _default_edges()
        walk = walk_plants or []
        if design_state is None and walk:
            design_state = _food_web(walk)
        made, tries = [], 0
        seen: set = set()
        while len(made) < n and tries < n * 6:
            tries += 1
            for q in _landscape_questions(rng, walk, catalogue, rows,
                                          design_state):
                key = (q["type"], q.get("subject") or q["prompt"])
                if key not in seen and len(made) < n:
                    seen.add(key)
                    made.append(q)
        return made
    out, seen, tries = [], set(), 0
    while len(out) < n and tries < n * 12:
        tries += 1
        q = build()
        if not q:
            continue
        # One question per animal or plant: a short quiz asked the Yellow
        # Warbler four times, each with another of its plants.
        key = (q["type"], q.get("subject") or q["prompt"])
        if key not in seen:
            seen.add(key)
            out.append(q)
    return out


def _food_web(walk: list[dict]) -> Optional[dict]:
    try:
        from src.habitat_score import compute_habitat_score
        hs = compute_habitat_score(walk, [])
        return hs.food_web if hs else None
    except Exception:                                       # noqa: BLE001
        return None


# ── best scores ──────────────────────────────────────────────────────────────

def best_key(topic: str, focus: str) -> str:
    return f"quiz_best:{topic}:{focus or ALL}"


def best(topic: str, focus: str, *, get: Optional[Callable] = None) -> tuple:
    """``(score, out of)`` of the best quiz on this topic and focus, or
    ``(0, 0)``."""
    if get is None:
        from src.db.progress import get_state as get
    try:
        score, total = (int(v) for v in get(best_key(topic, focus), "").split("/"))
        return score, total
    except (ValueError, AttributeError):
        return 0, 0


def record(topic: str, focus: str, score: int, total: int, *,
           get: Optional[Callable] = None,
           put: Optional[Callable] = None) -> bool:
    """Keep ``score / total`` if it beats the best so far (as a share, then
    as a count). Returns whether it is the new best."""
    if total <= 0:
        return False
    if put is None:
        from src.db.progress import set_state as put
    old_score, old_total = best(topic, focus, get=get)
    if old_total:
        if (score * old_total, score) <= (old_score * total, old_score):
            return False
    put(best_key(topic, focus), f"{score}/{total}")
    return True
