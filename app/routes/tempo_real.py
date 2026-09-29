import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import config
from ..security import COOKIE_SESSAO, validar_token
from ..tempo_real import central

router = APIRouter(tags=["tempo real"])

# De quanto em quanto tempo a sessão é conferida de novo (sair, exclusão, banimento, expiração).
REVALIDAR_S = 60


@router.websocket("/ws")
async def canal(ws: WebSocket):
    """Avisos de "algo novo na conversa X". Só avisos: o conteúdo vem sempre pela API.

    Autenticação: o mesmo cookie de sessão do site (ou `Authorization: Bearer` em clientes de
    API). A origem é conferida contra as origens do app: impede que outro site abra o canal
    em nome da pessoa (cross-site WebSocket hijacking).
    """
    origem = ws.headers.get("origin")
    if origem is not None and origem.rstrip("/") not in config().webauthn_origens:
        await ws.close(code=4403)
        return
    autorizacao = ws.headers.get("authorization", "")
    token = autorizacao[7:] if autorizacao.lower().startswith("bearer ") else ws.cookies.get(COOKIE_SESSAO)
    pool = ws.app.state.pool
    sessao = await validar_token(pool, token) if token else None
    if sessao is None:
        await ws.close(code=4401)
        return

    await ws.accept()
    if not central.entrar(sessao.conta_id, ws):
        await ws.close(code=4429)  # aparelhos demais conectados
        return
    try:
        while True:
            try:
                # O cliente não precisa mandar nada; o que chegar é ignorado (serve de "ping").
                await asyncio.wait_for(ws.receive_text(), timeout=REVALIDAR_S)
            except TimeoutError:
                if await validar_token(pool, token) is None:
                    await ws.close(code=4401)
                    return
    except WebSocketDisconnect:
        pass
    finally:
        central.sair(sessao.conta_id, ws)
