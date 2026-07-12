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
plugin.py — Entry point for the STAC Browser QGIS plugin.
"""

import os

from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.core import Qgis

from .dialog import StacBrowserDialog
from .map_tool import DrawBboxTool, DrawPointTool, DrawLineTool


class StacBrowserPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.dialog = None
        self.map_tool = None

    # ------------------------------------------------------------------
    # initGui / unload
    # ------------------------------------------------------------------

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, "icon.svg")
        self.action = QAction(
            QIcon(icon_path),
            "STAC Browser",
            self.iface.mainWindow(),
        )
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&GeoFusion Tools", self.action)

    def unload(self):
        if self.action:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu("&GeoFusion Tools", self.action)
        if self.map_tool:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None
        if self.dialog:
            self.dialog.close()
            self.dialog = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _push(self, title, message, level_name="Info"):
        level = getattr(Qgis, level_name, None)
        if level is None:
            ml = getattr(Qgis, "MessageLevel", None)
            level = getattr(ml, level_name, 0) if ml else 0
        try:
            self.iface.messageBar().pushMessage(title, message, level)
        except TypeError:
            self.iface.messageBar().pushMessage(title, message, level=level)

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(self):
        """Open (or show) the STAC Browser dialog."""
        if self.dialog is None:
            self.dialog = StacBrowserDialog(self.iface.mainWindow())
            # Connect the draw request to activate the chosen map tool
            self.dialog.drawRequested.connect(self._activate_draw_tool)

        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    # ------------------------------------------------------------------
    # Map tool activation
    # ------------------------------------------------------------------

    _DRAW_HINTS = {
        "bbox": (
            "Clicca e trascina per disegnare un rettangolo. "
            "Esc per annullare. / "
            "Click and drag to draw a rectangle. Esc to cancel."
        ),
        "point": (
            "Clicca un punto sulla mappa. Esc per annullare. / "
            "Click a point on the map. Esc to cancel."
        ),
        "line": (
            "Clicca per aggiungere vertici, tasto destro o doppio "
            "click per chiudere. Esc per annullare. / "
            "Click to add vertices, right-click "
            "or double-click to finish. Esc to cancel."
        ),
    }

    def _activate_draw_tool(self, mode="bbox"):
        """Activate the requested drawing tool and hide the dialog."""
        if self.map_tool is not None:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None

        if mode == "point":
            self.map_tool = DrawPointTool(self.iface.mapCanvas())
        elif mode == "line":
            self.map_tool = DrawLineTool(self.iface.mapCanvas())
        else:
            self.map_tool = DrawBboxTool(self.iface.mapCanvas())
        self.map_tool.bboxDrawn.connect(self._on_bbox_drawn)

        # Hide dialog so the user can draw on the canvas
        if self.dialog:
            self.dialog.hide()

        self.iface.mapCanvas().setMapTool(self.map_tool)
        self._push("STAC Browser", self._DRAW_HINTS.get(mode, ""), "Info")

    # ------------------------------------------------------------------
    # Bbox drawn callback
    # ------------------------------------------------------------------

    def _on_bbox_drawn(self, west, south, east, north):
        """Called when the user finishes drawing a bbox on the map."""
        # Deactivate the map tool (restore previous tool)
        self.iface.mapCanvas().unsetMapTool(self.map_tool)

        if self.dialog is None:
            self.dialog = StacBrowserDialog(self.iface.mainWindow())
            self.dialog.drawRequested.connect(self._activate_draw_tool)

        self.dialog.set_bbox(west, south, east, north)
