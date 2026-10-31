"""The bird builds' proportions, in a bpy-free module (F174, V2.97).

Every bird was one of three builds whose wings were short paddles: the model's
whole width was 0.65 of its length. The viewer sizes a bird by setting its width
to the recorded wingspan (src/scene_wildlife._SIZE_AXIS), so each bird came out
at 1.5 times its wingspan in length, a robin 52 cm long. Here every build is
authored with its wings at the span its birds really have, so the width IS the
wingspan and the body follows at the right size.

Units are the bird's length, bill tip to tail tip, about 1.0. Blender frame:
+Y forward (the head), Z up, +X to the bird's right. A perching build's origin
is its body's centre, where the viewer puts the perch; a ground build's is its
feet.

Read without Blender by the tests, and by :mod:`fauna_birds`, which draws them.
``src/bird_body_plan.py`` mirrors PERCH_PITCH and WATERLINE, and a test keeps
the copies equal.

Keys, all optional except the first four (positions are centres, radii are the
three semi-axes):

    body, belly         ((x, y, z), (rx, ry, rz))
    head                ((x, y, z), r)
    beak                ((x, y, z) base, length, radius, droop radians)
    tail                ((x, y, z), (rx, ry, rz), tilt: + puts the tip down)
    fold                ((x, y, z) of one side, (rx, ry, rz), tilt)
    wing                ((x, y, z) hinge of one side, span, chord)
    neck                [((x, y, z), r), ...] a chain from the body to the head
    legs                ((x, y, z) hip of one side, r) -- feet at z = 0
    disc, eyes, tufts   the owl's face: see fauna_birds._build_bird_one
    bustle              ((x, y, z), (rx, ry, rz)) the crane's drooping tertials
"""

