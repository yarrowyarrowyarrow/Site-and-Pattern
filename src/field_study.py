"""
field_study.py — the Field Study quiz layer (F48).

Site & Pattern only ever *answers* questions; this module is the first thing
that *asks* them. It generates retrieval-practice questions from data the app
already holds — no new content — turning passive facts into active recall and
doubling as plant-ID prep for a nursery or trail visit.

Three question kinds, each grounded in a real relationship (never Indigenous
plant-use knowledge; Principle 12):
  * identify — a plant photo + traits, name it (four choices);
  * specialist — which plant feeds this *specialist* animal (from the
    documented specialist `plant_fauna` edges);
  * gap — spot the food-web gap in the user's OWN design (from
    `habitat_score.compute_habitat_score(...).food_web`).

Design principle P5 (perception is constructed — retrieval practice builds the
mental model the tool is trying to teach) and P7 (generalist knowledge — field
ID crosses the screen-to-site divide). See docs/DESIGN_PHILOSOPHY.md.

Qt-free and deterministic: seed the ``random.Random`` and a quiz is
reproducible, so the panel, the scripting layer and the tests share one set.
All data access is injectable for tests; defaults read the DB.
"""

from __future__ import annotations

import random
from typing import Callable, Optional

_MONTHS_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ── data access (injectable) ──────────────────────────────────────────────────

def _default_plants() -> list[dict]:
    from src.db.plants import get_all_plants
    return get_all_plants()


def _default_specialists() -> list[dict]:
    """Documented specialist edges: ``{fauna, taxon, plant, plant_id}``."""
    from src.db.plants import get_connection
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT f.common_name AS fauna, f.taxon AS taxon,
                      p.common_name AS plant, p.id AS plant_id
               FROM plant_fauna pf
               JOIN fauna f  ON f.id = pf.fauna_id
               JOIN plants p ON p.id = pf.plant_id
               WHERE pf.specificity = 'specialist'"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── question builders ─────────────────────────────────────────────────────────

def _traits(p: dict) -> str:
    bits = []
    bp = (p.get("bloom_period") or "").strip()
    if bp:
        bits.append(f"blooms {bp}")
    pt = (p.get("plant_type") or "").strip()
    if pt:
        bits.append(pt)
    h = p.get("mature_height_meters")
    if h:
        bits.append(f"~{h:g} m tall")
    return " · ".join(bits) or "a native plant"


def _mc(rng: random.Random, correct: str, distractors: list[str]) -> tuple:
    """Shuffle the correct answer among distractors; return (options, idx)."""
    opts = [correct] + distractors
    rng.shuffle(opts)
    return opts, opts.index(correct)


def _identify_question(rng: random.Random, plants: list[dict]) -> Optional[dict]:
    withimg = [p for p in plants if (p.get("image_url") or "").strip()
               and (p.get("common_name") or "").strip()]
    if len(withimg) < 4:
        return None
    target = rng.choice(withimg)
    # Distractors prefer the same plant type for a fairer challenge.
    same = [p for p in plants
            if p.get("plant_type") == target.get("plant_type")
            and p.get("common_name") != target.get("common_name")]
    pool = same if len(same) >= 3 else [p for p in plants
                                        if p.get("common_name") != target.get("common_name")]
    names = list({p["common_name"] for p in pool if p.get("common_name")})
    if len(names) < 3:
        return None
    distract = rng.sample(names, 3)
    opts, idx = _mc(rng, target["common_name"], distract)
    return {
        "type": "identify",
        "prompt": "Which native plant is this?",
        "image_url": target.get("image_url", ""),
        "hint": _traits(target),
        "options": opts,
        "answer_index": idx,
        "explanation": (f"This is {target['common_name']}"
                        + (f" ({target['scientific_name']})"
                           if target.get("scientific_name") else "")
                        + f" — {_traits(target)}."),
    }


