"""Panel to show the grid square code of the current mouse position."""

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

from qgis._gui import QgsMapCanvas
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsProject,
)
from qgis.gui import QgisInterface
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


class CoordinatePanel:
    def __init__(self, iface: QgisInterface):
        self._iface = iface
        self._setup()
        self._current_coord = None
        self._dest_crs = QgsCoordinateReferenceSystem(6668)  # JGD 2011

    def _handle_mousemove(self, xy: QgsPointXY):
        canvas = self._iface.mapCanvas()
        source_crs = canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(
            source_crs, self._dest_crs, QgsProject.instance()
        )
        geog_point = transform.transform(xy)
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

        self._iface.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._dock_widget
        )

        canvas: QgsMapCanvas = self._iface.mapCanvas()
        canvas.xyCoordinates.connect(self._handle_mousemove)

    def teardown(self):
        self._iface.removeDockWidget(self._dock_widget)
        del self._dock_widget
