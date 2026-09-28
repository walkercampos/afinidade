import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from .. import repository as repo
from ..config import config
from ..db import conexao
from ..ratelimit import exigir_limite, ip_do_cliente
from ..schemas import Login, Registro, Token
from ..security import (
    HASH_FALSO,
    apagar_cookie_sessao,
    conta_atual,
    emitir_token,
    gerar_hash_senha,
    gravar_cookie_sessao,
    verificar_senha,
)

router = APIRouter(tags=["autenticação"])

_ALFABETO_HANDLE = "abcdefghijkmnpqrstuvwxyz23456789"  # sem 0/o/1/l, fáceis de confundir


def _handle_aleatorio() -> str:
    return "anon_" + "".join(secrets.choice(_ALFABETO_HANDLE) for _ in range(8))


def _iniciar_sessao(response: Response, conta_id: UUID, versao: int, handle: str) -> Token:
    cfg = config()
    token = emitir_token(conta_id, versao, cfg.jwt_secret, cfg.jwt_expira_min)
    gravar_cookie_sessao(response, token, cfg)
    return Token(access_token=token, handle=handle)


@router.post("/auth/registro", response_model=Token, status_code=status.HTTP_201_CREATED)
async def registrar(dados: Registro, request: Request, response: Response, con=Depends(conexao)):
    exigir_limite("auth", config().limite_auth_por_min, ip_do_cliente(request))
    senha_hash = gerar_hash_senha(dados.senha)
    if dados.handle:
        handle, conta_id = dados.handle, await repo.criar_conta(con, dados.handle, senha_hash)
        if conta_id is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Apelido já em uso")
    else:
        for _ in range(5):  # 32^8 combinações: colisão é raríssima
            handle = _handle_aleatorio()
            if (conta_id := await repo.criar_conta(con, handle, senha_hash)) is not None:
                break
        else:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Tente novamente")
    return _iniciar_sessao(response, conta_id, 0, handle)


@router.post("/auth/login", response_model=Token)
async def login(dados: Login, request: Request, response: Response, con=Depends(conexao)):
    cfg = config()
    exigir_limite("auth", cfg.limite_auth_por_min, ip_do_cliente(request))
    # Também por apelido: impede força bruta distribuída em vários IPs contra uma conta.
    exigir_limite("login-handle", cfg.limite_auth_por_min, dados.handle)
    conta = await repo.buscar_conta_por_handle(con, dados.handle)
    senha_ok = verificar_senha(dados.senha, conta["senha_hash"] if conta else HASH_FALSO)
    if conta is None or not senha_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais inválidas")
    if conta["situacao"] == "banida":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Conta banida por violar as regras da comunidade")
    return _iniciar_sessao(response, conta["id"], conta["token_versao"], dados.handle)


@router.post("/auth/sair", status_code=status.HTTP_204_NO_CONTENT)
async def sair(response: Response, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Encerra a sessão em todos os dispositivos (também usado pelo botão de pânico)."""
    await repo.invalidar_sessoes(con, eu)
    apagar_cookie_sessao(response, config())


@router.delete("/conta", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_conta(response: Response, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    await repo.excluir_conta(con, eu)
    apagar_cookie_sessao(response, config())
