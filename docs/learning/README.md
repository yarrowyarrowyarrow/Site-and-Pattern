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

## The method: practices these lessons are built on

None of this is invented here — it's how programming is learned everywhere,
applied to this codebase. Six practices carry the whole curriculum; the
lessons assume you're using them even when they don't say so:

1. **Type everything yourself.** Never copy-paste code you're learning
   from — not from lessons, books, or AI. Typing is where syntax moves into
   your fingers, and mistyping is where you meet the error messages you
   need to know. (Copy-pasting *data* like coordinates is fine.)
2. **Predict before you run.** Before running anything — a function, a
   test, a query — write down what you expect. A confirmed prediction
   builds confidence; a wrong one is a precision-guided lesson showing
   exactly where your mental model differs from reality. Wrong predictions
   are the most valuable thing this curriculum produces.
3. **Retrieval beats rereading.** You learn when you pull knowledge *out*,
   not when you put it in front of your eyes again. Hence the journal's
   close-the-book rule, the "from memory" in so many Done-whens, and the
   review gate at the top of every phase. Rereading feels productive and
   isn't; struggling to remember feels unproductive and is.
4. **Short and often beats long and rare.** Three or four 30–60 minute
   sessions a week outperform one Saturday marathon — spacing is when the
   brain consolidates. Programming is a physical skill in this respect;
   nobody learns piano in monthly six-hour blocks.
5. **Struggle for twenty minutes, then ask small.** Being stuck is where
   learning happens — sit with a problem for ~20 minutes before seeking
   help. Then ask for the *smallest* useful thing: a hint, a where-to-look,
   an explanation of one line — never the whole answer. Log what unstuck
   you; it's usually the thing to check first next time.
6. **Park downhill.** End every session by writing tomorrow's first step in
   the journal while it's obvious ("next: run the JOIN query on the fauna
   table"). Restarting is the highest-friction moment in self-study — 
   leave yourself a running start.

Most lessons here follow the **PRIMM** cycle — Predict, Run, Investigate,
Modify, Make — a sequence designed specifically for learning *from existing
code*, which is exactly what learning a codebase is. You'll feel it: read
and predict (L1.2), run and check (everywhere), investigate by stepping
through (L1.4), modify and watch tests react (L2.2), make your own
(L1.10, L2.3, all of Phase 5).

**The session ritual** that stitches it together:

- *Warm-up (3 min):* before opening anything, write in the journal what you
  remember from last session — then check yourself.
- *Work:* the lesson, with the six practices above.
- *Wind-down (5 min):* journal what clicked and what's foggy, tick any
  finished lesson, run the tracker, commit, park downhill.

And one scope note: everything this curriculum teaches — terminal, git,
Python, testing, SQL, debugging, code reading — is the standard, portable
developer toolkit. You're learning it *on* Site & Pattern because owning
this app is the goal, but nothing here is only true here. Each phase file
names the transferable skill it builds.

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
