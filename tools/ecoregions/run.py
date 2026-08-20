"""Run the whole pipeline, stopping at the first stage that fails.

    python -m tools.ecoregions.run
    python -m tools.ecoregions.run --from 3        # resume at harmonize

Every stage writes its intermediate to ``out/``, so a run is resumable and each
stage is separately inspectable. Stopping rather than continuing is deliberate:
stage 4's failures are blocking, and a render produced from a build that failed
validation is exactly the artefact this pipeline exists to stop being made.
"""

from __future__ import annotations

import argparse
import sys

STAGES = (
    ("fetch", "download the sources"),
    ("inspect_schema", "report the real field names"),
    ("harmonize", "ELC geometry, Alberta subregions as an attribute"),
    ("validate", "point probes and structural checks (blocking)"),
    ("render", "the publication map"),
    ("export", "GeoPackage and GeoJSON"),
)


def run(start: int = 1, stop: int = len(STAGES)) -> int:
    import importlib

    for number, (name, what) in enumerate(STAGES, start=1):
        if not start <= number <= stop:
            continue
        print()
        print("=" * 74)
        print(f"  STAGE {number} - {name}: {what}")
        print("=" * 74)
        module = importlib.import_module(f"tools.ecoregions.{name}")
        code = module.main([])
        if code:
            print()
            print(f"Stage {number} ({name}) exited {code}. Stopping here.")
            print("Nothing downstream has run, so nothing downstream is stale.")
            return code
    print()
    print("All requested stages completed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--from", dest="start", type=int, default=1,
                        metavar="N", help="first stage to run (1-6)")
    parser.add_argument("--to", dest="stop", type=int, default=len(STAGES),
                        metavar="N", help="last stage to run (1-6)")
    args = parser.parse_args(argv)
    return run(args.start, args.stop)


if __name__ == "__main__":
    sys.exit(main())
