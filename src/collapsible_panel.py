"""
collapsible_panel.py — the side panel's collapse strip (``CollapsibleSidebar``).

The module once held ``CollapsiblePanel`` too, a header that hid a section of a
panel. Its toggle was ``NoFocus`` by design, which is how a keyboard user lost
the Placement section, and nothing has used it since V2.98 moved placing into
the bar over the map. It was deleted in V3.02 (F195). The strip below takes
focus and says what it does; Ctrl+\\ does the same from anywhere.

Persistent collapse state is keyed by a caller-supplied panel_id; the state is
read from / written to the shared user-settings JSON file via src.settings.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal


# Shared settings key namespace so ad-hoc widgets can persist their state
# without bothering the caller. The settings module already manages its
# JSON file at ~/.permadesign_config.json.
_PANEL_SETTINGS_KEY = "ui_collapsed_panels"


def _load_collapsed_state(panel_id: str) -> Optional[bool]:
    """Return True if the named panel is collapsed (per saved settings)."""
    if not panel_id:
        return None
    try:
        from src.settings import load_config
        cfg = load_config()
        m = cfg.get(_PANEL_SETTINGS_KEY) or {}
        if panel_id in m:
            return bool(m[panel_id])
    except Exception:
        pass
    return None


def _save_collapsed_state(panel_id: str, collapsed: bool) -> None:
    if not panel_id:
        return
    try:
        from src.settings import load_config, save_config
        cfg = load_config()
        m = cfg.get(_PANEL_SETTINGS_KEY) or {}
        m[panel_id] = bool(collapsed)
        cfg[_PANEL_SETTINGS_KEY] = m
        save_config(cfg)
    except Exception:
        pass


class CollapsibleSidebar(QWidget):
    """Sidebar wrapper that horizontally collapses to a thin chevron strip.

    Different from CollapsiblePanel: the body is hidden and the wrapper
    itself shrinks to a fixed width so the central widget can reclaim
    horizontal space. Used to make the entire side QTabWidget collapsible
    in MainWindow.
    """

    toggled = pyqtSignal(bool)

    COLLAPSED_WIDTH = 28

    def __init__(self, title: str, panel_id: str = "",
                 expanded: bool = True, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._panel_id = panel_id
        self._content: Optional[QWidget] = None
        self._saved_min_w = 0
        self._saved_max_w = 16777215

        saved = _load_collapsed_state(panel_id)
        if saved is not None:
            expanded = not saved
        self._expanded = expanded

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Vertical chevron strip on the left edge of the sidebar.
        self._chev = QToolButton(self)
        # Use a brighter, larger glyph when collapsed so users can find the
        # re-open affordance — the side panel hosts critical UI (Contours,
        # Plants, etc.) and a faint 22 px strip on the right edge has been
        # easy to miss.
        self._chev.setText("‹" if expanded else "›")
        self._chev.setToolTip(
            f"Collapse {title}" if expanded else f"Expand {title} (Ctrl+\\)"
        )
        self._chev.setStyleSheet(
            "QToolButton { color: #a5d6a7; background: #1b3a1b; "
            "border-left: 1px solid #2e4a2e; padding: 6px 2px; "
            "font-size: 18px; font-weight: bold; }"
            "QToolButton:hover { background: #2e7d32; color: #ffffff; }"
        )
        self._chev.setSizePolicy(QSizePolicy.Policy.Fixed,
                                  QSizePolicy.Policy.Expanding)
        self._chev.setFixedWidth(self.COLLAPSED_WIDTH)
        self._chev.setCursor(Qt.CursorShape.PointingHandCursor)
        # Reachable by Tab, and named for what pressing it does (V3.02).
        self._chev.setAccessibleName(
            f"Collapse {title}" if expanded else f"Expand {title}")
        self._chev.clicked.connect(self._on_toggle)
        root.addWidget(self._chev)

        self._content_holder = QVBoxLayout()
        self._content_holder.setContentsMargins(0, 0, 0, 0)
        self._content_holder.setSpacing(0)
        root.addLayout(self._content_holder, 1)

        self._title = title

    # ── Public API ────────────────────────────────────────────────────────

    def set_content(self, widget: QWidget) -> None:
        if self._content is not None:
            self._content_holder.removeWidget(self._content)
            self._content.setParent(None)
        self._content = widget
        widget.setParent(self)
        self._content_holder.addWidget(widget)
        widget.setVisible(self._expanded)

    def expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, *, persist: bool = True) -> None:
        if expanded == self._expanded:
            return
        self._expanded = expanded
        if self._content is not None:
            self._content.setVisible(expanded)
        if expanded:
            # Restore previous min/max so the sidebar can size normally.
            self.setMinimumWidth(self._saved_min_w)
            self.setMaximumWidth(self._saved_max_w)
        else:
            # Snapshot current limits so we can restore them on expand.
            self._saved_min_w = self.minimumWidth()
            self._saved_max_w = self.maximumWidth()
            self.setMaximumWidth(self.COLLAPSED_WIDTH)
            self.setMinimumWidth(self.COLLAPSED_WIDTH)
        self._chev.setText("‹" if expanded else "›")
        self._chev.setToolTip(
            f"Collapse {self._title}" if expanded else f"Expand {self._title}"
        )
        self._chev.setAccessibleName(
            f"Collapse {self._title}" if expanded else f"Expand {self._title}")
        if persist:
            _save_collapsed_state(self._panel_id, not expanded)
        self.toggled.emit(expanded)

    # ── Internals ─────────────────────────────────────────────────────────

    def _on_toggle(self):
        self.set_expanded(not self._expanded)
