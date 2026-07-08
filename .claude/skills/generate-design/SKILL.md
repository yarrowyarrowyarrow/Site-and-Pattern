---
name: generate-design
description: Use when touching the Generate Design pipeline — src/llm_design.py, src/design_critic.py, src/placement_score.py, src/habitat_score.py, src/design_goals.py, src/layout.py, src/zoning.py, src/exclusion.py, the generation controller/dialog/worker, or the offline generator. Covers the LLM-selects/Python-places division of labour, the spec→resolve→place→critic loop, scored-cell placement and layer ordering, the Habitat Value Score weights and its headline-stability rule, adding a design goal, and the fake-client test pattern.
---

# Generate Design — the LLM → deterministic-placement pipeline

## Purpose / when to use

"Generate Design" is the app's flagship and most complex subsystem
(~7,400 lines across the generation/scoring cluster). One click turns a
brief + goals into a placed, scored, critiqued starting design. Use this
skill when you: change what the generator selects or where it places;
add a design goal; touch the critic/repair loop; change the Habitat
Value Score or placement scoring; or debug "the generator placed
something weird".

## The division of labour (the design's one big idea)

> **The LLM does ecological *selection* (which species, communities,
> structures suit the brief). Python does ALL the *geometry*.**

The model returns a compact JSON spec of names/queries/quantities —
never coordinates. Python resolves names against the catalogue and lays
everything out deterministically, so positions are always valid no
matter how bad the model is at arithmetic. Uphold this split in any
change: if you're tempted to ask the LLM for positions, sizes, or
distances, stop — that belongs in the placement engine.

The LLM is **optional**: `generate_design_offline` builds a design from
goal filters + seeded communities with zero network, and
`src/generate_worker.py` transparently falls back to it on any
`LLMError`, so the one-click button always yields a design.

## Pipeline in one page

```
GUI: src/generate_design_dialog.py  (brief, goal checkboxes, offline toggle,
  │                                  budget, wildlife picker, density, match-site)
  ▼
src/controllers/generation.py  GenerationController.open_dialog
  │   persists goals → site_config["priorities"], hands over existing features (F5)
  ▼
src/generate_worker.py  GenerateWorker on a QThread
  │   offline flag → generate_design_offline;  LLMError → falls back to it
  ▼
src/llm_design.py  generate_design(prompt, …)
  │ 1. zone context up front: elevation grid + wet/dry zones (src/zoning.py),
  │    keep-out circles + fill regions (src/exclusion.py), scored cell map
  │    (src/placement_score.py build_cell_env_map)
  │ 2. build context digests (palette, communities, structures, fauna, zones)
  │    → LLMClient.generate_spec → JSON spec {plants, communities, structures}
  │ 3. _resolve_* : names/queries → catalogue ids (unmatched entries DROP;
  │    all-unmatched raises LLMError). Budget trim BEFORE placement
  │    (src/sourcing.py trim_to_budget).
  │ 4. _place_within_boundary: layer-ordered (_LAYER_ORDER: trees first,
  │    groundcover last), ScoredPositioner picks best-scoring free cells,
  │    dripline bonus pulls understory to new canopy, keep-out + fill-region
  │    clipping, per-plant catalogue spacing, layout patterns (src/layout.py)
  │ 5. critic loop (src/design_critic.py): evaluate → critique_lines →
  │    LLM revise_spec → re-place → adopt ONLY if Habitat Score improves
  │ 6. deterministic apply_repairs (≤3: keystone/host/bloom-gap fills),
  │    goal + fauna feedback fills, budget note → generation_warnings
  ▼
Project (facade dict)  →  GenerationController._render  (@undoable, ONE
placement_group_id, pattern_kind="generated", through src/project_store.py)
```

Headless callers: `python -m src.cli generate` and the MCP
`generate_design` tool wrap the same functions (see `agent-api`).

## LLM client facts

`LLMClient` (`src/llm_design.py`) speaks any OpenAI-compatible
chat-completions endpoint; the default is **local Ollama**
(`http://localhost:11434/v1`, model `llama3.2`) so it runs fully offline
with stdlib `urllib` only. Resolution order for endpoint/model:
explicit arg → `PERMADESIGN_LLM_ENDPOINT`/`PERMADESIGN_LLM_MODEL` env →
`~/.permadesign_config.json` via `src/settings.py` (`llm_endpoint` /
`llm_model`) → built-in default. Timeout 120 s. The User-Agent keeps the
legacy `PermaDesign/1.0` string on purpose (see `legacy-lessons`).

Spec safety rails, in order of defence:
- `_parse_spec_json` tolerates markdown fences / prose around the JSON.
- `_validate_spec` rejects non-dict or empty specs (`LLMError`).
- `_ALLOWED_FILTERS` allowlists which plant-search filters the model may
  emit — anything else is dropped so a hallucinated filter name can't
  crash `search_plants`. **If you add a filter to `query_plants`, add it
  here too or the model can never use it** (and remember the facade
  contract snapshot — see `agent-api`).
