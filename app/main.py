"""Montagem da aplicação: ciclo de vida, cabeçalhos de segurança, rotas e front-end.

Regras de negócio NÃO moram aqui — veja CONTRIBUTING.md para o mapa das camadas.
"""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.staticfiles import StaticFiles

from . import mensagens, verificacao
from . import passkeys as dominio_passkeys
from .config import config
from .cripto import Cifrador
from .db import criar_pool, migrar
from .email import criar_carteiro
from .routes import auth, chat, descoberta, fotos, moderacao, passkeys, perfil, saude

log = logging.getLogger("matchmaking")
DIR_STATIC = Path(__file__).resolve().parent.parent / "static"
# Mais curto que os 5 min de vida das mensagens lidas; a API já esconde as expiradas
# no instante exato, esta limpeza só remove fisicamente do banco.
INTERVALO_LIMPEZA_S = 30

_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
    "font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)


async def _limpeza_periodica(app: FastAPI) -> None:
    while True:
        try:
            async with app.state.pool.acquire() as con:
                await mensagens.apagar_expiradas(con, config().mensagens_retencao_dias)
                await dominio_passkeys.apagar_desafios_expirados(con)
                await verificacao.apagar_expiradas(con)
        except Exception:  # a limpeza nunca deve derrubar a API; tenta de novo no próximo ciclo
            log.exception("Falha na limpeza periódica")
        await asyncio.sleep(INTERVALO_LIMPEZA_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = config()
    app.state.pool = await criar_pool(cfg.database_url)
    app.state.cifrador = Cifrador(cfg.chave_mensagens)
    app.state.carteiro = criar_carteiro(cfg.email)
    novas = await migrar(app.state.pool)
    if novas:
        log.info("Migrações aplicadas: %s", ", ".join(novas))
    tarefa = asyncio.create_task(_limpeza_periodica(app))
    yield
    tarefa.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await tarefa
    await app.state.pool.close()


def criar_app() -> FastAPI:
    cfg = config()
    # Em produção a documentação interativa fica desligada: menos superfície exposta.
    docs = {} if not cfg.producao else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title="Afinidade API", version="0.3.0", lifespan=lifespan, **docs)

    @app.middleware("http")
    async def cabecalhos_de_seguranca(request: Request, call_next):
        response = await call_next(request)
        h = response.headers
        # /docs (só em dev) carrega Swagger de CDN e não funcionaria com a CSP estrita.
        if not request.url.path.startswith(("/docs", "/redoc")):
            h["Content-Security-Policy"] = _CSP
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "no-referrer"
        h["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=(), payment=(), interest-cohort=()"
        h["Cross-Origin-Opener-Policy"] = "same-origin"
        h["Cross-Origin-Resource-Policy"] = "same-origin"
        # no-store em tudo (API e páginas): nada do app fica no cache do navegador, e o
        # "voltar" depois do botão de pânico não reabre a última tela.
        h["Cache-Control"] = "no-store"
        if cfg.producao:
            h["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    api = APIRouter(prefix="/api")
    for modulo in (saude, auth, passkeys, perfil, descoberta, fotos, chat, moderacao):
        api.include_router(modulo.router)
    app.include_router(api)
    # Front-end estático no mesmo domínio: sem CORS, e o cookie SameSite=Strict funciona.
    app.mount("/", StaticFiles(directory=DIR_STATIC, html=True), name="static")
    return app


app = criar_app()
