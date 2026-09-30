"""WebSocket de avisos: autenticado, só da origem do app, e sem conteúdo."""

import asyncio
import json
import uuid
from uuid import UUID

import asyncpg
import pytest
from starlette.websockets import WebSocketDisconnect

from app.tempo_real import MAX_CONEXOES_POR_CONTA, Central, central, codificar_evento, decodificar_evento
from tests.conftest import URL


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


# ---------- vários processos: LISTEN/NOTIFY ----------

CONTA = uuid.UUID("11111111-1111-4111-8111-111111111111")
CONVERSA = uuid.UUID("22222222-2222-4222-8222-222222222222")


def test_evento_ida_e_volta_so_com_ids():
    carga = codificar_evento("abc", "avisar", CONTA, "mensagem", CONVERSA)
    assert json.loads(carga) == {"o": "abc", "a": "avisar", "c": str(CONTA), "t": "mensagem", "v": str(CONVERSA)}
    assert decodificar_evento(carga) == {
        "origem": "abc",
        "acao": "avisar",
        "conta": CONTA,
        "tipo": "mensagem",
        "conversa": CONVERSA,
    }
    assert decodificar_evento(codificar_evento("abc", "derrubar", CONTA)) == {
        "origem": "abc",
        "acao": "derrubar",
        "conta": CONTA,
    }


@pytest.mark.parametrize(
    "args",
    [
        ("abc", "apagar", CONTA),  # ação desconhecida
        ("abc", "avisar", CONTA, "texto", CONVERSA),  # tipo desconhecido
        ("abc", "avisar", CONTA, "mensagem", None),  # aviso sem conversa
        ("abc", "avisar", CONTA, None, CONVERSA),
    ],
)
def test_evento_invalido_nem_e_publicado(args):
    with pytest.raises(ValueError):
        codificar_evento(*args)


@pytest.mark.parametrize(
    "carga",
    [
        "",
        "nao-e-json",
        "[]",
        "null",
        '{"o":"x","a":"avisar","c":"nao-e-uuid","t":"mensagem","v":"' + str(CONVERSA) + '"}',
        '{"o":"x","a":"avisar","c":"' + str(CONTA) + '","t":"conteudo","v":"' + str(CONVERSA) + '"}',
        '{"o":"x","a":"avisar","c":"' + str(CONTA) + '"}',
        '{"o":1,"a":"derrubar","c":"' + str(CONTA) + '"}',
        '{"o":"x","a":"formatar-disco","c":"' + str(CONTA) + '"}',
    ],
)
def test_evento_malformado_e_ignorado(carga):
    assert decodificar_evento(carga) is None


class _CanalFalso:
    """Faz o papel do WebSocket de um aparelho."""

    def __init__(self):
        self.recebidos, self.fechado_com = [], None

    async def send_json(self, dados):
        self.recebidos.append(dados)

    async def close(self, code):
        self.fechado_com = code


async def _esperar(condicao, limite_s=3.0):
    for _ in range(int(limite_s / 0.02)):
        if condicao():
            return True
        await asyncio.sleep(0.02)
    return False


def test_aviso_e_derrubada_chegam_a_outro_processo(client):
    """Dois workers = duas Centrais. Quem está no worker B recebe o que foi publicado no A."""

    async def cenario():
        pool = await asyncpg.create_pool(URL, min_size=1, max_size=2)
        a, b = Central(), Central()
        await a.ligar(URL)
        await b.ligar(URL)
        try:
            canal_b, canal_a = _CanalFalso(), _CanalFalso()
            assert b.entrar(CONTA, canal_b)
            outra = uuid.uuid4()
            assert a.entrar(outra, canal_a)

            await a.avisar(CONTA, "mensagem", CONVERSA)
            assert await _esperar(lambda: canal_b.recebidos)
            assert canal_b.recebidos == [{"tipo": "mensagem", "conversa": str(CONVERSA)}]

            # O próprio processo não entrega duas vezes (local + o eco do NOTIFY)
            await a.avisar(outra, "lida", CONVERSA)
            await asyncio.sleep(0.5)
            assert canal_a.recebidos == [{"tipo": "lida", "conversa": str(CONVERSA)}]

            # "Sair de todos os dispositivos" num worker fecha o canal no outro
            await a.derrubar(CONTA)
            assert await _esperar(lambda: canal_b.fechado_com == 4401)
            assert b.conectados(CONTA) == 0
        finally:
            await a.desligar()
            await b.desligar()
            await pool.close()

    asyncio.run(cenario())


def test_sem_banco_continua_entregando_localmente(client):
    async def cenario():
        central = Central()
        canal = _CanalFalso()
        central.entrar(CONTA, canal)
        await central.avisar(CONTA, "prazo", CONVERSA)  # sem ligar(): nada publicado, nada quebra
        assert await _esperar(lambda: canal.recebidos == [{"tipo": "prazo", "conversa": str(CONVERSA)}])

        # Banco inacessível: o ouvinte não conecta, publicar falha em silêncio e o local funciona
        await central.ligar("postgresql://ninguem:errado@127.0.0.1:1/nada")
        await central.avisar(CONTA, "lida", CONVERSA)
        assert await _esperar(lambda: canal.recebidos[-1] == {"tipo": "lida", "conversa": str(CONVERSA)})
        await asyncio.sleep(0.2)  # o envio da fila falha e segue vivo
        assert central._envio is not None and not central._envio.done()
        await central.desligar()

    asyncio.run(cenario())


def test_avisar_nao_trava_quem_segura_a_ultima_conexao_do_pool(client):
    """Regressão (teste de carga, 10,7 mil pessoas): a rota de enviar mensagem segura uma conexão
    do pool e chama avisar(). Se publicar pedisse outra conexão do mesmo pool, 10 envios ao mesmo
    tempo prendiam as 10 conexões de um worker esperando uma 11ª: a API inteira parava."""

    async def cenario():
        pool = await asyncpg.create_pool(URL, min_size=1, max_size=1)
        a, b = Central(), Central()
        await a.ligar(URL)
        await b.ligar(URL)
        try:
            canal = _CanalFalso()
            b.entrar(CONTA, canal)
            async with pool.acquire():  # a rota segura a única conexão do pool
                await asyncio.wait_for(a.avisar(CONTA, "mensagem", CONVERSA), timeout=2)
            assert await _esperar(lambda: canal.recebidos)  # e o aviso chega ao outro processo
        finally:
            await a.desligar()
            await b.desligar()
            await pool.close()

    asyncio.run(cenario())
