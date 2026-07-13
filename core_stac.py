# -*- coding: utf-8 -*-
# Copyright (C) 2026 Dott. Sarino Alfonso Grande <sino.grande@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
core_stac.py — STAC search, item parsing, QGIS layer loading, asset download.
"""

import json
import urllib.request
import urllib.parse
import urllib.error

try:
    from qgis.core import QgsRasterLayer
    _HAS_QGIS = True
except ImportError:
    _HAS_QGIS = False

try:
    from osgeo import gdal
    _HAS_GDAL = True
except ImportError:
    _HAS_GDAL = False

# ---------------------------------------------------------------------------
# Catalog registry
# ---------------------------------------------------------------------------

STAC_CATALOGS = [
    {
        "id": "earth-search",
        "name": "Element84 Earth Search",
        "url": "https://earth-search.aws.element84.com/v1",
        "site_url": "https://www.element84.com/earth-search/",
        "description": "Sentinel-2, Landsat C2, NAIP, DEM Copernicus",
        "license": ("Dati Sentinel-2: CC BY 4.0 (Copernicus/ESA). "
                    "Dati Landsat: Public Domain (USGS/NASA)."),
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "auth": False,
        "search_method": "POST",
    },
    {
        "id": "planetary-computer",
        "name": "Microsoft Planetary Computer",
        "url": "https://planetarycomputer.microsoft.com/api/stac/v1",
        "site_url": "https://planetarycomputer.microsoft.com/",
        "description": ("Sentinel-2, Landsat, MODIS, NAIP, DEM, "
                        "permafrost e molto altro"),
        "license": ("Dati dipendono dalla collezione. Molti sono "
                    "CC BY 4.0 o Public Domain."),
        "license_url": "https://planetarycomputer.microsoft.com/terms",
        "auth": False,
        "search_method": "POST",
        "note": ("Il download degli asset richiede token SAS gratuito "
                 "per alcuni dataset."),
    },
    {
        "id": "usgs-landsat",
        "name": "USGS LandsatLook",
        "url": "https://landsatlook.usgs.gov/stac-server",
        "site_url": "https://www.usgs.gov/landsat-missions",
        "description": "Landsat Collection 2 (Landsat 5, 7, 8, 9)",
        "license": "Public Domain — USGS/NASA.",
        "license_url": (
            "https://www.usgs.gov/information-policies-and-instructions/"
            "crediting-usgs"
        ),
        "auth": True,
        "register_url": "https://ers.cr.usgs.gov/register",
        "auth_note": "Il download richiede un account gratuito USGS EROS.",
        "search_method": "POST",
    },
    {
        "id": "nasa-cmr",
        "name": "NASA EarthData CMR",
        "url": "https://cmr.earthdata.nasa.gov/stac",
        "site_url": "https://www.earthdata.nasa.gov/",
        "description": ("Archivio NASA: MODIS, VIIRS, ASTER, OCO-2, "
                        "e centinaia di altri dataset"),
        "license": (
            "Dati NASA: Public Domain. Alcuni dataset richiedono "
            "registrazione EarthData gratuita per il download."
        ),
        "license_url": (
            "https://www.earthdata.nasa.gov/engage/"
            "open-data-services-and-software/data-information-policy"
        ),
        "auth": True,
        "register_url": "https://urs.earthdata.nasa.gov/users/new",
        "auth_note": "Il download richiede un account gratuito NASA EarthData "
                     "Login (token Bearer consigliato).",
        "search_method": "POST",
    },
    {
        "id": "openlandmap",
        "name": "OpenLandMap",
        "url": "https://openlandmap.github.io/stac",
        "site_url": "https://openlandmap.org/",
        "description": "Variabili pedologiche, vegetazione, clima globale",
        "license": "CC BY 4.0.",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "auth": False,
        "search_method": "GET",
    },
    {
        "id": "geoplatform",
        "name": "US GeoPlatform",
        "url": "https://stac.geoplatform.gov",
        "site_url": "https://www.geoplatform.gov/",
        "description": "Dataset geospaziali federali USA",
        "license": "Public Domain (US Government).",
        "license_url": "https://www.usa.gov/government-works",
        "auth": False,
        "search_method": "POST",
    },
    {
        "id": "copernicus",
        "name": "Copernicus Data Space",
        "url": "https://catalogue.dataspace.copernicus.eu/stac",
        "site_url": "https://dataspace.copernicus.eu/",
        "description": "Sentinel-1, Sentinel-2, Sentinel-3, Sentinel-5P",
        "license": "CC BY 4.0 — Copernicus Programme / ESA.",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "auth": True,
        "register_url": "https://dataspace.copernicus.eu/",
        "auth_note": "Il download richiede un account gratuito Copernicus "
                     "Data Space (token di accesso OAuth).",
        "search_method": "POST",
    },
    {
        "id": "dea",
        "name": "Digital Earth Australia",
        "url": "https://explorer.dea.ga.gov.au/stac",
        "site_url": "https://www.dea.ga.gov.au/",
        "description": "Landsat e Sentinel elaborati su Australia",
        "license": "CC BY 4.0 — Geoscience Australia.",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "auth": False,
        "search_method": "POST",
    },
]

# ---------------------------------------------------------------------------
# Raster MIME types / extensions considered "data" assets
# ---------------------------------------------------------------------------

_RASTER_TYPES = {
    "image/tiff", "image/tiff; application=geotiff",
    "image/tiff; application=geotiff; profile=cloud-optimized",
    "image/jp2", "image/vnd.stac.geotiff",
    "application/x-netcdf", "application/x-hdf",
    "application/vnd.las", "image/png", "image/webp",
}

_RASTER_ROLES = {"data", "overview", "visual", "analytic"}

_RASTER_EXTENSIONS = {".tif", ".tiff", ".jp2", ".nc", ".hdf", ".hdf5", ".h5"}

_SPECTRAL_DEFINITIONS = {
    "ndvi": {
        "label_it": "NDVI",
        "label_en": "NDVI",
        "requires": ("nir", "red"),
        "formula": "(NIR - Red) / (NIR + Red)",
    },
    "ndwi": {
        "label_it": "NDWI",
        "label_en": "NDWI",
        "requires": ("green", "nir"),
        "formula": "(Green - NIR) / (Green + NIR)",
    },
    "false_color": {
        "label_it": "Falso colore",
        "label_en": "False color",
        "requires": ("nir", "red", "green"),
        "formula": "RGB = NIR / Red / Green",
    },
}

_BAND_ALIASES = {
    "blue": {
        "blue", "coastal_blue", "b02", "b2", "band2", "band_2", "sr_b2",
        "blue.tif",
    },
    "green": {
        "green", "b03", "b3", "band3", "band_3", "sr_b3", "green.tif",
    },
    "red": {
        "red", "b04", "b4", "band4", "band_4", "sr_b4", "red.tif",
    },
    "nir": {
        "nir", "nir08", "nir09", "b08", "b8", "b8a", "b05", "b5",
        "band5", "band_5", "sr_b5", "nir.tif",
    },
    "swir16": {
        "swir", "swir16", "swir1", "b11", "b6", "b06", "band6",
        "band_6", "sr_b6",
    },
    "swir22": {
        "swir22", "swir2", "b12", "b7", "b07", "band7", "band_7",
        "sr_b7",
    },
}

_LANDSAT_45_TM = {"landsat-4", "landsat-5", "landsat-7", "landsat4",
                  "landsat5", "landsat7"}


def _text_tokens(*values):
    """Return normalized text tokens used for light-weight STAC heuristics."""
    tokens = set()
    for value in values:
        text = str(value or "").lower()
        for sep in ("/", "\\", ".", "-", "_", ":", " "):
            text = text.replace(sep, " ")
        tokens.update(t for t in text.split() if t)
    return tokens


def _spectral_roles_from_band_dict(band):
    """Extract normalized spectral roles from an eo/raster band object."""
    roles = set()
    if not isinstance(band, dict):
        return roles
    common = (band.get("common_name") or band.get("name") or "").lower()
    center = band.get("center_wavelength")
    if common in _BAND_ALIASES:
        roles.add(common)
    for role, aliases in _BAND_ALIASES.items():
        if common in aliases:
            roles.add(role)
    try:
        wl = float(center)
    except (TypeError, ValueError):
        wl = None
    if wl is not None:
        if 0.45 <= wl <= 0.52:
            roles.add("blue")
        elif 0.52 < wl <= 0.60:
            roles.add("green")
        elif 0.62 <= wl <= 0.70:
            roles.add("red")
        elif 0.75 <= wl <= 0.95:
            roles.add("nir")
        elif 1.55 <= wl <= 1.75:
            roles.add("swir16")
        elif 2.05 <= wl <= 2.35:
            roles.add("swir22")
    return roles


def _spectral_roles_from_asset(key, asset, platform=""):
    """Infer spectral roles for a STAC asset from metadata and common keys."""
    roles = set()
    for band in asset.get("eo:bands") or []:
        roles.update(_spectral_roles_from_band_dict(band))
    for band in asset.get("raster:bands") or []:
        roles.update(_spectral_roles_from_band_dict(band))

    title = asset.get("title") or ""
    href_tail = (asset.get("href") or "").split("?")[0].rsplit("/", 1)[-1]
    tokens = _text_tokens(key, title, href_tail)
    for role, aliases in _BAND_ALIASES.items():
        if tokens & aliases:
            roles.add(role)

    # Landsat 4/5/7 use B4 as NIR and B3 as red. Prefer explicit
    # common_name metadata, but fix the common ambiguous asset-key case.
    platform_key = (platform or "").lower().replace("_", "-")
    if any(name in platform_key for name in _LANDSAT_45_TM):
        if "b4" in tokens or "b04" in tokens or "sr b4" in " ".join(tokens):
            roles.discard("red")
            roles.add("nir")
        if "b3" in tokens or "b03" in tokens or "sr b3" in " ".join(tokens):
            roles.discard("green")
            roles.add("red")
        if "b2" in tokens or "b02" in tokens or "sr b2" in " ".join(tokens):
            roles.discard("blue")
            roles.add("green")

    return sorted(roles)


def _spectral_asset_map(assets):
    """Return first raster asset found for each normalized spectral role."""
    mapping = {}
    for asset in assets:
        if not asset.get("is_raster"):
            continue
        for role in asset.get("band_roles") or []:
            mapping.setdefault(role, asset)
    return mapping


def spectral_index_options(assets):
    """Return available spectral index/composite options for parsed assets."""
    mapping = _spectral_asset_map(assets)
    options = []
    for key, definition in _SPECTRAL_DEFINITIONS.items():
        required = definition["requires"]
        missing = [role for role in required if role not in mapping]
        if missing:
            continue
        option = dict(definition)
        option["key"] = key
        option["asset_keys"] = {
            role: mapping[role].get("key") or mapping[role].get("title") or ""
            for role in required
        }
        options.append(option)
    return options


def classify_data_type(feature, parsed_assets, bands_count):
    """Classify a parsed item for result grouping in the UI."""
    props = feature.get("properties") or {}
    context = " ".join(
        str(v or "") for v in (
            feature.get("id"),
            feature.get("collection"),
            props.get("collection"),
            props.get("platform"),
            props.get("constellation"),
            props.get("instruments"),
        )
    ).lower()
    asset_context = " ".join(
        "%s %s" % (a.get("key", ""), a.get("title", ""))
        for a in parsed_assets
    ).lower()
    context = context + " " + asset_context
    roles = set()
    for asset in parsed_assets:
        roles.update(asset.get("band_roles") or [])

    if any(k in context for k in ("naip", "ortho", "orthophoto",
                                  "aerial", "aerofoto")):
        return "orthophoto"
    if any(k in context for k in ("dem", "elevation", "terrain",
                                  "copernicus dem", "srtm")):
        return "dem"
    if any(k in context for k in ("sentinel-1", "sar", "radar", "grd")):
        return "radar"
    if bands_count == 1:
        return "bands_1"
    if bands_count == 2:
        return "bands_2"
    if bands_count == 3:
        return "bands_3"
    if bands_count and bands_count > 3:
        return "multispectral"
    if {"red", "green", "blue"} <= roles:
        return "bands_3"
    if {"red", "nir"} <= roles or len(roles) > 3:
        return "multispectral"
    return "other"


def _is_raster_asset(asset):
    """Return True if an asset dict looks like a raster data asset."""
    mime = (asset.get("type") or "").lower()
    roles = set(r.lower() for r in (asset.get("roles") or []))
    href = (asset.get("href") or "").lower()

    if any(ext in href for ext in _RASTER_EXTENSIONS):
        return True
    if mime in _RASTER_TYPES:
        return True
    if roles & _RASTER_ROLES:
        return True
    return False


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_TIMEOUT = 20
_HEADERS = {
    "User-Agent": "QGIS-STAC-Browser/1.0 (+https://sinocloud.it)",
    "Accept": "application/json",
}
_ALLOWED_SCHEMES = ("http", "https")


def _check_url_scheme(url):
    """Reject non-HTTP(S) URLs to avoid file:// or custom schemes."""
    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError("URL scheme non consentito: %r" % scheme)


