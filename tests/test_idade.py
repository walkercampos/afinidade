"""Parte 3: verificação de idade (só o resultado é guardado)."""

import pytest

from app import idade


@pytest.fixture
def obrigatoria(monkeypatch):
    monkeypatch.setattr(idade, "obrigatoria", lambda: True)


def _verificar(db, p):
    db.execute("UPDATE contas SET idade_verificada_em = now(), idade_provedor = 'simulado' WHERE id = $1::uuid", p.id)


def _sessao(url: str) -> str:
    assert url.startswith("/#/idade-simulada/")
    return url.rsplit("/", 1)[1]


@pytest.mark.parametrize(
    ("producao", "obrig", "provedor", "erro"),
    [
        (True, True, "desativado", "obrigatória em produção"),
        (True, False, "simulado", "não é permitido em produção"),
        (False, False, "inexistente", "desconhecido"),
    ],
)
def test_configuracao_perigosa_impede_o_app_de_subir(producao, obrig, provedor, erro):
    with pytest.raises(RuntimeError, match=erro):
        idade.validar_configuracao(producao, obrig, provedor)


@pytest.mark.parametrize(
    ("producao", "obrig", "provedor"),
    [(True, False, "desativado"), (False, True, "simulado"), (False, False, "desativado")],
)
def test_configuracoes_aceitas(producao, obrig, provedor):
    idade.validar_configuracao(producao, obrig, provedor)


def test_sem_verificacao_so_cria_o_perfil(obrigatoria, pessoa):
    p = pessoa()
    assert p.get("/api/perfil").status_code == 200  # o perfil pode ser montado antes
    r = p.get("/api/descobrir")
    assert r.status_code == 403 and r.json()["detail"] == idade.DETALHE_PENDENTE
    assert p.get("/api/idade").json() | {"verificada_em": None} == {
        "obrigatoria": True,
        "verificada": False,
        "verificada_em": None,
        "pendente": False,
        "disponivel": True,
    }


def test_fluxo_completo_com_o_provedor_simulado(obrigatoria, pessoa, db):
    p = pessoa()
    sessao = _sessao(p.post("/api/idade/iniciar").json()["url"])
    assert p.get("/api/idade").json()["pendente"] is True
    # O id da sessão nunca é gravado em claro
    assert (
        db.fetchval(
            "SELECT count(*) FROM verificacoes_idade WHERE position($1::bytea in sessao_hash) > 0", sessao.encode()
        )
        == 0
    )

    assert p.post(f"/api/idade/simulado/{sessao}", json={"aprovar": True}).status_code == 204
    s = p.get("/api/idade").json()
    assert s["verificada"] is True and s["pendente"] is False
    assert p.get("/api/descobrir").status_code == 200
    # A mesma sessão não serve duas vezes, e verificar de novo não faz sentido
    assert p.post(f"/api/idade/simulado/{sessao}", json={"aprovar": True}).status_code == 404
    assert p.post("/api/idade/iniciar").status_code == 409
    linha = db.fetchrow("SELECT idade_provedor, idade_verificada_em FROM contas WHERE id = $1::uuid", p.id)
    assert linha["idade_provedor"] == "simulado" and linha["idade_verificada_em"] is not None


def test_recusada_expirada_e_de_outra_pessoa(obrigatoria, pessoa, db):
    p, intrusa = pessoa(), pessoa()
    s1 = _sessao(p.post("/api/idade/iniciar").json()["url"])
    # Outra conta não consegue concluir a tentativa de p
    assert intrusa.post(f"/api/idade/simulado/{s1}", json={"aprovar": True}).status_code == 404
    assert p.post(f"/api/idade/simulado/{s1}", json={"aprovar": False}).status_code == 204
    assert p.get("/api/idade").json()["verificada"] is False

    # Tentativa com mais de 1 hora: o retorno é ignorado
    s2 = _sessao(p.post("/api/idade/iniciar").json()["url"])
    db.execute("UPDATE verificacoes_idade SET criado_em = now() - interval '61 minutes' WHERE situacao = 'pendente'")
    assert p.post(f"/api/idade/simulado/{s2}", json={"aprovar": True}).status_code == 404

    # Uma tentativa nova invalida a anterior
    s3 = _sessao(p.post("/api/idade/iniciar").json()["url"])
    _s4 = _sessao(p.post("/api/idade/iniciar").json()["url"])
    assert p.post(f"/api/idade/simulado/{s3}", json={"aprovar": True}).status_code == 404


def test_quem_nao_verificou_nao_aparece_para_ninguem(obrigatoria, pessoa, db):
    eu = pessoa("homem-cis", ["mulher-cis"], quero=["leather"])
    verificada = pessoa("mulher-cis", ["homem-cis"], quero=["leather"])
    pendente = pessoa("mulher-cis", ["homem-cis"], quero=["leather"])
    _verificar(db, eu)
    _verificar(db, verificada)
    vistos = {c["perfil"]["id"] for c in eu.get("/api/descobrir", params={"limite": 100}).json()}
    assert verificada.id in vistos and pendente.id not in vistos
    assert eu.get(f"/api/perfis/{pendente.id}").status_code == 404
    assert eu.post(f"/api/perfis/{pendente.id}/curtir").status_code == 404


def test_limite_de_tentativas_por_dia(obrigatoria, pessoa):
    p = pessoa()
    for _ in range(5):
        assert p.post("/api/idade/iniciar").status_code == 200
    assert p.post("/api/idade/iniciar").status_code == 429


def test_rota_simulada_nao_existe_com_provedor_real(pessoa, monkeypatch):
    import dataclasses

    from app import config as modulo_config
    from app.routes import idade as rotas

    p = pessoa()
    falsa = dataclasses.replace(modulo_config.config(), idade_provedor="desativado")
    monkeypatch.setattr(rotas, "config", lambda: falsa)
    assert p.post("/api/idade/simulado/qualquer", json={"aprovar": True}).status_code == 404
