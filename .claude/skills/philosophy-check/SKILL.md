---
name: philosophy-check
description: Use before designing or reviewing any feature, and whenever a change touches recommendations, seed data, scoring, or UI copy. Covers the pre-design fit check against the twelve principles, the P12 Indigenous-knowledge hard rule (stop-and-ask), the exact `Design principle P#` anchor convention that tests/test_philosophy.py enforces, keeping the State markers honest, and updating the roadmap Shipped section.
---

# Philosophy check

This project is not a generic plant-placement tool; it is built on a
coherent philosophy, and work that ignores it tends to be technically fine
but spiritually off. Do this check **before** you design, not after.

Sources of truth:
- `docs/DESIGN_PHILOSOPHY.md` — the twelve principles, each with a "Where
  this lives in the code" note and an honest **State** marker.
- `docs/PHILOSOPHY_ROADMAP.md` — features (F1–F…) organized by principle,
  with a **Shipped** section at the top and Impact/Effort/Risk ratings.
- `docs/REFERENCES.md` — the full bibliography (the source texts).

## The twelve principles (State as documented; verify against the doc)

| # | One line | State | Where it lives (see doc for the authoritative note) |
|---|---|---|---|
| 1 | Living systems self-organize bottom-up — encode generative rules, not fixed layouts | strong | `src/placement_score.py`, `src/llm_design.py`, `src/pattern_language.py` |
| 2 | The best designs disappear into their context ("grown, not designed") | strong | `src/placement_score.py`, `src/layout.py`, `src/planting_spacing.py`, `src/reference_ecosystem.py` |
| 3 | Relationships matter more than components — the edge is the unit of value | partial (strengthening) | `src/habitat_score.py`, fauna/junction data |
| 4 | Time is the most undervalued design variable — design the trajectory | strong | `src/succession.py`, `src/phenology.py`, snapshot timeline |
| 5 | Perception is constructed — make invisible ecology visible | partial | analysis panels, overlays, `src/docent.py` |
| 6 | Conventional value metrics miss ecological value — make it legible | strong | `src/habitat_score.py`, On-This-Design nudges |
| 7 | Generalist knowledge yields original insight — cross domains | foundational | cross-cutting (climate × soil × fauna × design) |
| 8 | Repair is more sophisticated than creation — conversion is first-class | strong (language); partial (placement) | `src/conversion_plan.py`, `src/lawn_zones.py` |
| 9 | Uncertainty is a feature — ship ranges and confidence, never false precision | strong (language); partial (placement) | leaf-off shade, chickadee ranges, `src/phenology.py` |
| 10 | Design for relationships, not objects — plants are nodes in a network | partial | `src/plant_impact.py`, fauna links |
| 11 | The body and the site know things the screen does not — drive the user outside | strong (was a gap) | `src/field_study.py`, field-notes, phenology "go verify" prompts |
| 12 | Indigenous knowledge is honoured through relationship, not extraction | directional guardrail | `CLAUDE.md`, the SessionStart hook — **see hard rule below** |

Treat this table as a map; the doc is authoritative. When your feature
changes a State, update the doc (below), not just this table.

## P12 — the hard rule (read in full)

**Do NOT incorporate Indigenous ecological knowledge, land-management
practices, plant-use traditions, or design frameworks into the data model,
recommendations, seed data, or UI without explicit *free, prior, and
informed consent* from the relevant communities.**

- Until that consent exists, treat any reference as **directional only** —
  point *toward* the knowledge, never encode or operationalize it.
- The single highest-risk surface is **seed data** (`data/*.json` plant-use
  / traditional-use fields) and **recommendations** (anything that would
  surface such knowledge as advice). See the `seed-data` skill.
- If a task seems to push in that direction, **stop and raise it with the
  user** rather than proceeding. This is a stop-and-ask, not a judgment
  call you make alone.

## Pre-design checklist

1. **Which principle(s) does this serve?** Name them. If you can't, the
   feature may be off-philosophy — reconsider or reframe.
