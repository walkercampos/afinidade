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
    gerar_hash_senha,
    iniciar_sessao,
    verificar_senha,
)

router = APIRouter(tags=["autenticação"])


@router.post("/auth/registro", response_model=Token, status_code=status.HTTP_201_CREATED)
async def registrar(dados: Registro, request: Request, response: Response, con=Depends(conexao)):
    exigir_limite("auth", config().limite_auth_por_min, ip_do_cliente(request))
    criada = await repo.criar_conta_anonima(con, dados.handle, gerar_hash_senha(dados.senha))
    if criada is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Apelido já em uso")
    conta_id, handle = criada
    return iniciar_sessao(response, conta_id, 0, handle)


@router.post("/auth/login", response_model=Token)
async def login(dados: Login, request: Request, response: Response, con=Depends(conexao)):
    cfg = config()
    exigir_limite("auth", cfg.limite_auth_por_min, ip_do_cliente(request))
    # Também por apelido: impede força bruta distribuída em vários IPs contra uma conta.
    exigir_limite("login-handle", cfg.limite_auth_por_min, dados.handle)
    conta = await repo.buscar_conta_por_handle(con, dados.handle)
    # Contas só com passkey não têm senha: comparamos com o hash falso (mesmo tempo de resposta).
    armazenado = conta["senha_hash"] if conta and conta["senha_hash"] else HASH_FALSO
    senha_ok = verificar_senha(dados.senha, armazenado)
    if conta is None or not conta["senha_hash"] or not senha_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais inválidas")
    if conta["situacao"] == "banida":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Conta banida por violar as regras da comunidade")
    return iniciar_sessao(response, conta["id"], conta["token_versao"], dados.handle)


@router.post("/auth/sair", status_code=status.HTTP_204_NO_CONTENT)
async def sair(response: Response, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Encerra a sessão em todos os dispositivos (também usado pelo botão de pânico)."""
    await repo.invalidar_sessoes(con, eu)
    apagar_cookie_sessao(response, config())


@router.delete("/conta", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_conta(response: Response, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    await repo.excluir_conta(con, eu)
    apagar_cookie_sessao(response, config())
