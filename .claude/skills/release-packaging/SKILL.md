---
name: release-packaging
description: Use when building installers, cutting a release, or debugging a build/updater failure — the Windows PyInstaller+NSIS path, the macOS DMG path, the automatic push-V-branch → GitHub Actions → DMG/EXE → GitHub Release → in-app updater chain, how a frozen build learns its version (version.txt / src/app_version.py), how data/ and html/ get bundled (src/resources.py + the .spec), and the optional-deps lesson that keeps the frozen build green.
---

# Release & packaging

## Two worlds: source run vs frozen build

- **Source checkout** (`python main.py`) — runs from the tree; the updater
  reads the newest `origin/V*.*` branch (see `start-work`). No `version.txt`.
- **Frozen build** (`.dmg` / `.exe`) — a PyInstaller one-directory bundle with
  no git. It learns its own version from a bundled `version.txt`
  (`src/app_version.py` `build_version()`), and the updater lists **GitHub
  Releases** by tag to find newer installers.

`resource_path(...)` (`src/resources.py`) is what makes bundled data work in
both worlds: source → repo root; frozen → `sys._MEIPASS`. Always resolve
`data/`, `html/`, and `src/db/schema.sql` through it, never `__file__` joins.

## The automatic release chain (how a version ships)

```
push to a V<major>.<minor> branch
      │
      ├─►  .github/workflows/release-macos.yml   (GitHub-hosted Apple-Silicon Mac)
      │        builds an x86_64 DMG under Rosetta → publishes to a GitHub Release (tag = branch)
      │
      └─►  .github/workflows/release-windows.yml  (Windows runner)
               builds the NSIS EXE → publishes to the SAME GitHub Release
      │
      ▼
GitHub Release  (tag e.g. V2.19, assets: SiteAndPattern-V2.19.dmg + ...-Setup.exe)
      │
      ▼
in-app updater  src/github_releases.py  (list_releases / latest_release by tag)
                + src/controllers/update_flow.py  →  Help → Check for Updates downloads it
```

Key facts (from `.github/workflows/release-macos.yml`):
- Trigger: `push` to `branches: ['V[0-9]*.[0-9]*']` or manual `workflow_dispatch`.
- It runs on `macos-14` (Apple Silicon — GitHub retired Intel runners) but
  builds an **x86_64** app via Rosetta + a python.org universal2 Python, so
  ONE DMG runs on both Intel and Apple Silicon (Big Sur 11+).
- `APP_BUILD_VERSION: ${{ github.ref_name }}` is baked into `version.txt`;
  `PYI_TARGET_ARCH: x86_64` drives the spec's `EXE(target_arch=…)`.
- Publishes with `softprops/action-gh-release@v2`, `tag_name = ref_name`,
  `fail_on_unmatched_files: true`. The macOS and Windows workflows publish to
  the **same release** with an identical body, so whichever finishes last
  sets correct combined notes.

So: **pushing your V-branch is the release action.** There's no separate tag
step. Merge/label conventions aside, the branch push is what the workflows key
on. Only push when the branch is release-ready.

## Local builds (not run here — this container can't build installers)

