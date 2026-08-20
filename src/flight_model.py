"""
flight_model.py — how fast a wing actually beats, and in what pattern (V2.45).

Design principle P9 (uncertainty is a feature — ship ranges and confidence,
never false precision) and P5 (perception is constructed — make the invisible
visible) — see docs/DESIGN_PHILOSOPHY.md. Bibliography: docs/REFERENCES.md.

Author's report: birds *"are just gliding as if along a zip line"*, butterflies
should flap *"fast, fast, slow"*, and it *"should be mathematically correct"*.

Before V2.45 the viewer's wingbeats came from hardcoded per-taxon constants —
``{ base: 0.2, amp: 0.75, speed: 0.09 }`` — where ``speed`` was a raw multiplier
on the animation clock. Not hertz, not derived from anything, and identical for
every species in a taxon. This module replaces the magic numbers with published
allometry, and returns **bands rather than points**, because that is what the
evidence supports.

═══════════════════════════════════════════════════════════════════════════════
THE THREE THINGS THIS COMPUTES
═══════════════════════════════════════════════════════════════════════════════

1. **Beat frequency**, in Hz, as a band.
2. **Bout structure** — how many beats in a burst and how long the pause is.
   This is the author's "fast, fast, slow", and it is not decoration: it is
   where the frequency correction below comes from.
3. **Render mode** — whether a beat can honestly be drawn at all (see Nyquist,
   below), or has to become a blur.

═══════════════════════════════════════════════════════════════════════════════
BIRDS — Pennycuick, and why the raw formula is wrong for chickadees
═══════════════════════════════════════════════════════════════════════════════

Pennycuick (1990, *J. Exp. Biol.* 150:171–185) derived, from dimensional
analysis of flapping flight:

    f = m^(3/8) · g^(1/2) · b^(−23/24) · S^(−1/3) · ρ^(−3/8)

(m body mass kg, g 9.81 m/s², b wingspan m, S wing area m², ρ air density
1.23 kg/m³.)

**It underestimates small passerines by roughly a factor of two.** For an 11 g
black-capped chickadee with a 203 mm span it predicts ~12.6 Hz; published
measurements are 25–30 Hz. That is not a flaw in the formula — it is the
formula being applied outside what it was derived for. Pennycuick's derivation
assumes **continuous flapping**, where the wings support the body's weight on
every cycle.

Small passerines do not fly that way. They use **bounding flight**: a burst of
beats, then the wings fold and the bird travels ballistically. If the wings are
working for only a fraction *d* of the cycle, they must generate 1/*d* times
body weight while they are working. Lift scales with the square of flapping
frequency, so:

    f_burst ≈ f_continuous / √d

At d = 0.25 that is exactly the factor of two the measurements show
(12.6 / 0.5 = 25.2 Hz — inside the published 25–30 Hz range).

This is why the bout structure and the frequency are computed together and not
as two unrelated tables. **The pattern is the reason for the rate.** A model
that tuned a "×2 fudge for small birds" would get the same number and teach
nothing; this one predicts that a bird which bounds harder beats faster, which
is a claim that could be checked.

The uncertainty band comes from *d* being a range, not a constant.

═══════════════════════════════════════════════════════════════════════════════
INSECTS — inverse size allometry, calibrated on measured anchors
═══════════════════════════════════════════════════════════════════════════════

Pennycuick's relation does not apply: insect wings are not bird wings and the
flight is not quasi-steady. Greenewalt (1962, *Smithsonian Misc. Coll.* 144:1)
established that within a taxonomic group, wingbeat frequency falls roughly with
the inverse of wing length. Broader surveys put the mass exponent near −1/4 to
−1/3; with mass ∝ length³ that is length^(−0.72) to length^(−1.0).

So this module uses **f = k · L^(−0.75)**, with *k* fitted per taxon to
measured anchors, and states the anchors in the code so the fit can be argued
with:

  * **Bees** — L is body length. Fitted to *Apis mellifera* (≈230 Hz at ≈13 mm).
    Predicts *Bombus* at 20 mm → 166 Hz, against a published 150–160 Hz. Good.
    **Below about 10 mm this is extrapolation beyond both anchors**, so the
    band widens there rather than pretending otherwise — the catalogue has bees
    down to 6 mm.
  * **Lepidoptera** — L is wingspan, and the anchors fit an inverse-*first*-power
    law strikingly well, so butterflies use f = k/L: monarch ≈5.4 Hz at ~100 mm
    and cabbage white ≈11 Hz at ~45 mm give k ≈ 540 and ≈495. Moths fly faster
    for their size and get their own, much wider, constant.

═══════════════════════════════════════════════════════════════════════════════
RENDERING — the honest limit (P5)
═══════════════════════════════════════════════════════════════════════════════

The viewer runs at 60 fps at best. Nyquist says a 30 Hz beat is the fastest
that can be sampled without aliasing, and anything above it renders as a slow
backwards flutter — the wagon-wheel effect. A bumblebee at 166 Hz and a
hummingbird at 50 Hz **cannot be drawn as moving wings at all.**

That is not a compromise, it is what the eye does too: nobody has ever seen a
bee's wings, only the blurred arc they sweep. So above the limit this returns
``render='blur'`` and the viewer draws the swept envelope instead of a wing.
Below it, ``render='discrete'`` and the wing is really there.

Qt-free and DB-free: the numbers are physics, and the physics should be
testable without a display or a database.
"""