- `_coerce_qty` clamps quantities; unmatched plant/community/structure
  entries are silently dropped, and only an entirely-empty resolution
  raises.

## Placement engine facts (the deterministic half)

- The anchor pool is `grid_cells_in_boundary` at `_SPACING_M` = 6 m.
  Anchors inside keep-out circles (existing trees/buildings/water,
  `src/exclusion.py:keepout_circles`) are removed; when the user drew
  restoration/lawn-conversion fill zones, the pool is restricted to them
  (`fill_regions`) — guarded so an empty restriction falls back to the
  whole boundary rather than starving placement.
- Plants place in **ecological layer order** — `_LAYER_ORDER` maps
  plant_type tree→0 … groundcover→6 — so canopy anchors first and a
  **dripline bonus** attracts understory into the zone around freshly
  placed trees. Stable sort preserves the model's order within a layer.
- `ScoredPositioner.take_best` picks the highest-scoring free cell for
  each plant using the pre-computed `cell_env_map`
  (`src/placement_score.py:build_cell_env_map` — shade fraction,
  elevation percentile, slope, aspect, edge flag per cell). **No DB or
  network calls at score time** — everything environmental is
  pre-computed once per design pass; keep it that way, it's the perf
  contract. When terrain data is absent the older zone-routing
  `_Positioner` (wet/dry/shaded buckets from `src/zoning.py`) is the
  fallback.
- Density: `_DENSITY_FRACTION` = sparse 0.30 / balanced 0.60 / full 0.90
  of the boundary's plantable capacity, with an absolute cap
  `_MAX_GENERATED_PLANTS = 300` — a generated design is a workable seed
  the user refines, not thousands of markers that stall the map.
- Layout patterns (`src/layout.py`): row/grid/circle/scatter/drift.
  `scatter_positions` and `drift_positions` use `random.Random(seed)` —
  **deterministic for a given seed**. Never introduce unseeded
  randomness anywhere in placement; "realizing the same spec twice gives
  the same design" is what makes the critic's re-place step cheap and
  the tests stable.
- Per-plant spacing comes from the catalogue (`_plant_spacing_m`),
  falling back to 6 m. Community placement checks `community_fits`
  before anchoring.

## The critic loop (P8/P9 made executable)

`src/design_critic.py` closes the evaluate→revise→repair loop:

1. `evaluate_design` scores the placed project with the **same** Habitat
   Value Score the Analysis panel shows — one metric, no private critic
   scale.