def _http_get(url, timeout=_TIMEOUT):
    _check_url_scheme(url)  # rejects file:// and custom schemes
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        return json.loads(resp.read().decode("utf-8"))


def _http_post(url, body, timeout=_TIMEOUT):
    _check_url_scheme(url)  # rejects file:// and custom schemes
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={**_HEADERS, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# stac_search
# ---------------------------------------------------------------------------

def stac_search(
    catalog_url,
    bbox,
    datetime_range=None,
    collections=None,
    cloud_max=None,
    limit=20,
    method="POST",
):
    """
    Search STAC items in the given bounding box.

    Parameters
    ----------
    catalog_url : str
    bbox : list  [west, south, east, north]
    datetime_range : str | None
        e.g. "2023-01-01T00:00:00Z/2023-12-31T23:59:59Z"
    collections : list | None
    cloud_max : float | None      0–100
    limit : int
    method : str   "POST" or "GET"

    Returns
    -------
    dict  {"items": [...], "error": None | str}
    """
    search_url = catalog_url.rstrip("/") + "/search"

    body = {"bbox": bbox, "limit": limit}
    if datetime_range:
        body["datetime"] = datetime_range
    if collections:
        body["collections"] = collections
    if cloud_max is not None:
        body["query"] = {"eo:cloud_cover": {"lte": cloud_max}}

    try:
        if method.upper() == "POST":
            try:
                result = _http_post(search_url, body)
            except urllib.error.HTTPError as exc:
                if exc.code == 405:
                    # fallback to GET
                    result = _search_get(
                        search_url, bbox, datetime_range,
                        collections, cloud_max, limit,
                    )
                else:
                    raise
        else:
            result = _search_get(
                search_url, bbox, datetime_range, collections,
                cloud_max, limit,
            )

        items = result.get("features") or result.get("items") or []
        return {"items": items, "error": None}

    except Exception as exc:
        return {"items": [], "error": str(exc)}


def _search_get(search_url, bbox, datetime_range, collections,
                cloud_max, limit):
    params = {
        "bbox": ",".join(str(v) for v in bbox),
        "limit": str(limit),
    }
    if datetime_range:
        params["datetime"] = datetime_range
    if collections:
        params["collections"] = ",".join(collections)
    url = search_url + "?" + urllib.parse.urlencode(params)
    return _http_get(url)


# ---------------------------------------------------------------------------
# geocode_nominatim — turn an address/place name into a bbox
# ---------------------------------------------------------------------------

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def geocode_nominatim(query, limit=5, timeout=15):
    """
    Geocode a free-text address/place name using OpenStreetMap Nominatim.

    Returns
    -------
    list of dict, each ``{"display_name", "lon", "lat",
    "bbox": (west, south, east, north)}``. An empty list is returned on any
    error or when no match is found.

    Nominatim usage policy: at most ~1 request/second and a descriptive
    User-Agent (sent via ``_HEADERS``).
    """
    query = (query or "").strip()
    if not query:
        return []

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": str(limit),
        "addressdetails": "0",
        "polygon_geojson": "1",
    }
    url = _NOMINATIM_URL + "?" + urllib.parse.urlencode(params)
    try:
        raw = _http_get(url, timeout=timeout)
    except Exception:
        return []

    results = []
    for hit in raw or []:
        try:
            lon = float(hit["lon"])
            lat = float(hit["lat"])
        except (KeyError, ValueError, TypeError):
            continue
        # Nominatim boundingbox = [south, north, west, east] as strings.
        bb = hit.get("boundingbox")
        if bb and len(bb) == 4:
            try:
                south, north, west, east = (float(v) for v in bb)
            except (ValueError, TypeError):
                west = lon - 0.02
                east = lon + 0.02
                south = lat - 0.02
                north = lat + 0.02
        else:
            west, east = lon - 0.02, lon + 0.02
            south, north = lat - 0.02, lat + 0.02
        results.append({
            "display_name": hit.get("display_name") or query,
            "lon": lon,
            "lat": lat,
            "bbox": (west, south, east, north),
            "geojson": hit.get("geojson"),
        })
    return results


