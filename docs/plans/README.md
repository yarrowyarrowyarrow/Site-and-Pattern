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
| V2.38 | [ecoregion-rebuild](V2.38-ecoregion-rebuild.md) | Second round of feedback: rebuild the ecoregion data properly, send feedback by email, fix three regressions | In progress. |
