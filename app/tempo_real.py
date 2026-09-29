"""Avisos em tempo real por WebSocket: "chegou algo novo na conversa X".

O canal NUNCA leva conteúdo (nem texto, nem nome, nem prazo): só o tipo do aviso e o id da
conversa. O cliente então busca pela API normal, que aplica todas as regras (conexão, bloqueio,
prazo). Assim o WebSocket não abre nenhum caminho novo para dados.

Limitação conhecida: o registro de quem está conectado fica na memória do processo. Com mais de
uma réplica, o aviso só chega a quem estiver conectado na mesma réplica; o cliente continua
buscando de tempos em tempos, então nada se perde, só atrasa. Para várias réplicas, troque por
um pub/sub (ex.: LISTEN/NOTIFY do PostgreSQL).
"""

import asyncio
import contextlib
from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket

MAX_CONEXOES_POR_CONTA = 5


class Central:
    def __init__(self) -> None:
        self._conexoes: dict[UUID, set[WebSocket]] = defaultdict(set)

    def entrar(self, conta: UUID, ws: WebSocket) -> bool:
        if len(self._conexoes[conta]) >= MAX_CONEXOES_POR_CONTA:
            return False
        self._conexoes[conta].add(ws)
        return True

    def sair(self, conta: UUID, ws: WebSocket) -> None:
        self._conexoes[conta].discard(ws)
        if not self._conexoes[conta]:
            del self._conexoes[conta]

    def conectados(self, conta: UUID) -> int:
        return len(self._conexoes.get(conta, ()))

    async def avisar(self, conta: UUID, tipo: str, conversa: UUID) -> None:
        """Manda o aviso para todos os aparelhos conectados da conta. Falhas são ignoradas:
        o cliente sempre tem a busca periódica como reserva."""
        for ws in list(self._conexoes.get(conta, ())):
            with contextlib.suppress(Exception):
                await asyncio.wait_for(ws.send_json({"tipo": tipo, "conversa": str(conversa)}), timeout=2)

    async def derrubar(self, conta: UUID) -> None:
        """Fecha os canais da conta (sair de todos os dispositivos, exclusão, banimento)."""
        for ws in self._conexoes.pop(conta, set()):
            with contextlib.suppress(Exception):
                await ws.close(code=4401)


central = Central()
