"""
errors.py — Typed exception hierarchy for the PermaDesign scripting API.

The GUI historically reported failures with ``QMessageBox`` pop-ups
deep inside controller code. That's invisible to a headless caller. The
scripting facade in :mod:`src.permadesign_api` instead raises these
typed exceptions so an AI agent, a CLI, or an MCP tool gets a structured
failure it can branch on (and a non-zero exit code, once the CLI lands
in Chunk 7).

All of them subclass :class:`PermaDesignError`, so callers that just want
"did the API call fail?" can catch the base class.
"""

from __future__ import annotations


class PermaDesignError(Exception):
    """Base class for every error the scripting API raises."""


class ProjectError(PermaDesignError):
    """A project file couldn't be loaded, saved, or is malformed."""


class PlantNotFoundError(PermaDesignError):
    """A referenced plant id has no row in the plant database."""


class PolycultureNotFoundError(PermaDesignError):
    """A referenced polyculture / community id doesn't exist."""


class AnalysisError(PermaDesignError):
    """A design analysis (e.g. habitat score) couldn't be computed —
    usually because the plant database is unavailable."""


class ExportError(PermaDesignError):
    """An export (PDF / DOCX) failed or isn't available headlessly."""
