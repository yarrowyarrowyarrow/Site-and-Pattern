"""
tests/test_photo_warm.py — the background species-photo cache warmer (V2.29).

src/photo_warm.py is Qt-free and takes its rows and its resolver by injection, so
everything here runs offline with no database and no network: the module's whole
job is to be a nicety that can never sink the app, and that is what these check.
"""

import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.photo_warm import (PhotoWarmer, catalogue_photo_rows,   # noqa: E402
                            photo_rows)


def _row(url, attribution="© Someone", license_str="CC BY 4.0"):
    return {"image_url": url, "image_attribution": attribution,
            "image_license": license_str}


class PhotoRowsTest(unittest.TestCase):
    def test_rows_without_a_photo_are_dropped(self):
        rows = photo_rows([_row("https://a/1.jpg"), _row(""), {}, _row("   ")])
        self.assertEqual([r[0] for r in rows], ["https://a/1.jpg"])

    def test_a_shared_photo_is_fetched_once(self):
        """Several species map to one observation photo; fetching it twice is
        pure waste against a free host."""
        rows = photo_rows([_row("https://a/1.jpg"), _row("https://a/1.jpg"),
                           _row("https://a/2.jpg")])
        self.assertEqual([r[0] for r in rows], ["https://a/1.jpg",
                                                "https://a/2.jpg"])

    def test_attribution_travels_with_the_url(self):
        rows = photo_rows([_row("https://a/1.jpg", "© P", "CC0")])
        self.assertEqual(rows[0], ("https://a/1.jpg", "© P", "CC0"))

    def test_catalogue_rows_survive_a_broken_query(self):
        def boom():
            raise RuntimeError("db down")
        rows = catalogue_photo_rows(
            queries=(boom, lambda: [_row("https://a/1.jpg")]))
        self.assertEqual([r[0] for r in rows], ["https://a/1.jpg"])


class WarmerTest(unittest.TestCase):
    def _items(self, n):
        return [(f"https://a/{i}.jpg", "© P", "CC0") for i in range(n)]

    def test_warms_every_item(self):
        seen = []
        w = PhotoWarmer(self._items(4), delay_s=0,
                        resolve=lambda u, a, l: seen.append(u) or "/tmp/x")
        result = w.run()
        self.assertEqual(len(seen), 4)
        self.assertEqual(result["cached"], 4)
        self.assertEqual(result["failed"], 0)

    def test_a_failing_fetch_is_counted_and_the_walk_continues(self):
        """One unreachable photo must not end the warm — the next species'
        might be fine, and the whole thing retries on the next run anyway."""
        def flaky(url, _a, _l):
            if url.endswith("1.jpg"):
                raise OSError("connection reset")
            return "/tmp/x" if url.endswith("2.jpg") else None
        w = PhotoWarmer(self._items(4), delay_s=0, resolve=flaky)
        result = w.run()
        self.assertEqual(result["total"], 4)
        self.assertEqual(result["cached"], 1)
        self.assertEqual(result["failed"], 3)
        self.assertFalse(result["cancelled"])

    def test_cancel_stops_between_items(self):
        w = None
        seen = []

        def resolve(url, _a, _l):
            seen.append(url)
            if len(seen) == 2:
                w.cancel()
            return "/tmp/x"
        w = PhotoWarmer(self._items(10), delay_s=0, resolve=resolve)
        result = w.run()
        self.assertEqual(len(seen), 2)
        self.assertTrue(result["cancelled"])

    def test_cancel_does_not_wait_out_the_courtesy_delay(self):
        """Closing the 3D window must not block for the inter-request gap
        times the number of photos left."""
        w = PhotoWarmer(self._items(50), delay_s=30,
                        resolve=lambda _u, _a, _l: "/tmp/x")
        threading.Timer(0.05, w.cancel).start()
        start = time.monotonic()
        w.run()
        self.assertLess(time.monotonic() - start, 5.0)

    def test_progress_reports_whether_each_photo_landed(self):
        calls = []
        PhotoWarmer(self._items(3), delay_s=0,
                    resolve=lambda u, _a, _l: None if u.endswith("1.jpg") else "/x",
                    on_progress=lambda d, t, ok: calls.append((d, t, ok))).run()
        self.assertEqual(calls, [(1, 3, True), (2, 3, False), (3, 3, True)])

    def test_a_raising_progress_callback_cannot_sink_the_warm(self):
        def boom(*_a):
            raise RuntimeError("ui gone")
        result = PhotoWarmer(self._items(3), delay_s=0, on_progress=boom,
                             resolve=lambda *_a: "/x").run()
        self.assertEqual(result["cached"], 3)

    def test_nothing_to_warm_is_not_an_error(self):
        self.assertEqual(PhotoWarmer([], delay_s=0).run(),
                         {"cached": 0, "failed": 0, "total": 0,
                          "cancelled": False})


if __name__ == "__main__":
    unittest.main()
