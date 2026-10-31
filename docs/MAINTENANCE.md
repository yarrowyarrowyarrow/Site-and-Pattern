# Keeping Site & Pattern going

*The runbook (V3.32, FN-13 and FN-14; [`homeowner/10-finishing.md`](homeowner/10-finishing.md) §10).
Short on purpose: for whoever looks after the app once its owner has moved on.
Everything else is in [`CLAUDE.md`](../CLAUDE.md), which a Claude Code session
reads by itself.*

## What you are looking after

A free desktop app (Windows and macOS) that plans a native-plant yard in the
Edmonton region. Code, plans and data live in this repository. Every push to a
branch named like `V3.32` builds both installers on GitHub and attaches them to
a **prerelease**, which nobody's copy installs. Installed copies take a release
only after you **promote** it. That one step is the safety catch: a broken build
reaches nobody until you have tried it.

## Cut a release

1. **Work on the next V-branch.** If the newest is `V3.32`, the next is `V3.33`.
   A Claude Code session does this by itself (`.claude/hooks/branch_policy.py`).
   One branch, one version: never commit a second version onto an old branch.
2. **Push.** Three jobs run: *Tests*, *Build & publish Windows installer* and
   *Build & publish macOS DMG*. All three must go green (the Actions tab). If a
   push changes anything under `.github/workflows/`, follow it with one more
   commit before pushing: GitHub will not let a workflow tag the commit that
   changed a workflow, and publishing fails after both installers have built.
3. **Try the prerelease on a real Windows laptop.** From the release page
   (`Releases` on GitHub, named after the version), download the
   `-Setup.exe`, install it over a copy you already have, and:
   - open the example (start screen → *Look at an example yard*),
   - plan a yard (find an Edmonton address, draw a bed, *Plan my yard*),
   - print it (Share → Export → *Export PDF…*), and open the PDF.
   If anything there is wrong, fix it on the next V-branch; do not promote.
4. **Promote it.** On the release page: *Edit* → untick *Set as a pre-release* →
   tick *Set as the latest release* → *Update release*. Installed copies offer it
   at their next *Help → Check for Updates*. (The *Promote a release* workflow
   does the same with a check that both installers are attached, but GitHub
   lists a hand-run workflow only once its file is on `main`, which it is not
   yet.)

A later push to a promoted version makes it a prerelease again. That is on
purpose: the new build is the one nobody has tried.

## Run the tests yourself

```bash
QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox QT_QPA_PLATFORM=offscreen \
  python scripts/run_tests.py --exclude tests.test_undo_redo --max-skips 25
```

Read its `RESULT:` line. About 5,200 tests, half an hour. CI runs the same
command on every push, so you rarely need to.

## The build's versions

`scripts/packaging/constraints-windows.txt` and `constraints-macos.txt` say the
exact version of every library the installers carry, taken from the last good
build. Each installer also carries `build-versions.txt`, and the build log
prints it. A new Qt, numpy or PyInstaller is therefore a choice: change the
line, push, try the prerelease (step 3), then promote. The Windows build runs on
GitHub's `windows-2025` image with Python 3.11.9; the macOS build on `macos-14`
under Rosetta, with Qt held at 6.7 so the app still runs on macOS 11 Big Sur.

After adding a library to `requirements.txt` or `html/vendor/`, run
`python scripts/write_third_party_notices.py` and commit the
`THIRD_PARTY_NOTICES.txt` it writes; a test fails until you do.

## Every year

- **Nurseries.** The five in `data/regions/edmonton/region.json`
  (`nurseries`): check each still sells native plants. Fold their new
  availability lists in through the stock review page
  ([`tools/stock_review/README.md`](../tools/stock_review/README.md)).
- **Service terms.** Read again the terms of Open-Meteo (climate, free for
  non-commercial use, credit asked), OpenStreetMap's address search and tiles
  (no autocomplete, an identifying app name, at most a request a second), and
  Esri's World Imagery (the satellite view). Esri's terms could not be read when
  this was written (decision D4 in [`homeowner/12-decisions.md`](homeowner/12-decisions.md)):
  if they forbid a free app using the tiles without an account, make the street
  map the only default. Every service is listed in `src/services.py`, with what
  it is sent.
