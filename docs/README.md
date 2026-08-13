# What each document here is for

Eighteen files is enough that "which of these matters?" is a fair question. This
is the map. Roughly in the order a newcomer should meet them.

## Start here

| Document | What it is | Read it when |
|---|---|---|
| [`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md) | **The founding text.** Thirteen principles, each with a "where this lives in the code" note and an honest *strong / partial / gap* marker. | Before designing anything. `tests/test_philosophy.py` guards it. |
| [`UI_PRINCIPLES.md`](UI_PRINCIPLES.md) | **The usability counterpart.** Steve Krug applied to this app: the three laws, how people actually use software, the two things that must die, and a checklist for any screen. `DESIGN_PHILOSOPHY.md` is what a feature should mean; this is whether anyone can work it. | Before laying out any panel, dialog or screen. |
| [`USER_GUIDE.md`](USER_GUIDE.md) | Every feature, from the user's side. | You want to know what the app does. |
| [`../README.md`](../README.md) | The project's front door. | First contact. |
| [`../CLAUDE.md`](../CLAUDE.md) | Conventions that are easy to miss — branch naming, schema bumps, the single write path. | Before your first commit. |

## Planning

| Document | What it is | Read it when |
|---|---|---|
| [`ROADMAP_NEXT.md`](ROADMAP_NEXT.md) | **The live plan.** F63–F82 and what comes after, grouped by theme, each with impact/effort/risk and a "how I'd build it". | Deciding what to do next. |
| [`PHILOSOPHY_ROADMAP.md`](PHILOSOPHY_ROADMAP.md) | Features organized by the *principle* they serve, with a Shipped section as the historical record. Long, and meant to be. | Asking "does this belong in this app?" |
| [`ROADMAP.md`](ROADMAP.md) | The effort/impact ledger — what shipped, tier by tier. **Historical**, not live. | Archaeology. |
| [`DATA_GAPS.md`](DATA_GAPS.md) | Seed-data debt: what the code is ready for and the catalogue is not. Photo coverage, flower-morphology provenance, the unbacked Generate-Design goals. | Wondering why a feature is a "hint" and not a filter. |
| [`DATA_SOURCES.md`](DATA_SOURCES.md) | **Where every shipped fact and photograph came from, and what its licence obliges.** Includes the position on reading numbers out of a copyrighted flora. | Anyone asks "are you allowed to have that?" — or before you add a new data source. |
| [`BOTANY_FIELD_GUIDE.md`](BOTANY_FIELD_GUIDE.md) | **The drawn vocabulary** — all 33 leaf shapes, inflorescence architectures and leaf arrangements, with a definition each — plus which phrase of a flora's description lands in which field, what to skip, and which corrections actually change the render. | Working through the catalogue with a flora open. |
| [`FAUNA_FIELD_GUIDE.md`](FAUNA_FIELD_GUIDE.md) | The same for the animals: wing shapes, patterns, resting postures, flight styles, bee builds — and the **bumblebee band pattern**, thorax to T6, which is what turns 29 identical *Bombus* into 29 animals. | Working through the bees and butterflies with a guide open. |
| [`FNA_PERMISSION_LETTER.md`](FNA_PERMISSION_LETTER.md) | An unsent draft asking the Flora of North America Association for permission to record floral measurements. | Deciding to fill the catalogue from published descriptions. |
| [`REFERENCES.md`](REFERENCES.md) | The bibliography behind the philosophy. | Citing, or checking a claim. |

## Reference

| Document | What it is |
|---|---|
| [`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md) | Every table and column, plus the version-bump checklist. |
| [`AGENT_API.md`](AGENT_API.md) | The headless scripting facade, the CLI, and the MCP tools. A frozen contract. |
| [`PROJECT_FILE_FORMAT.md`](PROJECT_FILE_FORMAT.md) | The `.perma.geojson` project file. |
| [`BUILD.md`](BUILD.md) | Building the installers, and the release/updater chain. |
| [`PUBLISHING_THE_SITE.md`](PUBLISHING_THE_SITE.md) | Getting the static plant directory onto the public web, free. |

## The 3D viewer

| Document | What it is |
|---|---|
| [`3D_SPRITES.md`](3D_SPRITES.md) | The **procedural** geometry — every archetype the viewer can draw without any assets, plus the live sprite gallery and the flower-tuning bench. The permanent fallback set. |
| [`3D_ASSETS.md`](3D_ASSETS.md) | The **baked** GLB library: the Blender generator package and the generator↔viewer contract. |
| [`SPRITE_AUDIT.md`](SPRITE_AUDIT.md) | How good the sprites actually are, scored for fidelity *and* distinctness, with four passes of what changed and what is still wrong. The honest record. |

## Working documents

| Document | What it is |
|---|---|
| [`review.md`](review.md) | The rubric for a deep-dive code review: conventions, decision log, per-area checklists. Overlaps with `.claude/skills/` — the skills are the task-shaped version, this is the review-shaped one. |
| [`LEARNING_ROADMAP.md`](LEARNING_ROADMAP.md) + [`learning/`](learning/) | The owner's self-study path from no programming background to owning this codebase. 33 lessons in six phases, with a progress checklist. Personal; `tests/test_learning_progress.py` keeps it honest. |
| [`3d/`](3d/) | Render evidence — before/after images referenced from the audit. |

---

**Retired in V2.35:** `archive/SESSION_HANDOFF.md` (dated March, and it named a
`claude/*` branch the branch policy now forbids — actively misleading) and
`archive/FEATURE_BRAINSTORM.md` (everything still live in it had been absorbed
into `PHILOSOPHY_ROADMAP.md`, which said so itself). `data_gaps_v1.44.md` became
`DATA_GAPS.md`, because seed-data debt outlives the release that noticed it.
