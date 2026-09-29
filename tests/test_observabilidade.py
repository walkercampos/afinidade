"""Logs e erros: rastreáveis pelo id da requisição, sem nenhum dado pessoal."""

import json
import logging
import re
import tomllib
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import VERSAO
from app.observabilidade import FormatoJSON, FormatoTexto

RAIZ = Path(__file__).resolve().parent.parent


def test_versao_unica_e_registrada_no_changelog():
    assert tomllib.loads((RAIZ / "pyproject.toml").read_text())["project"]["version"] == VERSAO
    assert f"## [{VERSAO}]" in (RAIZ / "CHANGELOG.md").read_text()


def test_toda_resposta_tem_id_de_requisicao_gerado_pelo_servidor(client):
    r = client.get("/api/saude", headers={"X-Request-ID": "valor-do-cliente\ninjetado"})
    assert re.fullmatch(r"[0-9a-f]{16}", r.headers["X-Request-ID"])
    assert client.get("/api/saude").headers["X-Request-ID"] != r.headers["X-Request-ID"]


def test_log_de_requisicao_sem_dados_pessoais(pessoa, caplog):
    alvo = pessoa()
    eu = pessoa()
    with caplog.at_level(logging.INFO, logger="matchmaking.http"):
        eu.post(f"/api/perfis/{alvo.id}/curtir")
        eu.get("/api/descobrir", params={"limite": 5})
    registros = [r for r in caplog.records if r.name == "matchmaking.http"]
    rotas = {r.rota for r in registros}
    assert "/api/perfis/{alvo}/curtir" in rotas  # a rota-modelo, não o id da pessoa
    tudo = " ".join(json.dumps(vars(r), default=str) for r in registros)
    for proibido in (alvo.id, eu.id, alvo.email, eu.email, "testclient", "limite=5"):
        assert proibido not in tudo


def test_erro_500_nao_vaza_detalhes_e_informa_o_id(client, caplog):
    def explodir():
        raise RuntimeError("segredo interno: senha=hunter2")

    rotas = client.app.router.routes
    rotas.insert(0, APIRoute("/api/_teste_erro", explodir))
    try:
        with caplog.at_level(logging.ERROR, logger="matchmaking.http"):
            r = TestClient(client.app, raise_server_exceptions=False).get("/api/_teste_erro")
    finally:
        rotas.pop(0)
    assert r.status_code == 500
    corpo = r.json()
    assert "segredo" not in r.text and "RuntimeError" not in r.text
    assert corpo["requisicao"] == r.headers["X-Request-ID"]
    # O detalhe completo fica no log, achável pelo mesmo id
    erro = next(x for x in caplog.records if getattr(x, "requisicao", None) == corpo["requisicao"])
    assert "segredo interno" in FormatoJSON().format(erro)


def test_formato_json_uma_linha_por_evento():
    registro = logging.LogRecord("matchmaking.http", logging.INFO, "", 0, "requisição", None, None)
    registro.rota, registro.status = "/api/perfil", 200
    linha = FormatoJSON().format(registro)
    assert "\n" not in linha
    assert json.loads(linha) | {"quando": None} == {
        "quando": None,
        "nivel": "INFO",
        "origem": "matchmaking.http",
        "mensagem": "requisição",
        "rota": "/api/perfil",
        "status": 200,
    }


def test_formato_texto_mostra_os_campos():
    registro = logging.LogRecord("matchmaking.http", logging.INFO, "", 0, "requisição", None, None)
    registro.rota, registro.status, registro.ms = "/api/perfil", 200, 3.2
    assert FormatoTexto().format(registro) == "INFO matchmaking.http: requisição rota=/api/perfil status=200 ms=3.2"
