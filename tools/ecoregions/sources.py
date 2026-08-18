"""Every dataset this pipeline reads, in one table.

Dev-time only. One place to look when a portal moves a file, which they do
constantly — the landing page is recorded beside the direct link precisely
because the direct link is the part that rots.

WHAT "REACHABLE" MEANS HERE
-------------------------------------------------------------------------------
The cloud sessions this project is developed in run behind an egress proxy that
allows GitHub and PyPI and refuses everything else with a 403 to CONNECT. That
is why the Natural Earth basemap arrives from the ``nvkelso`` GitHub mirrors —
which are the upstream project's own repositories, not a third-party copy —
while the two classification datasets have to be fetched by hand on a machine
with open egress.

That is a property of the *session*, not of the data, and the ``manual`` flag
records it so the fetch stage can print a precise instruction instead of a
stack trace. Nothing here is ever substituted for something easier to reach;
per the rebuild brief, a source that cannot be retrieved is reported, not
worked around.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Source:
    """One downloadable dataset."""

    key: str
    #: File name under ``data/raw`` once fetched.
    filename: str
    #: What the layer is, in one line, for the fetch report.
    what: str
    #: Direct download. Empty when only the landing page is stable.
    url: str = ""
    #: The human page to go to when ``url`` has rotted. Always populated.
    landing: str = ""
    #: Publisher and edition, copied into README.md by the fetch stage.
    publisher: str = ""
    edition: str = ""
    licence: str = ""
    #: True when this session cannot reach the host and a human must fetch it.
    manual: bool = False
    #: Extra files that must arrive alongside (shapefile siblings, etc).
    siblings: tuple = field(default_factory=tuple)
    #: ArcGIS MapServer/FeatureServer URL, when the dataset is published as a
    #: live service rather than as a downloadable file.
    service: str = ""


#: Natural Earth 1:10m, from the upstream project's own GitHub repositories.
#: Public domain, no attribution required (the project asks for it anyway, and
#: the map gives it).
_NE_VECTOR = ("https://raw.githubusercontent.com/nvkelso/"
              "natural-earth-vector/master")
_NE_RASTER = ("https://raw.githubusercontent.com/nvkelso/"
              "natural-earth-raster/master")

BASEMAP: tuple = (
    Source(
        key="ne_admin_1",
        filename="ne_10m_admin_1_states_provinces.shp",
        what="Provinces and states, 1:10m",
        url=f"{_NE_VECTOR}/10m_cultural/ne_10m_admin_1_states_provinces.shp",
        landing="https://www.naturalearthdata.com/downloads/10m-cultural-vectors/",
        publisher="Natural Earth", edition="5.1.2", licence="Public domain",
        siblings=("shx", "dbf", "prj", "cpg"),
    ),
    Source(
        key="ne_rivers",
        filename="ne_10m_rivers_lake_centerlines.shp",
        what="River centrelines, 1:10m",
        url=f"{_NE_VECTOR}/10m_physical/ne_10m_rivers_lake_centerlines.shp",
        landing="https://www.naturalearthdata.com/downloads/10m-physical-vectors/",
        publisher="Natural Earth", edition="5.1.2", licence="Public domain",
        siblings=("shx", "dbf", "prj", "cpg"),
    ),
    Source(
        key="ne_lakes",
        filename="ne_10m_lakes.geojson",
        what="Lakes, 1:10m",
        url=f"{_NE_VECTOR}/geojson/ne_10m_lakes.geojson",
        landing="https://www.naturalearthdata.com/downloads/10m-physical-vectors/",
        publisher="Natural Earth", edition="5.1.2", licence="Public domain",
    ),
    Source(
        key="ne_lakes_na",
        filename="ne_10m_lakes_north_america.geojson",
        what="Lakes, North America supplement, 1:10m",
        url=f"{_NE_VECTOR}/geojson/ne_10m_lakes_north_america.geojson",
        landing="https://www.naturalearthdata.com/downloads/10m-physical-vectors/",
        publisher="Natural Earth", edition="5.1.2", licence="Public domain",
    ),
    Source(
        key="ne_relief",
        filename="SR_HR.tif",
        what="Shaded relief raster, 1:10m (21600x10800)",
        url=f"{_NE_RASTER}/10m_rasters/SR_HR/SR_HR.tif",
        landing="https://www.naturalearthdata.com/downloads/10m-raster-data/",
        publisher="Natural Earth", edition="2.0", licence="Public domain",
    ),
)

#: The classification. ELC is the base geometry because it is national and
#: already spans both provinces; the Alberta subregions ride along as an
#: attribute joined spatially, never on name.
CLASSIFICATION: tuple = (
    Source(
        key="elc_ecoregion",
        filename="nef_ca_ter_ecoregion_v2_2.geojson",
        what="Terrestrial Ecoregions of Canada (the base geometry)",
        url="https://agriculture.canada.ca/atlas/data_donnees/"
            "nationalEcologicalFramework/data_donnees/geoJSON/er/"
            "nef_ca_ter_ecoregion_v2_2.geojson",
        landing="https://open.canada.ca/data/en/dataset/"
                "3ef8e8a9-8d05-4fea-a8bf-7f5023d2b6e1",
        publisher="Agriculture and Agri-Food Canada / Ecological "
                  "Stratification Working Group",
        edition="National Ecological Framework v2.2 (1995 framework)",
        licence="Open Government Licence - Canada",
        manual=True,
    ),
    Source(
        key="elc_ecozone",
        filename="nef_ca_ter_ecozone_v2_2.geojson",
        what="Terrestrial Ecozones of Canada (the parent level, for the "
             "crosswalk: this is what separates Boreal Shield from Boreal "
             "Plains and Taiga Shield)",
        url="https://agriculture.canada.ca/atlas/data_donnees/"
            "nationalEcologicalFramework/data_donnees/geoJSON/ez/"
            "nef_ca_ter_ecozone_v2_2.geojson",
        landing="https://open.canada.ca/data/en/dataset/"
                "3ef8e8a9-8d05-4fea-a8bf-7f5023d2b6e1",
        publisher="Agriculture and Agri-Food Canada / Ecological "
                  "Stratification Working Group",
        edition="National Ecological Framework v2.2 (1995 framework)",
        licence="Open Government Licence - Canada",
        manual=True,
    ),
    Source(
        key="ab_subregions",
        filename="alberta_natural_subregions.geojson",
        what="Natural Regions and Subregions of Alberta (the detail layer, "
             "joined spatially as an attribute)",
        url="",
        landing="https://open.alberta.ca/opendata/"
                "gda-2f36921e-41e3-4cd8-813e-3333ea3c5983",
        publisher="Alberta Environment and Protected Areas "
                  "(Natural Regions Committee 2006)",
        edition="2005 Final, 1:250 000",
        licence="Open Government Licence - Alberta",
        manual=True,
        # Not a file. Alberta publishes this as a live ArcGIS service; the
        # portal's four "resources" are an HTML metadata page, an XML metadata
        # record, and two REST endpoints. `tools.ecoregions.arcgis` queries it
        # and writes the GeoJSON this expects. The brief warned that Alberta
        # might arrive as a File Geodatabase rather than a shapefile; it
        # arrives as neither, which is the same lesson one step further on.
        service="https://geospatial.alberta.ca/titan/rest/services/biota/"
                "natural_subregions_alberta_2005/FeatureServer",
    ),
)

ALL: tuple = BASEMAP + CLASSIFICATION


def by_key(key: str) -> Source:
    for source in ALL:
        if source.key == key:
            return source
    raise KeyError(key)
