"""
src/controllers/ — Per-concern controllers extracted from MainWindow.

Each controller owns a coherent slice of app.py's former 3,900-line
``MainWindow`` god-class (update-flow, mode-switching, map-event routing,
persistence, …). MainWindow holds them via composition and keeps thin
shim methods so the public surface used by tests / signals / menus
doesn't change.

Why composition (not a Mixin or inheritance):

- The Chunk 4 split of plant_panel.py taught us that mixin extractions
  risk MRO surprises with QWidget bases; composition has none of that.
- Controllers can be unit-tested by instantiating them with a fake
  ``main`` (a SimpleNamespace with the few attrs they read). Chunk 6
  will lean on that for the Qt-free agent surface.
- The shim pattern (``MainWindow._foo`` → ``self._controller.foo``)
  keeps QAction / signal connections in ``_build_menu`` /
  ``_connect_signals`` working without churn.

Add a controller here when MainWindow grows past ~50 methods again.
"""
