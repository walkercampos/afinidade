"""Rate limiting em memória, sem Redis (custo zero) e sem guardar IPs.

A chave é um HMAC do IP com um sal aleatório que só existe na memória do processo e é
trocado a cada hora: nem um dump da memória permite reconstruir IPs de horas anteriores.
Limitação: vale por processo. Com várias réplicas, troque por Redis ou limite no proxy.
"""
import hashlib
import hmac
import secrets
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

JANELA_S = 60
ROTACAO_SAL_S = 3600


class Limitador:
    def __init__(self, relogio=time.monotonic):
        self._relogio = relogio
        # (escopo, chave, fim_da_janela) -> contagem
        self._contagens: dict[tuple[str, str, float], int] = defaultdict(int)
        self._sal = secrets.token_bytes(32)
        self._sal_desde = relogio()

    def _chave(self, identificador: str) -> str:
        agora = self._relogio()
        if agora - self._sal_desde > ROTACAO_SAL_S:
            self._sal, self._sal_desde = secrets.token_bytes(32), agora
        return hmac.new(self._sal, identificador.encode(), hashlib.sha256).hexdigest()[:32]

    def permitir(self, escopo: str, identificador: str, limite: int, janela_s: int = JANELA_S,
                 anonimizar: bool = True) -> bool:
        """`anonimizar=False` só para identificadores que não são dados pessoais de rede (ex.: o
        UUID da conta). Necessário em janelas maiores que a rotação do sal, que as zeraria."""
        agora = self._relogio()
        fim = (agora // janela_s + 1) * janela_s
        if len(self._contagens) > 50_000:  # descarta janelas já encerradas
            self._contagens = defaultdict(int, {k: v for k, v in self._contagens.items() if k[2] > agora})
        k = (escopo, self._chave(identificador) if anonimizar else identificador, fim)
        self._contagens[k] += 1
        return self._contagens[k] <= limite


def ip_do_cliente(request: Request) -> str:
    return request.client.host if request.client else "desconhecido"


def exigir_limite(escopo: str, limite: int, identificador: str, janela_s: int = JANELA_S,
                  anonimizar: bool = True) -> None:
    if not limitador.permitir(escopo, identificador, limite, janela_s, anonimizar):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitas tentativas. Aguarde e tente de novo.")


limitador = Limitador()
