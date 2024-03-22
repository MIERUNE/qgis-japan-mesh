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

from typing import Any, List, TypedDict

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
    QgsProcessingException,  # pyright: ignore  # pyright: ignore
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

from .utils.legacy_grid import estimate_total_count, iter_patch

_DESCRIPTION = """日本の「国土基本図図郭」をベクタレイヤとして作成します。

平面直角座標系の系番号を選択したうえで、作成したい地図情報レベルのレイヤの出力先を「一時レイヤ」や「ファイル」に設定して、アルゴリズムを実行してください。

必要に応じて、平面直角座標系の測地系（データム）を変更することができます。

各メッシュの大きさ（参考）：

- 地図情報レベル 50000: 30km × 40km
- 地図情報レベル 5000: 3km × 4km
- 地図情報レベル 2500: 1.5km × 2km
- 地図情報レベル 1000: 600m × 800m
- 地図情報レベル 500: 300m × 400m
"""


def _tr(string: str):
    return QCoreApplication.translate("Processing", string)


_LAYERS = {
    "lv50000": {
        "param": "OUTPUT_50000",
        "default": False,
        "label": _tr("地図情報レベル 50000"),
        "max_scale": 200000,
        "min_scale": 4200000,
    },
    "lv5000": {
        "param": "OUTPUT_5000",
        "default": False,
        "label": _tr("地図情報レベル 5000"),
        "max_scale": 20000,
        "min_scale": 300000,
    },
    "lv2500": {
        "param": "OUTPUT_2500",
        "default": False,
        "label": _tr("地図情報レベル 2500"),
        "max_scale": 2000,
        "min_scale": 150000,
    },
    "lv1000": {
        "param": "OUTPUT_1000",
        "default": False,
        "label": _tr("地図情報レベル 1000"),
        "max_scale": 1000,
        "min_scale": 50000,
    },
    "lv500": {
        "param": "OUTPUT_500",
        "default": False,
        "label": _tr("地図情報レベル 500"),
        "max_scale": 500,
        "min_scale": 25000,
    },
}

_DATUM_SELECTION = [
    {"label": "日本測地系2011 (JGD2011)", "datum": "jgd2011"},
    {"label": "日本測地系2000 (JGD2000)", "datum": "jgd2000"},
    {"label": "日本測地系 (Tokyo Datum)", "datum": "tokyo"},
]


class _PlaneRectPlaneDef(TypedDict):
    label: str
    prefix: str
    jgd2011: int
    jgd2000: int
    tokyo: int


_PLANE_RECTANGULAR_PLANES: List[_PlaneRectPlaneDef] = [
    {
        "label": "I (1) 系: 長崎, 鹿児島県の一部",
        "prefix": "01",
        "jgd2011": 6669,
        "jgd2000": 2443,
        "tokyo": 30161,
    },
    {
        "label": "II (2) 系: 福岡, 佐賀, 熊本, 大分, 宮崎, 鹿児島県の一部",
        "prefix": "02",
        "jgd2011": 6670,
        "jgd2000": 2444,
        "tokyo": 30162,
    },
    {
        "label": "III (3) 系: 山口, 島根, 広島",
        "prefix": "03",
        "jgd2011": 6671,
        "jgd2000": 2445,
        "tokyo": 30163,
    },
    {
        "label": "IV (4) 系: 香川, 愛媛, 徳島, 高知",
        "prefix": "04",
        "jgd2011": 6672,
        "jgd2000": 2446,
        "tokyo": 30164,
    },
    {
        "label": "V (5) 系: 兵庫, 鳥取, 岡山",
        "prefix": "05",
        "jgd2011": 6673,
        "jgd2000": 2447,
        "tokyo": 30165,
    },
    {
        "label": "VI (6) 系: 京都, 大阪, 福井, 滋賀, 三重, 奈良 和歌山",
        "prefix": "06",
        "jgd2011": 6674,
        "jgd2000": 2448,
        "tokyo": 30166,
    },
    {
        "label": "VII (7) 系: 石川, 富山, 岐阜, 愛知",
        "prefix": "07",
        "jgd2011": 6675,
        "jgd2000": 2449,
        "tokyo": 30167,
    },
    {
        "label": "VIII (8) 系: 新潟, 長野, 山梨, 静岡",
        "prefix": "08",
        "jgd2011": 6676,
        "jgd2000": 2450,
        "tokyo": 30168,
    },
    {
        "label": "IX (9) 系: 東京都 (小笠原村を除く), 福島, 栃木, 茨城, 埼玉, 千葉, 群馬, 神奈川",
        "prefix": "09",
        "jgd2011": 6677,
        "jgd2000": 2451,
        "tokyo": 30169,
    },
    {
        "label": "X (10) 系: 青森, 秋田, 山形, 岩手, 宮城",
        "prefix": "10",
        "jgd2011": 6678,
        "jgd2000": 2452,
        "tokyo": 30170,
    },
    {
        "label": "XI (11) 系: 北海道 西部",
        "prefix": "11",
        "jgd2011": 6679,
        "jgd2000": 2453,
        "tokyo": 30171,
    },
    {
        "label": "XII (12) 系: 北海道 中央部",
        "prefix": "12",
        "jgd2011": 6680,
        "jgd2000": 2454,
        "tokyo": 30172,
    },
    {
        "label": "XIII (13) 系: 北海道 東部",
        "prefix": "13",
        "jgd2011": 6681,
        "jgd2000": 2455,
        "tokyo": 30173,
    },
    {
        "label": "XIV (14) 系: 東京都の一部 (聟島列島, 父島列島, 母島列島, 硫黄島)",
        "prefix": "14",
        "jgd2011": 6682,
        "jgd2000": 2456,
        "tokyo": 30174,
    },
    {
        "label": "XV (15) 系: 沖縄県 中央部",
        "prefix": "15",
        "jgd2011": 6683,
        "jgd2000": 2457,
        "tokyo": 30175,
    },
    {
        "label": "XVI (16) 系: 沖縄県 西部",
        "prefix": "16",
        "jgd2011": 6684,
        "jgd2000": 2458,
        "tokyo": 30176,
    },
    {
        "label": "XVII (17) 系: 沖縄県 東部",
        "prefix": "17",
        "jgd2011": 6685,
        "jgd2000": 2459,
        "tokyo": 30177,
    },
    {
        "label": "XVIII (18) 系: 東京都の一部 (沖ノ鳥島)",
        "prefix": "18",
        "jgd2011": 6686,
        "jgd2000": 2460,
        "tokyo": 30178,
    },
    {
        "label": "XIX (19) 系: 東京都の一部 (南鳥島)",
        "prefix": "19",
        "jgd2011": 6687,
        "jgd2000": 2461,
        "tokyo": 30179,
    },
]


