"""
tests package — and the suite's offline guard (V2.38).

Measured: a full run made **771 live internet requests**.

    api.open-meteo.com                     465   llm_design._zone_context
                                                 fetching a real elevation grid
    inaturalist-open-data.s3.amazonaws.com 306   analysis_panel's photo warmer
                                                 downloading plant photographs
    archive-api.open-meteo.com               5   climate history

Not one test needed any of them. Every caller already degrades gracefully when
offline — that is the whole offline-first design — so the downloads bought
nothing and cost a slow, flaky suite that depends on somebody else's uptime and
burns a public API's quota on every run. A user running the suite on Windows
started getting ``HTTP 429 Too Many Requests`` back from Open-Meteo, which is
how this was found.

So the suite is offline by default. Anything reaching past the machine raises
``URLError``, which is exactly the shape of "no network" the app is written to
survive, so the code under test takes the same path a real offline user does.

**Still allowed**, because they are not the internet:

  * ``file://`` — several tests serve fixtures from a temp file this way
  * ``localhost`` / ``127.0.0.1`` — ``test_web_assets`` starts its own server

Set ``SITEANDPATTERN_ALLOW_NETWORK=1`` to lift the guard for a run, e.g. when
deliberately testing a fetcher against the real endpoint. Nothing in the suite
needs it today.

This lives in ``tests/__init__.py`` because ``unittest discover`` imports the
package before any test module, and there is no pytest conftest to hang it on.
"""

import os
import urllib.error
import urllib.request

_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _install_offline_guard() -> None:
    if os.environ.get("SITEANDPATTERN_ALLOW_NETWORK") == "1":
        return

    real_urlopen = urllib.request.urlopen

    def guarded(url, *args, **kwargs):
        full = url.full_url if hasattr(url, "full_url") else str(url)
        if full.startswith("file:"):
            return real_urlopen(url, *args, **kwargs)
        host = ""
        if "//" in full:
            host = full.split("//", 1)[1].split("/", 1)[0].split("@")[-1]
        if host.split(":")[0] in _ALLOWED_HOSTS:
            return real_urlopen(url, *args, **kwargs)
        raise urllib.error.URLError(
            f"offline: the test suite does not reach the network "
            f"({host or full!r}). Stub the fetcher, or set "
            f"SITEANDPATTERN_ALLOW_NETWORK=1 if you really mean it.")

    urllib.request.urlopen = guarded


_install_offline_guard()
