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


def test_nota_so_para_os_mais_ativos_depois_de_todos_os_filtros(pessoa, db, monkeypatch):
    """Carga: a nota é calculada só para os CANDIDATOS_MAX elegíveis mais ativos. Os filtros
    (bloqueio, curtida, limites) valem ANTES do corte: quem some não ocupa vaga."""
    from app import descoberta

    monkeypatch.setattr(descoberta, "CANDIDATOS_MAX", 3)
    # Par de gêneros exclusivo deste teste: os perfis "no futuro" não podem aparecer para outros
    # testes que compartilham o banco (test_paridade compara conjuntos exatos).
    eu = pessoa("nao-binarie", ["homem-trans"], quero=["roleplay"], limite=["latex"])
    outros = [pessoa("homem-trans", ["nao-binarie"], quero=["roleplay"]) for _ in range(5)]
    conflito = pessoa("homem-trans", ["nao-binarie"], quero=["latex"])  # quer um limite meu
    bloqueada, curtida, *resto = outros
    # Ordem de atividade (no futuro, para ficarem à frente de perfis de outros testes):
    # conflito > bloqueada > curtida > resto[0] > resto[1] > resto[2]
    for minutos, p in zip([60, 50, 40, 30, 20, 10], [conflito, bloqueada, curtida, *resto], strict=True):
        db.execute(
            "UPDATE perfis SET ativo_em = now() + make_interval(mins => $2) WHERE conta_id = $1::uuid", p.id, minutos
        )
    assert eu.post(f"/api/perfis/{bloqueada.id}/bloquear").status_code == 204
    assert eu.post(f"/api/perfis/{curtida.id}/curtir").status_code == 200

    # As 3 vagas vão para os 3 elegíveis mais ativos; conflito, bloqueada e curtida não ocupam vaga
    assert _ids(eu) == {r.id for r in resto}

    monkeypatch.setattr(descoberta, "CANDIDATOS_MAX", 2)
    assert _ids(eu) == {resto[0].id, resto[1].id}
