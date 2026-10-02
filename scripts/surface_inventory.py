#!/usr/bin/env python3
"""
scripts/surface_inventory.py — every surface of the app, walked, counted and
clicked (V3.05).

Written for the retirement pass that F94 (a task-shaped home) and F89 (the 3D
preview's toolbar) both say must come first: *what is genuinely load-bearing?*
That question had been answered by reasoning for a year. This answers it by
measurement, from the real window, the way V3.02 and V3.03 measured focus and
contrast:

* **Inventory.** Boots ``MainWindow`` in a sandbox (its own HOME, so no user
  data or settings are read or written), opens the worked example, and walks
  every tab at every depth, the menus, the toolbars and the strips above the
  map. Per page: each control (kind, words, tooltip, accessible name, enabled,
  whether it is wired to anything), how far down the column it sits and
  whether a person at 1366 × 768 has to scroll to reach it, the words of prose
  on the page and its longest paragraph. A screenshot of each page, and of the
  whole column when it scrolls.
* **Click pass** (``--click``). Clicks every enabled button on every page and
  records what changed: a window or dialog opened, a question asked, the map
  told something, the design changed, the mode or the status line changed,
  controls appeared, text on the page changed, or *nothing at all*. Dialogs,
  questions, file pickers and URL opens are intercepted and answered "cancel",
  so nothing is saved, deleted or sent. An exception in a slot is caught and
  recorded against the control that raised it (without this, PyQt6 aborts the
  process, which is what the shipped app does).
* **Windows** (``--windows``). Opens the secondary windows from the View menu
  and inventories each.

Run under a virtual display so the web views render (headless Chromium under
``offscreen`` draws nothing), in an Arial-metric font, which is what Windows
users measure in::

    QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox QT_QPA_PLATFORM=xcb \\
      xvfb-run -a -s "-screen 0 1366x768x24" \\
      python scripts/surface_inventory.py --out /tmp/surface --click --windows

Output: ``<out>/inventory.json`` and ``<out>/shots/*.png``. Prints a summary.
Exits with ``os._exit`` after writing, because WebEngine's teardown segfaults
in a GPU-less container (CLAUDE.md, "Running tests") and that must not read as
a failed run.

Dev tool, not shipped. Nothing in ``src/`` imports it.
"""

from __future__ import annotations

import argparse
import faulthandler
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Arial's metrics, which Windows and most macOS text widths are close to. CI
# draws in DejaVu Sans, about 12% wider (CLAUDE.md, V3.03); --font changes it.
_FONTS_CONF = """<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <alias binding="strong">
    <family>sans-serif</family><prefer><family>{font}</family></prefer>
  </alias>
  <match target="pattern">
    <test qual="any" name="family"><string>DejaVu Sans</string></test>
    <edit name="family" mode="assign" binding="strong"><string>{font}</string></edit>
  </match>
</fontconfig>
"""

# Buttons and actions the click pass leaves alone, by their words. Each would
# leave the sandbox: quit the process, or reach for git or the network.
_NEVER_CLICK = (
    "exit", "quit", "check for updates", "switch to a specific version",
)


def _sandbox(font: str) -> None:
    """Re-exec once into a throwaway HOME: settings, the catalogue database,
    logs, saves and the font configuration all land there, never in the real
    user's folders."""
    if os.environ.get("SURFACE_SANDBOX"):
        return
    home = tempfile.mkdtemp(prefix="surface_home_")
    cfg = os.path.join(home, ".config")
    os.makedirs(os.path.join(cfg, "fontconfig"))
    with open(os.path.join(cfg, "fontconfig", "fonts.conf"), "w") as fh:
        fh.write(_FONTS_CONF.format(font=font))
    env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=cfg,
               XDG_DATA_HOME=os.path.join(home, ".local", "share"),
               XDG_CACHE_HOME=os.path.join(home, ".cache"),
               SURFACE_SANDBOX="1")
    os.execve(sys.executable, [sys.executable] + sys.argv, env)


# ── Qt, from here on ──────────────────────────────────────────────────────────

def _qt():
    # The import order main.py uses: WebEngine before any QApplication.
    from PyQt6 import QtWebEngineWidgets  # noqa: F401
    from PyQt6 import QtCore, QtGui, QtWidgets
    return QtCore, QtGui, QtWidgets


QtCore = QtGui = QtWidgets = None
APP = None
MAIN = None
LOG = {"dialogs": [], "boxes": [], "files": [], "urls": [], "errors": [],
       "menus": [], "js": []}


def pump(ms: int = 60) -> None:
    end = time.monotonic() + ms / 1000.0
    while True:
        APP.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 20)
        if time.monotonic() >= end:
            break
        time.sleep(0.005)


def wait_for(pred, timeout_s: float, step_ms: int = 100) -> bool:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        try:
            if pred():
                return True
        except Exception:                                  # noqa: BLE001
            pass
        pump(step_ms)
    return False


# ── Interception: nothing leaves the sandbox, nothing blocks ─────────────────

#: While on, a dialog that would be shown modally is instead shown, waited for,
#: photographed and inventoried, then dismissed: the click pass then records
#: the dialogs it reaches as surfaces in their own right.
CAPTURE = {"on": False, "busy": False, "out": "", "seen": {}, "records": []}


