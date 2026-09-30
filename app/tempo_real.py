"""Avisos em tempo real por WebSocket: "chegou algo novo na conversa X".

O canal NUNCA leva conteúdo (nem texto, nem nome, nem prazo): só o tipo do aviso e o id da
conversa. O cliente então busca pela API normal, que aplica todas as regras (conexão, bloqueio,
prazo). Assim o WebSocket não abre nenhum caminho novo para dados.

Vários processos (workers ou réplicas): cada um guarda na memória só os canais abertos nele.
Para o aviso chegar a quem está em outro processo, ele também é publicado no PostgreSQL
(LISTEN/NOTIFY, sem custo extra): todo processo escuta e entrega aos seus canais. O que é
publicado segue a mesma regra: só ids e o tipo, nunca conteúdo. Se o banco ficar fora, cada
processo continua entregando localmente e o cliente tem a busca periódica como reserva.
"""

import asyncio
import contextlib
import json
import logging
import secrets
from collections import defaultdict
from uuid import UUID

import asyncpg
from fastapi import WebSocket

MAX_CONEXOES_POR_CONTA = 5
CANAL_PG = "afinidade_avisos"
TIPOS = {"mensagem", "lida", "prazo"}
ACOES = {"avisar", "derrubar"}
RECONECTAR_S = 5
FILA_MAX = 10_000  # avisos esperando publicação; acima disso são descartados (a busca periódica cobre)
LOTE_MAX = 500  # avisos por ida ao banco

log = logging.getLogger("afinidade.tempo_real")


def codificar_evento(origem: str, acao: str, conta: UUID, tipo: str | None = None, conversa: UUID | None = None) -> str:
    """Carga do NOTIFY. Só ids e o tipo; nunca conteúdo."""
    if acao not in ACOES or (acao == "avisar" and (tipo not in TIPOS or conversa is None)):
        raise ValueError("evento inválido")
    evento = {"o": origem, "a": acao, "c": str(conta)}
    if acao == "avisar":
        evento |= {"t": tipo, "v": str(conversa)}
    return json.dumps(evento, separators=(",", ":"))


def decodificar_evento(carga: str) -> dict | None:
    """Evento validado, ou None se a carga for malformada (é ignorada, nunca derruba o processo)."""
    try:
        bruto = json.loads(carga)
        acao = bruto["a"]
        if acao not in ACOES or not isinstance(bruto["o"], str):
            return None
        evento = {"origem": bruto["o"], "acao": acao, "conta": UUID(bruto["c"])}
        if acao == "avisar":
            if bruto["t"] not in TIPOS:
                return None
            evento |= {"tipo": bruto["t"], "conversa": UUID(bruto["v"])}
        return evento
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


