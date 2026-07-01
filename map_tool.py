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
map_tool.py — Geometry drawing tools for STAC Browser.

Three interactive map tools are provided, all of which finally emit
``bboxDrawn(west, south, east, north)`` in EPSG:4326 so the dialog can run a
single, uniform STAC search regardless of how the area was defined:

  * :class:`DrawBboxTool`  — click-drag rectangle.
  * :class:`DrawPointTool` — single click, buffered into a small bbox.
  * :class:`DrawLineTool`  — multi-vertex polyline, bbox of its envelope.
"""

from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.core import (
    QgsPointXY, QgsRectangle, QgsWkbTypes,
    QgsCoordinateTransform, QgsCoordinateReferenceSystem,
    QgsProject,
)
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QColor

from .qt_compat import ensure_qt_compat, QtCompat

ensure_qt_compat(Qt)

_CRS_4326 = QgsCoordinateReferenceSystem("EPSG:4326")

# Half-size (in degrees) of the bbox generated around a single clicked point
# (~2 km at the equator). A line whose envelope collapses on one axis is
# padded by the same amount so the resulting bbox is never degenerate.
POINT_BUFFER_DEG = 0.02
LINE_PAD_DEG = 0.005


def transform_point_to_4326(point):
    """Transform a single :class:`QgsPointXY` from the project CRS to 4326."""
    project_crs = QgsProject.instance().crs()
    if project_crs == _CRS_4326 or project_crs.authid() == "EPSG:4326":
        return point.x(), point.y()
    try:
        xform = QgsCoordinateTransform(
            project_crs, _CRS_4326,
            QgsProject.instance().transformContext(),
        )
    except TypeError:
        xform = QgsCoordinateTransform(
            project_crs, _CRS_4326, QgsProject.instance()
        )
    out = xform.transform(point)
    return out.x(), out.y()


def _bbox_from_4326_points(points, pad=0.0):
    """Return (w, s, e, n) enclosing a list of (lon, lat) tuples."""
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)
    if east - west < 1e-9:
        west -= pad or LINE_PAD_DEG
        east += pad or LINE_PAD_DEG
    if north - south < 1e-9:
        south -= pad or LINE_PAD_DEG
        north += pad or LINE_PAD_DEG
    return west, south, east, north


class DrawBboxTool(QgsMapTool):
    """Click-and-drag rectangle tool emitting ``bboxDrawn`` in EPSG:4326."""

    bboxDrawn = pyqtSignal(float, float, float, float)  # W, S, E, N (4326)

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self._start_point = None
        self._drawing = False

        self._rb = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self._rb.setColor(QColor(0, 229, 255, 50))
        self._rb.setWidth(2)
        try:
            self._rb.setFillColor(QColor(0, 229, 255, 30))
            self._rb.setStrokeColor(QColor(0, 229, 255, 200))
        except AttributeError:
            pass

    def canvasPressEvent(self, e):
        if e.button() == QtCompat.LeftButton:
            self._start_point = self.toMapCoordinates(e.pos())
            self._drawing = True
            self._rb.reset(QgsWkbTypes.PolygonGeometry)

    def canvasMoveEvent(self, e):
        if self._drawing and self._start_point is not None:
            current = self.toMapCoordinates(e.pos())
            self._update_rubber_band(self._start_point, current)

    def canvasReleaseEvent(self, e):
        if (
            e.button() == QtCompat.LeftButton
            and self._drawing
            and self._start_point is not None
        ):
            end_point = self.toMapCoordinates(e.pos())
            self._drawing = False
            self._rb.reset(QgsWkbTypes.PolygonGeometry)

            x1, y1 = self._start_point.x(), self._start_point.y()
            x2, y2 = end_point.x(), end_point.y()

            if abs(x2 - x1) < 1e-10 or abs(y2 - y1) < 1e-10:
                self._start_point = None
                return

            rect = QgsRectangle(
                min(x1, x2), min(y1, y2),
                max(x1, x2), max(y1, y2),
            )
            west, south, east, north = self._rect_to_4326(rect)
            self._start_point = None
            self.bboxDrawn.emit(west, south, east, north)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reset()

    def _update_rubber_band(self, p1, p2):
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()
        self._rb.reset(QgsWkbTypes.PolygonGeometry)
        points = [
            QgsPointXY(x1, y1),
            QgsPointXY(x2, y1),
            QgsPointXY(x2, y2),
            QgsPointXY(x1, y2),
            QgsPointXY(x1, y1),
        ]
        for pt in points:
            self._rb.addPoint(pt, True)
        self._rb.show()

    def _rect_to_4326(self, rect):
        ll = transform_point_to_4326(
            QgsPointXY(rect.xMinimum(), rect.yMinimum())
        )
        ur = transform_point_to_4326(
            QgsPointXY(rect.xMaximum(), rect.yMaximum())
        )
        west = min(ll[0], ur[0])
        south = min(ll[1], ur[1])
        east = max(ll[0], ur[0])
        north = max(ll[1], ur[1])
        return west, south, east, north

    def reset(self):
        self._start_point = None
        self._drawing = False
        self._rb.reset(QgsWkbTypes.PolygonGeometry)

    def deactivate(self):
        self.reset()
        super().deactivate()


class DrawPointTool(QgsMapTool):
    """Single-click tool; emits a small bbox buffered around the point."""

    bboxDrawn = pyqtSignal(float, float, float, float)

    def __init__(self, canvas, buffer_deg=POINT_BUFFER_DEG):
        super().__init__(canvas)
        self.canvas = canvas
        self.buffer_deg = buffer_deg

        self._rb = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self._rb.setColor(QColor(0, 229, 255, 200))
        self._rb.setWidth(3)
        try:
            self._rb.setIconSize(12)
        except AttributeError:
            pass

    def canvasReleaseEvent(self, e):
        if e.button() != QtCompat.LeftButton:
            return
        map_pt = self.toMapCoordinates(e.pos())
        self._rb.reset(QgsWkbTypes.PointGeometry)
        self._rb.addPoint(map_pt, True)
        self._rb.show()

        lon, lat = transform_point_to_4326(map_pt)
        b = self.buffer_deg
        self.bboxDrawn.emit(lon - b, lat - b, lon + b, lat + b)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reset()

    def reset(self):
        self._rb.reset(QgsWkbTypes.PointGeometry)

    def deactivate(self):
        self.reset()
        super().deactivate()


class DrawLineTool(QgsMapTool):
    """
    Multi-vertex polyline tool.

    Left-click adds a vertex, the moving cursor previews the next segment,
    a right-click or a double-click finishes the line and emits the bbox of
    its envelope. Esc cancels.
    """

    bboxDrawn = pyqtSignal(float, float, float, float)

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self._points = []

        self._rb = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self._rb.setColor(QColor(0, 229, 255, 200))
        self._rb.setWidth(2)

    def canvasPressEvent(self, e):
        if e.button() == QtCompat.LeftButton:
            self._points.append(self.toMapCoordinates(e.pos()))
            self._redraw(None)
        elif e.button() == QtCompat.RightButton:
            self._finish()

    def canvasMoveEvent(self, e):
        if self._points:
            self._redraw(self.toMapCoordinates(e.pos()))

    def canvasDoubleClickEvent(self, e):
        self._finish()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reset()

    def _redraw(self, hover_pt):
        self._rb.reset(QgsWkbTypes.LineGeometry)
        for pt in self._points:
            self._rb.addPoint(pt, True)
        if hover_pt is not None:
            self._rb.addPoint(hover_pt, True)
        self._rb.show()

    def _finish(self):
        if len(self._points) < 2:
            self.reset()
            return
        coords = [transform_point_to_4326(p) for p in self._points]
        west, south, east, north = _bbox_from_4326_points(coords)
        self.reset()
        self.bboxDrawn.emit(west, south, east, north)

    def reset(self):
        self._points = []
        self._rb.reset(QgsWkbTypes.LineGeometry)

    def deactivate(self):
        self.reset()
        super().deactivate()