2. `critique_lines` turns the breakdown into concrete issues ("no bloom
   in August", "no keystone species"); `LLMClient.revise_spec` feeds
   them back to the model.
3. The revised spec is re-placed and adopted **only if the total score
   improves** — the loop can never make a design worse by our own
   metric. Any exception in the revision round is swallowed and the
   valid round-1 design ships. Keep both properties intact.
4. `apply_repairs` is the deterministic backstop (runs with or without
   an LLM): missing keystone → add one, missing host plant → add one,
   bloom-gap months → add natives flowering then — capped at
   `_MAX_REPAIRS = 3` because the critic mends gaps, it doesn't take
   over the design.

Everything the generator did to the user's request is reported in
`properties.generation_warnings` (revision adopted, budget trims,
goal/fauna feedback fills, unbacked goals). The GUI shows them in a
"Design notes" dialog. **This is the P9 honesty channel — when your
change alters or drops something the user asked for, append a warning;
never adjust silently.**

## Habitat Value Score (`src/habitat_score.py`)

The 0–100 headline is the sum of seven components (max points):

| Component | Max | Full marks at |
|---|---|---|
| % native species | 20 | 100% native |
| Keystone species | 15 | 5 distinct |
| Larval-host species | 10 | see code |
| Bird-food species | 10 | see code |
| Vertical layers | 15 | canonical layers present |
| Habitat structures | 10 | distinct structure types |
| Bloom continuity | 20 | no growing-season gap months |

**The stability rule:** fields like `n_lepidoptera_supported`,
`fauna_by_taxon`, and `food_web` are reported alongside but deliberately
**NOT summed into the headline**, so existing designs' scores stay
stable as the fauna dataset grows. If you add a metric, default to
informational/un-summed; changing the headline weighting is a
philosophy-level decision (P6) — flag it, update
`tests/test_habitat_score.py` deliberately, and expect every generated
design and the critic's adoption threshold to feel it. Species count
once toward diversity regardless of duplicates; `habitat_nudges`
(tested in `tests/test_habitat_nudges.py`) turns headroom into the
On-This-Design tips.

## Adding a design goal

Goals live in `GOALS` in `src/design_goals.py` — a `Goal` dataclass:
`key` (stable id, stored in `site_config["priorities"]`, a CLI choice),
`label` (checkbox text), `filters` (hard `query_plants` filters),
`prompt_hint` (appended to the LLM brief), `community_hints` (substring
match against seeded community names for the offline path), `backed`
(False = hint-only, reported via `unbacked_goals` → a generation
warning), `caveat` (shown when the goal is honoured by a denylist — e.g.
pet-safe excludes *known*-toxic plants, which is not a safety
guarantee; see `seed-data` on why empty ≠ "none").

The dialog, CLI (`--goal` choices) and offline selector all read the
registry — adding a `Goal` is one edit. List order = checkbox order.
Add coverage in `tests/test_design_goals.py`. A goal whose filter has no
data backing yet should ship `backed=False` with a `prompt_hint` (the
honest state) rather than a filter that silently matches nothing —
`docs/data_gaps_v1.44.md` tracks what data each unbacked goal awaits.

## Pitfalls & gotchas (real ones)

- **Never let the LLM produce geometry.** Also never *trust* spec
  content beyond the allowlisted filters — resolution against the
  catalogue is the boundary between model output and app state.
- **The GUI render path is sacrosanct**: `GenerationController._render`
  places through `store_for(main).add_plant(...)` under **one**
  `placement_group_id` with `pattern_kind="generated"`, wrapped in
  `@undoable("generate design")` — the whole design is one undo step and
  deletes as a unit. Bypassing the store trips
  `tests/test_project_store.py` (see `placed-plants`).
- **Determinism is load-bearing.** `_realize` re-places specs cheaply
  precisely because placement is pure; the critic's adopt-if-better
  comparison and the fake-client tests both depend on it.
- **Budget trims before placement**, not after — there is deliberately
  no "remove placed plant" API in the generator. A community that alone
  blows the budget is dropped only when individual plants remain to
  carry the design.
- **Everything degrades**: zone context, critic evaluation, fauna
  digests are all wrapped in broad try/excepts that fall back to
  simpler behaviour. A bug here often *looks* like "generator works but
  placement is dumber than expected" — check stderr, not just output.
- **`quantity` is real data**: a generated placement can represent
  several plants (`quantity` on the feature). Count totals via
  quantities, not feature count, when reporting.
- The `generate` CLI honours `--no-llm` (offline), `--goal` (repeat),
  `--density`, `--budget`, `--fauna`, `--lat/--lng`; MCP has a
  `generate_design` tool. Their surfaces are frozen by the contract
  test — see `agent-api` before renaming anything.
- **P12 applies to the prompt too.** The system prompt, goal hints, and
  community digests are recommendation surfaces — do not add framing
  that operationalizes Indigenous knowledge (see `philosophy-check`).

## Key files

| Path | What |
|---|---|
| `src/llm_design.py` | The pipeline: client, spec parsing/validation, resolution, positioners, placement, offline generator (~1,800 lines — the app's largest module). |
| `src/design_critic.py` | evaluate → critique → revise-adoption → deterministic repairs. |
| `src/placement_score.py` | Per-cell env map + plant-fit scoring + aesthetic terms + companion-proximity checks. |
| `src/habitat_score.py` | The 0–100 Habitat Value Score + nudges (shared GUI/critic/API). |
| `src/design_goals.py` | The `Goal` registry (single source for dialog/CLI/offline). |
| `src/layout.py` / `src/zoning.py` / `src/exclusion.py` | Patterns; wet/dry/shaded micro-zones; keep-out + fill regions. |
| `src/sourcing.py` | Price estimates + `trim_to_budget`. |
| `src/controllers/generation.py` + `src/generate_worker.py` + `src/generate_design_dialog.py` | Qt orchestration (dialog → thread → render). |
| `src/design_api.py` | `DesignGenerator` — the programmatic builder the facade wraps. |
| `src/pattern_language.py`, `src/succession.py`, `src/planting_spacing.py`, `src/lawn_zones.py`, `src/conversion_plan.py`, `src/polyculture.py` | Sibling Qt-free cores the generator draws on. |
| `tests/test_llm_design.py` | The `_FakeClient` end-to-end pattern — copy it. |

## Testing your change

Copy the `tests/test_llm_design.py` header: temp-DB redirect, then a
`_FakeClient` returning a canned spec drives `generate_design`
end-to-end with **no LLM and no network**. For critic tests, inject
synthetic `query_plants` / `position_for` callables
(`tests/test_design_critic.py`). Placement/scoring have their own
suites.

## Validation

```bash
# The generation test spine:
python3 -m unittest tests.test_llm_design tests.test_design_critic \
  tests.test_design_placement tests.test_placement_score \
  tests.test_habitat_score tests.test_habitat_nudges \
  tests.test_design_goals tests.test_exclusion tests.test_layout \
  tests.test_generate_dialog tests.test_agent_generation_loop -v

# Observe a real generated design headlessly (offline path, temp output):
python3 -m src.cli generate --no-llm --goal native_only --goal pollinator \
  --lat 53.5461 --lng -113.4938 --out /tmp/gen_check.perma.geojson

python3 -m unittest discover -s tests   # full suite before pushing
```

The Qt dialog/controller layer only gets offscreen smoke coverage — for
anything user-visible in the dialog or render path, see `verify`.
