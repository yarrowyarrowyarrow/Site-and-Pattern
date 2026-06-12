"""
check_plant_data.py — Validate shipped plant JSON before it ships.

Run from project root:
    python scripts/check_plant_data.py
    python scripts/check_plant_data.py --quiet      # only print errors

Exits 0 if all data files pass, non-zero otherwise. The validation
logic lives in ``src/data_quality.py`` so the unit-test wrapper at
``tests/test_data_quality.py`` can call ``validate_all()`` directly
without shelling out.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Run-from-project-root pattern matching scripts/export_plant_docx.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_quality import validate_all, DATA_DIR  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--quiet", action="store_true",
                   help="only print errors / warnings, not progress")
    p.add_argument("--no-warnings", action="store_true",
                   help="suppress warning output (errors still shown)")
    args = p.parse_args(argv)

    if not args.quiet:
        print(f"Validating plant data in {DATA_DIR}…")

    errors, warnings = validate_all()

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  x  {e}")

    if warnings and not args.no_warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  !  {w}")

    if errors:
        print(f"\n{len(errors)} error(s) — please fix before shipping.")
        return 1

    if not args.quiet:
        msg = "All plant data is clean."
        if warnings:
            msg += f" ({len(warnings)} warning(s) — data debt, not blocking.)"
        print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
