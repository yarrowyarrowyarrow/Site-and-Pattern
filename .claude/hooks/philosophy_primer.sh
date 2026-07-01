#!/usr/bin/env bash
# SessionStart hook — inject the Site & Pattern design-philosophy primer into the session so
# the spirit of the philosophy is woven through every session's work, even before CLAUDE.md is
# consulted. The full source of truth is docs/DESIGN_PHILOSOPHY.md (the twelve principles); this
# is the deliberately short reminder, not a re-statement of the whole doc.
#
# Wired in .claude/settings.json as a SessionStart hook. Its stdout is added to session context.
set -uo pipefail

cat <<'PRIMER'
[Site & Pattern — design-philosophy primer]
This project is guided by TWELVE design principles (see docs/DESIGN_PHILOSOPHY.md, with the
feature map in docs/PHILOSOPHY_ROADMAP.md and the bibliography in docs/REFERENCES.md). Let them
shape design decisions: encode generative rules over fixed layouts; model relationships over
objects; design the trajectory over time, not the install day; make invisible ecology visible;
keep the "grown, not designed" feel; ship ranges and confidence, never false precision. Strongly
-aligned modules carry a `Design principle P#` anchor — keep that weave intact.

HARD RULE — Principle 12 (Indigenous knowledge is honoured through relationship, not
extraction): never incorporate Indigenous knowledge, land-management practices, plant-use
traditions, or design frameworks into the data model, seed content, recommendations, or UI
without explicit FREE, PRIOR, AND INFORMED CONSENT from the relevant communities. Until then,
any reference is DIRECTIONAL ONLY. If a task pushes that way, stop and check with the user.
PRIMER

# Confirm the doc<->code weave is intact (pure file-read test; no Qt/DB). One status line only.
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
if command -v python >/dev/null 2>&1; then
  PY=python
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=""
fi
if [ -n "$PY" ]; then
  if ( cd "$ROOT" && "$PY" -m unittest discover -s tests -p test_philosophy.py ) >/dev/null 2>&1; then
    echo "[philosophy] weave intact — tests/test_philosophy passes."
  else
    echo "[philosophy] WARNING: tests/test_philosophy is failing — the doc<->code weave has drifted; reconcile docs/DESIGN_PHILOSOPHY.md and the P# anchors before relying on them."
  fi
fi
