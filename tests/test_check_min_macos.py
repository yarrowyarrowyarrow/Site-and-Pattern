"""
tests/test_check_min_macos.py — the Mac app's binaries are held to the
macOS the app declares (V3.42).

V3.41's DMG declared Big Sur (LSMinimumSystemVersion 11.0) and carried 13
numpy modules that needed macOS 14: pip took numpy's Accelerate wheel for
the macOS 14 build machine. Nothing noticed, because nothing read the
binaries. ``scripts/packaging/check_min_macos.py`` reads them in the build;
these tests build Mach-O files by hand, so they run anywhere.
"""

from __future__ import annotations

import contextlib
import io
import os
import plistlib
import shutil
import struct
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scripts", "packaging"))

import check_min_macos as cmm  # noqa: E402

X86_64, ARM64 = 0x01000007, 0x0100000C


def quietly(argv) -> int:
    """The check's exit code, its printout kept out of the test log."""
    with contextlib.redirect_stdout(io.StringIO()):
        return cmm.main(argv)


def _version(major, minor=0, patch=0):
    return (major << 16) | (minor << 8) | patch


def thin(cpu=X86_64, minimum=(11, 0), old_style=False) -> bytes:
    """A 64-bit Mach-O with one load command naming its minimum macOS."""
    if old_style:       # LC_VERSION_MIN_MACOSX: version, sdk
        cmd = struct.pack("<IIII", cmm.LC_VERSION_MIN_MACOSX, 16,
                          _version(*minimum), _version(*minimum))
    else:               # LC_BUILD_VERSION: platform, minos, sdk, ntools
        cmd = struct.pack("<IIIIII", cmm.LC_BUILD_VERSION, 24, 1,
                          _version(*minimum), _version(*minimum), 0)
    header = b"\xcf\xfa\xed\xfe" + struct.pack(
        "<iiIIIII", cpu, 3, 6, 1, len(cmd), 0, 0)
    return header + cmd


def fat(*slices: bytes) -> bytes:
    """A universal binary holding ``slices``, each at a 4 KiB boundary."""
    head = b"\xca\xfe\xba\xbe" + struct.pack(">I", len(slices))
    offset, table, body = 4096, b"", b""
    for s in slices:
        cpu = struct.unpack_from("<i", s, 4)[0]
        table += struct.pack(">iiIII", cpu, 3, offset, len(s), 12)
        body += s.ljust(4096, b"\0")
        offset += 4096
    return (head + table).ljust(4096, b"\0") + body


class ReadingABinary(unittest.TestCase):

    def test_a_thin_binary_says_its_architecture_and_minimum(self):
        self.assertEqual(cmm.parse_macho(thin(minimum=(14, 0))),
                         [("x86_64", (14, 0, 0))])

    def test_the_older_load_command_is_read_too(self):
        self.assertEqual(cmm.parse_macho(thin(minimum=(10, 9), old_style=True)),
                         [("x86_64", (10, 9, 0))])

    def test_a_universal_binary_gives_each_slice(self):
        both = fat(thin(X86_64, (10, 13)), thin(ARM64, (11, 0)))
        self.assertEqual(cmm.parse_macho(both),
                         [("x86_64", (10, 13, 0)), ("arm64", (11, 0, 0))])

    def test_what_is_not_a_binary_gives_nothing(self):
        self.assertEqual(cmm.parse_macho(b"import numpy\n"), [])
        # A Java class file starts with the universal binary's magic number;
        # its next word is the class version, far above any count of slices.
        self.assertEqual(cmm.parse_macho(b"\xca\xfe\xba\xbe\x00\x00\x00\x34"),
                         [])

    def test_versions_read_and_print_as_people_write_them(self):
        self.assertEqual(cmm.version_tuple("11.0"), (11, 0, 0))
        self.assertEqual(cmm.version_tuple("10.13.6"), (10, 13, 6))
        self.assertEqual(cmm._words((14, 0, 0)), "14.0")
        self.assertEqual(cmm._words((13, 3, 1)), "13.3.1")


class CheckingAnApp(unittest.TestCase):

    def setUp(self):
        self.app = os.path.join(tempfile.mkdtemp(), "SiteAndPattern.app")
        self.addCleanup(shutil.rmtree, os.path.dirname(self.app),
                        ignore_errors=True)
        os.makedirs(os.path.join(self.app, "Contents", "Frameworks"))
        with open(os.path.join(self.app, "Contents", "Info.plist"), "wb") as fh:
            plistlib.dump({"LSMinimumSystemVersion": "11.0"}, fh)
        self.put("MacOS/SiteAndPattern", thin(minimum=(10, 13)))
        self.put("Frameworks/QtCore", fat(thin(X86_64, (11, 0))))
        self.put("Resources/notes.txt", b"not a binary")

    def put(self, rel, data):
        path = os.path.join(self.app, "Contents", rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)

    def test_an_app_whose_binaries_all_fit_passes(self):
        declared, offenders, binaries = cmm.too_new(self.app)
        self.assertEqual((declared, offenders, binaries), ((11, 0, 0), [], 2))
        self.assertEqual(quietly([self.app]), 0)

    def test_a_numpy_module_that_needs_macos_14_fails_the_build(self):
        """V3.41's DMG, in miniature."""
        self.put("Frameworks/numpy/_core/_multiarray_umath.cpython-311-darwin.so",
                 thin(minimum=(14, 0)))
        _declared, offenders, _n = cmm.too_new(self.app)
        self.assertEqual(offenders, [(
            (14, 0, 0), "x86_64",
            os.path.join("Contents", "Frameworks", "numpy", "_core",
                         "_multiarray_umath.cpython-311-darwin.so"))])
        self.assertEqual(quietly([self.app]), 1)

    def test_a_bundle_that_promises_nothing_is_refused(self):
        with open(os.path.join(self.app, "Contents", "Info.plist"), "wb") as fh:
            plistlib.dump({}, fh)
        with self.assertRaises(ValueError):
            cmm.too_new(self.app)


class TheBuildRunsIt(unittest.TestCase):
    """Read as text: the build happens on a Mac this suite never sees."""

    def test_the_build_checks_before_it_makes_the_dmg(self):
        with open(os.path.join(_ROOT, "scripts", "packaging",
                               "build_installer.sh"), encoding="utf-8") as fh:
            script = fh.read()
        check = script.index("check_min_macos.py")
        self.assertLess(script.index("codesign --verify"), check)
        self.assertLess(check, script.index("hdiutil create"))

    def test_the_workflow_fetches_numpy_for_the_declared_macos(self):
        with open(os.path.join(_ROOT, ".github", "workflows",
                               "release-macos.yml"), encoding="utf-8") as fh:
            workflow = fh.read()
        with open(os.path.join(_ROOT, "scripts", "packaging",
                               "permadesign.spec"), encoding="utf-8") as fh:
            spec = fh.read()
        self.assertIn("'LSMinimumSystemVersion': '11.0'", spec)
        self.assertIn("--platform macosx_11_0_x86_64", workflow)
        self.assertLess(workflow.index("bigsur/numpy-"),
                        workflow.index("pip install -r requirements.txt"))


if __name__ == "__main__":
    unittest.main()
