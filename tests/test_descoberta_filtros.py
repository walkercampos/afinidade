"""Parte 5: filtros da descoberta (só com foto, ativos nos últimos dias)."""

from pathlib import Path

FOTO = Path(__file__).resolve().parent / "e2e" / "foto.jpg"


def _ids(p, **params):
    return {c["perfil"]["id"] for c in p.get("/api/descobrir", params={"limite": 100, **params}).json()}


def test_so_com_foto_e_ativos(pessoa, db):
    eu = pessoa("travesti", ["mulher-trans"], quero=["impact-play"])
    com_foto = pessoa("mulher-trans", ["travesti"], quero=["impact-play"])
    sem_foto = pessoa("mulher-trans", ["travesti"], quero=["impact-play"])
    sumida = pessoa("mulher-trans", ["travesti"], quero=["impact-play"])
    r = com_foto.post("/api/fotos", content=FOTO.read_bytes(), headers={**com_foto.h, "Content-Type": "image/jpeg"})
    assert r.status_code == 201, r.text
    db.execute("UPDATE perfis SET ativo_em = now() - interval '20 days' WHERE conta_id = $1::uuid", sumida.id)

    assert {com_foto.id, sem_foto.id, sumida.id} <= _ids(eu)
    assert com_foto.id in _ids(eu, com_foto="true") and sem_foto.id not in _ids(eu, com_foto="true")
    assert sumida.id not in _ids(eu, ativos_dias=7) and sem_foto.id in _ids(eu, ativos_dias=7)
    assert eu.get("/api/descobrir", params={"ativos_dias": 0}).status_code == 422
    assert eu.get("/api/descobrir", params={"ativos_dias": 91}).status_code == 422
