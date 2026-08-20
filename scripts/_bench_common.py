"""
scripts/_bench_common.py — the bits both catalogue benches genuinely share
(V2.36).

`tune_morphology.py` (plants) and `tune_fauna.py` (animals) have the same
skeleton and not one field in common. This module holds only what is *identical*
— reading and writing a master JSON, the provenance vocabulary, and the
coerce-a-posted-value loop — and deliberately nothing else. Two implementations
is not enough evidence to abstract a shape; it is enough to stop copying a
`json.dump(..., indent=2, ensure_ascii=False)` and having the two files disagree
about whether the seed data ends with a newline.
"""

from __future__ import annotations

import json

# Where a value can come from, weakest first. A bench's whole job is to move
# records UP this list; a seeder can only ever write the bottom one.
DATA_SOURCES = ("estimated", "photo", "flora", "measured")


def load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: str, data) -> None:
    """Two spaces, unicode kept, trailing newline — matching how the seed files
    are already committed, so a bench edit shows as a one-line diff rather than
    as a whole-file reformat."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def coerce_field(field: str, value, int_fields, float_fields):
    """A value off the wire, typed.

    A browser sends everything as a string, including the empty one. Blank has
    to become None rather than 0 or "": "nobody has said" and "somebody measured
    zero" are different claims, and `eyespot_count` 0 is a real answer that most
    butterflies give. Raises ValueError/TypeError on a non-numeric number, so
    the caller can refuse the save while the person is still looking at it.
    """
    if field in int_fields:
        return None if value in ("", None) else int(value)
    if field in float_fields:
        return None if value in ("", None) else round(float(value), 3)
    return value
