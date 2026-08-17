"""Paths, the map window, and the one projection every stage agrees on.

Dev-time only — nothing under ``tools/`` ships to users or is imported by the
app at runtime.

WHY A SEPARATE PROJECTION FROM ``src/projection.py``
-------------------------------------------------------------------------------
The app's projection module is about *site-scale* metres-per-degree around a
single property, where a cosine factor is within ~1% and pulling in pyproj was
judged not worth the packaging risk. This pipeline is about *provincial-scale*
areas and boundaries across twelve degrees of latitude, where that cosine factor
is exactly the distortion the rebuild brief calls out. So this file uses a real
equal-area conic and never imports ``src.projection`` — different problem,
different tool, and no runtime dependency created in either direction.
"""

from __future__ import annotations

import pathlib

#: ``tools/ecoregions/``
ROOT = pathlib.Path(__file__).resolve().parent
#: Downloaded sources. Gitignored; 50-150 MB when full.
DATA = ROOT / "data"
#: Where each stage writes its intermediate. Gitignored, resumable.
OUT = ROOT / "out"
#: The repository root, for writing shipped artefacts into ``data/``.
REPO = ROOT.parent.parent

#: Lon/lat window every render and clip uses: Alberta and Saskatchewan with
#: enough of BC, the Territories, Manitoba and Montana around them that the two
#: provinces read as part of a continent rather than as a floating shape.
#: (west, south, east, north)
WINDOW = (-125.0, 47.6, -96.0, 61.4)

#: The provinces the layer actually classifies. Everything else in the window is
#: context, drawn in grey.
SUBJECT_PROVINCES = ("Alberta", "Saskatchewan")

#: Canada Albers Equal Area Conic. Equal-area matters here because the whole
#: point of the map is comparing how much ground each ecoregion covers; the
#: brief's complaint about plate carree at 49-60 degrees north is that it
#: inflates east-west distance so badly that areas stop being comparable.
CRS_PROJECTED = "ESRI:102001"
#: What the source data and every exported GeoJSON use.
CRS_WGS84 = "EPSG:4326"


def ensure_dirs() -> None:
    """Create the working directories. Safe to call repeatedly."""
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "raw").mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)


def require(*modules: str) -> None:
    """Fail with an install line rather than a traceback.

    These are dev-only dependencies. Putting them in ``requirements.txt`` would
    push a native-extension geospatial stack onto every user of a PyQt6 desktop
    app that has no use for it, and the packaging lesson this repo already
    learned the hard way is that optional native deps in the frozen build are
    where builds go to die.
    """
    missing = []
    for name in modules:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        raise SystemExit(
            "Missing dev-only dependencies: " + ", ".join(missing) + "\n"
            "    pip install " + " ".join(missing) + "\n"
            "(or: conda install -c conda-forge geopandas rasterio, which is "
            "the path of least resistance on Windows)"
        )
