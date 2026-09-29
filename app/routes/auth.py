"""Acesso sem senha: e-mail (código de 6 dígitos ou link) para criar a conta e para recuperar o
acesso; depois, biometria com passkey (ver routes/passkeys.py) para o dia a dia."""

import json
import logging
import uuid
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status

from .. import contato
from .. import repository as repo
from .. import verificacao as verif
from ..config import config
from ..db import conexao
from ..email import FalhaNoEnvio, mensagem_de_acesso
from ..ratelimit import exigir_limite, ip_do_cliente
from ..schemas import (
    Cadastro,
    ConfirmarCodigo,
    ConfirmarLink,
    MinhaConta,
    PedidoEntrar,
    Preferencias,
    Token,
    VerificacaoEnviada,
)
from ..security import apagar_cookie_sessao, conta_atual, iniciar_sessao
from ..tempo_real import central

router = APIRouter(tags=["autenticação"])
log = logging.getLogger("matchmaking.auth")

ENVIOS_POR_EMAIL_POR_HORA = 5


async def _entregar(carteiro, mensagem) -> None:
    try:
        await carteiro.enviar(mensagem)
    except FalhaNoEnvio:
        log.exception("Falha ao enviar e-mail de acesso")  # a pessoa pode pedir outro código


async def _enviar_codigo(
    request: Request, tarefas: BackgroundTasks, con, email: str, email_hash: bytes, *, conta_id=None, dados=None
) -> UUID:
    email_cifrado = contato.cifrar_email(request.app.state.cifrador_email, email, email_hash)
    verificacao_id, codigo, token = await verif.criar(
        con, config().email_pepper, email_hash, email_cifrado, conta_id=conta_id, dados=dados
    )
    # O token vai no fragmento (#): navegadores não o enviam a servidores nem em Referer.
    link = f"{config().email.app_url}/#/verificar/{token}"
    # Envio DEPOIS da resposta: o tempo de resposta não revela se o e-mail tem conta.
    tarefas.add_task(_entregar, request.app.state.carteiro, mensagem_de_acesso(email, codigo, link))
    return verificacao_id


def _limites(request: Request, email_hash: bytes) -> None:
    exigir_limite("auth", config().limite_auth_por_min, ip_do_cliente(request))
    # Impede usar o app para bombardear a caixa de alguém.
    exigir_limite("email", ENVIOS_POR_EMAIL_POR_HORA, email_hash.hex(), janela_s=3600, anonimizar=False)


@router.post("/auth/email/cadastro", response_model=VerificacaoEnviada, status_code=status.HTTP_202_ACCEPTED)
async def cadastro(dados: Cadastro, request: Request, tarefas: BackgroundTasks, con=Depends(conexao)):
    """Envia o código para criar a conta. Se o e-mail já tem conta, o código serve para entrar
    nela: a resposta é a mesma, então ninguém descobre quais e-mails estão cadastrados."""
    email_hash = verif.hash_email(config().email_pepper, dados.email)
    _limites(request, email_hash)
    existente = await repo.buscar_conta_por_email(con, email_hash)
    if existente:
        verificacao_id = await _enviar_codigo(request, tarefas, con, dados.email, email_hash, conta_id=existente["id"])
    else:
        if dados.handle and await repo.buscar_conta_por_handle(con, dados.handle):
            raise HTTPException(status.HTTP_409_CONFLICT, "Apelido já em uso")
        pendente = {"handle": dados.handle}
        verificacao_id = await _enviar_codigo(request, tarefas, con, dados.email, email_hash, dados=pendente)
    return VerificacaoEnviada(verificacao_id=verificacao_id)


@router.post("/auth/email/entrar", response_model=VerificacaoEnviada, status_code=status.HTTP_202_ACCEPTED)
async def entrar(dados: PedidoEntrar, request: Request, tarefas: BackgroundTasks, con=Depends(conexao)):
    """Envia um código de acesso (útil em aparelho novo ou para recuperar a conta)."""
    email_hash = verif.hash_email(config().email_pepper, dados.email)
    _limites(request, email_hash)
    existente = await repo.buscar_conta_por_email(con, email_hash)
    if existente is None:
        # Sem conta: nada é enviado, mas a resposta tem o mesmo formato (id que não existe).
        return VerificacaoEnviada(verificacao_id=uuid.uuid4())
    verificacao_id = await _enviar_codigo(request, tarefas, con, dados.email, email_hash, conta_id=existente["id"])
    return VerificacaoEnviada(verificacao_id=verificacao_id)