# A paired part is given for one side, with x >= 0; the builder mirrors it,
# WingL and FoldL at -x.
BIRD_BUILDS = {
    # A robin: the catalogue's songbirds, jays, magpie and the dove.
    "passerine": {
        "body": ((0.0, 0.0, 0.0), (0.13, 0.24, 0.13)),
        "belly": ((0.0, 0.03, -0.04), (0.11, 0.20, 0.10)),
        "head": ((0.0, 0.26, 0.09), 0.095),
        "beak": ((0.0, 0.34, 0.08), 0.08, 0.025, 0.0),
        "tail": ((0.0, -0.40, 0.0), (0.07, 0.18, 0.015), 0.20),
        "fold": ((0.11, -0.10, 0.05), (0.035, 0.22, 0.06), 0.12),
        "wing": ((0.08, 0.04, 0.07), 1.55, 0.11),
    },
    # A flicker: a longer bill, the stiff tail propped down against the trunk.
    "woodpecker": {
        "body": ((0.0, -0.02, 0.0), (0.12, 0.26, 0.12)),
        "belly": ((0.0, 0.0, -0.04), (0.10, 0.22, 0.09)),
        "head": ((0.0, 0.27, 0.07), 0.09),
        "beak": ((0.0, 0.35, 0.065), 0.13, 0.022, 0.0),
        "tail": ((0.0, -0.38, -0.04), (0.06, 0.15, 0.012), 0.45),
        "fold": ((0.10, -0.10, 0.05), (0.03, 0.22, 0.055), 0.15),
        "wing": ((0.08, 0.04, 0.06), 1.75, 0.12),
    },
    # A hummingbird: the long bill is the body plan, narrow fast wings.
    "hummer": {
        "body": ((0.0, 0.0, 0.0), (0.12, 0.20, 0.12)),
        "belly": ((0.0, 0.02, -0.04), (0.10, 0.16, 0.09)),
        "head": ((0.0, 0.20, 0.06), 0.085),
        "beak": ((0.0, 0.27, 0.055), 0.26, 0.012, 0.0),
        "tail": ((0.0, -0.30, -0.02), (0.06, 0.14, 0.01), 0.10),
        "fold": ((0.10, -0.08, 0.05), (0.025, 0.18, 0.045), 0.10),
        "wing": ((0.07, 0.03, 0.06), 1.35, 0.07),
    },
    # A red-tailed hawk. Built level, as it flies; the viewer tips it up by
    # PERCH_PITCH on a perch, so the head is angled down by about as much and
    # looks ahead from the branch (and down, hunting, in the air).
    "raptor": {
        "body": ((0.0, 0.0, 0.0), (0.14, 0.26, 0.14)),
        "belly": ((0.0, 0.06, -0.04), (0.12, 0.20, 0.11)),
        "head": ((0.0, 0.30, 0.03), 0.10),
        "beak": ((0.0, 0.37, -0.02), 0.07, 0.028, 0.95),
        "tail": ((0.0, -0.42, 0.0), (0.09, 0.20, 0.015), 0.0),
        "fold": ((0.12, -0.16, 0.06), (0.04, 0.32, 0.08), 0.05),
        "wing": ((0.09, 0.05, 0.07), 2.2, 0.17),
    },
    # A great horned owl: a big round head with a pale facial disc, the ear
    # tufts, and a stocky body, upright on the perch like the hawk.
    "owl": {
        "body": ((0.0, 0.0, 0.0), (0.18, 0.30, 0.18)),
        "belly": ((0.0, 0.05, -0.05), (0.15, 0.22, 0.14)),
        "head": ((0.0, 0.32, 0.02), 0.15),
        "beak": ((0.0, 0.43, -0.07), 0.04, 0.02, 1.15),
        "tail": ((0.0, -0.38, 0.0), (0.10, 0.14, 0.015), 0.0),
        "fold": ((0.16, -0.12, 0.08), (0.04, 0.28, 0.10), 0.05),
        "wing": ((0.12, 0.04, 0.08), 2.1, 0.20),
        # The face looks along `disc`'s droop, so tipped up on the perch it
        # looks ahead. Tufts point up once the owl is upright.
        "disc": (0.10, 0.12, 1.15),            # distance out, radius, droop
        "eyes": (0.035, 0.02),                 # spacing either side, radius
        "tufts": (0.07, 0.10, 0.05),           # spacing, length, radius
    },
    # A ruffed grouse (and the ptarmigans): round and heavy, a small head, a
    # fan tail, short feathered legs; it walks. Span 1.3 is the ruffed grouse's
    # (it is in a quarter of designs); a ptarmigan's wing is longer for its
    # body, so the white-tailed comes out about a fifth long.
    "grouse": {
        "body": ((0.0, 0.0, 0.25), (0.17, 0.30, 0.15)),
        "belly": ((0.0, 0.05, 0.20), (0.14, 0.24, 0.10)),
        "head": ((0.0, 0.31, 0.43), 0.075),
        "beak": ((0.0, 0.37, 0.42), 0.05, 0.02, 0.2),
        "tail": ((0.0, -0.38, 0.28), (0.13, 0.17, 0.015), -0.20),
        "fold": ((0.15, -0.05, 0.30), (0.04, 0.22, 0.08), 0.10),
        "wing": ((0.10, 0.05, 0.33), 1.3, 0.13),
        "neck": [((0.0, 0.20, 0.30), 0.07), ((0.0, 0.28, 0.40), 0.06)],
        "legs": ((0.07, -0.02, 0.12), 0.025),
    },
    # A northern shoveler: long and flat, a short neck, the spoon bill.
    "duck": {
        "body": ((0.0, 0.0, 0.20), (0.17, 0.32, 0.12)),
        "belly": ((0.0, 0.02, 0.15), (0.15, 0.26, 0.08)),
        "head": ((0.0, 0.33, 0.39), 0.075),
        "beak": ((0.0, 0.40, 0.37), 0.14, 0.035, 0.15),
        "tail": ((0.0, -0.37, 0.24), (0.07, 0.10, 0.015), -0.20),
        "fold": ((0.15, -0.08, 0.25), (0.035, 0.24, 0.06), 0.05),
        "wing": ((0.10, 0.05, 0.28), 1.6, 0.11),
        "neck": [((0.0, 0.24, 0.26), 0.065), ((0.0, 0.30, 0.36), 0.055)],
        "legs": ((0.06, -0.08, 0.10), 0.018),
    },
    # A snow goose, alert: the long neck raised.
    "goose": {
        "body": ((0.0, -0.05, 0.27), (0.17, 0.30, 0.14)),
        "belly": ((0.0, -0.03, 0.22), (0.15, 0.24, 0.10)),
        "head": ((0.0, 0.33, 0.61), 0.065),
        "beak": ((0.0, 0.38, 0.60), 0.09, 0.028, 0.15),
        "tail": ((0.0, -0.38, 0.30), (0.08, 0.10, 0.02), -0.10),
        "fold": ((0.15, -0.10, 0.32), (0.04, 0.26, 0.07), 0.05),
        "wing": ((0.10, 0.02, 0.35), 2.0, 0.13),
        "neck": [((0.0, 0.18, 0.33), 0.06), ((0.0, 0.26, 0.47), 0.05),
                 ((0.0, 0.30, 0.58), 0.045)],
        "legs": ((0.07, -0.03, 0.16), 0.02),
    },
    # A sandhill crane: long legs, the upright S of the neck, a straight bill
    # and the drooping bustle over the tail.
    "crane": {
        "body": ((0.0, -0.02, 0.62), (0.12, 0.24, 0.12)),
        "belly": ((0.0, 0.0, 0.58), (0.10, 0.18, 0.08)),
        "head": ((0.0, 0.25, 1.04), 0.045),
        "beak": ((0.0, 0.29, 1.03), 0.12, 0.013, 0.12),
        "tail": ((0.0, -0.24, 0.62), (0.07, 0.08, 0.02), 0.30),
        "fold": ((0.11, -0.08, 0.66), (0.03, 0.22, 0.07), 0.15),
        "wing": ((0.08, 0.02, 0.68), 2.0, 0.12),
        "neck": [((0.0, 0.18, 0.70), 0.035), ((0.0, 0.24, 0.90), 0.03),
                 ((0.0, 0.23, 1.02), 0.025)],
        "legs": ((0.05, -0.02, 0.52), 0.013),
        "bustle": ((0.0, -0.27, 0.56), (0.10, 0.13, 0.08)),
    },
}

