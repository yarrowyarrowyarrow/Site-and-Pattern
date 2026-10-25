"""
tests/test_js_names.py — every function a page's scripts call by name is
declared somewhere (V3.37).

The 3D viewer (``html/scene3d/*.js``) and the 2D map (``html/map/*.js``) are
classic scripts sharing one global scope, so a function declared in one chunk is
called from another by bare name, and nothing checks the name until the call
runs. V3.22 deleted ``buildStructures`` together with the splat code it sat
between; ``permaSetScene`` still called it, so every scene push threw after the
plants were built and before the sun, the shadows and the camera were set. The
owner saw a dark scene under "3D viewer error: Uncaught ReferenceError:
buildStructures is not defined". The render gates that would have caught it
skipped, reading the thrown probe as a machine without WebGL (see
``tests/test_scene3d_render.py:viewer_errors``).

This needs no browser and is never skipped. It reads every chunk with comments,
strings and regular expressions taken out, collects every name declared
anywhere (functions, variables, parameters, ``window.x =``), and fails on a
bare call to a name in none of them and not a browser built-in.
"""

import os
import pathlib
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_HTML = pathlib.Path(__file__).resolve().parent.parent / "html"

#: What the browser provides, and what each page's bootstrap sets on window
#: before the chunks run (scene3d.html: mergeGeometries).
BROWSER = {
    "Number", "String", "Boolean", "Array", "Object", "Date", "Symbol",
    "addEventListener", "removeEventListener", "requestAnimationFrame",
    "cancelAnimationFrame", "setTimeout", "clearTimeout", "setInterval",
    "clearInterval", "fetch", "encodeURIComponent", "decodeURIComponent",
    "isFinite", "isNaN", "parseFloat", "parseInt", "prompt", "alert", "confirm",
    "getComputedStyle", "queueMicrotask", "structuredClone",
    "mergeGeometries",
}

_KEYWORDS = {
    "if", "for", "while", "switch", "return", "function", "catch", "typeof",
    "new", "await", "yield", "delete", "void", "in", "of", "do", "else", "case",
    "throw", "super", "import",
}
_NAME = r"[A-Za-z_$][\w$]*"


def _code(src):
    """The source with comments, strings and regular expressions blanked."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"//[^\n]*", " ", src)
    src = re.sub(r"`(?:\\.|[^`\\])*`", "``", src, flags=re.S)
    src = re.sub(r"'(?:\\.|[^'\\\n])*'", "''", src)
    src = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', src)
    return re.sub(r"([=(,:!&|?{};]\s*)/(?:\\.|\[(?:\\.|[^\]\\])*\]|[^/\\\n\[])+"
                  r"/[gimsuy]*", r"\1/re/", src)


def _declared(code):
    names = set(re.findall(r"\bfunction\s*\*?\s*(" + _NAME + ")", code))
    names |= set(re.findall(r"\b(?:const|let|var)\s+(" + _NAME + ")", code))
    names |= set(re.findall(r"\bwindow\.(" + _NAME + r")\s*=", code))
    names |= set(re.findall(r"(" + _NAME + r")\s*=>", code))
    names |= set(re.findall(r"catch\s*\(\s*(" + _NAME + ")", code))
    lists = re.findall(r"\b(?:const|let|var)\s*[\[{]([^=]*?)[\]}]\s*=", code)
    lists += re.findall(r"function\s*[\w$]*\s*\(([^)]*)\)", code)
    lists += re.findall(r"\(([^()]*)\)\s*=>", code)
    for names_in in lists:
        names |= set(re.findall(_NAME, names_in))
    return names


def _undeclared(sources, page=""):
    """{called name: [chunks]} for every bare call to a name that no chunk, and
    nothing in the page itself, declares. `sources` is {chunk: source}."""
    chunks = {name: _code(src) for name, src in sources.items()}
    declared = set(BROWSER) | _declared(_code(page))
    for code in chunks.values():
        declared |= _declared(code)
    missing = {}
    for name, code in chunks.items():
        for m in re.finditer(r"(?<![\w$.])(" + _NAME + r")\s*\(", code):
            called = m.group(1)
            if called in _KEYWORDS or called in declared:
                continue
            if re.search(r"(?:function|new)\s*$", code[max(0, m.start() - 12):m.start()]):
                continue
            missing.setdefault(called, set()).add(name)
    return {k: sorted(v) for k, v in missing.items()}


def _undeclared_calls(folder, page):
    return _undeclared({p.name: p.read_text(encoding="utf-8")
                        for p in sorted((_HTML / folder).glob("*.js"))},
                       (_HTML / page).read_text(encoding="utf-8"))


class EveryCalledFunctionIsDeclared(unittest.TestCase):

    def test_the_3d_viewer(self):
        self.assertEqual(_undeclared_calls("scene3d", "scene3d.html"), {},
                         "a chunk calls a function no chunk declares; it "
                         "throws the first time that line runs")

    def test_the_map(self):
        self.assertEqual(_undeclared_calls("map", "map.html"), {},
                         "a chunk calls a function no chunk declares; it "
                         "throws the first time that line runs")

    def test_it_finds_the_v322_deletion(self):
        """The check has to see the case that started it: a chunk calling a
        function nobody declares any more."""
        found = _undeclared({
            "05-flowers.js": "window.permaSetScene = function (sc) {\n"
                             "  buildPlants(g, sc.plants);\n"
                             "  buildStructures(g, sc.structures);  // gone\n"
                             "  const t = '(not a call)'; fitShadow(sc.bounds);\n"
                             "};\n",
            "02-plants.js": "function buildPlants(group, plants) {}\n"
                            "const fitShadow = (b) => b;\n"})
        self.assertEqual(found, {"buildStructures": ["05-flowers.js"]})


if __name__ == "__main__":
    unittest.main()
