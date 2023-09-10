"""Processing algorithm for generating Japan's Mesh"""

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

from typing import Any, Optional, cast

from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsLineString,
    QgsPalLayerSettings,
    QgsPolygon,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,  # pyright: ignore
    QgsProcessingFeedback,
    QgsProcessingParameterEnum,
    QgsProcessingParameterExtent,
    QgsProcessingParameterFeatureSink,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
    QgsWkbTypes,
)

from .utils.generator import estimate_total_count, iter_patch

_DESCRIPTION = """日本の「地域メッシュ」 (JIS X 0410) をベクタレイヤとして作成します。

作成したい種類のメッシュの出力先を「一時レイヤ」や「ファイル」に設定して、アルゴリズムを実行してください。

デフォルトでは日本全域のメッシュを作成しますが、「メッシュの作成範囲」オプションで作成する範囲を制限できます。

なお、1/2地域メッシュより小さいメッシュについては、大量の地物生成を防ぐため、生成範囲を制限しないとアルゴリズムを実行できません。
"""  # noqa: RUF001


def _tr(string: str):
    return QCoreApplication.translate("Processing", string)


_LAYERS = {
    "primary": {
        "param": "OUTPUT_PRIMARY",
        "default": False,
        "label": _tr("第1次地域区画"),
        "max_scale": 200000,
        "min_scale": 12500000,
    },
    "secondary": {
        "param": "OUTPUT_SECONDARY",
        "default": False,
        "label": _tr("第2次地域区画"),
        "max_scale": 20000,
        "min_scale": 1100000,
    },
    "standard": {
        "param": "OUTPUT_STANDARD",
        "default": False,
        "label": _tr("基準地域メッシュ（第3次地域区画）"),  # noqa: RUF001
        "max_scale": 2000,
        "min_scale": 80000,
    },
    "half": {
        "param": "OUTPUT_HALF",
        "default": False,
        "label": _tr("2分の1地域メッシュ"),
        "max_scale": 1000,
        "min_scale": 40000,
    },
    "quarter": {
        "param": "OUTPUT_QUARTER",
        "default": False,
        "label": _tr("4分の1地域メッシュ"),
        "max_scale": 500,
        "min_scale": 20000,
    },
    "eighth": {
        "param": "OUTPUT_EIGHTH",
        "default": False,
        "label": _tr("8分の1地域メッシュ"),
        "max_scale": 250,
        "min_scale": 10000,
    },
}

_CRS_SELECTION = {
    0: {"label": "日本測地系2011 (JGD2011)", "epsg": 6668},
    1: {"label": "日本測地系2000 (JGD2000)", "epsg": 4612},
    2: {"label": "世界測地系1984 (WGS 84)", "epsg": 4326},
    3: {"label": "日本測地系 (Tokyo Datum)", "epsg": 4301},
}


