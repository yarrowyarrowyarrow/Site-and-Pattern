"""
tests/test_ssl_bootstrap.py

Coverage for src/ssl_bootstrap.py — the startup CA-bundle wiring that keeps
https fetches working on macOS and in frozen builds (plant photos,
elevation, Edmonton contours, OSM import, address search). All branches are
exercised by patching env vars / sys.platform / module internals; no real
network or certificate state is touched, and the process env is
snapshotted and restored.
"""

import io
import contextlib
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.ssl_bootstrap as sb  # noqa: E402


def _fake_certifi(pem_path: str) -> types.ModuleType:
    fake = types.ModuleType("certifi")
    fake.where = lambda: pem_path
    return fake


class TestEnsureCaBundle(unittest.TestCase):

    def setUp(self):
        self._saved = {k: os.environ.get(k)
                       for k in ("SSL_CERT_FILE", "SSL_CERT_DIR")}
        for k in self._saved:
            os.environ.pop(k, None)
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as f:
            self.pem = f.name
        self.addCleanup(os.unlink, self.pem)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_respects_existing_ssl_cert_file(self):
        os.environ["SSL_CERT_FILE"] = "/somewhere/custom.pem"
        self.assertEqual(sb.ensure_ca_bundle(verbose=False),
                         "/somewhere/custom.pem")
        self.assertEqual(os.environ["SSL_CERT_FILE"], "/somewhere/custom.pem")

    def test_respects_existing_ssl_cert_dir(self):
        os.environ["SSL_CERT_DIR"] = "/somewhere/certs"
        self.assertIsNone(sb.ensure_ca_bundle(verbose=False))
        self.assertNotIn("SSL_CERT_FILE", os.environ)

    def test_noop_on_linux_when_store_has_certs(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch.object(sb, "_context_has_ca_certs", return_value=True):
            self.assertIsNone(sb.ensure_ca_bundle(verbose=False))
        self.assertNotIn("SSL_CERT_FILE", os.environ)

    def test_linux_with_empty_store_uses_certifi(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch.object(sb, "_context_has_ca_certs", return_value=False), \
             mock.patch.dict(sys.modules, {"certifi": _fake_certifi(self.pem)}):
            self.assertEqual(sb.ensure_ca_bundle(verbose=False), self.pem)
            self.assertEqual(os.environ["SSL_CERT_FILE"], self.pem)

    def test_darwin_uses_certifi_even_when_store_has_certs(self):
        # A present-but-stale Homebrew bundle passes the store check yet
        # still fails verification — on macOS certifi must win regardless.
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch.object(sb, "_context_has_ca_certs", return_value=True), \
             mock.patch.dict(sys.modules, {"certifi": _fake_certifi(self.pem)}):
            self.assertEqual(sb.ensure_ca_bundle(verbose=False), self.pem)
            self.assertEqual(os.environ["SSL_CERT_FILE"], self.pem)

    def test_warns_when_certifi_unavailable_and_store_empty(self):
        # A None entry in sys.modules makes `import certifi` raise
        # ImportError — the bootstrap must degrade to a warning, not crash.
        err = io.StringIO()
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch.object(sb, "_context_has_ca_certs", return_value=False), \
             mock.patch.dict(sys.modules, {"certifi": None}), \
             contextlib.redirect_stderr(err):
            self.assertIsNone(sb.ensure_ca_bundle())
        self.assertIn("certifi", err.getvalue())
        self.assertNotIn("SSL_CERT_FILE", os.environ)

    def test_noop_when_certifi_bundle_file_missing(self):
        fake = _fake_certifi("/nonexistent/cacert.pem")
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch.dict(sys.modules, {"certifi": fake}):
            self.assertIsNone(sb.ensure_ca_bundle(verbose=False))
        self.assertNotIn("SSL_CERT_FILE", os.environ)

    def test_verbose_logs_the_chosen_bundle(self):
        err = io.StringIO()
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch.dict(sys.modules, {"certifi": _fake_certifi(self.pem)}), \
             contextlib.redirect_stderr(err):
            self.assertEqual(sb.ensure_ca_bundle(), self.pem)
        self.assertIn(self.pem, err.getvalue())


if __name__ == "__main__":
    unittest.main()
