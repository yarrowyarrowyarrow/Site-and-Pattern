"""Stage 1 — get the sources onto disk.

    python -m tools.ecoregions.fetch          # everything reachable
    python -m tools.ecoregions.fetch --check  # report only, download nothing

Caches by filename and skips what is already present, so re-running is cheap
and a half-finished run resumes.

THE RULE THIS STAGE EXISTS TO ENFORCE
-------------------------------------------------------------------------------
On any failure it stops and reports the URL and the landing page. It never
substitutes a different dataset, never falls back to a lower resolution, and
never writes a placeholder. A boundary that came from somewhere other than the
source named in ``README.md`` is worse than no boundary, because the map does
not look any less confident for being wrong.

When a source is marked ``manual`` — the host is unreachable from this session —
the stage prints exactly what to download and where to put it, and exits
non-zero. That is a normal outcome here, not an error in the pipeline.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request

from tools.ecoregions.common import DATA, ensure_dirs
from tools.ecoregions.sources import ALL, BASEMAP, CLASSIFICATION, Source

_RAW = DATA / "raw"
#: raw.githubusercontent rate-limits bursts with 429/503. Four tries with a
#: growing pause clears it; more than that and something else is wrong.
_ATTEMPTS = 4


def _paths(source: Source) -> list:
    """Every file that must exist for this source to count as present."""
    out = [_RAW / source.filename]
    if source.siblings:
        stem = source.filename.rsplit(".", 1)[0]
        out += [_RAW / f"{stem}.{ext}" for ext in source.siblings]
    return out


def have(source: Source) -> bool:
    """True when the main file is on disk and not empty.

    Siblings are reported separately rather than folded in here: a shapefile
    missing its .dbf is a different problem from one that never downloaded, and
    saying so saves a confusing "file not found" from deep inside pyogrio.
    """
    main = _RAW / source.filename
    return main.exists() and main.stat().st_size > 0


def _missing_siblings(source: Source) -> list:
    return [p.name for p in _paths(source)[1:] if not p.exists()]


def _download(url: str, target) -> None:
    last = None
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(url, timeout=300) as response:
                if response.status != 200:
                    raise urllib.error.HTTPError(
                        url, response.status, "unexpected status", None, None)
                target.write_bytes(response.read())
            return
        except Exception as exc:                              # noqa: BLE001
            last = exc
            if attempt < _ATTEMPTS:
                time.sleep(attempt * 4)
    raise RuntimeError(f"{url}\n    {last}")


def fetch_one(source: Source) -> tuple:
    """``(ok, message)``. Never raises for an unreachable host."""
    if have(source):
        gaps = _missing_siblings(source)
        if gaps:
            return False, f"present but incomplete, missing {', '.join(gaps)}"
        return True, "cached"
    if source.manual or not source.url:
        return False, "manual"
    targets = _paths(source)
    try:
        _download(source.url, targets[0])
        if source.siblings:
            stem = source.url.rsplit(".", 1)[0]
            for ext, target in zip(source.siblings, targets[1:]):
                _download(f"{stem}.{ext}", target)
    except RuntimeError as exc:
        for target in targets:                                # no half files
            target.unlink(missing_ok=True)
        return False, f"download failed\n    {exc}"
    size = targets[0].stat().st_size / 1e6
    return True, f"downloaded, {size:.1f} MB"


def _manual_instructions(pending: list) -> str:
    lines = [
        "",
        "=" * 74,
        "  THESE MUST BE DOWNLOADED BY HAND",
        "=" * 74,
        "",
        "  Their hosts are not reachable from this session (the egress proxy",
        "  answers 403 to CONNECT for everything except GitHub and PyPI). They",
        "  are ordinary public open-data downloads from any normal connection.",
        "",
        f"  Put each file in:  {_RAW}",
        "",
    ]
    for source in pending:
        lines.append(f"  {source.key}")
        lines.append(f"      what     : {source.what}")
        lines.append(f"      save as  : {source.filename}")
        if source.siblings:
            stem = source.filename.rsplit(".", 1)[0]
            lines.append("      plus     : " + ", ".join(
                f"{stem}.{ext}" for ext in source.siblings))
        if source.url:
            lines.append(f"      direct   : {source.url}")
        if source.service:
            lines.append("      NOT A FILE - this is a live ArcGIS service.")
            lines.append(f"      service  : {source.service}")
            lines.append("      get it with:")
            lines.append(f"          python -m tools.ecoregions.arcgis "
                         f"{source.service}")
            lines.append(f"          python -m tools.ecoregions.arcgis "
                         f"{source.service} \\")
            lines.append(f"              --layer <id> --out "
                         f"tools/ecoregions/data/raw/{source.filename}")
        lines.append(f"      landing  : {source.landing}")
        lines.append(f"      publisher: {source.publisher}")
        lines.append(f"      licence  : {source.licence}")
        lines.append("")
    lines += [
        "  The direct links were correct when this table was written. Portals",
        "  move files constantly; if one 404s, go to the landing page and take",
        "  the current link from there, then update tools/ecoregions/sources.py",
        "  so the next run does not repeat the search.",
        "",
        "  Then run this again. It will skip everything already downloaded.",
        "=" * 74,
        "",
    ]
    return "\n".join(lines)


def run(*, check_only: bool = False) -> int:
    ensure_dirs()
    print(f"Sources -> {_RAW}\n")
    pending, failed = [], []
    for group, name in ((BASEMAP, "basemap"), (CLASSIFICATION, "classification")):
        print(f"  {name}:")
        for source in group:
            if check_only:
                ok, note = have(source), "present" if have(source) else "absent"
            else:
                ok, note = fetch_one(source)
            print(f"    {'ok  ' if ok else 'MISS'}  {source.key:16} {note}")
            if ok:
                continue
            (pending if (source.manual or not source.url) else failed).append(
                source)
        print()

    if failed:
        print("These should have downloaded and did not. Nothing has been")
        print("substituted; fix the source or the network and run again:")
        for source in failed:
            print(f"  {source.key}: {source.url}")
            print(f"      landing page: {source.landing}")
        return 2
    if pending:
        print(_manual_instructions(pending))
        return 1
    print("All sources present.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="report what is present, download nothing")
    args = parser.parse_args(argv)
    return run(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
