import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# scrypt da stdlib: sem dependência nativa extra e resistente a força bruta em GPU.
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def gerar_hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    chave = hashlib.scrypt(senha.encode(), salt=sal, **_SCRYPT)
    return f"scrypt${sal.hex()}${chave.hex()}"


def verificar_senha(senha: str, armazenado: str) -> bool:
    try:
        _, sal_hex, chave_hex = armazenado.split("$")
    except ValueError:
        return False
    chave = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal_hex), **_SCRYPT)
    return hmac.compare_digest(chave.hex(), chave_hex)


def emitir_token(conta_id: UUID, segredo: str, expira_min: int) -> str:
    agora = datetime.now(timezone.utc)
    payload = {"sub": str(conta_id), "iat": agora, "exp": agora + timedelta(minutes=expira_min)}
    return jwt.encode(payload, segredo, algorithm="HS256")


_bearer = HTTPBearer(auto_error=False)


def conta_atual(request: Request, cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> UUID:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token ausente")
    try:
        payload = jwt.decode(cred.credentials, request.app.state.config.jwt_secret, algorithms=["HS256"])
        return UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido ou expirado")
