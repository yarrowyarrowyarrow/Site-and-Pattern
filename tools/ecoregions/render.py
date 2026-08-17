"""Stage 5 — the publication map.

    python -m tools.ecoregions.render                 # from out/ecoregions.gpkg
    python -m tools.ecoregions.render --from-shipped  # from data/ecoregions_canada.geojson

Draw order, bottom to top: shaded relief, neighbouring land in grey, ecoregion
fills, lakes, rivers, provincial borders, city points, labels, then the legend
and the rest of the furniture.

WHY ``--from-shipped`` EXISTS
-------------------------------------------------------------------------------
So the cartography can be exercised before the classification data arrives. The
two ELC downloads need a machine with open egress; the drawing does not, and a
render pipeline that has never once been run is not a render pipeline. With
``--from-shipped`` it draws the hand-traced placeholder polygons the app ships
today, which proves every layer, the projection and the legend, and produces an
image whose caption says exactly what it is.

The one thing it must never do is produce a *publishable* map from placeholder
geometry with no caption saying so. So the caption is not optional and not a
parameter: it is derived from which source was used, and the placeholder path
stamps the image itself.

COLOURS COME FROM THE APP
-------------------------------------------------------------------------------
``src.ecoregion_palette`` is imported rather than duplicated, so the printed map
and the website cannot drift apart, and the legend swatches are generated from
the same dict as the polygon fills. That is structural, not a convention: the
second attempt shipped a legend with two of its colours swapped, which is only
possible when the two lists are maintained separately.
"""

from __future__ import annotations

import argparse
import sys

from tools.ecoregions.common import (CRS_PROJECTED, CRS_WGS84, DATA, OUT, REPO,
                                     WINDOW, ensure_dirs, require)
from tools.ecoregions.harmonize import GPKG

_RAW = DATA / "raw"
PNG = OUT / "ecoregions.png"
SVG = OUT / "ecoregions.svg"

#: Standard parallels for the printed map. Same family as the website's SVG
#: projector and for the same reason; see src/ecoregion_map.py:_ALBERS.
_PROJ = ("+proj=aea +lat_1=50 +lat_2=58 +lat_0=54 +lon_0=-110.5 "
         "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")

_CAPTION_REAL = (
    "Ecoregion boundaries: National Ecological Framework for Canada v2.2 "
    "(Ecological Stratification Working Group 1995; Agriculture and "
    "Agri-Food Canada), clipped to Alberta and Saskatchewan. Alberta "
    "subregions: Natural Regions and Subregions of Alberta, 2005 Final "
    "(Natural Regions Committee 2006), joined by spatial overlap. "
    "Basemap, relief, water and populated places: Natural Earth 1:10m "
    "(public domain). Projection: Albers Equal Area Conic, standard "
    "parallels 50 N and 58 N, central meridian 110.5 W."
)
_CAPTION_PLACEHOLDER = (
    "PLACEHOLDER GEOMETRY. The ecoregion outlines drawn here are the "
    "hand-traced approximations the application ships as a stand-in; they "
    "are not digitised from any survey and must not be read as boundaries. "
    "Basemap, relief, water and populated places: Natural Earth 1:10m "
    "(public domain). Projection: Albers Equal Area Conic."
)


def _relief(ax, extent_ll):
    """The Natural Earth shaded relief, cropped to the window and reprojected.

    Reprojected rather than drawn in lat/lon and stretched, because the whole
    map is on an equal-area conic and a basemap that is not on the same
    projection as the polygons over it is a basemap that lies about where the
    mountains are by a visible margin at this scale.
    """
    import numpy as np
    import rasterio
    from rasterio.warp import Resampling, calculate_default_transform, reproject
    from rasterio.windows import from_bounds

    path = _RAW / "SR_HR.tif"
    if not path.exists():
        print("  relief raster absent; drawing without it")
        return
    west, south, east, north = extent_ll
    with rasterio.open(path) as src:
        window = from_bounds(west, south, east, north, src.transform)
        data = src.read(1, window=window)
        src_transform = src.window_transform(window)
        transform, width, height = calculate_default_transform(
            src.crs, _PROJ, data.shape[1], data.shape[0],
            *rasterio.windows.bounds(window, src.transform))
        out = np.zeros((height, width), dtype=data.dtype)
        reproject(source=data, destination=out,
                  src_transform=src_transform, src_crs=src.crs,
                  dst_transform=transform, dst_crs=_PROJ,
                  resampling=Resampling.bilinear)
    left, top = transform * (0, 0)
    right, bottom = transform * (width, height)
    # Reprojecting a lat/lon window onto a cone gives a curved quadrilateral,
    # but imshow can only place an axis-aligned rectangle. The corners outside
    # the footprint stay at the fill value, and drawn as greyscale that is
    # solid black - which is how the first render came out framed in dark bands.
    # Masking them makes those pixels transparent so the page shows through.
    # Zero is a legitimate relief value in principle; in this raster it means
    # "no data here", because Natural Earth's shading bottoms out well above it.
    ax.imshow(np.ma.masked_equal(out, 0), cmap="Greys_r", vmin=0, vmax=255,
              alpha=0.45, extent=(left, right, bottom, top), zorder=1,
              interpolation="bilinear")


