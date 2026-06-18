# Site & Pattern — Mac Setup Guide

Two audiences, two parts:

- **Part A — For your friend (installing the app).** No Terminal, no coding.
  This is what you send along with the `.dmg`.
- **Part B — For you (building the `.dmg` on your Mac).** A few Terminal
  commands, once, to produce the file you share.

Big Sur (macOS 11) and newer are supported.

---

## Part A — For your friend: installing Site & Pattern

You'll receive one file: **`SiteAndPattern.dmg`**. Save it to your Downloads.

### Step 1 — Install the app
1. Double-click **`SiteAndPattern.dmg`**. A window opens.
2. Drag the **Site & Pattern** icon onto the **Applications** folder shown
   in that window.
3. Eject the disk (drag it to the Trash, which becomes an Eject button).

### Step 2 — Open it the FIRST time (one time only)
This app isn't registered with Apple, so macOS shows a security warning the
very first time. **The app is safe** — this just happens for apps from small
projects. **Double-clicking will NOT work the first time.** Do this instead:

**On macOS 11–14 (Big Sur, Monterey, Ventura, Sonoma):**
1. Open your **Applications** folder.
2. **Right-click** (or hold **Control** and click) **Site & Pattern**.
3. Choose **Open** from the menu.
4. Click **Open** in the box that appears.

**On macOS 15 (Sequoia) or newer** *(or if no "Open" button appears above)*:
1. Double-click **Site & Pattern** once — it gets blocked. Click **Done**.
2. Apple menu → **System Settings → Privacy & Security**.
3. Scroll to **Security**; next to "Site & Pattern was blocked…" click
   **Open Anyway** (enter your password if asked), then **Open Anyway** again.

> Not sure which macOS you have? Apple menu → **About This Mac**.

### Step 3 — Done
After that one time, Site & Pattern opens normally forever — just
double-click it.

### Getting new versions later (easy!)
Open Site & Pattern and choose **Help → Check for Updates…**. If a newer
version exists, the app downloads it for you and opens the installer — just
drag the new Site & Pattern onto Applications (choose **Replace**), then
reopen it. You can also pick any specific version under
**Help → Switch to a specific version…**.

> Nice bonus: because the app downloads the update itself, macOS does **not**
> show the security warning from Step 2 — updates install cleanly with no
> right-click needed.

**Apple Silicon Macs (M1/M2/M3/M4):** if macOS offers to install **Rosetta**
on first launch, click **Install** (one time), let it finish, and open the app
again.

**If it ever says "damaged" or won't open:** re-download the `.dmg` (a
half-finished download can corrupt it) and repeat Steps 1–2.

---

## Part B — For you: building the `.dmg` on your Mac

You build the app once on your Mac, then share the resulting
`dist/SiteAndPattern.dmg`.

### One-time prerequisites
- **Xcode Command Line Tools** (provides `git` and `codesign`):
  ```bash
  xcode-select --install
  ```
  Click through the installer if it pops up. (If already installed, it just
  says so.)
- **Python 3.10+**. Check with `python3 --version`. If missing, install from
  <https://www.python.org/downloads/macos/>.

### Get the code onto your Mac and build
Open **Terminal** (Applications → Utilities → Terminal) and run:

```bash
# 1. Download the code (creates a PermaDesign folder in your home directory)
cd ~
git clone https://github.com/yarrowyarrowyarrow/PermaDesign.git
cd PermaDesign

# 2. (Recommended) isolate dependencies in a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies (Qt is auto-pinned to a Big-Sur-compatible version)
pip install -r requirements.txt

# 4. Build the app + DMG (installs PyInstaller, signs, and verifies the seal)
bash build_installer.sh
```

When it finishes you'll have:
- **`dist/SiteAndPattern.dmg`** ← the file you share with friends
- `dist/SiteAndPattern.app` ← the app itself (test it with
  `open dist/SiteAndPattern.app`)

The build **verifies the code signature and stops with an error if it's
invalid**, so if it completes you have a DMG that opens with right-click →
Open (it won't be the un-fixable "damaged" kind).

### Updating to a newer version later
```bash
cd ~/PermaDesign
git pull
source venv/bin/activate
pip install -r requirements.txt   # usually a no-op
bash build_installer.sh
```

### Automatic publishing (so friends' apps can self-update)
A GitHub Actions workflow (`.github/workflows/release-macos.yml`) builds the
DMG on a cloud Mac and attaches it to a **GitHub Release** named after the
branch (e.g. `V1.73`) **every time you push a `V*` branch**. That published
DMG is what the in-app **Help → Check for Updates…** finds and installs, so
once you push a new `V` version your friends can update from inside the app —
you don't have to send them a new file. (You can still build locally with the
steps above for testing.)

### Which Mac should I build on? (important for compatibility)
PyInstaller builds for the **architecture of the Mac you build on**:

| You build on…        | The `.dmg` runs on…                                  |
|----------------------|------------------------------------------------------|
| **Intel Mac**        | Intel **and** Apple Silicon (via Rosetta) — widest reach |
| **Apple Silicon Mac**| **Apple Silicon only** (won't run on Intel Macs)     |

If any friend might have an older **Intel** Mac, build on an Intel Mac so the
single `.dmg` works for everyone. If everyone you're sharing with is on Apple
Silicon, building on your Apple Silicon Mac is fine.

### Why no "zero-click, no-warning" version?
Removing the first-launch warning entirely requires an **Apple Developer ID**
($99/year) plus notarizing the app with Apple. Without that, the free path is
the one-time right-click → Open in Part A. The build here is ad-hoc signed and
**verified**, which is what makes that right-click → Open reliably work.
