"""
import_usda.py — Import native-species data from the USDA PLANTS database CSV.

This script updates the `native_to_alberta` flag in the local PermaDesign
database by cross-referencing scientific names against the USDA PLANTS
database.  It can work with either:

  1. A pre-downloaded CSV file (pass path as argument), or
  2. An automatic download from the USDA PLANTS API.

The USDA CSV is expected to have at least a "Scientific Name" column.
Plants whose scientific name (genus + species) matches an entry in the CSV
will have their `native_to_alberta` flag set to 1.

Usage:
    python -m src.db.import_usda                          # auto-download AB native list
    python -m src.db.import_usda path/to/usda_plants.csv  # use local CSV file

The USDA PLANTS database is at: https://plants.usda.gov
To manually download:
  1. Go to https://plants.usda.gov/home/plantProfile
  2. Use Advanced Search → State/Province: Alberta
  3. Filter: Native → Download CSV
"""

import csv
import io
import os
import sqlite3
import sys
import urllib.request
import urllib.parse
from typing import Optional


# ── Paths ─────────────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))


def _normalize_sciname(name: Optional[str]) -> str:
    """
    Normalise a scientific name to 'Genus species' (lowercase, no
    subspecies/variety/author suffixes).
    """
    if not name:
        return ""
    parts = name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0].lower()} {parts[1].lower()}"
    return parts[0].lower() if parts else ""


def _read_csv(path: str) -> set[str]:
    """
    Read a USDA PLANTS CSV and return a set of normalised scientific names.
    Tries common column names: 'Scientific Name', 'scientific_name',
    'Scientific Name with Author', 'sciname'.
    """
    names: set[str] = set()
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        # Detect delimiter
        sample = f.read(2048)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t|")
        reader = csv.DictReader(f, dialect=dialect)

        # Find the scientific name column
        sci_col = None
        candidates = [
            "Scientific Name", "scientific_name", "sciname",
            "Scientific Name with Author", "ScientificName",
            "scientific name", "SCIENTIFIC NAME",
        ]
        if reader.fieldnames:
            for c in candidates:
                if c in reader.fieldnames:
                    sci_col = c
                    break
            # Fallback: any column containing 'scien'
            if sci_col is None:
                for col in reader.fieldnames:
                    if "scien" in col.lower():
                        sci_col = col
                        break

        if sci_col is None:
            print(f"ERROR: Could not find a scientific-name column in {path}")
            print(f"  Available columns: {reader.fieldnames}")
            return names

        for row in reader:
            raw = row.get(sci_col, "")
            normed = _normalize_sciname(raw)
            if normed:
                names.add(normed)

    return names


def _download_usda_alberta_csv() -> Optional[str]:
    """
    Attempt to download Alberta native plant data from the USDA PLANTS API.
    Returns path to a temporary CSV file, or None on failure.
    """
    # The USDA PLANTS database provides a CSV download endpoint.
    # This URL fetches plants native to Alberta (province code AB).
    url = (
        "https://plants.usda.gov/assets/docs/CompletePLANTSList/plantlst.txt"
    )
    print(f"Attempting to download USDA PLANTS list from:\n  {url}")
    print("(This is a large file ~5 MB, may take a moment...)")

    tmp_path = os.path.join(_PROJECT_ROOT, "data", "usda_plants_raw.txt")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "PermaDesign/1.0 (permaculture design tool)"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
        with open(tmp_path, "wb") as f:
            f.write(data)
        print(f"Downloaded {len(data):,} bytes to {tmp_path}")
        return tmp_path
    except Exception as exc:
        print(f"Download failed: {exc}")
        print("\nTo use this script, manually download the CSV from:")
        print("  https://plants.usda.gov → Advanced Search → Alberta → Native → Download")
        print("Then run:  python -m src.db.import_usda path/to/downloaded.csv")
        return None


def import_from_csv(csv_path: str, dry_run: bool = False) -> dict:
    """
    Cross-reference USDA CSV against the local plant database and update
    the native_to_alberta flag.

    Returns a summary dict: {matched, updated, not_found, total_usda}.
    """
    usda_names = _read_csv(csv_path)
    if not usda_names:
        return {"matched": 0, "updated": 0, "not_found": [], "total_usda": 0}

    print(f"Loaded {len(usda_names):,} scientific names from USDA CSV")

    # Connect to local DB
    sys.path.insert(0, _PROJECT_ROOT)
    from src.db.plants import get_connection

    conn = get_connection()
    try:
        plants = conn.execute(
            "SELECT id, common_name, scientific_name, native_to_alberta FROM plants"
        ).fetchall()

        matched = 0
        updated = 0
        not_found = []

        for p in plants:
            local_name = _normalize_sciname(p["scientific_name"])
            if not local_name:
                continue

            if local_name in usda_names:
                matched += 1
                if not p["native_to_alberta"]:
                    if not dry_run:
                        conn.execute(
                            "UPDATE plants SET native_to_alberta = 1 WHERE id = ?",
                            (p["id"],)
                        )
                    updated += 1
                    print(f"  ✓ {p['common_name']} ({p['scientific_name']}) → native")
                else:
                    print(f"  = {p['common_name']} ({p['scientific_name']}) already native")
            else:
                not_found.append(
                    f"{p['common_name']} ({p['scientific_name']})"
                )

        if not dry_run:
            conn.commit()

        return {
            "matched": matched,
            "updated": updated,
            "not_found": not_found,
            "total_usda": len(usda_names),
        }
    finally:
        conn.close()


def main():
    """CLI entry point."""
    csv_path = None

    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        if not os.path.isfile(csv_path):
            print(f"ERROR: File not found: {csv_path}")
            sys.exit(1)
    else:
        # Try auto-download
        csv_path = _download_usda_alberta_csv()
        if csv_path is None:
            sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("\n=== DRY RUN — no changes will be written ===\n")

    result = import_from_csv(csv_path, dry_run=dry_run)

    print(f"\n{'='*50}")
    print(f"USDA names loaded:  {result['total_usda']:,}")
    print(f"Local plants matched: {result['matched']}")
    print(f"Newly flagged native: {result['updated']}")
    if result["not_found"]:
        print(f"\nNot found in USDA data ({len(result['not_found'])} plants):")
        for name in result["not_found"]:
            print(f"  · {name}")

    if dry_run:
        print("\n(Dry run — no changes saved. Remove --dry-run to apply.)")


if __name__ == "__main__":
    main()