def _load_regions(from_shipped: bool):
    import geopandas as gpd

    if from_shipped:
        path = REPO / "data" / "ecoregions_canada.geojson"
        gdf = gpd.read_file(path)
        # The shipped file names the region in `key`; the real one uses
        # `ecoregion`. Normalise so one drawing routine serves both.
        gdf = gdf.rename(columns={"key": "ecoregion"})
        return gdf, True
    if not GPKG.exists():
        raise SystemExit(
            f"{GPKG} does not exist.\n"
            "  Run:  python -m tools.ecoregions.harmonize\n"
            "  or:   python -m tools.ecoregions.render --from-shipped")
    return gpd.read_file(GPKG, layer="ecoregions"), False


def _colour_for(name: str, palette, fallback_cycle) -> str:
    """A colour for a region name, from the app's palette where it knows one.

    The real ELC names will not all be app keys, so anything unknown draws from
    a generated ramp. That is flagged in the run output rather than passed over:
    a region drawn in a colour nobody chose is a region whose colour means
    nothing, and the fix is to add it to the app's palette.
    """
    key = name.lower().replace(" ", "_").replace("/", "_")
    if key in palette:
        return palette[key]
    return fallback_cycle(name)


def _draw_legend(ax, used: dict, hatched: set) -> None:
    """Swatches generated from the same dict that filled the polygons.

    Structural rather than conventional: the second rebuild attempt shipped a
    legend whose Peace River Parkland swatch was the colour of its Aspen
    Parkland polygons and vice versa, which is only reachable when the fills
    and the key are two lists somebody keeps in step by hand.
    """
    from matplotlib.patches import Patch

    handles = [
        Patch(facecolor=colour, edgecolor="#6d6a5e", linewidth=0.5,
              hatch="///" if name in hatched else None, label=_display(name))
        for name, colour in sorted(used.items())
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, -0.02),
              ncol=3, frameon=False, fontsize=8, handlelength=1.6,
              handleheight=1.1, borderaxespad=0.0)


def _display(name: str) -> str:
    """The app's display name for a region key, or the name unchanged.

    The shipped placeholder file keys regions as `aspen_parkland`; the ELC file
    names them `Aspen Parkland`. A legend should read as the latter either way.
    """
    try:
        from src.ecoregion import ecoregion_display            # noqa: PLC0415
        label, _where = ecoregion_display(name)
        if label and label != name:
            return label
    except Exception:                                          # noqa: BLE001
        pass
    return name.replace("_", " ").title() if "_" in name else name


