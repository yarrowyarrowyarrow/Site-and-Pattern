"""
scripts/learning_progress.py — progress bars for the learning curriculum.

Reads docs/learning/PROGRESS.md (the master checklist the learner ticks as
lessons are finished) and prints one bar per phase, an overall bar, and the
next unfinished lesson. Pure stdlib, Qt-free, DB-free — runnable from
Phase 0 onward:

    python scripts/learning_progress.py

The checklist format parsed here is pinned by tests/test_learning_progress.py
(which also keeps PROGRESS.md in sync with the docs/learning/phase-*.md
lesson files):

    ## Phase 0 — Operate the machinery
    - [x] **L0.1** — Home in the terminal
    - [ ] **L0.2** — Run the app from source
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
PROGRESS_PATH = _ROOT / "docs" / "learning" / "PROGRESS.md"

PHASE_RE = re.compile(r"^## Phase (\d+) — (.+?)\s*$")
LESSON_RE = re.compile(r"^- \[([ xX])\] \*\*(L\d+\.\d+)\*\* — (.+?)\s*$")

BAR_WIDTH = 24


def parse_progress(text: str):
    """Parse checklist text into ``[(phase_num, phase_title, lessons)]``
    where each lesson is ``(lesson_id, lesson_title, done)``. Lines that
    match neither pattern (prose, blank) are ignored."""
    phases: list[tuple[int, str, list[tuple[str, str, bool]]]] = []
    for line in text.splitlines():
        m = PHASE_RE.match(line)
        if m:
            phases.append((int(m.group(1)), m.group(2), []))
            continue
        m = LESSON_RE.match(line)
        if m and phases:
            done = m.group(1).lower() == "x"
            phases[-1][2].append((m.group(2), m.group(3), done))
    return phases


def next_lesson(phases):
    """First unticked lesson in checklist order, or None when all done."""
    for _num, _title, lessons in phases:
        for lesson_id, title, done in lessons:
            if not done:
                return lesson_id, title
    return None


def _bar(done: int, total: int, blocks: tuple[str, str]) -> str:
    full, empty = blocks
    n = round(BAR_WIDTH * done / total) if total else 0
    return full * n + empty * (BAR_WIDTH - n)


def render(phases, unicode_ok: bool = True) -> str:
    """The full report as one printable string."""
    blocks = ("█", "░") if unicode_ok else ("#", "-")
    title = "Site & Pattern — learning progress"
    lines = ["", title, "=" * len(title), ""]
    width = max((len(t) for _n, t, _l in phases), default=0)
    total_done = total_all = 0
    for num, ptitle, lessons in phases:
        done = sum(1 for _i, _t, d in lessons if d)
        total = len(lessons)
        total_done += done
        total_all += total
        pct = 100 * done // total if total else 0
        lines.append(f"Phase {num}  {ptitle:<{width}}  "
                     f"{_bar(done, total, blocks)}  {done:>2}/{total:<2} {pct:>3}%")
    pct = 100 * total_done // total_all if total_all else 0
    lines.append("")
    lines.append(f"{'Overall':<{width + 9}}  "
                 f"{_bar(total_done, total_all, blocks)}  "
                 f"{total_done:>2}/{total_all:<2} {pct:>3}%")
    lines.append("")
    nxt = next_lesson(phases)
    if nxt:
        lines.append(f"Next up: {nxt[0]} — {nxt[1]}")
    else:
        lines.append("Curriculum complete. The codebase is yours.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    try:
        text = PROGRESS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Checklist not found: {PROGRESS_PATH}", file=sys.stderr)
        return 1
    phases = parse_progress(text)
    if not phases:
        print(f"No phases found in {PROGRESS_PATH}", file=sys.stderr)
        return 1
    # Fall back to ASCII bars on terminals that can't print block glyphs
    # (e.g. a Windows console in a legacy codepage).
    enc = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "█".encode(enc)
        unicode_ok = True
    except (UnicodeEncodeError, LookupError):
        unicode_ok = False
    print(render(phases, unicode_ok=unicode_ok))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
