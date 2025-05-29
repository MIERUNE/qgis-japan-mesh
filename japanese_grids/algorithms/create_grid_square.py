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

from typing import Any

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
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterEnum,
    QgsProcessingParameterExtent,
    QgsProcessingParameterFeatureSink,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsVectorLayerSimpleLabeling,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QCoreApplication, QVariant

from .utils.grid_square import estimate_total_count, iter_patch

_DESCRIPTION = """日本の「地域メッシュ」 (JIS X 0410) をベクタレイヤとして作成します。

作成したい種類のメッシュの出力先を「一時レイヤ」や「ファイル」に設定して、アルゴリズムを実行してください。

デフォルトでは日本全域のメッシュを作成しますが、「メッシュの作成範囲」オプションでメッシュの作成範囲を制限できます。

1/2地域メッシュ以下のサイズのメッシュについては、大量の地物生成を防ぐため、生成範囲を制限しないとアルゴリズムを実行できません。

各メッシュの大きさとコードの桁数（参考）：

- 第1次地域区画: 約80km四方、4桁
- 第2次地域区画: 約10km四方、6桁
- 基準地域メッシュ（第3次地域区画）: 約1km四方、8桁

分割地域メッシュ：
- 2分の1地域メッシュ: 約500m四方、9桁
- 4分の1地域メッシュ: 約250m四方、10桁
- 8分の1地域メッシュ: 約125m四方、11桁

統合地域メッシュ：
- 5倍地域メッシュ: 約5km四方、7桁
- 2倍地域メッシュ: 約2km四方、9桁
"""


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
        "label": _tr("基準地域メッシュ（第3次地域区画）"),
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
    "quintuple": {
        "param": "OUTPUT_QUINTUPLE",
        "default": False,
        "label": _tr("5倍地域メッシュ"),
        "max_scale": 10000,
        "min_scale": 400000,
    },
    "double": {
        "param": "OUTPUT_DOUBLE",
        "default": False,
        "label": _tr("2倍地域メッシュ"),
        "max_scale": 4000,
        "min_scale": 120000,
    },
    "m100": {
        "param": "OUTPUT_100M",
        "default": False,
        "label": _tr("100mメッシュ"),
        "max_scale": 250,
        "min_scale": 10000,
    },
}

_CRS_SELECTION = [
    {"label": "日本測地系2011 (JGD2011, EPSG:6668)", "epsg": 6668},
    {"label": "日本測地系2000 (JGD2000, EPSG:4612)", "epsg": 4612},
    {"label": "世界測地系1984 (WGS 84, EPSG:4326)", "epsg": 4326},
    {"label": "旧日本測地系 (Tokyo Datum, EPSG:4301)", "epsg": 4301},
]


class CreateGridSquareAlgorithm(QgsProcessingAlgorithm):
    """Create vector layers representing the "Grid Square Code" used in Japan."""

    EXTENT = "EXTENT"
    GEOGRAPHIC_CRS = "GEOGRAPHIC_CRS"

    def __init__(self) -> None:
        super().__init__()
        self.post_processors = {key: LayerStyler(key) for key in _LAYERS}

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
                options=[v["label"] for v in _CRS_SELECTION],
                defaultValue=1,
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
        return "creategridsquare"

    def group(self):
        return None

    def groupId(self):
        return None

    def displayName(self):
        return _tr("地域メッシュを作成")

    def shortHelpString(self) -> str:
        return _tr(_DESCRIPTION)

    def processAlgorithm(
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
        if not extent.isEmpty():
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

                if (
                    layer_kind_name in ["quarter", "eighth", "100m"]
                    and extent_bbox is None
                ):
                    raise QgsProcessingException(
                        "1/2メッシュよりも細かいメッシュを出力する場合は、思わぬ大量の地物生成を防ぐため、メッシュの作成範囲を指定する必要があります。"
                    )

                # Set post-processor
                if context.willLoadLayerOnCompletion(dest_id):
                    comp = context.layerToLoadOnCompletionDetails(dest_id)
                    comp.setPostProcessor(self.post_processors[layer_kind_name])

        if not sinks:
            raise QgsProcessingException(
                "地域メッシュの出力先が1つも選択されていません。\n利用したい地域メッシュの出力先を一時ファイルやファイルに切り替えて実行してください。"
            )

        # Generate square patches
        total_count = estimate_total_count(
            extent=extent_bbox,
            primary="primary" in sinks,
            secondary="secondary" in sinks,
            standard="standard" in sinks,
            half="half" in sinks,
            quarter="quarter" in sinks,
            eighth="eighth" in sinks,
            m100="m100" in sinks,
            double="double" in sinks,
            quintuple="quintuple" in sinks,
        )
        for count, (kind, code, bbox) in enumerate(
            iter_patch(
                extent=extent_bbox,
                primary="primary" in sinks,
                secondary="secondary" in sinks,
                standard="standard" in sinks,
                half="half" in sinks,
                quarter="quarter" in sinks,
                eighth="eighth" in sinks,
                m100="m100" in sinks,
                double="double" in sinks,
                quintuple="quintuple" in sinks,
            )
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

        feedback.setProgress(100)

        return result


class LayerStyler(QgsProcessingLayerPostProcessorInterface):
    def __init__(self, kind: str):
        self._kind = kind
        super().__init__()

    def postProcessLayer(self, layer, context, feedback):
        if not layer.isValid():
            return

        layer_kind = _LAYERS[self._kind]
        settings = QgsPalLayerSettings()
        settings.fieldName = "code"
        settings.placement = Qgis.LabelPlacement.OverPoint  # type: ignore
        settings.centroidInside = False
        settings.centroidWhole = True
        settings.scaleVisibility = True
        format = QgsTextFormat()
        buffer = QgsTextBufferSettings()
        buffer.setEnabled(True)
        buffer.setSize(1)
        buffer.setOpacity(0.75)
        format.setBuffer(buffer)
        settings.setFormat(format)
        settings.maximumScale = layer_kind["max_scale"]
        settings.minimumScale = layer_kind["min_scale"]
        labeling = QgsVectorLayerSimpleLabeling(settings)
        layer.setOpacity(0.5)
        layer.setLabeling(labeling)
        layer.setLabelsEnabled(True)