from __future__ import annotations

import math
from typing import Optional

# ── Physical constants ───────────────────────────────────────────────────────

_G = 9.81            # m/s²
_RHO = 1.23          # kg/m³, sea-level air at 15 °C

#: What the viewer runs at when there is something moving worth watching.
#: `08-modes.js` capped the ambient orbit view at 30 fps to spare weak GPUs —
#: a sensible default set before anything in the scene beat its wings. V2.45b
#: lifts it to 60 whenever the wildlife group is visible, because 30 fps cannot
#: show a wingbeat at all (see VISIBLE_HZ), and the creatures are the thing
#: people are looking at when they are on screen.
RENDER_FPS = 60.0
#: Nyquist — the *theoretical* sampling limit.
NYQUIST_HZ = RENDER_FPS / 2.0

#: …and the limit that actually matters, which is not Nyquist.
#:
#: **V2.45b correction, from the author watching it: "the birds move too fast
#: for me to see what they are doing".** Two mistakes in the first cut, both
#: mine:
#:
#: 1. It assumed 60 fps. The view creatures are usually watched in runs at 30.
#: 2. It used Nyquist. Two samples per cycle is enough to *reconstruct* a
#:    signal mathematically; it is nowhere near enough to *see* one. A wing
#:    caught twice per beat reads as strobing, not flapping.
#:
#: Six frames per cycle is about where a repeating motion starts reading as
#: motion rather than as noise. At the old 30 fps that put the honest ceiling
#: at 5 Hz — below almost every bird in this catalogue, and the real reason
#: nothing looked like it was flapping. At 60 fps it is 10 Hz, which covers the
#: butterflies outright and leaves the songbirds needing the slowed treatment.
VISIBLE_FRAMES_PER_CYCLE = 6.0
VISIBLE_HZ = RENDER_FPS / VISIBLE_FRAMES_PER_CYCLE          # 10 Hz

#: The fastest we will animate anything as a moving wing — exactly VISIBLE_HZ,
#: i.e. as fast as can still be seen. Above it the beat is shown SLOWED and
#: labelled, because a slowed beat still carries the rhythm, the bout and the
#: shape of the stroke — everything recognisable about how an animal flies —
#: whereas a strobing one carries nothing at all.
SLOWED_HZ = 10.0

#: Past this there is no wing to show at any speed: a bee's wings are a blur to
#: the naked eye too, so drawing one is the falsehood, not the blur.
BLUR_ABOVE_HZ = 45.0

# ── Flight styles ────────────────────────────────────────────────────────────
#
# Each carries the duty cycle band (what fraction of the cycle the wings are
# actually working) and the bout shape that follows from it. These are the only
# tunable numbers in the module and every one of them is a *range*.

