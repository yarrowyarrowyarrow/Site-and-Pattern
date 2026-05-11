"""
terrain_downloader.py — QThread worker that bulk-downloads the full
City of Edmonton LiDAR contour dataset into the local SQLite store.

If the live Socrata API can't be reached or its schema can't be
sniffed (the historical "Could not detect field names" error), the
worker falls back to importing a locally-bundled seed file at
``data/edmonton_contours.geojson`` (gzipped variants ``.geojson.gz``
and ``.json.gz`` also accepted). That seed is optional — when absent,
the worker reports the network error with an actionable hint.
"""

import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from PyQt6.QtCore import QObject, pyqtSignal

from src.terrain import (
    _EDM_RESOURCE,
    _USER_AGENT,
    _edm_detect_fields,
    _coerce_float,
    _flatten_geojson_lines,
    _http_get_json,
)
from src.terrain_store import TerrainStore


def _diag_fetch(url: str, timeout: float = 30.0) -> "tuple[bool, int | None, dict | list | None, str]":
    """Diagnostic HTTP GET that surfaces the *real* failure reason.

    ``_http_get_json`` swallows every exception and returns None, which
    is great for the silent-fallback case but useless when we need to
    figure out *why* the Edmonton download stalled. This helper does
    the same urllib call but returns a (ok, http_status, payload,
    error_text) tuple — caller can log the error_text to stderr and
    surface a short summary via the worker's ``progress`` signal.
    """
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None)
            body = resp.read().decode("utf-8")
            try:
                payload = json.loads(body)
            except ValueError as exc:
                dt = time.monotonic() - t0
                return False, status, None, (
                    f"JSON decode failed after {dt:.1f}s ({len(body)} bytes): {exc}"
                )
            dt = time.monotonic() - t0
            return True, status, payload, ""
    except urllib.error.HTTPError as exc:
        dt = time.monotonic() - t0
        return False, exc.code, None, f"HTTPError {exc.code} after {dt:.1f}s: {exc.reason}"
    except urllib.error.URLError as exc:
        dt = time.monotonic() - t0
        return False, None, None, f"URLError after {dt:.1f}s: {exc.reason}"
    except Exception as exc:
        dt = time.monotonic() - t0
        return False, None, None, f"{type(exc).__name__} after {dt:.1f}s: {exc}"


_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_SEED_CANDIDATES = (
    os.path.join(_PROJECT_ROOT, "data", "edmonton_contours.geojson"),
    os.path.join(_PROJECT_ROOT, "data", "edmonton_contours.geojson.gz"),
    os.path.join(_PROJECT_ROOT, "data", "edmonton_contours.json"),
    os.path.join(_PROJECT_ROOT, "data", "edmonton_contours.json.gz"),
)


def _find_local_seed() -> "str | None":
    for path in _SEED_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def _load_seed(path: str) -> "dict | None":
    """Load a GeoJSON FeatureCollection from a (gzipped) local file."""
    try:
        if path.endswith(".gz"):
            with gzip.open(path, "rb") as f:
                return json.loads(f.read().decode("utf-8"))
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


