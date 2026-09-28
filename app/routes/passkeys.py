"""Rotas das passkeys: a "biometria" do app. A conta nasce pelo e-mail (routes/auth.py); depois
a pessoa cadastra passkeys e passa a entrar com digital, rosto ou PIN. Toda cerimônia tem duas etapas:

1. `.../opcoes`: o servidor cria um desafio de uso único e devolve as opções para o navegador;
2. a rota sem `/opcoes`: recebe a resposta assinada pelo aparelho e confere.
"""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from webauthn import base64url_to_bytes

from .. import passkeys as pk
from .. import repository as repo
from ..config import config
from ..db import conexao
from ..ratelimit import exigir_limite, ip_do_cliente
from ..schemas import OpcoesPasskey, PasskeySalva, RespostaPasskey, Token
from ..security import conta_atual, iniciar_sessao

router = APIRouter(tags=["passkeys"])


def _limite_ip(request: Request) -> None:
    exigir_limite("auth", config().limite_auth_por_min, ip_do_cliente(request))


def _recusar(e: pk.PasskeyInvalida, codigo: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(codigo, str(e))


# ---------- entrar ----------


@router.post("/auth/passkey/login/opcoes", response_model=OpcoesPasskey)
async def opcoes_login(request: Request, con=Depends(conexao)):
    _limite_ip(request)
    opcoes, desafio = pk.opcoes_login(config())
    return OpcoesPasskey(desafio_id=await pk.criar_desafio(con, "login", desafio), opcoes=opcoes)


@router.post("/auth/passkey/login", response_model=Token)
async def entrar(dados: RespostaPasskey, request: Request, response: Response, con=Depends(conexao)):
    _limite_ip(request)
    nao_reconhecida = HTTPException(status.HTTP_401_UNAUTHORIZED, "Passkey não reconhecida")
    try:
        desafio, _ = await pk.consumir_desafio(con, dados.desafio_id, "login")
        salva = await pk.buscar(con, pk.id_da_credencial(dados.credencial))
        if salva is None:
            raise nao_reconhecida
        verificado = pk.verificar_login(
            config(), dados.credencial, desafio, chave_publica=salva["chave_publica"], contador=salva["contador"]
        )
    except pk.PasskeyInvalida as e:
        raise _recusar(e, status.HTTP_401_UNAUTHORIZED) from e
    if salva["situacao"] == "banida":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Conta banida por violar as regras da comunidade")
    await pk.registrar_uso(con, salva["id"], verificado.new_sign_count, verificado.credential_backed_up)
    return iniciar_sessao(response, salva["conta_id"], salva["token_versao"], salva["handle"])


# ---------- gerenciar as passkeys da própria conta ----------


def _publica(linha) -> PasskeySalva:
    return PasskeySalva(
        id=pk.id_publico(linha["id"]),
        nome=linha["nome"],
        sincronizada=linha["sincronizada"],
        criado_em=linha["criado_em"],
        usado_em=linha["usado_em"],
    )


@router.get("/passkeys", response_model=list[PasskeySalva])
async def listar(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    return [_publica(linha) for linha in await pk.listar(con, eu)]


@router.post("/passkeys/opcoes", response_model=OpcoesPasskey)
async def opcoes_adicionar(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Adiciona uma passkey a uma conta existente (inclusive contas criadas com senha)."""
    conta = await repo.buscar_conta(con, eu)
    webauthn_id = conta["webauthn_id"]
    if webauthn_id is None:
        webauthn_id = pk.novo_webauthn_id()
        await con.execute("UPDATE contas SET webauthn_id = $2 WHERE id = $1", eu, webauthn_id)
    opcoes, desafio = pk.opcoes_registro(
        config(), webauthn_id=webauthn_id, apelido=conta["handle"], excluir=await pk.ids_da_conta(con, eu)
    )
    return OpcoesPasskey(desafio_id=await pk.criar_desafio(con, "adicionar", desafio, conta_id=eu), opcoes=opcoes)


@router.post("/passkeys", response_model=PasskeySalva, status_code=status.HTTP_201_CREATED)
async def adicionar(dados: RespostaPasskey, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    try:
        desafio, _ = await pk.consumir_desafio(con, dados.desafio_id, "adicionar", conta_id=eu)
        verificado = pk.verificar_registro(config(), dados.credencial, desafio)
        await pk.salvar(con, eu, verificado, dados.credencial, dados.nome)
    except pk.PasskeyInvalida as e:
        raise _recusar(e) from e
    except asyncpg.UniqueViolationError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta passkey já está cadastrada") from e
    return _publica(await con.fetchrow("SELECT * FROM passkeys WHERE id = $1", verificado.credential_id))


@router.delete("/passkeys/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remover(passkey_id: str, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    try:
        credencial_id = base64url_to_bytes(passkey_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Passkey não encontrada") from e
    # Sempre é possível remover: o e-mail continua permitindo entrar e cadastrar outra passkey.
    if not await pk.apagar(con, eu, credencial_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Passkey não encontrada")