def _capture_dialog(dlg) -> None:
    key = f"{type(dlg).__name__}|{dlg.windowTitle()}"
    if key in CAPTURE["seen"]:
        CAPTURE["seen"][key] += 1
        return
    CAPTURE["seen"][key] = 1
    dlg.show()
    dlg.raise_()
    pump(900)
    slug = _slug(["dialog", type(dlg).__name__, dlg.windowTitle()])
    path = os.path.join(CAPTURE["out"], f"{slug}.png")
    try:
        g = dlg.frameGeometry()
        APP.primaryScreen().grabWindow(0, g.x(), g.y(), g.width(),
                                       g.height()).save(path)
    except Exception:                                      # noqa: BLE001
        dlg.grab().save(path)
    ctrls = [c for c in dlg.findChildren(QtWidgets.QWidget)
             if isinstance(c, _interactive_types()) and not _is_internal(c)
             and c.isVisibleTo(dlg)]
    labels = [_plain(l.text()) for l in dlg.findChildren(QtWidgets.QLabel)
              if l.isVisibleTo(dlg) and _plain(l.text())]
    tabs = [[_label_of_tab(tw.tabText(i)) for i in range(tw.count())]
            for tw in dlg.findChildren(QtWidgets.QTabWidget)]
    CAPTURE["records"].append({
        "class": type(dlg).__name__, "title": dlg.windowTitle(),
        "size": [dlg.width(), dlg.height()], "tabs": tabs,
        "controls": [_describe(c) for c in ctrls],
        "words": sum(_words(t) for t in labels),
        "prose": sorted(({"words": _words(t), "text": t[:140]}
                         for t in labels if _words(t) >= 15),
                        key=lambda d: -d["words"])[:8],
        "shot": os.path.basename(path)})
    dlg.hide()


def _install_interceptors() -> None:
    W = QtWidgets

    def _fake_exec(self, *a, **k):
        LOG["dialogs"].append({"class": type(self).__name__,
                               "title": self.windowTitle()})
        if CAPTURE["on"] and not CAPTURE["busy"]:
            CAPTURE["busy"] = True
            try:
                _capture_dialog(self)
            except Exception as exc:                       # noqa: BLE001
                sys.stderr.write(f"[surface] capture failed: {exc}\n")
            CAPTURE["busy"] = False
        try:
            self.reject()
        except Exception:                                  # noqa: BLE001
            pass
        return 0

    for name in dir(W):
        cls = getattr(W, name)
        if isinstance(cls, type) and issubclass(cls, W.QDialog):
            if "exec" in cls.__dict__ or cls is W.QDialog:
                cls.exec = _fake_exec

    def _box(kind, ret):
        def f(parent, title, text="", *a, **k):
            LOG["boxes"].append({"kind": kind, "title": str(title),
                                 "text": re.sub(r"\s+", " ", str(text))[:160]})
            return ret
        return staticmethod(f)

    SB = W.QMessageBox.StandardButton
    W.QMessageBox.question = _box("question", SB.No)
    W.QMessageBox.warning = _box("warning", SB.Ok)
    W.QMessageBox.information = _box("information", SB.Ok)
    W.QMessageBox.critical = _box("critical", SB.Ok)
    W.QMessageBox.about = _box("about", None)

    def _file(kind):
        def f(*a, **k):
            caption = ""
            for v in a[1:2]:
                caption = str(v)
            LOG["files"].append({"kind": kind, "caption": caption})
            return ("", "") if kind != "getExistingDirectory" else ""
        return staticmethod(f)

    for kind in ("getOpenFileName", "getOpenFileNames", "getSaveFileName",
                 "getExistingDirectory"):
        setattr(W.QFileDialog, kind, _file(kind))

    def _input(kind):
        def f(*a, **k):
            LOG["dialogs"].append({"class": "QInputDialog." + kind,
                                   "title": str(a[1]) if len(a) > 1 else ""})
            return ("", False) if kind in ("getText", "getItem",
                                           "getMultiLineText") else (0, False)
        return staticmethod(f)

    for kind in ("getText", "getItem", "getInt", "getDouble",
                 "getMultiLineText"):
        setattr(W.QInputDialog, kind, _input(kind))

    def _color(*a, **k):
        LOG["dialogs"].append({"class": "QColorDialog.getColor", "title": ""})
        return QtGui.QColor()
    W.QColorDialog.getColor = staticmethod(_color)

    def _menu_exec(self, *a, **k):
        LOG["menus"].append([a.text() for a in self.actions() if a.text()])
        return None
    W.QMenu.exec = _menu_exec

    def _open_url(url, *a, **k):
        LOG["urls"].append(url.toString() if hasattr(url, "toString")
                           else str(url))
        return True
    QtGui.QDesktopServices.openUrl = staticmethod(_open_url)
    import webbrowser
    webbrowser.open = lambda url, *a, **k: LOG["urls"].append(url) or True
    webbrowser.open_new_tab = webbrowser.open

    # PyQt6 aborts the process on an exception escaping a slot unless
    # sys.excepthook has been replaced; the shipped app does not replace it.
    def _hook(etype, value, tb):
        LOG["errors"].append({
            "type": etype.__name__, "message": str(value)[:300],
            "where": "".join(traceback.format_tb(tb)[-3:])[-900:]})
        sys.stderr.write("[surface] exception in a slot: "
                         + "".join(traceback.format_exception(
                             etype, value, tb))[-1500:] + "\n")
    sys.excepthook = _hook


