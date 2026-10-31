"""
write_third_party_notices.py — the licences of what the installer carries
(FN-2, V3.31; docs/homeowner/10-finishing.md §2.3).

The installer bundles Qt, PyQt6, Python and the libraries below, and the map's
and the 3D preview's JavaScript. Most of their licences ask that a copy goes
with the program: the LGPL v3 for Qt, the MIT and BSD licences for the rest. This
writes ``THIRD_PARTY_NOTICES.txt`` at the repository's root, which
``scripts/packaging/permadesign.spec`` ships beside ``LICENSE``.

The texts come from the files themselves: ``html/vendor/*/LICENSE`` for the web
libraries and each installed package's own licence files for the Python ones,
so run it in an environment with ``requirements.txt`` installed::

    python scripts/write_third_party_notices.py          # writes the file
    python scripts/write_third_party_notices.py --check  # names, no writing

``--check`` is what ``tests/test_third_party_notices.py`` runs: every vendored
library and every package ``requirements.txt`` names is in the file. Exact
versions are not written here, because the build installs its own: the
installer's ``build-versions.txt`` (FN-12) says which it carries.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import os
import sys
from typing import NamedTuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "THIRD_PARTY_NOTICES.txt")


class Component(NamedTuple):
    name: str
    what: str
    licence: str
    url: str
    package: str = ""     # the installed distribution whose licence files
                          # are copied in; "" when the text is below
    vendored: str = ""    # html/vendor/<folder> holding a LICENSE


COMPONENTS = (
    Component("Qt 6", "the windows, buttons and drawing", "LGPL-3.0-only",
              "https://www.qt.io/licensing/", package="PyQt6-Qt6"),
    Component("Qt WebEngine (with Chromium)", "the map and the 3D preview",
              "LGPL-3.0-only; Chromium's own components under their "
              "licences, listed at https://doc.qt.io/qt-6/"
              "qtwebengine-licensing.html",
              "https://www.qt.io/licensing/", package="PyQt6-WebEngine-Qt6"),
    Component("PyQt6", "Python's bridge to Qt", "GPL-3.0-only",
              "https://www.riverbankcomputing.com/software/pyqt/",
              package="PyQt6"),
    Component("PyQt6-WebEngine", "Python's bridge to Qt WebEngine",
              "GPL-3.0-only",
              "https://www.riverbankcomputing.com/software/pyqtwebengine/",
              package="PyQt6-WebEngine"),
    Component("PyQt6-sip", "part of PyQt6", "BSD-2-Clause",
              "https://www.riverbankcomputing.com/software/sip/",
              package="PyQt6-sip"),
    Component("Python", "the language the app is written in", "PSF-2.0",
              "https://docs.python.org/3/license.html",
              package="typing_extensions"),
    Component("python-docx", "the planting plan as a Word file", "MIT",
              "https://github.com/python-openxml/python-docx",
              package="python-docx"),
    Component("lxml", "part of python-docx", "BSD-3-Clause",
              "https://lxml.de/", package="lxml"),
    Component("certifi", "the certificates for secure downloads",
              "MPL-2.0", "https://github.com/certifi/python-certifi",
              package="certifi"),
    Component("Shapely (with GEOS)", "shapes, shade and keep-out areas",
              "BSD-3-Clause; GEOS LGPL-2.1", "https://shapely.readthedocs.io/",
              package="shapely"),
    Component("NumPy", "terrain arithmetic",
              "BSD-3-Clause, with parts under 0BSD, MIT, Zlib and CC0-1.0",
              "https://numpy.org/", package="numpy"),
    Component("PyInstaller bootloader", "starts the installed app",
              "GPL-2.0-or-later with the PyInstaller bootloader exception, "
              "which lets it start a program under any licence",
              "https://pyinstaller.org/en/stable/license.html"),
    Component("three.js 0.180.0", "the 3D preview", "MIT",
              "https://threejs.org/"),
    Component("Leaflet 1.9.4", "the map", "BSD-2-Clause",
              "https://leafletjs.com/", vendored="leaflet"),
    Component("Leaflet.draw 1.0.4", "drawing on the map", "MIT",
              "https://github.com/Leaflet/Leaflet.draw",
              vendored="leaflet-draw"),
)

#: three.js ships its licence in the package, not in the files vendored here.
THREE_MIT = """The MIT License

