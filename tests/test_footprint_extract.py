"""
tests/test_footprint_extract.py

V1.53 — the footprint-extraction abstraction. The shipped default is a stub
(no SAM / whiteboxtools / GDAL), so it must import cleanly and raise a clear
NotImplementedError until a real backend is registered.
"""

import unittest

import src.footprint_extract as fe


class TestExtractorStub(unittest.TestCase):

    def setUp(self):
        fe._extractor = None        # ensure a clean registry per test

    def test_default_is_not_available(self):
        self.assertFalse(fe.extraction_available())

    def test_get_extractor_returns_stub(self):
        ex = fe.get_extractor()
        self.assertIsInstance(ex, fe.NotImplementedExtractor)

    def test_stub_raises_not_implemented(self):
        ex = fe.get_extractor()
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