- **The domain.** `grownativeplants.ca` (the website, frozen for now) renews
  yearly with its registrar.
- **The tests**, on the pinned build (above).

## When a service breaks

The app keeps working without each one; nothing needs an emergency fix.

| Service | Without it | Where the code is |
|---|---|---|
| OpenStreetMap address search | "Couldn't search for addresses just now", and *Click my yard on the map* still works | `src/property_data.py` `geocode_address`, `src/site_panel.py` |
| Map tiles (Esri, OpenStreetMap) | The map tries the next basemap, then says it needs a connection; the design is safe | `html/map/01-core.js`, `html/map/11-map-furniture.js` |
| Open-Meteo (climate, elevation, wind) | Site Info says the region's typical figures instead | `src/property_data.py`, `src/region_climate.py`, `data/*_fallback_prairie.json` |
| SoilGrids (soil) | The offline soil pack if downloaded, else the regional soil atlas | `src/property_data.py` `fetch_soil`, `src/soil_grid.py` |
| Overpass (buildings, *Scan this area*) | Three public servers are asked in turn; with none answering, the buildings are read off OpenFreeMap's map tiles (no trees or streets that way), else the offline building pack, else the status line says "OpenStreetMap didn't answer", why (busy, too slow, refused, a certificate, offline) and what each server said | `src/osm_features.py`, `src/vector_tiles.py`, `src/building_store.py` |
| OpenFreeMap (map tiles, as data) | Only asked when Overpass did not answer; without it the import says what each server said | `src/vector_tiles.py` |
| iNaturalist photographs | Plant pages and lists show no photograph; nothing else changes | `src/db/photos.py`, `src/image_cache.py` |
| GitHub (*Check for Updates*) | Says it could not reach GitHub; the app carries on | `src/github_releases.py`, `src/controllers/update_flow.py` |

## Feedback

*Help → Send Feedback…* lets a person copy their message, open it on GitHub, or,
once an address is set, email it. To set the address, put a mailbox kept for the
app (never a person's own) in `data/edition.json` as
`"feedback_email": "…"` and push; the dialog shows it from then on.

Read what arrives monthly. Answer what is a bug. Decline what the app is not for
([`homeowner/01-personas.md`](homeowner/01-personas.md) §2: identifying a plant,
acreage and reclamation work, places outside Alberta and Saskatchewan, a
vegetable garden), and point them where that section says.

## What not to do

- **Never `git pull` a V-branch.** Old releases have a tag with the same name,
  and `git pull` silently takes the tag and rewinds your work. Fetch with
  `git fetch origin refs/heads/V3.32:refs/remotes/origin/V3.32`, then
  `git switch V3.32` ([`CLAUDE.md`](../CLAUDE.md) explains why).
- **Never push to `main`.** Releases come from V-branches.
- **Never delete a tag or a release.** Each one is what installed copies read to
  find updates.
- **Never promote a release you have not installed.**
- **Never put Indigenous knowledge into the data or the app** without the free,
  prior and informed consent of the communities it belongs to (Design principle
  12, [`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md)). Point to it; never encode it.

## Access (a second maintainer)

The owner does these once, so someone else can do everything above:

- [ ] **Add the maintainer as a collaborator** with *Write* access: the
      repository's *Settings → Collaborators and teams → Add people*.
- [ ] **The maintainer cuts one release** (above), start to finish, while the
      owner watches. That is how this runbook gets tested.
- [ ] **Share the session notes page** (`tools/usability/README.md`) with them as
      an editor.
- [ ] **Write down, somewhere outside this public repository,** who holds the
      `grownativeplants.ca` registrar account and the feedback mailbox, and how
      the maintainer reaches them.
- [ ] There is no code-signing account: the installers are unsigned on purpose
      (decisions D2 and D3), and the README says how to open them.
