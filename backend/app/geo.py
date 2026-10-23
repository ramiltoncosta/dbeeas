"""Conversão entre pontos do PostGIS e latitude/longitude."""

from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape


def ponto(latitude: float | None, longitude: float | None) -> WKTElement | None:
    if latitude is None or longitude is None:
        return None
    # Atenção: no PostGIS a ordem é (longitude, latitude)
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def lat_lon(valor) -> tuple[float | None, float | None]:
    if valor is None:
        return None, None
    if isinstance(valor, WKTElement):  # ainda não foi salvo no banco
        lon, lat = (float(x) for x in valor.data.split("(")[1].rstrip(")").split())
        return lat, lon
    p = to_shape(valor)
    return p.y, p.x
