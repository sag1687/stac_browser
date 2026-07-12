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
dialog.py — Main dialog for the STAC Browser QGIS plugin.

Three tabs:
  0. Ricerca / Search
  1. Risultati / Results
  2. ℹ Info
"""

import os
import time

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
        QgsRasterLayer, QgsMessageLog, Qgis,
    )
    _HAS_QGIS = True
except ImportError:
    _HAS_QGIS = False
    QgsMessageLog = None
    Qgis = None

try:
    from qgis.utils import iface as _iface
except ImportError:
    _iface = None

from .qt_compat import ensure_qt_compat, QtCompat
from . import plugin_hub
from .core_stac import (
    STAC_CATALOGS, stac_search, stac_collections, geocode_nominatim,
    nominatim_polygon, parse_stac_item, best_raster_asset,
    load_raster_to_qgis, download_asset, clip_raster, sign_href_if_needed,
)

try:
    from qgis.core import QgsSettings
except ImportError:
    QgsSettings = None

ensure_qt_compat(Qt)


def _log(msg, level="warning"):
    """Log a message to the QGIS log panel (no-op outside QGIS)."""
    if QgsMessageLog is None or Qgis is None:
        return
    lvl = {
        "info": Qgis.Info,
        "warning": Qgis.Warning,
        "critical": Qgis.Critical,
    }.get(level, Qgis.Warning)
    QgsMessageLog.logMessage(str(msg), "STAC Browser", lvl)


# ---------------------------------------------------------------------------
# Translation helper
# ---------------------------------------------------------------------------

def _t(lang, it, en):
    """Return Italian or English string based on lang ('it' or 'en')."""
    return en if lang == "en" else it


def _en_it(en, it):
    """Return a compact English-first bilingual UI string."""
    return f"{en} / {it}"


# ---------------------------------------------------------------------------
# Dark stylesheet
# ---------------------------------------------------------------------------

OCEAN_STYLE = """
QDialog {
    background-color: #141a22;
    color: #f2f5f8;
    font-family: 'Segoe UI', 'Inter', 'Roboto', Tahoma, Geneva,
                 Verdana, sans-serif;
    font-size: 13px;
}
QWidget { background-color: #141a22; color: #f2f5f8; }
QLabel { color: #c3ccd6; font-size: 13px; }
QGroupBox {
    border: 1px solid #2c3a48;
    border-radius: 8px;
    margin-top: 10px;
    padding: 12px 10px;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #1b2430,stop:1 #141a22);
    color: #f2f5f8;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #5b9bd5;
    font-size: 12px;
}
QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #3f6f9e,stop:1 #2c4f70);
    color: #5b9bd5;
    border: 1px solid #5b9bd5;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 700;
    font-size: 12px;
}
QPushButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #4d84b8,stop:1 #3f6f9e);
    color: #f2f5f8;
}
QPushButton:pressed { background: #2c4f70; }
QPushButton:disabled {
    background: #1b2430; color: #8a97a5; border-color: #2c4f70;
}
QPushButton#btnLang {
    background: #1b2430;
    color: #c3ccd6;
    border: 1px solid #2c3a48;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
    border-radius: 4px;
}
QPushButton#btnLang:hover { background: #22303e; color: #5b9bd5; }
QPushButton#btnClose {
    background: #1b2430;
    color: #c3ccd6;
    border: 1px solid #2c3a48;
}
QPushButton#btnClose:hover { background: #22303e; color: #f2f5f8; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QDateEdit {
    padding: 5px 8px;
    border: 1px solid #2c3a48;
    border-radius: 5px;
    background: #1b2430;
    color: #f2f5f8;
    selection-background-color: #2c3a48;
}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QLineEdit:focus, QDateEdit:focus {
    border-color: #5b9bd5;
}
QComboBox::drop-down { border: none; padding-right: 6px; }
QTabWidget::pane {
    border: 1px solid #2c3a48;
    border-radius: 6px;
    top: -1px;
    background: #141a22;
}
QTabBar::tab {
    background: #1b2430;
    border: 1px solid #2c3a48;
    padding: 7px 14px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #8a97a5;
    font-size: 12px;
}
QTabBar::tab:selected {
    background: #141a22;
    border-bottom-color: #141a22;
    font-weight: bold;
    color: #5b9bd5;
}
QTabBar::tab:hover:!selected { background: #22303e; color: #c3ccd6; }
QProgressBar {
    border: 1px solid #2c3a48;
    border-radius: 4px;
    height: 6px;
    background: #1b2430;
    color: transparent;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #4d84b8,stop:1 #5b9bd5);
    border-radius: 3px;
}
QCheckBox { color: #c3ccd6; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 3px;
    border: 1px solid #2c3a48;
    background: #1b2430;
}
QCheckBox::indicator:checked { background: #5b9bd5; border-color: #5b9bd5; }
QListWidget {
    background: #1b2430;
    border: 1px solid #2c3a48;
    border-radius: 5px;
    color: #f2f5f8;
    font-size: 12px;
}
QListWidget::item { padding: 5px 8px; }
QListWidget::item:selected { background: #2c3a48; color: #5b9bd5; }
QListWidget::item:hover { background: #22303e; }
QTextBrowser {
    background: #1b2430;
    border: 1px solid #2c3a48;
    border-radius: 5px;
    color: #c3ccd6;
    font-size: 12px;
}
QScrollArea { background: #141a22; border: none; }
QScrollBar:vertical, QScrollBar:horizontal {
    background: #1b2430;
    border: none;
    width: 8px; height: 8px;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #2c3a48;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: #5b9bd5;
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
  body { background:#141a22; color:#f2f5f8;
         font-family:'Segoe UI',Arial,sans-serif;
         font-size:12px; margin:16px; line-height:1.6; }
  h2   { color:#5b9bd5; font-size:15px; margin:0 0 12px;
         border-bottom:1px solid #22303e; padding-bottom:6px; }
  h3   { color:#60a5fa; font-size:13px; margin:16px 0 6px; }
  h4   { color:#f59e0b; font-size:12px; margin:12px 0 4px; }
  p, li { margin:3px 0; color:#c3ccd6; }
  a    { color:#5b9bd5; }
  code { background:#22303e; padding:1px 4px; border-radius:3px;
         font-family:monospace; }
  table { border-collapse:collapse; width:100%; margin:8px 0; }
  th   { background:#22303e; color:#c3ccd6; padding:6px 10px; text-align:left;
         border-bottom:2px solid #2c3a48; font-size:11px; }
  td   { padding:5px 10px; border-bottom:1px solid #22303e; color:#f2f5f8; }
  tr:nth-child(even) td { background:rgba(27,36,48,0.5); }
  .badge-warn { background:rgba(239,68,68,0.15); color:#ef4444;
                padding:1px 6px; border-radius:8px; font-size:11px;
                font-weight:600; }
  .badge-ok   { background:rgba(34,197,94,0.15); color:#22c55e;
                padding:1px 6px; border-radius:8px; font-size:11px;
                font-weight:600; }
  .section-sep { border:none; border-top:1px solid #22303e; margin:16px 0; }
</style>
</head>
<body>

<h2>STAC BROWSER &mdash; INFORMATION / INFORMAZIONI</h2>

<h3>THE PLUGIN IS A FACILITATOR / IL PLUGIN È UN FACILITATORE</h3>
<p><b>EN:</b> STAC Browser <b>does not host or resell data</b>. It only helps
you <i>find</i> and <i>download</i> data already published by the official
providers (ESA, NASA, USGS, Microsoft, etc.). The data remains owned by and is
the responsibility of those providers and is subject to <b>their licenses</b>:
always read them before use and give the required attribution.</p>
<p><b>IT:</b> STAC Browser <b>non ospita né rivende dati</b>. È solo uno
strumento che ti aiuta a <i>trovare</i> e <i>scaricare</i> dati gi&agrave;
pubblicati dai provider ufficiali (ESA, NASA, USGS, Microsoft, ecc.). I dati
restano di propriet&agrave; e responsabilit&agrave; dei rispettivi provider e
sono soggetti alle <b>loro licenze</b>: leggile sempre prima dell'uso e cita
la fonte richiesta.</p>

<h3>OPEN vs REGISTERED SOURCES / FONTI LIBERE E CON REGISTRAZIONE</h3>
<table>
  <tr><th>Type / Tipo</th><th>Catalogs / Cataloghi</th><th>Download</th></tr>
  <tr><td><span class="badge-ok">Open / Libero</span></td>
      <td>Element84 Earth Search, Microsoft Planetary Computer (automatic SAS
      signing / firma SAS automatica), OpenLandMap, US GeoPlatform,
      Digital Earth Australia</td>
      <td>Automatic, no login / Automatico, nessun login</td></tr>
  <tr><td><span class="badge-warn">Registration / Registrazione</span></td>
      <td>USGS LandsatLook (EROS), NASA EarthData CMR, Copernicus Data
      Space</td>
      <td>Requires free account / Richiede account gratuito</td></tr>
</table>
<p><b>EN:</b> by default the plugin auto-downloads only from open sources. For
catalogs that need registration, the card shows a
<code>🔐 Registration required</code> button that opens the <b>official
site</b>; after registering, enter username/password or token in the
<code>🔐 Account</code> tab (credentials are stored locally only). When GDAL
gets a login page instead of the file, the plugin <b>never saves bogus
files</b> and tells you.</p>
<p><b>IT:</b> per impostazione predefinita il plugin scarica automaticamente
solo dalle fonti libere. Per i cataloghi che richiedono registrazione, sulla
scheda compare il pulsante <code>🔐 Registrazione richiesta</code> che apre il
<b>sito ufficiale</b>; dopo esserti registrato inserisci utente/password o
token nel tab <code>🔐 Account</code> (le credenziali sono salvate solo in
locale). Quando GDAL riceve una pagina di login al posto del file, il plugin
<b>non salva file fasulli</b> e te lo segnala.</p>

<h3>CLIPPING / RITAGLIO</h3>
<p><b>EN:</b> in the <code>🔍 Search</code> tab, <b>Output</b> group, pick
<code>📦 Full dataset</code> or <code>✂️ Automatic clip</code>. The clip
boundary can be the <b>OSM municipal boundary</b> (type the municipality name,
geometry from OpenStreetMap via Nominatim) or the <b>geometry of the active
QGIS layer/selection</b>. Clipping reads the remote COG directly through GDAL
<code>/vsicurl/</code>, fetching only the pixels inside the chosen area.</p>
<p><b>IT:</b> nel tab <code>🔍 Ricerca</code>, gruppo <b>Output</b>, scegli
<code>📦 Dataset completo</code> oppure <code>✂️ Ritaglio automatico</code>.
Per il ritaglio il confine pu&ograve; essere il <b>limite comunale OSM</b>
(digiti il nome del comune, geometria presa da OpenStreetMap via Nominatim)
oppure la <b>geometria del layer/selezione attiva</b> in QGIS. Il ritaglio
legge direttamente il COG remoto via GDAL <code>/vsicurl/</code>, quindi
scarica solo i pixel nell'area scelta.</p>

<h3>INCLUDED CATALOGS / CATALOGHI INCLUSI</h3>

<h4>1. Element84 Earth Search</h4>
<table>
  <tr><th>URL</th><td>
      <a href="https://earth-search.aws.element84.com/v1"
      >earth-search.aws.element84.com/v1</a></td></tr>
  <tr><th>Data / Dati</th>
      <td>Sentinel-2 L2A, Landsat Collection 2, NAIP,
      Copernicus DEM</td></tr>
  <tr><th>License / Licenza</th>
      <td>Sentinel-2: CC BY 4.0 (Copernicus/ESA).
      Landsat: Public Domain (USGS/NASA).</td></tr>
  <tr><th>Limits / Limiti</th><td>
      <span class="badge-ok">No explicit limit (AWS, fair use) /
      Nessun limite esplicito</span>
      </td></tr>
</table>

<h4>2. Microsoft Planetary Computer</h4>
<table>
  <tr><th>URL</th>
      <td><a href="https://planetarycomputer.microsoft.com/api/stac/v1"
      >planetarycomputer.microsoft.com/api/stac/v1</a></td></tr>
  <tr><th>Data / Dati</th>
      <td>Sentinel-2, Landsat, MODIS, NAIP, DEM, permafrost
      and much more / e molto altro</td></tr>
  <tr><th>License / Licenza</th>
      <td>Collection-dependent. Many are CC BY 4.0 or Public Domain. /
      Dipende dalla collezione. Molti sono CC BY 4.0 o Public Domain.</td></tr>
  <tr><th>Note</th>
      <td>Asset download may require a free SAS token for some datasets. /
      Il download degli asset può richiedere un token SAS gratuito per alcuni
      dataset.</td></tr>
  <tr><th>Limits / Limiti</th>
      <td><span class="badge-ok">No search limit / Nessun limite per la
      ricerca</span></td></tr>
</table>

<h4>3. USGS LandsatLook</h4>
<table>
  <tr><th>URL</th><td><a href="https://landsatlook.usgs.gov/stac-server"
      >landsatlook.usgs.gov/stac-server</a></td></tr>
  <tr><th>Data / Dati</th>
      <td>Landsat Collection 2 (Landsat 5, 7, 8, 9)</td></tr>
  <tr><th>License / Licenza</th><td>Public Domain &mdash; USGS/NASA.</td></tr>
  <tr><th>Limits / Limiti</th><td>
      <span class="badge-ok">No explicit limit (US Gov) / Nessun limite
      esplicito</span></td></tr>
</table>

<h4>4. NASA EarthData CMR</h4>
<table>
  <tr><th>URL</th><td><a href="https://cmr.earthdata.nasa.gov/stac"
      >cmr.earthdata.nasa.gov/stac</a></td></tr>
  <tr><th>Data / Dati</th>
      <td>MODIS, VIIRS, ASTER, OCO-2, hundreds of NASA datasets /
      centinaia di dataset NASA</td></tr>
  <tr><th>License / Licenza</th>
      <td>Public Domain. Some datasets require free EarthData registration. /
      Alcuni dataset richiedono registrazione EarthData gratuita.</td></tr>
  <tr><th>Limits / Limiti</th>
      <td><span class="badge-ok">Open search / Ricerca libera</span></td></tr>
</table>

<h4>5. OpenLandMap</h4>
<table>
  <tr><th>URL</th><td><a href="https://openlandmap.github.io/stac"
      >openlandmap.github.io/stac</a></td></tr>
  <tr><th>Data / Dati</th>
      <td>Soil variables, vegetation, global climate / Variabili
      pedologiche, vegetazione, clima globale</td></tr>
  <tr><th>License / Licenza</th><td>CC BY 4.0</td></tr>
  <tr><th>Limits / Limiti</th><td>
      <span class="badge-warn">~100 req/day (fair use) / ~100 req/giorno
      (fair use)</span></td></tr>
</table>

<h4>6. US GeoPlatform</h4>
<table>
  <tr><th>URL</th><td><a href="https://stac.geoplatform.gov"
      >stac.geoplatform.gov</a></td></tr>
  <tr><th>Data / Dati</th><td>US federal geospatial datasets / Dataset
      geospaziali federali USA</td></tr>
  <tr><th>License / Licenza</th><td>Public Domain (US Government)</td></tr>
  <tr><th>Limits / Limiti</th>
      <td><span class="badge-ok">No explicit limit / Nessun limite
      esplicito</span></td></tr>
</table>

<h4>7. Copernicus Data Space</h4>
<table>
  <tr><th>URL</th><td>
      <a href="https://catalogue.dataspace.copernicus.eu/stac"
      >catalogue.dataspace.copernicus.eu/stac</a></td></tr>
  <tr><th>Data / Dati</th>
      <td>Sentinel-1, Sentinel-2, Sentinel-3, Sentinel-5P</td></tr>
  <tr><th>License / Licenza</th>
      <td>CC BY 4.0 &mdash; Copernicus Programme / ESA</td></tr>
  <tr><th>Note</th><td>Download requires free registration at /
      Il download richiede registrazione gratuita su
      <a href="https://dataspace.copernicus.eu"
      >dataspace.copernicus.eu</a></td></tr>
  <tr><th>Limits / Limiti</th>
      <td><span class="badge-ok">Open search / Ricerca libera</span></td></tr>
</table>

<h4>8. Digital Earth Australia</h4>
<table>
  <tr><th>URL</th><td><a href="https://explorer.dea.ga.gov.au/stac"
      >explorer.dea.ga.gov.au/stac</a></td></tr>
  <tr><th>Data / Dati</th>
      <td>Landsat and Sentinel processed over Australia / Landsat e Sentinel
      elaborati su Australia</td></tr>
  <tr><th>License / Licenza</th>
      <td>CC BY 4.0 &mdash; Geoscience Australia</td></tr>
  <tr><th>Limits / Limiti</th>
      <td><span class="badge-ok">No explicit limit / Nessun limite
      esplicito</span></td></tr>
</table>

<hr class="section-sep"/>
<h3>STANDARD STAC</h3>
<p>STAC (SpatioTemporal Asset Catalog) is an open standard for cataloging
geospatial data. / STAC &egrave; uno standard aperto per la catalogazione di
dati geospaziali.<br>
Current version / Versione corrente: <strong>1.5.0</strong>.<br>
Official site / Sito ufficiale:
<a href="https://stacspec.org">https://stacspec.org</a></p>

<hr class="section-sep"/>
<h3>ATTRIBUTION REQUIRED / ATTRIBUZIONE RICHIESTA</h3>
<ul>
  <li><b>Sentinel:</b> "Contains modified Copernicus Sentinel data
      [year] / [anno] / ESA"</li>
  <li><b>Landsat:</b> "Courtesy of the U.S. Geological Survey"</li>
  <li><b>OpenLandMap:</b> "&copy; OpenLandMap contributors, CC BY 4.0"</li>
  <li><b>DEA:</b> "&copy; Commonwealth of Australia
      (Geoscience Australia), CC BY 4.0"</li>
</ul>

<hr class="section-sep"/>
<h3>TECHNICAL NOTES / NOTE TECNICHE</h3>
<ul>
  <li>The plugin uses GDAL/OGR <code>/vsicurl/</code> to open remote rasters
      in QGIS without downloading the whole file. / Il plugin usa
      <code>/vsicurl/</code> di GDAL/OGR per aprire raster remoti in QGIS
      senza scaricare l'intero file.</li>
  <li>Cloud Optimized GeoTIFF files (COG) are supported natively. / I file
      GeoTIFF cloud-optimized (COG) sono supportati nativamente.</li>
  <li>NetCDF, HDF5 and JPEG2000 may require additional GDAL drivers. /
      NetCDF, HDF5 e JPEG2000 potrebbero richiedere driver GDAL
      aggiuntivi.</li>
  <li>For very large files (&gt;1 GB), downloading before opening is
      recommended. / Per file molto grandi (&gt;1 GB), si raccomanda il
      download prima dell'apertura.</li>
</ul>

<hr class="section-sep"/>
<h3>OTHER PLUGINS BY THE AUTHOR / ALTRI PLUGIN DELL'AUTORE</h3>
<p>IT: usa il menù a tendina in fondo a questa scheda per scoprire gli
altri plugin della famiglia e aprire i rispettivi repository GitHub.<br>
EN: use the drop-down at the bottom of this tab to discover the other
plugins of the family and open their GitHub repositories.</p>
<ul>
  <li><b>SARIAG</b> &mdash; Sentinel-1 InSAR displacement time series /
      Serie temporali di spostamento InSAR Sentinel-1</li>
  <li><b>GeoBridge</b> &mdash; Unofficial IGM client: coordinate and layer
      conversion / Client IGM non ufficiale: conversione coordinate e
      layer</li>
  <li><b>Quick CRS Fixer</b> &mdash; Automatic layer CRS correction /
      Correzione automatica CRS layer</li>
  <li><b>GeoCSV Mapper</b> &mdash; Advanced geographic CSV import /
      Importazione CSV geografici avanzata</li>
  <li><b>Q-Press</b> &mdash; Professional cartographic PDF generator /
      Generatore PDF cartografico professionale</li>
  <li><b>QGIS Ledger</b> &mdash; Git-like version control for QGIS /
      Versionamento in stile Git per QGIS</li>
  <li><b>TAF Italia</b> &mdash; Cadastral Fiducial Points download /
      Download Punti Fiduciali catastali</li>
</ul>
<p>Author / Autore: Dott. Sarino Alfonso Grande &nbsp;|&nbsp;
   <a href="mailto:sino.grande@gmail.com">sino.grande@gmail.com</a>
   &nbsp;|&nbsp;
   <a href="https://sinocloud.it">sinocloud.it</a></p>

<hr class="section-sep"/>
<h3>PLUGIN LICENSE / LICENZA PLUGIN</h3>
<p>GPL-2.0 &mdash; Copyright (C) 2026 Dott. Sarino Alfonso Grande<br>
This plugin is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License version 2.<br>
Questo plugin &egrave; software libero: puoi redistribuirlo e/o modificarlo
secondo i termini della GNU General Public License versione 2.</p>

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
            self.catalogResult.emit(
                cat["id"], parsed, result.get("error") or "")
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
        import urllib.parse
        try:
            if urllib.parse.urlparse(self.url).scheme.lower() not in (
                    "http", "https"):
                return
            req = urllib.request.Request(
                self.url,
                headers={"User-Agent": "QGIS-STAC-Browser/1.0"},
            )
            # Scheme already validated above: only http/https reach here.
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                data = resp.read()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                self.cache[self.url] = pixmap
                self.pixmapReady.emit(self.url, pixmap)
        except Exception as exc:
            _log("Preview fetch failed for %s: %s" % (self.url, exc))


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
                progress_callback=lambda done, total: self.progress.emit(
                    done, total),
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

_DATA_TYPE_ORDER = (
    "orthophoto", "bands_1", "bands_2", "bands_3", "multispectral",
    "radar", "dem", "other",
)


def _data_type_label(lang, key):
    labels = {
        "orthophoto": ("Ortofoto", "Orthophoto"),
        "bands_1": ("1 banda", "1 band"),
        "bands_2": ("2 bande", "2 bands"),
        "bands_3": ("3 bande / RGB", "3 bands / RGB"),
        "multispectral": ("Multispettrale", "Multispectral"),
        "radar": ("Radar / SAR", "Radar / SAR"),
        "dem": ("DEM / Elevazione", "DEM / Elevation"),
        "other": ("Altri dati", "Other data"),
    }
    it, en = labels.get(key, labels["other"])
    return _t(lang, it, en)


def _data_type_icon(key):
    icons = {
        "orthophoto": "🗺",
        "bands_1": "◐",
        "bands_2": "◒",
        "bands_3": "🎨",
        "multispectral": "🌈",
        "radar": "📡",
        "dem": "⛰",
        "other": "📦",
    }
    return icons.get(key, "📦")


def _item_date(item):
    dt = item.get("datetime") or item.get("start_datetime") or ""
    return dt[:10] if dt else ""


def _item_title(item, max_chars=64):
    title = item.get("id") or item.get("collection") or "STAC item"
    return title if len(title) <= max_chars else title[:max_chars - 1] + "…"


def _asset_by_band_role(item):
    mapping = {}
    for asset in item.get("assets") or []:
        if not asset.get("is_raster"):
            continue
        for role in asset.get("band_roles") or []:
            mapping.setdefault(role, asset)
    return mapping


def _html_escape(value):
    import html
    return html.escape(str(value or ""))


def _format_elapsed(seconds):
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    if minutes:
        return "%dm %02ds" % (minutes, secs)
    return "%ds" % secs


def _plugin_icon_path():
    return os.path.join(os.path.dirname(__file__), "icon.svg")


def _make_progress_logo(size=56):
    logo = QLabel()
    logo.setAlignment(QtCompat.AlignCenter)
    pix = QIcon(_plugin_icon_path()).pixmap(QSize(size, size))
    if not pix.isNull():
        logo.setPixmap(pix)
    else:
        logo.setText("STAC")
    opacity = QGraphicsOpacityEffect(logo)
    opacity.setOpacity(1.0)
    logo.setGraphicsEffect(opacity)
    return logo, opacity


def _pulse_logo_opacity(opacity, fade_up, progress):
    floor = max(0.15, 0.7 - progress / 100.0 * 0.55)
    step = 0.12 + progress / 100.0 * 0.25
    op = opacity.opacity()
    op = op + step if fade_up else op - step
    if op <= floor:
        op = floor
        fade_up = True
    elif op >= 1.0:
        op = 1.0
        fade_up = False
    opacity.setOpacity(op)
    return fade_up


class _ItemDetailsDialog(QDialog):
    """Modal with complete STAC item metadata and asset inventory."""

    def __init__(self, item, lang="it", parent=None):
        super().__init__(parent)
        self.item = item
        self.lang = lang
        self.setWindowTitle(_t(lang, "Dettagli dataset", "Dataset details"))
        self.resize(680, 560)
        self.setStyleSheet(OCEAN_STYLE)

        layout = QVBoxLayout(self)
        title = QLabel(_item_title(item, 96))
        title.setWordWrap(True)
        title.setStyleSheet(
            "color:#5b9bd5; font-size:15px; font-weight:700;"
            "padding:4px 0;"
        )
        layout.addWidget(title)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(self._html())
        layout.addWidget(browser, 1)

        row = QHBoxLayout()
        row.addStretch()
        btn_close = QPushButton(_t(lang, "Chiudi", "Close"))
        btn_close.clicked.connect(self.accept)
        row.addWidget(btn_close)
        layout.addLayout(row)

    def _html(self):
        item = self.item
        L = self.lang
        dtype = item.get("data_type") or "other"
        roles = ", ".join(item.get("band_roles") or [])
        if not roles:
            roles = _t(L, "non dichiarati", "not declared")
        spectral = item.get("spectral_indices") or []
        if spectral:
            spectral_html = "".join(
                "<li><b>%s</b> <span>%s</span></li>" % (
                    _html_escape(opt.get("label_it")
                                 if L == "it" else opt.get("label_en")),
                    _html_escape(opt.get("formula")),
                )
                for opt in spectral
            )
        else:
            spectral_html = (
                "<li>%s</li>" %
                _html_escape(_t(
                    L,
                    "Nessun indice spettrale disponibile con le bande "
                    "dichiarate.",
                    "No spectral index is available from the declared bands.",
                ))
            )

        assets_html = []
        for asset in item.get("assets") or []:
            roles_txt = ", ".join(asset.get("roles") or [])
            bands_txt = ", ".join(asset.get("band_roles") or [])
            meta = []
            if roles_txt:
                meta.append(roles_txt)
            if bands_txt:
                meta.append(_t(L, "bande: ", "bands: ") + bands_txt)
            if asset.get("size_mb") is not None:
                meta.append("%s MB" % asset.get("size_mb"))
            meta_txt = " · ".join(meta)
            href = _html_escape(asset.get("href"))
            assets_html.append(
                "<tr><td><b>%s</b><br><span>%s</span></td>"
                "<td>%s</td><td><a href=\"%s\">link</a></td></tr>" % (
                    _html_escape(asset.get("title") or asset.get("key")),
                    _html_escape(meta_txt),
                    _html_escape(asset.get("type")),
                    href,
                )
            )
        assets_table = "\n".join(assets_html)

        style = """
        <style>
        body { background:#141a22; color:#f2f5f8; font-family:Segoe UI;
               font-size:12px; }
        h3 { color:#5b9bd5; margin:8px 0; }
        h4 { color:#c3ccd6; margin:14px 0 6px; }
        table { border-collapse:collapse; width:100%; }
        td, th { border-bottom:1px solid #2c3a48; padding:6px;
                 vertical-align:top; }
        th { color:#5b9bd5; text-align:left; width:170px; }
        a { color:#3b82f6; }
        .pill { display:inline-block; border:1px solid #2c3a48;
                border-radius:8px; padding:3px 8px; color:#5b9bd5;
                background:#1b2430; }
        span { color:#c3ccd6; }
        </style>
        """
        return """
        <html><head>%s</head><body>
        <h3>%s</h3>
        <table>
        <tr><th>%s</th><td>%s</td></tr>
        <tr><th>%s</th><td>%s</td></tr>
        <tr><th>%s</th><td><span class="pill">%s %s</span></td></tr>
        <tr><th>%s</th><td>%s</td></tr>
        <tr><th>%s</th><td>%s</td></tr>
        <tr><th>%s</th><td>%s</td></tr>
        <tr><th>%s</th><td>%s</td></tr>
        </table>
        <h4>%s</h4><ul>%s</ul>
        <h4>%s</h4>
        <table><tr><th>%s</th><th>Type</th><th>URL</th></tr>%s</table>
        </body></html>
        """ % (
            style,
            _html_escape(_t(L, "Metadati", "Metadata")),
            _html_escape(_t(L, "ID", "ID")),
            _html_escape(item.get("id")),
            _html_escape(_t(L, "Collezione", "Collection")),
            _html_escape(item.get("collection")),
            _html_escape(_t(L, "Tipo dato", "Data type")),
            _html_escape(_data_type_icon(dtype)),
            _html_escape(_data_type_label(L, dtype)),
            _html_escape(_t(L, "Data", "Date")),
            _html_escape(_item_date(item)),
            _html_escape(_t(L, "Piattaforma", "Platform")),
            _html_escape(item.get("platform")),
            _html_escape(_t(L, "Risoluzione", "Resolution")),
            _html_escape(item.get("gsd")),
            _html_escape(_t(L, "Bande", "Bands")),
            _html_escape(roles),
            _html_escape(_t(L, "Indici disponibili", "Available indices")),
            spectral_html,
            _html_escape(_t(L, "Asset", "Assets")),
            _html_escape(_t(L, "Nome", "Name")),
            assets_table,
        )


def _build_spectral_vrt(item, option, lang="it"):
    """Create a temporary VRT for a spectral index/composite."""
    try:
        from osgeo import gdal
    except ImportError as exc:
        raise RuntimeError(_t(
            lang,
            "GDAL non disponibile: impossibile creare il VRT.",
            "GDAL is not available: cannot create the VRT.",
        )) from exc
    import copy
    import tempfile
    from defusedxml.ElementTree import (
        fromstring as safe_xml_fromstring,
        parse as safe_xml_parse,
        tostring as safe_xml_tostring,
    )

    mapping = _asset_by_band_role(item)
    roles = tuple(option.get("requires") or ())
    hrefs = []
    for role in roles:
        asset = mapping.get(role)
        if not asset:
            raise RuntimeError(_t(
                lang,
                f"Banda mancante: {role}",
                f"Missing band: {role}",
            ))
        href = sign_href_if_needed(asset.get("href"))
        if href.startswith("http://") or href.startswith("https://"):
            href = "/vsicurl/" + href
        hrefs.append(href)

    safe_id = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in (_item_title(item, 48) or "stac_item")
    )
    out_dir = tempfile.gettempdir()
    if option.get("key") == "false_color":
        vrt_path = os.path.join(out_dir, safe_id + "_false_color.vrt")
        ds = gdal.BuildVRT(vrt_path, hrefs, separate=True)
        if ds is None:
            raise RuntimeError("GDAL BuildVRT failed.")
        ds = None
        return vrt_path

    stack_path = os.path.join(out_dir, safe_id + "_stack.vrt")
    ds = gdal.BuildVRT(stack_path, hrefs, separate=True)
    if ds is None:
        raise RuntimeError("GDAL BuildVRT failed.")
    ds = None

    tree = safe_xml_parse(stack_path)
    root = tree.getroot()
    sources = []
    for band in list(root.findall("VRTRasterBand")):
        source = band.find("ComplexSource") or band.find("SimpleSource")
        if source is not None:
            sources.append(copy.deepcopy(source))
        root.remove(band)
    if len(sources) < 2:
        raise RuntimeError("VRT sources missing.")

    derived = safe_xml_fromstring(
        '<VRTRasterBand dataType="Float32" band="1" '
        'subClass="VRTDerivedRasterBand">'
        '<NoDataValue>0</NoDataValue>'
        '<PixelFunctionType>stac_index</PixelFunctionType>'
        '<PixelFunctionLanguage>Python</PixelFunctionLanguage>'
        '<PixelFunctionCode />'
        '</VRTRasterBand>'
    )
    derived.find("PixelFunctionCode").text = """
import numpy as np
def stac_index(in_ar, out_ar, xoff, yoff, xsize, ysize, raster_xsize,
               raster_ysize, buf_radius, gt, **kwargs):
    a = in_ar[0].astype(np.float32)
    b = in_ar[1].astype(np.float32)
    den = a + b
    with np.errstate(divide='ignore', invalid='ignore'):
        out_ar[:] = np.where(den == 0, 0, (a - b) / den)
"""
    for source in sources[:2]:
        derived.append(source)
    root.append(derived)

    gdal.SetConfigOption("GDAL_VRT_ENABLE_PYTHON", "YES")
    index_path = os.path.join(
        out_dir, "%s_%s.vrt" % (safe_id, option.get("key"))
    )
    with open(index_path, "wb") as out_f:
        out_f.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
        out_f.write(safe_xml_tostring(root, encoding="utf-8"))
    return index_path


class SpectralIndexWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str, str)

    def __init__(self, item, option, output_path, lang="it", parent=None):
        super().__init__(parent)
        self.item = item
        self.option = option
        self.output_path = output_path
        self.lang = lang

    def run(self):
        try:
            from osgeo import gdal
        except ImportError as exc:
            self.finished.emit(False, str(exc), "")
            return

        try:
            self.progress.emit(
                2, _en_it("Preparing VRT...", "Preparazione VRT...")
            )
            vrt_path = _build_spectral_vrt(self.item, self.option, self.lang)

            def _cb(complete, _msg, _data):
                pct = 10 + int(max(0.0, min(1.0, complete)) * 90)
                self.progress.emit(pct, _en_it(
                    "Downloading/processing COG...",
                    "Download/elaborazione COG...",
                ))
                return 1

            self.progress.emit(
                10, _en_it("Writing GeoTIFF...", "Scrittura GeoTIFF...")
            )
            gdal.UseExceptions()
            options = gdal.TranslateOptions(
                format="GTiff",
                creationOptions=["COMPRESS=DEFLATE", "TILED=YES"],
                callback=_cb,
            )
            ds = gdal.Translate(self.output_path, vrt_path, options=options)
            if ds is None:
                raise RuntimeError("GDAL Translate failed.")
            ds = None
            self.progress.emit(100, _en_it("Done.", "Completato."))
            self.finished.emit(True, self.output_path, self.output_path)
        except Exception as exc:
            self.finished.emit(False, str(exc), "")


class BandDownloadWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str, object)

    def __init__(self, band_assets, output_dir, auth=None, lang="it",
                 parent=None):
        super().__init__(parent)
        self.band_assets = band_assets
        self.output_dir = output_dir
        self.auth = auth or {}
        self.lang = lang

    def run(self):
        saved = []
        total = max(1, len(self.band_assets))
        try:
            for idx, (role, asset) in enumerate(self.band_assets):
                title = asset.get("title") or asset.get("key") or role
                href = asset.get("href") or ""
                base = os.path.basename(href.split("?")[0])
                if not base:
                    base = "%s.tif" % (asset.get("key") or role)
                stem, ext = os.path.splitext(base)
                if not ext:
                    ext = ".tif"
                safe_stem = "".join(
                    c if c.isalnum() or c in "-_" else "_"
                    for c in "%s_%s" % (role, stem)
                )
                out_path = os.path.join(self.output_dir, safe_stem + ext)

                def _cb(done, file_total, i=idx, name=title):
                    file_pct = 0.0
                    status = _en_it(f"Downloading {name}",
                                    f"Scaricando {name}")
                    if file_total > 0:
                        file_pct = min(1.0, float(done) / float(file_total))
                        done_mb = done / (1024 * 1024)
                        total_mb = file_total / (1024 * 1024)
                        status += " · %.1f / %.1f MB" % (done_mb, total_mb)
                    else:
                        done_mb = done / (1024 * 1024)
                        status += " · %.1f MB" % done_mb
                    percent = int(((i + file_pct) / total) * 100)
                    self.progress.emit(percent, status)

                self.progress.emit(
                    int((idx / total) * 100),
                    _en_it(f"Preparing {title}", f"Preparazione {title}"),
                )
                download_asset(
                    href, out_path, progress_callback=_cb, auth=self.auth
                )
                saved.append((role, out_path))
            self.progress.emit(100, _t(
                self.lang,
                "Bands saved. / Bande salvate.",
                "Bands saved. / Bande salvate.",
            ))
            self.finished.emit(True, self.output_dir, saved)
        except Exception as exc:
            self.finished.emit(False, str(exc), saved)


class _SpectralProgressDialog(QDialog):
    def __init__(self, worker, lang="it", title=None, message=None,
                 parent=None):
        super().__init__(parent)
        self._lang = lang
        self._worker = worker
        self.success = False
        self.result_path = None
        self.result = None
        self._progress = 0
        self._started_at = time.monotonic()
        self.setWindowTitle(
            title or _en_it("Processing index", "Elaborazione indice")
        )
        self.setModal(True)
        self.resize(430, 210)
        self.setStyleSheet(OCEAN_STYLE)

        layout = QVBoxLayout(self)
        layout.setAlignment(QtCompat.AlignCenter)

        self.logo, self._opacity = _make_progress_logo(64)
        layout.addWidget(self.logo)
        self._fade_up = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse)
        self._timer.start(90)

        self.lbl = QLabel(message or _en_it(
            "Downloading and processing data...",
            "Download ed elaborazione del dato in corso...",
        ))
        self.lbl.setAlignment(QtCompat.AlignCenter)
        self.lbl.setStyleSheet("color:#f2f5f8;")
        layout.addWidget(self.lbl)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#8a97a5; font-size:11px;")
        layout.addWidget(self.lbl_status)

        self.btn_close = QPushButton(_en_it("Close", "Chiudi"))
        self.btn_close.setEnabled(False)
        self.btn_close.clicked.connect(self.accept)
        layout.addWidget(self.btn_close)

        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.start()

    def _pulse(self):
        self._fade_up = _pulse_logo_opacity(
            self._opacity, self._fade_up, self._progress
        )
        interval = max(28, 90 - int(self._progress * 0.6))
        if interval != self._timer.interval():
            self._timer.setInterval(interval)

    def _on_progress(self, percent, message):
        self._progress = max(0, min(100, percent))
        self.bar.setValue(self._progress)
        elapsed = _format_elapsed(time.monotonic() - self._started_at)
        self.lbl_status.setText("%s · %s: %s" % (
            message,
            _en_it("time", "tempo"),
            elapsed,
        ))

    def _on_finished(self, success, message, result):
        elapsed = _format_elapsed(time.monotonic() - self._started_at)
        self._timer.stop()
        self._opacity.setOpacity(1.0)
        self.success = success
        self.result = result if success else None
        self.result_path = (
            result if success and isinstance(result, str) else None
        )
        if success:
            self.bar.setValue(100)
            if isinstance(result, list):
                self.lbl.setText(_en_it("Bands saved.", "Bande salvate."))
            else:
                self.lbl.setText(_en_it("Index saved.", "Indice salvato."))
            self.lbl_status.setText("%s · %s: %s" % (
                message,
                _en_it("total time", "tempo totale"),
                elapsed,
            ))
            self.btn_close.setEnabled(True)
            QTimer.singleShot(1200, self.accept)
        else:
            self.lbl.setText(_en_it("Processing error",
                                    "Errore elaborazione"))
            self.lbl_status.setText("%s · %s: %s" % (
                message[:180],
                _en_it("time", "tempo"),
                elapsed,
            ))
            self.btn_close.setEnabled(True)


class _BandSelectionDialog(QDialog):
    def __init__(self, band_assets, lang="it", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.band_assets = band_assets
        self.checks = []
        self.setWindowTitle(_en_it("Choose bands", "Scegli bande"))
        self.resize(480, 360)
        self.setStyleSheet(OCEAN_STYLE)

        layout = QVBoxLayout(self)
        title = QLabel(_en_it(
            "Select bands to download",
            "Seleziona le bande da scaricare",
        ))
        title.setStyleSheet("color:#5b9bd5; font-size:14px; font-weight:700;")
        layout.addWidget(title)

        note = QLabel(_en_it(
            "You can download all bands or only the useful ones. Bands will "
            "be saved locally before loading into QGIS.",
            "Puoi scaricarle tutte o solo quelle utili. Le bande verranno "
            "salvate localmente prima del caricamento in QGIS.",
        ))
        note.setWordWrap(True)
        note.setStyleSheet("color:#c3ccd6; font-size:12px;")
        layout.addWidget(note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        box = QVBoxLayout(content)
        box.setSpacing(6)
        for role, asset in band_assets:
            label = "%s · %s" % (
                role.upper(),
                asset.get("title") or asset.get("key") or asset.get("href"),
            )
            chk = QCheckBox(label)
            chk.setChecked(True)
            chk.toggled.connect(self._update_accept)
            chk.setToolTip(asset.get("href") or "")
            box.addWidget(chk)
            self.checks.append((chk, role, asset))
        box.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        select_row = QHBoxLayout()
        btn_all = QPushButton(_en_it("All", "Tutte"))
        btn_all.clicked.connect(lambda: self._set_all(True))
        select_row.addWidget(btn_all)
        btn_none = QPushButton(_en_it("None", "Nessuna"))
        btn_none.clicked.connect(lambda: self._set_all(False))
        select_row.addWidget(btn_none)
        select_row.addStretch()
        layout.addLayout(select_row)

        row = QHBoxLayout()
        row.addStretch()
        self.btn_ok = QPushButton(_en_it("Download selected",
                                         "Scarica selezionate"))
        self.btn_ok.clicked.connect(self.accept)
        row.addWidget(self.btn_ok)
        btn_cancel = QPushButton(_en_it("Cancel", "Annulla"))
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        layout.addLayout(row)
        self._update_accept()

    def _set_all(self, checked):
        for chk, _role, _asset in self.checks:
            chk.setChecked(checked)
        self._update_accept()

    def _update_accept(self):
        self.btn_ok.setEnabled(any(chk.isChecked()
                                   for chk, _r, _a in self.checks))

    def selected_bands(self):
        return [
            (role, asset)
            for chk, role, asset in self.checks
            if chk.isChecked()
        ]


class _SpectralCompareDialog(QDialog):
    """Explicitly save COG-backed spectral indices before QGIS loading."""

    def __init__(self, item, lang="it", auth=None, parent=None):
        super().__init__(parent)
        self.item = item
        self.lang = lang
        self.auth = auth or {}
        self.setWindowTitle(_en_it("COG spectral indices",
                                   "Indici spettrali COG"))
        self.resize(560, 420)
        self.setStyleSheet(OCEAN_STYLE)

        layout = QVBoxLayout(self)
        title = QLabel(_item_title(item, 82))
        title.setWordWrap(True)
        title.setStyleSheet("color:#5b9bd5; font-size:14px; font-weight:700;")
        layout.addWidget(title)

        intro = QLabel(_en_it(
            "NDVI, NDWI and False Color can read large portions of remote "
            "COGs and slow QGIS down. For safety they are computed only if "
            "you enable the flag below and are saved as a local GeoTIFF.",
            "Gli indici NDVI, NDWI e Falso Colore possono leggere molte "
            "porzioni di COG remoti e rallentare QGIS. Per sicurezza vengono "
            "calcolati solo se abiliti il flag sotto e vengono salvati come "
            "GeoTIFF locale.",
        ))
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#c3ccd6; font-size:12px;")
        layout.addWidget(intro)

        self.index_buttons = []
        self.chk_enable = QCheckBox(_en_it(
            "Enable index download/processing and local save",
            "Abilita download/elaborazione indici e salvataggio locale",
        ))
        self.chk_enable.setChecked(False)
        self.chk_enable.setStyleSheet("color:#f59e0b; font-size:12px;")
        self.chk_enable.toggled.connect(self._toggle_index_buttons)
        layout.addWidget(self.chk_enable)

        self.options = item.get("spectral_indices") or []
        if self.options:
            for opt in self.options:
                layout.addWidget(self._option_widget(opt))
        else:
            missing = QLabel(_en_it(
                "This record does not declare enough red/green/NIR bands to "
                "compute the indices.",
                "Questo record non dichiara una combinazione sufficiente di "
                "bande red/green/NIR per calcolare gli indici.",
            ))
            missing.setWordWrap(True)
            missing.setStyleSheet(
                "background:rgba(245,158,11,0.08);"
                "border:1px solid rgba(245,158,11,0.35);"
                "border-radius:6px; padding:8px; color:#f59e0b;"
            )
            layout.addWidget(missing)

        layout.addStretch()
        row = QHBoxLayout()
        btn_bands = QPushButton(_en_it("💾 Choose COG bands",
                                       "💾 Scegli bande COG"))
        btn_bands.clicked.connect(self._load_declared_bands)
        btn_bands.setEnabled(bool(self._available_band_assets()))
        btn_bands.setToolTip(_en_it(
            "Choose all bands or only some of them, then save them locally.",
            "Scegli tutte o solo alcune bande, poi salvale localmente.",
        ))
        row.addWidget(btn_bands)
        row.addStretch()
        btn_close = QPushButton(_en_it("Close", "Chiudi"))
        btn_close.clicked.connect(self.accept)
        row.addWidget(btn_close)
        layout.addLayout(row)
        self._toggle_index_buttons(self.chk_enable.isChecked())

    def _option_widget(self, opt):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background:#1b2430; border:1px solid #2c3a48;"
            "border-radius:8px; } QLabel { background:transparent; }"
        )
        box = QVBoxLayout(frame)
        box.setContentsMargins(10, 8, 10, 8)

        label = _en_it(opt.get("label_en"), opt.get("label_it"))
        lbl = QLabel("<b style='color:#5b9bd5;'>%s</b><br>"
                     "<span style='color:#c3ccd6;'>%s</span>" % (
                         _html_escape(label), _html_escape(opt.get("formula"))
                     ))
        lbl.setTextFormat(QtCompat.RichText)
        box.addWidget(lbl)

        assets = opt.get("asset_keys") or {}
        bands = " · ".join("%s: %s" % (k.upper(), v)
                           for k, v in assets.items())
        lbl_assets = QLabel(bands)
        lbl_assets.setWordWrap(True)
        lbl_assets.setStyleSheet("color:#8a97a5; font-size:11px;")
        box.addWidget(lbl_assets)

        row = QHBoxLayout()
        row.addStretch()
        btn = QPushButton(_en_it("💾 Save index", "💾 Salva indice"))
        btn.setEnabled(False)
        btn.setToolTip(_en_it(
            "Download/process the index and save it as a local GeoTIFF.",
            "Scarica/elabora l'indice e salvalo come GeoTIFF locale.",
        ))
        btn.clicked.connect(lambda _c, o=opt: self._save_index(o))
        row.addWidget(btn)
        self.index_buttons.append(btn)
        box.addLayout(row)
        return frame

    def _toggle_index_buttons(self, enabled):
        for btn in self.index_buttons:
            btn.setEnabled(bool(enabled))

    def _available_band_assets(self):
        roles_order = ("blue", "green", "red", "nir", "swir16", "swir22")
        selected = []
        seen = set()
        assets = self.item.get("assets") or []
        for role in roles_order:
            for asset in assets:
                if not asset.get("is_raster"):
                    continue
                if role not in (asset.get("band_roles") or []):
                    continue
                uid = asset.get("href") or asset.get("key") or id(asset)
                if uid in seen:
                    continue
                seen.add(uid)
                selected.append((role, asset))
        return selected

    def _load_declared_bands(self):
        band_assets = self._available_band_assets()
        if not band_assets:
            return
        sel = _BandSelectionDialog(
            band_assets, lang=self.lang, parent=self
        )
        if not sel.exec():
            return
        selected = sel.selected_bands()
        if not selected:
            return
        QMessageBox.information(
            self,
            "STAC Browser",
            _t(
                self.lang,
                "Choose a destination folder. The selected bands will be "
                "downloaded one by one with logo, percentage and load time. / "
                "Scegli una cartella di destinazione. Le bande selezionate "
                "verranno scaricate una alla volta, con logo, percentuale e "
                "tempo di caricamento.",
                "Choose a destination folder. The selected bands will be "
                "downloaded one by one with logo, percentage and load time. / "
                "Scegli una cartella di destinazione. Le bande selezionate "
                "verranno scaricate una alla volta, con logo, percentuale e "
                "tempo di caricamento.",
            ),
        )
        out_dir = QFileDialog.getExistingDirectory(
            self,
            _en_it("Folder for bands", "Cartella per le bande"),
        )
        if not out_dir:
            return
        worker = BandDownloadWorker(
            selected, out_dir, auth=self.auth, lang=self.lang, parent=self
        )
        dlg = _SpectralProgressDialog(
            worker,
            lang=self.lang,
            title=_en_it("COG band download", "Download bande COG"),
            message=_en_it(
                "Saving selected bands locally...",
                "Salvataggio locale delle bande selezionate...",
            ),
            parent=self,
        )
        dlg.exec()
        if not dlg.success or not dlg.result:
            return
        QMessageBox.information(
            self,
            "STAC Browser",
            _t(
                self.lang,
                "Bands saved. Keep them locally to avoid new heavy remote "
                "loads in QGIS. / Bande salvate. Conservale localmente per "
                "evitare nuovi caricamenti remoti pesanti in QGIS.",
                "Bands saved. Keep them locally to avoid new heavy remote "
                "loads in QGIS. / Bande salvate. Conservale localmente per "
                "evitare nuovi caricamenti remoti pesanti in QGIS.",
            ),
        )
        if _HAS_QGIS:
            for role, path in dlg.result:
                layer_name = "%s %s" % (
                    _item_title(self.item, 36), role.upper()
                )
                layer = QgsRasterLayer(path, layer_name)
                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer)

    def _save_index(self, option):
        if not self.chk_enable.isChecked():
            return
        QMessageBox.information(
            self,
            "STAC Browser",
            _t(
                self.lang,
                "Choose where to save the local GeoTIFF. The plugin will "
                "read the remote COGs and compute the index: this can take "
                "time depending on data size and network speed. / Ora scegli "
                "dove salvare il GeoTIFF locale. Il plugin leggerà i COG "
                "remoti e calcolerà l'indice: l'operazione può richiedere "
                "tempo in base alla dimensione del dato e alla connessione.",
                "Choose where to save the local GeoTIFF. The plugin will "
                "read the remote COGs and compute the index: this can take "
                "time depending on data size and network speed. / Ora scegli "
                "dove salvare il GeoTIFF locale. Il plugin leggerà i COG "
                "remoti e calcolerà l'indice: l'operazione può richiedere "
                "tempo in base alla dimensione del dato e alla connessione.",
            ),
        )
        label = _en_it(option.get("label_en"), option.get("label_it"))
        base = "%s_%s.tif" % (
            _item_title(self.item, 40),
            option.get("key") or "index",
        )
        safe_name = "".join(
            c if c.isalnum() or c in "-_." else "_"
            for c in base
        )
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            _en_it(f"Save {label}", f"Salva {label}"),
            safe_name,
            "GeoTIFF (*.tif)",
        )
        if not out_path:
            return
        worker = SpectralIndexWorker(
            self.item, option, out_path, lang=self.lang, parent=self
        )
        dlg = _SpectralProgressDialog(worker, lang=self.lang, parent=self)
        dlg.exec()
        if dlg.success and dlg.result_path:
            QMessageBox.information(
                self,
                "STAC Browser",
                _t(
                    self.lang,
                    f"Data saved: {dlg.result_path}\n\n"
                    "Keep this local file: it avoids recalculating the index "
                    "and reduces the risk of slowing QGIS down.\n\n"
                    f"Dato salvato: {dlg.result_path}\n\n"
                    "Conserva questo file locale: evita di ricalcolare "
                    "l'indice e riduce il rischio di rallentamenti in QGIS.",
                    f"Data saved: {dlg.result_path}\n\n"
                    "Keep this local file: it avoids recalculating the index "
                    "and reduces the risk of slowing QGIS down.\n\n"
                    f"Dato salvato: {dlg.result_path}\n\n"
                    "Conserva questo file locale: evita di ricalcolare "
                    "l'indice e riduce il rischio di rallentamenti in QGIS.",
                ),
            )
            if _HAS_QGIS:
                layer = QgsRasterLayer(dlg.result_path, label)
                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer)

    def _add_vrt(self, option):
        if not _HAS_QGIS:
            return
        try:
            vrt_path = _build_spectral_vrt(self.item, option, self.lang)
            layer_name = "%s %s" % (
                _item_title(self.item, 36),
                option.get("label_it")
                if self.lang == "it" else option.get("label_en"),
            )
            layer = QgsRasterLayer(vrt_path, layer_name)
            if not layer.isValid():
                raise RuntimeError(_t(
                    self.lang,
                    "Il VRT è stato creato ma QGIS non lo considera valido.",
                    "The VRT was created but QGIS does not consider it valid.",
                ))
            QgsProject.instance().addMapLayer(layer)
            if _iface:
                _iface.messageBar().pushSuccess(
                    "STAC Browser",
                    _t(self.lang, "Indice aggiunto a QGIS.",
                       "Index added to QGIS."),
                )
        except Exception as exc:
            QMessageBox.warning(self, "STAC Browser", str(exc))

    def _build_vrt(self, option):
        return _build_spectral_vrt(self.item, option, self.lang)


class ItemCard(QFrame):
    """A compact card widget showing a single STAC item."""

    def __init__(self, item, lang="it", preview_cache=None,
                 catalog=None, auth=None, controller=None,
                 details_callback=None, spectral_callback=None, parent=None):
        super().__init__(parent)
        self.item = item
        self.lang = lang
        self.preview_cache = preview_cache if preview_cache is not None else {}
        self.catalog = catalog or {}
        self.auth = auth or {}
        self.controller = controller
        self.details_callback = details_callback
        self.spectral_callback = spectral_callback
        self._preview_label = None
        self._fetcher = None

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            ItemCard {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #22303e, stop:1 #141a22);
                border: 1px solid #2c3a48;
                border-radius: 10px;
            }
            ItemCard:hover { border-color: #4d84b8; }
        """)
        self.setFixedWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Preview image
        self._preview_label = QLabel()
        self._preview_label.setFixedSize(224, 112)
        self._preview_label.setStyleSheet(
            "background:#141a22; border-radius:6px; border:1px solid #2c3a48;"
        )
        self._preview_label.setAlignment(QtCompat.AlignCenter)
        self._preview_label.setText("🛰️")
        layout.addWidget(self._preview_label)

        # Collection badge
        collection = item.get("collection") or item.get("catalog_name") or ""
        if collection:
            lbl_col = QLabel(collection)
            lbl_col.setStyleSheet(
                "background:rgba(52,211,153,0.12); color:#5b9bd5;"
                "padding:2px 8px;"
                "border-radius:8px; font-size:10px; font-weight:600;"
            )
            lbl_col.setAlignment(QtCompat.AlignCenter)
            layout.addWidget(lbl_col)

        dtype = item.get("data_type") or "other"
        lbl_dtype = QLabel(
            "%s %s" % (
                _data_type_icon(dtype),
                _data_type_label(lang, dtype),
            )
        )
        lbl_dtype.setStyleSheet(
            "background:rgba(91,155,213,0.08); color:#c3ccd6;"
            "padding:2px 8px; border-radius:8px; font-size:10px;"
            "font-weight:600;"
        )
        lbl_dtype.setAlignment(QtCompat.AlignCenter)
        layout.addWidget(lbl_dtype)

        # Item ID (truncated)
        item_id = item.get("id") or "—"
        lbl_id = QLabel(item_id)
        lbl_id.setStyleSheet("color:#f2f5f8; font-size:11px; font-weight:600;")
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
            lbl_meta.setStyleSheet("color:#c3ccd6; font-size:11px;")
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
            lbl_metrics.setStyleSheet("color:#8a97a5; font-size:10px;")
            lbl_metrics.setWordWrap(True)
            layout.addWidget(lbl_metrics)

        band_roles = item.get("band_roles") or []
        if band_roles:
            lbl_roles = QLabel(
                "%s%s" % (
                    _t(lang, "Canali: ", "Channels: "),
                    ", ".join(role.upper() for role in band_roles[:6]),
                )
            )
            lbl_roles.setStyleSheet("color:#8a97a5; font-size:10px;")
            lbl_roles.setWordWrap(True)
            layout.addWidget(lbl_roles)

        # Assets list (max 6)
        assets = item.get("assets") or []
        if assets:
            lbl_assets_title = QLabel(_t(lang, "Asset:", "Assets:"))
            lbl_assets_title.setStyleSheet(
                "color:#8a97a5; font-size:10px; margin-top:4px;")
            layout.addWidget(lbl_assets_title)

            for a in assets[:6]:
                a_title = a.get("title") or a.get("key") or ""
                a_type = a.get("type") or ""
                icon = "📥" if a.get("is_raster") else "📎"
                color = "#5b9bd5" if a.get("is_raster") else "#8a97a5"
                size_mb = a.get("size_mb")
                size_str = f" ({size_mb} MB)" if size_mb is not None else ""
                lbl_a = QLabel(
                    f'<span style="color:{color}">{icon}</span>'
                    f' <span style="font-size:10px;">'
                    f'{a_title[:28]}{size_str}</span>')
                lbl_a.setStyleSheet("color:#c3ccd6;")
                lbl_a.setToolTip(f"{a_title}\n{a_type}\n{a.get('href', '')}")
                layout.addWidget(lbl_a)

        layout.addStretch()

        tool_row = QHBoxLayout()
        tool_row.setSpacing(4)
        btn_details = QPushButton(_t(lang, "ℹ Dettagli", "ℹ Details"))
        btn_details.setObjectName("btnDetails")
        btn_details.setToolTip(
            _t(lang, "Apri metadati e asset", "Open metadata and assets")
        )
        btn_details.clicked.connect(self._show_details)
        tool_row.addWidget(btn_details)

        btn_spectral = QPushButton(_t(lang, "🧪 Indici", "🧪 Indices"))
        btn_spectral.setObjectName("btnSpectral")
        btn_spectral.setToolTip(_t(
            lang,
            "Confronta NDVI, NDWI e Falso Colore da COG",
            "Compare NDVI, NDWI and False Color from COGs",
        ))
        btn_spectral.setEnabled(bool(item.get("spectral_indices")))
        btn_spectral.clicked.connect(self._show_spectral)
        tool_row.addWidget(btn_spectral)
        layout.addLayout(tool_row)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        best = best_raster_asset(item)

        # Catalogs that require a free registration are not downloaded blindly:
        # without credentials we only offer a link to the official portal, so
        # the plugin never fetches a login page by mistake.
        auth_required = bool(self.catalog.get("auth"))
        has_creds = bool(
            self.auth.get("token") or (
                self.auth.get("username") and self.auth.get("password")
            )
        )

        if auth_required and not has_creds:
            btn_portal = QPushButton(
                _t(lang, "🔐 Registrazione richiesta",
                   "🔐 Registration required")
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
                lambda _checked, i=item, a=best:
                self._on_action("download", i, a)
            )
            btn_row.addWidget(btn_dl)

        layout.addLayout(btn_row)

        # Load preview
        self._load_preview()

    def _show_details(self):
        if self.details_callback:
            self.details_callback(self.item)

    def _show_spectral(self):
        if self.spectral_callback:
            self.spectral_callback(self.item)

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
        if (
            self.controller is not None and
            self.controller.is_clip_mode()
        ):
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
                        _en_it(
                            f"Layer added: {item.get('id', '')}",
                            f"Layer aggiunto: {item.get('id', '')}",
                        ),
                    )
            else:
                if _iface:
                    _iface.messageBar().pushCritical(
                        "STAC Browser",
                        _t(self.lang,
                           "Layer non valido: l'asset potrebbe richiedere "
                           "un login presso il provider "
                           "(USGS/NASA/Copernicus).",
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
        layout.setAlignment(QtCompat.AlignCenter)
        self.logo, self._opacity = _make_progress_logo(56)
        layout.addWidget(self.logo)
        self._fade_up = False
        self._progress = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse)
        self._timer.start(90)

        fname = os.path.basename(output_path)
        self.lbl = QLabel(
            _t(lang, f"Scaricando {fname}...", f"Downloading {fname}..."))
        self.lbl.setAlignment(QtCompat.AlignCenter)
        self.lbl.setStyleSheet("color:#f2f5f8;")
        layout.addWidget(self.lbl)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#8a97a5; font-size:11px;")
        layout.addWidget(self.lbl_status)

        btn_cancel = QPushButton(_t(lang, "Annulla", "Cancel"))
        btn_cancel.setObjectName("btnCancel")
        btn_cancel.clicked.connect(self._cancel)
        layout.addWidget(btn_cancel)

        self._worker = DownloadWorker(
            href, output_path, auth=auth, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()
        self._lang = lang
        self._cancelled = False
        self._started_at = time.monotonic()

    def _pulse(self):
        self._fade_up = _pulse_logo_opacity(
            self._opacity, self._fade_up, self._progress
        )
        interval = max(28, 90 - int(self._progress * 0.6))
        if interval != self._timer.interval():
            self._timer.setInterval(interval)

    def _on_progress(self, done, total):
        elapsed = _format_elapsed(time.monotonic() - self._started_at)
        if total > 0:
            pct = int(done * 100 / total)
            self._progress = max(0, min(100, pct))
            self.bar.setRange(0, 100)
            self.bar.setValue(pct)
            done_mb = done / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self.lbl_status.setText(
                f"{done_mb:.1f} / {total_mb:.1f} MB · "
                f"{_t(self._lang, 'tempo', 'time')}: {elapsed}"
            )
        else:
            self.bar.setRange(0, 0)
            done_mb = done / (1024 * 1024)
            self.lbl_status.setText(
                f"{done_mb:.1f} MB · "
                f"{_t(self._lang, 'tempo', 'time')}: {elapsed}"
            )

    def _on_finished(self, success, message):
        elapsed = _format_elapsed(time.monotonic() - self._started_at)
        self._timer.stop()
        self._opacity.setOpacity(1.0)
        if success:
            self.lbl.setText(
                _t(self._lang, "Download completato!",
                   "Download complete!"))
            self.lbl_status.setText(
                "%s · %s: %s" % (
                    message,
                    _t(self._lang, "tempo totale", "total time"),
                    elapsed,
                )
            )
            if _iface:
                _iface.messageBar().pushSuccess(
                    "STAC Browser",
                    _t(self._lang, f"Salvato: {message}", f"Saved: {message}"),
                )
        else:
            self.lbl.setText(
                _t(self._lang, "Errore download", "Download error"))
            self.lbl_status.setText(
                "%s · %s: %s" % (
                    message,
                    _t(self._lang, "tempo", "time"),
                    elapsed,
                )
            )
        QTimer.singleShot(1500, self.accept)

    def _cancel(self):
        self._cancelled = True
        if hasattr(self, "_timer"):
            self._timer.stop()
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
        self._started_at = time.monotonic()
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
        self.lbl.setStyleSheet("color:#f2f5f8;")
        layout.addWidget(self.lbl)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(QtCompat.AlignCenter)
        self.lbl_status.setStyleSheet("color:#8a97a5; font-size:11px;")
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
        elapsed = _format_elapsed(time.monotonic() - self._started_at)
        self.lbl_status.setText(
            "%s%% · %s: %s" % (
                self._progress,
                _t(self._lang, "tempo", "time"),
                elapsed,
            )
        )

    def _on_finished(self, success, message):
        elapsed = _format_elapsed(time.monotonic() - self._started_at)
        self._timer.stop()
        self._opacity.setOpacity(1.0)
        self.success = success
        if success:
            self.result_path = message
            self.bar.setValue(100)
            self.lbl.setText(_t(self._lang, "Completato!", "Done!"))
            self.lbl_status.setText(
                "%s: %s" % (
                    _t(self._lang, "Tempo totale", "Total time"),
                    elapsed,
                )
            )
        else:
            self.lbl.setText(_t(self._lang, "Errore", "Error"))
            self.lbl_status.setText(
                "%s · %s: %s" % (
                    message[:160],
                    _t(self._lang, "tempo", "time"),
                    elapsed,
                )
            )
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
        self.resize(1180, 820)
        self.setMinimumSize(QSize(760, 540))
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
        self._last_result_col_count = 0
        self._resize_rerender_pending = False
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
        self.lbl_header.setStyleSheet("color: #5b9bd5; padding: 4px 0;")
        header_row.addWidget(self.lbl_header)
        header_row.addStretch()
        self.btn_lang = QPushButton(plugin_hub.LANG_LABEL_EN)
        self.btn_lang.setObjectName("btnLang")
        self.btn_lang.setFixedWidth(72)
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
        self.lbl_status.setStyleSheet("color: #8a97a5; font-size: 11px;")
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not getattr(self, "_results", None):
            return
        if not hasattr(self, "scroll_area"):
            return
        new_count = self._result_column_count()
        if new_count == self._last_result_col_count:
            return
        if self._resize_rerender_pending:
            return
        self._resize_rerender_pending = True
        QTimer.singleShot(140, self._rerender_results_after_resize)

    def _rerender_results_after_resize(self):
        self._resize_rerender_pending = False
        if not getattr(self, "_results", None):
            return
        new_count = self._result_column_count()
        if new_count == self._last_result_col_count:
            return
        self._rerender_results()

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
                    _t(L,
                       "Nessuna area di interesse definita "
                       "per il ritaglio.",
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
        dlg = _ProcessingDialog(worker, _plugin_icon_path(),
                                lang=L, parent=self)
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
        self.lbl_bbox.setStyleSheet("color:#8a97a5; font-size:11px;")
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
        self.lbl_search_status.setStyleSheet("color:#c3ccd6; font-size:11px;")
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
        self.cb_output.currentIndexChanged.connect(
            self._on_output_mode_changed)
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
            "color:#5b9bd5; font-size:13px; font-weight:600; padding:6px 4px;"
        )
        layout.addWidget(self.lbl_summary)

        # Scroll area for cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            QtCompat.ScrollBarAsNeeded)
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
            "color:#c3ccd6; font-size:12px; padding:4px 2px;"
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
                free_vbox.addWidget(
                    self._make_catalog_box(cat, with_creds=False))
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
                auth_vbox.addWidget(
                    self._make_catalog_box(cat, with_creds=True))
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
        desc.setStyleSheet("color:#c3ccd6; font-size:11px;")
        form.addWidget(desc)

        lic = QLabel()
        lic.setOpenExternalLinks(True)
        lic.setWordWrap(True)
        lic.setStyleSheet("color:#8a97a5; font-size:11px;")
        lic_url = cat.get("license_url")
        lic_txt = cat.get("license", "")
        if lic_url:
            lic.setText(
                f'⚖️ {lic_txt} &nbsp;'
                f'<a href="{lic_url}" style="color:#3b82f6;">'
                f'↗ licenza/license</a>'
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
        layout.addWidget(browser, 1)
        self.family_widget = plugin_hub.make_family_widget(
            "stac_browser", lang=self.lang
        )
        layout.addWidget(self.family_widget)

    # ──────────────────────────────────────────────────────────────
    # Language toggle
    # ──────────────────────────────────────────────────────────────

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "it" else "it"
        self._update_ui_lang()

    def _update_ui_lang(self):
        L = self.lang
        self.btn_lang.setText(plugin_hub.lang_button_label(L))
        if hasattr(self, "family_widget"):
            self.family_widget.set_lang(L)
        self.setWindowTitle(
            _t(L, "GeoFusion — STAC Browser", "GeoFusion — STAC Browser"))
        self.lbl_header.setText(_t(L, "🛰️ STAC Browser", "🛰️ STAC Browser"))
        self.btn_close.setText(_t(L, "Chiudi", "Close"))

        # Tab labels
        self.tabs.setTabText(self.TAB_SEARCH, _t(L, "🔍 Ricerca", "🔍 Search"))
        self.tabs.setTabText(
            self.TAB_RESULTS, _t(L, "📋 Risultati", "📋 Results"))
        self.tabs.setTabText(
            self.TAB_ACCOUNT, _t(L, "🗂 Cataloghi", "🗂 Catalogs"))
        self.tabs.setTabText(self.TAB_INFO, "ℹ Info")

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
        self.chk_dates.setText(
            _t(L, "Abilita filtro date", "Enable date filter"))
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

        # Re-render result cards so button labels and section headers
        # reflect the new language.
        if self._results:
            self._clear_result_cards()
            for cat in STAC_CATALOGS:
                cid = cat["id"]
                if cid in self._results:
                    self._add_catalog_section(
                        cat,
                        self._results[cid],
                        self._errors.get(cid, ""),
                    )
            self._update_summary()

    def _refresh_bbox_label(self):
        L = self.lang
        if self._bbox:
            w, s, e, n = self._bbox
            self.lbl_bbox.setText(
                f"Area: W={w:.4f}° E={e:.4f}° S={s:.4f}° N={n:.4f}°"
            )
        else:
            self.lbl_bbox.setText(
                _t(L, "Nessuna area selezionata", "No area selected"))

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
        except Exception as exc:
            _log("Failed to zoom canvas to item extent: %s" % exc)

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
                   "Verrà effettuato il ritaglio vicino "
                   "all'area più prossima indicata "
                   "(utilizzando il rettangolo).",
                   "Exact boundary not available for this area. "
                   "Clipping will be performed near the "
                   "closest indicated area "
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
                   "Prima disegna un'area sulla mappa "
                   "(pulsante 'Disegna area').",
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

        cloud_max = (self.sb_cloud.value()
                     if self.chk_cloud.isChecked() else None)
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
        self.lbl_search_status.setText(
            _t(L, "Ricerca in corso...", "Searching..."))
        self.lbl_status.setText(
            _t(L, "Ricerca STAC avviata.", "STAC search started."))

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
        self.lbl_status.setText(
            _t(L, "Ricerca completata.", "Search complete."))
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

    def _show_item_details(self, item):
        dlg = _ItemDetailsDialog(item, lang=self.lang, parent=self)
        dlg.exec()

    def _show_spectral_compare(self, item):
        cat = next(
            (c for c in STAC_CATALOGS
             if c.get("url") == item.get("catalog_url")),
            {},
        )
        dlg = _SpectralCompareDialog(
            item, lang=self.lang, auth=self._cred_for(cat), parent=self
        )
        dlg.exec()

    def _rerender_results(self):
        self._clear_result_cards()
        for cat in STAC_CATALOGS:
            cid = cat["id"]
            if cid in self._results:
                self._add_catalog_section(
                    cat,
                    self._results[cid],
                    self._errors.get(cid, ""),
                )
        self._update_summary()

    def _result_column_count(self):
        width = self.width()
        if hasattr(self, "scroll_area") and self.scroll_area.viewport():
            width = self.scroll_area.viewport().width()
        # 240 px card + spacing/margins. Limit to four columns to keep
        # previews readable on wide screens.
        return max(1, min(4, int(max(240, width - 20) / 258)))

    def _group_items_by_data_type(self, items):
        groups = {}
        for item in items:
            key = item.get("data_type") or "other"
            groups.setdefault(key, []).append(item)
        ordered = []
        for key in _DATA_TYPE_ORDER:
            if key in groups:
                ordered.append((key, groups.pop(key)))
        for key in sorted(groups):
            ordered.append((key, groups[key]))
        for _key, group_items in ordered:
            group_items.sort(key=lambda i: _item_date(i), reverse=True)
        return ordered

    def _make_timeline_widget(self, items):
        wrapper = QFrame()
        wrapper.setStyleSheet(
            "QFrame { background:#1b2430; border:1px solid #2c3a48;"
            "border-radius:8px; } QLabel { background:transparent; }"
        )
        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        lbl = QLabel(_t(
            self.lang, "Timeline acquisizioni", "Acquisition timeline"
        ))
        lbl.setStyleSheet("color:#5b9bd5; font-size:12px; font-weight:700;")
        outer.addWidget(lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCompat.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCompat.ScrollBarAlwaysOff)
        scroll.setMaximumHeight(76)
        scroll.setStyleSheet("QScrollArea { border:none; }")

        content = QWidget()
        row = QHBoxLayout(content)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        for item in sorted(items, key=lambda i: _item_date(i)):
            dtype = item.get("data_type") or "other"
            date_txt = _item_date(item) or "n/d"
            btn = QPushButton(
                "%s\n%s %s" % (
                    date_txt,
                    _data_type_icon(dtype),
                    _data_type_label(self.lang, dtype),
                )
            )
            btn.setFixedSize(132, 48)
            btn.setToolTip(_item_title(item, 120))
            btn.setStyleSheet(
                "QPushButton { background:#141a22; border:1px solid #2c3a48;"
                "border-radius:8px; padding:4px; color:#c3ccd6;"
                "font-size:10px; text-align:center; }"
                "QPushButton:hover { border-color:#5b9bd5; color:#f2f5f8; }"
            )
            btn.clicked.connect(
                lambda _checked, i=item: self._show_item_details(i)
            )
            row.addWidget(btn)
        row.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return wrapper

    def _make_data_group_widget(self, cat, type_key, items):
        group_widget = QWidget()
        group_layout = QVBoxLayout(group_widget)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(6)

        spectral_count = len([i for i in items if i.get("spectral_indices")])
        hdr = QLabel(
            '<span style="color:#5b9bd5; font-weight:700;">%s %s</span>'
            ' <span style="color:#c3ccd6;">· %s</span>'
            ' <span style="color:#8a97a5;">%s</span>' % (
                _data_type_icon(type_key),
                _html_escape(_data_type_label(self.lang, type_key)),
                len(items),
                _html_escape(_t(
                    self.lang,
                    f"{spectral_count} con indici COG",
                    f"{spectral_count} with COG indices",
                )),
            )
        )
        hdr.setStyleSheet("font-size:12px; padding:6px 2px 2px 2px;")
        group_layout.addWidget(hdr)

        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(8)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        col_count = self._result_column_count()
        self._last_result_col_count = col_count
        cat_auth = self._cred_for(cat)
        for idx, item in enumerate(items):
            card = ItemCard(
                item, lang=self.lang,
                preview_cache=self._preview_cache,
                catalog=cat, auth=cat_auth, controller=self,
                details_callback=self._show_item_details,
                spectral_callback=self._show_spectral_compare,
                parent=grid_widget,
            )
            grid_layout.addWidget(card, idx // col_count, idx % col_count)

        group_layout.addWidget(grid_widget)
        return group_widget

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
                f' &nbsp;<span style="color:#8a97a5; font-size:11px;">'
                f'{_t(self.lang, "Non disponibile", "Not available")}</span>'
            )
        else:
            header_lbl.setText(
                f'<b style="color:#5b9bd5;">🛰️ {cat_name}</b>'
                f' &nbsp;<span style="color:#8a97a5;">·</span>&nbsp;'
                f'<span style="color:#c3ccd6;">'
                f'{n} {_t(self.lang, "risultati", "results")}</span>'
                f'&nbsp;&nbsp;<a href="{cat_url}" '
                f'style="color:#3b82f6; font-size:11px;">↗ '
                f'{_t(self.lang, "apri catalogo", "open catalog")}</a>'
            )
            header_lbl.setOpenExternalLinks(True)
        header_lbl.setStyleSheet("font-size:13px; padding:4px 0;")
        section_layout.addWidget(header_lbl)

        # Auth notice: free registration required + link to official portal.
        if cat.get("auth") and items:
            has_creds = bool(
                self._cred_for(cat).get("token") or (
                    self._cred_for(cat).get("username") and
                    self._cred_for(cat).get("password")
                )
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
                "background:rgba(239,68,68,0.08);"
                "border:1px solid rgba(239,68,68,0.2);"
                "border-radius:6px; padding:8px; font-size:11px;"
            )
            section_layout.addWidget(err_lbl)
        elif items:
            section_layout.addWidget(self._make_timeline_widget(items))
            for type_key, group_items in self._group_items_by_data_type(items):
                section_layout.addWidget(
                    self._make_data_group_widget(cat, type_key, group_items)
                )
        else:
            lbl_empty = QLabel(
                _t(self.lang, "Nessun risultato in questo catalogo.",
                   "No results in this catalog.")
            )
            lbl_empty.setStyleSheet(
                "color:#8a97a5; font-size:11px; padding:4px;")
            section_layout.addWidget(lbl_empty)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#2c3a48;")
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
        self.lbl_status.setText(
            _t(L, "Risultati cancellati.", "Results cleared."))
