"""
tests/test_plan_my_yard_probe.py — Plan My Yard keeps the probe's rules (PY-11,
V3.28; docs/homeowner/07-plan-my-yard.md §5).

Runs ``scripts/probe_plan_my_yard.py``'s cases and fails on any rule: plants in
a drawn bed (with an outline or without one) and none on a lawn, path or
patio; *Fill it now* at 65% cover or
more and *Over two or three summers* at 35-45%; a conversion zone covered as
fully as the open yard. About forty seconds.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

try:
    import shapely  # noqa: F401
    _HAVE_SHAPELY = True
except ImportError:                                        # pragma: no cover
    _HAVE_SHAPELY = False


@unittest.skipUnless(_HAVE_SHAPELY, "shapely not installed")
class ThePlanKeepsTheProbesRules(unittest.TestCase):

    def test_every_rule(self):
        import probe_plan_my_yard as probe
        probe._db()
        self.assertEqual(probe.failures(probe.measure()), [])


if __name__ == "__main__":
    unittest.main()
