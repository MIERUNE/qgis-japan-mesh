"""Coordinate Panel"""

# Copyright (C) 2023 MIERUNE Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import re
from typing import Callable

from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
from qgis.gui import QgisInterface, QgsMapMouseEvent, QgsMapTool
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from japanese_grids.algorithms.utils.gridsquare_to_box import lnglat_to_grid_square_code


class MapMouseMoveTool(QgsMapTool):
    def __init__(self, canvas, callback: Callable[[float, float], None]):
        super().__init__(canvas)
        self._canvas = canvas
        self._callback = callback
        self._pressed = False

    def canvasPressEvent(self, event: QgsMapMouseEvent):
        self._pressed = True

    def canvasReleaseEvent(self, event: QgsMapMouseEvent):
        self._pressed = False

    def canvasMoveEvent(self, event: QgsMapMouseEvent):
        if not self._pressed:
            point = self.toMapCoordinates(event.pos())
            self._callback(point.x(), point.y())


class CoordinatePanel:
    def __init__(self, iface: QgisInterface):
        self._iface = iface
        self._setup()
        self._current_coord = None

    def _handle_mousemove(self, x: float, y: float):
        canvas = self._iface.mapCanvas()
        source_crs = canvas.mapSettings().destinationCrs()
        dest_crs = QgsCoordinateReferenceSystem(4326)  # WGS 84
        transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
        geog_point = transform.transform(x, y)
        self._current_coord = geog_point

        (geog_lng, geog_lat) = (self._current_coord.x(), self._current_coord.y())
        self._coordinate_label.setText(f"緯度: {geog_lat:.5f}°, 経度: {geog_lng:.5f}°")
        if code := lnglat_to_grid_square_code(geog_lng, geog_lat):
            if m := re.match(r"(\d{4})(\d{4})(\d)(\d)(\d)", code["eighth"]):
                self._line_edit.setText(
                    f"{m.group(1)}-{m.group(2)}-{m.group(3)}-{m.group(4)}-{m.group(5)}"
                )
        else:
            self._line_edit.setText("-")

    def _setup(self):
        self._dock_widget = QDockWidget("地域メッシュコード", self._iface.mainWindow())

        self._coordinate_label = QLabel("緯度: -.-°, 経度: -.-°")
        layout = QVBoxLayout()
        layout.addWidget(self._coordinate_label)

        self._line_edit = QLineEdit()

        self._line_edit.focusInEvent = lambda a0: QTimer.singleShot(
            1, self._line_edit.selectAll
        )

        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("コード:"))
        h_layout.addWidget(self._line_edit)
        layout.addLayout(h_layout)

        container = QWidget()
        container.setLayout(layout)
        container.setMaximumHeight(layout.totalSizeHint().height())
        self._dock_widget.setWidget(container)

        self._iface.addDockWidget(Qt.RightDockWidgetArea, self._dock_widget)

        canvas = self._iface.mapCanvas()
        self._maptool = MapMouseMoveTool(
            self._iface.mapCanvas(), self._handle_mousemove
        )
        canvas.setMapTool(self._maptool)

    def teardown(self):
        self._iface.removeDockWidget(self._dock_widget)
        del self._dock_widget
        del self._maptool
