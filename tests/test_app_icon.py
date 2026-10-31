"""
tests/test_app_icon.py

The app's icon (F232, V3.17). Until V3.17 the build set none
(``permadesign.spec``: ``icon=None``), so PyInstaller put its own on the
program: a snake on a floppy disk, which the owner read, rightly, as the look
of malware. These check that the files the build, the installer and the windows
read are there, hold what Windows and macOS ask for, and are the ones each of
them names.

The files are read with the standard library, so nothing here skips for want of
Pillow; only the last class, which asks Qt to draw the window icon, needs PyQt6.
"""

import os
import re
import struct
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src import app_icon  # noqa: E402

_ICON = _ROOT / "assets" / "icon"
_ICO = _ICON / "site_and_pattern.ico"
_ICNS = _ICON / "site_and_pattern.icns"
_PNG = b"\x89PNG\r\n\x1a\n"


def _png_size(data: bytes) -> tuple:
    return struct.unpack(">II", data[16:24])


def _ico_frames(raw: bytes) -> list:
    reserved, kind, count = struct.unpack("<HHH", raw[:6])
    assert (reserved, kind) == (0, 1), "not an icon file"
    frames = []
    for i in range(count):
        w, h, colours, _, planes, bpp, size, off = struct.unpack(
            "<BBBBHHII", raw[6 + 16 * i:22 + 16 * i])
        frames.append((w or 256, h or 256, bpp, raw[off:off + size]))
    return frames


def _icns_entries(raw: bytes) -> list:
    assert raw[:4] == b"icns", "not an icns file"
    assert struct.unpack(">I", raw[4:8])[0] == len(raw), "icns length is wrong"
    entries, i = [], 8
    while i < len(raw):
        kind, length = raw[i:i + 4], struct.unpack(">I", raw[i + 4:i + 8])[0]
        entries.append((kind.decode("ascii"), raw[i + 8:i + length]))
        i += length
    assert i == len(raw), "icns entries overrun the file"
    return entries


class TheIconFiles(unittest.TestCase):

    def test_the_window_icon_is_there_at_every_size(self):
        for s in app_icon.SIZES:
            data = Path(app_icon.path(s)).read_bytes()
            self.assertEqual(data[:8], _PNG, s)
            self.assertEqual(_png_size(data), (s, s), s)
            self.assertEqual(data[25], 6, f"{s} px is not RGBA: the corners "
                             "of the tile must be transparent")

    def test_the_windows_icon_holds_every_size_as_windows_own_do(self):
        """Bitmaps up to 128 px, PNG at 256, as PyInstaller's own icon is
        made; each bitmap with the 1-bit mask its header promises, which
        Pillow's writer leaves out."""
        frames = _ico_frames(_ICO.read_bytes())
        self.assertEqual(sorted(w for w, *_ in frames), sorted(app_icon.SIZES))
        for w, h, bpp, data in frames:
            self.assertEqual((h, bpp), (w, 32), w)
            if w >= 256:
                self.assertEqual(data[:8], _PNG)
                self.assertEqual(_png_size(data), (256, 256))
                continue
            size, dw, dh, planes, bits, compression = struct.unpack(
                "<IiiHHI", data[:20])
            self.assertEqual((size, dw, dh, planes, bits, compression),
                             (40, w, 2 * w, 1, 32, 0), w)
            mask = ((w + 31) // 32) * 4 * w
            self.assertEqual(len(data), 40 + w * w * 4 + mask, w)

    def test_the_mac_icon_holds_the_sizes_a_mac_asks_for(self):
        entries = dict(_icns_entries(_ICNS.read_bytes()))
        expected = {"icp4": 16, "icp5": 32, "ic11": 32, "ic12": 64,
                    "ic07": 128, "ic13": 256, "ic08": 256, "ic14": 512,
                    "ic09": 512}
        self.assertEqual(set(entries), set(expected))
        for kind, size in expected.items():
            self.assertEqual(entries[kind][:8], _PNG, kind)
            self.assertEqual(_png_size(entries[kind]), (size, size), kind)

    def test_the_photograph_carries_no_metadata(self):
        """A phone photo can hold the coordinates of where it was taken, and
        this one is committed and shipped (the rule src/photo_import.py
        applies to imported photos)."""
        for photo in _ICON.glob("source_*"):
            data = photo.read_bytes()
            self.assertNotIn(b"Exif\x00\x00", data, photo.name)
            self.assertNotIn(b"http://ns.adobe.com/xap/1.0/", data, photo.name)


class WhereTheIconIsUsed(unittest.TestCase):

    def test_the_build_puts_it_on_the_program_and_the_mac_app(self):
        spec = (_ROOT / "scripts" / "packaging" / "permadesign.spec").read_text(
            encoding="utf-8")
        self.assertNotIn("icon=None", spec)
        named = dict(re.findall(
            r"^(_ICON_\w+) = os\.path\.join\(_ROOT, 'assets', 'icon', '([^']+)'\)",
            spec, re.M))
        self.assertEqual(named, {"_ICON_WINDOWS": _ICO.name, "_ICON_MAC": _ICNS.name})
        self.assertIn("icon=_ICON_WINDOWS", spec)
        self.assertIn("icon=_ICON_MAC", spec)
        self.assertIn("(os.path.join(_ROOT, 'assets', 'icon', 'app_*.png'), "
                      "'assets/icon')", spec,
                      "the window icon must be bundled where app_icon looks")

    def test_the_installer_wears_it_and_refreshes_the_shell(self):
        packaging = _ROOT / "scripts" / "packaging"
        nsi = (packaging / "installer.nsi").read_text(encoding="utf-8")
        for name in ("MUI_ICON", "MUI_UNICON"):
            m = re.search(rf'^!define {name} "([^"]+)"', nsi, re.M)
            self.assertIsNotNone(m, name)
            # NSIS reads paths from the script's own folder.
            target = (packaging / m.group(1).replace("\\", os.sep)).resolve()
            self.assertEqual(target, _ICO.resolve(), name)
        install = nsi.split('Section "Site & Pattern"', 1)[1].split("SectionEnd", 1)[0]
        self.assertIn("SHChangeNotify(i 0x08000000", install,
                      "without it a replaced program can keep its old icon "
                      "on the desktop until the next sign-in")

    def test_every_window_wears_it(self):
        main = (_ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("app_icon.install(app)", main)


def _qt():
    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401  (before any QApplication)
    except Exception:
        pass
    try:
        from PyQt6.QtWidgets import QApplication
        return QApplication
    except Exception:
        return None


@unittest.skipUnless(_qt(), "PyQt6 not installed in this env")
class TheWindowIcon(unittest.TestCase):

    def test_qt_draws_every_size(self):
        QApplication = _qt()
        self._app = QApplication.instance() or QApplication(["sp-app-icon"])
        ic = app_icon.icon()
        self.assertFalse(ic.isNull())
        sizes = sorted(s.width() for s in ic.availableSizes())
        self.assertEqual(sizes, sorted(app_icon.SIZES))
        for s in (16, 32, 256):
            pm = ic.pixmap(s, s)
            self.assertEqual((pm.width(), pm.height()), (s, s), s)


if __name__ == "__main__":
    unittest.main()
