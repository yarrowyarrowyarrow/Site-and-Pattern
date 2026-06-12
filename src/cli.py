"""
cli.py — Command-line interface for PermaDesign's headless operations.

A thin argparse shell over the Qt-free scripting facade
(:mod:`src.permadesign_api`). Every subcommand is a few lines around an
API call, so the CLI never duplicates domain logic. Run either as::

    python -m src.cli <subcommand> ...
    permadesign <subcommand> ...        # once installed (see pyproject.toml)

Subcommands:
    query             search the plant catalogue
    list-communities  list seeded plant communities (polycultures)
    list-structures   list habitat structures
    analyze           score a saved project's habitat value
    export-catalogue  write the plant catalogue to a .docx
    validate-data     check the shipped seed JSON for errors

Most subcommands accept ``--json`` for machine-readable output (handy for
agents and scripts). The process exit code is non-zero on failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from src.errors import PermaDesignError


# ── Subcommand handlers ─────────────────────────────────────────────────────
# Each takes the parsed args namespace and returns a process exit code.

def _cmd_query(args) -> int:
    from src.permadesign_api import query_plants
    filters = {}
    if args.text:
        filters["query"] = args.text
    if args.type:
        filters["plant_type"] = args.type
    if args.zone is not None:
        filters["zone"] = args.zone
    if args.native:
        filters["native_only"] = True
    if args.pollinator:
        filters["pollinator_only"] = True
    if args.host:
        filters["host_plant_only"] = True
    if args.keystone:
        filters["keystone_only"] = True
    if args.bird_food:
        filters["bird_food_only"] = True
    if args.ecoregion:
        filters["ab_ecoregion"] = args.ecoregion

    results = query_plants(**filters)
    if args.limit:
        results = results[: args.limit]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if not results:
            print("No plants matched.")
            return 0
        for p in results:
            native = "AB" if p.get("native_to_alberta") else "  "
            print(f"  {p['id']:>4}  [{native}]  {p.get('common_name', '?')}"
                  f"  ({p.get('plant_type', '?')})")
        print(f"\n{len(results)} plant(s).")
    return 0


def _cmd_list_communities(args) -> int:
    from src.permadesign_api import list_polycultures
    polys = list_polycultures()
    if args.json:
        print(json.dumps(polys, indent=2))
    else:
        for c in polys:
            print(f"  {c['id']:>4}  {c.get('name', '?')}")
        print(f"\n{len(polys)} community/-ies.")
    return 0


def _cmd_list_structures(args) -> int:
    from src.permadesign_api import list_structures
    structs = list_structures()
    if args.json:
        print(json.dumps(structs, indent=2))
    else:
        for s in structs:
            print(f"  {s.get('id', '?'):<18}  {s.get('name', '?')}")
        print(f"\n{len(structs)} structure(s).")
    return 0


def _cmd_analyze(args) -> int:
    from src.permadesign_api import Project, run_analysis
    project = Project.load(args.project)
    result = run_analysis(project)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    score = result["habitat_score"]
    if score is None:
        print("Nothing placed yet — no habitat score.")
    else:
        print(f"Habitat Value Score: {score['total']} / 100  ({score['grade']})")
        for name, comp in score["components"].items():
            print(f"  {name:<11} {comp['score']:>5} / {comp['max']}")
        print(f"  lepidoptera supported: {score['lepidoptera_supported']}")
    if result["warnings"]:
        print("\nWarnings:")
        for w in result["warnings"]:
            print(f"  - {w}")
    return 0


def _cmd_export_catalogue(args) -> int:
    from src.permadesign_api import export_plant_catalogue_docx
    path = export_plant_catalogue_docx(args.out)
    print(f"Wrote plant catalogue → {path}")
    return 0


def _cmd_generate(args) -> int:
    from src.llm_design import (
        generate_design, generate_design_offline, LLMClient,
    )
    from src.errors import LLMError
    site_config = None
    if args.lat is not None and args.lng is not None:
        site_config = {"latitude": args.lat, "longitude": args.lng}
    goals = args.goals or []

    budget = args.budget
    fauna_ids = args.fauna or []
    match_site = not args.no_match_site
    density = args.density
    if args.no_llm:
        print("Building design offline (no LLM) …")
        project = generate_design_offline(site_config=site_config, goals=goals,
                                          budget=budget, fauna_ids=fauna_ids,
                                          match_site=match_site, density=density)
    else:
        client = LLMClient(endpoint=args.endpoint or None, model=args.model or None)
        print(f"Generating design via {client.model} at {client.endpoint} …")
        try:
            project = generate_design(args.prompt, site_config=site_config,
                                      client=client, goals=goals, budget=budget,
                                      fauna_ids=fauna_ids, match_site=match_site,
                                      density=density)
        except LLMError as exc:
            # Unreachable model (or an unusable response): degrade to the
            # deterministic, goal-driven path rather than failing outright.
            print(f"LLM unavailable ({exc}); falling back to offline generation.",
                  file=sys.stderr)
            project = generate_design_offline(site_config=site_config,
                                              goals=goals, budget=budget,
                                              fauna_ids=fauna_ids,
                                              match_site=match_site,
                                              density=density)

    project.save(args.out)
    print(f"Wrote generated design ({len(project.placed_plants)} plant placements, "
          f"{len(project.structures)} structures) → {args.out}")
    for w in project.as_dict().get("properties", {}).get("generation_warnings", []):
        print(f"  note: {w}")
    return 0


def _cmd_validate_data(args) -> int:
    # Wraps src.data_quality.validate_all — the same check
    # scripts/check_plant_data.py runs. Exits non-zero on errors.
    from src.data_quality import validate_all, DATA_DIR
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


# ── Parser ───────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="permadesign",
        description="PermaDesign headless CLI (native-plant landscape design).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # query
    q = sub.add_parser("query", help="search the plant catalogue")
    q.add_argument("text", nargs="?", default="",
                   help="free-text match on name / uses")
    q.add_argument("--type", default="", help="plant_type filter (tree, shrub, …)")
    q.add_argument("--zone", type=int, default=None, help="hardiness zone")
    q.add_argument("--native", action="store_true", help="Alberta-native only")
    q.add_argument("--pollinator", action="store_true", help="pollinator plants only")
    q.add_argument("--host", action="store_true", help="larval-host plants only")
    q.add_argument("--keystone", action="store_true", help="keystone species only")
    q.add_argument("--bird-food", action="store_true", dest="bird_food",
                   help="bird-food plants only")
    q.add_argument("--ecoregion", default="", help="Alberta ecoregion tag")
    q.add_argument("--limit", type=int, default=0, help="cap result count")
    q.add_argument("--json", action="store_true", help="JSON output")
    q.set_defaults(func=_cmd_query)

    # list-communities
    lc = sub.add_parser("list-communities",
                        help="list seeded plant communities")
    lc.add_argument("--json", action="store_true", help="JSON output")
    lc.set_defaults(func=_cmd_list_communities)

    # list-structures
    ls = sub.add_parser("list-structures", help="list habitat structures")
    ls.add_argument("--json", action="store_true", help="JSON output")
    ls.set_defaults(func=_cmd_list_structures)

    # analyze
    an = sub.add_parser("analyze", help="score a saved project's habitat value")
    an.add_argument("project", help="path to a .perma.geojson project file")
    an.add_argument("--json", action="store_true", help="JSON output")
    an.set_defaults(func=_cmd_analyze)

    # export-catalogue
    ec = sub.add_parser("export-catalogue",
                        help="write the plant catalogue to a .docx")
    ec.add_argument("out", help="output .docx path")
    ec.set_defaults(func=_cmd_export_catalogue)

    # generate
    from src.design_goals import goal_keys
    ge = sub.add_parser("generate",
                        help="generate a design from goals / a prompt (local LLM, "
                             "with an offline fallback)")
    ge.add_argument("prompt", nargs="?", default="",
                    help="natural-language design brief "
                         "(optional when using --goal / --no-llm)")
    ge.add_argument("--out", required=True,
                    help="output .perma.geojson path")
    ge.add_argument("--goal", action="append", dest="goals", default=[],
                    choices=goal_keys(),
                    help="design goal, repeatable (choices: "
                         + ", ".join(goal_keys()) + ")")
    ge.add_argument("--no-llm", action="store_true", dest="no_llm",
                    help="skip the LLM; build deterministically from the goals "
                         "and seeded plant communities")
    ge.add_argument("--no-match-site", action="store_true", dest="no_match_site",
                    help="skip terrain micro-zoning (wet/dry/shaded placement); "
                         "still keeps the design inside the boundary")
    ge.add_argument("--density", choices=("sparse", "balanced", "full"),
                    default="balanced",
                    help="how much of the boundary to fill (default: balanced)")
    ge.add_argument("--lat", type=float, default=None, help="site latitude")
    ge.add_argument("--lng", type=float, default=None, help="site longitude")
    ge.add_argument("--budget", type=float, default=None,
                    help="approx. total plant budget in CAD; trims the priciest "
                         "plants to fit and prints an estimated cost")
    ge.add_argument("--fauna", action="append", type=int, default=[],
                    dest="fauna", metavar="FAUNA_ID",
                    help="fauna id to design for (repeatable); ensures plants "
                         "supporting that species are included")
    ge.add_argument("--endpoint", default="",
                    help="OpenAI-compatible base URL (default: local Ollama)")
    ge.add_argument("--model", default="",
                    help="model name (default: env / config / llama3.2)")
    ge.set_defaults(func=_cmd_generate)

    # validate-data
    vd = sub.add_parser("validate-data",
                        help="check the shipped seed JSON for errors")
    vd.add_argument("--quiet", action="store_true",
                    help="only print errors / warnings, not progress")
    vd.add_argument("--no-warnings", action="store_true",
                    help="suppress warning output (errors still shown)")
    vd.set_defaults(func=_cmd_validate_data)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point. Returns a process exit code (0 = success)."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except PermaDesignError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
