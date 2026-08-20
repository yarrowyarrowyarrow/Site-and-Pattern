"""Headless GLB asset build for Site & Pattern.

    blender --background --python scripts/blender/build_assets.py -- \
        --out html/assets/models [--only tree.spruce,fauna*] [--check]

Builds every archetype GLB (or the --only subset), enforces the triangle
budgets and naming conventions (build fails loudly on violation), exports
to --out, and writes manifest.json. --check builds and validates without
writing anything. Exit code propagates for release checklists.

Same code path as the Blender-MCP session (assetlib.build_all), so an
MCP-iterated look and a headless rebuild are identical.
"""

import argparse
import os
import sys
import traceback


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="build_assets.py")
    ap.add_argument("--out", default=None,
                    help="output dir for GLBs + manifest.json "
                         "(e.g. html/assets/models)")
    ap.add_argument("--only", default=None,
                    help="comma-separated keys / prefix* patterns")
    ap.add_argument("--check", action="store_true",
                    help="build + validate without writing files")
    args = ap.parse_args(argv)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from assetlib.build_all import build_all

    only = [s.strip() for s in args.only.split(",")] if args.only else None
    if not args.check and not args.out:
        ap.error("--out is required unless --check")

    summary = build_all(out_dir=args.out, only=only, check_only=args.check)
    total = 0
    for key in sorted(summary):
        units = summary[key]
        line = ", ".join(f"{u}={n}" for u, n in sorted(units.items()))
        total += sum(units.values())
        print(f"  {key:24s} {line}")
    print(f"built {len(summary)} assets, {total} triangles total"
          + (" (check only)" if args.check else f" -> {args.out}"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