class Central:
    def __init__(self) -> None:
        self._conexoes: dict[UUID, set[WebSocket]] = defaultdict(set)
        self.origem = secrets.token_hex(8)  # identifica este processo nos eventos publicados
        self._dsn: str | None = None
        self._ouvinte: asyncpg.Connection | None = None
        self._publicador: asyncpg.Connection | None = None
        self._fila: asyncio.Queue[str] | None = None
        self._vigia: asyncio.Task | None = None
        self._envio: asyncio.Task | None = None
        self._tarefas: set[asyncio.Task] = set()  # referência forte até terminar

    # ---------- canais locais ----------

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

    async def _avisar_local(self, conta: UUID, tipo: str, conversa: UUID) -> None:
        for ws in list(self._conexoes.get(conta, ())):
            with contextlib.suppress(Exception):
                await asyncio.wait_for(ws.send_json({"tipo": tipo, "conversa": str(conversa)}), timeout=2)

    async def _derrubar_local(self, conta: UUID) -> None:
        for ws in self._conexoes.pop(conta, set()):
            with contextlib.suppress(Exception):
                await ws.close(code=4401)

    # ---------- API usada pelas rotas ----------

    async def avisar(self, conta: UUID, tipo: str, conversa: UUID) -> None:
        """Manda o aviso para todos os aparelhos conectados da conta, em qualquer processo.

        Não espera nada: a entrega local vira uma tarefa e a publicação entra numa fila com
        conexão própria. Assim quem envia a mensagem não fica preso a um aparelho lento nem
        disputa o pool de conexões da requisição (isso travava a API sob carga)."""
        if conta in self._conexoes:
            self._agendar(self._avisar_local(conta, tipo, conversa))
        self._publicar(codificar_evento(self.origem, "avisar", conta, tipo, conversa))

    async def derrubar(self, conta: UUID) -> None:
        """Fecha os canais da conta em todos os processos (sair de todos os dispositivos,
        exclusão, banimento). Os locais fecham antes de responder."""
        await self._derrubar_local(conta)
        self._publicar(codificar_evento(self.origem, "derrubar", conta))

    # ---------- LISTEN/NOTIFY ----------

    async def ligar(self, dsn: str) -> None:
        """Passa a publicar e a ouvir eventos dos outros processos. Usa duas conexões próprias,
        fora do pool das requisições."""
        self._dsn = dsn
        self._fila = asyncio.Queue(maxsize=FILA_MAX)
        await self._conectar_ouvinte()
        self._vigia = asyncio.create_task(self._vigiar())
        self._envio = asyncio.create_task(self._enviar_fila())

    async def desligar(self) -> None:
        for tarefa in (self._vigia, self._envio):
            if tarefa:
                tarefa.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await tarefa
        for con in (self._ouvinte, self._publicador):
            if con and not con.is_closed():
                with contextlib.suppress(Exception):
                    await con.close()
        self._ouvinte = self._publicador = self._vigia = self._envio = self._fila = None

    async def _conectar_ouvinte(self) -> None:
        try:
            self._ouvinte = await asyncpg.connect(self._dsn)
            await self._ouvinte.add_listener(CANAL_PG, self._ao_receber)
        except Exception:  # noqa: BLE001 — sem ouvinte, segue só local; o vigia tenta de novo
            log.warning("tempo real: sem conexão para ouvir avisos de outros processos")
            self._ouvinte = None

    async def _vigiar(self) -> None:
        while True:
            await asyncio.sleep(RECONECTAR_S)
            if self._ouvinte is None or self._ouvinte.is_closed():
                await self._conectar_ouvinte()

    def _publicar(self, carga: str) -> None:
        if self._fila is None:
            return
        try:
            self._fila.put_nowait(carga)
        except asyncio.QueueFull:
            log.warning("tempo real: fila de avisos cheia, aviso descartado")

    async def _enviar_fila(self) -> None:
        """Publica em lotes numa conexão própria. Aviso é um extra (a mensagem já foi gravada e o
        cliente busca de tempos em tempos): se o banco falhar, o lote é descartado."""
        while True:
            lote = [await self._fila.get()]
            while len(lote) < LOTE_MAX and not self._fila.empty():
                lote.append(self._fila.get_nowait())
            try:
                if self._publicador is None or self._publicador.is_closed():
                    self._publicador = await asyncpg.connect(self._dsn)
                await self._publicador.execute(
                    "SELECT pg_notify($1, carga) FROM unnest($2::text[]) AS carga", CANAL_PG, lote
                )
            except Exception:  # noqa: BLE001
                log.warning("tempo real: falha ao publicar %d aviso(s)", len(lote))
                self._publicador = None
                await asyncio.sleep(1)

    def _ao_receber(self, _con, _pid, _canal, carga: str) -> None:
        evento = decodificar_evento(carga)
        if evento is None or evento["origem"] == self.origem:
            return  # malformado, ou nosso próprio evento (já entregue localmente)
        if evento["acao"] == "derrubar":
            self._agendar(self._derrubar_local(evento["conta"]))
        elif evento["conta"] in self._conexoes:
            self._agendar(self._avisar_local(evento["conta"], evento["tipo"], evento["conversa"]))

    def _agendar(self, corotina) -> None:
        tarefa = asyncio.get_running_loop().create_task(corotina)
        self._tarefas.add(tarefa)
        tarefa.add_done_callback(self._tarefas.discard)


central = Central()
