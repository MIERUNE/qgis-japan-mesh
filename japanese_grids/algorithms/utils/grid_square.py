from typing import Iterator, Optional, Tuple

AVAILABLE_PRIMARY_CODES = frozenset(
    [
        "3036",
        "3622",
        "3623",
        "3624",
        "3631",
        "3641",
        "3653",
        "3724",
        "3725",
        "3741",
        "3823",
        "3824",
        "3831",
        "3841",
        "3926",
        "3927",
        "3928",
        "3942",
        "4027",
        "4028",
        "4040",
        "4042",
        "4128",
        "4129",
        "4142",
        "4229",
        "4230",
        "4328",
        "4329",
        "4429",
        "4440",
        "4529",
        "4530",
        "4531",
        "4540",
        "4629",
        "4630",
        "4631",
        "4728",
        "4729",
        "4730",
        "4731",
        "4739",
        "4740",
        "4828",
        "4829",
        "4830",
        "4831",
        "4839",
        "4928",
        "4929",
        "4930",
        "4931",
        "4932",
        "4933",
        "4934",
        "4939",
        "5029",
        "5030",
        "5031",
        "5032",
        "5033",
        "5034",
        "5035",
        "5036",
        "5038",
        "5039",
        "5129",
        "5130",
        "5131",
        "5132",
        "5133",
        "5134",
        "5135",
        "5136",
        "5137",
        "5138",
        "5139",
        "5229",
        "5231",
        "5232",
        "5233",
        "5234",
        "5235",
        "5236",
        "5237",
        "5238",
        "5239",
        "5240",
        "5332",
        "5333",
        "5334",
        "5335",
        "5336",
        "5337",
        "5338",
        "5339",
        "5340",
        "5432",
        "5433",
        "5435",
        "5436",
        "5437",
        "5438",
        "5439",
        "5440",
        "5531",
        "5536",
        "5537",
        "5538",
        "5539",
        "5540",
        "5541",
        "5636",
        "5637",
        "5638",
        "5639",
        "5640",
        "5641",
        "5738",
        "5739",
        "5740",
        "5741",
        "5839",
        "5840",
        "5841",
        "5939",
        "5940",
        "5941",
        "5942",
        "6039",
        "6040",
        "6041",
        "6139",
        "6140",
        "6141",
        "6239",
        "6240",
        "6241",
        "6243",
        "6339",
        "6340",
        "6341",
        "6342",
        "6343",
        "6439",
        "6440",
        "6441",
        "6442",
        "6443",
        "6444",
        "6445",
        "6540",
        "6541",
        "6542",
        "6543",
        "6544",
        "6545",
        "6546",
        "6641",
        "6642",
        "6643",
        "6644",
        "6645",
        "6646",
        "6647",
        "6740",
        "6741",
        "6742",
        "6747",
        "6748",
        "6840",
        "6841",
        "6842",
        "6847",
        "6848",
    ]
)

MULTIPLIER = 30  # 浮動小数点誤差を回避するために内部的な経緯度にかける係数

LngLatBox = Tuple[float, float, float, float]


def _intersect(a: LngLatBox, b: LngLatBox):
    a_lng0, a_lat0, a_lng1, a_lat1 = a
    b_lng0, b_lat0, b_lng1, b_lat1 = b
    return not (
        a_lng1 < b_lng0 * MULTIPLIER
        or a_lng0 > b_lng1 * MULTIPLIER
        or a_lat1 < b_lat0 * MULTIPLIER
        or a_lat0 > b_lat1 * MULTIPLIER
    )


def _iter_primary_mesh_patch(
    extent: Optional[LngLatBox] = None,
) -> Iterator[tuple[str, LngLatBox]]:
    """第1次地域区画"""
    for y in range(30, 68 + 1):
        lat0 = y * MULTIPLIER * 2 / 3
        lat1 = (y + 1) * MULTIPLIER * 2 / 3
        for x in range(22, 53 + 1):
            lng0 = (x + 100) * MULTIPLIER
            lng1 = (x + 101) * MULTIPLIER
            code = f"{y:02d}{x:02d}"
            if code in AVAILABLE_PRIMARY_CODES:
                bbox = (lng0, lat0, lng1, lat1)
                if extent is None or (_intersect(bbox, extent)):
                    yield (code, bbox)


def _iter_secondary_mesh_patch(
    primary_mesh_patch: tuple[str, LngLatBox], extent: Optional[LngLatBox] = None
):
    """第2次地域区画"""
    parent_code, parent_bbox = primary_mesh_patch
    parent_lng0, parent_lat0, parent_lng1, parent_lat1 = parent_bbox
    sy = (parent_lat1 - parent_lat0) / 8
    sx = (parent_lng1 - parent_lng0) / 8
    for y in range(8):
        lat0 = sy * y + parent_lat0
        prefix = parent_code + str(y)
        for x in range(8):
            lng0 = sx * x + parent_lng0
            bbox = (lng0, lat0, lng0 + sx, lat0 + sy)
            if extent is None or _intersect(bbox, extent):
                yield (prefix + str(x), bbox)


