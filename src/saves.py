"""
saves.py — where a design lives, and how to recognise it in a list (F87, V2.39).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md (a native planting has to
be loved to survive: the ceremony around the work is part of whether the work
gets done).

User feedback: *"Saving a file should be more simple and similar to how game
files are saved and loaded. There should be a folder that they automatically
save to. When loading a previously saved file they should be listed in the app
rather than opening the computer's file explorer."*

Until now a design went wherever the OS file dialog happened to be pointing,
and finding it again meant remembering. A game does not ask you where to put a
save; it has a place, and it shows you what is in it. That is the whole feature.

This module is the Qt-free half: the folder, the filename, and the one-line
description that tells one yard apart from another. The browser dialog is in
``src/saves_dialog.py`` and the wiring in ``src/controllers/persistence.py``.

**No thumbnails.** Rendering one needs the map widget, a live QWebEngineView
and a screenshot round-trip per save — a great deal of machinery for a picture,
and the wrong first move. The counts below are what actually distinguishes two
designs of the same yard; if they turn out not to be enough, a thumbnail is the
follow-on rather than a promise made up front.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

SAVE_SUFFIX = ".perma.geojson"
SAVES_DIRNAME = "saves"

# Windows forbids these outright; the rest are merely a bad idea in a filename.
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_STEM = 80


def saves_dir() -> str:
    """``<user data dir>/saves`` — the folder designs go to when nobody says.

    Beside the database, under the same platform paths ``src/user_paths`` is
    already the single source of truth for. One more directory under an
    existing concept, not a new one.
    """
    from src.user_paths import user_data_dir
    return os.path.join(user_data_dir(), SAVES_DIRNAME)


def ensure_saves_dir() -> str:
    """:func:`saves_dir`, created if missing. Returns the path."""
    path = saves_dir()
    os.makedirs(path, exist_ok=True)
    return path


def slugify(name: str) -> str:
    """A project name turned into a filename stem that survives every OS.

    Kept readable rather than encoded — the point of a saves folder is that a
    person can open it and see their designs, so ``Back Yard Meadow`` becomes
    ``Back Yard Meadow`` and not ``back-yard-meadow`` or a hash.
    """
    stem = _UNSAFE.sub(" ", (name or "").strip())
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    # Reserved device names on Windows are refused as whole stems.
    if stem.upper() in {"CON", "PRN", "AUX", "NUL"} or re.fullmatch(
            r"(?i)(COM|LPT)[1-9]", stem or ""):
        stem = f"{stem}_"
    return (stem or "Untitled Design")[:_MAX_STEM].strip() or "Untitled Design"


def unique_save_path(name: str, directory: Optional[str] = None) -> str:
    """A path in the saves folder that does not already exist.

    Collides by *adding a number*, never by overwriting: two designs both
    called "Untitled Design" are two designs, and silently replacing the first
    with the second is the single worst thing a save button can do.
    """
    directory = directory or saves_dir()
    stem = slugify(name)
    candidate = os.path.join(directory, stem + SAVE_SUFFIX)
    if not os.path.exists(candidate):
        return candidate
    for n in range(2, 1000):
        candidate = os.path.join(directory, f"{stem} {n}{SAVE_SUFFIX}")
        if not os.path.exists(candidate):
            return candidate
    # Vanishingly unlikely; a timestamp is still better than clobbering.
    return os.path.join(directory, f"{stem} {int(time.time())}{SAVE_SUFFIX}")


def is_save_file(path: str) -> bool:
    return path.endswith(SAVE_SUFFIX) or path.endswith(".geojson")


# ── Describing a save without opening it ────────────────────────────────────

_cache: dict[str, tuple[tuple[float, int], dict]] = {}


def describe(path: str) -> dict:
    """What this save is, enough to recognise it in a list.

    ``{path, filename, name, modified, plants, species, site, error}``.

    Reading the file is the only honest way — nothing else knows how many
    plants a design holds. Cached on ``(mtime, size)`` so reopening the browser
    costs nothing, and invalidated for free when the file changes.

    An unreadable save is **described as unreadable, not omitted**: a file
    disappearing from the list is how a user concludes their work is gone.
    """
    try:
        stat = os.stat(path)
        key = (stat.st_mtime, stat.st_size)
    except OSError as exc:
        return _broken(path, str(exc))

    hit = _cache.get(path)
    if hit is not None and hit[0] == key:
        return hit[1]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("not a project file")
    except (OSError, ValueError) as exc:
        return _broken(path, str(exc), stat.st_mtime)

    props = data.get("properties") or {}
    features = data.get("features") or []
    plants = [f for f in features
              if ((f.get("properties") or {}).get("element_type") == "plant")]
    species = {(f.get("properties") or {}).get("common_name")
               for f in plants} - {None, ""}
    sc = props.get("site_config") or {}

    out = {
        "path": path,
        "filename": os.path.basename(path),
        "name": props.get("project_name") or os.path.basename(path),
        "modified": stat.st_mtime,
        "plants": len(plants),
        "species": len(species),
        "site": sc.get("pin_label") or "",
        "error": "",
    }
    _cache[path] = (key, out)
    return out


def _broken(path: str, why: str, modified: float = 0.0) -> dict:
    return {"path": path, "filename": os.path.basename(path),
            "name": os.path.basename(path), "modified": modified,
            "plants": 0, "species": 0, "site": "", "error": why}


def list_saves(directory: Optional[str] = None) -> list[dict]:
    """Every save in the folder, newest first. Never raises."""
    directory = directory or saves_dir()
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    out = [describe(os.path.join(directory, n))
           for n in names if is_save_file(n)]
    out.sort(key=lambda d: d["modified"], reverse=True)
    return out


def clear_cache() -> None:
    """Drop the description cache (tests, and after a delete)."""
    _cache.clear()


def summary_line(entry: dict) -> str:
    """The second line under a save's name, in a person's words.

    Says nothing it does not know: a design with no plants yet says so rather
    than showing "0 species", and an unreadable file says what went wrong
    instead of pretending to be empty.
    """
    if entry.get("error"):
        return f"Could not be read — {entry['error']}"
    bits = []
    plants, species = entry.get("plants", 0), entry.get("species", 0)
    if plants:
        bits.append(f"{plants} plant{'s' if plants != 1 else ''}")
        if species:
            bits.append(f"{species} species")
    else:
        bits.append("no plants yet")
    if entry.get("site"):
        bits.append(entry["site"])
    return " · ".join(bits)


def when(entry: dict, now: Optional[float] = None) -> str:
    """"Just now" / "2 hours ago" / a date. Recency is what you scan a save
    list for; an ISO timestamp makes you do the arithmetic yourself."""
    stamp = entry.get("modified") or 0
    if not stamp:
        return ""
    delta = max(0.0, (now if now is not None else time.time()) - stamp)
    if delta < 90:
        return "just now"
    if delta < 3600:
        n = int(delta // 60)
        return f"{n} minute{'s' if n != 1 else ''} ago"
    if delta < 86400:
        n = int(delta // 3600)
        return f"{n} hour{'s' if n != 1 else ''} ago"
    if delta < 7 * 86400:
        n = int(delta // 86400)
        return f"{n} day{'s' if n != 1 else ''} ago"
    return time.strftime("%d %b %Y", time.localtime(stamp))
