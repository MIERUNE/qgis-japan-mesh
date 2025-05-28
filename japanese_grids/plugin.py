"""Plugin class"""

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

import contextlib

from qgis.core import QgsApplication
from qgis.gui import QgisInterface
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolButton

from .panel import CoordinatePanel
from .provider import JapanMeshProcessingProvider

with contextlib.suppress(ImportError):
    from processing import execAlgorithmDialog


class JapanMeshPlugin:
    """Japanese Grid Square Mesh plugin"""

    def __init__(self, iface: QgisInterface):
        self.iface = iface

    def initGui(self):
        self.provider = JapanMeshProcessingProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

        if self.iface:
            self.setup_algorithms_tool_button()
            self._coord_panel = CoordinatePanel(self.iface)

    def unload(self):
        if self.iface:
            self.teardown_algorithms_tool_button()
            self._coord_panel.teardown()

        QgsApplication.processingRegistry().removeProvider(self.provider)

    def setup_algorithms_tool_button(self):
        """ツールバー上にアルゴリズムの呼び出しボタンを追加する"""

        # Add a button on the toolbar
        tool_button = QToolButton()
        icon = self.provider.icon()
        default_action = QAction(icon, "地域メッシュを作成", self.iface.mainWindow())
        default_action.triggered.connect(
            lambda: execAlgorithmDialog("japanesegrid:creategridsquare", {})
        )
        tool_button.setDefaultAction(default_action)

        # ToolButton Menu
        menu = QMenu()
        tool_button.setMenu(menu)
        tool_button.setPopupMode(QToolButton.MenuButtonPopup)

        action_grid_square = QAction(
            icon, "地域メッシュを作成", self.iface.mainWindow()
        )
        action_grid_square.triggered.connect(
            lambda: execAlgorithmDialog("japanesegrid:creategridsquare", {})
        )
        menu.addAction(action_grid_square)

        action_legacy = QAction(icon, "国土基本図郭を作成", self.iface.mainWindow())
        action_legacy.triggered.connect(
            lambda: execAlgorithmDialog("japanesegrid:createlegacygrid", {})
        )
        menu.addAction(action_legacy)

        action_estat = QAction(
            icon, "地域メッシュ統計を読み込む", self.iface.mainWindow()
        )
        action_estat.triggered.connect(
            lambda: execAlgorithmDialog("japanesegrid:loadestatgridstats", {})
        )
        menu.addAction(action_estat)

        self.toolButtonAction = self.iface.addToolBarWidget(tool_button)

    def teardown_algorithms_tool_button(self):
        """ツールバー上のアルゴリズムの呼び出しボタンを削除する"""

        self.iface.removeToolBarIcon(self.toolButtonAction)
