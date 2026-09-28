from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app import descoberta, geo


@pytest.mark.parametrize("lat,lon", [(-23.55, -46.63), (0, 0), (89.9, 179.9), (-89.9, -179.9)])
def test_centro_da_celula_fica_a_menos_de_5km(lat, lon):
    celula = geo.codificar(lat, lon)
    assert len(celula) == 5
    c_lat, c_lon = geo.centro(celula)
    assert geo.codificar(c_lat, c_lon) == celula
    assert geo.distancia_km(lat, lon, c_lat, c_lon) < 5


def test_cursor_ida_e_volta():
    linha = {"score_mutuo": 87, "similaridade": 40, "ativo_em": datetime.now(UTC), "conta_id": uuid4()}
    for ordem, esperado in (("compatibilidade", (87, 40)), ("afinidade", (40, 87)), ("recentes", (0, 0))):
        k1, k2, ativo, conta = descoberta.decodificar_cursor(descoberta.codificar_cursor(linha, ordem))
        assert (k1, k2) == esperado and ativo == linha["ativo_em"] and conta == linha["conta_id"]


@pytest.mark.parametrize("cursor", ["", "lixo", "W10", "WyJhIiwxLCIyMDI2IiwieCJd"])
def test_cursor_invalido(cursor):
    with pytest.raises(descoberta.CursorInvalido):
        descoberta.decodificar_cursor(cursor)
