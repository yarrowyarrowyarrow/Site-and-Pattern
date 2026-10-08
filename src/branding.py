"""
src/branding.py — the app's display identity (V1.69 rebrand).

Single source of truth for the user-facing product name. The app was formerly
"PermaDesign"; with V1.69 the name users *see* becomes **Site & Pattern**, drawn
from the design-philosophy document (see ``docs/DESIGN_PHILOSOPHY.md``).

What deliberately keeps the legacy ``PermaDesign`` identifier — so existing
installs keep their data and the update path keeps working — is everything the
user does NOT see:

  * the GitHub repo + the releases URL (``controllers/update_flow.py``);
  * the QSettings org/app name (``main.py``) that keys window geometry and the
    one-time legacy-recipe migration flag;
  * the on-disk database *filenames* (``permadesign.db`` …);
  * the frozen scripting / MCP API symbols (``src/permadesign_api.py``,
    ``src/mcp_server.py``) snapshotted by ``tests/test_architecture_guard.py``.

The on-disk data *folder* IS renamed (PermaDesign → Site & Pattern) with a
one-time migration — see ``src/user_paths.py``.

Kept dependency-free (no Qt) so any layer can import the name.
"""

from __future__ import annotations

# What the user sees.
APP_NAME = "Site & Pattern"
APP_TAGLINE = "Native Habitat Designer"
APP_TITLE = f"{APP_NAME} — {APP_TAGLINE}"


def window_title(document: str | None = None, *, version: str | None) -> str:
    """The main window's title (F231, V3.16): the name, the release it is
    running, and the open design, or the tagline before one is named.
    ``window_title(version=None)`` is ``APP_TITLE``.

    The version is there so a screenshot says which copy it came from, and so
    an update can be checked at a glance: the words come from the program, the
    number from the ``version.txt`` installed beside it. It is a required
    keyword so a new caller cannot leave it out by accident; pass
    ``app_version.running_version()``."""
    name = f"{APP_NAME} {version}" if version else APP_NAME
    return f"{name} — {document or APP_TAGLINE}"


# Per-user data-folder names (see ``src/user_paths.py``). The folder is migrated
# from the legacy name to the new one on first launch after the rebrand.
DATA_DIR_NAME = "Site & Pattern"
LEGACY_DATA_DIR_NAME = "PermaDesign"
