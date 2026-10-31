"""
fauna_body_plan.py — what kind of animal an insect IS, read from the catalogue
rather than from words in its common name (V2.88).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md. The 3D scene drew every
``other_insect`` it could not name as a yellow-and-black hoverfly, because
``scene_wildlife._insect_appearance`` looked for "beetle", "lacewing" or a
dragonfly word in the common name — and since the V2.59-V2.65 fauna expansion
347 of the 408 insects carry their scientific name AS their common name. So 208
wasps, beetles, aphids, ants and grasshoppers were drawn with a body they do not
have.

The catalogue already knew. Every insect row's ``description`` opens by naming
its group (*"Crabronid wasps, native."*, *"Flower longhorns, boreal and
montane."*), and all 266 genera fall in exactly one group. :func:`insect_group`
reads that, first rule wins; ``tests/test_fauna_body_plan.py`` checks that every
insect in the shipped catalogue lands in a group and none falls through, which
is how a new arrival gets looked at rather than trusted.

:func:`insect_appearance` then maps a group onto the nearest model the viewer
HAS. For flies, beetles, dragonflies and lacewings that is the right model. For
wasps, sawflies, true bugs, ants, grasshoppers and thrips it is an interim
choice — a flier stays on the fly, a walker goes on the beetle's crawl — until
their own bodies are built (F173 in docs/BACKLOG.md,
the audit's batch C1). The colours and typical lengths
here are GROUP-level fallbacks for species nobody has described, in the same
spirit as the bee genus table in ``scene_wildlife``: a group's look, not a
species' measurement.

Qt-free and DB-free.
"""

from __future__ import annotations

import re

# (group, pattern over "common name | description"), first match wins. Order
# matters where one group's words contain another's: "Ant-hunting wasps" is a
# wasp, "Ant-mimicking longhorns" a beetle, "Aphid-eating hoverflies" a
# hoverfly, "Flesh flies that parasitise grasshoppers" a fly.
_RULES = (
    ("odonata", r"dragonfl|damselfl|darner|skimmer|meadowhawk"),
    ("lacewing", r"lacewing|aphid lion"),
    ("hoverfly", r"hoverfl|hover fl|drone fl|flower fl|syrphid|sap runs|sap-run"),
    ("bee_fly", r"bee fl"),
    ("social_wasp", r"yellowjacket|hornet|paper wasp"),
    ("sawfly", r"sawfl|horntail"),
    ("wasp", r"wasp|beewol|parasitoid|chalcid|braconid|ichneumon|leucospid"
             r"|mud dauber"),
    ("lady_beetle", r"lady beetle|ladybug|ladybird"),
    ("beetle", r"beetle|longhorn|weevil|firefl|scarab|fruitworm|borer"),
    ("ant", r"\bants?\b"),
    ("fly", r"\bfl(?:y|ies)\b|midge|tachinid|muscid|gnat|agromyzid"),
    ("bug", r"\bbugs?\b|aphid|adelgid|leafhopper|spittlebug|treehopper|cicada"
            r"|\bscale\b|sharpshooter|psyllid"),
    ("grasshopper", r"grasshopper|cricket|katydid"),
    ("thrips", r"\bthrips\b"),
)
_COMPILED = tuple((g, re.compile(p)) for g, p in _RULES)

#: Every group :func:`insect_group` can return, in rule order.
GROUPS = tuple(g for g, _ in _RULES)

#: What an unrecognised insect falls back to. The hoverfly was the pre-V2.88
#: default for everything; keeping it as the default for the genuinely unknown
#: means an unclassified row looks exactly as it always did.
UNKNOWN = "hoverfly"


def insect_group(scientific_name: str = "", common_name: str = "",
                 description: str = "") -> str:
    """The body-plan group of an ``other_insect`` row, or :data:`UNKNOWN`.

    Reads the description first (it names the group in every shipped row) and
    the common name with it, so a row with a real common name and no
    description ("Nine-spotted Lady Beetle") still resolves.
    """
    text = f"{common_name or ''} | {description or ''}".lower()
    for group, rx in _COMPILED:
        if rx.search(text):
            return group
    return UNKNOWN


