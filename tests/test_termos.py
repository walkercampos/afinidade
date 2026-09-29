"""Parte 10: termos versionados, aceite obrigatório e modo discrição."""

import re
from pathlib import Path

import pytest

from app import termos

ESTATICO = Path(__file__).resolve().parent.parent / "static"


@pytest.fixture
def sem_aceite(monkeypatch):
    """Contas criadas sem aceitar os termos (o helper normalmente aceita, como o front)."""
    import tests.conftest as conftest

    monkeypatch.setattr(conftest, "ACEITAR_TERMOS", False)


def test_versao_publica(client):
    r = client.get("/api/termos").json()
    assert r == {"versao": termos.VERSAO_ATUAL, "termos_url": "/termos.html", "privacidade_url": "/privacidade.html"}


def test_sem_aceite_nao_ve_ninguem_mas_cuida_da_propria_conta(sem_aceite, pessoa):
    p = pessoa()
    r = p.get("/api/descobrir")
    assert r.status_code == 403 and r.json()["detail"] == termos.DETALHE_PENDENTE
    # O próprio perfil, as preferências e a exclusão da conta continuam acessíveis
    assert p.get("/api/perfil").status_code == 200
    assert p.put("/api/conta/preferencias", json={"modo_discreto": True}).status_code == 200
    assert p.get("/api/termos/situacao").json()["aceita"] is False

    assert p.post("/api/termos/aceitar", json={"versao": "2000-01-01"}).status_code == 409  # versão velha
    s = p.post("/api/termos/aceitar", json={"versao": termos.VERSAO_ATUAL}).json()
    assert s["aceita"] is True and s["versao_aceita"] == termos.VERSAO_ATUAL and s["aceitos_em"]
    assert p.get("/api/descobrir").status_code == 200
    assert p.delete("/api/conta").status_code == 204


def test_versao_nova_pede_aceite_de_novo(pessoa, monkeypatch):
    p = pessoa()
    assert p.get("/api/descobrir").status_code == 200
    monkeypatch.setattr(termos, "VERSAO_ATUAL", "2099-01-01")
    assert p.get("/api/descobrir").json()["detail"] == termos.DETALHE_PENDENTE
    assert p.get("/api/termos/situacao").json()["versao_aceita"] != "2099-01-01"
    p.post("/api/termos/aceitar", json={"versao": "2099-01-01"})
    assert p.get("/api/descobrir").status_code == 200


def test_termos_vem_antes_da_idade(sem_aceite, pessoa, monkeypatch):
    from app import idade

    monkeypatch.setattr(idade, "obrigatoria", lambda: True)
    p = pessoa()
    assert p.get("/api/descobrir").json()["detail"] == termos.DETALHE_PENDENTE
    p.post("/api/termos/aceitar", json={"versao": termos.VERSAO_ATUAL})
    assert p.get("/api/descobrir").json()["detail"] == idade.DETALHE_PENDENTE


def test_preferencias_modo_discreto(pessoa, db):
    p = pessoa()
    assert p.get("/api/conta/preferencias").json() == {"modo_discreto": False}
    assert p.put("/api/conta/preferencias", json={"modo_discreto": True}).json() == {"modo_discreto": True}
    assert db.fetchval("SELECT modo_discreto FROM contas WHERE id = $1::uuid", p.id) is True
    assert p.put("/api/conta/preferencias", json={"modo_discreto": "talvez"}).status_code == 422


@pytest.mark.parametrize("pagina", ["termos.html", "privacidade.html"])
def test_paginas_legais_honestas_e_na_versao_atual(pagina):
    texto = (ESTATICO / pagina).read_text()
    assert f'data-versao="{termos.VERSAO_ATUAL}"' in texto
    minusculo = texto.lower()
    # Regras do plano: nunca PROMETER anonimato total nem criptografia de ponta a ponta. Citar
    # para negar ("não é de ponta a ponta", "nenhum sistema garante anonimato absoluto") é honesto.
    for termo in ("100% anônim", "anonimato total", "totalmente anônim", "anonimato absoluto", "ponta a ponta"):
        for frase in re.findall(rf"[^.:]*{re.escape(termo)}[^.]*", minusculo):
            assert re.search(r"\b(não|nenhum|nunca)\b", frase), f"promessa sem negação: {frase!r}"
    # Sem recursos de terceiros (a CSP bloquearia e seria rastreamento)
    assert not re.search(r'(src|href)="https?://', texto)
