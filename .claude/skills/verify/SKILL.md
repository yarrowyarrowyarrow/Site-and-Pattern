---
name: verify
description: Use before committing a nontrivial change to prove it actually works end-to-end, not just that tests pass. Covers per-change-type verification recipes — pure logic, schema/seed, UI/widget, map JS, agent/API — the golden rule that a green suite is necessary but not sufficient for UI-visible changes, and the runnable probes (facade one-liners, temp-DB reinit, offscreen smoke) that close the gap.
---

# Verify a change end-to-end

This is the project-level verify skill. The goal is to **observe the changed
behaviour**, not just to see green tests. Match the recipe to what you
changed.

## Golden rule

> A green `unittest` suite is **necessary but not sufficient** for
> UI-visible changes.

Much of the domain logic is well covered, but widgets get only an
offscreen smoke test, and the Leaflet map and 3D pages are **not** exercised
headlessly at all. So for anything a user would *see*, tests passing is the
floor, not the ceiling — add a targeted probe (below), and where only a real
launch can confirm it, say so honestly in your summary rather than implying
you verified it.

## By change type

### Pure logic / scoring / analysis (Qt-free core module)

1. Run the module's own test(s): `python3 -m unittest tests.test_<module> -v`.
2. Drive it through the facade to see real numbers (this ran in-session):

   ```bash
   python3 -c "
   from src.permadesign_api import Project, query_plants, run_analysis
   proj = Project.create('Verify', boundary=[(53.55,-113.50),(53.55,-113.49),(53.54,-113.49),(53.54,-113.50)])
   proj.place_plant(query_plants(query='yarrow')[0]['id'], 53.545, -113.495)
   print(run_analysis(proj))
   "
   ```
3. Run the full suite once before pushing (slow, ~7 min — see `testing`).

### Schema / seed-data change

Prove the reseed actually produces what you intended, in a throwaway DB
(never your real one):

```bash
python3 -c "
import tempfile, os
import src.db.plants as p
d = tempfile.mkdtemp(prefix='verify_schema_')
p._DATA_DIR = d; p._DB_PATH = os.path.join(d, 'v.db')
p.init_db()
c = p.get_connection()
print('user_version =', c.execute('PRAGMA user_version').fetchone()[0])
print('plants =', c.execute('SELECT COUNT(*) FROM plants').fetchone()[0])
print('tables =', sorted(r[0] for r in c.execute(
    \"SELECT name FROM sqlite_master WHERE type='table'\")))
c.close()
"
```

Check: `user_version` equals your new `_SCHEMA_VERSION`; your new
table/column is present; row counts look right. Then run
`python3 -m src.cli validate-data` and your temp-DB test module. See
`schema-change` / `seed-data`.

### UI / widget change (PyQt6)

The offscreen smoke test instantiates `MainWindow` headlessly. When PyQt6 is
installed:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_app_smoke tests.test_plant_panel_smoke -v
```

This confirms construction, signal wiring, and that panels/tabs register —
but **not** that the widget looks or behaves right. For that, launch the app
(`run` skill) and exercise the specific control. If you can't launch (e.g.
headless CI, or PyQt6 absent — as in this container, where `python main.py`
fails with `ModuleNotFoundError: No module named 'PyQt6'`), state clearly in
your summary that you verified construction via offscreen smoke but could not
visually confirm.

### Map JS change (`html/map/*.js`)

1. `python3 -m unittest tests.test_map_js tests.test_bridge_contract tests.test_map_features -v`
   — these check the JS/bridge contract statically.
2. **What tests can't catch:** actual rendering, overlay draw, drag
   behaviour, Leaflet interactions. Those require launching the app and
   watching the routed JS console (see `map-frontend` / `debugging`). Say so
   if you couldn't launch.

### Agent / API / CLI / MCP change

```bash
python3 -m unittest tests.test_architecture_guard tests.test_permadesign_api tests.test_cli tests.test_mcp_server -v
python3 examples/agent_session.py          # full create→place→analyze→save round-trip
python3 -m src.cli list-structures         # or the subcommand you touched
```

If you changed the public surface, the guard test's `EXPECTED_*` snapshot
must be a deliberate edit — see `agent-api`.

## The honest-summary discipline

When you report a change as verified, say **what you actually observed** and
**what you couldn't**. "Full suite green; facade run shows habitat score
29→34 as intended; did not launch the GUI (PyQt6 absent here) so I did not
visually confirm the new tab renders" is a correct, useful summary. "Verified
✓" with nothing behind it is not.

## Pitfalls

- **Don't verify a schema change against the real user DB** — always a temp
  dir, or you mutate your own data and can't repeat the test.
- **Tests green ≠ map works.** The map and 3D pages have no headless render
  path. Budget a manual launch for anything visual, or flag the gap.
- **The full suite is slow** (network tests) — during iteration verify the
  touched module + guards, run the whole suite once before pushing.
- If a fetch-touching change "works," confirm it also works **offline**
  (fallback path) — see `external-data`.

## Validation

Minimum bar before commit:

```bash
python3 -m unittest tests.test_<the_module_you_touched> -v   # targeted
python3 -m unittest discover -s tests                        # full, once (slow)
```
plus the type-specific probe above.