def _scale_bar(ax, length_km: int = 200) -> None:
    """A scale bar. Meaningful because the projection is equal-area, which is
    also why one bar is honest across the whole frame rather than only at the
    standard parallels."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    bar = length_km * 1000.0
    left = x0 + (x1 - x0) * 0.04
    bottom = y0 + (y1 - y0) * 0.05
    ax.plot([left, left + bar], [bottom, bottom], color="#2b2d24", lw=2.4,
            solid_capstyle="butt", zorder=9)
    ax.text(left + bar / 2, bottom + (y1 - y0) * 0.012, f"{length_km} km",
            ha="center", va="bottom", fontsize=7.5, color="#2b2d24", zorder=9)


def _north_arrow(ax) -> None:
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x0 + (x1 - x0) * 0.955
    bottom = y0 + (y1 - y0) * 0.045
    ax.annotate("", xy=(x, bottom + (y1 - y0) * 0.055), xytext=(x, bottom),
                arrowprops={"arrowstyle": "-|>", "color": "#2b2d24",
                            "linewidth": 1.4}, zorder=9)
    ax.text(x, bottom + (y1 - y0) * 0.062, "N", ha="center", va="bottom",
            fontsize=8.5, weight="bold", color="#2b2d24", zorder=9)


def run(*, from_shipped: bool = False, dpi: int = 200) -> int:
    require("geopandas", "matplotlib", "rasterio", "shapely")
    ensure_dirs()
    import geopandas as gpd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sys.path.insert(0, str(REPO))
    from src.ecoregion_palette import HATCHED, REGION_COLOUR   # noqa: PLC0415

    regions, placeholder = _load_regions(from_shipped)
    regions = regions.to_crs(_PROJ)

    base = gpd.read_file(REPO / "data" / "basemap_prairie.geojson")
    # `subject` is only set on province features, so it arrives as an object
    # column full of None for the lakes and rivers. Coerce before inverting.
    is_subject = base["subject"].fillna(False).astype(bool)
    is_province = base["layer"] == "province"
    land = base[base["layer"] == "land"].to_crs(_PROJ)
    context = base[is_province & ~is_subject].to_crs(_PROJ)
    subject = base[is_province & is_subject].to_crs(_PROJ)
    lakes = base[base["layer"] == "lake"].to_crs(_PROJ)
    rivers = base[base["layer"] == "river"].to_crs(_PROJ)

    fig, ax = plt.subplots(figsize=(11.5, 8.6))
    fig.patch.set_facecolor("#f6f5f0")
    ax.set_facecolor("#f6f5f0")

    _relief(ax, WINDOW)
    land.plot(ax=ax, color="#d7d6cd", edgecolor="none", zorder=2)
    context.plot(ax=ax, color="#d7d6cd", edgecolor="#c6c5bb", lw=0.4, zorder=3)
    subject.plot(ax=ax, color="#eceada", edgecolor="none", zorder=4)

    spare = plt.get_cmap("tab20")
    seen: dict = {}

    def fallback(name):
        seen.setdefault(name, None)
        idx = sorted(seen).index(name) % 20
        return matplotlib.colors.to_hex(spare(idx))

    used: dict = {}
    unknown: list = []
    for name, group in regions.groupby("ecoregion"):
        colour = _colour_for(str(name), REGION_COLOUR, fallback)
        key = str(name).lower().replace(" ", "_").replace("/", "_")
        if key not in REGION_COLOUR:
            unknown.append(str(name))
        used[str(name)] = colour
        group.plot(ax=ax, color=colour, edgecolor="#8b8878", lw=0.5,
                   alpha=0.92, zorder=5)
        if key in HATCHED:
            group.plot(ax=ax, color="none", edgecolor="#6d6a5e", lw=0.0,
                       hatch="///", zorder=6)

    lakes.plot(ax=ax, color="#b9cfdd", edgecolor="#93b3c6", lw=0.4, zorder=7)
    rivers.plot(ax=ax, color="#93b3c6", lw=0.7, zorder=7)
    subject.boundary.plot(ax=ax, color="#6d6a5e", lw=1.1, zorder=8)

    from src.ecoregion_basemap import CITIES                   # noqa: PLC0415
    points = gpd.GeoDataFrame(
        {"name": [c[0] for c in CITIES]},
        geometry=gpd.points_from_xy([c[2] for c in CITIES],
                                    [c[1] for c in CITIES]),
        crs=CRS_WGS84).to_crs(_PROJ)
    points.plot(ax=ax, color="#2b2d24", markersize=9, zorder=9)
    for _, row in points.iterrows():
        ax.annotate(row["name"], (row.geometry.x, row.geometry.y),
                    xytext=(5, 2), textcoords="offset points", fontsize=7.5,
                    color="#2b2d24", zorder=9)

    bounds = land.total_bounds
    ax.set_xlim(bounds[0], bounds[2])
    ax.set_ylim(bounds[1], bounds[3])
    ax.set_axis_off()
    _scale_bar(ax)
    _north_arrow(ax)

    title = ("Ecoregions of Alberta and Saskatchewan"
             if not placeholder else
             "Ecoregions of Alberta and Saskatchewan  [PLACEHOLDER GEOMETRY]")
    ax.set_title(title, fontsize=15, loc="left", pad=12, color="#23261d")
    _draw_legend(ax, used, set(HATCHED))
    caption = _CAPTION_PLACEHOLDER if placeholder else _CAPTION_REAL
    fig.text(0.012, 0.012, _wrap(caption, 150), fontsize=6.4, color="#5c5a4f",
             va="bottom", ha="left")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.94, bottom=0.20)

    fig.savefig(PNG, dpi=dpi, facecolor=fig.get_facecolor())
    fig.savefig(SVG, facecolor=fig.get_facecolor())
    plt.close(fig)

    print(f"  wrote {PNG.relative_to(REPO)}  ({PNG.stat().st_size / 1e6:.1f} MB)")
    print(f"  wrote {SVG.relative_to(REPO)}")
    if placeholder:
        print("\n  NOTE: drawn from placeholder geometry. The image says so in")
        print("  its title and caption; do not crop either off.")
    if unknown:
        print(f"\n  {len(unknown)} region(s) drew from the fallback ramp rather")
        print("  than the app palette, so their colour asserts nothing:")
        for name in sorted(unknown):
            print(f"    {name}")
        print("  Add them to REGION_COLOUR in src/ecoregion_palette.py, then")
        print("  re-run tests/test_ecoregion.py to re-check the hatch rule.")
    return 0


def _wrap(text: str, width: int) -> str:
    import textwrap
    return "\n".join(textwrap.wrap(text, width))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--from-shipped", action="store_true",
                        help="draw the app's placeholder polygons instead of "
                             "the harmonized build (stamps the image as such)")
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args(argv)
    return run(from_shipped=args.from_shipped, dpi=args.dpi)


if __name__ == "__main__":
    sys.exit(main())
