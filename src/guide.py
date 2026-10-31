"""
guide.py — the guide behind Help › How to Plan Your Yard (F253, V3.38).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.

The owner, testing V3.37: *"'How to plan your yard' button simply takes you to
the github repo website… not sure what that's about."* It opened the README's
guide on GitHub's default branch, which was still V2.72 and had no guide, so
the browser landed at the top of an outdated repository page. Even with the
branch current, the app's own instructions were a code-hosting page away and
needed a connection. They live in the app now, in :mod:`src.guide_window`.

The text is one shipped file, ``data/guide.md``. The README keeps its *Get
started* section, because that is GitHub's front page, and
``tests/test_guide.py`` holds the two to the same five steps: this module
reads the steps out of either, so the test compares what a person reads in
each place rather than two copies of a constant.

Qt-free: nothing here imports PyQt6.
"""

from __future__ import annotations

import re

#: Where the guide ships, relative to the app's root (``data/`` is bundled).
GUIDE_FILE = ("data", "guide.md")

#: The heading the five steps sit under, in the guide and in the README.
STEPS_HEADING = "Your first yard, in five steps"

#: What the window shows when the file cannot be read: a broken bundle should
#: still say something a person can act on.
MISSING = ("# How to plan your yard\n\n"
           "The guide could not be read from this copy of the app. "
           "Reinstalling it puts the guide back.\n")

_HEADING = re.compile(r"^(#+)\s+(.*?)\s*$")
_STEP = re.compile(r"^\s*(\d+)\.\s+(.*\S)\s*$")


def guide_path() -> str:
    """Absolute path to the shipped guide."""
    from src.resources import resource_path
    return resource_path(*GUIDE_FILE)


def guide_text(path: str = "") -> str:
    """The guide as Markdown, or :data:`MISSING` when it cannot be read."""
    try:
        with open(path or guide_path(), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return MISSING


def numbered_steps(markdown: str, heading: str = STEPS_HEADING) -> list[str]:
    """The numbered lines under ``heading`` (any level), in order, without
    their numbers. Stops at the next heading of the same level or higher, so
    a list further down the page is not read as more steps."""
    out: list[str] = []
    level = 0
    for line in (markdown or "").splitlines():
        head = _HEADING.match(line)
        if head:
            depth, title = len(head.group(1)), head.group(2)
            if level and depth <= level:
                break
            if title == heading:
                level = depth
            continue
        if level:
            step = _STEP.match(line)
            if step:
                out.append(step.group(2))
    return out
