# PermaDesign — Uninstall & Reinstall Guide

If the app won't launch or is behaving unexpectedly, a clean reinstall usually fixes it.

---

## Step 1: Delete Everything App-Related

Inside your PermaDesign project folder, delete these items:

| Item | What it is |
|------|-----------|
| `venv\` | Python virtual environment + all installed packages |
| `plants.db` | The plant database (auto-recreated on next run) |
| `*.perma.geojson` | Any saved design files you don't want to keep |
| `__pycache__\` | Python bytecode cache (in root and inside `src\`) |
| `src\__pycache__\` | Same as above, inside src |
| `src\db\__pycache__\` | Same, inside db |

To delete them all at once, open Command Prompt in the project folder and run:

```bat
rmdir /s /q venv
rmdir /s /q __pycache__
rmdir /s /q src\__pycache__
rmdir /s /q src\db\__pycache__
del /q plants.db
```

> **Keep your `.perma.geojson` design files** if you want to reload your work after reinstalling.

---

## Step 2: Verify Python Is Installed

Open Command Prompt and run:

```bat
python --version
```

You should see `Python 3.11.x` or higher. If not, download Python from [python.org](https://www.python.org/downloads/) and re-run the installer, making sure to check **"Add Python to PATH"**.

---

## Step 3: Recreate the Virtual Environment

In Command Prompt, navigate to the project folder and run:

```bat
python -m venv venv
venv\Scripts\activate
```

Your prompt should now show `(venv)` at the start.

---

## Step 4: Install Dependencies

With the virtual environment active:

```bat
pip install PyQt6 PyQt6-WebEngine
```

This downloads and installs all required packages fresh.

---

## Step 5: Initialize the Plant Database

```bat
python -m src.db.seed_data
```

This creates a new `plants.db` file and populates it with the full plant list.

---

## Step 6: Launch the App

```bat
python main.py
```

The app should open, showing a map centered on Edmonton.

---

## Still Not Working?

Try these in order:

1. **Check for error output** — run `python main.py` from Command Prompt (not by double-clicking) so you can see any error messages.

2. **WebEngine DLL error** — if you see an error about WebEngine or Qt, try:
   ```bat
   pip install --upgrade PyQt6 PyQt6-WebEngine
   ```

3. **"Module not found" error** — make sure your virtual environment is activated (`venv\Scripts\activate`) before running.

4. **Antivirus blocking** — some antivirus software blocks Qt WebEngine processes. Try temporarily disabling it to test.

5. **Full nuclear option** — delete the entire project folder and re-clone from GitHub:
   ```bat
   git clone https://github.com/yarrowyarrowyarrow/permadesign.git
   cd permadesign
   python -m venv venv
   venv\Scripts\activate
   pip install PyQt6 PyQt6-WebEngine
   python -m src.db.seed_data
   python main.py
   ```