CONTINUOUS = "continuous"    # bees, hummingbirds — wings never stop
BOUNDING = "bounding"        # small passerines, woodpeckers — flap, fold, dip
FLAP_GLIDE = "flap_glide"    # corvids, larger birds, skippers
SOARING = "soaring"          # raptors — long glides, occasional beats
BURST = "burst"              # grouse — explosive, then a long flat glide
HOVERING = "hovering"        # hummingbirds holding station
#: **Butterflies get their own two** (V2.46). They were sharing ``FLAP_GLIDE``
#: with crows, which gave them a 3–8 beat burst and a quarter-second pause — a
#: near-continuous flutter, and the author's report was exact:
#:
#:     *"The butterfly wings flap now but it is too fast and unnatural. A
#:     butterfly will flap-flap-glide… As it is the flapping is visually
#:     distracting."*
#:
#: A crow's bout and a butterfly's are not the same shape and never were. The
#: separation is what lets the monarch sail without turning every corvid into
#: one.
FLUTTER_GLIDE = "flutter_glide"   # most butterflies: a few beats, then a sail
SAIL = "sail"                     # monarchs, swallowtails — long glides

#: **Styles where the wings FOLD during the pause**, and therefore where the
#: 1/√d correction applies.
#:
#: This distinction is the one thing in this module that must not be got wrong,
#: and the first cut did get it wrong — it applied the correction to every
#: style and predicted 7–12 Hz for a red-tailed hawk against a published
#: 2.6–3 Hz, while the *uncorrected* formula gave 4.0 Hz.
#:
#: The physics: a bounding chickadee folds its wings, so during the pause it
#: makes **no lift at all** and has to overcompensate while flapping. A gliding
#: hawk holds its wings **extended**, so they carry its weight as an airfoil
#: throughout — there is nothing to compensate for, and the continuous-flight
#: prediction already applies. Correcting a glider is not conservative, it is
#: simply wrong, and by a factor of three.
_FOLDS_WINGS = frozenset({BOUNDING})

#: ``(duty_lo, duty_hi, burst_lo, burst_hi, pause_lo_s, pause_hi_s)``.
#:
#: duty = fraction of the cycle spent flapping. For folding styles it drives
#: BOTH the frequency correction and the visible pause, which is the point. For
#: gliding styles it drives only the pause.
_STYLES = {
    CONTINUOUS: (1.00, 1.00, 0, 0, 0.00, 0.00),
    BOUNDING:   (0.22, 0.40, 4, 9, 0.16, 0.42),
    FLAP_GLIDE: (0.45, 0.70, 3, 8, 0.25, 1.10),
    SOARING:    (0.10, 0.30, 2, 6, 1.50, 6.00),
    BURST:      (0.30, 0.55, 6, 14, 0.60, 2.50),
    HOVERING:   (1.00, 1.00, 0, 0, 0.00, 0.00),
    # Lepidoptera (V2.46). Two to four beats then a glide is the canonical
    # butterfly bout — literally the author's *"flap-flap-glide"* — and for the
    # big sailing nymphalids and papilionids the glide dominates the cycle
    # outright. Given as bands, like everything else here: a cabbage white on a
    # windy day is not a monarch on a thermal.
    FLUTTER_GLIDE: (0.35, 0.60, 2, 5, 0.35, 1.10),
    SAIL:          (0.20, 0.40, 2, 4, 0.90, 2.60),
}

#: Wing aspect ratio (span² / area) when a species has no measured wing area —
#: which is all of them, since wing area is the one bird measurement that is
#: not routinely published. Broad classes only, because that is all this
#: supports.
_ASPECT_BY_STYLE = {
    BOUNDING: 5.5,      # passerine — short, rounded wings
    FLAP_GLIDE: 5.8,
    SOARING: 6.5,       # buteos; long and broad
    BURST: 5.0,         # galliforms — very short, very broad
    HOVERING: 8.5,      # hummingbirds — long and narrow for their size
    CONTINUOUS: 8.5,
}
_ASPECT_DEFAULT = 5.8

# ── Insect allometry ─────────────────────────────────────────────────────────
#
# f = k · L^(-exp). Anchors named so the fit can be argued with rather than
# taken on faith.

#: Bees: L is body length in mm. k from Apis mellifera ≈ 230 Hz at 13 mm.
_BEE_K = 230.0 * (13.0 ** 0.75)
_BEE_EXP = 0.75
#: Below this the fit is extrapolating past both anchors and the band widens.
_BEE_ANCHOR_FLOOR_MM = 10.0

