"""
services.py — every outside service the app asks, credited, and what it is
sent (FN-5, V3.31; docs/homeowner/10-finishing.md §4).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

One table. *Where Site & Pattern's data comes from* lists it (credit is the
licence condition on most of these: Open-Meteo's and SoilGrids' CC BY 4.0,
OpenStreetMap's ODbL), and ``tests/test_services.py`` reads every host a URL in
``src/`` or the map's scripts points at and fails on one that is neither here
nor in :data:`NOT_ASKED`, so a new service cannot arrive uncredited.

:data:`PRIVACY` is the paragraph About shows: what leaves the computer, and
that nothing else does.

Qt-free.
"""

from __future__ import annotations

from typing import NamedTuple


class Service(NamedTuple):
    name: str
    hosts: tuple
    used_for: str
    credit: str           # what the provider asks to be said, or the licence
    sent: str             # what the app sends it


SERVICES: tuple = (
    Service("Open-Meteo", ("api.open-meteo.com", "archive-api.open-meteo.com"),
            "elevation, climate history, wind",
            "Weather data by Open-Meteo.com (CC BY 4.0)",
            "the pin's coordinates"),
    Service("OpenStreetMap address search (Nominatim)",
            ("nominatim.openstreetmap.org",),
            "finding your address",
            "© OpenStreetMap contributors (ODbL)",
            "the address you type, when you press Find"),
    Service("OpenStreetMap map tiles", ("tile.openstreetmap.org",),
            "the street map",
            "© OpenStreetMap contributors (ODbL)",
            "the part of the map on screen"),
    Service("Overpass API", ("overpass-api.de", "overpass.private.coffee",
                             "overpass.kumi.systems"),
            "buildings, trees and roads near the yard (Scan this area)",
            "© OpenStreetMap contributors (ODbL)",
            "a box around the yard, when you ask"),
    Service("Esri basemaps (World Topographic Map, World Imagery)",
            ("server.arcgisonline.com",),
            "the street map and the satellite view; trees for Scan this area "
            "when the canopy map cannot be reached",
            "Powered by Esri. Imagery: Esri, Maxar, Earthstar Geographics and "
            "the GIS User Community",
            "the part of the map on screen"),
    Service("ISRIC SoilGrids", ("rest.isric.org",),
            "soil, when the offline soil pack is not downloaded",
            "SoilGrids by ISRIC – World Soil Information (CC BY 4.0)",
            "the pin's coordinates"),
    Service("Agriculture and Agri-Food Canada",
            ("agriculture.canada.ca",),
            "the offline soil pack (Soil Landscapes of Canada), when you "
            "download it",
            "Open Government Licence – Canada",
            "nothing about you: one download"),
    Service("Natural Resources Canada (HRDEM)", ("datacube.services.geo.ca",),
            "detailed elevation (advanced)",
            "Open Government Licence – Canada",
            "a box around the yard, when you ask"),
    Service("City of Edmonton Open Data",
            ("data.edmonton.ca", "api.us.socrata.com"),
            "0.5 m contours (advanced)",
            "City of Edmonton Open Data Licence",
            "a box around the yard, when you ask"),
    Service("Meta and WRI canopy height", (
                "dataforgood-fb-data.s3.amazonaws.com",),
            "trees for Scan this area",
            "High Resolution Canopy Height Maps by Meta and WRI (CC BY 4.0)",
            "nothing about you: map tiles near the yard"),
    Service("iNaturalist", ("inaturalist-open-data.s3.amazonaws.com",),
            "plant photographs",
            "each photograph's own credit and licence, shown with it",
            "nothing about you: the photograph's address"),
    Service("Mapbox", ("api.mapbox.com",),
            "satellite imagery with your own token (advanced, off unless "
            "you add one)",
            "© Mapbox, © OpenStreetMap",
            "the part of the map on screen, under your own account"),
    Service("GitHub", ("api.github.com",),
            "Check for Updates",
            "",
            "nothing about you: asks for the latest release"),
)

#: Hosts a URL in the code names that the app does not ask while you use it:
#: ``host: why``.
NOT_ASKED: dict = {
    "github.com": "a link to the app's page, opened in your browser if you click",
    "www.openstreetmap.org": "a link in the map's credit line",
    "www.esri.com": "a link in the map's credit line",
    "www.mapbox.com": "a link in the map's credit line",
    "account.mapbox.com": "a link in Preferences, for your own token",
    "www.w3.org": "a name in an SVG drawing, never fetched",
    "www.sitemaps.org": "a name in the website's sitemap, never fetched",
    "localhost": "the computer itself",
    "127.0.0.1": "the computer itself",
    "grownativeplants.ca": "the website's own address, in its pages",
    "www.gbif.org": "links on the website's species pages",
    "www.inaturalist.org": "links on the website's species pages",
    "data.canadensys.net": "a link naming the flora checklist (VASCAN)",
    "cloud.umami.is": "website analytics, off unless the site is built with it",
    "eu.umami.is": "website analytics, off unless the site is built with it",
    "static.cloudflareinsights": "website analytics, off unless asked for",
    "plants.usda.gov": "a developer's import script, never the app",
}

#: About's paragraph (FN-5, §4): what leaves the computer.
PRIVACY = (
    "What leaves your computer: the address you type goes to OpenStreetMap's "
    "address search when you press Find; your yard's pin goes to Open-Meteo "
    "and SoilGrids for its climate and soil, and the map's tile servers see "
    "the part of the map on screen. When you ask, a box around your yard goes "
    "to Overpass, Natural Resources Canada or the City of Edmonton. Nothing "
    "else leaves: there is no account, no analytics, and feedback is sent "
    "only when you send it. Photographs you add have their location removed.")


def hosts() -> set:
    return {h for s in SERVICES for h in s.hosts}


def credit_lines() -> list:
    """``["Open-Meteo: elevation, climate history, wind. Weather data by …"]``."""
    out = []
    for s in SERVICES:
        line = f"{s.name}: {s.used_for}."
        if s.credit:
            line += f" {s.credit}."
        line += f" Sent: {s.sent}."
        out.append(line)
    return out
