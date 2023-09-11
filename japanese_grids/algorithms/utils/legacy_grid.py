from typing import Iterator, Optional, Tuple

LngLatBox = Tuple[float, float, float, float]


def _intersect(a: LngLatBox, b: LngLatBox):
    a_lng0, a_lat0, a_lng1, a_lat1 = a
    b_lng0, b_lat0, b_lng1, b_lat1 = b
    return not (
        a_lng1 < b_lng0 or a_lng0 > b_lng1 or a_lat1 < b_lat0 or a_lat0 > b_lat1
    )


def iter_lv50000_mesh_patch(
    extent: Optional[LngLatBox] = None,
) -> Iterator[tuple[str, LngLatBox]]:
    """地図情報レベル50000"""
    for xi in range(20):
        x = 300000 - 30000 * xi
        cx = chr(ord("A") + xi)
        for yi in range(8):
            cy = chr(ord("A") + yi)
            y = -160000 + 40000 * yi
            bbox = (y, x, y + 40000, x + 30000)
            if extent is None or (_intersect(bbox, extent)):
                yield (cx + cy, bbox)


def iter_lv5000_mesh_patch(
    primary_mesh_patch: tuple[str, LngLatBox], extent: Optional[LngLatBox] = None
):
    """地図情報レベル5000"""
    parent_code, parent_bbox = primary_mesh_patch
    parent_y0, parent_x0, _, _ = parent_bbox
    for xi in range(0, 10):
        x = -3000 * xi + parent_x0 + 30000
        prefix = parent_code + str(xi)
        for yi in range(0, 10):
            y = 4000 * yi + parent_y0
            bbox = (y, x - 3000, y + 4000, x)
            if extent is None or _intersect(bbox, extent):
                yield (prefix + str(yi), bbox)


def iter_lv2500_mesh_patch(standard_mesh_patch: tuple[str, LngLatBox]):
    """地図情報レベル2500"""
    parent_code, parent_bbox = standard_mesh_patch
    y0, x0, y1, x1 = parent_bbox
    xh = (x0 + x1) / 2
    yh = (y0 + y1) / 2
    return [
        (parent_code + "3", (y0, x0, yh, xh)),
        (parent_code + "4", (yh, x0, y1, xh)),
        (parent_code + "1", (y0, xh, yh, x1)),
        (parent_code + "2", (yh, xh, y1, x1)),
    ]


def iter_lv1000_mesh_patch(
    primary_mesh_patch: tuple[str, LngLatBox], extent: Optional[LngLatBox] = None
):
    """地図情報レベル1000"""
    parent_code, parent_bbox = primary_mesh_patch
    parent_y0, parent_x0, _, _ = parent_bbox
    for xi in range(0, 5):
        x = -600 * xi + parent_x0 + 3000
        prefix = parent_code + str(xi)
        for yi in range(0, 5):
            y = 800 * yi + parent_y0
            bbox = (y, x - 600, y + 800, x)
            cy = chr(ord("A") + yi)
            if extent is None or _intersect(bbox, extent):
                yield (prefix + cy, bbox)


def iter_lv500_mesh_patch(
    primary_mesh_patch: tuple[str, LngLatBox], extent: Optional[LngLatBox] = None
):
    """地図情報レベル500"""
    parent_code, parent_bbox = primary_mesh_patch
    parent_y0, parent_x0, _, _ = parent_bbox
    for xi in range(0, 10):
        x = -300 * xi + parent_x0 + 3000
        prefix = parent_code + str(xi)
        for yi in range(0, 10):
            y = 400 * yi + parent_y0
            bbox = (y, x - 300, y + 400, x)
            if extent is None or _intersect(bbox, extent):
                yield (prefix + str(yi), bbox)


def iter_patch(  # noqa: C901
    extent: Optional[LngLatBox] = None,
    lv50000: bool = False,
    lv5000: bool = False,
    lv2500: bool = False,
    lv1000: bool = False,
    lv500: bool = False,
) -> Iterator[tuple[str, str, LngLatBox]]:
    """メッシュのパッチを返すイテレータを作る"""
    for lv50000_mesh_patch in iter_lv50000_mesh_patch(extent=extent):
        if lv50000:
            yield ("lv50000", *lv50000_mesh_patch)
        if lv5000 or lv2500 or lv1000 or lv500:
            for lv5000_mesh_patch in iter_lv5000_mesh_patch(lv50000_mesh_patch, extent):
                if lv5000:
                    yield ("lv5000", *lv5000_mesh_patch)
                if lv2500:
                    for lv2500_mesh_patch in iter_lv2500_mesh_patch(lv5000_mesh_patch):
                        yield ("lv2500", *lv2500_mesh_patch)
                if lv1000:
                    for lv1000_mesh_patch in iter_lv1000_mesh_patch(lv5000_mesh_patch):
                        yield ("lv1000", *lv1000_mesh_patch)
                if lv500:
                    for lv500_mesh_patch in iter_lv500_mesh_patch(lv5000_mesh_patch):
                        yield ("lv500", *lv500_mesh_patch)


def estimate_total_count(
    extent: Optional[LngLatBox] = None,
    lv50000: bool = False,
    lv5000: bool = False,
    lv2500: bool = False,
    lv1000: bool = False,
    lv500: bool = False,
):
    """生成されるパッチ数の概数を返す"""
    num_primary = len(list(iter_lv50000_mesh_patch(extent=extent)))

    c = 0
    if lv50000:
        c += num_primary
    if lv5000:
        c += num_primary * 100
    if lv2500:
        c += num_primary * 100 * 4
    if lv1000:
        c += num_primary * 100 * 25
    if lv500:
        c += num_primary * 100 * 100
    return c