#: Butterflies: L is wingspan in mm, and the anchors fit 1/L almost exactly —
#: monarch ≈5.4 Hz at 100 mm (k≈540), cabbage white ≈11 Hz at 45 mm (k≈495).
_BUTTERFLY_K = 515.0
#: Skippers (Hesperiidae) are the buzzy exception: small, thick-bodied, and
#: beating far faster than a butterfly of their span — which is why they are a
#: separate ``kind`` in the catalogue rather than a note on butterflies.
_SKIPPER_K = 900.0
#: Moths fly faster for their size, and the family spread is genuinely large
#: (a noctuid at ~20 Hz and a hawkmoth at 25–40 Hz are not the same animal),
#: so the band is wide and ``flight_style`` is what narrows it.
_MOTH_K = 1400.0
_LEP_EXP = 1.0

#: ``flight_style`` → (frequency multiplier, folds/glides).
#:
#: A **closed vocabulary**, matched exactly, because that is what the column
#: actually contains — ``bobbing`` (8), ``gliding`` (7), ``erratic`` (7),
#: ``darting`` (3), ``hovering`` (3), ``fluttery`` (3). The first cut matched
#: substrings against words like "fast" and "swift" that appear nowhere in the
#: data, so it silently did nothing for 31 of 31 species. An exact map over a
#: known vocabulary fails loudly instead — and this column has been reaching
#: the viewer since V2.36 with nothing reading it.
_LEP_STYLE = {
    "hovering": (1.60, CONTINUOUS),      # hawkmoths holding station at a flower
    # Skippers keep the busiest bout: they really do buzz between perches, and
    # that buzziness is how you tell a skipper from a butterfly in the field.
    "darting":  (1.35, FLAP_GLIDE),
    "fluttery": (1.20, FLUTTER_GLIDE),
    "erratic":  (1.15, FLUTTER_GLIDE),
    "bobbing":  (1.00, FLUTTER_GLIDE),   # the classic butterfly rise-and-fall
    "gliding":  (0.80, SAIL),            # long sails between beats
}


# ── Published measurements ───────────────────────────────────────────────────
#
# Where somebody has actually put a bird or an insect in front of a high-speed
# camera, the measurement wins and the formula is not consulted. This table is
# small on purpose: it holds the anchors the allometry is calibrated against,
# and the species where the allometry is known to be poor.
#
# ⚠ SOURCING HONESTY (P9). These are literature values recorded from published
# sources, but they were entered in a session with **no network access**, so
# they could not be checked against the primary papers as they were written.
# They are therefore banded generously and every one is marked unverified in
# `data/bird_morphology_master.json`. A session with egress should re-derive
# them from AVONET (Tobias et al. 2022, *Ecol. Lett.* 25:581, CC BY 4.0, all
# 11,009 bird species) and Dunning's *CRC Handbook of Avian Body Masses* (2nd
# ed., 2008), and flip the flag. Do not treat a number here as checked.
#
# The two calibration anchors are marked; changing them changes the fit.
MEASURED_HZ = {
    # Birds — where Pennycuick is weakest (very low wing loading, or hovering).
    "Bubo virginianus":     (2.2, 3.0),    # great horned owl: outsized wings
    "Buteo jamaicensis":    (2.4, 3.2),    # red-tailed hawk
    "Archilochus colubris": (48.0, 58.0),  # ruby-throated hummingbird
    "Selasphorus rufus":    (50.0, 62.0),  # rufous hummingbird
    "Poecile atricapillus": (25.0, 30.0),  # black-capped chickadee
    # Insects — the allometry's calibration anchors.
    "Apis mellifera":       (215.0, 245.0),   # ANCHOR for the bee fit
    "Danaus plexippus":     (5.0, 6.0),       # ANCHOR for the butterfly fit
}


def measured_for(scientific_name: str) -> Optional[tuple]:
    """The published band for a species, or ``None``. Callers pass the result
    straight into ``measured_hz=`` and get ``basis='measured'`` back."""
    return MEASURED_HZ.get((scientific_name or "").strip())


def _band(lo: float, hi: float, digits: int = 1) -> dict:
    """A measurement with its uncertainty, in the shape the rest of the app
    uses for banded numbers: never a bare float."""
    lo, hi = (lo, hi) if lo <= hi else (hi, lo)
    return {"lo": round(lo, digits),
            "hi": round(hi, digits),
            "mid": round((lo + hi) / 2.0, digits)}


