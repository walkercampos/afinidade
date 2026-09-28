"""Geohash mínimo (sem dependências) e faixas de distância."""

import math

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
PRECISAO = 5  # ~4,9 km x 4,9 km no equador
FAIXA_KM = 5


def codificar(lat: float, lon: float, precisao: int = PRECISAO) -> str:
    lat_int, lon_int = [-90.0, 90.0], [-180.0, 180.0]
    bit, ch, par = 0, 0, True
    resultado = []
    while len(resultado) < precisao:
        intervalo, valor = (lon_int, lon) if par else (lat_int, lat)
        meio = (intervalo[0] + intervalo[1]) / 2
        if valor >= meio:
            ch = (ch << 1) | 1
            intervalo[0] = meio
        else:
            ch <<= 1
            intervalo[1] = meio
        par = not par
        bit += 1
        if bit == 5:
            resultado.append(_BASE32[ch])
            bit, ch = 0, 0
    return "".join(resultado)


def centro(geohash: str) -> tuple[float, float]:
    lat_int, lon_int = [-90.0, 90.0], [-180.0, 180.0]
    par = True
    for c in geohash:
        v = _BASE32.index(c)
        for i in range(4, -1, -1):
            intervalo = lon_int if par else lat_int
            meio = (intervalo[0] + intervalo[1]) / 2
            if (v >> i) & 1:
                intervalo[0] = meio
            else:
                intervalo[1] = meio
            par = not par
    return (lat_int[0] + lat_int[1]) / 2, (lon_int[0] + lon_int[1]) / 2


def faixa_km(distancia: float | None) -> int | None:
    """Arredonda para cima em faixas de 5 km ("até 5 km", "até 10 km", ...)."""
    if distancia is None:
        return None
    return max(FAIXA_KM, math.ceil(distancia / FAIXA_KM) * FAIXA_KM)


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine, igual à função SQL distancia_km (migração 0003)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))
