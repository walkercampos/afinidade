"""WebSocket de avisos: autenticado, só da origem do app, e sem conteúdo."""

from uuid import UUID

import pytest
from starlette.websockets import WebSocketDisconnect

from app.tempo_real import MAX_CONEXOES_POR_CONTA, central


def _abrir(client, pessoa=None, **headers):
    if pessoa is not None:
        headers.update(pessoa.h)
    return client.websocket_connect("/api/ws", headers=headers)


def test_recusa_sem_sessao_e_de_outro_site(client, pessoa):
    with pytest.raises(WebSocketDisconnect) as erro, _abrir(client):
        pass
    assert erro.value.code == 4401
    with pytest.raises(WebSocketDisconnect) as erro, _abrir(client, Authorization="Bearer invalido"):
        pass
    assert erro.value.code == 4401
    p = pessoa()
    with pytest.raises(WebSocketDisconnect) as erro, _abrir(client, p, origin="https://site-malicioso.example"):
        pass
    assert erro.value.code == 4403


def test_aviso_de_mensagem_sem_conteudo(client, conexao_entre):
    a, b = conexao_entre()
    with _abrir(client, b, origin="http://testserver") as ws:
        assert central.conectados(UUID(b.id)) == 1
        a.post(f"/api/conversas/{b.id}/mensagens", json={"texto": "segredo no aviso?"})
        aviso = ws.receive_json()
        assert aviso == {"tipo": "mensagem", "conversa": a.id}  # nada do texto, nome ou prazo

        a.post(f"/api/conversas/{b.id}/prazo", json={"ttl_minutos": 60})
        assert ws.receive_json() == {"tipo": "prazo", "conversa": a.id}

    # Quem enviou fica sabendo que a mensagem foi lida (a contagem do prazo começou)
    with _abrir(client, a) as ws:
        b.get(f"/api/conversas/{a.id}/mensagens")
        assert ws.receive_json() == {"tipo": "lida", "conversa": b.id}


def test_sair_derruba_o_canal_e_limita_aparelhos(client, pessoa):

    p = pessoa()
    contextos = [_abrir(client, p) for _ in range(MAX_CONEXOES_POR_CONTA)]
    abertos = [c.__enter__() for c in contextos]
    with pytest.raises(WebSocketDisconnect) as erro, _abrir(client, p) as ws:
        ws.receive_json()
    assert erro.value.code == 4429

    assert p.post("/api/auth/sair").status_code == 204
    for ws in abertos:
        with pytest.raises(WebSocketDisconnect) as erro:
            ws.receive_json()
        assert erro.value.code == 4401
    assert central.conectados(UUID(p.id)) == 0
    for c in contextos:
        c.__exit__(None, None, None)


def test_csp_libera_so_o_websocket_do_proprio_app(client):
    from app.main import politica_de_conteudo

    csp = politica_de_conteudo(("https://afinidade.onrender.com", "http://localhost:8000"))
    assert "connect-src 'self' wss://afinidade.onrender.com ws://localhost:8000;" in csp
    assert "script-src 'self';" in csp