class CreateGridSquareAlgorithm(QgsProcessingAlgorithm):
    """Create vector layers representing the "Grid Square Code" used in Japan."""

    EXTENT = "EXTENT"
    GEOGRAPHIC_CRS = "GEOGRAPHIC_CRS"

    def initAlgorithm(self, config=None):
        for layer_kind in _LAYERS.values():
            self.addParameter(
                QgsProcessingParameterFeatureSink(
                    layer_kind["param"],
                    layer_kind["label"],
                    QgsProcessing.TypeVectorPolygon,
                    optional=True,
                    createByDefault=layer_kind["default"],
                )
            )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.GEOGRAPHIC_CRS,
                _tr("地理座標系"),
                options=[v["label"] for v in _CRS_SELECTION.values()],
                defaultValue=0,
            )
        )

        self.addParameter(
            QgsProcessingParameterExtent(
                self.EXTENT,
                "メッシュの作成範囲",
                optional=True,
            )
        )

    def createInstance(self):
        return CreateGridSquareAlgorithm()

    def name(self):
        return "create_grid_square"

    def group(self):
        return None

    def groupId(self):
        return None

    def displayName(self):
        return _tr("地域メッシュを作成")

    def shortHelpString(self) -> str:
        return _tr(_DESCRIPTION)

    def processAlgorithm(  # noqa: C901
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ):
        fields = QgsFields()
        fields.append(QgsField("code", type=QVariant.String))

        sinks = {}
        result = {}
        dest_ids = {}

        # Geographic CRS to assign
        crs_no = self.parameterAsEnum(
            parameters,
            self.GEOGRAPHIC_CRS,
            context,
        )
        crs_to_assign = QgsCoordinateReferenceSystem.fromEpsgId(
            _CRS_SELECTION[crs_no]["epsg"]
        )

        # Extent
        extent = self.parameterAsExtent(parameters, self.EXTENT, context, crs_to_assign)
        if not extent.isNull():
            extent_bbox = (
                extent.xMinimum(),
                extent.yMinimum(),
                extent.xMaximum(),
                extent.yMaximum(),
            )
        else:
            extent_bbox = None

        # Prepare destination layers
        for layer_kind_name, layer_kind in _LAYERS.items():
            (sink, dest_id) = self.parameterAsSink(
                parameters,
                layer_kind["param"],
                context,
                fields,
                QgsWkbTypes.Polygon,
                crs_to_assign,
            )
            if sink:
                sinks[layer_kind_name] = sink
                dest_ids[layer_kind_name] = dest_id
                result[layer_kind["param"]] = dest_id

                if layer_kind_name in ["quarter", "eighth"] and extent_bbox is None:
                    raise QgsProcessingException(
                        "1/4メッシュ、1/8メッシュを出力する場合は、思わぬ大量の地物生成を防ぐため、メッシュの作成範囲を指定する必要があります。"
                    )

        if not sinks:
            raise QgsProcessingException(
                "地域メッシュの出力先が1つも選択されていません。\n利用したい地域メッシュの出力先を一時ファイルやファイルに切り替えて実行してください。"
            )

        # Generate square patches
        count = 0
        total_count = estimate_total_count(
            extent=extent_bbox,
            primary="primary" in sinks,
            secondary="secondary" in sinks,
            standard="standard" in sinks,
            half="half" in sinks,
            quarter="quarter" in sinks,
            eighth="eighth" in sinks,
        )
        for kind, code, bbox in iter_patch(
            extent=extent_bbox,
            primary="primary" in sinks,
            secondary="secondary" in sinks,
            standard="standard" in sinks,
            half="half" in sinks,
            quarter="quarter" in sinks,
            eighth="eighth" in sinks,
        ):
            if feedback.isCanceled():
                return {}

            if count % 1000 == 0:
                feedback.setProgress(count / total_count * 100)

            lng0, lat0, lng1, lat1 = bbox
            exterior = (
                (lng0, lat0),
                (lng0, lat1),
                (lng1, lat1),
                (lng1, lat0),
                (lng0, lat0),
            )
            geom = QgsPolygon(QgsLineString(exterior))
            feat = QgsFeature()
            feat.setGeometry(geom)
            feat.setFields(fields, initAttributes=True)
            feat.setAttribute("code", code)

            sink = sinks[kind]
            sink.addFeature(feat, QgsFeatureSink.FastInsert)
            count += 1

        feedback.setProgress(100)

        # Label settings
        for kind, dest_id in dest_ids.items():
            layer = cast(
                Optional[QgsVectorLayer],
                context.temporaryLayerStore().mapLayer(dest_id),
            )
            if layer is None:
                continue
            layer_kind = _LAYERS[kind]
            settings = QgsPalLayerSettings()
            settings.fieldName = "code"
            settings.placement = Qgis.LabelPlacement.OverPoint  # type: ignore
            settings.centroidInside = False
            settings.centroidWhole = True
            settings.scaleVisibility = True
            settings.maximumScale = layer_kind["max_scale"]
            settings.minimumScale = layer_kind["min_scale"]
            labeling = QgsVectorLayerSimpleLabeling(settings)
            layer.setOpacity(0.5)
            layer.setLabeling(labeling)
            layer.setLabelsEnabled(True)

        return result
