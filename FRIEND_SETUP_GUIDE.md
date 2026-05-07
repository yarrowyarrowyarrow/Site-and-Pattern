# PermaDesign — Setup Guide for Windows

This guide walks you through getting PermaDesign running on a Windows laptop
from scratch. No coding experience needed — just follow each step in order.

---

## Part 1 — Install the Required Programs (one-time only)

### Step 1: Install Python

1. Go to **python.org/downloads**
2. Click the big yellow "Download Python 3.x.x" button
3. Run the installer
4. **Important:** On the first screen, check the box that says
   **"Add Python to PATH"** before clicking Install
5. Click "Install Now" and wait for it to finish

To confirm it worked: open the Start menu, search for **Command Prompt**,
open it, and type:
```
python --version
```
You should see something like `Python 3.11.x`. If so, you're good.

---

### Step 2: Install Git

1. Go to **git-scm.com/download/win**
2. The download should start automatically — run the installer
3. Click Next through all the screens (defaults are fine)
4. Click Finish when done

---

## Part 2 — Download the App (one-time only)

1. Open **Command Prompt** (Start menu → search "cmd")
2. Navigate to your Desktop:
   ```
   cd %USERPROFILE%\Desktop
   ```
3. Download the app:
   ```
   git clone https://github.com/yarrowyarrowyarrow/PermaDesign.git
   ```
4. Move into the folder:
   ```
   cd PermaDesign
   ```
5. Switch to the correct version:
   ```
   git checkout claude/build-step-1-v1-hTpZB
   ```
6. Install the app's dependencies:
   ```
   pip install -r requirements.txt
   ```
   This may take a minute or two — that's normal.

---

## Part 3 — Run the App

Every time you want to use PermaDesign:

1. Open **File Explorer** and navigate to your **Desktop → PermaDesign** folder
2. Click the address bar at the top of File Explorer
3. Type `cmd` and press Enter (this opens a Command Prompt in the right folder)
4. Type:
   ```
   python main.py
   ```
5. The app will open — the Command Prompt window needs to stay open while you use it

---

## Part 4 — Connect the Permapeople Plant Database (optional but recommended)

Permapeople gives you access to 8,500+ permaculture plant profiles to search
and import directly into your designs.

### Get your free API key

1. Go to **permapeople.org** and create a free account
2. Once logged in, go to your account settings and look for **API** or **API Access**
3. Generate a key — you will receive two values:
   - A **Key ID** (looks like a username or code)
   - A **Key Secret** (looks like a long password)
4. Copy both — you will need them in the next step

### Enter the key in the app

1. Open PermaDesign (follow Part 3 above)
2. Click **⚙ Settings** in the toolbar at the top
3. Paste your Key ID and Key Secret into the two fields
4. Click Save

### Use it

1. In the Plant Browser panel on the right, click the **Permapeople** tab
2. Type any plant name in the search box and press Enter
3. Click a result to preview it
4. Click **Import to Local Database** to save it — it then appears in your
   Local tab and can be placed on the map

---

## Troubleshooting

**"python is not recognized"**
- You forgot to check "Add Python to PATH" during install
- Uninstall Python and reinstall, making sure to check that box

**The app opens but the map is black**
- Wait 5–10 seconds for the map tiles to load
- Make sure you have an internet connection

**The Command Prompt closes and the app disappears**
- An error occurred — re-open Command Prompt, navigate to the PermaDesign
  folder, run `python main.py` again, and read the error message shown

**"No results" in Permapeople search**
- Double-check your Key ID and Key Secret in Settings
- Make sure you have an internet connection

---

## Everyday Use at a Glance

| What you want to do | How |
|---|---|
| Start the app | Open cmd in PermaDesign folder → `python main.py` |
| Draw your property boundary | Toolbar → Boundary → click points on map → double-click to close |
| Place permaculture zones | Toolbar → Zone Circles → click centre point |
| Find a plant | Search in Plant Browser (right panel) |
| Place a plant | Select it → click Place on Map → click on the map |
| Remove a plant | Right-click the plant circle on the map |
| Save your design | File → Save (Ctrl+S) |
| Search 8,500+ plants | Permapeople tab in Plant Browser |
