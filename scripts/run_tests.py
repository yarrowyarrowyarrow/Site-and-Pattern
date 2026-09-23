#!/usr/bin/env python3
"""
scripts/run_tests.py — run the suite and report what it actually did.

    python scripts/run_tests.py                                  # everything
    python scripts/run_tests.py --exclude tests.test_undo_redo   # what CI runs
    python scripts/run_tests.py tests.test_plant_panel_smoke     # one module
    python scripts/run_tests.py --max-skips 30                   # fail on silent skips

Why not ``python -m unittest discover -s tests -t .``
------------------------------------------------------
That command is still correct at a desk, where a person reads the summary. It
is unfit to be the only thing a CI job looks at, for two reasons ``CLAUDE.md``
already records:

* **With PyQt6-WebEngine installed the process exits 139 at teardown, after
  the summary** (``Release of profile requested but WebEnginePage still not
  deleted``). It fires even when zero tests run, so it is WebEngine shutdown and
  not test code -- but a green run then has a crash for an exit code. This
  script takes the verdict from the ``TestResult`` and leaves with
  ``os._exit`` before interpreter teardown gets the chance.
* **A skipped test is a pass to CI.** Without the Qt runtime ~156 widget tests
  skip; without WebEngine another 47; without rasterio/pyproj 42. That is how
  PDF export raised ``NameError`` on every call for four minor versions behind
  a green suite, and how a widget test went red in V2.80 and stayed red through
  V2.82 while every session that ran it lacked PyQt6. ``--max-skips`` turns a
  lost dependency into a failure, and every skip reason is printed with its
  count so a new one reads as a fact in the log rather than a mystery.

Modules are loaded by dotted name (``tests.test_x``), which imports the
``tests`` package first, so the offline guard in ``tests/__init__.py`` installs
exactly as it does under ``-t .``.
"""

from __future__ import annotations

import argparse
import collections
import faulthandler
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def all_test_modules() -> list[str]:
    """Every ``tests/test_*.py`` as a dotted module name, sorted."""
    names = sorted(f[:-3] for f in os.listdir(os.path.join(ROOT, "tests"))
                   if f.startswith("test_") and f.endswith(".py"))
    return [f"tests.{n}" for n in names]


def skip_summary(skipped) -> list[tuple[int, str]]:
    """``(count, reason)`` pairs, most frequent first."""
    counts = collections.Counter(reason.strip().splitlines()[0]
                                 if reason.strip() else "(no reason given)"
                                 for _test, reason in skipped)
    return sorted(((n, r) for r, n in counts.items()), key=lambda x: (-x[0], x[1]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("modules", nargs="*",
                    help="dotted module names (default: every tests/test_*.py)")
    ap.add_argument("--exclude", action="append", default=[],
                    help="a dotted module name to leave out; repeatable")
    ap.add_argument("--max-skips", type=int, default=None,
                    help="fail the run when more tests than this are skipped")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    os.chdir(ROOT)
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    faulthandler.enable()

    names = args.modules or all_test_modules()
    unknown = [m for m in args.exclude if m not in names]
    if unknown:
        # An exclusion that matches nothing is a typo, and a typo here quietly
        # runs a module somebody meant to keep out -- or, reversed, hides that
        # the module was renamed and is no longer excluded from anything.
        print(f"--exclude names no module in this run: {', '.join(unknown)}",
              file=sys.stderr)
        return 2
    names = [m for m in names if m not in set(args.exclude)]

    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(
        verbosity=2 if args.verbose else 1, stream=sys.stderr).run(suite)

    out = sys.stderr
    print("", file=out)
    print(f"modules: {len(names)} run"
          + (f", {len(args.exclude)} excluded ({', '.join(args.exclude)})"
             if args.exclude else ""), file=out)
    print(f"tests:   {result.testsRun} run, {len(result.failures)} failed, "
          f"{len(result.errors)} errors, {len(result.skipped)} skipped", file=out)
    if result.skipped:
        print("skipped, by reason:", file=out)
        for n, reason in skip_summary(result.skipped):
            print(f"  {n:4d}  {reason}", file=out)

    ok = result.wasSuccessful()
    if args.max_skips is not None and len(result.skipped) > args.max_skips:
        print(f"FAIL: {len(result.skipped)} tests skipped, more than the "
              f"{args.max_skips} allowed -- a dependency is probably missing, "
              "and a skipped test proves nothing.", file=out)
        ok = False
    print("RESULT: " + ("OK" if ok else "FAILED"), file=out)
    return 0 if ok else 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    # Not sys.exit: see the module docstring. Qt WebEngine's shutdown segfaults
    # in a GPU-less process after every test has already reported, and the
    # verdict above is the one that counts.
    os._exit(code)
