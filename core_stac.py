# -*- coding: utf-8 -*-
# Copyright (C) 2024 Dott. Sarino Alfonso Grande <sino.grande@gmail.com>
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
        "description": "Sentinel-2, Landsat, MODIS, NAIP, DEM, permafrost e molto altro",
        "license": "Dati dipendono dalla collezione. Molti sono CC BY 4.0 o Public Domain.",
        "license_url": "https://planetarycomputer.microsoft.com/terms",
        "auth": False,
        "search_method": "POST",
        "note": "Il download degli asset richiede token SAS gratuito per alcuni dataset.",
    },
    {
        "id": "usgs-landsat",
        "name": "USGS LandsatLook",
        "url": "https://landsatlook.usgs.gov/stac-server",
        "site_url": "https://www.usgs.gov/landsat-missions",
        "description": "Landsat Collection 2 (Landsat 5, 7, 8, 9)",
        "license": "Public Domain — USGS/NASA.",
        "license_url": "https://www.usgs.gov/information-policies-and-instructions/crediting-usgs",
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
        "description": "Archivio NASA: MODIS, VIIRS, ASTER, OCO-2, e centinaia di altri dataset",
        "license": (
            "Dati NASA: Public Domain. Alcuni dataset richiedono "
            "registrazione EarthData gratuita per il download."
        ),
        "license_url": ("https://www.earthdata.nasa.gov/engage/"
                        "open-data-services-and-software/data-information-policy"),
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


def _http_get(url, timeout=_TIMEOUT):
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post(url, body, timeout=_TIMEOUT):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={**_HEADERS, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
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
    datetime_range : str | None   e.g. "2023-01-01T00:00:00Z/2023-12-31T23:59:59Z"
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
            result = _search_get(search_url, bbox, datetime_range, collections, cloud_max, limit)

        items = result.get("features") or result.get("items") or []
        return {"items": items, "error": None}

    except Exception as exc:
        return {"items": [], "error": str(exc)}


def _search_get(search_url, bbox, datetime_range, collections, cloud_max, limit):
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

        parsed_assets.append({
            "key": key,
            "title": title,
            "href": href,
            "type": atype,
            "roles": roles,
            "size_mb": size_mb,
            "is_raster": _is_raster_asset({"href": href, "type": atype, "roles": roles}),
        })

    # Sort: raster data assets first
    parsed_assets.sort(key=lambda a: (0 if a["is_raster"] else 1, a["key"]))

    return {
        "id": feature.get("id") or "",
        "collection": props.get("collection") or feature.get("collection") or "",
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
        "processing_level": props.get("processing:level") or props.get("processing_level") or "",
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
    ``auth`` is a dict ``{"token": ..., "username": ..., "password": ...}`` used
    only for catalogs that require a free registration: a token is sent as
    ``Authorization: Bearer``, username/password enable HTTP Basic/Digest auth.

    If the server still returns an HTML page instead of the file — typically a
    login/error page — no bogus file is written and a clear error is raised.

    progress_callback(bytes_done, bytes_total) is called every 64 KB.
    bytes_total may be 0 if Content-Length is unavailable.
    """
    href = sign_href_if_needed(href)
    auth = auth or {}
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

    with open_fn(req, timeout=120) as resp:
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
