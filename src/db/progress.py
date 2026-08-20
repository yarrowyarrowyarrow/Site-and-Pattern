"""
progress.py — the species-discovery ledger and the learner's place (V2.43).

Design principle P5 (perception is constructed — make the invisible visible)
and P13 (a native planting has to be loved to survive) — see
docs/DESIGN_PHILOSOPHY.md.

Learn mode needs one thing before any of the rest of it is worth building: a
reason to look closely. This is that reason, at its cheapest — a record of
every species the person has actually found, and a count of how much of the
catalogue is still dark.

Two tables, both schema v62, both **user-authored**:

  ``discovered_species``  what you have found, and how
  ``learn_state``         where you are up to (companion choice, last sandbox,
                          lesson position) — a small key/value store

**Neither is ever wiped by the reseed.** That is the single most important fact
about this module and it is enforced by a test: a schema bump rebuilds the
catalogue from the shipped JSON, and rebuilding the catalogue must not delete
the record of what somebody found in it. This is the same reasoning that keeps
user polycultures (schema v46) and user photographs (v55) alive across an
upgrade, with one simplification — those tables need an ``origin`` column
because they hold a mix of shipped and authored rows, and these hold nothing
shipped at all.

Keyed by ``scientific_name``, never by id. Plant and fauna ids are not stable
across a reseed; a ledger keyed on them would come back after an upgrade
pointing at different species, which is worse than losing it outright because
nothing would look wrong.

Nothing here raises. A ledger is an ornament on the real work: if the DB is
locked or the table is missing, the honest result is "nothing discovered yet",
not a traceback in front of somebody trying to learn about bees.
"""

from __future__ import annotations

import datetime
import sqlite3
from typing import Iterable, Optional

#: How a species came to be discovered. Kept as a closed vocabulary so a later
#: achievement can distinguish "walked past it in a scene" from "went out and
#: identified it" — the P11 distinction that makes an outdoor achievement
#: mean something.
HOW_INSPECTED = "inspected"    # clicked in a 3D scene
HOW_PLANTED = "planted"        # placed it yourself
HOW_CAUGHT = "caught"          # reserved for the net
HOW_DIRECTORY = "directory"    # opened its page in the Field Guide
_HOWS = frozenset({HOW_INSPECTED, HOW_PLANTED, HOW_CAUGHT, HOW_DIRECTORY})

#: The two halves of the catalogue a learner can work through.
PLANT = "plant"
FAUNA = "fauna"
_KINDS = frozenset({PLANT, FAUNA})


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")


def _conn() -> Optional[sqlite3.Connection]:
    """A connection, or ``None`` if the database cannot be opened.

    Imported lazily and defensively: this module is called from paint-adjacent
    code (a start screen counting discoveries) and must never be the reason a
    window fails to open.
    """
    try:
        from src.db.plants import get_connection
        return get_connection()
    except Exception:                                      # noqa: BLE001
        return None


# ── Writing ──────────────────────────────────────────────────────────────────

def record_seen(kind: str, scientific_name: str, *,
                how: str = HOW_INSPECTED, where: str = "") -> bool:
    """Record that the user has found this species. Returns ``True`` the
    **first** time a species is seen, so a caller can say "new!" without
    querying first.

    Re-recording an existing species bumps ``times_seen`` and the last-seen
    stamp but leaves ``first_seen_at`` and ``how`` alone — the first sighting
    is the one worth keeping, and an upgrade from "inspected" to "caught" would
    quietly rewrite history the person might be proud of.
    """
    name = (scientific_name or "").strip()
    if kind not in _KINDS or not name:
        return False
    if how not in _HOWS:
        how = HOW_INSPECTED
    conn = _conn()
    if conn is None:
        return False
    try:
        with conn:
            cur = conn.execute(
                "UPDATE discovered_species "
                "   SET times_seen = times_seen + 1, last_seen_at = ? "
                " WHERE kind = ? AND scientific_name = ?",
                (_now(), kind, name))
            if cur.rowcount:
                return False
            conn.execute(
                "INSERT INTO discovered_species "
                "  (kind, scientific_name, first_seen_at, last_seen_at, "
                "   how, times_seen, where_seen) "
                "VALUES (?, ?, ?, ?, ?, 1, ?)",
                (kind, name, _now(), _now(), how, where or ""))
        return True
    except Exception:                                      # noqa: BLE001
        return False
    finally:
        try:
            conn.close()
        except Exception:                                  # noqa: BLE001
            pass