def _widen(band: dict, factor: float) -> dict:
    """Widen a band about its midpoint — for extrapolation past the anchors."""
    mid = band["mid"]
    return _band(mid - (mid - band["lo"]) * factor,
                 mid + (band["hi"] - mid) * factor)


# ── Birds ────────────────────────────────────────────────────────────────────

def pennycuick_hz(mass_g: float, span_mm: float,
                  wing_area_cm2: Optional[float] = None, *,
                  style: str = FLAP_GLIDE) -> float:
    """Continuous-flight wingbeat frequency, Pennycuick (1990).

    Returns the raw prediction, **uncorrected for bounding flight** — see
    :func:`bird_flight`, which is what callers should use. Exposed separately
    so the correction can be tested against the bare formula.
    """
    m = max(1e-4, float(mass_g)) / 1000.0            # kg
    b = max(1e-3, float(span_mm)) / 1000.0           # m
    if wing_area_cm2:
        s = float(wing_area_cm2) / 10000.0           # m²
    else:
        ar = _ASPECT_BY_STYLE.get(style, _ASPECT_DEFAULT)
        s = (b * b) / ar
    return (m ** 0.375) * (_G ** 0.5) * (b ** (-23.0 / 24.0)) \
        * (s ** (-1.0 / 3.0)) * (_RHO ** -0.375)


def bird_flight(mass_g: float, span_mm: float,
                wing_area_cm2: Optional[float] = None, *,
                style: str = FLAP_GLIDE,
                measured_hz: Optional[tuple] = None) -> dict:
    """Everything the viewer needs to fly one bird.

    ``measured_hz`` is an optional ``(lo, hi)`` from the literature. When a
    species has one, **it wins**: a published measurement beats a prediction,
    and the result says so in ``basis``. That is the whole reason the data file
    carries measured anchors at all.
    """
    style = style if style in _STYLES else FLAP_GLIDE
    duty_lo, duty_hi, burst_lo, burst_hi, pause_lo, pause_hi = _STYLES[style]

    if measured_hz:
        hz = _band(float(measured_hz[0]), float(measured_hz[1]))
        basis = "measured"
    elif style in _FOLDS_WINGS:
        raw = pennycuick_hz(mass_g, span_mm, wing_area_cm2, style=style)
        # Wings working a fraction d of the cycle must make 1/d times weight,
        # and lift goes as f², so f scales as 1/√d. A LOWER duty cycle means a
        # HIGHER burst frequency, so duty_lo gives the upper bound.
        hz = _band(raw / math.sqrt(duty_hi), raw / math.sqrt(duty_lo))
        basis = "predicted"
    else:
        # Wings stay extended through the glide and keep carrying the bird, so
        # the continuous-flight prediction stands as-is. The band is the
        # wing-area estimate: S is inferred from an assumed aspect ratio and
        # enters as S^(-1/3), so a generous ±25% on the area is about ±8% on
        # the frequency — widened to ±25% because Pennycuick's accuracy is
        # known to fall off at both size extremes, and this catalogue runs from
        # a 3 g hummingbird to a 1.4 kg owl.
        raw = pennycuick_hz(mass_g, span_mm, wing_area_cm2, style=style)
        hz = _band(raw * 0.75, raw * 1.25)
        basis = "predicted"

    return {
        "hz": hz,
        "basis": basis,
        "style": style,
        "duty_cycle": _band(duty_lo, duty_hi, 2),
        "burst_beats": _band(burst_lo, burst_hi, 0),
        "pause_s": _band(pause_lo, pause_hi, 2),
        "render": render_mode(hz["mid"]),
        # A bounding bird rises on the burst and falls on the fold. The viewer
        # needs an amplitude for that dip, and it follows from the pause: the
        # longer the wings are off, the further it falls. s = ½gt², halved
        # because the bird is not in true free fall (the folded body still
        # generates some lift), and capped so a long soaring glide does not
        # drop a hawk through the floor.
        "bound_dip_m": _band(
            min(2.0, 0.25 * _G * pause_lo * pause_lo),
            min(2.0, 0.25 * _G * pause_hi * pause_hi), 3),
    }


# ── Insects ──────────────────────────────────────────────────────────────────

