"""Pull a whole ArcGIS feature layer down as GeoJSON.

    python -m tools.ecoregions.arcgis <service-url>            # list the layers
    python -m tools.ecoregions.arcgis <service-url> --layer 0 --out <path>

WHY THIS EXISTS
-------------------------------------------------------------------------------
Because "download the shapefile" turned out not to be an option. The Natural
Regions and Subregions of Alberta is published on Alberta's open-data portal as
four resources: an HTML metadata page, an XML metadata record, and two **ESRI
REST** endpoints. None of them is a file. The layer is a live service, and the
supported way to get the whole thing is to query it.

The rebuild brief anticipated the shape of this problem — it warned that Alberta
"may arrive as a File Geodatabase rather than a shapefile" and said to list the
layers first rather than assume. It arrives as neither, which is the same lesson
one step further along: do not assume the *format* either.

PAGING IS THE PART THAT BITES
-------------------------------------------------------------------------------
A feature service caps how many records one query returns —
``maxRecordCount``, commonly 1000 or 2000. Ask for a province's worth of
polygons in one request and you get the cap, silently, with no error: a valid
GeoJSON file containing the first thousand features and nothing to say the rest
exist. That is the failure mode this module is written against, so it pages
until the server stops setting ``exceededTransferLimit`` **and** verifies the
final count against the service's own ``returnCountOnly`` total. A short file is
a hard error, never a quiet success.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

from tools.ecoregions.common import DATA, ensure_dirs

_RAW = DATA / "raw"
_TIMEOUT = 180
#: Requested page size. The server lowers it to its own cap; asking for more
#: than it allows is not an error, it just returns fewer.
_PAGE = 1000


def _get(url: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{url}?{query}", timeout=_TIMEOUT) as response:
        body = response.read().decode("utf-8", "replace")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise SystemExit(
            f"{url} did not return JSON. First 300 characters:\n{body[:300]}")
    # ArcGIS reports failures inside a 200 response rather than as a status.
    if isinstance(payload, dict) and "error" in payload:
        raise SystemExit(f"Service error from {url}:\n  {payload['error']}")
    return payload


def list_layers(service: str) -> int:
    info = _get(service.rstrip("/"), {"f": "json"})
    layers = (info.get("layers") or []) + (info.get("tables") or [])
    if not layers:
        raise SystemExit(f"No layers reported by {service}")
    print(f"{info.get('serviceDescription') or service}\n")
    print(f"  {'id':>4}  {'name':44} geometry")
    print(f"  {'-' * 4}  {'-' * 44} {'-' * 20}")
    for layer in layers:
        print(f"  {layer.get('id'):>4}  {str(layer.get('name'))[:44]:44} "
              f"{layer.get('geometryType') or ''}")
    print("\nRe-run with --layer <id> --out <path> to download one.")
    return 0


def download(service: str, layer: int, out) -> int:
    endpoint = f"{service.rstrip('/')}/{layer}/query"

    expected = _get(endpoint, {"where": "1=1", "returnCountOnly": "true",
                               "f": "json"}).get("count")
    if expected is None:
        print("  service did not report a count; the total cannot be verified")
    else:
        print(f"  service reports {expected} features")

    features: list = []
    offset = 0
    while True:
        page = _get(endpoint, {
            "where": "1=1",
            "outFields": "*",
            "outSR": "4326",
            "returnGeometry": "true",
            "resultOffset": offset,
            "resultRecordCount": _PAGE,
            "f": "geojson",
        })
        batch = page.get("features") or []
        features.extend(batch)
        print(f"    {len(features)} features")
        # Two independent stop conditions, because servers disagree about which
        # they set. Trusting only `exceededTransferLimit` truncates on the ones
        # that omit it; trusting only an empty page costs one extra request.
        if not batch:
            break
        if not (page.get("exceededTransferLimit")
                or page.get("properties", {}).get("exceededTransferLimit")):
            break
        offset += len(batch)

    if expected is not None and len(features) != expected:
        raise SystemExit(
            f"Downloaded {len(features)} features but the service says there "
            f"are {expected}.\nRefusing to write a partial layer - a short file "
            f"here is a map with holes in it, and nothing downstream would "
            f"notice.")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "type": "FeatureCollection",
        "name": f"{service.rstrip('/').rsplit('/', 2)[-2]} layer {layer}",
        "comment": f"Downloaded from {endpoint} by tools/ecoregions/arcgis.py",
        "features": features,
    }), encoding="utf-8")
    print(f"\n  wrote {out}  ({out.stat().st_size / 1e6:.1f} MB, "
          f"{len(features)} features)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("service", help="MapServer or FeatureServer URL")
    parser.add_argument("--layer", type=int, default=None,
                        help="layer id; omit to list what is available")
    parser.add_argument("--out", default="",
                        help="output path (default: data/raw/<name>.geojson)")
    args = parser.parse_args(argv)
    ensure_dirs()
    if args.layer is None:
        return list_layers(args.service)
    import pathlib
    out = (pathlib.Path(args.out) if args.out
           else _RAW / f"arcgis_layer_{args.layer}.geojson")
    return download(args.service, args.layer, out)


if __name__ == "__main__":
    sys.exit(main())