class EdmontonDownloadWorker(QObject):
    """
    Downloads all pages of the Edmonton contour dataset and writes them to
    TerrainStore.  Move to a QThread before calling run().

    Signals:
      progress(features_stored, page_num, status_text)
      finished(total_stored)
      error(message)
    """

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int)
    error    = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def _diag_log(self, msg: str) -> None:
        """Print to stderr and surface via the progress signal so the
        user sees diagnostic output both in the terminal and in the UI."""
        try:
            print(f"[edmonton-dl] {msg}", file=sys.stderr, flush=True)
        except Exception:
            pass
        try:
            self.progress.emit(0, 0, msg)
        except Exception:
            pass

    def run(self) -> None:
        store = TerrainStore()
        store.clear_edmonton()

        # Phase 5 / Phase 2 diagnostic instrumentation — capture the
        # actual network behaviour before guessing at a fix.
        self._diag_log("Detecting Edmonton dataset fields…")
        t_detect = time.monotonic()
        elev_field, geom_field = _edm_detect_fields()
        self._diag_log(
            f"Field detection took {time.monotonic() - t_detect:.1f}s "
            f"→ elev={elev_field!r} geom={geom_field!r}"
        )
        if not elev_field or not geom_field:
            # Run the diagnostic fetch against the views-metadata URL so
            # we can show the user *why* detection failed.
            meta_url = (
                f"https://data.edmonton.ca/api/views/"
                f"{_EDM_RESOURCE.rsplit('/', 1)[-1].split('.')[0]}.json"
            )
            ok, status, payload, err = _diag_fetch(meta_url, timeout=15)
            self._diag_log(
                f"Probe metadata: ok={ok} status={status} err={err or '-'}"
            )
            # Dump the parsed column list so we can see what
            # _edm_detect_via_metadata had to work with. The previous
            # probe round confirmed the network is fine; this round
            # tells us *why* no number column was matched.
            if ok and isinstance(payload, dict):
                cols = payload.get("columns")
                if isinstance(cols, list):
                    self._diag_log(f"Metadata columns ({len(cols)}):")
                    for col in cols:
                        if isinstance(col, dict):
                            fname = col.get("fieldName") or col.get("name") or "?"
                            dtype = col.get("dataTypeName") or "?"
                            self._diag_log(f"  • {fname!r}  type={dtype!r}")
                else:
                    self._diag_log(
                        f"Metadata payload has no 'columns' key "
                        f"(top-level keys={sorted((payload or {}).keys())[:8]})"
                    )

            sample_url = f"{_EDM_RESOURCE}?$limit=1"
            ok2, status2, payload2, err2 = _diag_fetch(sample_url, timeout=15)
            feat_count = len(
                (payload2 or {}).get("features", [])
                if isinstance(payload2, dict) else []
            )
            self._diag_log(
                f"Probe sample row: ok={ok2} status={status2} "
                f"err={err2 or '-'} features={feat_count}"
            )
            # Dump the first feature's properties so we can see what
            # _edm_detect_via_sample saw. Show the value's Python type
            # too — Socrata sometimes returns numbers as strings, which
            # would still coerce; if every value is None / non-numeric
            # that explains why the second-pass fallback also failed.
            if ok2 and feat_count > 0:
                feat0 = payload2["features"][0]
                props = (feat0.get("properties") or {}) if isinstance(feat0, dict) else {}
                self._diag_log(f"Sample feature properties ({len(props)}):")
                for k, v in props.items():
                    self._diag_log(
                        f"  • {k!r} = {v!r}  ({type(v).__name__})"
                    )
                # Also dump the geometry shape and the *length* of the
                # first coordinate tuple. For Edmonton's "3D contour
                # lines" datasets the elevation may be embedded as the
                # Z component of every vertex (`[lng, lat, z]`) rather
                # than living in a separate column — which is a perfect
                # fit for an empty-properties response. Knowing whether
                # we're looking at a 2D or 3D coord settles it in one
                # screenshot.
                geom = (feat0.get("geometry") or {}) if isinstance(feat0, dict) else {}
                gtype = geom.get("type") if isinstance(geom, dict) else None
                coords = geom.get("coordinates") if isinstance(geom, dict) else None
                first_pt = None
                # Walk into the nested coordinate arrays to grab a
                # representative point: Point→[lng,lat], LineString→
                # [[lng,lat], …], MultiLineString→[[[lng,lat], …], …].
                cur = coords
                for _ in range(4):
                    if isinstance(cur, list) and cur and isinstance(cur[0], list) \
                            and cur[0] and not isinstance(cur[0][0], list):
                        first_pt = cur[0]
                        break
                    if isinstance(cur, list) and cur:
                        cur = cur[0]
                    else:
                        break
                if first_pt is None and isinstance(coords, list) \
                        and coords and not isinstance(coords[0], list):
                    first_pt = coords  # bare Point
                self._diag_log(
                    f"Sample feature geometry: type={gtype!r} "
                    f"first_point={first_pt!r} "
                    f"(len={len(first_pt) if isinstance(first_pt, list) else 'n/a'})"
                )

            # Live API unavailable — fall back to a bundled seed file
            # if the project ships one.
            seed_path = _find_local_seed()
            if seed_path is not None:
                self.progress.emit(
                    0, 0,
                    f"Importing bundled seed: {os.path.basename(seed_path)}…"
                )
                if self._import_local_seed(store, seed_path):
                    return
                # Fall through to the error if the seed didn't parse.
            self.error.emit(
                "Could not detect field names from the Edmonton dataset.\n"
                "\n"
                "Tried:\n"
                f"  • Socrata views metadata: {err or 'ok'}\n"
                f"  • Sample-row sniffing: {err2 or 'ok'}\n"
                "  • Local seed at data/edmonton_contours.geojson(.gz)\n"
                "\n"
                "Check your internet connection, or drop a downloaded\n"
                "GeoJSON of the Edmonton contour dataset at\n"
                "data/edmonton_contours.geojson and retry."
            )
            return

        total_stored = 0
        page_num     = 0

        while not self._cancel:
            offset = page_num * 1000
            qs = urllib.parse.urlencode({
                "$select": f"{geom_field},{elev_field}",
                "$limit":  1000,
                "$offset": offset,
                "$order":  ":id",
            })
            url = f"{_EDM_RESOURCE}?{qs}"
            t_page = time.monotonic()
            page_data = _http_get_json(url, timeout=30)

            if page_data is None:
                # Possibly $order=:id not supported — retry without it
                qs2 = urllib.parse.urlencode({
                    "$select": f"{geom_field},{elev_field}",
                    "$limit":  1000,
                    "$offset": offset,
                })
                page_data = _http_get_json(f"{_EDM_RESOURCE}?{qs2}", timeout=30)

            if not page_data or "features" not in page_data:
                if page_num == 0:
                    # Probe the same URL with the diagnostic helper so
                    # the user (and us) can see the real failure mode
                    # instead of just "no data".
                    ok, status, payload, err = _diag_fetch(url, timeout=30)
                    self._diag_log(
                        f"Page-0 fetch: ok={ok} status={status} "
                        f"err={err or '-'} "
                        f"elapsed={time.monotonic() - t_page:.1f}s "
                        f"url={url}"
                    )
                    self.error.emit(
                        "No data received from the Edmonton Open Data API.\n"
                        f"\nDiagnostic: status={status}, error={err or 'none'}.\n"
                        "Check your internet connection and try again."
                    )
                    return
                break  # empty last page or network blip after we have data

            feats = page_data.get("features") or []
            if not feats:
                break  # clean end-of-dataset

            converted = _convert_page(feats, elev_field)
            stored = store.store_edmonton_page(converted)
            total_stored += stored
            page_num += 1

            self.progress.emit(
                total_stored,
                page_num,
                f"Page {page_num} downloaded — {total_stored:,} features stored…",
            )

            if len(feats) < 1000:
                break  # last page

        if self._cancel:
            # Leave the store in a partial state (has_edmonton_data() stays False)
            return

        try:
            self.progress.emit(total_stored, page_num, "Merging tiles, please wait…")
            store.mark_edmonton_complete(total_stored)
        except Exception as exc:
            self.error.emit(f"Failed to finalise download: {exc}")
            return

        self.finished.emit(total_stored)

    def _import_local_seed(self, store: TerrainStore, path: str) -> bool:
        """Import a locally-bundled GeoJSON contour file in chunks.

        Returns True if anything was stored (and emits ``finished``);
        False if the file couldn't be parsed (caller falls back to the
        regular network error). The seed is expected to be a GeoJSON
        FeatureCollection with the same shape as the live Socrata API
        response — properties carrying an elevation, geometry as
        (Multi)LineString in [lng, lat] order.
        """
        data = _load_seed(path)
        if not isinstance(data, dict):
            return False
        feats = data.get("features") or []
        if not isinstance(feats, list) or not feats:
            return False

        # Sniff the elevation field from the first feature with a numeric
        # property — same hint list as the API path.
        from src.terrain import _EDM_ELEV_HINTS  # local import to avoid cycle
        elev_field: "str | None" = None
        for f in feats[:50]:
            props = (f.get("properties") or {})
            for k, v in props.items():
                if any(h in k.lower() for h in _EDM_ELEV_HINTS):
                    if _coerce_float(v) is not None:
                        elev_field = k
                        break
            if elev_field:
                break
        if elev_field is None:
            for f in feats[:50]:
                for k, v in (f.get("properties") or {}).items():
                    if _coerce_float(v) is not None:
                        elev_field = k
                        break
                if elev_field:
                    break
        if elev_field is None:
            return False

        total_stored = 0
        page_num = 0
        page_size = 1000
        for i in range(0, len(feats), page_size):
            if self._cancel:
                return False
            chunk = feats[i:i + page_size]
            converted = _convert_page(chunk, elev_field)
            stored = store.store_edmonton_page(converted)
            total_stored += stored
            page_num += 1
            self.progress.emit(
                total_stored,
                page_num,
                f"Local seed: page {page_num} — {total_stored:,} features stored…",
            )

        if total_stored == 0:
            return False
        try:
            self.progress.emit(
                total_stored, page_num, "Merging tiles, please wait…"
            )
            store.mark_edmonton_complete(total_stored)
        except Exception as exc:
            self.error.emit(f"Failed to finalise local-seed import: {exc}")
            return True   # we did emit error; tell caller not to re-error
        self.finished.emit(total_stored)
        return True


# ── Internal helpers ─────────────────────────────────────────────────────────

def _convert_page(features: list, elev_field: str) -> list:
    """
    Convert a page of Socrata GeoJSON features to the internal format:
      {"coords": [[lat, lng], ...], "elevation_m": float}

    Socrata encodes coordinates as [lng, lat]; we flip to [lat, lng] to
    match the rest of PermaDesign.
    """
    result = []
    for f in features:
        props = f.get("properties") or {}
        geom  = f.get("geometry") or {}
        elev  = _coerce_float(props.get(elev_field))
        if elev is None:
            continue
        for line in _flatten_geojson_lines(geom):
            coords = [[c[1], c[0]] for c in line if len(c) >= 2]
            if len(coords) >= 2:
                result.append({"coords": coords, "elevation_m": elev})
    return result
