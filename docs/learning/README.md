# The Workbook — lesson-by-lesson curriculum

This folder is the working version of `docs/LEARNING_ROADMAP.md`. The
roadmap is the map; this is the trail, cut into **33 lessons across six
phases**. Every lesson tells you *why it exists* (Purpose), *what you will
walk away with* (Aim), *exactly what to do* (Steps), and *how you'll know
you're done* (Done when). No lesson ends with a vague "understand X" — each
one ends with something you can point at.

## Seeing progress in real time

Three feedback loops, from seconds to months:

1. **The progress bars (instant).** `docs/learning/PROGRESS.md` is the
   master checklist — one checkbox per lesson. When a lesson's "Done when"
   is true, change its `[ ]` to `[x]`, then run:

   ```bash
   python scripts/learning_progress.py
   ```

   You get a bar per phase, an overall bar, and the next lesson queued up.
   Watching that bar fill is the point — run it as often as you like.

2. **The git journal (weekly).** After each lesson, commit your tick (plus
   any journal notes) with a message like `Learning: L1.3 complete`. Then
   `git log --oneline --grep="Learning:"` is a scrolling record of every
   step you've taken. From Phase 2 onward your commits start containing
   *code*, and the log quietly turns from a diary into a portfolio.

3. **The app itself (monthly).** Phase capstones make the app do something
   visible that *you* caused — your plant in the catalogue, your test in
   the suite, your fix on the map. That's the progress that counts.

A guard test (`tests/test_learning_progress.py`) keeps this folder honest,
the same way the rest of the repo is kept honest: if a lesson goes missing
from the checklist, or a lesson loses its Purpose/Aim/Done-when, the test
suite fails. The curriculum can't silently rot.

## Anatomy of a lesson

```
### L1.3 — Functions: inputs in, answer out
*Time: ~2 h · Builds on: L1.2*
**Purpose:** why this lesson exists — what it unlocks.
**Aim:** the concrete thing you'll produce or be able to do.
**Steps:** numbered, specific, no guessing.
**Done when:** a checkable statement. If it's true, tick the box.
```

## Rules of the road

- **One lesson at a time, in order** (within a phase). Skipping *phases*
  when bored is allowed; skipping "Done when" is not — it's the contract.
- **The journal habit:** several Aims say "write it in your journal" — that's
  `docs/learning/journal.md`, yours, free-form, committed with everything
  else. Explaining in your own words is where learning actually happens.
- **The AI ladder** (full version in `docs/LEARNING_ROADMAP.md`): through
  Phase 2 use AI to *explain*, never to do the lesson. From Phase 5, AI
  reviews your work — it doesn't write it. If AI does the lesson, the bar
  moves but you don't.
- **Nothing here can hurt the app.** Every experiment is undoable with git,
  and the test suite catches what git doesn't. Break things on purpose;
  that's Lesson 2.2.

## The phases

| Phase | File | Lessons | Time |
|---|---|---|---|
| 0 — Operate the machinery | [phase-0-machinery.md](phase-0-machinery.md) | 4 | ~5 h over 1–2 weeks |
| 1 — Python fundamentals | [phase-1-python.md](phase-1-python.md) | 10 | ~25–30 h over 6–10 weeks |
| 2 — Tests as your textbook | [phase-2-tests.md](phase-2-tests.md) | 4 | ~8 h over 2–4 weeks |
| 3 — The data layer | [phase-3-data.md](phase-3-data.md) | 5 | ~12 h over 3–5 weeks |
| 4 — The architecture | [phase-4-architecture.md](phase-4-architecture.md) | 5 | ~12 h over 4–6 weeks |
| 5 — Solo changes | [phase-5-solo.md](phase-5-solo.md) | 5 | open-ended |

Start here → [phase-0-machinery.md](phase-0-machinery.md), Lesson L0.1.