def nominatim_polygon(query, timeout=25):
    """
    Fetch the OSM administrative boundary polygon for a place (e.g. a comune).

    Uses Nominatim with ``polygon_geojson=1`` so the geometry comes straight
    from OpenStreetMap boundaries.

    Returns
    -------
    dict | None
        ``{"display_name", "geometry": <GeoJSON geometry in EPSG:4326>,
        "bbox": (w, s, e, n)}`` or ``None`` if nothing usable was found.
    """
    query = (query or "").strip()
    if not query:
        return None
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": "1",
        "polygon_geojson": "1",
    }
    url = _NOMINATIM_URL + "?" + urllib.parse.urlencode(params)
    try:
        raw = _http_get(url, timeout=timeout)
    except Exception:
        return None
    if not raw:
        return None
    hit = raw[0]
    geom = hit.get("geojson")
    if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
        return None
    bb = hit.get("boundingbox")
    bbox = None
    if bb and len(bb) == 4:
        try:
            south, north, west, east = (float(v) for v in bb)
            bbox = (west, south, east, north)
        except (ValueError, TypeError):
            bbox = None
    return {
        "display_name": hit.get("display_name") or query,
        "geometry": geom,
        "bbox": bbox,
    }


# ---------------------------------------------------------------------------
# stac_collections
# ---------------------------------------------------------------------------

