"""
tests/test_footprint_extract.py

V1.53 — the footprint-extraction abstraction. With numpy + shapely present the
built-in nDSM backend is offered automatically; without them get_extractor()
returns the NotImplemented stub (which raises a clear error). An explicitly
registered backend always wins.
"""

import unittest

import src.footprint_extract as fe

try:
    import numpy, shapely  # noqa: F401
    _HAVE_NDSM_DEPS = True
except ImportError:
    _HAVE_NDSM_DEPS = False


class TestExtractorDefault(unittest.TestCase):

    def setUp(self):
        fe._extractor = None        # ensure a clean registry per test

    def test_default_availability_tracks_deps(self):
        # nDSM backend is auto-offered iff its deps are importable.
        self.assertEqual(fe.extraction_available(), _HAVE_NDSM_DEPS)

    @unittest.skipIf(_HAVE_NDSM_DEPS, "nDSM deps present → real backend offered")
    def test_stub_when_no_deps(self):
        ex = fe.get_extractor()
        self.assertIsInstance(ex, fe.NotImplementedExtractor)
        with self.assertRaises(NotImplementedError):
            ex.extract_footprints("/tmp/whatever.tif")

    def test_stub_raises_not_implemented_directly(self):
        ex = fe.NotImplementedExtractor()
        with self.assertRaises(NotImplementedError):
            ex.extract_footprints("/tmp/whatever.tif")
        with self.assertRaises(NotImplementedError):
            ex.extract_with_heights("/tmp/whatever.tif")

    def test_register_backend(self):
        class _Fake:
            def extract_footprints(self, p):
                return [[(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)]]

            def extract_with_heights(self, p):
                return [([(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)], 5.0)]

        fe.set_extractor(_Fake())
        try:
            self.assertTrue(fe.extraction_available())
            rings = fe.get_extractor().extract_footprints("x")
            self.assertEqual(len(rings), 1)
        finally:
            fe._extractor = None


if __name__ == "__main__":
    unittest.main()
