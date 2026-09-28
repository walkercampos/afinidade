import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .ratelimit import exigir_limite

# scrypt da stdlib: sem dependência nativa extra e resistente a força bruta em GPU.
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}

COOKIE_SESSAO = "sessao"
# Header que o front envia em toda requisição que altera dados. Um site de terceiros não
# consegue enviá-lo sem um preflight CORS, que esta API nunca aprova (defesa extra contra
# CSRF, somada ao SameSite=Strict do cookie).
HEADER_CSRF = "X-CSRF"
_METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


def gerar_hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    chave = hashlib.scrypt(senha.encode(), salt=sal, **_SCRYPT)
    return f"scrypt${sal.hex()}${chave.hex()}"


# Usado quando o handle não existe, para que o tempo de resposta do login não revele
# quais handles estão cadastrados.
HASH_FALSO = gerar_hash_senha(secrets.token_urlsafe(16))


def verificar_senha(senha: str, armazenado: str) -> bool:
    try:
        _, sal_hex, chave_hex = armazenado.split("$")
    except ValueError:
        return False
    chave = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal_hex), **_SCRYPT)
    return hmac.compare_digest(chave.hex(), chave_hex)


def emitir_token(conta_id: UUID, versao: int, segredo: str, expira_min: int) -> str:
    agora = datetime.now(timezone.utc)
    payload = {"sub": str(conta_id), "ver": versao, "iat": agora, "exp": agora + timedelta(minutes=expira_min)}
    return jwt.encode(payload, segredo, algorithm="HS256")


def gravar_cookie_sessao(response: Response, token: str, config) -> None:
    response.set_cookie(
        COOKIE_SESSAO, token, max_age=config.jwt_expira_min * 60, path="/api",
        httponly=True, secure=config.producao, samesite="strict",
    )


def apagar_cookie_sessao(response: Response, config) -> None:
    response.delete_cookie(COOKIE_SESSAO, path="/api", httponly=True, secure=config.producao, samesite="strict")


_bearer = HTTPBearer(auto_error=False)


async def conta_atual(request: Request, cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> UUID:
    """Aceita Bearer (clientes de API) ou o cookie HttpOnly (front-end web)."""
    nao_autorizado = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada")
    if cred is not None:
        token = cred.credentials
    else:
        token = request.cookies.get(COOKIE_SESSAO)
        if token and request.method not in _METODOS_SEGUROS and request.headers.get(HEADER_CSRF) != "1":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Header anti-CSRF ausente")
    if not token:
        raise nao_autorizado

    config = request.app.state.config
    try:
        payload = jwt.decode(token, config.jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub", "ver"]})
        conta_id = UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        raise nao_autorizado

    # A versão do token permite "sair de todos os dispositivos" e invalida tokens de
    # contas excluídas imediatamente, em vez de esperar a expiração.
    versao = await request.app.state.pool.fetchval("SELECT token_versao FROM contas WHERE id = $1", conta_id)
    if versao is None or versao != payload["ver"]:
        raise nao_autorizado

    exigir_limite("api", config.limite_api_por_min, str(conta_id))
    return conta_id
