"""Parte 7: moderação automática do conteúdo público (regras locais) e painel."""

import pytest

from app import moderacao_automatica
from tests.test_moderacao import moderador  # noqa: F401 (fixture)

# Precisão importa: um falso positivo esconde uma pessoa inocente até a revisão.
SINALIZA = [
    "Tenho 16 anos e gosto de sair",
    "sou menor de idade",
    "Idade: 15",
    "16a curiosa",
    "Ana, 17",
    "tô com 17",
    "17 aninhos",
    "estou no 2 ano do ensino médio",
    "Busco alguém de menor idade",
]
NAO_SINALIZA = [
    "Tenho 30 anos",
    "Gosto de 3 anos de namoro",
    "Moro aqui há 5 anos",
    "Casada há 12 anos",
    "12 anos de experiência em dança",
    "Nada de menor de idade aqui, só 18+",
    "Não sou menor, tenho 25",
    "menores? não, só adultos",
    "Tenho 2 filhos",
    "Leo, 34",
    "bebo 2 cervejas",
    "",
]


@pytest.mark.parametrize("texto", SINALIZA)
def test_sinais_de_menor_de_idade(texto):
    sinais = moderacao_automatica.analisar(texto)
    assert sinais and {s.motivo for s in sinais} == {"menor_de_idade"}


@pytest.mark.parametrize("texto", NAO_SINALIZA)
def test_sem_falsos_positivos(texto):
    assert moderacao_automatica.analisar(texto) == []


def test_perfil_sinalizado_vai_para_revisao_e_fila(pessoa, moderador, db):  # noqa: F811
    p = pessoa("mulher-cis", ["homem-cis"], quero=["latex"])
    vendo = pessoa("homem-cis", ["mulher-cis"], quero=["latex"])
    assert p.id in {c["perfil"]["id"] for c in vendo.get("/api/descobrir", params={"limite": 100}).json()}

    perfil = p.get("/api/perfil").json()
    r = p.put(
        "/api/perfil",
        json={
            **perfil,
            "bio": "Oi! Tenho 16 anos e sou nova aqui",
            "tags_interesses": {"quero": perfil["tags_interesses"]["quero"], "curioso": [], "limite_absoluto": []},
        },
    )
    assert r.status_code == 200
    # Fica oculta na hora, e a moderação vê o caso com o trecho que disparou a regra
    assert db.fetchval("SELECT situacao FROM contas WHERE id = $1::uuid", p.id) == "em_revisao"
    assert p.id not in {c["perfil"]["id"] for c in vendo.get("/api/descobrir", params={"limite": 100}).json()}
    [caso] = [c for c in moderador.get("/api/moderacao/fila").json() if c["conta_id"] == p.id]
    [denuncia] = caso["denuncias"]
    assert denuncia["motivo"] == "menor_de_idade" and "16 anos" in denuncia["detalhes"]
    assert db.fetchval("SELECT denunciante_id FROM denuncias WHERE id = $1", denuncia["id"]) is None  # do sistema

    # Salvar de novo não duplica a denúncia aberta
    p.put("/api/perfil", json={**perfil, "bio": "Tenho 16 anos", "tags_interesses": perfil["tags_interesses"]})
    assert db.fetchval("SELECT count(*) FROM denuncias WHERE denunciado_id = $1::uuid AND status = 'aberta'", p.id) == 1

    # Moderação decide
    assert moderador.post(f"/api/moderacao/contas/{p.id}/decisao", json={"acao": "banir"}).status_code == 204
    assert p.get("/api/perfil").status_code == 401


def test_texto_normal_nao_mexe_em_nada(pessoa, db):
    p = pessoa()
    perfil = p.get("/api/perfil").json()
    p.put("/api/perfil", json={**perfil, "bio": "Tenho 29 anos, moro aqui há 5 anos"})
    assert db.fetchval("SELECT situacao FROM contas WHERE id = $1::uuid", p.id) == "ativa"
    assert db.fetchval("SELECT count(*) FROM denuncias WHERE denunciado_id = $1::uuid", p.id) == 0


def test_conta_informa_se_e_moderador(pessoa, moderador):  # noqa: F811
    assert pessoa().get("/api/conta").json()["moderador"] is False
    assert moderador.get("/api/conta").json()["moderador"] is True