def _intercept_map_js(main) -> None:
    for view in (main.map_widget,):
        page = view.page()
        orig = page.runJavaScript

        def run(js, *a, _orig=orig, **k):
            LOG["js"].append(str(js)[:120])
            return _orig(js, *a, **k)
        page.runJavaScript = run


# ── Describing what is on screen ──────────────────────────────────────────────

def _plain(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", (text or "").replace("&nbsp;", " "))
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", text).strip()


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][\w'’.-]*", _plain(text)))


def _label_of_tab(text: str) -> str:
    return _plain(text).replace("&&", "&").replace("&", "", 1) \
        if "&" in text and "&&" not in text else _plain(text).replace("&&", "&")


def _kind(w) -> str:
    W = QtWidgets
    for cls, name in ((W.QCheckBox, "checkbox"), (W.QRadioButton, "radio"),
                      (W.QToolButton, "toolbutton"), (W.QPushButton, "button"),
                      (W.QComboBox, "dropdown"), (W.QSlider, "slider"),
                      (W.QDateTimeEdit, "date"), (W.QAbstractSpinBox, "spinbox"),
                      (W.QLineEdit, "textfield"), (W.QTextEdit, "textarea"),
                      (W.QPlainTextEdit, "textarea"),
                      (W.QTableView, "table"), (W.QTreeView, "tree"),
                      (W.QListView, "list"), (W.QAbstractSlider, "slider")):
        if isinstance(w, cls):
            return name
    return type(w).__name__


def _interactive_types():
    W = QtWidgets
    return (W.QAbstractButton, W.QComboBox, W.QAbstractSpinBox,
            W.QAbstractSlider, W.QLineEdit, W.QTextEdit, W.QPlainTextEdit,
            W.QAbstractItemView)


def _is_internal(w) -> bool:
    """Parts of composite widgets Qt builds for itself: a tab bar's scroll
    arrows, a scroll area's bars, a spin box's line edit, a combo's view."""
    W = QtWidgets
    p = w.parentWidget()
    while p is not None:
        if isinstance(p, (W.QTabBar, W.QAbstractSpinBox, W.QComboBox,
                          W.QScrollBar)):
            return True
        if isinstance(p, W.QAbstractScrollArea) and not isinstance(
                p, W.QScrollArea) and w is not p:
            return True             # a list's or text box's own viewport parts
        p = p.parentWidget()
    if isinstance(w, W.QScrollBar):
        return True
    if type(w).__name__ in ("QTabBar", "QCalendarWidget"):
        return True
    return False


def _receivers(w) -> int:
    W = QtWidgets
    sigs = []
    if isinstance(w, W.QAbstractButton):
        sigs = [w.clicked, w.toggled, w.pressed, w.released]
    elif isinstance(w, W.QComboBox):
        sigs = [w.currentIndexChanged, w.currentTextChanged, w.activated,
                w.textActivated]
    elif isinstance(w, W.QAbstractSlider):
        sigs = [w.valueChanged, w.sliderMoved, w.sliderReleased]
    elif isinstance(w, W.QAbstractSpinBox):
        sigs = [w.editingFinished] + ([w.valueChanged]
                                      if hasattr(w, "valueChanged") else []) \
            + ([w.dateChanged] if hasattr(w, "dateChanged") else [])
    elif isinstance(w, W.QLineEdit):
        sigs = [w.textChanged, w.textEdited, w.returnPressed,
                w.editingFinished]
    elif isinstance(w, (W.QTextEdit, W.QPlainTextEdit)):
        sigs = [w.textChanged]
    elif isinstance(w, W.QAbstractItemView):
        sigs = [w.clicked, w.doubleClicked, w.activated, w.pressed]
        try:
            sm = w.selectionModel()
            if sm is not None:
                return sum(w.receivers(s) for s in sigs) + sum(
                    sm.receivers(s) for s in (sm.currentChanged,
                                              sm.selectionChanged))
        except Exception:                                  # noqa: BLE001
            pass
    n = 0
    for s in sigs:
        try:
            n += w.receivers(s)
        except Exception:                                  # noqa: BLE001
            pass
    return n


def _recv(obj, *names):
    """How many slots listen to ``obj``'s signals ``names``; None when Qt will
    not say (objects Qt made itself, such as a menu's own actions)."""
    n = 0
    for name in names:
        try:
            n += obj.receivers(getattr(obj, name))
        except (RuntimeError, AttributeError, TypeError):
            return None
    return n


def _scroll_area_of(w):
    W = QtWidgets
    p = w.parentWidget()
    while p is not None:
        if isinstance(p, W.QScrollArea):
            return p
        p = p.parentWidget()
    return None


def _describe(w, page=None) -> dict:
    W = QtWidgets
    text = ""
    if isinstance(w, W.QAbstractButton):
        text = w.text()
    elif isinstance(w, W.QComboBox):
        text = w.currentText()
    elif isinstance(w, W.QLineEdit):
        text = w.placeholderText() or w.text()
    d = {
        "kind": _kind(w),
        "text": _plain(text)[:90],
        "tooltip": _plain(w.toolTip())[:200],
        "name": _plain(w.accessibleName())[:90],
        "enabled": w.isEnabled(),
        "wired": _receivers(w),
        "w": w.width(), "h": w.height(),
    }
    if isinstance(w, W.QAbstractButton):
        d["checkable"] = w.isCheckable()
        d["checked"] = w.isChecked() if w.isCheckable() else None
        menu = w.menu() if hasattr(w, "menu") else None
        if menu is not None:
            d["menu"] = [_plain(a.text()) for a in menu.actions() if a.text()]
    if isinstance(w, W.QComboBox):
        d["items"] = w.count()
        d["editable"] = w.isEditable()
    if isinstance(w, W.QAbstractItemView):
        try:
            d["rows"] = w.model().rowCount() if w.model() else 0
        except Exception:                                  # noqa: BLE001
            d["rows"] = None
    sa = _scroll_area_of(w)
    if sa is not None and sa.widget() is not None:
        y = w.mapTo(sa.widget(), QtCore.QPoint(0, 0)).y()
        vh = max(1, sa.viewport().height())
        d["y"] = y
        d["viewport_h"] = vh
        d["below_fold"] = (y + min(w.height(), 24)) > vh
    else:
        top = w.mapTo(w.window(), QtCore.QPoint(0, 0)).y()
        d["y"] = top
        d["below_fold"] = top + min(w.height(), 24) > w.window().height()
    return d


# ── Walking the tab tree ──────────────────────────────────────────────────────

class Page:
    def __init__(self, path, widget, chain):
        self.path = path            # labels, outermost first
        self.widget = widget
        self.chain = chain          # [(tabwidget, index), ...] to select it

    @property
    def key(self) -> str:
        return " › ".join(self.path)


def select(chain) -> None:
    for tw, i in chain:
        if tw.currentIndex() != i:
            tw.setCurrentIndex(i)
    pump(80)


def _directly_inside(tw, page_w) -> bool:
    """True when no other tab widget stands between ``page_w`` and ``tw``."""
    p = tw.parentWidget()
    while p is not None and p is not page_w:
        if isinstance(p, QtWidgets.QTabWidget):
            return False
        p = p.parentWidget()
    return p is page_w


def walk_tabs(root_tabs, root_path=()) -> list:
    """Every page of every tab widget reachable from ``root_tabs``, outermost
    first, each with the selections that show it."""
    W = QtWidgets
    pages: list[Page] = []
    registry: dict = {}

    def nearest_page(w):
        p = w.parentWidget()
        while p is not None:
            if id(p) in registry:
                return registry[id(p)]
            p = p.parentWidget()
        return None

    def visit(tw, path, chain, parent_page):
        for i in range(tw.count()):
            page_w = tw.widget(i)
            label = _label_of_tab(tw.tabText(i)) or f"tab {i + 1}"
            c = chain + [(tw, i)]
            select(c)
            pg = Page(list(path) + [label], page_w, c)
            registry[id(page_w)] = pg
            pages.append(pg)
            nested = [t for t in page_w.findChildren(W.QTabWidget)
                      if _directly_inside(t, page_w)]
            for t in nested:
                visit(t, pg.path, c, pg)

    for tw in root_tabs:
        visit(tw, list(root_path), [], None)
    return pages, registry


def owner_page(w, registry):
    p = w.parentWidget()
    while p is not None:
        if id(p) in registry:
            return registry[id(p)]
        p = p.parentWidget()
    return None


def controls_on(page: Page, registry, top) -> list:
    W = QtWidgets
    out = []
    for w in page.widget.findChildren(QtWidgets.QWidget):
        if not isinstance(w, _interactive_types()):
            continue
        if _is_internal(w) or not w.isVisibleTo(top):
            continue
        if owner_page(w, registry) is not page:
            continue
        out.append(w)
    out.sort(key=lambda w: (w.mapTo(top, QtCore.QPoint(0, 0)).y(),
                            w.mapTo(top, QtCore.QPoint(0, 0)).x()))
    return out


def labels_on(page: Page, registry, top) -> list:
    W = QtWidgets
    out = []
    for w in page.widget.findChildren(W.QLabel):
        if not w.isVisibleTo(top) or owner_page(w, registry) is not page:
            continue
        t = _plain(w.text())
        if t:
            out.append(t)
    return out


def scroll_of(page: Page, top) -> dict:
    """The deepest scroll area that holds the page's controls, and how many
    screens of it there are."""
    W = QtWidgets
    best = None
    areas = [page.widget] if isinstance(page.widget, W.QScrollArea) else []
    areas += [a for a in page.widget.findChildren(W.QScrollArea)
              if a.isVisibleTo(top)]
    p = page.widget.parentWidget()
    while p is not None:
        if isinstance(p, W.QScrollArea):
            areas.append(p)
        p = p.parentWidget()
    for a in areas:
        if a.widget() is None:
            continue
        ch, vh = a.widget().height(), max(1, a.viewport().height())
        if best is None or ch * 1.0 / vh > best["screens"]:
            best = {"content_h": ch, "viewport_h": vh,
                    "screens": round(ch / vh, 2), "area": a}
    return best or {"content_h": 0, "viewport_h": 0, "screens": 0.0,
                    "area": None}


def _slug(parts) -> str:
    s = "-".join(parts).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:80] or "page"


