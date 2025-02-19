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
    QgsGeometry,
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

_DESCRIPTION = """日本の政府統計の総合窓口 e-Stat (https://www.e-stat.go.jp/gis) で公開されている、国勢調査や経済センサスなどの地域メッシュ統計のCSVファイルを読み込んで、ベクタレイヤとして出力します。"""

_CRS_SELECTION = [
    {"label": "日本測地系2011 (JGD2011, EPSG:6668)", "epsg": 6668},
    {"label": "日本測地系2000 (JGD2000, EPSG:4612)", "epsg": 4612},
    {"label": "世界測地系1984 (WGS 84, EPSG:4326)", "epsg": 4326},
    {"label": "旧日本測地系 (Tokyo Datum, EPSG:4301)", "epsg": 4301},
]


def _tr(string: str):
    return QCoreApplication.translate("Processing", string)


def _load_header(f):
    header = [s.strip() for s in f.readline().split(",")]
    alias_header = [s.strip() for s in f.readline().split(",")]
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
    HTKSYORI = "HTKSYORI"
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
                _tr("カラム名に日本語を付与"),
                defaultValue=True,
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HTKSYORI,
                _tr("秘匿対象地域を併合する"),
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
        return _tr("地域メッシュ統計を読み込む")

    def shortHelpString(self) -> str:
        return _tr(_DESCRIPTION)

    def _open_file(self, filename: str) -> TextIO:
        return open(filename, encoding="cp932")  # noqa: SIM115

    def _bbox_to_polygon(self, bbox: tuple[float, float, float, float]) -> QgsPolygon:
        lng0, lat0, lng1, lat1 = bbox
        exterior = (
            (lng0, lat0),
            (lng0, lat1),
            (lng1, lat1),
            (lng1, lat0),
            (lng0, lat0),
        )
        return QgsPolygon(QgsLineString(exterior))

    def processAlgorithm(  # noqa: C901
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

        merge_hitoku = self.parameterAsBool(parameters, self.HTKSYORI, context)

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
        patches = {}

        # TODO: refactor

        num_gassan_idx = None
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

            if "GASSAN" in columns:
                fields.append(QgsField("NUM_GASSAN", type=QVariant.Int))
                num_gassan_idx = len(fields) - 1

            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT,
                context,
                fields,
                QgsWkbTypes.MultiPolygon,
                crs_to_assign,
            )
            result[self.OUTPUT] = dest_id

            # Load rows
            str_field_indexes = [
                idx
                for idx in range(len(columns))
                if columns[idx] in ("KEY_CODE", "HTKSAKI", "GASSAN")
            ]

            num_columns = len(columns)
            key_code_column_idx = columns.index("KEY_CODE")
            try:
                gassan_column_idx = columns.index("GASSAN")
                htksyori_column_idx = columns.index("HTKSYORI")
                htksaki_column_idx = columns.index("HTKSAKI")
            except ValueError:
                gassan_column_idx = None
                htksyori_column_idx = None
                htksaki_column_idx = None

            # Scan all source entries
            for row in _iter_rows(f):
                assert len(row) == num_columns
                key_code = None
                patch_attrs: list = [None] * num_columns
                for idx, s in enumerate(row):
                    if s is None or s == "*":
                        patch_attrs[idx] = None
                    else:
                        patch_attrs[idx] = s if idx in str_field_indexes else int(s)

                    if idx == key_code_column_idx:
                        key_code = s

                assert key_code is not None
                patches[key_code] = patch_attrs

        value_column_indexes = set(range(num_columns)) - {
            key_code_column_idx,
            gassan_column_idx,
            htksyori_column_idx,
            htksaki_column_idx,
        }

        # Generate QGIS features
        for patch_attrs in patches.values():
            # GASSAN (HTKSYORI)
            if merge_hitoku and (
                htksyori_column_idx is not None and gassan_column_idx is not None
            ):
                if patch_attrs[htksyori_column_idx] == 2:
                    continue

                if gassan := patch_attrs[gassan_column_idx]:
                    for gassan_area_code in gassan.split(";"):
                        merging_patch = patches[gassan_area_code]
                        for idx in value_column_indexes:
                            if (v := merging_patch[idx]) is not None:
                                patch_attrs[idx] += v

            geoms = []
            feat = QgsFeature()
            feat.setFields(fields, initAttributes=True)

            for idx, s in enumerate(patch_attrs):
                if s is None:
                    continue

                feat.setAttribute(
                    idx,
                    s if idx in str_field_indexes else int(s),
                )

                # Geometry
                if idx == key_code_column_idx:
                    if bbox := grid_square_code_to_bbox(s):
                        geoms.append(self._bbox_to_polygon(bbox))
                elif merge_hitoku and idx == gassan_column_idx:
                    bboxes = [grid_square_code_to_bbox(s) for s in s.split(";")]
                    geoms.extend(
                        self._bbox_to_polygon(bbox)
                        for bbox in bboxes
                        if bbox is not None
                    )

            # パッチのジオメトリを作成
            if len(geoms) == 1:
                feat.setGeometry(geoms[0])
            elif len(geoms) > 1:
                # 合算されている場合はジオメトリを合成
                feat.setGeometry(QgsGeometry.unaryUnion(QgsGeometry(p) for p in geoms))

            if merge_hitoku and num_gassan_idx is not None:
                feat.setAttribute(num_gassan_idx, len(geoms))

            sink.addFeature(feat, QgsFeatureSink.FastInsert)

        return {}