From `docs/BUILD.md` (quote, don't assume). All invoked from the repo root;
the scripts `cd` to the root themselves.

Windows 1-click installer:
```bash
# not run here — from docs/BUILD.md (Windows)
scripts\packaging\build_installer.bat
```
Falls back to a ZIP if NSIS `makensis` isn't found; install NSIS to
`C:\Program Files (x86)\NSIS\` and rebuild for the true installer.

macOS DMG / Linux archive:
```bash
# not run here — from docs/BUILD.md
bash scripts/packaging/build_installer.sh
```

Manual PyInstaller (any OS):
```bash
# not run here — from docs/BUILD.md
pyinstaller scripts/packaging/permadesign.spec      # from the repo root
```

### What's in `scripts/packaging/`

| File | What it does |
|---|---|
| `permadesign.spec` | PyInstaller one-dir spec. Bundles `data/`, `html/`, `src/db/schema.sql` (and `version.txt` when present) via `datas`; artifact base name `SiteAndPattern` (no spaces), display name "Site & Pattern". |
| `build_installer.sh` | macOS/Linux build: clean, write `version.txt`, run PyInstaller, package DMG/archive. Called by `release-macos.yml`. |
| `build_installer.bat` | Windows equivalent; runs PyInstaller then NSIS. Called by `release-windows.yml`. |
| `installer.nsi` | NSIS script for the Windows 1-click installer (shortcuts, Start-Menu). |

## How a frozen build knows its version

`build_installer.sh` / `.bat` (or the workflow via `APP_BUILD_VERSION`) writes
a one-line `version.txt` holding the `V<major>.<minor>` tag. The spec bundles
it **only when present** (absent in a plain checkout). `src/app_version.py`
`build_version()` reads it via `resource_path("version.txt")`; a source
checkout returns `None` and the updater falls back to the live git branch.

## Resource bundling (why installs don't crash with "no such file")

The spec's `datas` entries preserve the relative layout (`data/`, `html/`,
`src/db/schema.sql`) under the bundle root, and every runtime read goes
through `resource_path`. If you add a new shipped data/HTML file:
1. Add it to `datas` in `scripts/packaging/permadesign.spec`.
2. Read it via `resource_path(...)`, never `__file__`-relative.
3. `tests/test_resource_path.py` simulates the frozen layout — run it.

Missing Python module in the frozen app → add it to `hiddenimports` in the
spec (see `docs/BUILD.md`).

## The optional-deps lesson (commit dface97 — internalize this)

`git show dface97 --stat`: *"Fix macOS DMG (and Windows EXE) build: move
rasterio/pyproj to optional reqs."* The macOS DMG **stopped building at
V2.17**, where a feature added `rasterio` + `pyproj` to `requirements.txt`.
The release workflows `pip install -r requirements.txt` on the CI machine, and
those deps pull in native GDAL/PROJ that **fail to install/bundle** under the
Rosetta x86_64 toolchain — so the DMG job errored and published no asset.

The fix: move them to `requirements-optional.txt`. Every `rasterio`/`pyproj`
import in the tree is already **lazy** (`soil_grid`, `hrdem`, `footprint_ndsm`,
`projection`) and the code degrades gracefully (SoilGrids / the 30 m
Copernicus DEM) without them.

**Rule:** anything you add to `requirements.txt` gets bundled into the frozen
build and installed on the CI runners. If a dep has heavy native wheels that
may not build there, and the feature degrades gracefully without it, put it in
`requirements-optional.txt` and guard the import lazily. Don't discover this by
a silently-missing release asset. See `run` (deps) and `offline-packs`.

## Verifying a build (from docs/BUILD.md)

1. Run the installer on a clean machine with **no** Python (a VM is ideal),
   using a **non-default** install dir to test path handling.
2. Launch from the shortcut / Applications folder.
3. Confirm the plant browser and community panels are populated, the Leaflet
   map loads, and no error dialogs appear.
4. Without a spare machine, `python3 -m unittest discover -s tests` includes a
   frozen-build resource-resolution simulation (`tests/test_resource_path.py`).

## Troubleshooting build/release failures

| Symptom | Cause / fix |
|---|---|
| DMG/EXE job errors, no release asset | A `requirements.txt` dep won't build on the runner (the dface97 trap) — move it to optional + lazy-guard. |
| Installed app: empty panels / "no such table" | A data file missing from `datas` or not read via `resource_path` (see `debugging` §1). |
| Installed app: "Missing module" | Add to `hiddenimports` in the spec. |
| "NSIS makensis not found" (Windows) | Falls back to ZIP; install NSIS and rebuild for the 1-click installer. |
| Network features dead in the frozen app | Certs — `src/ssl_bootstrap.py` / `certifi`; see `debugging` §6. |
| Updater doesn't see a new version | Branch/tag not `V<major>.<minor>`, or no Release published — check the workflow run. |

## Pitfalls

- **Pushing a V-branch triggers a real public release build.** Don't push a
  half-finished branch expecting it to be private — the workflows fire on the
  push. Confirm the branch is release-ready (see `start-work` definition of
  done).
- **Never add a heavy native dep to `requirements.txt` casually** — see the
  optional-deps lesson.
- **Keep the two release-workflow bodies identical** — they publish to the
  same GitHub Release; divergent notes get clobbered by whichever finishes
  last.
- The artifact base name is `SiteAndPattern` (quoting-safe); the display name
  is "Site & Pattern". Don't rename the artifact — NSIS/`.app`/shortcut paths
  depend on it.

## Key files

| Path | What |
|---|---|
| `docs/BUILD.md` | Full build + troubleshooting guide (authoritative). |
| `INSTALL.md` | End-user install instructions. |
| `.github/workflows/release-macos.yml` | Cloud-Mac x86_64 DMG build + Release publish. |
| `.github/workflows/release-windows.yml` | Windows NSIS EXE build + Release publish. |
| `scripts/packaging/permadesign.spec` | PyInstaller spec (`datas`, `hiddenimports`). |
| `scripts/packaging/build_installer.sh` | macOS/Linux build script. |
| `scripts/packaging/build_installer.bat` | Windows build script. |
| `scripts/packaging/installer.nsi` | NSIS installer script. |
| `src/app_version.py` | Reads bundled `version.txt` (frozen build's self-version). |
| `src/github_releases.py` | GitHub Releases lookup for the in-app updater. |
| `src/controllers/update_flow.py` | In-app "Check for Updates" flow. |
| `src/resources.py` | `resource_path` — frozen-safe bundled-file resolution. |
| `requirements.txt` / `requirements-optional.txt` | Bundled deps vs feature-gated deps. |

## Validation

```bash
python3 -m unittest tests.test_github_releases tests.test_resource_path -v
git show dface97 --stat        # the optional-deps lesson
```