# ── Chrome: menus, toolbars, the strips around the map ────────────────────────

def menu_tree(menu, path=()) -> list:
    out = []
    for a in menu.actions():
        if a.isSeparator():
            continue
        label = _plain(a.text()).replace("&", "")
        item = {"path": list(path) + [label], "shortcut":
                a.shortcut().toString(), "enabled": a.isEnabled(),
                "checkable": a.isCheckable(), "tip": _plain(a.statusTip()),
                "wired": _recv(a, "triggered", "toggled")}
        out.append(item)
        if a.menu() is not None:
            out.extend(menu_tree(a.menu(), item["path"]))
    return out


def toolbar_items(main) -> list:
    W = QtWidgets
    out = []
    for bar in main.findChildren(W.QToolBar):
        if not bar.isVisibleTo(main):
            continue
        row = bar.windowTitle() or bar.objectName() or "toolbar"
        for a in bar.actions():
            if a.isSeparator() or not a.isVisible():
                continue
            w = bar.widgetForAction(a)
            label = _plain(a.text()) or (
                _plain(w.toolTip()) if w is not None else "")
            out.append({"row": row, "text": label,
                        "tip": _plain(a.toolTip() or a.statusTip()),
                        "checkable": a.isCheckable(), "enabled": a.isEnabled(),
                        "wired": _recv(a, "triggered", "toggled"),
                        "kind": _kind(w) if w is not None else "action",
                        "hidden_in_overflow": (w is not None
                                               and not w.isVisibleTo(main))})
    return out