def bee_flight(body_length_mm: float, *,
               measured_hz: Optional[tuple] = None) -> dict:
    """Wingbeat for a bee, from body length.

    Bees fly with a continuous beat — no bouts, no glide. Every bee in this
    catalogue lands above the Nyquist limit, so every one of them renders as a
    blur, which is also the only way anybody has ever seen one.
    """
    L = max(1.0, float(body_length_mm))
    if measured_hz:
        hz = _band(float(measured_hz[0]), float(measured_hz[1]))
        basis = "measured"
    else:
        f = _BEE_K * (L ** -_BEE_EXP)
        hz = _band(f * 0.85, f * 1.15)
        basis = "predicted"
        if L < _BEE_ANCHOR_FLOOR_MM:
            # Extrapolating past both anchors. Say so with the band rather
            # than by shipping a confident number nobody measured.
            hz = _widen(hz, 2.0)
            basis = "extrapolated"
    return {
        "hz": hz,
        "basis": basis,
        "style": CONTINUOUS,
        "duty_cycle": _band(1.0, 1.0, 2),
        "burst_beats": _band(0, 0, 0),
        "pause_s": _band(0.0, 0.0, 2),
        "render": render_mode(hz["mid"]),
        "bound_dip_m": _band(0.0, 0.0, 3),
    }


def lepidoptera_flight(wingspan_mm: float, *, kind: str = "butterfly",
                       flight_style: str = "",
                       measured_hz: Optional[tuple] = None) -> dict:
    """Wingbeat and bout structure for a butterfly or moth.

    Butterflies are the clearest case of the author's "fast, fast, slow": a
    short burst of beats and then a glide with the wings held in a shallow V.
    ``flight_style`` is the schema-v58 column that has been reaching the viewer
    since V2.36 and being read by nothing.
    """
    L = max(1.0, float(wingspan_mm))
    k_kind = (kind or "").strip().lower()
    moth = k_kind == "moth"
    k = _MOTH_K if moth else (_SKIPPER_K if k_kind == "skipper"
                              else _BUTTERFLY_K)

    # The schema-v58 column, finally read. Exact lookup over a closed
    # vocabulary; an unrecognised value falls back to neutral rather than
    # silently matching nothing.
    tilt, style = _LEP_STYLE.get((flight_style or "").strip().lower(),
                                 (1.0, CONTINUOUS if moth else FLAP_GLIDE))

    if measured_hz:
        hz = _band(float(measured_hz[0]), float(measured_hz[1]))
        basis = "measured"
    else:
        f = k * (L ** -_LEP_EXP) * tilt
        # Moths span noctuids to hawkmoths; the constant cannot carry that, so
        # the band does.
        spread = 0.45 if moth else 0.25
        hz = _band(f * (1 - spread), f * (1 + spread))
        basis = "predicted"

    duty_lo, duty_hi, burst_lo, burst_hi, pause_lo, pause_hi = _STYLES[style]

    return {
        "hz": hz,
        "basis": basis,
        "style": style,
        "duty_cycle": _band(duty_lo, duty_hi, 2),
        "burst_beats": _band(burst_lo, burst_hi, 0),
        "pause_s": _band(pause_lo, pause_hi, 2),
        "render": render_mode(hz["mid"]),
        # A gliding butterfly sinks rather than dips — much gentler than a
        # bounding bird, and it is why they read as drifting. A sailing monarch
        # holds its glide for a second and a half, so it sinks further.
        "bound_dip_m": (_band(0.05, 0.25, 3) if style == SAIL
                        else _band(0.02, 0.12, 3)
                        if style in (FLAP_GLIDE, FLUTTER_GLIDE)
                        else _band(0.0, 0.0, 3)),
    }


# ── Rendering honesty ────────────────────────────────────────────────────────

def render_mode(hz: float) -> str:
    """How this beat can honestly be shown: ``discrete`` / ``slowed`` / ``blur``.

    Three regimes, because there are genuinely three:

    * **discrete** (≤ 5 Hz) — slow enough to draw at its true rate. Butterflies,
      big moths, hawks, magpies.
    * **slowed** (≤ 45 Hz) — a real wingbeat that no ordinary display can show.
      Animated at :data:`SLOWED_HZ` and **labelled as slowed**, because the
      rhythm, the bout and the shape of the stroke all survive being slowed and
      none of them survive strobing. Most songbirds land here.
    * **blur** (> 45 Hz) — bees and hummingbirds. There is no wing to draw at
      any speed; the blur is what a human eye sees too.

    The first cut had only two regimes and put the boundary at Nyquist for
    60 fps. That made every songbird "discrete" at a rate the renderer could
    not show, which is why they appeared not to flap at all.
    """
    f = float(hz)
    if f <= VISIBLE_HZ:
        return "discrete"
    return "slowed" if f <= BLUR_ABOVE_HZ else "blur"


