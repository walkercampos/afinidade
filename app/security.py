from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import idade, termos
from .config import config
from .ratelimit import exigir_limite

COOKIE_SESSAO = "sessao"
# Header que o front envia em toda requisição que altera dados. Um site de terceiros não
# consegue enviá-lo sem um preflight CORS, que esta API nunca aprova (defesa extra contra
# CSRF, somada ao SameSite=Strict do cookie).
HEADER_CSRF = "X-CSRF"
_METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


def emitir_token(conta_id: UUID, versao: int, segredo: str, expira_min: int) -> str:
    agora = datetime.now(UTC)
    payload = {"sub": str(conta_id), "ver": versao, "iat": agora, "exp": agora + timedelta(minutes=expira_min)}
    return jwt.encode(payload, segredo, algorithm="HS256")


def iniciar_sessao(response: Response, conta_id: UUID, versao: int, handle: str, *, novo: bool = False) -> dict:
    """Emite o token, grava o cookie HttpOnly e devolve o corpo da resposta de login.
    `novo` avisa o front que a conta acabou de ser criada (hora de oferecer a biometria)."""
    cfg = config()
    token = emitir_token(conta_id, versao, cfg.jwt_secret, cfg.jwt_expira_min)
    gravar_cookie_sessao(response, token, cfg)
    return {"access_token": token, "token_type": "bearer", "handle": handle, "novo": novo}


def gravar_cookie_sessao(response: Response, token: str, config) -> None:
    response.set_cookie(
        COOKIE_SESSAO,
        token,
        max_age=config.jwt_expira_min * 60,
        path="/api",
        httponly=True,
        secure=config.producao,
        samesite="strict",
    )


def apagar_cookie_sessao(response: Response, config) -> None:
    response.delete_cookie(COOKIE_SESSAO, path="/api", httponly=True, secure=config.producao, samesite="strict")


@dataclass(frozen=True)
class Sessao:
    conta_id: UUID
    papel: str  # 'usuario' | 'moderador'
    situacao: str  # 'ativa' | 'em_revisao' (banida nunca chega aqui)
    idade_verificada: bool = False
    termos_aceitos: bool = False


_bearer = HTTPBearer(auto_error=False)


async def sessao_atual(request: Request, cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Sessao:
    """Aceita Bearer (clientes de API) ou o cookie HttpOnly (front-end web)."""
    nao_autorizado = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada")
    if cred is not None:
        token = cred.credentials
    else:
        token = request.cookies.get(COOKIE_SESSAO)
        if token and request.method not in _METODOS_SEGUROS and request.headers.get(HEADER_CSRF) != "1":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Header anti-CSRF ausente")
    sessao = await validar_token(request.app.state.pool, token) if token else None
    if sessao is None:
        raise nao_autorizado
    exigir_limite("api", config().limite_api_por_min, str(sessao.conta_id), anonimizar=False)
    return sessao


async def validar_token(pool, token: str) -> Sessao | None:
    """Sessão do token, ou None se for inválido, expirado, revogado ou de conta banida.
    Usado pelas rotas HTTP e pelo WebSocket."""
    try:
        payload = jwt.decode(
            token, config().jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub", "ver"]}
        )
        conta_id = UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        return None
    # A versão do token permite "sair de todos os dispositivos" e invalida na hora tokens de
    # contas excluídas ou banidas, em vez de esperar a expiração.
    conta = await pool.fetchrow(
        """SELECT token_versao, papel, situacao, idade_verificada_em IS NOT NULL AS idade_ok,
                  termos_versao = $2 AS termos_ok
           FROM contas WHERE id = $1""",
        conta_id,
        termos.VERSAO_ATUAL,
    )
    if conta is None or conta["token_versao"] != payload["ver"] or conta["situacao"] == "banida":
        return None
    return Sessao(conta_id, conta["papel"], conta["situacao"], conta["idade_ok"], bool(conta["termos_ok"]))


async def conta_atual(sessao: Sessao = Depends(sessao_atual)) -> UUID:
    return sessao.conta_id


async def conta_ativa(sessao: Sessao = Depends(sessao_atual)) -> UUID:
    """Para ações que alcançam outras pessoas (curtir, enviar mensagem): bloqueadas enquanto
    a conta estiver em revisão por denúncias."""
    if sessao.situacao != "ativa":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Conta em revisão pela moderação")
    return sessao.conta_id


def exigir_liberada(sessao: Sessao) -> UUID:
    """Conta ativa, com a versão atual dos termos aceita e, quando a verificação de idade é
    obrigatória, com a idade verificada. Nessa ordem: os termos vêm antes da verificação."""
    if sessao.situacao != "ativa":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Conta em revisão pela moderação")
    if not sessao.termos_aceitos:
        raise HTTPException(status.HTTP_403_FORBIDDEN, termos.DETALHE_PENDENTE)
    if not sessao.idade_verificada and idade.obrigatoria():
        raise HTTPException(status.HTTP_403_FORBIDDEN, idade.DETALHE_PENDENTE)
    return sessao.conta_id


async def conta_liberada(sessao: Sessao = Depends(sessao_atual)) -> UUID:
    """Para ver perfis, curtir e conversar (Parte 3)."""
    return exigir_liberada(sessao)


async def moderador(sessao: Sessao = Depends(sessao_atual)) -> UUID:
    if sessao.papel != "moderador":
        # 404 em vez de 403: não revela que a rota existe.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    return sessao.conta_id