def stac_collections(catalog_url, timeout=10):
    """
    Fetch /collections from a STAC catalog.

    Returns
    -------
    list of dict  {"id", "title", "description"}
    """
    url = catalog_url.rstrip("/") + "/collections"
    try:
        result = _http_get(url, timeout=timeout)
        raw = result.get("collections") or []
        return [
            {
                "id": c.get("id", ""),
                "title": c.get("title") or c.get("id", ""),
                "description": c.get("description") or "",
            }
            for c in raw
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# parse_stac_item
# ---------------------------------------------------------------------------

def parse_stac_item(feature, catalog_url="", catalog_name=""):
    """
    Extract a normalised dict from a raw STAC GeoJSON feature.
    """
    props = feature.get("properties") or {}
    assets_raw = feature.get("assets") or {}

    # datetime
    dt = props.get("datetime") or feature.get("datetime") or ""
    start_dt = props.get("start_datetime") or ""
    end_dt = props.get("end_datetime") or ""

    # cloud cover
    cloud = props.get("eo:cloud_cover")
    if cloud is None:
        cloud = props.get("cloud_cover")

    # bands
    eo_bands = props.get("eo:bands") or []
    bands_count = len(eo_bands) if eo_bands else None
    item_band_roles = set()
    for band in eo_bands:
        item_band_roles.update(_spectral_roles_from_band_dict(band))

    # preview / thumbnail
    preview = None
    for key in ("thumbnail", "overview", "rendered_preview", "visual"):
        asset = assets_raw.get(key)
        if asset and asset.get("href"):
            preview = asset["href"]
            break

    # proj:shape
    proj_shape = props.get("proj:shape") or props.get("proj:epsg")

    # Parse assets
    parsed_assets = []
    for key, asset in assets_raw.items():
        href = asset.get("href") or ""
        if not href:
            continue
        atype = asset.get("type") or ""
        roles = asset.get("roles") or []
        title = asset.get("title") or key

        # Attempt to get size
        size_mb = None
        file_info = asset.get("file:size")
        if file_info is not None:
            try:
                size_mb = round(int(file_info) / (1024 * 1024), 1)
            except (ValueError, TypeError):
                pass

        band_roles = _spectral_roles_from_asset(
            key, asset, props.get("platform") or props.get("constellation")
        )
        item_band_roles.update(band_roles)

        parsed_assets.append({
            "key": key,
            "title": title,
            "href": href,
            "type": atype,
            "roles": roles,
            "band_roles": band_roles,
            "size_mb": size_mb,
            "is_raster": _is_raster_asset(
                {"href": href, "type": atype, "roles": roles}
            ),
        })

    # Sort: raster data assets first
    parsed_assets.sort(key=lambda a: (0 if a["is_raster"] else 1, a["key"]))

    data_type = classify_data_type(feature, parsed_assets, bands_count)
    spectral_options = spectral_index_options(parsed_assets)

    return {
        "id": feature.get("id") or "",
        "collection": (
            props.get("collection") or feature.get("collection") or ""
        ),
        "catalog_url": catalog_url,
        "catalog_name": catalog_name,
        "bbox": feature.get("bbox"),
        "datetime": dt,
        "start_datetime": start_dt,
        "end_datetime": end_dt,
        "cloud_cover": cloud,
        "platform": props.get("platform") or props.get("constellation") or "",
        "gsd": props.get("gsd"),
        "proj_shape": proj_shape,
        "bands_count": bands_count,
        "band_roles": sorted(item_band_roles),
        "data_type": data_type,
        "spectral_indices": spectral_options,
        "processing_level": (
            props.get("processing:level") or props.get("processing_level") or
            ""
        ),
        "preview": preview,
        "assets": parsed_assets,
    }


# ---------------------------------------------------------------------------
# Best raster asset selector
# ---------------------------------------------------------------------------

def best_raster_asset(parsed_item):
    """
    Return the best raster asset dict from a parsed STAC item, or None.
    Priority: data > visual > overview > any raster.
    """
    assets = parsed_item.get("assets") or []
    for role_pref in ("data", "visual", "overview", "analytic"):
        for a in assets:
            if a.get("is_raster") and role_pref in (a.get("roles") or []):
                return a
    # fallback: first raster asset
    for a in assets:
        if a.get("is_raster"):
            return a
    return None


# ---------------------------------------------------------------------------
# Microsoft Planetary Computer — automatic (login-free) SAS signing
# ---------------------------------------------------------------------------

_PC_SIGN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"


def sign_href_if_needed(href):
    """
    Return an href usable without a login.

    Microsoft Planetary Computer assets live on Azure Blob Storage
    (``*.blob.core.windows.net``) and need a short-lived SAS token, granted
    for free and without authentication by the PC ``/sign`` endpoint. This
    helper signs such hrefs transparently; for any other host, or on error,
    the original href is returned unchanged.
    """
    if not href:
        return href
    low = href.lower()
    if "blob.core.windows.net" not in low:
        return href
    if "sig=" in low and ("st=" in low or "se=" in low):
        return href  # already signed
    try:
        url = _PC_SIGN_URL + "?href=" + urllib.parse.quote(href, safe="")
        data = _http_get(url, timeout=15)
        return data.get("href") or href
    except Exception:
        return href


def _looks_like_html_or_login(content_type, first_bytes=b""):
    """Heuristic: did the server hand us a web/login page instead of a file?"""
    ct = (content_type or "").lower()
    if ct.startswith("text/html") or ct.startswith("application/xhtml"):
        return True
    head = first_bytes[:512].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


# ---------------------------------------------------------------------------
# load_raster_to_qgis
# ---------------------------------------------------------------------------

def load_raster_to_qgis(href, layer_name):
    """
    Load a remote raster in QGIS via /vsicurl/.

    Returns a QgsRasterLayer (not yet added to the project).
    """
    if not _HAS_QGIS:
        raise ImportError("QgsRasterLayer not available outside QGIS.")

    href = sign_href_if_needed(href)

    vsicurl_href = href
    if href.startswith("http://") or href.startswith("https://"):
        lower = href.lower()
        if any(lower.endswith(ext) for ext in _RASTER_EXTENSIONS) or \
                not vsicurl_href.startswith("/vsicurl/"):
            vsicurl_href = "/vsicurl/" + href

    layer = QgsRasterLayer(vsicurl_href, layer_name)
    return layer


# ---------------------------------------------------------------------------
# download_asset
# ---------------------------------------------------------------------------

def catalog_by_url(catalog_url):
    """Return the catalog registry entry matching a STAC root URL, or None."""
    root = (catalog_url or "").rstrip("/")
    for c in STAC_CATALOGS:
        if c["url"].rstrip("/") == root:
            return c
    return None


def download_asset(href, output_path, progress_callback=None, auth=None):
    """
    Download an asset to ``output_path``.

    The href is signed automatically when needed (Planetary Computer). Optional
    ``auth`` is a dict ``{"token": ..., "username": ..., "password":
    ...}`` used
    only for catalogs that require a free registration: a token is sent as
    ``Authorization: Bearer``, username/password enable HTTP Basic/Digest auth.

    If the server still returns an HTML page instead of the file — typically a
    login/error page — no bogus file is written and a clear error is raised.

    progress_callback(bytes_done, bytes_total) is called every 64 KB.
    bytes_total may be 0 if Content-Length is unavailable.
    """
    href = sign_href_if_needed(href)
    _check_url_scheme(href)  # rejects file:// and custom schemes
    auth = auth or {}
    has_credentials = any(
        (auth.get(k) or "").strip()
        for k in ("token", "api_key", "username", "password")
    )
    if has_credentials and not href.lower().startswith("https://"):
        raise ValueError(
            "Credenziali su URL non-HTTPS rifiutate per sicurezza. / "
            "Credentials over a non-HTTPS URL were refused for security."
        )
    headers = dict(_HEADERS)
    token = (auth.get("token") or "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    api_key = (auth.get("api_key") or "").strip()
    if api_key:
        # Provider-dependent; sent best-effort as a common API-key header.
        headers["X-Api-Key"] = api_key

    opener = None
    user = (auth.get("username") or "").strip()
    pwd = auth.get("password") or ""
    if user and pwd:
        mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        mgr.add_password(None, href, user, pwd)
        opener = urllib.request.build_opener(
            urllib.request.HTTPBasicAuthHandler(mgr),
            urllib.request.HTTPDigestAuthHandler(mgr),
        )

    req = urllib.request.Request(href, headers=headers)
    open_fn = opener.open if opener else urllib.request.urlopen
    chunk_size = 64 * 1024  # 64 KB

    with open_fn(req, timeout=120) as resp:  # nosec B310
        content_type = resp.headers.get("Content-Type", "")
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        first_chunk = resp.read(chunk_size)

        if _looks_like_html_or_login(content_type, first_chunk):
            raise ValueError(
                "Il server ha restituito una pagina HTML (login o errore) "
                "invece del file: questo asset richiede l'autenticazione "
                "presso il provider (es. USGS EROS / NASA EarthData / "
                "Copernicus). / The server returned an HTML page (login or "
                "error) instead of the file: this asset requires "
                "authentication with the data provider."
            )

        with open(output_path, "wb") as out_f:
            while first_chunk:
                out_f.write(first_chunk)
                done += len(first_chunk)
                if progress_callback:
                    progress_callback(done, total)
                first_chunk = resp.read(chunk_size)


# ---------------------------------------------------------------------------
# clip_raster — clip a (possibly remote) raster to a cutline polygon
# ---------------------------------------------------------------------------

def clip_raster(src_href, cutline_path, out_path, progress_callback=None):
    """
    Clip a raster to the polygon stored (as GeoJSON, EPSG:4326) in
    ``cutline_path`` and write a GeoTIFF to ``out_path``.

    The source can be a remote COG: it is signed when needed and read through
    GDAL ``/vsicurl/`` so only the pixels inside the cutline are fetched.

    progress_callback(percent_0_100, 100) is called as the warp proceeds.
    """
    if not _HAS_GDAL:
        raise ImportError(
            "GDAL (osgeo) non disponibile per il ritaglio. / "
            "GDAL (osgeo) is not available for clipping."
        )

    src = sign_href_if_needed(src_href)
    if src.startswith("http://") or src.startswith("https://"):
        if not src.startswith("/vsicurl/"):
            src = "/vsicurl/" + src

    def _cb(complete, _msg, _data):
        if progress_callback:
            progress_callback(int(complete * 100), 100)
        return 1

    gdal.UseExceptions()
    options = gdal.WarpOptions(
        format="GTiff",
        cutlineDSName=cutline_path,
        cutlineSRS="EPSG:4326",
        cropToCutline=True,
        dstNodata=0,
        creationOptions=["COMPRESS=DEFLATE", "TILED=YES"],
        callback=_cb,
    )
    ds = gdal.Warp(out_path, src, options=options)
    if ds is None:
        raise RuntimeError("Ritaglio fallito / clip failed.")
    ds = None
    return out_path
