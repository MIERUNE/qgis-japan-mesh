"""Processing algorithm to create the "Grid Square Code" of Japan (JIS X 0410) as vector layers"""

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

from typing import Any, TextIO

from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsLineString,
    QgsPolygon,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,  # pyright: ignore
    QgsProcessingFeedback,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFile,
    QgsWkbTypes,
)

from .utils.gridsquare_to_box import grid_square_code_to_bbox

_DESCRIPTION = """国勢調査や経済センサスなどの、日本の政府統計の綜合窓口 e-Stat (https://www.e-stat.go.jp/gis) で公開されている地域メッシュ統計のCSVファイルを読み込んで、ベクトルレイヤーとして出力します。"""

_CRS_SELECTION = [
    {"label": "日本測地系2011 (JGD2011)", "epsg": 6668},
    {"label": "日本測地系2000 (JGD2000)", "epsg": 4612},
    {"label": "世界測地系1984 (WGS 84)", "epsg": 4326},
    {"label": "日本測地系 (Tokyo Datum)", "epsg": 4301},
]


def _tr(string: str):
    return QCoreApplication.translate("Processing", string)


def _load_header(f):
    header = [s.strip() for s in f.readline().split(",")]
    alias_header = [s.strip() for s in f.readline().split(",")]
    print(header)
    print(alias_header)
    assert len(header) == len(alias_header)
    return header, alias_header


def _iter_rows(f: TextIO):
    for line in f:
        row = [v.strip() if v != "" else None for v in line.replace(" ", "").split(",")]
        yield row


class LoadEstatGridSquareStats(QgsProcessingAlgorithm):
    """Load Grid Square Statistics CSV files provided by e-stat.go.jp"""

    INPUT = "INPUT"
    GEOGRAPHIC_CRS = "GEOGRAPHIC_CRS"
    LABEL = "LABEL"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT,
                _tr("地域メッシュ統計CSVファイル"),
                fileFilter=_tr("メッシュ統計 (*.txt *.csv)"),
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.GEOGRAPHIC_CRS,
                _tr("地理座標系"),
                options=[v["label"] for v in _CRS_SELECTION],
                defaultValue=1,
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.LABEL,
                _tr("カラムに日本語ラベルを付与"),
                defaultValue=True,
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                _tr("メッシュ統計出力"),
                QgsProcessing.TypeVectorPolygon,
                supportsAppend=True,
            )
        )

    def createInstance(self):
        return LoadEstatGridSquareStats()

    def name(self):
        return "loadestatgridstats"

    def group(self):
        return None

    def groupId(self):
        return None

    def displayName(self):
        return _tr("地域メッシュ統計データを読み込む")

    def shortHelpString(self) -> str:
        return _tr(_DESCRIPTION)

    def _open_file(self, filename: str) -> TextIO:
        return open(filename, encoding="cp932")  # noqa: SIM115

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ):
        # Geographic CRS to assign
        crs_no = self.parameterAsEnum(
            parameters,
            self.GEOGRAPHIC_CRS,
            context,
        )
        crs_to_assign = QgsCoordinateReferenceSystem.fromEpsgId(
            _CRS_SELECTION[crs_no]["epsg"]
        )

        # Input CSV file
        filename = self.parameterAsFile(parameters, self.INPUT, context)
        if filename is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.INPUT)
            )  # pragma: no cover

        result = {}

        # Load data
        label = self.parameterAsBool(parameters, self.LABEL, context)
        fields = QgsFields()
        with open(filename, encoding="cp932") as f:
            columns, aliases = _load_header(f)
            # Make fields
            for idx, column in enumerate(columns):
                if label and aliases[idx] != "":
                    name = f"{column}_{aliases[idx]}"
                else:
                    name = column
                if columns[idx] in ("KEY_CODE", "HTKSAKI", "GASSAN"):
                    field = QgsField(name, type=QVariant.String)
                else:
                    field = QgsField(name, type=QVariant.Int)
                fields.append(field)

            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT,
                context,
                fields,
                QgsWkbTypes.Polygon,
                crs_to_assign,
            )
            result[self.OUTPUT] = dest_id

            # Load rows
            str_fields = [
                idx
                for idx in range(len(columns))
                if columns[idx] in ("KEY_CODE", "HTKSAKI", "GASSAN")
            ]
            num_columns = len(columns)
            key_code_idx = columns.index("KEY_CODE")
            for row in _iter_rows(f):
                feat = QgsFeature()
                feat.setFields(fields, initAttributes=True)
                assert len(row) == num_columns
                for idx, s in enumerate(row):
                    if s is None or s == "*":
                        continue
                    if idx in str_fields:
                        feat.setAttribute(idx, s)
                    else:
                        feat.setAttribute(idx, int(s))
                    if idx == key_code_idx and (bbox := grid_square_code_to_bbox(s)):
                        lng0, lat0, lng1, lat1 = bbox
                        exterior = (
                            (lng0, lat0),
                            (lng0, lat1),
                            (lng1, lat1),
                            (lng1, lat0),
                            (lng0, lat0),
                        )
                        geom = QgsPolygon(QgsLineString(exterior))
                        feat.setGeometry(geom)

                sink.addFeature(feat, QgsFeatureSink.FastInsert)

        return {}
