# Installing Site & Pattern

How to get Site & Pattern running, whether you're a non-technical user with a
one-click installer or running from source. Pick the section that matches you:

- **[Windows — one-click installer](#windows--one-click-installer)** (easiest)
- **[macOS — `.dmg`](#macos--dmg)** (easiest on Mac)
- **[From source](#from-source-any-platform)** (Windows / macOS / Linux)
- **[Updating](#updating-to-the-newest-version)**
- **[Troubleshooting](#troubleshooting)** · **[Where your files live](#where-your-files-live)**

> Building the installers yourself? See **[docs/BUILD.md](docs/BUILD.md)**.
> Learning the app? See **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**.

---

## Windows — one-click installer

No Python, no command line.

### 1. Download
Go to the project's **Releases** page (GitHub → "Releases" on the right sidebar)
and download **`SiteAndPattern-Installer.exe`** from the latest release. If the
release only ships `SiteAndPattern-Windows.zip`, use the [zip fallback](#windows-zip-fallback).

### 2. Install
1. Double-click **`SiteAndPattern-Installer.exe`** in Downloads.
2. Windows SmartScreen may warn ("Windows protected your PC"). Click
   **More info → Run anyway** — this appears only because the installer isn't
   code-signed; the file is safe.
3. Click **Next** through the screens (the default install folder is fine; leave
   **Create desktop shortcut** checked), then **Install → Finish**.

### 3. Launch
Double-click the **Site & Pattern** desktop icon, or find it in the Start menu.
The first launch takes 5–10 seconds while the plant database is set up (one time).

### Windows zip fallback
If the release only has `SiteAndPattern-Windows.zip`:
1. Right-click the zip → **Extract All…** → choose your Desktop.
2. Open the extracted **Site & Pattern** folder.
3. Double-click **`SiteAndPattern.exe`**. No installation needed — keep the whole
   folder together.

---

## macOS — `.dmg`

You'll receive one file: **`SiteAndPattern.dmg`**. Big Sur (macOS 11) and newer
are supported.

### 1. Install
1. Double-click **`SiteAndPattern.dmg`**.
2. Drag the **Site & Pattern** icon onto the **Applications** folder in the window.
3. Eject the disk image.

### 2. Open it the FIRST time (one time only)
The app isn't registered with Apple, so macOS blocks the first launch.
**The app is safe** — double-clicking won't work the first time; do this instead:

**macOS 11–14 (Big Sur, Monterey, Ventura, Sonoma):**
1. Open **Applications**.
2. **Right-click** (or Control-click) **Site & Pattern** → **Open**.
3. Click **Open** in the dialog.

**macOS 15 (Sequoia) or newer** (or if no "Open" button appears above):
1. Double-click **Site & Pattern** once — it gets blocked. Click **Done**.
2. Apple menu → **System Settings → Privacy & Security**.
3. Under **Security**, next to "Site & Pattern was blocked…", click
   **Open Anyway** (enter your password if asked), then **Open Anyway** again.

> Not sure which macOS you have? Apple menu → **About This Mac**.

After that one time, the app opens normally forever — just double-click it.

**Apple Silicon Macs (M1/M2/M3/M4):** if macOS offers to install **Rosetta** on
first launch, click **Install** (one time), let it finish, and reopen the app.

**If it ever says "damaged" or won't open:** re-download the `.dmg` (a
half-finished download can corrupt it) and repeat steps 1–2.

---

## From source (any platform)

Useful if an installer isn't available for the version you want, or if you plan
to tinker with the code. Requires **Python 3.10+** and **Git**.

```bash
# 1. Clone the repository (creates a Site-and-Pattern folder)
git clone https://github.com/yarrowyarrowyarrow/Site-and-Pattern.git
cd Site-and-Pattern

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate              # macOS / Linux
# venv\Scripts\activate.bat            # Windows (Command Prompt)
# venv\Scripts\Activate.ps1            # Windows (PowerShell)

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python main.py
```

The app opens immediately. On first run the database is seeded automatically from
the bundled plant data (a few extra seconds, one time).

> **macOS note:** `requirements.txt` automatically pins Qt to the 6.7 series —
> the last release that still runs on macOS 11 Big Sur. Don't override the pin.

### Windows from source — step by step
1. Install **Python** from [python.org/downloads](https://www.python.org/downloads/)
   — on the first installer screen, check **"Add Python to PATH"** before
   clicking Install. Verify with `python --version`.
2. Install **Git** from [git-scm.com/download/win](https://git-scm.com/download/win)
   (defaults are fine).
3. Open **Command Prompt** and run the four steps above (use the
   `venv\Scripts\activate.bat` activation line).
4. To launch later: open the project folder, type `cmd` in the address bar, press
   Enter, and run `python main.py`. Keep the Command Prompt window open while you
   use the app.

---

## Updating to the newest version

### Easiest — the in-app button
Open Site & Pattern → **Help → Check for Updates…**:
- **Source installs** — the app runs `git pull` for you. If you have unsaved
  local edits it offers **Stash & update** (keeps them) or **Discard & update**.
  It shows incoming commits, then asks you to **close and relaunch** so the new
  code loads.
- **Frozen installs** (`.exe` / `.dmg`) — the app fetches published versions from
  GitHub Releases and downloads + opens the matching installer in-app. On macOS,
  an app-initiated download isn't quarantined, so updates install with **no
  Gatekeeper warning**. You can also pick a specific version under
  **Help → Switch to a specific version…**.

### From source — terminal
```bash
cd Site-and-Pattern
git pull
source venv/bin/activate
pip install -r requirements.txt   # usually a no-op
python main.py
```
If `git pull` complains about local changes: `git stash` → `git pull` →
`git stash pop` to keep your edits, or `git checkout -- .` then `git pull` to
discard them. (`git status` first if unsure.)

On the first launch after an update, the database may take a few extra seconds to
apply schema migrations and reseed new plant communities. That's normal.

### From the `.exe` installer
Download the newest `SiteAndPattern-Installer.exe` from the Releases page and run
it — it updates the existing install in place; your designs and database are kept.

---

## Where your files live

- **Designs** save wherever you choose with **File → Save** (`.geojson` files).
- **Plant database** lives in the per-user data folder, **not** in the install
  directory, so it survives reinstalls:
  - Windows: `%APPDATA%\Site & Pattern\permadesign.db`
  - macOS: `~/Library/Application Support/Site & Pattern/permadesign.db`
  - Linux: `~/.local/share/Site & Pattern/permadesign.db`

  Deleting it forces a fresh seed on next launch. Settings live alongside it.

---

## Troubleshooting

**Windows installer blocked ("Windows protected your PC")** — click
**More info → Run anyway** (the installer isn't code-signed).

**macOS won't open the app** — see the [first-time open steps](#2-open-it-the-first-time-one-time-only)
above; for a "damaged" message, re-download the `.dmg`.

**App opens but the map is black** — wait 5–10 seconds for map tiles, and check
your internet connection.

**`"python is not recognized"`** (Windows from source) — Python wasn't added to
PATH; reinstall and check **"Add Python to PATH"**.

**The Command Prompt closes and the app disappears** (from source) — an error
occurred; reopen Command Prompt in the project folder, run `python main.py`, and
read the error message.

**Network features fail (no plant photos / elevation / OSM import)** — Python
needs root certificates; reinstall dependencies with
`pip install -r requirements.txt` (Site & Pattern wires up `certifi` at startup).