# ── State, for the click pass ─────────────────────────────────────────────────

def _visible_windows() -> dict:
    W = QtWidgets
    out = {}
    for w in APP.topLevelWidgets():
        if not w.isVisible() or w is MAIN:
            continue
        if isinstance(w, W.QMenu) or type(w).__name__ in (
                "QTipLabel", "QComboBoxPrivateContainer"):
            continue
        out[id(w)] = (type(w).__name__, w.windowTitle(), w)
    return out


def _tab_state(main) -> tuple:
    return tuple(t.currentIndex()
                 for t in main._side_tabs.findChildren(QtWidgets.QTabWidget)
                 ) + (main._side_tabs.currentIndex(),)


def _view_shape(view) -> str:
    """Rows, and for a tree which of them are open: expanding a tree changes
    what a person sees without changing its row count."""
    W = QtWidgets
    try:
        model = view.model()
        if model is None:
            return "0"
        n = model.rowCount()
        if isinstance(view, W.QTreeView):
            opened = sum(1 for r in range(min(n, 400))
                         if view.isExpanded(model.index(r, 0)))
            kids = sum(model.rowCount(model.index(r, 0))
                       for r in range(min(n, 400)))
            return f"{n}/{opened}/{kids}"
        return str(n)
    except Exception:                                      # noqa: BLE001
        return "?"


def _page_fingerprint(page: Page, registry, top) -> tuple:
    labels = labels_on(page, registry, top)
    ctrls = controls_on(page, registry, top)
    texts = []
    for w in ctrls:
        if isinstance(w, QtWidgets.QAbstractItemView):
            texts.append(_view_shape(w))
        elif isinstance(w, QtWidgets.QAbstractButton):
            texts.append(_plain(w.text()) + ("*" if w.isEnabled() else ""))
        elif isinstance(w, QtWidgets.QComboBox):
            texts.append(_plain(w.currentText()))
    blob = "\n".join(labels + texts)
    return (len(ctrls), hashlib.md5(blob.encode()).hexdigest(), len(labels))


def state(main, page, registry) -> dict:
    s = {
        "windows": _visible_windows(),
        "tabs": _tab_state(main),
        "mode": main._sb_mode.text() if hasattr(main, "_sb_mode") else "",
        "status": main.statusBar().currentMessage(),
        "features": len(main._project.get("features", [])),
        "undo": len(getattr(main, "_undo_stack", [])),
        "modified": bool(getattr(main, "_modified", False)),
        "counts": {k: len(v) for k, v in LOG.items()},
        "page": _page_fingerprint(page, registry, main) if page else None,
    }
    bar = getattr(main, "placement_bar", None)
    s["placing"] = bool(bar is not None and bar.isVisible())
    flyout = getattr(main, "species_flyout", None)
    s["flyout"] = bool(flyout is not None and flyout.isVisible())
    return s


