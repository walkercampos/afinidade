import pytest

from app import admin
from tests.conftest import SENHA


@pytest.fixture
def moderador(pessoa, client):
    m = pessoa()
    assert admin.main(["moderador", m.handle]) == 0
    return m


def _envelhecer(db, *pessoas):
    """Contas novas (< 24 h) não contam para a revisão automática por volume."""
    db.execute("UPDATE contas SET criado_em = now() - interval '2 days' WHERE id = ANY($1::uuid[])",
               [p.id for p in pessoas])


def test_denunciar_bloqueia_na_hora(pessoa):
    a = pessoa("homem-cis", ["mulher-cis"], quero=["latex"])
    b = pessoa("mulher-cis", ["homem-cis"], quero=["latex"])
    assert a.post(f"/api/perfis/{b.id}/denunciar", json={"motivo": "spam"}).status_code == 204
    assert a.get(f"/api/perfis/{b.id}").status_code == 404
    assert b.get(f"/api/perfis/{a.id}").status_code == 404


def test_tres_denunciantes_antigos_ocultam_ate_revisao(pessoa, db, moderador):
    alvo = pessoa("mulher-cis", ["homem-cis"], quero=["latex"])
    observador = pessoa("homem-cis", ["mulher-cis"], quero=["latex"])
    novos = [pessoa() for _ in range(3)]
    for n in novos:  # contas recém-criadas: não disparam a revisão
        n.post(f"/api/perfis/{alvo.id}/denunciar", json={"motivo": "assedio"})
    assert db.fetchval("SELECT situacao FROM contas WHERE id = $1::uuid", alvo.id) == "ativa"

    antigos = [pessoa() for _ in range(3)]
    _envelhecer(db, *antigos)
    for n in antigos:
        n.post(f"/api/perfis/{alvo.id}/denunciar", json={"motivo": "assedio", "detalhes": "insistente"})
    assert db.fetchval("SELECT situacao FROM contas WHERE id = $1::uuid", alvo.id) == "em_revisao"

    # Em revisão: some da descoberta e não consegue curtir ninguém
    assert alvo.id not in {c["perfil"]["id"] for c in observador.get("/api/descobrir").json()}
    assert alvo.post(f"/api/perfis/{observador.id}/curtir").status_code == 403

    fila = moderador.get("/api/moderacao/fila").json()
    item = next(i for i in fila if i["conta_id"] == alvo.id)
    assert len(item["denuncias"]) == 6 and item["situacao"] == "em_revisao"

    assert moderador.post(f"/api/moderacao/contas/{alvo.id}/decisao", json={"acao": "restaurar"}).status_code == 204
    assert observador.get(f"/api/perfis/{alvo.id}").status_code == 200
    assert not any(i["conta_id"] == alvo.id for i in moderador.get("/api/moderacao/fila").json())


def test_motivo_grave_oculta_com_uma_denuncia(pessoa, db):
    alvo = pessoa()
    pessoa().post(f"/api/perfis/{alvo.id}/denunciar", json={"motivo": "menor_de_idade"})
    assert db.fetchval("SELECT situacao FROM contas WHERE id = $1::uuid", alvo.id) == "em_revisao"


def test_banir_derruba_sessoes_e_login(pessoa, client, moderador):
    alvo = pessoa()
    pessoa().post(f"/api/perfis/{alvo.id}/denunciar", json={"motivo": "perfil_falso"})
    r = moderador.post(f"/api/moderacao/contas/{alvo.id}/decisao", json={"acao": "banir", "observacao": "fake"})
    assert r.status_code == 204
    assert alvo.get("/api/perfil").status_code == 401
    assert client.post("/api/auth/login", json={"handle": alvo.handle, "senha": SENHA}).status_code == 403


def test_rotas_de_moderacao_invisiveis_para_usuarios(pessoa):
    comum = pessoa()
    assert comum.get("/api/moderacao/fila").status_code == 404
    assert comum.post(f"/api/moderacao/contas/{comum.id}/decisao", json={"acao": "banir"}).status_code == 404
