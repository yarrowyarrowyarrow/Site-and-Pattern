"""
check_fauna_data.py — what the wildlife data actually looks like right now.

Run from the project root, on any OS:

    python scripts/check_fauna_data.py

No arguments, no quoting, nothing to mistype. **That is the point.** The
`python -c "..."` one-liners this replaces do not survive being retyped: a
multi-line one handed over during V2.62 arrived in PowerShell as
``import get_conneciton c=get connection() for r in`` — the newlines
flattened into spaces, two typos, and `COUNT(*)` broke the quoting so the
shell tried to run `*` as a command. A file has none of those failure modes.

Reads the **live database**, not the seed JSON, so it answers the question a
person actually has: *did my install pick up the new data?* If the numbers
here look old, the reseed did not fire and `_SCHEMA_VERSION` is the thing to
check.
"""

from __future__ import annotations

import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    from src.db.plants import get_connection, _SCHEMA_VERSION

    conn = get_connection()
    try:
        def one(sql, *args):
            return conn.execute(sql, args).fetchone()[0]

        plants = one("SELECT COUNT(*) FROM plants")
        fauna = one("SELECT COUNT(*) FROM fauna")
        edges = one("SELECT COUNT(*) FROM plant_fauna")
        covered = one("SELECT COUNT(DISTINCT plant_id) FROM plant_fauna")
        photos = one("SELECT COUNT(*) FROM plant_photos")
        # `_schema_version`, with the leading underscore — the table is
        # private and `_get_schema_version` is the only reader. Guessing the
        # name without it printed "vNone" beside a perfectly current database.
        from src.db.plants import _get_schema_version
        stored = _get_schema_version(conn)

        print("=" * 62)
        print(f"  schema      v{stored}   (code expects v{_SCHEMA_VERSION})")
        if stored is not None and stored < _SCHEMA_VERSION:
            print("              ^^ OLDER THAN THE CODE — the reseed has not "
                  "run.\n                 Launch the app once, or delete the "
                  "DB to force it.")
        print(f"  plants      {plants}")
        print(f"  fauna       {fauna}")
        print(f"  edges       {edges}")
        print(f"  coverage    {covered} of {plants} plants have a wildlife "
              f"record ({100 * covered // max(1, plants)}%)")
        # Most of these are synthesized by `_seed_plant_photos` from the
        # `image_url` each plant already carried; only a couple are real rows
        # authored in `data/plant_photos.json`, so both numbers are shown.
        authored = one("SELECT COUNT(*) FROM plant_photos WHERE slot != ?",
                       "flower")
        print(f"  photos      {photos}  ({authored} in a slot other than "
              f"`flower`)")
        print("=" * 62)

        print("\nedges by relationship")
        for rel, n in sorted(conn.execute(
                "SELECT relationship, COUNT(*) FROM plant_fauna "
                "GROUP BY relationship").fetchall(), key=lambda r: -r[1]):
            print(f"  {n:6d}  {rel}")

        print("\nedges by source, top 12")
        rows = sorted(conn.execute(
            "SELECT source, COUNT(*) FROM plant_fauna GROUP BY source"
        ).fetchall(), key=lambda r: -r[1])
        for src, n in rows[:12]:
            print(f"  {n:6d}  {src or '(none)'}")
        if len(rows) > 12:
            print(f"          … and {len(rows) - 12} more sources")

        # The headline F128 number: how many edges name something better than
        # the aggregator. `globi` alone means "an aggregator has a record
        # somewhere"; anything else names a study, a collection or a book.
        aggregator = dict(rows).get("globi", 0)
        print(f"\n  {edges - aggregator} of {edges} edges cite something more "
              f"specific than the aggregator")

        print("\nfauna by taxon")
        for taxon, n in sorted(conn.execute(
                "SELECT taxon, COUNT(*) FROM fauna GROUP BY taxon"
        ).fetchall(), key=lambda r: -r[1]):
            print(f"  {n:6d}  {taxon}")

        orphans = one(
            "SELECT COUNT(*) FROM fauna f WHERE NOT EXISTS "
            "(SELECT 1 FROM plant_fauna pf WHERE pf.fauna_id = f.id)")
        if orphans:
            print(f"\n  {orphans} animals are connected to no plant")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
