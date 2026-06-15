# Building the Site & Pattern Windows Installer

Developer/maintainer guide for producing the one-click Windows `.exe`
installer. End users do **not** need any of this — they just run the
finished installer.

---

## What the finished installer does for the end user

- Single `SiteAndPattern-Installer.exe` — **no Python required** on the user's
  machine. The Python runtime, PyQt6/Qt WebEngine, and all data files are
  bundled inside.
- On first launch the app creates and **fully seeds** its database
  (`%APPDATA%\Site & Pattern\permadesign.db`) from the bundled `schema.sql` and
  `data\*.json`, so the plant and polyculture panels are populated
  immediately — no empty panels, no error dialogs.
- The app finds all its bundled files no matter where it was installed,
  because every runtime file is resolved through `src/resources.py`
  (`resource_path()` → `sys._MEIPASS` in a frozen build).

---

## Prerequisites (build machine)

| Tool | Version | Notes |
|------|---------|-------|
| Windows | 10 or 11, x64 | Target OS for the build and the installer. |
| Python | **3.11** (3.10+ works) | Must be x64 to match the target. Add to `PATH`. |
| Git | any recent | To clone and check out the release branch. |
| NSIS | **3.x** | Install to the default `C:\Program Files (x86)\NSIS\`. Get it from <https://nsis.sourceforge.io/Download>. Optional — without it the script falls back to a `.zip`. |

The Python dependencies themselves are installed automatically by the build
script from `requirements.txt` (PyQt6, PyQt6-WebEngine, python-docx, shapely,
numpy) plus PyInstaller.

---

## Build steps (Windows)

From a `cmd.exe` prompt in the repository root:

```bat
:: 1. Get the release branch
git clone https://github.com/yarrowyarrowyarrow/PermaDesign.git
cd PermaDesign
git checkout V1.57

:: 2. Create and activate a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate.bat

:: 3. Build — installs deps, runs PyInstaller, then NSIS
build_installer.bat
```

`build_installer.bat` performs, in order:

1. Kills any running `SiteAndPattern.exe` / `QtWebEngineProcess.exe` (so the old
   build isn't locked) and deletes `build\` and `dist\`.
2. `pip install -r requirements.txt` then `pip install pyinstaller`.
3. `pyinstaller permadesign.spec --clean` → `dist\SiteAndPattern\SiteAndPattern.exe`
   (one-directory bundle, with `data\`, `html\`, and `src\db\schema.sql`
   included via the spec's `datas`).
4. If NSIS is found, runs `makensis installer.nsi` → **`SiteAndPattern-Installer.exe`**
   in the repo root. Otherwise produces `SiteAndPattern-Windows.zip` as a fallback.

**Output:** `SiteAndPattern-Installer.exe` (~200–300 MB). Ship this file.

---

## Verifying a build

1. Run the installer on a clean Windows VM (one with **no** Python) and accept
   a **non-default** install directory to confirm path handling.
2. Launch from the Desktop / Start-Menu shortcut.
3. Confirm: the plant browser and the polyculture/community panels are
   populated, the Leaflet map loads, and **no** error dialogs appear.

To sanity-check the bundled-resource resolution without a Windows box, run the
test suite (it includes a frozen-build simulation):

```bash
python -m unittest discover -s tests
```

---

## How resource bundling works (for future maintainers)

- The PyInstaller spec (`permadesign.spec`) lists every non-Python runtime
  file in `datas`, preserving its relative layout:
  `('data', 'data')`, `('html', 'html')`, `('src/db/schema.sql', 'src/db')`.
- At runtime the app **must not** build paths from `__file__` — a module's
  `__file__` is unreliable once frozen into the PYZ archive. Instead it calls
  `resource_path("data", "plants_master.json")` etc. (`src/resources.py`),
  which returns a path under `sys._MEIPASS` in a frozen build and under the
  repo root in a source checkout.
- **If you add a new bundled data file**, do both: add it to `datas` in
  `permadesign.spec`, and read it via `resource_path(...)`. `installer.nsi`
  needs no change — it bundles the entire PyInstaller output with
  `File /r "dist\SiteAndPattern\*.*"`.
- The user database lives in `%APPDATA%\Site & Pattern\` (writable), **not** in
  the install directory — so it survives reinstalls/upgrades and never needs
  write access to `Program Files`.

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `ERROR: could not delete build\` | An old `SiteAndPattern.exe` or an Explorer window is holding a lock. Close them and rerun. |
| App launches but panels are empty / `no such table` | A bundled data file isn't being found. Confirm it's in `permadesign.spec` `datas` **and** read via `resource_path(...)`. |
| NSIS step skipped, only a `.zip` produced | NSIS isn't installed at `C:\Program Files (x86)\NSIS\`. Install it and rerun, or ship the `.zip`. |
| PyInstaller can't find `PyQt6` | The venv wasn't activated / `requirements.txt` didn't install. Activate `venv` and rerun. |

---

## macOS / Linux

`build_installer.sh` produces `dist/SiteAndPattern.dmg` (macOS) or
`SiteAndPattern-Linux.zip` (Linux) from the same `permadesign.spec`. The
resource-path fixes apply identically on those platforms.
