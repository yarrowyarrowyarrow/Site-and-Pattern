"""
resources.py — locate bundled, read-only data files in both a normal source
checkout and a PyInstaller-frozen build.

In a source checkout the project root is the parent of ``src/``.  In a
PyInstaller bundle the files live under ``sys._MEIPASS`` (the spec's ``datas``
entries preserve the same relative layout: ``data/``, ``html/``,
``src/db/schema.sql``).

Always resolve runtime data through :func:`resource_path` rather than
``__file__``-relative joins — a module's ``__file__`` is unreliable once it is
collected into the frozen PYZ archive, which is what produced the historic
"No such file or directory: schema.sql" crash on installed builds.
"""

import os
import sys


def resource_path(*relative_parts: str) -> str:
    """Absolute path to a bundled resource, given its path relative to the
    project root.

    Example::

        resource_path("data", "plants_master.json")
        resource_path("src", "db", "schema.sql")
    """
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS                       # PyInstaller bundle root
    else:
        # repo root == parent of this file's directory (src/)
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *relative_parts)