def is_known(scientific_name: str = "", common_name: str = "",
             description: str = "") -> bool:
    """True when a rule matched, rather than the fallback."""
    text = f"{common_name or ''} | {description or ''}".lower()
    return any(rx.search(text) for _, rx in _COMPILED)


# ── how each group is drawn, with the models the viewer has today ────────────
#
# kind: the viewer's critter family. `beetle` walks on the plant ("crawl"),
# `fly` flies. body/wing: group colours. size_m: a TYPICAL real size along the
# axis scene_wildlife._SIZE_AXIS measures for that kind (a fly's wingspan across
# X, a beetle's body length down Z), used only when a species has no record.
# interim: the model is the nearest one available, not the right one (C1).
_LOOK = {
    "hoverfly":    dict(kind="fly", body="#e0b53a", size_m=0.020),
    "bee_fly":     dict(kind="fly", body="#a88a60", size_m=0.020),
    "fly":         dict(kind="fly", body="#55595c", size_m=0.015),
    "social_wasp": dict(kind="fly", body="#e0b53a", size_m=0.028, interim=True),
    "wasp":        dict(kind="fly", body="#2a2622", size_m=0.022, interim=True),
    "sawfly":      dict(kind="fly", body="#3a3530", size_m=0.020, interim=True),
    "lady_beetle": dict(kind="beetle", body="#cc2a22", spots=True, size_m=0.006,
                        style=0.5),
    "beetle":      dict(kind="beetle", body="#3a3a2a", size_m=0.010),
    "bug":         dict(kind="beetle", body="#6b6a3a", size_m=0.006, interim=True),
    "ant":         dict(kind="beetle", body="#2a2018", size_m=0.007, interim=True),
    "grasshopper": dict(kind="beetle", body="#7a7445", size_m=0.025, interim=True),
    "thrips":      dict(kind="beetle", body="#3a3226", size_m=0.0015, interim=True),
    "lacewing":    dict(kind="fly", body="#8fd07a", wing="#e8f5e0", size_m=0.028,
                        style=0.6),
    "odonata":     dict(kind="fly", body="#3f8a6a", elongate=True, size_m=0.065,
                        style=0.9),
}

# The style scalar the procedural builders multiply by (not a real size — that
# is `size_m`, and the viewer rescales to it). Values carried over from the
# pre-V2.88 table so nothing that was already right changes shape.
_STYLE_SIZE = {"fly": 0.55, "beetle": 0.6}


def typical_size_m(group: str):
    """A group's typical real size in metres, or None for an unknown group.
    Only ever the fallback for a species with no measurement of its own."""
    look = _LOOK.get(group)
    return look["size_m"] if look else None


def insect_appearance(group: str, common_name: str = "") -> dict:
    """The viewer's appearance bag for an insect of ``group``.

    ``group`` and ``interim`` travel in the bag so the hover tip and the tests
    can tell a right model from a stand-in.
    """
    look = _LOOK.get(group) or _LOOK[UNKNOWN]
    kind = look["kind"]
    app = {"kind": kind, "group": group if group in _LOOK else UNKNOWN,
           "body": look["body"],
           "size": look.get("style", _STYLE_SIZE[kind])}
    if kind == "fly":
        app["wing"] = look.get("wing", "#eef4f8")
        app["elongate"] = bool(look.get("elongate"))
    else:
        app["spots"] = bool(look.get("spots"))
    if look.get("interim"):
        app["interim"] = True
    if group == "odonata":
        # The four in the catalogue have real common names, and the colour is
        # the field mark between them.
        n = (common_name or "").lower()
        app["body"] = ("#c0432e" if "meadowhawk" in n
                       else "#3f7d8a" if "damsel" in n else "#3f8a6a")
    return app
