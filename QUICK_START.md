# Site & Pattern: Quick Start Guide

## ⚡ Fastest Way to Run

```bash
cd /home/user/Site & Pattern
python3 -m venv venv
source venv/bin/activate              # macOS/Linux
# venv\Scripts\activate.bat            # Windows

pip install -r requirements.txt
python3 main.py
```

Done! The app opens immediately.

---

## 📦 Build a 1-Click Installer

### Windows
```cmd
cd C:\path\to\Site & Pattern
build_installer.bat
```
**Output:** `SiteAndPattern-Installer.exe` (or ZIP if NSIS not installed)

### macOS
```bash
cd /path/to/Site & Pattern
bash build_installer.sh
```
**Output:** `dist/SiteAndPattern.dmg` — drag to Applications

### Linux
```bash
cd /path/to/Site & Pattern
bash build_installer.sh
```
**Output:** `SiteAndPattern-Linux.zip` — extract & run binary

---

## 🎯 What's Next After Building?

**For Windows users:**
- Run `SiteAndPattern-Installer.exe` → installs to Program Files with Start Menu shortcut

**For macOS users:**
- Open `SiteAndPattern.dmg` → drag app to Applications folder

**For Linux users:**
- Unzip `SiteAndPattern-Linux.zip`
- Run: `./Site & Pattern/Site & Pattern`

---

## 📋 Full Documentation

See `BUILD.md` for:
- Step-by-step setup
- Platform-specific details
- Troubleshooting
- Advanced customization (custom icons, etc.)

---

## ✅ Verify It Works

Run locally first to test:
```bash
source venv/bin/activate
python3 main.py
```

Create a new project, test plant placement, verify all features work.
Then build the installer when satisfied.

---

## 📊 Typical Build Sizes

| Platform | File Size | Installed Size |
|----------|-----------|---|
| Windows EXE | 200–300 MB | 400–600 MB |
| macOS DMG | 200–300 MB | 400–600 MB |
| Linux ZIP | 200–300 MB | 400–600 MB |

(Large because PyQt6 with WebEngine is heavy. One-time download.)

---

## 🐛 Problems?

**App won't start:**
- Make sure Python 3.9+ is installed: `python3 --version`
- Try from terminal to see error messages
- Check `BUILD.md` troubleshooting section

**Build fails:**
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt` again
- Delete `build/` and `dist/` folders, rebuild

**NSIS installer doesn't work (Windows):**
- Install from https://nsis.sourceforge.io/
- Or just use the ZIP file that the script creates automatically

---

Happy designing! 🌿