def effects(before: dict, after: dict) -> dict:
    e = {}
    new = [v for k, v in after["windows"].items() if k not in before["windows"]]
    if new:
        e["window"] = [f"{c}: {t}" for c, t, _ in new]
    for k in ("dialogs", "boxes", "files", "urls", "errors", "menus", "js"):
        n0, n1 = before["counts"][k], after["counts"][k]
        if n1 > n0:
            e[k] = LOG[k][n0:n1][:4]
    if after["tabs"] != before["tabs"]:
        e["navigated"] = True
    for k in ("mode", "status", "features", "undo", "modified", "placing",
              "flyout"):
        if after[k] != before[k]:
            e[k] = [before[k], after[k]]
    if before["page"] and after["page"] and before["page"] != after["page"]:
        b, a = before["page"], after["page"]
        if a[0] != b[0]:
            e["controls_changed"] = [b[0], a[0]]
        if a[1] != b[1]:
            e["page_text_changed"] = True
    return e


def restore(main, before: dict, page: Page | None, example_path: str) -> None:
    for k, (c, t, w) in list(_visible_windows().items()):
        if k not in before["windows"]:
            try:
                w.close()
                w.deleteLater()
            except Exception:                              # noqa: BLE001
                pass
    try:
        if main._sb_mode.text() != before["mode"]:
            main._cancel_draw()
    except Exception:                                      # noqa: BLE001
        pass
    guard = 0
    while len(getattr(main, "_undo_stack", [])) > before["undo"] and guard < 8:
        try:
            main._do_undo()
        except Exception:                                  # noqa: BLE001
            break
        guard += 1
        pump(60)
    if len(main._project.get("features", [])) != before["features"] \
            and example_path:
        main._modified = False
        try:
            main._load_from_path(example_path)
        except Exception:                                  # noqa: BLE001
            pass
        pump(400)
    try:
        main._modified = before["modified"]
    except Exception:                                      # noqa: BLE001
        pass
    # Let a background fetch an undo restarted (the site pin's) finish, so its
    # status lines do not land on the next control's record.
    wait_for(lambda: "fetching" not in main._sb_mode.text().lower(), 8)
    if page is not None:
        select(page.chain)


def _skip(text: str) -> bool:
    t = text.lower()
    return any(s in t for s in _NEVER_CLICK)


# ── The run ───────────────────────────────────────────────────────────────────

def say(msg: str) -> None:
    print(f"[surface] {msg}", flush=True)


