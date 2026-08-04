# Plans

One file per increment, written before the work and kept with it.

A plan here is not a status report — it is the **reasoning** behind a release:
what was actually wrong, what was measured, what was decided and why, and what
was deliberately left alone. The commit log says what changed; this says what we
believed at the time. When a later session asks "why is it like this?", the
answer should be findable without reconstructing it from diffs.

## Naming

```
docs/plans/V<major>.<minor>-<short-slug>.md
```

Version first, matching the release-branch convention in
[`CLAUDE.md`](../../CLAUDE.md), so plans sort in release order and a plan is
obviously paired with the branch that carried it out.

## Writing one

- **Lead with the evidence.** Numbers where there are numbers. "moist_mixedgrass
  is on 246 plants and aspen_parkland on 136" is worth more than "the ecoregion
  tags look wrong".
- **Say what you could not verify**, and why. A constraint recorded once saves
  the next session rediscovering it.
- **Record corrections in place.** When investigation falsifies part of the
  plan, amend it and say so — a plan that only ever describes what turned out to
  be true is a plan nobody can learn from.
- **Name what is not being done**, so the omission reads as a decision rather
  than an oversight.

## The plans

| Branch | Plan | What it set out to do | How it went |
|---|---|---|---|
| V2.37 | [user-feedback-easy-wins](V2.37-user-feedback-easy-wins.md) | Record the first outside tester's sixteen items; ship the ten that were cheap | All ten shipped. Three turned out to be features that already existed and could not be found — including PDF export, which had been raising `NameError` on every call for four minor versions behind a test that skipped. |
| V2.38 | [ecoregion-rebuild](V2.38-ecoregion-rebuild.md) | Second round of feedback: rebuild the ecoregion data properly, send feedback by email, fix three regressions | In progress. Both bugs and the sun/shade merge shipped; the ecoregion pipeline is built and tested, with its two network steps written up in [ecoregion-runbook](V2.38-ecoregion-runbook.md) for a machine with open egress. |
| V2.41 | [start-screen-and-directory](V2.41-start-screen-and-directory.md) | The start menu becomes a landing page with a third door, and F90 builds the room behind it: the catalogue as a browsable reference work with a species page | Shipped. The directory is almost entirely reuse — the list, the facets, the relationships layer and the quiz all existed. The find: `search_plants` takes thirty parameters and the design-side browser wires fourteen; sixteen filters had worked the whole time with nothing to press. Generate a design came off the start screen on the author's call. |
| V2.40 | [start-menu](V2.40-start-menu.md) | Promote the first-run welcome to a start menu: continue, open, and crash recovery as rows that appear only when they mean something — opened as its own window *before* the map | Shipped in two cuts. The first got the rows right and the moment wrong (a modal 150 ms after the map painted, which is a greeting over the app); the second moved the whole menu ahead of `MainWindow`, which is what the ask meant. Verifying that turned up three stacked process aborts that had been stopping the suite from ever printing a summary, and a real V2.40 regression hiding behind them. |
| V2.39 | [game-style-saves](V2.39-game-style-saves.md) | F87 — a saves folder, Save that stops asking, and an in-app list instead of the OS file dialog | Shipped. The autosave moved out of its `$HOME` dotfile in the same increment, with a copy-verify-unlink migration, because the one launch that needs it is the one after a crash. |
| V2.38 | [ecoregion-runbook](V2.38-ecoregion-runbook.md) | The two steps that cannot run in a cloud session — the CEC polygon download and the GBIF range derivation | Handed over. Not a plan so much as the other half of one; kept here because the reasoning behind the threshold and the two axes belongs with it. |
