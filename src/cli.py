"""
cli.py — Command-line interface for PermaDesign (no Qt required).

Usage:
    python -m permadesign search-plants [--zone N] [--sun EXPOSURE] [--type TYPE]
                                        [--water NEEDS] [--native] [--edible]
                                        [--pollinator] [--nfixer] [--perennial]
                                        [--query TEXT]

    python -m permadesign design SITE_CONFIG_JSON [-o OUTPUT_PATH]

    python -m permadesign validate PROJECT_JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_search_plants(args: argparse.Namespace) -> None:
    from src.bootstrap import bootstrap_db
    from src.design_api import DesignGenerator

    bootstrap_db()
    gen = DesignGenerator()
    kwargs: dict = {}
    if args.query:
        kwargs["query"] = args.query
    if args.type:
        kwargs["plant_type"] = args.type
    if args.sun:
        kwargs["sun_req"] = args.sun
    if args.water:
        kwargs["water_needs"] = args.water
    if args.zone is not None:
        kwargs["zone"] = args.zone
    if args.native:
        kwargs["native_only"] = True
    if args.edible:
        kwargs["edible_only"] = True
    if args.pollinator:
        kwargs["pollinator_only"] = True
    if args.nfixer:
        kwargs["nfixer_only"] = True
    if args.perennial:
        kwargs["perennial_only"] = True

    results = gen.search_plants(**kwargs)
    json.dump(results, sys.stdout, indent=2, default=str)
    print()


def _cmd_design(args: argparse.Namespace) -> None:
    from src.bootstrap import bootstrap_db
    from src.design_api import DesignGenerator
    import src.project as project_io

    bootstrap_db()

    site_path = Path(args.config)
    if not site_path.exists():
        sys.exit(f"Error: site config not found: {site_path}")

    with site_path.open(encoding="utf-8") as f:
        site_config = json.load(f)

    gen = DesignGenerator(site_config)

    # If the site config contains pre-placed plants or guilds, apply them.
    for plant in site_config.get("plants", []):
        gen.add_plant(plant["plant_id"], plant["lat"], plant["lng"],
                      quantity=plant.get("quantity", 1))

    for guild in site_config.get("guilds", []):
        gen.add_guild(guild["guild_id"], guild["lat"], guild["lng"])

    project = gen.get_project()

    if args.output:
        out_path = Path(args.output)
        project_io.save_project(project, str(out_path))
        print(f"Saved to {out_path}", file=sys.stderr)
    else:
        json.dump(project, sys.stdout, indent=2, default=str)
        print()


def _cmd_validate(args: argparse.Namespace) -> None:
    from src.bootstrap import bootstrap_db
    from src.design_api import DesignGenerator
    import src.project as project_io

    bootstrap_db()

    proj_path = Path(args.project)
    if not proj_path.exists():
        sys.exit(f"Error: project file not found: {proj_path}")

    with proj_path.open(encoding="utf-8") as f:
        project = json.load(f)

    gen = DesignGenerator()
    gen.project = project

    issues = gen.validate()
    if not issues:
        print(json.dumps({"ok": True, "issues": []}))
    else:
        json.dump({"ok": False, "issues": issues}, sys.stdout, indent=2)
        print()
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="permadesign",
        description="PermaDesign headless CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # search-plants
    sp = sub.add_parser("search-plants", help="Search the plant catalogue")
    sp.add_argument("--query",     default="")
    sp.add_argument("--type",      default="", metavar="PLANT_TYPE")
    sp.add_argument("--sun",       default="", metavar="EXPOSURE")
    sp.add_argument("--water",     default="", metavar="NEEDS")
    sp.add_argument("--zone",      type=int,   default=None)
    sp.add_argument("--native",    action="store_true")
    sp.add_argument("--edible",    action="store_true")
    sp.add_argument("--pollinator",action="store_true")
    sp.add_argument("--nfixer",    action="store_true")
    sp.add_argument("--perennial", action="store_true")

    # design
    dp = sub.add_parser("design", help="Generate a design from a site config JSON")
    dp.add_argument("config", metavar="SITE_CONFIG_JSON")
    dp.add_argument("-o", "--output", default=None, metavar="OUTPUT_PATH")

    # validate
    vp = sub.add_parser("validate", help="Validate a saved project file")
    vp.add_argument("project", metavar="PROJECT_JSON")

    args = parser.parse_args()

    if args.command == "search-plants":
        _cmd_search_plants(args)
    elif args.command == "design":
        _cmd_design(args)
    elif args.command == "validate":
        _cmd_validate(args)


if __name__ == "__main__":
    main()
