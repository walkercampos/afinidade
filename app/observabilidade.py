"""Logs estruturados e identificador de requisição, sem dados pessoais.

O que um log de requisição contém: método, ROTA-MODELO (ex.: /api/perfis/{perfil_id}/curtir,
nunca o id real), status, duração e um id aleatório da requisição. O que nunca contém: IP,
conta, e-mail, query string, corpo, cabeçalhos ou coordenadas.

O id da requisição volta no cabeçalho `X-Request-ID` e no corpo dos erros 500, para a pessoa
informar ao suporte e o time achar o erro no log sem precisar de nenhum dado dela.
"""

import json
import logging
import secrets
import sys
import time

from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger("matchmaking.http")


class FormatoJSON(logging.Formatter):
    """Uma linha JSON por evento: fácil de filtrar no painel do Render ou em qualquer coletor."""

    CAMPOS_EXTRAS = ("requisicao", "metodo", "rota", "status", "ms")

    def format(self, registro: logging.LogRecord) -> str:
        dados = {
            "quando": self.formatTime(registro, "%Y-%m-%dT%H:%M:%S%z"),
            "nivel": registro.levelname,
            "origem": registro.name,
            "mensagem": registro.getMessage(),
        }
        dados.update({c: getattr(registro, c) for c in self.CAMPOS_EXTRAS if hasattr(registro, c)})
        if registro.exc_info:
            dados["erro"] = self.formatException(registro.exc_info)
        return json.dumps(dados, ensure_ascii=False)


class FormatoTexto(logging.Formatter):
    """Desenvolvimento: uma linha legível, com os mesmos campos do JSON no fim."""

    def format(self, registro: logging.LogRecord) -> str:
        extras = " ".join(f"{c}={getattr(registro, c)}" for c in FormatoJSON.CAMPOS_EXTRAS if hasattr(registro, c))
        linha = f"{registro.levelname} {registro.name}: {registro.getMessage()}" + (f" {extras}" if extras else "")
        if registro.exc_info:
            linha += "\n" + self.formatException(registro.exc_info)
        return linha


def configurar_logs(producao: bool) -> None:
    """Produção: JSON em stdout. Desenvolvimento: texto legível."""
    raiz = logging.getLogger("matchmaking")
    if raiz.handlers:  # já configurado (ex.: testes criando o app mais de uma vez)
        return
    saida = logging.StreamHandler(sys.stdout)
    saida.setFormatter(FormatoJSON() if producao else FormatoTexto())
    raiz.addHandler(saida)
    raiz.setLevel(logging.INFO)
    raiz.propagate = False


def novo_id() -> str:
    return secrets.token_hex(8)


def rota_modelo(request: Request) -> str:
    """A rota com os parâmetros no lugar dos valores; fora da API, só "estatico"."""
    if not request.url.path.startswith("/api"):
        return "estatico"
    caminho = getattr(request.scope.get("route"), "path", None)
    if caminho is None:
        return "desconhecida"  # 404: não registra o caminho digitado, que pode conter qualquer coisa
    # As rotas moram num APIRouter com prefixo /api, e o Starlette guarda o caminho sem ele.
    return caminho if caminho.startswith("/api") else "/api" + caminho


async def registrar_requisicao(request: Request, call_next):
    """Middleware: cria o id, mede a duração e registra só as requisições da API."""
    # O id é sempre gerado aqui: um valor vindo do cliente poderia ser usado para
    # correlacionar a pessoa entre requisições ou injetar texto no log.
    request.state.requisicao = novo_id()
    inicio = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.requisicao
    if request.url.path.startswith("/api") and request.url.path != "/api/saude":
        log.info(
            "requisição",
            extra={
                "requisicao": request.state.requisicao,
                "metodo": request.method,
                "rota": rota_modelo(request),
                "status": response.status_code,
                "ms": round((time.perf_counter() - inicio) * 1000, 1),
            },
        )
    return response


async def erro_inesperado(request: Request, erro: Exception) -> JSONResponse:
    """Erro 500 sem detalhes internos para o cliente; o detalhe completo vai só para o log."""
    requisicao = getattr(request.state, "requisicao", None) or novo_id()
    log.error(
        "erro inesperado",
        exc_info=erro,
        extra={"requisicao": requisicao, "metodo": request.method, "rota": rota_modelo(request), "status": 500},
    )
    return JSONResponse(
        {"detail": "Algo deu errado do nosso lado. Tente de novo em instantes.", "requisicao": requisicao},
        status_code=500,
        headers={"X-Request-ID": requisicao, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