class CreateLegacyGridAlgorithm(QgsProcessingAlgorithm):
    """Create vector layers representing the "Kokudo Kihon Zukaku" used in Japan."""

    EXTENT = "EXTENT"
    DATUM_NO = "DATUM"
    PLANE_RECTANGULAR_NO = "PLANE_RECTANGULAR_NO"

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
                self.PLANE_RECTANGULAR_NO,
                _tr("平面直角座標系の系番号"),
                options=[v["label"] for v in _PLANE_RECTANGULAR_PLANES],
                defaultValue=1,
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.DATUM_NO,
                _tr("測地系"),
                options=[v["label"] for v in _DATUM_SELECTION],
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
        return CreateLegacyGridAlgorithm()

    def name(self):
        return "createlegacygrid"

    def group(self):
        return None

    def groupId(self):
        return None

    def displayName(self):
        return _tr("国土基本図図郭を作成")

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
        datum_no = self.parameterAsEnum(
            parameters,
            self.DATUM_NO,
            context,
        )
        datum = _DATUM_SELECTION[datum_no]
        plane_rectangular_no = self.parameterAsEnum(
            parameters,
            self.PLANE_RECTANGULAR_NO,
            context,
        )
        crs = QgsCoordinateReferenceSystem.fromEpsgId(
            _PLANE_RECTANGULAR_PLANES[plane_rectangular_no][datum["datum"]]
        )
        feedback.pushInfo(f"{crs}")

        # Extent
        extent = self.parameterAsExtent(parameters, self.EXTENT, context, crs)
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
                crs,
            )
            if sink:
                sinks[layer_kind_name] = sink
                dest_ids[layer_kind_name] = dest_id
                result[layer_kind["param"]] = dest_id

                if layer_kind_name in ["quarter", "eighth"] and extent_bbox is None:
                    raise QgsProcessingException(
                        "地図情報レベル 1000, 500 を出力する場合は、思わぬ大量の地物生成を防ぐため、メッシュの作成範囲を指定する必要があります。"
                    )

                # Set post-processor
                if context.willLoadLayerOnCompletion(dest_id):
                    comp = context.layerToLoadOnCompletionDetails(dest_id)
                    comp.setPostProcessor(self.post_processors[layer_kind_name])

        if not sinks:
            raise QgsProcessingException(
                "地図情報レベルの出力先が1つも選択されていません。\n利用したい地図情報レベルの出力先を一時ファイルやファイルに切り替えて実行してください。"
            )

        # Generate square patches
        total_count = estimate_total_count(
            extent=extent_bbox,
            lv50000="lv50000" in sinks,
            lv5000="lv5000" in sinks,
            lv2500="lv2500" in sinks,
            lv1000="lv1000" in sinks,
            lv500="lv500" in sinks,
        )
        prefix = _PLANE_RECTANGULAR_PLANES[plane_rectangular_no]["prefix"]
        for count, (kind, code, bbox) in enumerate(iter_patch(
            extent=extent_bbox,
            lv50000="lv50000" in sinks,
            lv5000="lv5000" in sinks,
            lv2500="lv2500" in sinks,
            lv1000="lv1000" in sinks,
            lv500="lv500" in sinks,
        )):
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
            feat.setAttribute("code", prefix + code)

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
