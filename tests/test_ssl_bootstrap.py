"""
tests/test_ssl_bootstrap.py

Coverage for src/ssl_bootstrap.py — the startup CA-bundle wiring that keeps
https fetches working on macOS and in frozen builds (plant photos,
elevation, Edmonton contours, OSM import). All branches are exercised by
patching env vars / module internals; no real network or certificate state
is touched, and the process env is snapshotted and restored.
"""

import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.ssl_bootstrap as sb  # noqa: E402


class TestEnsureCaBundle(unittest.TestCase):

    def setUp(self):
        self._saved = {k: os.environ.get(k)
                       for k in ("SSL_CERT_FILE", "SSL_CERT_DIR")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_respects_existing_ssl_cert_file(self):
        os.environ["SSL_CERT_FILE"] = "/somewhere/custom.pem"
        self.assertEqual(sb.ensure_ca_bundle(), "/somewhere/custom.pem")
        self.assertEqual(os.environ["SSL_CERT_FILE"], "/somewhere/custom.pem")

    def test_respects_existing_ssl_cert_dir(self):
        os.environ["SSL_CERT_DIR"] = "/somewhere/certs"
        self.assertIsNone(sb.ensure_ca_bundle())
        self.assertNotIn("SSL_CERT_FILE", os.environ)

    def test_noop_when_system_bundle_exists(self):
        with mock.patch.object(sb, "_default_verify_paths_exist",
                               return_value=True):
            self.assertIsNone(sb.ensure_ca_bundle())
        self.assertNotIn("SSL_CERT_FILE", os.environ)

    def test_points_at_certifi_when_system_bundle_missing(self):
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as f:
            pem = f.name
        self.addCleanup(os.unlink, pem)
        fake = types.ModuleType("certifi")
        fake.where = lambda: pem
        with mock.patch.object(sb, "_default_verify_paths_exist",
                               return_value=False), \
             mock.patch.dict(sys.modules, {"certifi": fake}):
            self.assertEqual(sb.ensure_ca_bundle(), pem)
            self.assertEqual(os.environ["SSL_CERT_FILE"], pem)

    def test_noop_when_certifi_unavailable(self):
        # A None entry in sys.modules makes `import certifi` raise
        # ImportError — the bootstrap must degrade to a no-op.
        with mock.patch.object(sb, "_default_verify_paths_exist",
                               return_value=False), \
             mock.patch.dict(sys.modules, {"certifi": None}):
            self.assertIsNone(sb.ensure_ca_bundle())
        self.assertNotIn("SSL_CERT_FILE", os.environ)

    def test_noop_when_certifi_bundle_file_missing(self):
        fake = types.ModuleType("certifi")
        fake.where = lambda: "/nonexistent/cacert.pem"
        with mock.patch.object(sb, "_default_verify_paths_exist",
                               return_value=False), \
             mock.patch.dict(sys.modules, {"certifi": fake}):
            self.assertIsNone(sb.ensure_ca_bundle())
        self.assertNotIn("SSL_CERT_FILE", os.environ)


if __name__ == "__main__":
    unittest.main()
