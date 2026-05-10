# PermaDesign — Friend Setup Guide for Windows

This guide walks you through getting PermaDesign running on a Windows laptop
from scratch. No coding experience needed — just follow each step in order.

There are two ways to install PermaDesign:

1. **One-click installer (recommended)** — download a single `.exe` file and
   click through it. No Python, no command line.
2. **From source** — useful if the installer is not yet available for the
   version you want, or if you plan to tinker with the code.

If you just want to use the app, do **Option 1** below and skip the rest.

---

## Option 1 — One-Click Installer (recommended)

### Step 1: Download the installer

1. Go to the project's **Releases** page (link from the PermaDesign GitHub
   page → "Releases" on the right sidebar).
2. Download **`PermaDesign-Installer.exe`** from the latest release.
   - If the release only ships `PermaDesign-Windows.zip`, see the
     "Zip-only fallback" section at the bottom of this option.

### Step 2: Run the installer

1. Double-click **`PermaDesign-Installer.exe`** in your Downloads folder.
2. Windows SmartScreen may show a blue warning ("Windows protected your PC").
   Click **More info** → **Run anyway**. This appears because the installer
   isn't code-signed; the file is safe.
3. Click **Next** through the installer screens.
   - You can change the install folder if you want, but the default is fine.
   - Leave the **Create desktop shortcut** box checked.
4. Click **Install** and wait for it to finish.
5. Click **Finish**. The installer is done.

### Step 3: Launch the app

- Double-click the **PermaDesign** icon on your desktop, **or**
- Open the Start menu, type **PermaDesign**, and press Enter.

The first launch may take 5–10 seconds while the plant database is set up.
That's normal and only happens once.

### Step 4: (Optional) Connect the Permapeople plant database

Skip this unless you want access to 8,500+ extra plant profiles from
[permapeople.org](https://permapeople.org).

1. Create a free account at **permapeople.org** and request API access from
   your account settings — you'll get a **Key ID** and a **Key Secret**.
2. In PermaDesign, click **⚙ Settings** in the toolbar.
3. Paste the Key ID and Key Secret into the two fields and click **Save**.
4. In the right-hand Plant Browser, switch to the **Permapeople** tab,
   search any plant, and click **Import to Local Database** to keep it.

### Zip-only fallback

If the release only has `PermaDesign-Windows.zip`:

1. Right-click the zip → **Extract All...** → choose your Desktop.
2. Open the extracted **PermaDesign** folder.
3. Double-click **`PermaDesign.exe`** to run the app.

No installation needed — keep the whole folder together.

---

## Option 2 — From Source (advanced)

Use this only if the one-click installer is not available, or if you want to
run the latest in-development code.

### Step 1: Install Python

1. Go to **python.org/downloads**
2. Click the big yellow "Download Python 3.x.x" button
3. Run the installer
4. **Important:** On the first screen, check the box that says
   **"Add Python to PATH"** before clicking Install
5. Click "Install Now" and wait for it to finish

Confirm it worked — open Command Prompt and run:
```
python --version
```
You should see something like `Python 3.11.x`.

### Step 2: Install Git

1. Go to **git-scm.com/download/win**
2. Run the installer; click Next through all screens (defaults are fine).

### Step 3: Download the app

1. Open **Command Prompt** (Start menu → search "cmd")
2. ```
   cd %USERPROFILE%\Desktop
   git clone https://github.com/yarrowyarrowyarrow/PermaDesign.git
   cd PermaDesign
   pip install -r requirements.txt
   ```

### Step 4: Run the app

Every time you want to use PermaDesign:

1. Open File Explorer → **Desktop → PermaDesign**
2. Click the address bar, type `cmd`, press Enter
3. ```
   python main.py
   ```
4. Keep the Command Prompt window open while you use the app.

---

## Basic App Functionality

The same workflow applies whether you installed via the `.exe` or from source.

| Step | What to do | How |
|---|---|---|
| 1 | **Find your property** | Type the address in the Site panel's Address Finder, or click **Use Pin Drop** and click on the map. |
| 2 | **Draw your boundary** | Toolbar → **Boundary** → click points around your lot → double-click to close. |
| 3 | **Switch to satellite** | Top **View** bar → toggle **Satellite**. The View bar groups: Satellite, Boundary, Measurement, Grid, Plants, Canopy, Structures. |
| 4 | **Pick a plant** | In the right Plant panel, search by name or use the filters (Native AB, Edible, Pollinator, …). |
| 5 | **Place a plant** | Select it → click **Place on Map** → click the spot. The canopy circle previews mature size. |
| 6 | **Place a polyculture** | In the **Polycultures** tab, double-click a polyculture and click on the map to drop the whole grouping. |
| 7 | **Build a custom polyculture** | Polycultures tab → **New** → use the visual grid to add 5–8 Alberta-suitable plants → **Save**. The polyculture is stored locally and reusable. |
| 8 | **Move things you've placed** | Click and drag any placed plant. To move an entire polyculture as one unit, click its centre marker and drag. |
| 9 | **Measure distances** | View bar → **Measurement** → click two points. Toggling Measurement off **hides** measurements; right-click a measurement to delete it. |
| 10 | **Snap to grid** | View bar → **Grid** dropdown → choose 1×1 m / 5×5 m / 10×10 m / 100×100 m, and adjust opacity/colour. |
| 11 | **Undo a mistake** | **Ctrl+Z** undoes the last placement (plants, structures, boundaries, contours — all globally). |
| 12 | **Save your design** | **File → Save** (Ctrl+S). Designs are stored as `.geojson` files anywhere on your computer. |
| 13 | **Export a PDF** | **File → Export PDF**. Includes map screenshot, plant list, and notes. |

---

## Troubleshooting

**One-click installer is blocked by Windows ("Windows protected your PC")**
- Click **More info** → **Run anyway**. The installer is not code-signed,
  which is normal for a small project.

**The app opens but the map is black**
- Wait 5–10 seconds for the map tiles to load
- Make sure you have an internet connection

**App crashes when I click "Clear" on the address finder**
- Known issue being patched this sprint. As a workaround, use the small ✕ on
  the address field to clear instead of the big Clear button.

**"python is not recognized"** (from-source only)
- You forgot to check "Add Python to PATH" during install
- Uninstall Python and reinstall, making sure to check that box

**The Command Prompt closes and the app disappears** (from-source only)
- An error occurred — re-open Command Prompt, navigate to the PermaDesign
  folder, run `python main.py` again, and read the error message shown

**"No results" in Permapeople search**
- Double-check your Key ID and Key Secret in Settings
- Make sure you have an internet connection

---

## Where files are stored

- **Designs** save wherever you choose with **File → Save**.
- **Plant database** lives at `%APPDATA%\PermaDesign\permadesign.db` — you
  rarely need to touch it. Deleting it forces a fresh seed on next launch.
- **Settings (API keys, preferences)** live alongside the database.
