"""
scripts/packaging/make_app_icon.py — the app's icon, made from a photograph
(F232, V3.17).

Until V3.17 the build set no icon (``permadesign.spec``: ``icon=None``), so
PyInstaller put its own on the program: a yellow snake on a floppy disk. A
great deal of malware ships with exactly that icon, which is how the owner read
it on their desktop. The icon is now a native flower of the Edmonton region,
from a photograph of the owner's choosing.

Writes, into ``assets/icon/``:

* ``app_<size>.png`` — the same picture at every size Windows asks for. The
  window icon (``src/app_icon.py``): title bar, taskbar, Alt-Tab, on any
  platform and on a source checkout, which has no .exe to carry an icon.
* ``site_and_pattern.ico`` — the program's icon on Windows: the desktop
  shortcut, the Start menu, the taskbar, Settings -> Apps, and the installer's
  own (``installer.nsi``).
* ``site_and_pattern.icns`` — the app's icon on a Mac (the spec's BUNDLE).

**Two crops, not one.** At 32 px and below only the bloom survives, so the small
sizes use a tighter crop of the same photograph (``TIGHT``) than the large ones
(``WIDE``). Each is a square in source pixels: centre x, centre y, side.

The photograph is committed beside the icons (``SOURCE``) so the icon can be
made again; ``tests/test_app_icon.py`` checks it carries no EXIF, since a phone
photo can hold the coordinates of where it was taken (the rule
``src/photo_import.py`` applies to imported photos).

Run from the repo root (Pillow needed, a build-time tool only):

    python scripts/packaging/make_app_icon.py
"""

from __future__ import annotations

import os
import struct
import sys
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "assets", "icon")

SOURCE = "source_prairie_crocus.jpg"
WIDE = (454, 292, 500)          # 48 px and up: the whole bloom, a little ground
TIGHT = (454, 290, 440)         # 32 px and down: the bloom alone

# The sizes Windows draws an icon at, 100% to 200% display scaling.
WINDOWS_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
SMALL = 32

# A Mac icon keeps a margin round its tile (Apple's grid: an 824 tile on a
# 1024 canvas). The largest entry stops at 512: the photograph is not much
# larger than that, and macOS scales up for anything bigger.
MAC_PAD = 100 / 1024
MAC_ENTRIES = (                 # (type, size): Apple's PNG-bearing icns types
    (b"icp4", 16), (b"icp5", 32), (b"ic11", 32), (b"ic12", 64), (b"ic07", 128),
    (b"ic13", 256), (b"ic08", 256), (b"ic14", 512), (b"ic09", 512),
)


def crop(src: Image.Image, box) -> Image.Image:
    cx, cy, side = box
    half = side / 2
    return src.crop((round(cx - half), round(cy - half),
                     round(cx + half), round(cy + half)))


def tile(art: Image.Image, size: int, pad: float = 0.0,
         radius: float = 0.2) -> Image.Image:
    """The square artwork as a rounded tile on a transparent canvas, with a
    hairline just inside its edge so a pale tile still has an edge on a pale
    desktop."""
    inner = max(1, round(size * (1 - 2 * pad)))
    scale = 4                   # mask drawn large then reduced: smooth corners
    big = inner * scale
    im = art.resize((big, big), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, big - 1, big - 1), radius=round(big * radius), fill=255)
    im.putalpha(mask)
    edge = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle(
        (0, 0, big - 1, big - 1), radius=round(big * radius),
        outline=(20, 40, 20, 110), width=max(scale, round(big / 64)))
    im = Image.alpha_composite(im, edge).resize((inner, inner), Image.LANCZOS)
    if inner <= 48:             # small frames lose their edges to resampling
        im = im.filter(ImageFilter.UnsharpMask(radius=0.6, percent=60, threshold=1))
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(im, ((size - inner) // 2, (size - inner) // 2))
    return out


def _png(im: Image.Image) -> bytes:
    buf = BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _dib(im: Image.Image) -> bytes:
    """One icon frame as a 32-bit bitmap: a BITMAPINFOHEADER whose height
    counts the image and its mask, the BGRA rows bottom-up, then the 1-bit AND
    mask (set where the pixel is fully transparent), each row padded to 4 bytes.
    Pillow's own ICO writer leaves the mask out, though the header says it is
    there."""
    w, h = im.size
    px = im.convert("RGBA").tobytes()
    rows = [px[y * w * 4:(y + 1) * w * 4] for y in range(h)]
    xor = b"".join(bytes(b for i in range(0, len(r), 4)
                         for b in (r[i + 2], r[i + 1], r[i], r[i + 3]))
                   for r in reversed(rows))
    stride = ((w + 31) // 32) * 4
    mask = bytearray()
    for r in reversed(rows):
        line = bytearray(stride)
        for x in range(w):
            if r[x * 4 + 3] == 0:
                line[x // 8] |= 0x80 >> (x % 8)
        mask += line
    header = struct.pack("<IiiHHIIiiII", 40, w, 2 * h, 1, 32, 0,
                         len(xor) + len(mask), 0, 0, 0, 0)
    return header + xor + bytes(mask)


def write_ico(path: str, frames: dict) -> None:
    """Bitmaps up to 128 px and PNG at 256, as Windows' own icons and
    PyInstaller's default are made: a PNG small frame is read since Vista, but
    not by every tool that touches an .exe's icon."""
    sizes = sorted(frames)
    blobs = [_png(frames[s]) if s >= 256 else _dib(frames[s]) for s in sizes]
    head = struct.pack("<HHH", 0, 1, len(sizes))
    offset = len(head) + 16 * len(sizes)
    for s, blob in zip(sizes, blobs):
        dim = 0 if s >= 256 else s          # 0 means 256 in an icon directory
        head += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    with open(path, "wb") as fh:
        fh.write(head + b"".join(blobs))


def write_icns(path: str, frames: dict) -> None:
    """An icns of PNG entries, written by hand so it holds only what is listed
    (Pillow's writer always adds a 1024 entry, here an upscale)."""
    body = b"".join(t + struct.pack(">I", 8 + len(d)) + d
                    for t, d in ((t, _png(frames[s])) for t, s in MAC_ENTRIES))
    with open(path, "wb") as fh:
        fh.write(b"icns" + struct.pack(">I", 8 + len(body)) + body)


def main() -> int:
    src = Image.open(os.path.join(OUT, SOURCE)).convert("RGB")
    wide, tight = crop(src, WIDE), crop(src, TIGHT)
    art = lambda s: tight if s <= SMALL else wide  # noqa: E731

    win = {s: tile(art(s), s) for s in WINDOWS_SIZES}
    for s, im in win.items():
        im.save(os.path.join(OUT, f"app_{s}.png"), optimize=True)
    write_ico(os.path.join(OUT, "site_and_pattern.ico"), win)

    mac = {s: tile(art(s), s, pad=MAC_PAD, radius=0.225)
           for s in sorted({s for _, s in MAC_ENTRIES})}
    write_icns(os.path.join(OUT, "site_and_pattern.icns"), mac)
    print(f"wrote {len(win)} PNGs, site_and_pattern.ico and site_and_pattern.icns "
          f"to {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
