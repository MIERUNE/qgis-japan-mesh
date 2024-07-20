from typing import Optional, Tuple, TypedDict

from .grid_square import AVAILABLE_PRIMARY_CODES

_VALID_LENGTH = (4, 6, 8, 9, 10, 11)
_VALID_QUAD = ("1", "2", "3", "4")

LngLatBox = Tuple[float, float, float, float]

_MULTIPLIER = 30  # 浮動小数点誤差を回避するために内部的な経緯度にかける係数


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


class Codes(TypedDict):
    primary: str
    secondary: str
    standard: str
    half: str
    quarter: str
    eighth: str


def lnglat_to_grid_square_code(lng: float, lat: float) -> Optional[Codes]:
    lat *= 1.5
    lat_r = int(lat)
    lng_r = int(lng)
    primary_code = f"{lat_r:02d}{lng_r-100:02d}"
    if primary_code not in AVAILABLE_PRIMARY_CODES:
        return None

    lat = (lat - lat_r) * 8
    lng = (lng - lng_r) * 8
    lat_r = int(lat)
    lng_r = int(lng)
    secondary_code = primary_code + f"{lat_r}{lng_r}"

    lat = (lat - lat_r) * 10
    lng = (lng - lng_r) * 10
    lat_r = int(lat)
    lng_r = int(lng)
    standard_code = secondary_code + f"{lat_r}{lng_r}"

    lat = (lat - lat_r) * 2
    lng = (lng - lng_r) * 2
    lat_r = int(lat)
    lng_r = int(lng)
    suffix = 1 + lat_r * 2 + lng_r
    half_code = standard_code + str(suffix)

    lat = (lat - lat_r) * 2
    lng = (lng - lng_r) * 2
    lat_r = int(lat)
    lng_r = int(lng)
    suffix = 1 + lat_r * 2 + lng_r
    quarter_code = half_code + str(suffix)

    lat = (lat - lat_r) * 2
    lng = (lng - lng_r) * 2
    lat_r = int(lat)
    lng_r = int(lng)
    suffix = 1 + lat_r * 2 + lng_r
    eighth_code = quarter_code + str(suffix)

    return {
        "primary": primary_code,
        "secondary": secondary_code,
        "standard": standard_code,
        "half": half_code,
        "quarter": quarter_code,
        "eighth": eighth_code,
    }
