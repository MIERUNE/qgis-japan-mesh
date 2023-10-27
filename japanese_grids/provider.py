"""Processing provider for this plugin"""

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

from pathlib import Path

from PyQt5.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .algorithms.create_grid_square import CreateGridSquareAlgorithm
from .algorithms.create_legacy_grid import CreateLegacyGridAlgorithm
from .algorithms.load_estat_csv import LoadEstatGridSquareStats


class JapanMeshProcessingProvider(QgsProcessingProvider):
    def loadAlgorithms(self, *args, **kwargs):
        self.addAlgorithm(CreateGridSquareAlgorithm())
        self.addAlgorithm(CreateLegacyGridAlgorithm())
        self.addAlgorithm(LoadEstatGridSquareStats())

    def id(self, *args, **kwargs):
        return "japanesegrid"

    def name(self, *args, **kwargs):
        return self.tr("地域メッシュ")

    def icon(self):
        path = (Path(__file__).parent / "icon.png").resolve()
        return QIcon(str(path))
