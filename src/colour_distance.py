"""colour_distance.py — how far apart two colours look, including to a reader
who cannot see one of the channels.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

Split out in V2.66 because three places needed the same answer: the test that
guards the website's ecoregion palette, the ecoregion rebuild pipeline's own
validation stage, and any future palette that has to prove itself. It was
written twice before this file existed, which is exactly one time too many for
a function whose whole job is to be the authority on a number.

**Why this is computed rather than judged.** "Are these two colours far enough
apart" reads like a matter of taste and is not. The V2.51 ecoregion palette put
the boreal teal and the foothills olive within OKLab deltaE 7.7 of one another —
hard to tell apart with *full* colour vision, impossible under deuteranopia —
and it shipped, because nobody had written the question down in a form a test
could answer.

The maths is standard and small: sRGB to linear, linear to OKLab, Euclidean
distance times 100, with Machado et al. (2009) colour-vision-deficiency
matrices applied first. Reimplemented here rather than pulled from a colour
library because the app ships no colour-science dependency and this is fifty
lines that will never change.
"""

from __future__ import annotations

import math

__all__ = ["chroma", "delta_e", "lightness", "worst_cvd_delta_e"]

#: Machado, Oliveira and Fernandes (2009), severity 1.0. One matrix per common
#: form of colour-vision deficiency, applied to linear sRGB.
_MACHADO = {
    "protan": ((0.152286, 1.052583, -0.204868),
               (0.114503, 0.786281, 0.099216),
               (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968),
               (0.280085, 0.672501, 0.047413),
               (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779),
               (-0.078411, 0.930809, 0.147602),
               (0.004733, 0.691367, 0.303900)),
}


def _linear(hexcolour: str) -> list:
    """sRGB hex to linear-light RGB."""
    value = (hexcolour or "").lstrip("#")
    if len(value) != 6:
        raise ValueError(f"not a six-digit hex colour: {hexcolour!r}")
    out = []
    for offset in (0, 2, 4):
        channel = int(value[offset:offset + 2], 16) / 255.0
        out.append(channel / 12.92 if channel <= 0.04045
                   else ((channel + 0.055) / 1.055) ** 2.4)
    return out


def _oklab(rgb) -> tuple:
    red, green, blue = rgb
    long_ = (0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue) ** (1 / 3)
    medium = (0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue) ** (1 / 3)
    short = (0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue) ** (1 / 3)
    return (0.2104542553 * long_ + 0.7936177850 * medium - 0.0040720468 * short,
            1.9779984951 * long_ - 2.4285922050 * medium + 0.4505937099 * short,
            0.0259040371 * long_ + 0.7827717662 * medium - 0.8086757660 * short)


def _simulate(rgb, kind: str) -> list:
    matrix = _MACHADO[kind]
    return [min(1.0, max(0.0, sum(matrix[row][i] * rgb[i] for i in range(3))))
            for row in range(3)]


def delta_e(one: str, two: str, kind: str = "") -> float:
    """OKLab distance x100 between two hex colours.

    ``kind`` simulates a colour-vision deficiency first: ``protan``, ``deutan``
    or ``tritan``. Empty means normal vision.
    """
    first = _oklab(_simulate(_linear(one), kind) if kind else _linear(one))
    second = _oklab(_simulate(_linear(two), kind) if kind else _linear(two))
    return 100.0 * math.dist(first, second)


def worst_cvd_delta_e(one: str, two: str) -> float:
    """The smallest distance across all three deficiencies.

    The worst case is the one that matters: a pair separating well for two of
    the three and collapsing for the third is a pair that fails for whoever has
    the third.
    """
    return min(delta_e(one, two, kind) for kind in _MACHADO)


def lightness(hexcolour: str) -> float:
    """OKLCH L, 0 to 1."""
    return _oklab(_linear(hexcolour))[0]


def chroma(hexcolour: str) -> float:
    """OKLCH C. Near zero means the colour reads as grey."""
    _, a_axis, b_axis = _oklab(_linear(hexcolour))
    return math.hypot(a_axis, b_axis)


def _srgb(oklab) -> str:
    """OKLab back to an sRGB hex string, clamped into gamut."""
    lightness_, a_axis, b_axis = oklab
    long_ = (lightness_ + 0.3963377774 * a_axis + 0.2158037573 * b_axis) ** 3
    medium = (lightness_ - 0.1055613458 * a_axis - 0.0638541728 * b_axis) ** 3
    short = (lightness_ - 0.0894841775 * a_axis - 1.2914855480 * b_axis) ** 3
    linear = (
        +4.0767416621 * long_ - 3.3077115913 * medium + 0.2309699292 * short,
        -1.2684380046 * long_ + 2.6097574011 * medium - 0.3413193965 * short,
        -0.0041960863 * long_ - 0.7034186147 * medium + 1.7076147010 * short,
    )
    out = []
    for channel in linear:
        channel = min(1.0, max(0.0, channel))
        srgb = (12.92 * channel if channel <= 0.0031308
                else 1.055 * channel ** (1 / 2.4) - 0.055)
        out.append(f"{round(min(1.0, max(0.0, srgb)) * 255):02x}")
    return "#" + "".join(out)


def oklch_step(hexcolour: str, *, lightness_delta: float = 0.0,
               chroma_scale: float = 1.0, hue_delta: float = 0.0) -> str:
    """``hexcolour`` moved in OKLCH: lighter/darker, more/less saturated, hue
    rotated by ``hue_delta`` degrees.

    Added in V2.70 to separate the ecoregions *inside* one ecozone. They were
    spread along lightness alone, which is one channel shared between as many
    as ten siblings: Boreal Transition and Clear Hills Upland came out ΔE 0.3
    apart, which is the same colour. Rotating the hue a few degrees and varying
    the chroma gives two more channels to spend without pushing any of them far
    enough to collide with a neighbouring ecozone.

    Out-of-gamut results are clamped per channel rather than rejected: the
    steps here are small, and a caller measuring the result (which
    ``ecoregion_palette`` does, against the colour-vision floor) will catch a
    clamp that mattered.
    """
    lightness_, a_axis, b_axis = _oklab(_linear(hexcolour))
    radius = math.hypot(a_axis, b_axis) * max(0.0, chroma_scale)
    angle = math.atan2(b_axis, a_axis) + math.radians(hue_delta)
    return _srgb((min(1.0, max(0.0, lightness_ + lightness_delta)),
                  radius * math.cos(angle), radius * math.sin(angle)))