async def _concluir(con, response: Response, linha) -> dict:
    """Verificação válida: entra na conta existente ou cria a conta nova."""
    if linha["conta_id"] is not None:
        conta = await repo.buscar_conta(con, linha["conta_id"])
        if conta is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada")
        if conta["situacao"] == "banida":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Conta banida por violar as regras da comunidade")
        # Contas criadas antes da migração 0009 ganham o e-mail cifrado no primeiro acesso por e-mail.
        await con.execute(
            "UPDATE contas SET email_cifrado = $2 WHERE id = $1 AND email_cifrado IS NULL",
            conta["id"],
            linha["email_cifrado"],
        )
        return iniciar_sessao(response, conta["id"], conta["token_versao"], conta["handle"])

    pendente = json.loads(linha["dados"])
    try:
        criada = await repo.criar_conta_anonima(con, pendente["handle"], linha["email_hash"], linha["email_cifrado"])
    except repo.EmailJaCadastrado:
        # Outra verificação do mesmo e-mail criou a conta antes: quem tem o código entra nela.
        conta = await repo.buscar_conta_por_email(con, linha["email_hash"])
        return iniciar_sessao(response, conta["id"], conta["token_versao"], conta["handle"])
    if criada is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Apelido já em uso. Recomece o cadastro com outro.")
    conta_id, handle = criada
    return iniciar_sessao(response, conta_id, 0, handle, novo=True)


@router.post("/auth/email/confirmar", response_model=Token)
async def confirmar(dados: ConfirmarCodigo, request: Request, response: Response, con=Depends(conexao)):
    exigir_limite("auth", config().limite_auth_por_min, ip_do_cliente(request))
    try:
        linha = await verif.confirmar_codigo(con, config().email_pepper, dados.verificacao_id, dados.codigo)
    except verif.VerificacaoInvalida as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return await _concluir(con, response, linha)


@router.post("/auth/email/link", response_model=Token)
async def link(dados: ConfirmarLink, request: Request, response: Response, con=Depends(conexao)):
    exigir_limite("auth", config().limite_auth_por_min, ip_do_cliente(request))
    try:
        linha = await verif.confirmar_token(con, dados.token)
    except verif.VerificacaoInvalida as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return await _concluir(con, response, linha)


@router.post("/auth/sair", status_code=status.HTTP_204_NO_CONTENT)
async def sair(response: Response, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Encerra a sessão em todos os dispositivos (também usado pelo botão de pânico)."""
    await repo.invalidar_sessoes(con, eu)
    await central.derrubar(eu)
    apagar_cookie_sessao(response, config())


@router.get("/conta", response_model=MinhaConta)
async def minha_conta(request: Request, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Dados da própria conta. O e-mail vem mascarado: basta para a pessoa reconhecê-lo."""
    conta = await repo.buscar_conta(con, eu)
    email = await contato.email_da_conta(con, request.app.state.cifrador_email, eu)
    return MinhaConta(
        handle=conta["handle"],
        email=contato.mascarar(email) if email else None,
        moderador=conta["papel"] == "moderador",
    )


@router.get("/conta/preferencias", response_model=Preferencias)
async def ver_preferencias(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    return {"modo_discreto": await con.fetchval("SELECT modo_discreto FROM contas WHERE id = $1", eu)}


@router.put("/conta/preferencias", response_model=Preferencias)
async def salvar_preferencias(dados: Preferencias, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Modo discrição: nome e ícone neutros no navegador e na tela inicial (vale em todos os aparelhos)."""
    await con.execute("UPDATE contas SET modo_discreto = $2 WHERE id = $1", eu, dados.modo_discreto)
    return dados


@router.delete("/conta", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_conta(response: Response, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    await repo.excluir_conta(con, eu)
    await central.derrubar(eu)
    apagar_cookie_sessao(response, config())