def _iter_standard_mesh_patch(
    secondary_mesh_patch: tuple[str, LngLatBox], extent: Optional[LngLatBox] = None
):
    """基準地域メッシュ (第3次地域区画)"""
    parent_code, parent_bbox = secondary_mesh_patch
    parent_lng0, parent_lat0, parent_lng1, parent_lat1 = parent_bbox
    sy = (parent_lat1 - parent_lat0) / 10
    sx = (parent_lng1 - parent_lng0) / 10
    for y in range(10):
        lat0 = sy * y + parent_lat0
        prefix = parent_code + str(y)
        for x in range(10):
            lng0 = sx * x + parent_lng0
            bbox = (lng0, lat0, lng0 + sx, lat0 + sy)
            if extent is None or _intersect(bbox, extent):
                yield (prefix + str(x), bbox)


def _iter_subdivided_mesh_patch(standard_mesh_patch: tuple[str, LngLatBox]):
    parent_code, parent_bbox = standard_mesh_patch
    lng0, lat0, lng1, lat1 = parent_bbox
    lath = (lat0 + lat1) / 2
    lngh = (lng0 + lng1) / 2
    return [
        (parent_code + "1", (lng0, lat0, lngh, lath)),
        (parent_code + "2", (lngh, lat0, lng1, lath)),
        (parent_code + "3", (lng0, lath, lngh, lat1)),
        (parent_code + "4", (lngh, lath, lng1, lat1)),
    ]


def _iter_patch(  # noqa: C901
    extent: Optional[LngLatBox] = None,
    primary: bool = False,
    secondary: bool = False,
    standard: bool = False,
    half: bool = False,
    quarter: bool = False,
    eighth: bool = False,
) -> Iterator[tuple[str, str, LngLatBox]]:
    for primary_mesh_patch in _iter_primary_mesh_patch(extent=extent):
        if primary:
            yield ("primary", *primary_mesh_patch)
        if not (secondary or standard or half or quarter or eighth):
            continue

        for secondary_mesh_patch in _iter_secondary_mesh_patch(
            primary_mesh_patch, extent
        ):
            if secondary:
                yield ("secondary", *secondary_mesh_patch)
            if not (standard or half or quarter or eighth):
                continue
            for standard_mesh_patch in _iter_standard_mesh_patch(
                secondary_mesh_patch, extent
            ):
                if standard:
                    yield ("standard", *standard_mesh_patch)
                if half or quarter or eighth:
                    for patch2 in _iter_subdivided_mesh_patch(standard_mesh_patch):
                        if half:
                            yield ("half", *patch2)
                        if quarter or eighth:
                            for patch4 in _iter_subdivided_mesh_patch(patch2):
                                if quarter:
                                    yield ("quarter", *patch4)
                                if eighth:
                                    for patch8 in _iter_subdivided_mesh_patch(patch4):
                                        yield ("eighth", *patch8)


def iter_patch(
    extent: Optional[LngLatBox] = None,
    primary: bool = False,
    secondary: bool = False,
    standard: bool = False,
    half: bool = False,
    quarter: bool = False,
    eighth: bool = False,
) -> Iterator[tuple[str, str, LngLatBox]]:
    """メッシュのパッチを返すイテレータを作る"""
    for kind, code, bbox in _iter_patch(
        extent=extent,
        primary=primary,
        secondary=secondary,
        standard=standard,
        half=half,
        quarter=quarter,
        eighth=eighth,
    ):
        v0, v1, v2, v3 = bbox
        yield kind, code, (
            v0 / MULTIPLIER,
            v1 / MULTIPLIER,
            v2 / MULTIPLIER,
            v3 / MULTIPLIER,
        )


def estimate_total_count(
    extent: Optional[LngLatBox] = None,
    primary: bool = False,
    secondary: bool = False,
    standard: bool = False,
    half: bool = False,
    quarter: bool = False,
    eighth: bool = False,
):
    """生成されるパッチ数の概数を返す"""
    num_primary = len(list(_iter_primary_mesh_patch(extent=extent)))

    c = 0
    if primary:
        c += num_primary
    if secondary:
        c += num_primary * 64  # (8*8)
    if standard:
        c += num_primary * 64 * 100  # (8*8) * (10*10)
    if half:
        c += num_primary * 64 * 100 * 4  # (8*8) * (10*10)
    if quarter:
        c += num_primary * 64 * 100 * 4 * 4
    if eighth:
        c += num_primary * 64 * 100 * 4 * 4 * 4
    return c