def animation_hz(hz: float) -> float:
    """The rate to actually animate at — never faster than can be seen.

    Returns the true frequency when it is showable, the slowed rate when it is
    not, and a low shimmer for a blur. The true number is never lost: it rides
    alongside in ``true_hz`` and is what :func:`describe` reports.
    """
    f = float(hz)
    if f <= VISIBLE_HZ:
        return f
    if f <= BLUR_ABOVE_HZ:
        return SLOWED_HZ
    return 6.0                       # a blur only has to shimmer


def is_slowed(hz: float) -> bool:
    """Whether the viewer is showing this beat slower than it really is — the
    thing the label has to admit to."""
    return render_mode(hz) == "slowed"


def describe(flight: dict) -> str:
    """One honest sentence, for a dossier or a tooltip (P5, P9).

    Always names the basis. "23–27 Hz" and "23–27 Hz (predicted)" are different
    claims and the app must not blur them.
    """
    hz = flight.get("hz") or {}
    lo, hi = hz.get("lo", 0), hz.get("hi", 0)
    basis = flight.get("basis", "predicted")
    word = {"measured": "measured", "predicted": "estimated",
            "extrapolated": "extrapolated — beyond measured sizes"}.get(
                basis, basis)
    out = f"{lo:g}–{hi:g} wingbeats per second ({word})"
    if flight.get("render") == "slowed":
        # P9 again: the screen is not showing this rate and must not imply it.
        out += " — shown slowed, too fast to draw at speed"
    burst = flight.get("burst_beats") or {}
    if burst.get("hi"):
        out += (f", in bursts of {burst.get('lo'):g}–{burst.get('hi'):g} "
                f"then a glide")
    if flight.get("render") == "blur":
        out += " — too fast to draw, so it is shown as a blur"
    return out


# ── The one entry point the app should use ───────────────────────────────────

def flight_for(taxon: str, *, scientific_name: str = "",
               mass_g: Optional[float] = None,
               span_mm: Optional[float] = None,
               wing_area_cm2: Optional[float] = None,
               body_length_mm: Optional[float] = None,
               wingspan_mm: Optional[float] = None,
               kind: str = "", flight_style: str = "",
               style: str = "") -> dict:
    """Flight parameters for one animal, whichever taxon it is.

    Callers should not have to know that birds use Pennycuick and insects use
    an inverse-size law — they know a taxon and some morphology. This resolves
    the published measurement first, then dispatches.

    Returns the same shape for every taxon, so ``scene_wildlife`` can hand it
    to the viewer without branching, and an animal with no morphology at all
    still gets a usable (wide) band rather than nothing.
    """
    measured = measured_for(scientific_name)
    t = (taxon or "").strip().lower()

    if t == "bird":
        return bird_flight(mass_g or 30.0, span_mm or 250.0, wing_area_cm2,
                           style=style or BOUNDING, measured_hz=measured)
    if t == "bee":
        return bee_flight(body_length_mm or 11.0, measured_hz=measured)
    if t == "lepidoptera":
        return lepidoptera_flight(wingspan_mm or 45.0, kind=kind or "butterfly",
                                  flight_style=flight_style,
                                  measured_hz=measured)
    if t == "mammal":
        # Bats are the only fliers here; everything else never leaves the
        # ground and the viewer's `ground` animation ignores these numbers.
        return bird_flight(mass_g or 10.0, span_mm or 250.0,
                           style=FLAP_GLIDE, measured_hz=measured)
    # other_insect — beetles, wasps, flies, hoverflies. Sized like a small bee
    # and banded very wide, because "other" is not a taxon with an allometry.
    out = bee_flight(body_length_mm or 10.0, measured_hz=measured)
    if not measured:
        out["hz"] = _widen(out["hz"], 1.6)
        out["basis"] = "extrapolated"
        out["render"] = render_mode(out["hz"]["mid"])
    return out
