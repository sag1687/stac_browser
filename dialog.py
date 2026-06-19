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
dialog.py — Main dialog for the STAC Browser QGIS plugin.

Three tabs:
  0. Ricerca / Search
  1. Risultati / Results
  2. ℹ Info
"""

import os

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QSpinBox, QWidget, QTabWidget,
    QCheckBox, QProgressBar, QGroupBox,
    QListWidget, QListWidgetItem, QTextBrowser,
    QScrollArea, QFrame, QGridLayout,
    QFileDialog, QDateEdit, QMessageBox, QLineEdit,
    QGraphicsOpacityEffect,
)
from qgis.PyQt.QtCore import (
    Qt, QSize, QThread, pyqtSignal, QDate, QTimer, QUrl,
)
from qgis.PyQt.QtGui import QFont, QPixmap, QDesktopServices, QIcon

try:
    from qgis.core import (
        QgsProject, QgsRectangle, QgsCoordinateTransform,
        QgsCoordinateReferenceSystem, QgsGeometry, QgsVectorLayer,
        QgsRasterLayer,
    )
    _HAS_QGIS = True
except ImportError:
    _HAS_QGIS = False

try:
    from qgis.utils import iface as _iface
except ImportError:
    _iface = None

from .qt_compat import ensure_qt_compat, QtCompat
from .core_stac import (
    STAC_CATALOGS, stac_search, stac_collections, geocode_nominatim,
    nominatim_polygon, parse_stac_item, best_raster_asset,
    load_raster_to_qgis, download_asset, clip_raster,
)

try:
    from qgis.core import QgsSettings
except ImportError:
    QgsSettings = None

ensure_qt_compat(Qt)


# ---------------------------------------------------------------------------
# Translation helper
# ---------------------------------------------------------------------------

def _t(lang, it, en):
    """Return Italian or English string based on lang ('it' or 'en')."""
    return en if lang == "en" else it


# ---------------------------------------------------------------------------
# Dark stylesheet
# ---------------------------------------------------------------------------

OCEAN_STYLE = """
QDialog {
    background-color: #020e1a;
    color: #d0f0ff;
    font-family: 'Segoe UI', 'Inter', 'Roboto', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 13px;
}
QWidget { background-color: #020e1a; color: #d0f0ff; }
QLabel { color: #7ac8d8; font-size: 13px; }
QGroupBox {
    border: 1px solid #0a4a6e;
    border-radius: 8px;
    margin-top: 10px;
    padding: 12px 10px;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #071c2e,stop:1 #020e1a);
    color: #d0f0ff;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #00e5ff;
    font-size: 12px;
}
QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #006688,stop:1 #004455);
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 700;
    font-size: 12px;
}
QPushButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #0099bb,stop:1 #006688);
    color: #d0f0ff;
}
QPushButton:pressed { background: #004455; }
QPushButton:disabled { background: #071c2e; color: #4a8090; border-color: #0a3a58; }
QPushButton#btnLang {
    background: #071c2e;
    color: #7ac8d8;
    border: 1px solid #0a4a6e;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
    border-radius: 4px;
}
QPushButton#btnLang:hover { background: #0d2d42; color: #00e5ff; }
QPushButton#btnClose {
    background: #071c2e;
    color: #7ac8d8;
    border: 1px solid #0a4a6e;
}
QPushButton#btnClose:hover { background: #0d2d42; color: #d0f0ff; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QDateEdit {
    padding: 5px 8px;
    border: 1px solid #0a4a6e;
    border-radius: 5px;
    background: #071c2e;
    color: #d0f0ff;
    selection-background-color: #0a4a6e;
}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QLineEdit:focus, QDateEdit:focus {
    border-color: #00e5ff;
}
QComboBox::drop-down { border: none; padding-right: 6px; }
QTabWidget::pane {
    border: 1px solid #0a4a6e;
    border-radius: 6px;
    top: -1px;
    background: #020e1a;
}
QTabBar::tab {
    background: #071c2e;
    border: 1px solid #0a4a6e;
    padding: 7px 14px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #4a8090;
    font-size: 12px;
}
QTabBar::tab:selected {
    background: #020e1a;
    border-bottom-color: #020e1a;
    font-weight: bold;
    color: #00e5ff;
}
QTabBar::tab:hover:!selected { background: #0d2d42; color: #7ac8d8; }
QProgressBar {
    border: 1px solid #0a4a6e;
    border-radius: 4px;
    height: 6px;
    background: #071c2e;
    color: transparent;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0099bb,stop:1 #00e5ff);
    border-radius: 3px;
}
QCheckBox { color: #7ac8d8; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 3px;
    border: 1px solid #0a4a6e;
    background: #071c2e;
}
QCheckBox::indicator:checked { background: #00e5ff; border-color: #00e5ff; }
QListWidget {
    background: #071c2e;
    border: 1px solid #0a4a6e;
    border-radius: 5px;
    color: #d0f0ff;
    font-size: 12px;
}
QListWidget::item { padding: 5px 8px; }
QListWidget::item:selected { background: #0a4a6e; color: #00e5ff; }
QListWidget::item:hover { background: #0d2d42; }
QTextBrowser {
    background: #071c2e;
    border: 1px solid #0a4a6e;
    border-radius: 5px;
    color: #7ac8d8;
    font-size: 12px;
}
QScrollArea { background: #020e1a; border: none; }
QScrollBar:vertical, QScrollBar:horizontal {
    background: #071c2e;
    border: none;
    width: 8px; height: 8px;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #0a4a6e;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: #00e5ff;
}
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QFrame { background: transparent; }
"""

# ---------------------------------------------------------------------------
# Info tab HTML
# ---------------------------------------------------------------------------

INFO_HTML = """
<html>
<head>
<style>
  body { background:#020e1a; color:#d0f0ff;
         font-family:'Segoe UI',Arial,sans-serif;
         font-size:12px; margin:16px; line-height:1.6; }
  h2   { color:#00e5ff; font-size:15px; margin:0 0 12px;
         border-bottom:1px solid #0d2d42; padding-bottom:6px; }
  h3   { color:#60a5fa; font-size:13px; margin:16px 0 6px; }
  h4   { color:#f59e0b; font-size:12px; margin:12px 0 4px; }
  p, li { margin:3px 0; color:#7ac8d8; }
  a    { color:#00e5ff; }
  code { background:#0d2d42; padding:1px 4px; border-radius:3px; font-family:monospace; }
  table { border-collapse:collapse; width:100%; margin:8px 0; }
  th   { background:#0d2d42; color:#7ac8d8; padding:6px 10px; text-align:left;
         border-bottom:2px solid #0a4a6e; font-size:11px; }
  td   { padding:5px 10px; border-bottom:1px solid #0d2d42; color:#d0f0ff; }
  tr:nth-child(even) td { background:rgba(7,28,46,0.5); }
  .badge-warn { background:rgba(239,68,68,0.15); color:#ef4444; padding:1px 6px;
                border-radius:8px; font-size:11px; font-weight:600; }
  .badge-ok   { background:rgba(34,197,94,0.15); color:#22c55e; padding:1px 6px;
                border-radius:8px; font-size:11px; font-weight:600; }
  .section-sep { border:none; border-top:1px solid #0d2d42; margin:16px 0; }
</style>
</head>
<body>

<h2>STAC BROWSER &mdash; INFORMAZIONI / INFORMATION</h2>

<h3>IL PLUGIN È UN FACILITATORE / THE PLUGIN IS A FACILITATOR</h3>
<p><b>IT:</b> STAC Browser <b>non ospita né rivende dati</b>. È solo uno
strumento che ti aiuta a <i>trovare</i> e <i>scaricare</i> dati gi&agrave;
pubblicati dai provider ufficiali (ESA, NASA, USGS, Microsoft, ecc.). I dati
restano di propriet&agrave; e responsabilit&agrave; dei rispettivi provider e
sono soggetti alle <b>loro licenze</b>: leggile sempre prima dell'uso e cita
la fonte richiesta.</p>
<p><b>EN:</b> STAC Browser <b>does not host or resell data</b>. It only helps
you <i>find</i> and <i>download</i> data already published by the official
providers (ESA, NASA, USGS, Microsoft, etc.). The data remains owned by and is
the responsibility of those providers and is subject to <b>their licenses</b>:
always read them before use and give the required attribution.</p>

<h3>FONTI LIBERE E FONTI CON REGISTRAZIONE / OPEN vs REGISTERED SOURCES</h3>
<table>
  <tr><th>Tipo / Type</th><th>Cataloghi / Catalogs</th><th>Download</th></tr>
  <tr><td><span class="badge-ok">Libero / Open</span></td>
      <td>Element84 Earth Search, Microsoft Planetary Computer (firma SAS
      automatica), OpenLandMap, US GeoPlatform, Digital Earth Australia</td>
      <td>Automatico, nessun login / Automatic, no login</td></tr>
  <tr><td><span class="badge-warn">Registrazione / Registration</span></td>
      <td>USGS LandsatLook (EROS), NASA EarthData CMR, Copernicus Data
      Space</td>
      <td>Richiede account gratuito / Requires free account</td></tr>
</table>
<p><b>IT:</b> per impostazione predefinita il plugin scarica automaticamente
solo dalle fonti libere. Per i cataloghi che richiedono registrazione, sulla
scheda compare il pulsante <code>🔐 Registrazione richiesta</code> che apre il
<b>sito ufficiale</b>; dopo esserti registrato inserisci utente/password o
token nel tab <code>🔐 Account</code> (le credenziali sono salvate solo in
locale). Quando GDAL riceve una pagina di login al posto del file, il plugin
<b>non salva file fasulli</b> e te lo segnala.</p>
<p><b>EN:</b> by default the plugin auto-downloads only from open sources. For
catalogs that need registration, the card shows a
<code>🔐 Registration required</code> button that opens the <b>official
site</b>; after registering, enter username/password or token in the
<code>🔐 Account</code> tab (credentials are stored locally only). When GDAL
gets a login page instead of the file, the plugin <b>never saves bogus
files</b> and tells you.</p>

<h3>RITAGLIO / CLIPPING</h3>
<p><b>IT:</b> nel tab <code>🔍 Ricerca</code>, gruppo <b>Output</b>, scegli
<code>📦 Dataset completo</code> oppure <code>✂️ Ritaglio automatico</code>.
Per il ritaglio il confine pu&ograve; essere il <b>limite comunale OSM</b>
(digiti il nome del comune, geometria presa da OpenStreetMap via Nominatim)
oppure la <b>geometria del layer/selezione attiva</b> in QGIS. Il ritaglio
legge direttamente il COG remoto via GDAL <code>/vsicurl/</code>, quindi
scarica solo i pixel nell'area scelta.</p>
<p><b>EN:</b> in the <code>🔍 Search</code> tab, <b>Output</b> group, pick
<code>📦 Full dataset</code> or <code>✂️ Automatic clip</code>. The clip
boundary can be the <b>OSM municipal boundary</b> (type the municipality name,
geometry from OpenStreetMap via Nominatim) or the <b>geometry of the active
QGIS layer/selection</b>. Clipping reads the remote COG directly through GDAL
<code>/vsicurl/</code>, fetching only the pixels inside the chosen area.</p>

<h3>CATALOGHI INCLUSI / INCLUDED CATALOGS</h3>

<h4>1. Element84 Earth Search</h4>
<table>
  <tr><th>URL</th><td>
      <a href="https://earth-search.aws.element84.com/v1"
      >earth-search.aws.element84.com/v1</a></td></tr>
  <tr><th>Dati / Data</th><td>Sentinel-2 L2A, Landsat Collection 2, NAIP, Copernicus DEM</td></tr>
  <tr><th>Licenza / License</th>
      <td>Sentinel-2: CC BY 4.0 (Copernicus/ESA). Landsat: Public Domain (USGS/NASA).</td></tr>
  <tr><th>Limiti / Limits</th><td>
      <span class="badge-ok">Nessun limite esplicito (AWS, fair use)</span></td></tr>
</table>

<h4>2. Microsoft Planetary Computer</h4>
<table>
  <tr><th>URL</th>
      <td><a href="https://planetarycomputer.microsoft.com/api/stac/v1"
      >planetarycomputer.microsoft.com/api/stac/v1</a></td></tr>
  <tr><th>Dati / Data</th>
      <td>Sentinel-2, Landsat, MODIS, NAIP, DEM, permafrost e molto altro</td></tr>
  <tr><th>Licenza / License</th>
      <td>Dipende dalla collezione. Molti CC BY 4.0 o Public Domain.</td></tr>
  <tr><th>Note</th>
      <td>Download asset può richiedere token SAS gratuito per alcuni dataset.</td></tr>
  <tr><th>Limiti / Limits</th>
      <td><span class="badge-ok">Nessun limite per la ricerca</span></td></tr>
</table>

<h4>3. USGS LandsatLook</h4>
<table>
  <tr><th>URL</th><td><a href="https://landsatlook.usgs.gov/stac-server"
      >landsatlook.usgs.gov/stac-server</a></td></tr>
  <tr><th>Dati / Data</th><td>Landsat Collection 2 (Landsat 5, 7, 8, 9)</td></tr>
  <tr><th>Licenza / License</th><td>Public Domain &mdash; USGS/NASA.</td></tr>
  <tr><th>Limiti / Limits</th><td>
      <span class="badge-ok">Nessun limite esplicito (US Gov)</span></td></tr>
</table>

<h4>4. NASA EarthData CMR</h4>
<table>
  <tr><th>URL</th><td><a href="https://cmr.earthdata.nasa.gov/stac"
      >cmr.earthdata.nasa.gov/stac</a></td></tr>
  <tr><th>Dati / Data</th><td>MODIS, VIIRS, ASTER, OCO-2, centinaia di dataset NASA</td></tr>
  <tr><th>Licenza / License</th>
      <td>Public Domain. Alcuni dataset richiedono registrazione EarthData gratuita.</td></tr>
  <tr><th>Limiti / Limits</th><td><span class="badge-ok">Ricerca libera</span></td></tr>
</table>

<h4>5. OpenLandMap</h4>
<table>
  <tr><th>URL</th><td><a href="https://openlandmap.github.io/stac"
      >openlandmap.github.io/stac</a></td></tr>
  <tr><th>Dati / Data</th><td>Variabili pedologiche, vegetazione, clima globale</td></tr>
  <tr><th>Licenza / License</th><td>CC BY 4.0</td></tr>
  <tr><th>Limiti / Limits</th><td>
      <span class="badge-warn">~100 req/giorno (fair use)</span></td></tr>
</table>

<h4>6. US GeoPlatform</h4>
<table>
  <tr><th>URL</th><td><a href="https://stac.geoplatform.gov">stac.geoplatform.gov</a></td></tr>
  <tr><th>Dati / Data</th><td>Dataset geospaziali federali USA</td></tr>
  <tr><th>Licenza / License</th><td>Public Domain (US Government)</td></tr>
  <tr><th>Limiti / Limits</th><td><span class="badge-ok">Nessun limite esplicito</span></td></tr>
</table>

<h4>7. Copernicus Data Space</h4>
<table>
  <tr><th>URL</th><td>
      <a href="https://catalogue.dataspace.copernicus.eu/stac"
      >catalogue.dataspace.copernicus.eu/stac</a></td></tr>
  <tr><th>Dati / Data</th><td>Sentinel-1, Sentinel-2, Sentinel-3, Sentinel-5P</td></tr>
  <tr><th>Licenza / License</th><td>CC BY 4.0 &mdash; Copernicus Programme / ESA</td></tr>
  <tr><th>Note</th><td>Download richiede registrazione gratuita su
      <a href="https://dataspace.copernicus.eu">dataspace.copernicus.eu</a></td></tr>
  <tr><th>Limiti / Limits</th><td><span class="badge-ok">Ricerca libera</span></td></tr>
</table>

<h4>8. Digital Earth Australia</h4>
<table>
  <tr><th>URL</th><td><a href="https://explorer.dea.ga.gov.au/stac"
      >explorer.dea.ga.gov.au/stac</a></td></tr>
  <tr><th>Dati / Data</th><td>Landsat e Sentinel elaborati su Australia</td></tr>
  <tr><th>Licenza / License</th><td>CC BY 4.0 &mdash; Geoscience Australia</td></tr>
  <tr><th>Limiti / Limits</th><td><span class="badge-ok">Nessun limite esplicito</span></td></tr>
</table>

<hr class="section-sep"/>
<h3>STANDARD STAC</h3>
<p>STAC (SpatioTemporal Asset Catalog) &egrave; uno standard aperto per la catalogazione
di dati geospaziali. Versione corrente: <strong>1.0.0</strong>.<br>
Sito ufficiale: <a href="https://stacspec.org">https://stacspec.org</a></p>

<hr class="section-sep"/>
<h3>ATTRIBUZIONE RICHIESTA / ATTRIBUTION REQUIRED</h3>
<ul>
  <li><b>Sentinel:</b> "Contains modified Copernicus Sentinel data [anno] / ESA"</li>
  <li><b>Landsat:</b> "Courtesy of the U.S. Geological Survey"</li>
  <li><b>OpenLandMap:</b> "&copy; OpenLandMap contributors, CC BY 4.0"</li>
  <li><b>DEA:</b> "&copy; Commonwealth of Australia (Geoscience Australia), CC BY 4.0"</li>
</ul>

<hr class="section-sep"/>
<h3>NOTE TECNICHE / TECHNICAL NOTES</h3>
<ul>
  <li>Il plugin usa <code>/vsicurl/</code> di GDAL/OGR per aprire raster remoti
      direttamente in QGIS senza scaricare l'intero file.</li>
  <li>File GeoTIFF cloud-optimized (COG) sono supportati nativamente.</li>
  <li>NetCDF, HDF5 e JPEG2000 potrebbero richiedere driver GDAL aggiuntivi.</li>
  <li>Per file molto grandi (&gt;1 GB), si raccomanda il download prima dell'apertura.</li>
</ul>

<hr class="section-sep"/>
<h3>ALTRI PLUGIN DELL'AUTORE / OTHER PLUGINS BY THE AUTHOR</h3>
<ul>
  <li><b>Profili, Sezioni e Comuni</b> &mdash; Profili altimetrici e sezioni trasversali</li>
  <li><b>Q-Press</b> &mdash; Generatore PDF cartografico professionale</li>
  <li><b>QGIS Ledger</b> &mdash; Raccolta dati field con sync NextCloud</li>
  <li><b>Geobridge</b> &mdash; Conversione coordinate geodetiche e trasformazioni di datum</li>
  <li><b>CRS Fixer</b> &mdash; Correzione automatica CRS layer</li>
  <li><b>GeoCSV Mapper</b> &mdash; Importazione CSV geografici avanzata</li>
  <li><b>GeoFusion WebGIS</b> &mdash; Piattaforma WebGIS open source &mdash;
      <a href="https://sinocloud.it">sinocloud.it</a></li>
</ul>
<p>Autore: Dott. Sarino Alfonso Grande &nbsp;|&nbsp;
   <a href="mailto:sino.grande@gmail.com">sino.grande@gmail.com</a> &nbsp;|&nbsp;
   <a href="https://sinocloud.it">sinocloud.it</a></p>

<hr class="section-sep"/>
<h3>LICENZA PLUGIN / PLUGIN LICENSE</h3>
<p>GPL-2.0 &mdash; Copyright (C) 2024 Dott. Sarino Alfonso Grande<br>
Questo plugin &egrave; software libero: puoi redistribuirlo e/o modificarlo
secondo i termini della GNU General Public License versione 2.<br>
This plugin is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License version 2.</p>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Worker thread for STAC searches
# ---------------------------------------------------------------------------

class StacSearchWorker(QThread):
    """
    Searches multiple STAC catalogs in a background thread.
    Emits catalogResult for each catalog (success or error).
    """

    catalogResult = pyqtSignal(str, list, str)   # catalog_id, items, error
    catalogStarted = pyqtSignal(str, str)         # catalog_id, catalog_name
    finished = pyqtSignal()

    def __init__(self, catalogs, bbox, datetime_range=None,
                 collections=None, cloud_max=None, limit=20, parent=None):
        super().__init__(parent)
        self.catalogs = catalogs
        self.bbox = bbox
        self.datetime_range = datetime_range
        self.collections = collections
        self.cloud_max = cloud_max
        self.limit = limit
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        for cat in self.catalogs:
            if self._cancelled:
                break
            self.catalogStarted.emit(cat["id"], cat["name"])
            result = stac_search(
                catalog_url=cat["url"],
                bbox=self.bbox,
                datetime_range=self.datetime_range,
                collections=self.collections,
                cloud_max=self.cloud_max,
                limit=self.limit,
                method=cat.get("search_method", "POST"),
            )
            # Attach catalog metadata to each item for later use
            parsed = []
            for feat in result.get("items") or []:
                parsed.append(parse_stac_item(feat, cat["url"], cat["name"]))
            self.catalogResult.emit(cat["id"], parsed, result.get("error") or "")
        self.finished.emit()


# ---------------------------------------------------------------------------
# Geocoding worker (Nominatim) — runs off the UI thread
# ---------------------------------------------------------------------------

class GeocodeWorker(QThread):
    """Resolve an address/place name to candidate bboxes via Nominatim."""

    resultReady = pyqtSignal(list)   # list of geocode dicts

    def __init__(self, query, parent=None):
        super().__init__(parent)
        self.query = query

    def run(self):
        try:
            results = geocode_nominatim(self.query)
        except Exception:
            results = []
        self.resultReady.emit(results)


# ---------------------------------------------------------------------------
# Preview image fetcher (background thread)
# ---------------------------------------------------------------------------

class PreviewFetcher(QThread):
    """Fetch a single preview image from URL, emit pixmap when done."""

    pixmapReady = pyqtSignal(str, object)   # url, QPixmap

    def __init__(self, url, cache, parent=None):
        super().__init__(parent)
        self.url = url
        self.cache = cache

    def run(self):
        import urllib.request
        try:
            req = urllib.request.Request(
                self.url,
                headers={"User-Agent": "QGIS-STAC-Browser/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                self.cache[self.url] = pixmap
                self.pixmapReady.emit(self.url, pixmap)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Download worker
# ---------------------------------------------------------------------------

class DownloadWorker(QThread):
    progress = pyqtSignal(int, int)   # bytes_done, bytes_total
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, href, output_path, auth=None, parent=None):
        super().__init__(parent)
        self.href = href
        self.output_path = output_path
        self.auth = auth

    def run(self):
        try:
            download_asset(
                self.href,
                self.output_path,
                progress_callback=lambda done, total: self.progress.emit(done, total),
                auth=self.auth,
            )
            self.finished.emit(True, self.output_path)
        except Exception as exc:
            self.finished.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Clip processing worker (boundary fetch + GDAL warp)
# ---------------------------------------------------------------------------

class ClipWorker(QThread):
    """
    Clip a (remote) raster to a polygon and write a GeoTIFF.

    The cutline is either an OSM municipal boundary fetched from Nominatim
    (``comune_query``) or a GeoJSON geometry already extracted from a QGIS
    layer (``cutline_geojson``), both in EPSG:4326.
    """

    progress = pyqtSignal(int, int)   # percent, 100
    finished = pyqtSignal(bool, str)  # success, path or error message

    def __init__(self, href, output_path, auth=None,
                 comune_query="", cutline_geojson="", parent=None):
        super().__init__(parent)
        self.href = href
        self.output_path = output_path
        self.auth = auth
        self.comune_query = comune_query
        self.cutline_geojson = cutline_geojson

    def run(self):
        import json
        import tempfile
        try:
            geojson = self.cutline_geojson
            if not geojson and self.comune_query:
                self.progress.emit(2, 100)
                bnd = nominatim_polygon(self.comune_query)
                if not bnd:
                    self.finished.emit(
                        False,
                        "Confine comunale non trovato su OSM/Nominatim. / "
                        "Municipal boundary not found on OSM/Nominatim."
                    )
                    return
                geojson = json.dumps(bnd["geometry"])
            if not geojson:
                self.finished.emit(
                    False,
                    "Nessun confine di ritaglio disponibile. / "
                    "No clip boundary available."
                )
                return

            # Wrap a bare geometry into a FeatureCollection for OGR/GDAL.
            geom = json.loads(geojson)
            if geom.get("type") not in ("FeatureCollection", "Feature"):
                fc = {"type": "FeatureCollection", "features": [
                    {"type": "Feature", "properties": {}, "geometry": geom}
                ]}
            else:
                fc = geom

            tmp = tempfile.NamedTemporaryFile(
                suffix=".geojson", delete=False, mode="w", encoding="utf-8"
            )
            json.dump(fc, tmp)
            tmp.close()

            clip_raster(
                self.href, tmp.name, self.output_path,
                progress_callback=lambda p, t: self.progress.emit(p, t),
            )
            self.finished.emit(True, self.output_path)
        except Exception as exc:
            self.finished.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Item card widget
# ---------------------------------------------------------------------------

class ItemCard(QFrame):
    """A compact card widget showing a single STAC item."""

    def __init__(self, item, lang="it", preview_cache=None,
                 catalog=None, auth=None, controller=None, parent=None):
        super().__init__(parent)
        self.item = item
        self.lang = lang
        self.preview_cache = preview_cache if preview_cache is not None else {}
        self.catalog = catalog or {}
        self.auth = auth or {}
        self.controller = controller
        self._preview_label = None
        self._fetcher = None

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            ItemCard {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #0d2d42, stop:1 #020e1a);
                border: 1px solid #0a4a6e;
                border-radius: 10px;
            }
            ItemCard:hover { border-color: #0099bb; }
        """)
        self.setFixedWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Preview image
        self._preview_label = QLabel()
        self._preview_label.setFixedSize(224, 112)
        self._preview_label.setStyleSheet(
            "background:#020e1a; border-radius:6px; border:1px solid #0a4a6e;"
        )
        self._preview_label.setAlignment(QtCompat.AlignCenter)
        self._preview_label.setText("🛰️")
        layout.addWidget(self._preview_label)

        # Collection badge
        collection = item.get("collection") or item.get("catalog_name") or ""
        if collection:
            lbl_col = QLabel(collection)
            lbl_col.setStyleSheet(
                "background:rgba(52,211,153,0.12); color:#00e5ff; padding:2px 8px;"
                "border-radius:8px; font-size:10px; font-weight:600;"
            )
            lbl_col.setAlignment(QtCompat.AlignCenter)
            layout.addWidget(lbl_col)

        # Item ID (truncated)
        item_id = item.get("id") or "—"
        lbl_id = QLabel(item_id)
        lbl_id.setStyleSheet("color:#d0f0ff; font-size:11px; font-weight:600;")
        lbl_id.setToolTip(item_id)
        lbl_id.setMaximumWidth(224)
        fm = lbl_id.fontMetrics()
        elided = fm.elidedText(item_id, QtCompat.ElideRight, 220)
        lbl_id.setText(elided)
        layout.addWidget(lbl_id)

        # Date + cloud
        dt = item.get("datetime") or item.get("start_datetime") or ""
        if dt:
            dt = dt[:10]  # YYYY-MM-DD
        cloud = item.get("cloud_cover")
        meta_parts = []
        if dt:
            meta_parts.append(f"📅 {dt}")
        if cloud is not None:
            try:
                meta_parts.append(f"☁ {float(cloud):.0f}%")
            except (ValueError, TypeError):
                pass
        if meta_parts:
            lbl_meta = QLabel("  ".join(meta_parts))
            lbl_meta.setStyleSheet("color:#7ac8d8; font-size:11px;")
            layout.addWidget(lbl_meta)

        # Metrics row
        metrics = []
        platform = item.get("platform") or ""
        gsd = item.get("gsd")
        bands = item.get("bands_count")
        level = item.get("processing_level") or ""
        if platform:
            metrics.append(f"🛰 {platform}")
        if gsd is not None:
            try:
                metrics.append(f"📐 {float(gsd):.0f}m/px")
            except (ValueError, TypeError):
                pass
        if bands is not None:
            metrics.append(f"🎨 {bands}b")
        if level:
            metrics.append(f"⚙ {level}")
        if metrics:
            lbl_metrics = QLabel("  ".join(metrics))
            lbl_metrics.setStyleSheet("color:#4a8090; font-size:10px;")
            lbl_metrics.setWordWrap(True)
            layout.addWidget(lbl_metrics)

        # Assets list (max 6)
        assets = item.get("assets") or []
        if assets:
            lbl_assets_title = QLabel(_t(lang, "Asset:", "Assets:"))
            lbl_assets_title.setStyleSheet("color:#4a8090; font-size:10px; margin-top:4px;")
            layout.addWidget(lbl_assets_title)

            for a in assets[:6]:
                a_title = a.get("title") or a.get("key") or ""
                a_type = a.get("type") or ""
                icon = "📥" if a.get("is_raster") else "📎"
                color = "#00e5ff" if a.get("is_raster") else "#4a8090"
                size_mb = a.get("size_mb")
                size_str = f" ({size_mb} MB)" if size_mb is not None else ""
                lbl_a = QLabel(f'<span style="color:{color}">{icon}</span>'
                               f' <span style="font-size:10px;">{a_title[:28]}{size_str}</span>')
                lbl_a.setStyleSheet("color:#7ac8d8;")
                lbl_a.setToolTip(f"{a_title}\n{a_type}\n{a.get('href', '')}")
                layout.addWidget(lbl_a)

        layout.addStretch()

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        best = best_raster_asset(item)

        # Catalogs that require a free registration are not downloaded blindly:
        # without credentials we only offer a link to the official portal, so
        # the plugin never fetches a login page by mistake.
        auth_required = bool(self.catalog.get("auth"))
        has_creds = bool(
            self.auth.get("token")
            or (self.auth.get("username") and self.auth.get("password"))
        )

        if auth_required and not has_creds:
            btn_portal = QPushButton(
                _t(lang, "🔐 Registrazione richiesta", "🔐 Registration required")
            )
            btn_portal.setObjectName("btnPortal")
            btn_portal.setToolTip(
                _t(lang,
                   "Questo catalogo richiede un account gratuito. "
                   "Apri il portale ufficiale per registrarti, poi inserisci "
                   "le credenziali nel tab 🔐 Account.",
                   "This catalog needs a free account. Open the official "
                   "portal to register, then enter your credentials in the "
                   "🔐 Account tab.")
            )
            url = self.catalog.get("register_url") or self.catalog.get("url")
            btn_portal.clicked.connect(
                lambda _c, u=url: QDesktopServices.openUrl(QUrl(u))
            )
            btn_row.addWidget(btn_portal)
        else:
            btn_add = QPushButton(_t(lang, "➕ QGIS", "➕ QGIS"))
            btn_add.setObjectName("btnAddQgis")
            btn_add.setToolTip(
                _t(lang, "Aggiungi layer in QGIS", "Add layer to QGIS")
            )
            btn_add.setEnabled(best is not None and _HAS_QGIS)
            btn_add.clicked.connect(
                lambda _checked, i=item, a=best: self._on_action("add", i, a)
            )
            btn_row.addWidget(btn_add)

            btn_dl = QPushButton(_t(lang, "💾 Scarica", "💾 Download"))
            btn_dl.setObjectName("btnDownload")
            btn_dl.setToolTip(
                _t(lang, "Scarica asset su disco", "Download asset to disk")
            )
            btn_dl.setEnabled(best is not None)
            btn_dl.clicked.connect(
                lambda _checked, i=item, a=best: self._on_action("download", i, a)
            )
            btn_row.addWidget(btn_dl)

        layout.addLayout(btn_row)

        # Load preview
        self._load_preview()

    def _load_preview(self):
        url = self.item.get("preview")
        if not url:
            return
        if url in self.preview_cache:
            self._set_pixmap(self.preview_cache[url])
            return
        self._fetcher = PreviewFetcher(url, self.preview_cache, parent=self)
        self._fetcher.pixmapReady.connect(self._on_pixmap_ready)
        self._fetcher.start()

    def _on_pixmap_ready(self, url, pixmap):
        if url == self.item.get("preview"):
            self._set_pixmap(pixmap)

    def _set_pixmap(self, pixmap):
        if self._preview_label is None or pixmap is None or pixmap.isNull():
            return
        scaled = pixmap.scaled(
            QSize(224, 112),
            QtCompat.KeepAspectRatio,
            QtCompat.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)
        self._preview_label.setText("")

    def _on_action(self, action, item, asset):
        """Route a card action: clip via controller, or full add/download."""
        if (self.controller is not None
                and self.controller.is_clip_mode()):
            self.controller.start_clip(item, asset, self.auth, action)
            return
        if action == "add":
            self._add_to_qgis(item, asset)
        else:
            self._download(item, asset)

    def _add_to_qgis(self, item, asset):
        if asset is None:
            return
        href = asset.get("href") or ""
        if not href:
            return
        try:
            layer = load_raster_to_qgis(href, item.get("id") or "STAC layer")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                if _iface:
                    _iface.messageBar().pushSuccess(
                        "STAC Browser",
                        f"Layer aggiunto: {item.get('id', '')}",
                    )
            else:
                if _iface:
                    _iface.messageBar().pushCritical(
                        "STAC Browser",
                        _t(self.lang,
                           "Layer non valido: l'asset potrebbe richiedere "
                           "un login presso il provider (USGS/NASA/Copernicus).",
                           "Invalid layer: the asset may require a provider "
                           "login (USGS/NASA/Copernicus)."),
                    )
        except Exception as exc:
            QMessageBox.warning(self, "STAC Browser", str(exc))

    def _download(self, item, asset):
        if asset is None:
            return
        href = asset.get("href") or ""
        if not href:
            return

        fname = os.path.basename(href.split("?")[0]) or "asset"
        out_path, _ = QFileDialog.getSaveFileName(
            self, _t(self.lang, "Salva file", "Save file"), fname,
        )
        if not out_path:
            return

        dlg = _DownloadProgressDialog(
            href, out_path, self.lang, auth=self.auth, parent=self
        )
        dlg.exec()


# ---------------------------------------------------------------------------
# Download progress dialog
# ---------------------------------------------------------------------------

class _DownloadProgressDialog(QDialog):
    def __init__(self, href, output_path, lang="it", auth=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t(lang, "Download in corso", "Downloading"))
        self.setModal(True)
        self.resize(400, 120)
        self.setStyleSheet(OCEAN_STYLE)

        layout = QVBoxLayout(self)
        fname = os.path.basename(output_path)
        self.lbl = QLabel(_t(lang, f"Scaricando {fname}...", f"Downloading {fname}..."))
        self.lbl.setStyleSheet("color:#d0f0ff;")
        layout.addWidget(self.lbl)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#4a8090; font-size:11px;")
        layout.addWidget(self.lbl_status)

        btn_cancel = QPushButton(_t(lang, "Annulla", "Cancel"))
        btn_cancel.setObjectName("btnCancel")
        btn_cancel.clicked.connect(self._cancel)
        layout.addWidget(btn_cancel)

        self._worker = DownloadWorker(href, output_path, auth=auth, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()
        self._lang = lang
        self._cancelled = False

    def _on_progress(self, done, total):
        if total > 0:
            pct = int(done * 100 / total)
            self.bar.setRange(0, 100)
            self.bar.setValue(pct)
            done_mb = done / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self.lbl_status.setText(f"{done_mb:.1f} / {total_mb:.1f} MB")
        else:
            self.bar.setRange(0, 0)
            done_mb = done / (1024 * 1024)
            self.lbl_status.setText(f"{done_mb:.1f} MB")

    def _on_finished(self, success, message):
        if success:
            self.lbl.setText(_t(self._lang, "Download completato!", "Download complete!"))
            self.lbl_status.setText(message)
            if _iface:
                _iface.messageBar().pushSuccess(
                    "STAC Browser",
                    _t(self._lang, f"Salvato: {message}", f"Saved: {message}"),
                )
        else:
            self.lbl.setText(_t(self._lang, "Errore download", "Download error"))
            self.lbl_status.setText(message)
        QTimer.singleShot(1500, self.accept)

    def _cancel(self):
        self._cancelled = True
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
        self.reject()


# ---------------------------------------------------------------------------
# Processing dialog — progress bar + pulsing plugin logo
# ---------------------------------------------------------------------------

class _ProcessingDialog(QDialog):
    """
    Modal popup shown while a clip job runs.

    Displays the plugin logo that pulses (fades in/out); the closer the job is
    to completion the faster and stronger the pulse becomes.
    """

    def __init__(self, worker, icon_path, lang="it", title=None, parent=None):
        super().__init__(parent)
        self._lang = lang
        self._worker = worker
        self._progress = 0
        self.result_path = None
        self.success = False

        self.setWindowTitle(title or _t(lang, "Elaborazione", "Processing"))
        self.setModal(True)
        self.resize(420, 200)
        self.setStyleSheet(OCEAN_STYLE)

        layout = QVBoxLayout(self)
        layout.setAlignment(QtCompat.AlignCenter)

        self.logo = QLabel()
        self.logo.setAlignment(QtCompat.AlignCenter)
        pix = QIcon(icon_path).pixmap(QSize(72, 72))
        if not pix.isNull():
            self.logo.setPixmap(pix)
        else:
            self.logo.setText("🛰️")
        self._opacity = QGraphicsOpacityEffect(self.logo)
        self._opacity.setOpacity(1.0)
        self.logo.setGraphicsEffect(self._opacity)
        layout.addWidget(self.logo)

        self.lbl = QLabel(
            _t(lang, "Ritaglio in corso…", "Clipping in progress…")
        )
        self.lbl.setAlignment(QtCompat.AlignCenter)
        self.lbl.setStyleSheet("color:#d0f0ff;")
        layout.addWidget(self.lbl)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(QtCompat.AlignCenter)
        self.lbl_status.setStyleSheet("color:#4a8090; font-size:11px;")
        layout.addWidget(self.lbl_status)

        # Pulse animation driven by a timer; pace set by progress.
        self._fade_up = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse)
        self._timer.start(90)

        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.start()

    def _pulse(self):
        # Amplitude grows with progress: near the end the logo blinks harder.
        floor = max(0.15, 0.7 - self._progress / 100.0 * 0.55)
        step = 0.12 + self._progress / 100.0 * 0.25
        op = self._opacity.opacity()
        op = op + step if self._fade_up else op - step
        if op <= floor:
            op = floor
            self._fade_up = True
        elif op >= 1.0:
            op = 1.0
            self._fade_up = False
        self._opacity.setOpacity(op)
        # Speed up the blink as completion approaches.
        interval = max(28, 90 - int(self._progress * 0.6))
        if interval != self._timer.interval():
            self._timer.setInterval(interval)

    def _on_progress(self, percent, _total):
        self._progress = max(0, min(100, percent))
        self.bar.setValue(self._progress)
        self.lbl_status.setText(f"{self._progress}%")

    def _on_finished(self, success, message):
        self._timer.stop()
        self._opacity.setOpacity(1.0)
        self.success = success
        if success:
            self.result_path = message
            self.bar.setValue(100)
            self.lbl.setText(_t(self._lang, "Completato!", "Done!"))
        else:
            self.lbl.setText(_t(self._lang, "Errore", "Error"))
            self.lbl_status.setText(message[:200])
        QTimer.singleShot(900 if success else 2200, self.accept)


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class StacBrowserDialog(QDialog):

    TAB_SEARCH = 0
    TAB_RESULTS = 1
    TAB_ACCOUNT = 2
    TAB_INFO = 3

    # Emitted when the user asks to draw an area on the canvas.
    # Payload is the mode: "bbox", "point" or "line".
    drawRequested = pyqtSignal(str)

    def __init__(self, parent=None, lang="it"):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle("GeoFusion — STAC Browser")
        self.resize(1100, 800)
        self.setMinimumSize(QSize(880, 600))
        self.setStyleSheet(OCEAN_STYLE)

        # State
        self._bbox = None           # (west, south, east, north)
        self._current_cutline_geojson = None  # Stored GeoJSON from search/draw
        self._search_worker = None
        self._geocode_worker = None
        self._results = {}          # catalog_id -> list of parsed items
        self._errors = {}           # catalog_id -> error string
        self._preview_cache = {}    # url -> QPixmap
        self._preview_fetchers = []
        # catalog_id -> {"username", "password", "token"} for auth catalogs
        self._credentials = {}
        self._load_credentials()

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # ── Header ────────────────────────────────────────────────
        header_row = QHBoxLayout()
        self.lbl_header = QLabel()
        hf = QFont()
        hf.setPointSize(15)
        hf.setBold(True)
        self.lbl_header.setFont(hf)
        self.lbl_header.setStyleSheet("color: #00e5ff; padding: 4px 0;")
        header_row.addWidget(self.lbl_header)
        header_row.addStretch()
        self.btn_lang = QPushButton("EN")
        self.btn_lang.setObjectName("btnLang")
        self.btn_lang.setFixedWidth(48)
        self.btn_lang.clicked.connect(self._toggle_lang)
        header_row.addWidget(self.btn_lang)
        main_layout.addLayout(header_row)

        # ── Tabs ──────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tab_search = QWidget()
        self.tab_results = QWidget()
        self.tab_account = QWidget()
        self.tab_info = QWidget()
        self.tabs.addTab(self.tab_search, "")
        self.tabs.addTab(self.tab_results, "")
        self.tabs.addTab(self.tab_account, "")
        self.tabs.addTab(self.tab_info, "")

        self._build_tab_search()
        self._build_tab_results()
        self._build_tab_account()
        self._build_tab_info()

        main_layout.addWidget(self.tabs)

        # ── Status bar ────────────────────────────────────────────
        status_row = QHBoxLayout()
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #4a8090; font-size: 11px;")
        self.progress_global = QProgressBar()
        self.progress_global.setRange(0, 0)
        self.progress_global.setVisible(False)
        self.progress_global.setMaximumHeight(6)
        self.progress_global.setMaximumWidth(200)
        self.btn_close = QPushButton()
        self.btn_close.setObjectName("btnCancel")
        self.btn_close.clicked.connect(self.reject)
        status_row.addWidget(self.lbl_status, 1)
        status_row.addWidget(self.progress_global)
        status_row.addWidget(self.btn_close)
        main_layout.addLayout(status_row)

        self._update_ui_lang()

        self.chk_auto.toggled.connect(self._on_auto_toggled)
        self._on_auto_toggled(self.chk_auto.isChecked())

    def _on_auto_toggled(self, auto):
        """Grey out the manual catalog/collection pickers in automatic mode."""
        for w in (
            self.list_catalogs, self.btn_select_all, self.btn_deselect_all,
            self.cb_collection, self.btn_fetch_cols,
        ):
            w.setEnabled(not auto)

    # ──────────────────────────────────────────────────────────────
    # Output mode (full dataset vs automatic clip)
    # ──────────────────────────────────────────────────────────────

    def is_clip_mode(self):
        return self.cb_output.currentData() == "clip"

    def _on_output_mode_changed(self, *_):
        pass

    def _cutline_from_active_layer(self):
        """Return a GeoJSON geometry (EPSG:4326) from the active QGIS layer.

        Uses the selected features, or all features if none are selected.
        """
        if not (_HAS_QGIS and _iface):
            return None
        layer = _iface.activeLayer()
        if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
            return None
        feats = layer.selectedFeatures()
        if not feats:
            feats = list(layer.getFeatures())
        geoms = [f.geometry() for f in feats if f.hasGeometry()]
        if not geoms:
            return None
        combined = QgsGeometry.unaryUnion(geoms)
        if combined is None or combined.isEmpty():
            return None
        src_crs = layer.crs()
        dst_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        if src_crs.authid() != "EPSG:4326":
            xform = QgsCoordinateTransform(
                src_crs, dst_crs, QgsProject.instance().transformContext()
            )
            combined.transform(xform)
        return combined.asJson()

    def start_clip(self, item, asset, auth, action):
        """Run a clip job (boundary + GDAL warp) with the pulsing popup."""
        if asset is None:
            return
        href = asset.get("href") or ""
        if not href:
            return
        L = self.lang

        comune_query = ""
        cutline_geojson = self._current_cutline_geojson

        if not cutline_geojson:
            if self._bbox:
                # Fallback: create a geojson polygon from bbox
                import json
                w, s, e, n = self._bbox
                geom = {
                    "type": "Polygon",
                    "coordinates": [[
                        [w, s], [e, s], [e, n], [w, n], [w, s]
                    ]]
                }
                cutline_geojson = json.dumps(geom)
            else:
                QMessageBox.warning(
                    self, "STAC Browser",
                    _t(L, "Nessuna area di interesse definita per il ritaglio.",
                       "No area of interest defined for clipping."),
                )
                return

        base = os.path.basename(href.split("?")[0]) or "asset"
        stem = os.path.splitext(base)[0]
        if action == "download":
            out_path, _ = QFileDialog.getSaveFileName(
                self, _t(L, "Salva ritaglio", "Save clip"),
                stem + "_clip.tif", "GeoTIFF (*.tif)",
            )
            if not out_path:
                return
        else:
            import tempfile
            out_path = os.path.join(
                tempfile.gettempdir(), stem + "_clip.tif"
            )

        worker = ClipWorker(
            href, out_path, auth=auth,
            comune_query=comune_query, cutline_geojson=cutline_geojson,
            parent=self,
        )
        icon_path = os.path.join(os.path.dirname(__file__), "icon.svg")
        dlg = _ProcessingDialog(worker, icon_path, lang=L, parent=self)
        dlg.exec()

        if dlg.success and dlg.result_path:
            if action == "add" and _HAS_QGIS:
                layer = QgsRasterLayer(dlg.result_path, stem + "_clip")
                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer)
                    if _iface:
                        _iface.messageBar().pushSuccess(
                            "STAC Browser",
                            _t(L, "Ritaglio aggiunto a QGIS.",
                               "Clip added to QGIS."),
                        )
            elif _iface:
                _iface.messageBar().pushSuccess(
                    "STAC Browser",
                    _t(L, f"Ritaglio salvato: {dlg.result_path}",
                       f"Clip saved: {dlg.result_path}"),
                )

    # ──────────────────────────────────────────────────────────────
    # Tab 0 — Search
    # ──────────────────────────────────────────────────────────────

    def _build_tab_search(self):
        layout = QVBoxLayout(self.tab_search)
        layout.setSpacing(8)

        # -- Catalogs group --
        grp_cat = QGroupBox()
        grp_cat.setObjectName("grpCatalogs")
        cat_layout = QVBoxLayout(grp_cat)

        self.list_catalogs = QListWidget()
        self.list_catalogs.setMaximumHeight(170)
        for cat in STAC_CATALOGS:
            item = QListWidgetItem()
            item.setText(f"{cat['name']}  —  {cat['description']}")
            item.setData(QtCompat.UserRole, cat["id"])
            item.setCheckState(QtCompat.Checked)
            self.list_catalogs.addItem(item)
        cat_layout.addWidget(self.list_catalogs)

        sel_row = QHBoxLayout()
        self.btn_select_all = QPushButton()
        self.btn_select_all.setObjectName("btnClear")
        self.btn_select_all.clicked.connect(self._select_all_catalogs)
        sel_row.addWidget(self.btn_select_all)
        self.btn_deselect_all = QPushButton()
        self.btn_deselect_all.setObjectName("btnClear")
        self.btn_deselect_all.clicked.connect(self._deselect_all_catalogs)
        sel_row.addWidget(self.btn_deselect_all)
        sel_row.addStretch()
        cat_layout.addLayout(sel_row)

        # -- Filters group --
        grp_filt = QGroupBox()
        grp_filt.setObjectName("grpFilters")
        filt_layout = QVBoxLayout(grp_filt)

        # Date row
        date_row = QHBoxLayout()
        self.lbl_date_from = QLabel()
        date_row.addWidget(self.lbl_date_from)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addYears(-1))
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        date_row.addWidget(self.date_from)
        self.lbl_date_to = QLabel()
        date_row.addWidget(self.lbl_date_to)
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        date_row.addWidget(self.date_to)
        self.chk_dates = QCheckBox()
        self.chk_dates.setChecked(False)
        date_row.addWidget(self.chk_dates)
        date_row.addStretch()
        filt_layout.addLayout(date_row)

        # Cloud + limit row
        cloud_row = QHBoxLayout()
        self.lbl_cloud = QLabel()
        cloud_row.addWidget(self.lbl_cloud)
        self.sb_cloud = QSpinBox()
        self.sb_cloud.setRange(0, 100)
        self.sb_cloud.setValue(30)
        self.sb_cloud.setFixedWidth(70)
        cloud_row.addWidget(self.sb_cloud)
        self.chk_cloud = QCheckBox()
        self.chk_cloud.setChecked(True)
        cloud_row.addWidget(self.chk_cloud)
        cloud_row.addSpacing(20)
        self.lbl_limit = QLabel()
        cloud_row.addWidget(self.lbl_limit)
        self.sb_limit = QSpinBox()
        self.sb_limit.setRange(5, 100)
        self.sb_limit.setValue(20)
        self.sb_limit.setFixedWidth(70)
        cloud_row.addWidget(self.sb_limit)
        cloud_row.addStretch()
        filt_layout.addLayout(cloud_row)

        # Collection combobox (optional)
        col_row = QHBoxLayout()
        self.lbl_collection = QLabel()
        col_row.addWidget(self.lbl_collection)
        self.cb_collection = QComboBox()
        self.cb_collection.setMinimumWidth(200)
        col_row.addWidget(self.cb_collection, 1)
        self.btn_fetch_cols = QPushButton()
        self.btn_fetch_cols.setObjectName("btnClear")
        self.btn_fetch_cols.clicked.connect(self._fetch_collections)
        col_row.addWidget(self.btn_fetch_cols)
        filt_layout.addLayout(col_row)

        # -- Action group --
        grp_action = QGroupBox()
        grp_action.setObjectName("grpAction")
        act_layout = QVBoxLayout(grp_action)

        # Address (Nominatim) row
        addr_row = QHBoxLayout()
        self.lbl_address = QLabel()
        addr_row.addWidget(self.lbl_address)
        self.ed_address = QLineEdit()
        self.ed_address.setPlaceholderText("")
        self.ed_address.returnPressed.connect(self._geocode_address)
        addr_row.addWidget(self.ed_address, 1)
        self.btn_geocode = QPushButton()
        self.btn_geocode.setObjectName("btnGeocode")
        self.btn_geocode.clicked.connect(self._geocode_address)
        addr_row.addWidget(self.btn_geocode)
        act_layout.addLayout(addr_row)

        # Draw tools row (rectangle / point / line)
        draw_row = QHBoxLayout()
        self.btn_draw = QPushButton()
        self.btn_draw.setObjectName("btnDraw")
        self.btn_draw.clicked.connect(lambda: self.drawRequested.emit("bbox"))
        draw_row.addWidget(self.btn_draw)
        self.btn_draw_point = QPushButton()
        self.btn_draw_point.setObjectName("btnDraw")
        self.btn_draw_point.clicked.connect(
            lambda: self.drawRequested.emit("point")
        )
        draw_row.addWidget(self.btn_draw_point)
        self.btn_draw_line = QPushButton()
        self.btn_draw_line.setObjectName("btnDraw")
        self.btn_draw_line.clicked.connect(
            lambda: self.drawRequested.emit("line")
        )
        draw_row.addWidget(self.btn_draw_line)
        draw_row.addStretch()
        act_layout.addLayout(draw_row)

        # Automatic-search checkbox + bbox label
        auto_row = QHBoxLayout()
        self.chk_auto = QCheckBox()
        self.chk_auto.setChecked(True)
        auto_row.addWidget(self.chk_auto)
        self.lbl_bbox = QLabel()
        self.lbl_bbox.setStyleSheet("color:#4a8090; font-size:11px;")
        auto_row.addWidget(self.lbl_bbox, 1)
        act_layout.addLayout(auto_row)

        search_row = QHBoxLayout()
        self.btn_search = QPushButton()
        search_row.addWidget(self.btn_search)
        self.btn_search_clear = QPushButton()
        self.btn_search_clear.setObjectName("btnClear")
        search_row.addWidget(self.btn_search_clear)
        search_row.addStretch()
        act_layout.addLayout(search_row)

        # Progress indicator (inside search group)
        self.lbl_search_status = QLabel("")
        self.lbl_search_status.setStyleSheet("color:#7ac8d8; font-size:11px;")
        act_layout.addWidget(self.lbl_search_status)
        self.progress_search = QProgressBar()
        self.progress_search.setRange(0, 0)
        self.progress_search.setVisible(False)
        self.progress_search.setMaximumHeight(6)
        act_layout.addWidget(self.progress_search)

        # -- Output group (full dataset vs automatic clip) --
        grp_out = QGroupBox()
        grp_out.setObjectName("grpOutput")
        out_layout = QVBoxLayout(grp_out)

        mode_row = QHBoxLayout()
        self.lbl_output = QLabel()
        mode_row.addWidget(self.lbl_output)
        self.cb_output = QComboBox()
        self.cb_output.addItem("", "full")
        self.cb_output.addItem("", "clip")
        self.cb_output.currentIndexChanged.connect(self._on_output_mode_changed)
        mode_row.addWidget(self.cb_output, 1)
        out_layout.addLayout(mode_row)

        # Add all widgets to main layout in the requested order
        layout.addWidget(grp_action)
        layout.addWidget(grp_cat)
        layout.addWidget(grp_filt)
        layout.addWidget(grp_out)
        layout.addStretch()

        self.btn_search.clicked.connect(self._start_search)
        self.btn_search_clear.clicked.connect(self._clear_results)
        self._on_output_mode_changed()

    # ──────────────────────────────────────────────────────────────
    # Tab 1 — Results
    # ──────────────────────────────────────────────────────────────

    def _build_tab_results(self):
        layout = QVBoxLayout(self.tab_results)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Summary label at top
        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet(
            "color:#00e5ff; font-size:13px; font-weight:600; padding:6px 4px;"
        )
        layout.addWidget(self.lbl_summary)

        # Scroll area for cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCompat.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(QtCompat.ScrollBarAsNeeded)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(4, 4, 4, 4)
        self.scroll_layout.setSpacing(12)
        self.scroll_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area, 1)

    # ──────────────────────────────────────────────────────────────
    # Tab 2 — Account / credentials for catalogs that need registration
    # ──────────────────────────────────────────────────────────────

    def _build_tab_account(self):
        # catalog_id -> (ed_user, ed_pwd, ed_token, ed_api)
        self._cred_widgets = {}
        outer = QVBoxLayout(self.tab_account)
        outer.setContentsMargins(4, 4, 4, 4)

        self.lbl_account_intro = QLabel()
        self.lbl_account_intro.setWordWrap(True)
        self.lbl_account_intro.setStyleSheet(
            "color:#7ac8d8; font-size:12px; padding:4px 2px;"
        )
        outer.addWidget(self.lbl_account_intro)

        # Two sub-tabs: open (free) catalogs and catalogs needing registration.
        self.cat_subtabs = QTabWidget()
        self.page_free = QWidget()
        self.page_auth = QWidget()
        self.cat_subtabs.addTab(self.page_free, "")
        self.cat_subtabs.addTab(self.page_auth, "")
        outer.addWidget(self.cat_subtabs, 1)

        # -- Free catalogs page --
        free_scroll = QScrollArea()
        free_scroll.setWidgetResizable(True)
        free_content = QWidget()
        free_vbox = QVBoxLayout(free_content)
        free_vbox.setSpacing(10)
        for cat in STAC_CATALOGS:
            if not cat.get("auth"):
                free_vbox.addWidget(self._make_catalog_box(cat, with_creds=False))
        free_vbox.addStretch()
        free_scroll.setWidget(free_content)
        QVBoxLayout(self.page_free).addWidget(free_scroll)

        # -- Auth catalogs page --
        auth_scroll = QScrollArea()
        auth_scroll.setWidgetResizable(True)
        auth_content = QWidget()
        auth_vbox = QVBoxLayout(auth_content)
        auth_vbox.setSpacing(10)
        for cat in STAC_CATALOGS:
            if cat.get("auth"):
                auth_vbox.addWidget(self._make_catalog_box(cat, with_creds=True))
        auth_vbox.addStretch()
        auth_scroll.setWidget(auth_content)
        auth_page_layout = QVBoxLayout(self.page_auth)
        auth_page_layout.addWidget(auth_scroll, 1)

        btn_row = QHBoxLayout()
        self.btn_save_creds = QPushButton()
        self.btn_save_creds.clicked.connect(self._save_credentials)
        btn_row.addWidget(self.btn_save_creds)
        self.btn_clear_creds = QPushButton()
        self.btn_clear_creds.setObjectName("btnClear")
        self.btn_clear_creds.clicked.connect(self._clear_credentials)
        btn_row.addWidget(self.btn_clear_creds)
        btn_row.addStretch()
        auth_page_layout.addLayout(btn_row)

    def _make_catalog_box(self, cat, with_creds):
        """Build a per-catalog group: license, official site, (auth) creds."""
        cid = cat["id"]
        grp = QGroupBox(cat["name"])
        grp.setObjectName("grpCat_" + cid)
        form = QVBoxLayout(grp)

        desc = QLabel(cat.get("description", ""))
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#7ac8d8; font-size:11px;")
        form.addWidget(desc)

        lic = QLabel()
        lic.setOpenExternalLinks(True)
        lic.setWordWrap(True)
        lic.setStyleSheet("color:#4a8090; font-size:11px;")
        lic_url = cat.get("license_url")
        lic_txt = cat.get("license", "")
        if lic_url:
            lic.setText(
                f'⚖️ {lic_txt} &nbsp;'
                f'<a href="{lic_url}" style="color:#3b82f6;">↗ licenza/license</a>'
            )
        else:
            lic.setText(f"⚖️ {lic_txt}")
        form.addWidget(lic)

        btn_site = QPushButton(
            _t(self.lang, "🌐 Sito ufficiale", "🌐 Official site")
            if not with_creds else
            _t(self.lang, "🌐 Sito ufficiale / Registrati",
               "🌐 Official site / Register")
        )
        btn_site.setObjectName("btnPortal")
        url = cat.get("register_url") if with_creds else cat.get("site_url")
        url = url or cat.get("site_url") or cat.get("url")
        btn_site.clicked.connect(
            lambda _c, u=url: QDesktopServices.openUrl(QUrl(u))
        )
        form.addWidget(btn_site)

        if not with_creds:
            ok = QLabel(_t(self.lang,
                           "✅ Nessuna registrazione necessaria.",
                           "✅ No registration required."))
            ok.setStyleSheet("color:#22c55e; font-size:11px;")
            form.addWidget(ok)
            return grp

        note = QLabel(cat.get("auth_note", ""))
        note.setWordWrap(True)
        note.setStyleSheet("color:#f59e0b; font-size:11px;")
        form.addWidget(note)

        stored = self._credentials.get(cid, {})

        def _row(label, value="", password=False, placeholder=""):
            row = QHBoxLayout()
            lb = QLabel(label)
            lb.setFixedWidth(80)
            row.addWidget(lb)
            ed = QLineEdit(value)
            if password:
                ed.setEchoMode(QLineEdit.EchoMode.Password)
            if placeholder:
                ed.setPlaceholderText(placeholder)
            row.addWidget(ed, 1)
            form.addLayout(row)
            return ed

        ed_user = _row(_t(self.lang, "Utente:", "Username:"),
                       stored.get("username", ""))
        ed_pwd = _row(_t(self.lang, "Password:", "Password:"),
                      stored.get("password", ""), password=True)
        ed_token = _row(
            _t(self.lang, "Token:", "Token:"), stored.get("token", ""),
            placeholder=_t(self.lang, "Token Bearer (consigliato)",
                           "Bearer token (recommended)"),
        )
        ed_api = _row(
            _t(self.lang, "API key:", "API key:"), stored.get("api_key", ""),
            placeholder=_t(self.lang, "Chiave API (se prevista)",
                           "API key (if provided)"),
        )
        self._cred_widgets[cid] = (ed_user, ed_pwd, ed_token, ed_api)
        return grp

    # ── Credential persistence (QgsSettings) ──────────────────────

    _CRED_KEYS = ("username", "password", "token", "api_key")

    def _cred_for(self, catalog):
        """Return the stored credentials dict for a catalog entry."""
        if not catalog:
            return {}
        return self._credentials.get(catalog.get("id"), {})

    def _load_credentials(self):
        if QgsSettings is None:
            return
        s = QgsSettings()
        for cat in STAC_CATALOGS:
            if not cat.get("auth"):
                continue
            cid = cat["id"]
            base = f"GeoFusion/StacBrowser/auth/{cid}"
            cred = {
                k: (s.value(base + "/" + k, "") or "")
                for k in self._CRED_KEYS
            }
            if any(cred.values()):
                self._credentials[cid] = cred

    def _save_credentials(self):
        for cid, widgets in self._cred_widgets.items():
            ed_user, ed_pwd, ed_token, ed_api = widgets
            self._credentials[cid] = {
                "username": ed_user.text().strip(),
                "password": ed_pwd.text(),
                "token": ed_token.text().strip(),
                "api_key": ed_api.text().strip(),
            }
        if QgsSettings is not None:
            s = QgsSettings()
            for cid, cred in self._credentials.items():
                base = f"GeoFusion/StacBrowser/auth/{cid}"
                for k in self._CRED_KEYS:
                    s.setValue(base + "/" + k, cred.get(k, ""))
        self.lbl_status.setText(
            _t(self.lang, "Credenziali salvate.", "Credentials saved.")
        )

    def _clear_credentials(self):
        for widgets in self._cred_widgets.values():
            for ed in widgets:
                ed.clear()
        self._credentials = {}
        if QgsSettings is not None:
            s = QgsSettings()
            for cat in STAC_CATALOGS:
                if cat.get("auth"):
                    s.remove(f"GeoFusion/StacBrowser/auth/{cat['id']}")
        self.lbl_status.setText(
            _t(self.lang, "Credenziali cancellate.", "Credentials cleared.")
        )

    # ──────────────────────────────────────────────────────────────
    # Tab 3 — Info
    # ──────────────────────────────────────────────────────────────

    def _build_tab_info(self):
        layout = QVBoxLayout(self.tab_info)
        layout.setContentsMargins(0, 0, 0, 0)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(INFO_HTML)
        layout.addWidget(browser)

    # ──────────────────────────────────────────────────────────────
    # Language toggle
    # ──────────────────────────────────────────────────────────────

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "it" else "it"
        self.btn_lang.setText("IT" if self.lang == "en" else "EN")
        self._update_ui_lang()

    def _update_ui_lang(self):
        L = self.lang
        self.setWindowTitle(_t(L, "GeoFusion — STAC Browser", "GeoFusion — STAC Browser"))
        self.lbl_header.setText(_t(L, "🛰️ STAC Browser", "🛰️ STAC Browser"))
        self.btn_close.setText(_t(L, "Chiudi", "Close"))

        # Tab labels
        self.tabs.setTabText(self.TAB_SEARCH,  _t(L, "🔍 Ricerca", "🔍 Search"))
        self.tabs.setTabText(self.TAB_RESULTS, _t(L, "📋 Risultati", "📋 Results"))
        self.tabs.setTabText(self.TAB_ACCOUNT, _t(L, "🗂 Cataloghi", "🗂 Catalogs"))
        self.tabs.setTabText(self.TAB_INFO,    "ℹ Info")

        # Catalogs sub-tabs
        self.cat_subtabs.setTabText(
            0, _t(L, "🟢 Liberi", "🟢 Open"))
        self.cat_subtabs.setTabText(
            1, _t(L, "🔐 Con autenticazione", "🔐 With authentication"))

        # Output group
        grp_o = self.tab_search.findChild(QGroupBox, "grpOutput")
        if grp_o:
            grp_o.setTitle(_t(L, "Output", "Output"))
        self.lbl_output.setText(_t(L, "Modalità:", "Mode:"))
        self.cb_output.setItemText(
            0, _t(L, "📦 Dataset completo", "📦 Full dataset"))
        self.cb_output.setItemText(
            1, _t(L, "✂️ Ritaglio automatico", "✂️ Automatic clip"))

        # Account tab
        self.lbl_account_intro.setText(_t(
            L,
            "Questo plugin è solo un <b>facilitatore di download</b>: i dati "
            "restano dei rispettivi provider. Scarica automaticamente solo "
            "dalle fonti libere; i cataloghi qui sotto richiedono una "
            "<b>registrazione gratuita</b>. Apri il sito ufficiale, crea un "
            "account e inserisci utente/password o token. Le credenziali sono "
            "salvate solo in locale sul tuo computer.",
            "This plugin is only a <b>download facilitator</b>: the data "
            "belongs to its providers. It auto-downloads only from free "
            "sources; the catalogs below require a <b>free registration</b>. "
            "Open the official site, create an account and enter "
            "username/password or token. Credentials are stored locally on "
            "your computer only.",
        ))
        self.btn_save_creds.setText(
            _t(L, "💾 Salva credenziali", "💾 Save credentials")
        )
        self.btn_clear_creds.setText(
            _t(L, "🧹 Cancella", "🧹 Clear")
        )

        # Catalogs group
        grp = self.tab_search.findChild(QGroupBox, "grpCatalogs")
        if grp:
            grp.setTitle(_t(L, "Cataloghi STAC", "STAC Catalogs"))
        self.btn_select_all.setText(_t(L, "Seleziona tutti", "Select all"))
        self.btn_deselect_all.setText(_t(L, "Deseleziona", "Deselect all"))

        # Filters group
        grp_f = self.tab_search.findChild(QGroupBox, "grpFilters")
        if grp_f:
            grp_f.setTitle(_t(L, "Filtri", "Filters"))
        self.lbl_date_from.setText(_t(L, "Da:", "From:"))
        self.lbl_date_to.setText(_t(L, "A:", "To:"))
        self.chk_dates.setText(_t(L, "Abilita filtro date", "Enable date filter"))
        self.lbl_cloud.setText(_t(L, "Max nuvole %:", "Max cloud %:"))
        self.chk_cloud.setText(_t(L, "Applica", "Apply"))
        self.lbl_limit.setText(_t(L, "Limite:", "Limit:"))
        self.lbl_collection.setText(_t(L, "Collezione:", "Collection:"))
        self.btn_fetch_cols.setText(_t(L, "↺ Carica", "↺ Load"))

        # Action group
        grp_a = self.tab_search.findChild(QGroupBox, "grpAction")
        if grp_a:
            grp_a.setTitle(_t(L, "Area di interesse", "Area of interest"))
        self.lbl_address.setText(_t(L, "Indirizzo:", "Address:"))
        self.ed_address.setPlaceholderText(
            _t(L,
               "Via Roma 1, Napoli  —  premi Invio per geolocalizzare",
               "1 Main St, London  —  press Enter to geocode")
        )
        self.btn_geocode.setText(_t(L, "📍 Trova", "📍 Locate"))
        self.btn_draw.setText(_t(L, "▭ Rettangolo", "▭ Rectangle"))
        self.btn_draw_point.setText(_t(L, "• Punto", "• Point"))
        self.btn_draw_line.setText(_t(L, "╱ Linea", "╱ Line"))
        self.chk_auto.setText(
            _t(L,
               "🔄 Ricerca automatica (cerca subito in tutti i cataloghi)",
               "🔄 Automatic search (query all catalogs immediately)")
        )
        self.btn_draw.setToolTip(
            _t(L, "Disegna un rettangolo sulla mappa",
               "Draw a rectangle on the map")
        )
        self.btn_draw_point.setToolTip(
            _t(L, "Clicca un punto: cerca in un'area attorno ad esso",
               "Click a point: searches a small area around it")
        )
        self.btn_draw_line.setToolTip(
            _t(L,
               "Disegna una linea (tasto destro/doppio click per chiudere)",
               "Draw a line (right-click/double-click to finish)")
        )
        self.btn_search.setText(
            _t(L, "🔍 Cerca in tutti i cataloghi", "🔍 Search all catalogs")
        )
        self.btn_search_clear.setText(_t(L, "🧹 Pulisci", "🧹 Clear"))

        # Bbox label
        self._refresh_bbox_label()

        # Status
        self.lbl_status.setText(_t(L, "Pronto.", "Ready."))

    def _refresh_bbox_label(self):
        L = self.lang
        if self._bbox:
            w, s, e, n = self._bbox
            self.lbl_bbox.setText(
                f"Area: W={w:.4f}° E={e:.4f}° S={s:.4f}° N={n:.4f}°"
            )
        else:
            self.lbl_bbox.setText(_t(L, "Nessuna area selezionata", "No area selected"))

    # ──────────────────────────────────────────────────────────────
    # Bbox update (called from plugin)
    # ──────────────────────────────────────────────────────────────

    def set_bbox(self, west, south, east, north, geojson=None):
        self._bbox = (west, south, east, north)
        self._current_cutline_geojson = geojson
        self._refresh_bbox_label()

        # Automatically switch to Clip mode since the user selected an area
        idx = self.cb_output.findData("clip")
        if idx >= 0:
            self.cb_output.setCurrentIndex(idx)

        self.show()
        self.raise_()
        self.activateWindow()
        # Automatic mode: as soon as an area is defined, query every catalog
        # so the user immediately sees what data exists there.
        if self.chk_auto.isChecked():
            self._start_search()

    def _zoom_canvas_to_bbox(self, west, south, east, north):
        """Zoom the QGIS canvas to a 4326 bbox (best-effort)."""
        if not (_HAS_QGIS and _iface):
            return
        try:
            crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")
            project_crs = QgsProject.instance().crs()
            rect = QgsRectangle(west, south, east, north)
            if project_crs.authid() != "EPSG:4326":
                xform = QgsCoordinateTransform(
                    crs_4326, project_crs,
                    QgsProject.instance().transformContext(),
                )
                rect = xform.transformBoundingBox(rect)
            rect.scale(1.5)
            canvas = _iface.mapCanvas()
            canvas.setExtent(rect)
            canvas.refresh()
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────
    # Geocoding (Nominatim)
    # ──────────────────────────────────────────────────────────────

    def _geocode_address(self):
        query = self.ed_address.text().strip()
        if not query:
            return
        if self._geocode_worker and self._geocode_worker.isRunning():
            return
        L = self.lang
        self.btn_geocode.setEnabled(False)
        self.lbl_status.setText(_t(L, "Ricerca indirizzo...", "Geocoding..."))
        self._geocode_worker = GeocodeWorker(query, parent=self)
        self._geocode_worker.resultReady.connect(self._on_geocode_result)
        self._geocode_worker.start()

    def _on_geocode_result(self, results):
        self.btn_geocode.setEnabled(True)
        L = self.lang
        if not results:
            self.lbl_status.setText(
                _t(L, "Indirizzo non trovato.", "Address not found.")
            )
            QMessageBox.information(
                self, "STAC Browser",
                _t(L,
                   "Nessun risultato per questo indirizzo.",
                   "No match for this address."),
            )
            return
        hit = results[0]
        west, south, east, north = hit["bbox"]

        # If a geojson boundary was returned, store it for later clipping
        geojson = None
        if hit.get("geojson"):
            import json
            geojson = json.dumps(hit["geojson"])
        else:
            QMessageBox.information(
                self, "STAC Browser",
                _t(L,
                   "Confine esatto non disponibile per quest'area. "
                   "Verrà effettuato il ritaglio vicino all'area più prossima indicata "
                   "(utilizzando il rettangolo).",
                   "Exact boundary not available for this area. "
                   "Clipping will be performed near the closest indicated area "
                   "(using the bounding box).")
            )

        self.lbl_status.setText(hit.get("display_name", "")[:90])
        self._zoom_canvas_to_bbox(west, south, east, north)
        self.set_bbox(west, south, east, north, geojson=geojson)

    # ──────────────────────────────────────────────────────────────
    # Catalogs helpers
    # ──────────────────────────────────────────────────────────────

    def _select_all_catalogs(self):
        for i in range(self.list_catalogs.count()):
            self.list_catalogs.item(i).setCheckState(QtCompat.Checked)

    def _deselect_all_catalogs(self):
        for i in range(self.list_catalogs.count()):
            self.list_catalogs.item(i).setCheckState(QtCompat.Unchecked)

    def _get_selected_catalog_ids(self):
        ids = []
        for i in range(self.list_catalogs.count()):
            item = self.list_catalogs.item(i)
            if item.checkState() == QtCompat.Checked:
                ids.append(item.data(QtCompat.UserRole))
        return ids

    def _fetch_collections(self):
        selected_ids = self._get_selected_catalog_ids()
        if len(selected_ids) != 1:
            QMessageBox.information(
                self,
                "STAC Browser",
                _t(self.lang,
                   "Seleziona un solo catalogo per caricare le collezioni.",
                   "Select exactly one catalog to load its collections."),
            )
            return
        cat_id = selected_ids[0]
        cat = next((c for c in STAC_CATALOGS if c["id"] == cat_id), None)
        if cat is None:
            return
        self.cb_collection.clear()
        self.cb_collection.addItem(
            _t(self.lang, "— tutte le collezioni —", "— all collections —"),
            "",
        )
        cols = stac_collections(cat["url"])
        for c in cols:
            title = c.get("title") or c.get("id") or ""
            self.cb_collection.addItem(title, c.get("id") or "")

    # ──────────────────────────────────────────────────────────────
    # Search
    # ──────────────────────────────────────────────────────────────

    def _start_search(self):
        if self._bbox is None:
            QMessageBox.warning(
                self,
                "STAC Browser",
                _t(self.lang,
                   "Prima disegna un'area sulla mappa (pulsante 'Disegna area').",
                   "First draw an area on the map (click 'Draw area')."),
            )
            return

        if self.chk_auto.isChecked():
            # Automatic mode ignores the manual selection and queries
            # every available catalog.
            selected_ids = [c["id"] for c in STAC_CATALOGS]
        else:
            selected_ids = self._get_selected_catalog_ids()
            if not selected_ids:
                QMessageBox.warning(
                    self,
                    "STAC Browser",
                    _t(self.lang,
                       "Seleziona almeno un catalogo.",
                       "Select at least one catalog."),
                )
                return

        # Stop previous search if any
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.cancel()
            self._search_worker.wait(2000)

        # Gather params
        bbox = list(self._bbox)

        datetime_range = None
        if self.chk_dates.isChecked():
            d_from = self.date_from.date().toString("yyyy-MM-dd")
            d_to = self.date_to.date().toString("yyyy-MM-dd")
            datetime_range = f"{d_from}T00:00:00Z/{d_to}T23:59:59Z"

        cloud_max = self.sb_cloud.value() if self.chk_cloud.isChecked() else None
        limit = self.sb_limit.value()

        # The single-catalog collection filter is meaningless when querying
        # every catalog, so it is ignored in automatic mode.
        if self.chk_auto.isChecked():
            collections = None
        else:
            collection_data = self.cb_collection.currentData()
            collections = [collection_data] if collection_data else None

        catalogs = [c for c in STAC_CATALOGS if c["id"] in selected_ids]

        # Reset results
        self._results = {}
        self._errors = {}
        self._clear_result_cards()

        # Start worker
        self._search_worker = StacSearchWorker(
            catalogs=catalogs,
            bbox=bbox,
            datetime_range=datetime_range,
            collections=collections,
            cloud_max=cloud_max,
            limit=limit,
            parent=self,
        )
        self._search_worker.catalogStarted.connect(self._on_catalog_started)
        self._search_worker.catalogResult.connect(self._on_catalog_result)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.start()

        self.progress_search.setVisible(True)
        self.btn_search.setEnabled(False)
        L = self.lang
        self.lbl_search_status.setText(_t(L, "Ricerca in corso...", "Searching..."))
        self.lbl_status.setText(_t(L, "Ricerca STAC avviata.", "STAC search started."))

    def _on_catalog_started(self, cat_id, cat_name):
        L = self.lang
        self.lbl_search_status.setText(
            _t(L, f"Interrogando: {cat_name}...", f"Querying: {cat_name}...")
        )

    def _on_catalog_result(self, cat_id, items, error):
        self._results[cat_id] = items
        self._errors[cat_id] = error
        cat = next((c for c in STAC_CATALOGS if c["id"] == cat_id), {})
        self._add_catalog_section(cat, items, error)
        self._update_summary()

    def _on_search_finished(self):
        self.progress_search.setVisible(False)
        self.btn_search.setEnabled(True)
        total = sum(len(v) for v in self._results.values())
        n_cats = len([v for v in self._results.values() if v])
        L = self.lang
        self.lbl_search_status.setText(
            _t(L,
               f"Completato. {total} dataset in {n_cats} cataloghi.",
               f"Done. {total} datasets in {n_cats} catalogs.")
        )
        self.lbl_status.setText(_t(L, "Ricerca completata.", "Search complete."))
        if total > 0:
            self.tabs.setCurrentIndex(self.TAB_RESULTS)

    # ──────────────────────────────────────────────────────────────
    # Results rendering
    # ──────────────────────────────────────────────────────────────

    def _clear_result_cards(self):
        # Remove all children from scroll_layout except the final stretch
        while self.scroll_layout.count() > 1:
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.lbl_summary.setText("")

    def _update_summary(self):
        total = sum(len(v) for v in self._results.values())
        n_cats = len([v for v in self._results.values() if v])
        L = self.lang
        self.lbl_summary.setText(
            _t(L,
               f"Trovati {total} dataset in {n_cats} cataloghi",
               f"Found {total} datasets in {n_cats} catalogs")
        )

    def _add_catalog_section(self, cat, items, error):
        """Append a catalog section with cards to the results scroll area."""
        # "Show only present records": in automatic mode we hide catalogs that
        # returned nothing (empty or errored) so the user only sees real data.
        if self.chk_auto.isChecked() and not items:
            return

        section_widget = QWidget()
        section_layout = QVBoxLayout(section_widget)
        section_layout.setSpacing(6)

        # Header
        cat_name = cat.get("name") or cat.get("id") or "Unknown"
        cat_url = cat.get("url") or ""
        n = len(items)

        header_lbl = QLabel()
        if error and not items:
            header_lbl.setText(
                f'<b style="color:#ef4444;">⚠️ {cat_name}</b>'
                f' &nbsp;<span style="color:#4a8090; font-size:11px;">'
                f'{_t(self.lang, "Non disponibile", "Not available")}</span>'
            )
        else:
            header_lbl.setText(
                f'<b style="color:#00e5ff;">🛰️ {cat_name}</b>'
                f' &nbsp;<span style="color:#4a8090;">·</span>&nbsp;'
                f'<span style="color:#7ac8d8;">'
                f'{n} {_t(self.lang, "risultati", "results")}</span>'
                f'&nbsp;&nbsp;<a href="{cat_url}" style="color:#3b82f6; font-size:11px;">↗ '
                f'{_t(self.lang, "apri catalogo", "open catalog")}</a>'
            )
            header_lbl.setOpenExternalLinks(True)
        header_lbl.setStyleSheet("font-size:13px; padding:4px 0;")
        section_layout.addWidget(header_lbl)

        # Auth notice: free registration required + link to official portal.
        if cat.get("auth") and items:
            has_creds = bool(
                self._cred_for(cat).get("token")
                or (self._cred_for(cat).get("username")
                    and self._cred_for(cat).get("password"))
            )
            if not has_creds:
                reg = cat.get("register_url") or cat_url
                t_req = _t(self.lang, "Richiede registrazione gratuita",
                           "Requires free registration")
                t_open = _t(self.lang, "apri portale ufficiale",
                            "open official portal")
                auth_lbl = QLabel(
                    f'<span style="color:#f59e0b;">🔐 {t_req}</span> &nbsp;'
                    f'<a href="{reg}" style="color:#3b82f6;">↗ {t_open}</a>'
                )
                auth_lbl.setOpenExternalLinks(True)
                auth_lbl.setStyleSheet("font-size:11px; padding:0 0 4px 0;")
                section_layout.addWidget(auth_lbl)

        if error and not items:
            # Error card
            err_lbl = QLabel(
                f'<span style="color:#ef4444;">⚠ {error[:200]}</span>'
            )
            err_lbl.setWordWrap(True)
            err_lbl.setStyleSheet(
                "background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.2);"
                "border-radius:6px; padding:8px; font-size:11px;"
            )
            section_layout.addWidget(err_lbl)
        elif items:
            # Grid of cards (3 columns adaptive)
            grid_widget = QWidget()
            grid_layout = QGridLayout(grid_widget)
            grid_layout.setSpacing(8)
            grid_layout.setContentsMargins(0, 0, 0, 0)

            col_count = 3
            cat_auth = self._cred_for(cat)
            for idx, item in enumerate(items):
                card = ItemCard(
                    item, lang=self.lang,
                    preview_cache=self._preview_cache,
                    catalog=cat, auth=cat_auth, controller=self,
                    parent=grid_widget,
                )
                grid_layout.addWidget(card, idx // col_count, idx % col_count)

            section_layout.addWidget(grid_widget)
        else:
            lbl_empty = QLabel(
                _t(self.lang, "Nessun risultato in questo catalogo.", "No results in this catalog.")
            )
            lbl_empty.setStyleSheet("color:#4a8090; font-size:11px; padding:4px;")
            section_layout.addWidget(lbl_empty)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#0a4a6e;")
        section_layout.addWidget(sep)

        # Insert before the stretch at the end
        stretch_pos = self.scroll_layout.count() - 1
        self.scroll_layout.insertWidget(stretch_pos, section_widget)

    # ──────────────────────────────────────────────────────────────
    # Clear
    # ──────────────────────────────────────────────────────────────

    def _clear_results(self):
        self._results = {}
        self._errors = {}
        self._bbox = None
        self._clear_result_cards()
        self._refresh_bbox_label()
        L = self.lang
        self.lbl_search_status.setText("")
        self.lbl_status.setText(_t(L, "Risultati cancellati.", "Results cleared."))
