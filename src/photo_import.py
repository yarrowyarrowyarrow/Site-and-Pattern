"""
src/photo_import.py — bring a photograph into the library, safely (V2.35, F72).

Design principle P11 (the body and the site know things the screen does not) —
see docs/DESIGN_PHILOSOPHY.md. The whole point of a user's own photograph is
that they were standing in front of the plant.

Qt-free, stdlib-only for everything that matters. Two jobs:

1. **Strip the metadata.** This is not housekeeping. A photograph of your own
   yard carries your home's GPS coordinates in its EXIF, and the natural next
   step for a photo you are proud of is to commit it to a public repository.
   Nobody would choose to publish their address; they would simply not know they
   had. So metadata removal is unconditional, happens before anything else, and
   is implemented in the standard library so it cannot be skipped by an optional
   dependency being absent.

2. **Make it a sensible size.** A phone photo is 4–12 MB and 4000 px wide; the
   app shows it at a few hundred pixels. Downscaling needs Pillow, which this
   project does NOT depend on (see the note in requirements.txt about optional
   native deps and the frozen builds). Without it the file is copied at full
   size — stripped, but large — and the caller is told so, because a silent
   50 MB of photos in the repo is a worse surprise than a warning.

Nothing here touches the database. :mod:`src.db.photos` records the row;
this module only produces the file.
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
from typing import Optional

# Long edge, pixels. Big enough to fill the tuning bench's reference pane and a
# PDF page image; small enough that a hundred photos is ~15 MB rather than ~1 GB.
MAX_EDGE = 1600
JPEG_QUALITY = 85

# JPEG application markers that carry metadata. APP1 is EXIF (and XMP), APP13 is
# Photoshop/IPTC; APP2 can hold ICC profiles, which we KEEP because dropping the
# colour profile visibly shifts colour, and a plant's colour is the point.
_JPEG_STRIP_MARKERS = {0xE1, 0xED, 0xEE}          # APP1, APP13, APP14
# PNG ancillary chunks that carry metadata (lowercase first letter = ancillary).
_PNG_STRIP_CHUNKS = {b"eXIf", b"tEXt", b"iTXt", b"zTXt"}

_SAFE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """`Rudbeckia hirta` → `rudbeckia_hirta`. Filenames are keyed by scientific
    name for the same reason the table is (ids are not stable across a reseed)."""
    return _SAFE.sub("_", (name or "").strip().lower()).strip("_") or "unknown"


# ── metadata stripping (stdlib, always runs) ─────────────────────────────────

def strip_metadata(blob: bytes) -> bytes:
    """Return ``blob`` with EXIF/XMP/IPTC removed. Unknown formats pass through.

    Byte surgery on the container rather than a decode/re-encode round trip, so
    it works with no third-party library and does not touch a single pixel.
    """
    if blob[:2] == b"\xff\xd8":
        return _strip_jpeg(blob)
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        return _strip_png(blob)
    return blob


def _strip_jpeg(blob: bytes) -> bytes:
    out = bytearray(blob[:2])                       # SOI
    i = 2
    n = len(blob)
    while i + 4 <= n:
        if blob[i] != 0xFF:
            break                                   # not a marker — bail, keep the rest
        marker = blob[i + 1]
        if marker == 0xD8 or 0xD0 <= marker <= 0xD7:
            out += blob[i:i + 2]
            i += 2
            continue
        if marker == 0xDA:                          # start of scan: image data to EOI
            out += blob[i:]
            return bytes(out)
        seg_len = int.from_bytes(blob[i + 2:i + 4], "big")
        if seg_len < 2:
            break
        if marker not in _JPEG_STRIP_MARKERS:
            out += blob[i:i + 2 + seg_len]
        i += 2 + seg_len
    else:
        return bytes(out)
    return bytes(out) + blob[i:]


def _strip_png(blob: bytes) -> bytes:
    out = bytearray(blob[:8])
    i = 8
    n = len(blob)
    while i + 8 <= n:
        length = int.from_bytes(blob[i:i + 4], "big")
        ctype = blob[i + 4:i + 8]
        end = i + 12 + length                       # len + type + data + crc
        if end > n:
            break
        if ctype not in _PNG_STRIP_CHUNKS:
            out += blob[i:end]
        i = end
        if ctype == b"IEND":
            break
    return bytes(out)


def has_metadata(blob: bytes) -> bool:
    """Whether the blob still carries any of the markers we strip. Used by the
    tests — a check that the stripper is doing something is worth more than a
    check that it ran."""
    return strip_metadata(blob) != blob


# ── resizing (needs Pillow; degrades honestly) ───────────────────────────────

def _pillow():
    try:
        from PIL import Image                        # noqa: PLC0415
        return Image
    except ImportError:
        return None


def resize_blob(blob: bytes, max_edge: int = MAX_EDGE) -> tuple[bytes, str]:
    """Downscale to ``max_edge`` on the long side and re-encode as JPEG.

    Returns ``(blob, note)``. ``note`` is empty on success and explains itself
    when the image came through unchanged, which the caller is expected to show
    rather than swallow.
    """
    Image = _pillow()
    if Image is None:
        return blob, ("Pillow is not installed, so the photo was stored at full "
                      "size (metadata was still removed). `pip install Pillow` "
                      "to downscale.")
    import io                                        # noqa: PLC0415
    try:
        im = Image.open(io.BytesIO(blob))
        im = im.convert("RGB")
        if max(im.size) > max_edge:
            scale = max_edge / float(max(im.size))
            im = im.resize((max(1, round(im.width * scale)),
                            max(1, round(im.height * scale))),
                           Image.LANCZOS)
        buf = io.BytesIO()
        # Pillow writes no EXIF unless asked, so the re-encode is a second,
        # independent guarantee that nothing came along for the ride.
        im.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
        return buf.getvalue(), ""
    except Exception as exc:                         # noqa: BLE001
        return blob, f"could not re-encode ({exc}); stored as-is"


# ── the one entry point ──────────────────────────────────────────────────────

def import_photo(src_path: str, scientific_name: str, slot: str,
                 dest_dir: str, *, max_edge: int = MAX_EDGE) -> dict:
    """Copy one photograph into ``dest_dir``, stripped and downscaled.

    Returns ``{"path", "filename", "bytes", "note", "stripped"}``; raises
    ``FileNotFoundError`` / ``ValueError`` for an unusable source.

    ``dest_dir`` is the caller's choice and is the whole difference between the
    two destinations F72 needs: ``data/photos`` for a photograph that ships with
    the app, or the user-data dir (``src.user_paths``) for one that stays on
    this machine.
    """
    src = pathlib.Path(src_path)
    if not src.is_file():
        raise FileNotFoundError(src_path)
    blob = src.read_bytes()
    if len(blob) < 64:
        raise ValueError(f"{src.name}: not an image (too small)")
    if blob[:2] != b"\xff\xd8" and blob[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{src.name}: only JPEG and PNG are accepted")

    stripped = strip_metadata(blob)
    was_stripped = stripped != blob
    out, note = resize_blob(stripped, max_edge)

    dest = pathlib.Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    stem = f"{slugify(scientific_name)}-{slugify(slot)}"
    ext = ".jpg" if out[:2] == b"\xff\xd8" else src.suffix.lower() or ".jpg"
    i = 1
    while (dest / f"{stem}-{i}{ext}").exists():
        i += 1
    path = dest / f"{stem}-{i}{ext}"
    path.write_bytes(out)
    return {"path": str(path), "filename": path.name, "bytes": len(out),
            "note": note, "stripped": was_stripped}


def shipped_photo_dir() -> str:
    """`data/photos` — photographs that travel with the app."""
    root = pathlib.Path(__file__).resolve().parent.parent
    return str(root / "data" / "photos")


def user_photo_dir() -> str:
    """The per-user photo folder, beside the database. Never committed, never
    wiped by a reseed."""
    from src.user_paths import data_dir_path           # noqa: PLC0415
    return str(pathlib.Path(data_dir_path()) / "photos")


def copy_unstripped_is_never_ok() -> None:             # documentation, not code
    """There is deliberately no flag to skip :func:`strip_metadata`.

    Every path into the library goes through :func:`import_photo`, and the only
    reason someone would want the original bytes is to preserve metadata — which
    is exactly the thing that must not happen by accident. If a caller genuinely
    needs the original, they can copy the file themselves and know they did.
    """