Copyright © 2010-2025 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

HEADER = """Site & Pattern: third-party notices

Site & Pattern is free software under the GNU General Public License, version
3 (the file LICENSE beside this one). It is built on the software below, each
under its own licence, whose texts follow. Which version of each Python
package this copy carries is listed in build-versions.txt, beside this file,
in an installed copy.

The data and photographs the app shows keep their own licences; Help > Where
Site & Pattern's data comes from lists them, with the services the app asks.
"""


def _texts(c: Component) -> list:
    """``[(title, text)]`` for one component."""
    if c.vendored:
        path = os.path.join(ROOT, "html", "vendor", c.vendored, "LICENSE")
        with open(path, encoding="utf-8") as f:
            return [(f"html/vendor/{c.vendored}/LICENSE", f.read())]
    if c.name.startswith("three.js"):
        return [("three.js LICENSE", THREE_MIT)]
    if not c.package:
        return []
    dist = metadata.distribution(c.package)
    out = []
    for f in sorted(dist.files or [], key=str):
        name = str(f)
        if ".dist-info" not in name:
            continue
        base = os.path.basename(name).upper()
        if base.startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE")):
            out.append((name.split(".dist-info/", 1)[1],
                        f.read_text(encoding="utf-8")))
    return out


def render() -> str:
    parts = [HEADER, "", "Components", "=" * 10, ""]
    for c in COMPONENTS:
        parts.append(f"* {c.name}: {c.what}.")
        parts.append(f"  Licence: {c.licence}.")
        parts.append(f"  {c.url}")
    with open(os.path.join(ROOT, "LICENSE"), encoding="utf-8") as f:
        seen = {" ".join(f.read().split()): "LICENSE"}
    for c in COMPONENTS:
        for title, text in _texts(c):
            key = " ".join(text.split())
            body = (f"The same text as {seen[key]}." if key in seen
                    else text.strip())
            seen.setdefault(key, f"{c.name}'s {title}")
            parts += ["", "", "-" * 78, f"{c.name}: {title}", "-" * 78, "",
                      body]
    return "\n".join(parts).rstrip() + "\n"


def required_names() -> list:
    """What the file must name: every requirement and every vendored
    library, as written in requirements.txt and html/vendor/."""
    names = []
    with open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            for sep in "<>=;! ":
                line = line.split(sep, 1)[0]
            if line and line not in names:
                names.append(line)
    vendor = os.path.join(ROOT, "html", "vendor")
    for folder in sorted(os.listdir(vendor)):
        if os.path.isdir(os.path.join(vendor, folder)):
            names.append(folder)
    return names


#: How a requirement or vendor folder is spelled in the component list.
SPELLED = {"leaflet-draw": "Leaflet.draw", "three": "three.js",
           "shapely": "Shapely", "numpy": "NumPy", "leaflet": "Leaflet"}


def missing(text: str) -> list:
    return [n for n in required_names() if SPELLED.get(n, n) not in text]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="check the committed file names everything; write "
                         "nothing")
    args = ap.parse_args(argv)
    if args.check:
        with open(OUT, encoding="utf-8") as f:
            gone = missing(f.read())
        for n in gone:
            print(f"not named in THIRD_PARTY_NOTICES.txt: {n}")
        return 1 if gone else 0
    text = render()
    gone = missing(text)
    if gone:
        print("add these to COMPONENTS first: " + ", ".join(gone))
        return 1
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"wrote {os.path.relpath(OUT, ROOT)} ({len(text) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