# The order the builds sit in the file; the viewer selects by name, so the
# order only decides which build a file missing one falls back to.
BIRD_VARIANTS = tuple(BIRD_BUILDS)

#: How far a build is tipped nose-up on a perch, radians. The songbirds' 0.45
#: is the viewer's own default (07-wildlife.js _PERCH_PITCH); a hawk sits at
#: about 55 degrees and an owl nearly upright. src/bird_body_plan.PERCH_PITCH
#: mirrors this.
BIRD_PERCH_PITCH = {"raptor": 1.0, "owl": 1.2}

#: Standing builds: their origin is their feet.
GROUND_BUILDS = ("grouse", "duck", "goose", "crane")


def span(build):
    """The build's wingspan in its own units: its width, tip to tip."""
    return BIRD_BUILDS[build]["wing"][1]


def waterline(build):
    """How high above its feet a swimming build floats, in units of its own
    wingspan: 40% of the way up from the bottom of its belly to the top of its
    body. The viewer scales a bird by its wingspan, so this times the real
    wingspan is the depth in metres (src/bird_body_plan.WATERLINE)."""
    b = BIRD_BUILDS[build]
    (_, _, bz), (_, _, brz) = b["body"]
    (_, _, lz), (_, _, lrz) = b["belly"]
    bottom = min(bz - brz, lz - lrz)
    top = bz + brz
    return (bottom + 0.4 * (top - bottom)) / span(build)


def perch_foot(build):
    """How far below its origin a perching build's body reaches once the viewer
    has tipped it up by its perch pitch, in units of its own wingspan: where its
    feet grip. The tail hangs lower, past the perch, as a real one does.
    ``src/bird_body_plan.PERCH_FOOT`` mirrors it for the builds that sit on a
    tree's top."""
    import math                                   # noqa: PLC0415 (bpy-free)
    p = BIRD_PERCH_PITCH.get(build, 0.45)
    b = BIRD_BUILDS[build]
    low = 0.0
    for key in ("body", "belly"):
        (_, y, z), (_, ry, rz) = b[key]
        # Nose-up by p about X: a point (y, z) goes to z' = y sin p + z cos p.
        centre = y * math.sin(p) + z * math.cos(p)
        reach = math.hypot(ry * math.sin(p), rz * math.cos(p))
        low = min(low, centre - reach)
    return -low / span(build)