def record_many(kind: str, names: Iterable[str], *,
                how: str = HOW_INSPECTED, where: str = "") -> list[str]:
    """Record a batch; return the names that were newly discovered.

    Used when a scene is built — everything visible in a landscape you walked
    into counts as seen — so it must stay cheap enough to call on every scene
    push.
    """
    fresh: list[str] = []
    for n in names or ():
        if record_seen(kind, n, how=how, where=where):
            fresh.append(n)
    return fresh


# ── Reading ──────────────────────────────────────────────────────────────────

def discovered(kind: str = "") -> set[str]:
    """The set of scientific names discovered, for one kind or for both."""
    conn = _conn()
    if conn is None:
        return set()
    try:
        if kind in _KINDS:
            rows = conn.execute(
                "SELECT scientific_name FROM discovered_species WHERE kind = ?",
                (kind,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT scientific_name FROM discovered_species").fetchall()
        return {r[0] for r in rows}
    except Exception:                                      # noqa: BLE001
        return set()
    finally:
        try:
            conn.close()
        except Exception:                                  # noqa: BLE001
            pass


def is_discovered(kind: str, scientific_name: str) -> bool:
    conn = _conn()
    if conn is None:
        return False
    try:
        row = conn.execute(
            "SELECT 1 FROM discovered_species "
            " WHERE kind = ? AND scientific_name = ?",
            (kind, (scientific_name or "").strip())).fetchone()
        return row is not None
    except Exception:                                      # noqa: BLE001
        return False
    finally:
        try:
            conn.close()
        except Exception:                                  # noqa: BLE001
            pass


def coverage() -> dict:
    """``{plants_seen, plants_total, fauna_seen, fauna_total, seen, total}``.

    The totals come from the live catalogue rather than a stored constant, so
    the fraction stays honest when the catalogue grows — a "37 of 576" that
    silently means "of the 480 we shipped last year" is exactly the kind of
    false precision P9 rules out.
    """
    out = {"plants_seen": 0, "plants_total": 0,
           "fauna_seen": 0, "fauna_total": 0, "seen": 0, "total": 0}
    conn = _conn()
    if conn is None:
        return out
    try:
        for kind, seen_key, total_key, table in (
                (PLANT, "plants_seen", "plants_total", "plants"),
                (FAUNA, "fauna_seen", "fauna_total", "fauna")):
            try:
                out[seen_key] = conn.execute(
                    "SELECT COUNT(*) FROM discovered_species WHERE kind = ?",
                    (kind,)).fetchone()[0]
                out[total_key] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except Exception:                              # noqa: BLE001
                pass
        out["seen"] = out["plants_seen"] + out["fauna_seen"]
        out["total"] = out["plants_total"] + out["fauna_total"]
        return out
    except Exception:                                      # noqa: BLE001
        return out
    finally:
        try:
            conn.close()
        except Exception:                                  # noqa: BLE001
            pass


def coverage_line() -> str:
    """One phrase for the boot menu. ``""`` when there is nothing to say —
    a start screen must never fail to open over a count."""
    c = coverage()
    if not c["total"]:
        return ""
    if not c["seen"]:
        return f"{c['total']} species to find"
    return f"{c['seen']} of {c['total']} species discovered"


# ── Where the learner is up to ───────────────────────────────────────────────

def get_state(key: str, default: str = "") -> str:
    conn = _conn()
    if conn is None:
        return default
    try:
        row = conn.execute("SELECT value FROM learn_state WHERE key = ?",
                           (key,)).fetchone()
        return row[0] if row else default
    except Exception:                                      # noqa: BLE001
        return default
    finally:
        try:
            conn.close()
        except Exception:                                  # noqa: BLE001
            pass


def set_state(key: str, value: str) -> bool:
    conn = _conn()
    if conn is None:
        return False
    try:
        with conn:
            conn.execute(
                "INSERT INTO learn_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)))
        return True
    except Exception:                                      # noqa: BLE001
        return False
    finally:
        try:
            conn.close()
        except Exception:                                  # noqa: BLE001
            pass


#: Keys used by :func:`get_state` / :func:`set_state`. Named constants rather
#: than string literals at the call sites, because a typo in a key is a silent
#: reset of somebody's progress.
LAST_COMMUNITY = "last_community"       # the sandbox you were last in
COMPANION = "companion"                 # reserved for F85
