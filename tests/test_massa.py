"""Massa de teste no banco de verdade: as pessoas aparecem na descoberta e curtir de volta conecta."""

import asyncio

import pytest

from carga.massa import DestinoProibido, criar_massa
from tests.conftest import URL

TODOS = [
    "homem-cis",
    "mulher-cis",
    "homem-trans",
    "mulher-trans",
    "travesti",
    "nao-binarie",
    "genero-fluido",
    "agenero",
    "outro",
]


def test_massa_aparece_na_descoberta_e_curtir_de_volta_conecta(pessoa, db):
    eu = pessoa("mulher-cis", TODOS, quero=["bondage"])
    r = asyncio.run(criar_massa(URL, 150, curtir=eu.handle))
    assert r["pessoas"] == 150
    assert r["curtiram_voce"] > 0
    assert db.fetchval("SELECT count(*) FROM contas WHERE handle LIKE 'massa\\_%'") == 150

    # Rodar de novo recria a mesma massa, sem duplicar
    asyncio.run(criar_massa(URL, 150, curtir=eu.handle))
    assert db.fetchval("SELECT count(*) FROM contas WHERE handle LIKE 'massa\\_%'") == 150

    vistos = eu.get("/api/descobrir?limite=50")
    assert vistos.status_code == 200, vistos.text
    candidatos = [c["perfil"]["id"] for c in vistos.json()]
    assert candidatos, "a descoberta precisa mostrar gente da massa"

    quem_curtiu = {str(r["de_id"]) for r in db.fetch("SELECT de_id FROM curtidas WHERE para_id = $1::uuid", eu.id)}
    alguem = next(c for c in candidatos if c in quem_curtiu)
    assert eu.post(f"/api/perfis/{alguem}/curtir").json() == {"conexao": True}

    db.execute("DELETE FROM contas WHERE handle LIKE 'massa\\_%'")


def test_massa_recusa_apelido_inexistente(client):
    with pytest.raises(DestinoProibido, match="não existe conta"):
        asyncio.run(criar_massa(URL, 10, curtir="ninguem_com_esse_apelido"))