def main_run(args) -> dict:
    global QtCore, QtGui, QtWidgets, APP, MAIN
    faulthandler.enable()
    QtCore, QtGui, QtWidgets = _qt()
    from PyQt6.QtWidgets import QApplication

    APP = QApplication(["site-and-pattern-surface"])
    APP.setApplicationName("PermaDesign")
    APP.setOrganizationName("PermaDesign")
    from src import focus_ring, indicator_style, target_size
    focus_ring.install(APP)
    target_size.install(APP)
    indicator_style.install(APP)

    _install_interceptors()

    from src.app import MainWindow
    from src import onboarding_flow

    t0 = time.monotonic()
    say("building the window")
    main = MainWindow()
    MAIN = main
    w, h = args.size
    main.resize(w, h)
    main.move(0, 0)
    main.show()
    say("waiting for the map")
    ready = wait_for(lambda: main.map_widget.is_ready, 60)
    _intercept_map_js(main)
    meta = {"size": [w, h], "font": QtGui.QFontInfo(APP.font()).family(),
            "font_px": QtGui.QFontInfo(APP.font()).pixelSize(),
            "map_ready": ready, "boot_s": round(time.monotonic() - t0, 1)}

    example = ""
    if args.example:
        say("opening the example")
        onboarding_flow.open_example(main)
        pump(1500)
        wait_for(lambda: "fetching" not in main._sb_mode.text().lower(), 15)
        example = onboarding_flow.example_path()
        meta["example_plants"] = len(main._placed_plants)
    shots = os.path.join(args.out, "shots")
    os.makedirs(shots, exist_ok=True)

    main.grab().save(os.path.join(shots, "00-window.png"))

    # Chrome
    chrome = {
        "menus": [],
        "toolbar": toolbar_items(main),
        "first_step_bar": [],
        "status_bar": [],
    }
    for a in main.menuBar().actions():
        if a.menu() is not None:
            chrome["menus"].extend(menu_tree(a.menu(),
                                             (_plain(a.text()).replace("&", ""),)))
    fsb = getattr(main, "first_step_bar", None)
    if fsb is not None:
        chrome["first_step_bar"] = [
            _describe(c) for c in fsb.findChildren(QtWidgets.QAbstractButton)
            if c.isVisibleTo(main)]
        chrome["first_step_bar_visible"] = fsb.isVisible()
    for lab in main.statusBar().findChildren(QtWidgets.QLabel):
        if lab.isVisibleTo(main) and _plain(lab.text()):
            chrome["status_bar"].append(_plain(lab.text())[:120])

    # Pages
    say("walking the tabs")
    pages, registry = walk_tabs([main._side_tabs])
    out_pages = []
    for pg in pages:
        select(pg.chain)
        pump(150)
        ctrls = controls_on(pg, registry, main)
        labels = labels_on(pg, registry, main)
        sc = scroll_of(pg, main)
        prose = sorted(({"words": _words(t), "text": t[:140]}
                        for t in labels if _words(t) >= 15),
                       key=lambda d: -d["words"])
        slug = _slug(pg.path)
        main._side_wrapper.grab().save(os.path.join(shots, f"{slug}.png"))
        full = ""
        area = sc.pop("area", None)
        if area is not None and sc["screens"] > 1.05:
            full = f"{slug}-full.png"
            area.widget().grab().save(os.path.join(shots, full))
        out_pages.append({
            "path": pg.path, "depth": len(pg.path),
            "controls": [_describe(c, pg) for c in ctrls],
            "labels": len(labels),
            "words": sum(_words(t) for t in labels),
            "prose": prose[:12],
            "scroll": sc,
            "shot": f"{slug}.png", "shot_full": full,
        })

    report = {"meta": meta, "chrome": chrome, "pages": out_pages,
              "clicks": [], "windows": []}

    CAPTURE["out"] = shots
    CAPTURE["on"] = args.dialogs

    # Click pass
    if args.click:
        faulthandler.enable()
        for pg in pages:
            select(pg.chain)
            pump(120)
            ctrls = [c for c in controls_on(pg, registry, main)
                     if isinstance(c, QtWidgets.QAbstractButton)]
            done = 0
            for c in ctrls:
                try:
                    if not c.isVisible() or not c.isEnabled():
                        continue
                except RuntimeError:
                    continue            # deleted by an earlier click's rebuild
                label = _plain(c.text()) or _plain(c.toolTip()) or \
                    _plain(c.accessibleName())
                rec = {"page": pg.path, "text": label[:90],
                       "kind": _kind(c)}
                menu = c.menu() if hasattr(c, "menu") else None
                if menu is not None:
                    rec["effects"] = {"opens_menu": [
                        _plain(a.text()) for a in menu.actions() if a.text()]}
                    report["clicks"].append(rec)
                    continue
                if _skip(label):
                    rec["effects"] = {"skipped": True}
                    report["clicks"].append(rec)
                    continue
                before = state(main, pg, registry)
                was = c.isChecked() if c.isCheckable() else None
                faulthandler.dump_traceback_later(90, exit=True)
                try:
                    c.click()
                except RuntimeError as exc:
                    LOG["errors"].append({"type": "RuntimeError",
                                          "message": str(exc)[:200],
                                          "where": "click"})
                pump(args.settle)
                after = state(main, pg, registry)
                faulthandler.cancel_dump_traceback_later()
                rec["effects"] = effects(before, after)
                try:
                    if was is not None and c.isCheckable() and \
                            c.isChecked() != was:
                        c.click()
                        pump(args.settle)
                        rec["restored_check"] = True
                except RuntimeError:
                    pass
                restore(main, before, pg, example)
                report["clicks"].append(rec)
                done += 1
            print(f"  clicked {done:3d} on {pg.key}", flush=True)

        # The toolbars, likewise.
        for bar in main.findChildren(QtWidgets.QToolBar):
            for a in bar.actions():
                if a.isSeparator() or not a.isVisible() or \
                        not a.isEnabled():
                    continue
                label = _plain(a.text())
                rec = {"page": ["Toolbar"], "text": label, "kind": "action"}
                if _skip(label):
                    rec["effects"] = {"skipped": True}
                    report["clicks"].append(rec)
                    continue
                before = state(main, None, registry)
                was = a.isChecked() if a.isCheckable() else None
                faulthandler.dump_traceback_later(90, exit=True)
                a.trigger()
                pump(args.settle)
                after = state(main, None, registry)
                faulthandler.cancel_dump_traceback_later()
                rec["effects"] = effects(before, after)
                if was is not None and a.isChecked() != was:
                    a.trigger()
                    pump(args.settle)
                restore(main, before, None, example)
                report["clicks"].append(rec)

    # Secondary windows
    if args.windows:
        view_menu = None
        for a in main.menuBar().actions():
            if _plain(a.text()).replace("&", "").lower() == "view":
                view_menu = a.menu()
        for a in (view_menu.actions() if view_menu else []):
            label = _plain(a.text()).replace("&", "")
            if not label.endswith("…") and not label.endswith("..."):
                continue
            if "settings" in label.lower():
                continue
            before = _visible_windows()
            faulthandler.dump_traceback_later(120, exit=True)
            a.trigger()
            wait_for(lambda: len(_visible_windows()) > len(before), 15)
            pump(args.window_settle)
            faulthandler.cancel_dump_traceback_later()
            for k, (cls, title, win) in _visible_windows().items():
                if k in before:
                    continue
                slug = _slug(["window", label])
                try:
                    shot = APP.primaryScreen().grabWindow(
                        0, win.x(), win.y(), win.width(), win.height())
                    shot.save(os.path.join(shots, f"{slug}.png"))
                except Exception:                          # noqa: BLE001
                    win.grab().save(os.path.join(shots, f"{slug}.png"))
                ctrls = [c for c in win.findChildren(QtWidgets.QWidget)
                         if isinstance(c, _interactive_types())
                         and not _is_internal(c) and c.isVisibleTo(win)]
                tabs = []
                for tw in win.findChildren(QtWidgets.QTabWidget):
                    tabs.append([_label_of_tab(tw.tabText(i))
                                 for i in range(tw.count())])
                report["windows"].append({
                    "menu": label, "class": cls, "title": title,
                    "size": [win.width(), win.height()],
                    "tabs": tabs,
                    "controls": [_describe(c) for c in ctrls],
                    "shot": f"{slug}.png"})
                try:
                    win.close()
                    win.deleteLater()
                except Exception:                          # noqa: BLE001
                    pass
            pump(300)

    # The File and Help menus' dialogs, the start screen and the Learn menu.
    if args.dialogs:
        say("opening the menus' dialogs")
        for a in main.menuBar().actions():
            top = _plain(a.text()).replace("&", "")
            if top.lower() not in ("file", "help") or a.menu() is None:
                continue
            for act in a.menu().actions():
                label = _plain(act.text()).replace("&", "")
                if act.isSeparator() or not label or _skip(label):
                    continue
                if label.lower().startswith(("new", "open", "save", "export",
                                             "import", "open the example")):
                    continue        # file pickers: recorded by the click pass
                before = state(main, None, registry)
                faulthandler.dump_traceback_later(90, exit=True)
                act.trigger()
                pump(600)
                faulthandler.cancel_dump_traceback_later()
                after = state(main, None, registry)
                report["clicks"].append({"page": ["Menu", top],
                                         "text": label, "kind": "menu",
                                         "effects": effects(before, after)})
                restore(main, before, None, example)
        try:
            from src import learn_flow
            learn_flow.open_learn_menu(main)
        except Exception as exc:                           # noqa: BLE001
            sys.stderr.write(f"[surface] learn menu: {exc}\n")
        pump(300)

    report["dialogs"] = CAPTURE["records"]
    report["dialog_opens"] = CAPTURE["seen"]
    report["errors"] = LOG["errors"]
    return report