def _specialist_question(rng: random.Random, specialists: list[dict],
                         plants: list[dict]) -> Optional[dict]:
    if not specialists:
        return None
    # Group hosts per specialist animal; the correct answer is any host.
    by_fauna: dict = {}
    for e in specialists:
        by_fauna.setdefault(e["fauna"], {"taxon": e["taxon"], "hosts": set()})
        by_fauna[e["fauna"]]["hosts"].add(e["plant"])
    fauna = rng.choice(list(by_fauna.keys()))
    info = by_fauna[fauna]
    host = rng.choice(sorted(info["hosts"]))
    non_hosts = [p["common_name"] for p in plants
                 if p.get("common_name") and p["common_name"] not in info["hosts"]]
    if len(non_hosts) < 3:
        return None
    distract = rng.sample(list(set(non_hosts)), 3)
    opts, idx = _mc(rng, host, distract)
    kind = "caterpillar" if info["taxon"] == "lepidoptera" else "specialist"
    return {
        "type": "specialist",
        "prompt": f"The {fauna} is a specialist — which plant does it depend on?",
        "image_url": "",
        "hint": f"A specialist {kind} can only use particular host plants.",
        "options": opts,
        "answer_index": idx,
        "explanation": (f"{fauna} depends on {host}"
                        + (f" (and {len(info['hosts']) - 1} related host"
                           f"{'s' if len(info['hosts']) - 1 != 1 else ''})"
                           if len(info["hosts"]) > 1 else "")
                        + ". Lose the host and you lose the specialist."),
    }


def _gap_question(rng: random.Random, design_state: dict) -> Optional[dict]:
    """A 'spot the gap' question from the design's own food-web status."""
    status = (design_state or {}).get("status")
    if status == "no_birds":
        correct = "Add a berry or seed plant so birds visit"
        distract = ["Add another nectar flower",
                    "Remove a host plant",
                    "Add a garden ornament"]
        expl = ("Your plants make caterpillars, but nothing draws the birds that "
                "eat them. A fruit- or seed-bearing native closes the chain.")
        prompt = "Your design hosts caterpillars but supports no birds. What closes the food web?"
    elif status == "no_hosts":
        correct = "Add a keystone host plant (willow, aspen, aster, goldenrod)"
        distract = ["Add more mulch",
                    "Add a non-native shrub",
                    "Add a bird bath only"]
        expl = ("Birds feed their nestlings caterpillars, and caterpillars need "
                "host plants. Without hosts the food web has no base.")
        prompt = "Your design supports birds but grows no caterpillars. What's missing?"
    else:
        return None
    opts, idx = _mc(rng, correct, distract)
    return {"type": "gap", "prompt": prompt, "image_url": "", "hint": "",
            "options": opts, "answer_index": idx, "explanation": expl}


# ── generator ─────────────────────────────────────────────────────────────────

def generate_quiz(placed_plants: Optional[list[dict]] = None, *,
                  seed: int = 0, n: int = 5,
                  plants: Optional[list[dict]] = None,
                  specialists: Optional[list[dict]] = None,
                  design_state: Optional[dict] = None) -> list[dict]:
    """Return ``n`` deterministic quiz questions.

    ``placed_plants`` (optional) enables the design-aware 'gap' question and
    focuses 'identify' on species relevant to the user. ``seed`` makes the set
    reproducible. ``plants`` / ``specialists`` / ``design_state`` are injectable
    for tests; by default they read the DB (and the design's food-web status via
    ``habitat_score``).
    """
    rng = random.Random(seed)
    if plants is None:
        plants = _default_plants()
    if specialists is None:
        specialists = _default_specialists()
    if design_state is None and placed_plants:
        try:
            from src.habitat_score import compute_habitat_score
            hs = compute_habitat_score(placed_plants, [])
            design_state = hs.food_web if hs else None
        except Exception:      # noqa: BLE001
            design_state = None

    questions: list[dict] = []
    # One gap question up front when the design has a clear, teachable gap.
    if design_state:
        gq = _gap_question(rng, design_state)
        if gq:
            questions.append(gq)

    # Fill the rest by rotating identify / specialist, skipping questions with
    # the same answer (identify shares one prompt, so key on content not prompt).
    builders = [
        lambda: _identify_question(rng, plants),
        lambda: _specialist_question(rng, specialists, plants),
    ]
    def _key(q):
        return (q["type"], q["options"][q["answer_index"]])
    seen = {_key(q) for q in questions}
    guard = 0
    bi = 0
    while len(questions) < n and guard < n * 12:
        guard += 1
        q = builders[bi % len(builders)]()
        bi += 1
        if q and _key(q) not in seen:
            seen.add(_key(q))
            questions.append(q)
    return questions[:n]
