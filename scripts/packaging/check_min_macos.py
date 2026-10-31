"""
check_min_macos.py — nothing inside the Mac app may need a newer macOS than
the app says it runs on (V3.42).

    python3 scripts/packaging/check_min_macos.py dist/SiteAndPattern.app

The bundle declares ``LSMinimumSystemVersion`` 11.0 (Big Sur) in its
Info.plist, and the release notes promise the same. Every binary inside
carries its own minimum macOS (a Mach-O load command, LC_BUILD_VERSION or the
older LC_VERSION_MIN_MACOSX). When the two disagree, the app opens and the
part that needs the newer system fails to load, quietly, on a Mac nobody
building it owns.

That is how V3.41's DMG shipped: all 13 of numpy's compiled modules needed
macOS 14. numpy publishes two Intel Mac wheels, an OpenBLAS one for macOS
10.9 and newer and an Accelerate one for 14 and newer, and pip takes the best
one for the machine it runs on, which has been macOS 14 since the build
moved to GitHub's Apple Silicon runners. Nothing looked wrong: the build
passed, the DMG opened, the build machine ran it.

Exits 1 and names each offender when any binary needs more than the bundle
declares. Standard library only, so it runs in the build's own Python.
"""

from __future__ import annotations

import os
import plistlib
import struct
import sys

LC_VERSION_MIN_MACOSX = 0x24
LC_BUILD_VERSION = 0x32
_THIN = {b"\xcf\xfa\xed\xfe": True, b"\xce\xfa\xed\xfe": False}
_FAT = b"\xca\xfe\xba\xbe"
#: A Java class file starts with the fat magic too; its next word (the
#: class version) is far above any real count of architectures.
_MAX_ARCHS = 30
CPU_NAMES = {7: "i386", 0x01000007: "x86_64", 12: "arm",
             0x0100000C: "arm64"}


def version_tuple(text: str) -> tuple:
    """"11.0" -> (11, 0, 0)."""
    parts = [int(p) for p in str(text).strip().split(".") if p != ""]
    return tuple((parts + [0, 0, 0])[:3])


def _packed(value: int) -> tuple:
    """A Mach-O version, xxxx.yy.zz packed in 32 bits."""
    return (value >> 16, (value >> 8) & 0xFF, value & 0xFF)


def _thin_slice(data: bytes, base: int):
    """``(arch, minimum)`` of the thin Mach-O at ``base``, or ``None``.
    ``minimum`` is ``None`` when the binary declares none."""
    is64 = _THIN.get(data[base:base + 4])
    if is64 is None or len(data) < base + 28:
        return None
    cputype, _sub, _ftype, ncmds, _size, _flags = struct.unpack_from(
        "<iiIIII", data, base + 4)
    pos = base + (32 if is64 else 28)
    minimum = None
    for _ in range(ncmds):
        if pos + 8 > len(data):
            break
        cmd, cmdsize = struct.unpack_from("<II", data, pos)
        if cmd == LC_BUILD_VERSION and pos + 16 <= len(data):
            minimum = _packed(struct.unpack_from("<I", data, pos + 12)[0])
        elif cmd == LC_VERSION_MIN_MACOSX and pos + 12 <= len(data):
            minimum = _packed(struct.unpack_from("<I", data, pos + 8)[0])
        if cmdsize < 8:
            break
        pos += cmdsize
    return CPU_NAMES.get(cputype, hex(cputype)), minimum


def parse_macho(data: bytes) -> list:
    """Each architecture in a Mach-O (thin or fat) as ``(arch, minimum)``;
    ``[]`` for anything that is not one."""
    if data[:4] == _FAT and len(data) >= 8:
        (count,) = struct.unpack_from(">I", data, 4)
        if count > _MAX_ARCHS:
            return []
        out = []
        for i in range(count):
            at = 8 + 20 * i
            if at + 20 > len(data):
                break
            _ct, _st, offset, _size, _align = struct.unpack_from(
                ">iiIII", data, at)
            found = _thin_slice(data, offset)
            if found:
                out.append(found)
        return out
    found = _thin_slice(data, 0)
    return [found] if found else []


def declared_minimum(app: str) -> tuple:
    """The bundle's ``LSMinimumSystemVersion``. Raises when there is none:
    a bundle that promises nothing cannot be held to anything."""
    with open(os.path.join(app, "Contents", "Info.plist"), "rb") as fh:
        info = plistlib.load(fh)
    value = info.get("LSMinimumSystemVersion")
    if not value:
        raise ValueError(f"{app} declares no LSMinimumSystemVersion")
    return version_tuple(value)


def too_new(app: str):
    """``(declared, offenders, binaries)``: the bundle's minimum, each
    ``(minimum, arch, path)`` that needs more, and how many binaries were
    read."""
    declared = declared_minimum(app)
    offenders, binaries = [], 0
    for root, _dirs, files in os.walk(app):
        for name in files:
            path = os.path.join(root, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            with open(path, "rb") as fh:
                if fh.read(4) not in (_FAT, *_THIN):
                    continue
                fh.seek(0)
                slices = parse_macho(fh.read())
            if slices:
                binaries += 1
            for arch, minimum in slices:
                if minimum and minimum > declared:
                    offenders.append((minimum, arch,
                                      os.path.relpath(path, app)))
    return declared, sorted(offenders, reverse=True), binaries


def _words(version: tuple) -> str:
    """(14, 0, 0) -> "14.0"; (13, 3, 1) -> "13.3.1"."""
    shown = version[:2] if version[2:] == (0,) else version
    return ".".join(str(n) for n in shown)


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if len(args) != 1:
        print(__doc__.strip().splitlines()[0])
        print("usage: check_min_macos.py <path to the .app>")
        return 2
    declared, offenders, binaries = too_new(args[0])
    if offenders:
        print(f"{len(offenders)} binaries need a newer macOS than the "
              f"{_words(declared)} the app declares:")
        for minimum, arch, path in offenders:
            print(f"  macOS {_words(minimum)}  {arch}  {path}")
        return 1
    print(f"All {binaries} binaries run on macOS {_words(declared)}, as the "
          "app declares.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