def summarise(report: dict) -> str:
    pages = report["pages"]
    lines = []
    m = report["meta"]
    lines.append(f"window {m['size'][0]}x{m['size'][1]}, font {m['font']} "
                 f"{m['font_px']}px, map ready={m['map_ready']}, "
                 f"boot {m['boot_s']}s, example plants="
                 f"{m.get('example_plants')}")
    ch = report["chrome"]
    lines.append(f"menus: {len(ch['menus'])} items; toolbar: "
                 f"{len(ch['toolbar'])} items; first-step bar: "
                 f"{len(ch['first_step_bar'])} buttons")
    lines.append(f"pages: {len(pages)} (max depth "
                 f"{max(p['depth'] for p in pages)})")
    total = 0
    for p in pages:
        n = len(p["controls"])
        total += n
        below = sum(1 for c in p["controls"] if c.get("below_fold"))
        dead = sum(1 for c in p["controls"]
                   if c["kind"] in ("button", "toolbutton") and c["wired"] == 0)
        lines.append(f"  {' › '.join(p['path']):45s} {n:3d} controls, "
                     f"{below:3d} below fold, {p['scroll']['screens']:4.1f} "
                     f"screens, {p['words']:4d} words, "
                     f"{len(p['prose']):2d} prose, {dead} unwired buttons")
    lines.append(f"controls on pages: {total}")
    if report["clicks"]:
        none = [c for c in report["clicks"] if not c.get("effects")]
        lines.append(f"clicked: {len(report['clicks'])}; no visible effect: "
                     f"{len(none)}; errors: {len(report['errors'])}")
    for d in report.get("dialogs", []):
        lines.append(f"  dialog {d['class']} '{d['title']}': "
                     f"{len(d['controls'])} controls, {d['words']} words")
    if report["windows"]:
        for w in report["windows"]:
            lines.append(f"  window {w['menu']}: {len(w['controls'])} "
                         f"controls, tabs {w['tabs']}")
    return "\n".join(lines)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--size", default="1366x768",
                    help="window size, WxH (default 1366x768)")
    ap.add_argument("--font", default="Liberation Sans",
                    help="sans-serif family to measure in (default "
                         "Liberation Sans, Arial's metrics)")
    ap.add_argument("--no-example", dest="example", action="store_false",
                    help="walk the empty app instead of the worked example")
    ap.add_argument("--click", action="store_true",
                    help="click every enabled button and record its effect")
    ap.add_argument("--windows", action="store_true",
                    help="open the View menu's windows and inventory them")
    ap.add_argument("--dialogs", action="store_true",
                    help="show, photograph and inventory each dialog reached "
                         "(by the click pass and the File/Help menus)")
    ap.add_argument("--settle", type=int, default=350,
                    help="ms to let a click's effects land (default 350)")
    ap.add_argument("--window-settle", type=int, default=4000,
                    help="ms to let a window load (default 4000)")
    a = ap.parse_args(argv)
    a.size = tuple(int(v) for v in a.size.lower().split("x"))
    a.out = os.path.abspath(a.out)
    return a


if __name__ == "__main__":
    args = parse_args()
    _sandbox(args.font)
    os.makedirs(args.out, exist_ok=True)
    try:
        rep = main_run(args)
    except BaseException:                                  # noqa: BLE001
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(2)
    with open(os.path.join(args.out, "inventory.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=str)
    print(summarise(rep), flush=True)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
