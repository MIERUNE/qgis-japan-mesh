from typing import Optional, Tuple

_VALID_LENGTH = (4, 6, 8, 9, 10, 11)
_VALID_QUAD = ("1", "2", "3", "4")

LngLatBox = Tuple[float, float, float, float]


def grid_square_code_to_bbox(  # noqa: C901
    code: str,
) -> Optional[tuple[float, float, float, float]]:
    if not code.isdecimal():
        code = "".join(c for c in str(code) if c.isdigit())
    length = len(code)
    if length not in _VALID_LENGTH:
        return None
    lat = int(code[:2])
    lng = int(code[2:4]) + 100
    if length == 4:
        return (lng, lat / 1.5, lng + 1, (lat + 1) / 1.5)

    lat += int(code[4]) * 0.125
    lng += int(code[5]) * 0.125
    if length == 6:
        return (lng, lat / 1.5, lng + 0.125, (lat + 0.125) / 1.5)

    # 1km
    lat10 = int(code[6]) * 0.125
    lng10 = int(code[7]) * 0.125
    if length == 8:
        lat1 = lat + lat10 / 10
        lng1 = lng + lng10 / 10
        lat2 = lat + (lat10 + 0.125) / 10
        lng2 = lng + (lng10 + 0.125) / 10
        return (lng1, lat1 / 1.5, lng2, lat2 / 1.5)

    # 1/2 (500m)
    a = code[8]
    if a not in _VALID_QUAD:
        return None
    if a == "3" or a == "4":
        lat10 += 0.0625
    if a == "2" or a == "4":
        lng10 += 0.0625
    if length == 9:
        lat1 = lat + lat10 / 10
        lng1 = lng + lng10 / 10
        lat2 = lat + (lat10 + 0.0625) / 10
        lng2 = lng + (lng10 + 0.0625) / 10
        return (lng1, lat1 / 1.5, lng2, lat2 / 1.5)

    # 1/4 (250m)
    a = code[9]
    if a not in _VALID_QUAD:
        return None
    if a == "3" or a == "4":
        lat10 += 0.03125
    if a == "2" or a == "4":
        lng10 += 0.03125
    if length == 10:
        lat1 = lat + lat10 / 10
        lng1 = lng + lng10 / 10
        lat2 = lat + (lat10 + 0.03125) / 10
        lng2 = lng + (lng10 + 0.03125) / 10
        return (lng1, lat1 / 1.5, lng2, lat2 / 1.5)

    # 1/8 (125m)
    a = code[10]
    if a not in _VALID_QUAD:
        return None
    if a == "3" or a == "4":
        lat10 += 0.015625
    if a == "2" or a == "4":
        lng10 += 0.015625
    lat1 = lat + lat10 / 10
    lng1 = lng + lng10 / 10
    lat2 = lat + (lat10 + 0.015625) / 10
    lng2 = lng + (lng10 + 0.015625) / 10
    return (lng1, lat1 / 1.5, lng2, lat2 / 1.5)