2. **Does the roadmap already have it?** Search `docs/PHILOSOPHY_ROADMAP.md`
   for an F-number (`F5`, `F23`, …). If so, use that handle and its "how I'd
   build it" notes; if not, consider adding an entry.
3. **Does it conflict with any principle?** Common traps:
   - **P9 (uncertainty):** does it present a single hard number where a
     *range + confidence* is honest? False precision violates P9. Prefer
     ranges (as the chickadee-brood and leaf-off-shade features do).
   - **P10 / P3 (relationships):** does it treat a plant as an isolated
     object rather than a node in a network (companions, host/pollinator
     links, food web)? Object-thinking violates P10.
   - **P2 (grown, not designed):** does it produce gridded/stamped output
     instead of naturalistic drift? 
   - **P1 (generative rules):** does it hard-code a fixed layout instead of
     scoring candidates?
   - **P12:** the hard rule above.
4. **What State does it touch?** If it moves a principle gap→partial→strong,
   plan the doc update as part of the change.

## The anchor convention (enforced by a test)

Strongly-aligned modules carry a **one-line anchor at the top of the file**:

```
Design principle P# — see docs/DESIGN_PHILOSOPHY.md
```

Exact mechanics `tests/test_philosophy.py` checks:
- The regex is `Design principle P(\d+)`; the number must be **1–12** (a
  `P13` fails the build).
- At least **6 modules** must carry an anchor (a refactor that strips them
  all trips the test).
- The doc must document all twelve themes as `### N. ` headings, link
  `REFERENCES.md` and `PHILOSOPHY_ROADMAP.md`, and the app name must flow
  from `src/branding.py` (`APP_NAME == "Site & Pattern"`), not a hard-coded
  title in `src/app.py`.

**When to add an anchor:** only when the module is *strongly* aligned with a
principle — it implements that principle in a load-bearing way. Don't dilute
the convention by anchoring every file that vaguely relates. One primary
principle per module (name the strongest).

## Keeping State markers honest

If your feature strengthens a principle (e.g. moves P10 from *partial* toward
*strong* by adding real relationship modeling), **update the State marker**
in `docs/DESIGN_PHILOSOPHY.md` and the "Where this lives in the code" note to
mention your module. Honesty cuts both ways — don't upgrade a State on
aspiration; upgrade it when the code actually earns it. Overclaiming here is
worse than a gap, because the doc is how the next engineer calibrates.

## Updating the roadmap Shipped section

When you ship a roadmap feature, move it into the **Shipped** section at the
top of `docs/PHILOSOPHY_ROADMAP.md` (keep its F-id as the stable handle). Note
it in your commit subject too (`... (F46)`), matching the house style (see
`start-work`).

## Pitfalls

- **Anchoring a wrong or padded principle number** fails `test_philosophy.py`
  — use `P1`–`P12` only, no leading zeros beyond what the doc uses.
- **Silently regressing branding** (hard-coding the window title) trips the
  branding check — set the title from `src/branding.py` `APP_TITLE`.
- **Treating P12 as advisory.** It is a hard rule with a stop-and-ask, not a
  best-effort guideline.
- **Shipping false precision** to look impressive. Ranges + confidence are
  the house style; a single decimal where the data can't support it is an
  anti-pattern here.

## Key files

| Path | What |
|---|---|
| `docs/DESIGN_PHILOSOPHY.md` | The twelve principles + State markers (source of truth). |
| `docs/PHILOSOPHY_ROADMAP.md` | Features by principle + Shipped section. |
| `docs/REFERENCES.md` | The bibliography. |
| `tests/test_philosophy.py` | Enforces themes, anchors, and branding. |
| `src/branding.py` | `APP_NAME` / `APP_TITLE` — the rebrand's single source. |
| `.claude/hooks/philosophy_primer.sh` | SessionStart primer that keeps this front-of-mind. |

## Validation

```bash
python3 -m unittest tests.test_philosophy -v
```
