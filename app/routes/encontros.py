from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .. import encontros
from .. import repository as repo
from ..db import conexao
from ..ratelimit import exigir_limite
from ..schemas import Encontro, NovoEncontro
from ..security import conta_liberada

router = APIRouter(tags=["encontros"])


def _cifrador(request: Request):
    return request.app.state.cifrador_encontros


@router.get("/encontros", response_model=list[Encontro])
async def listar(eu: UUID = Depends(conta_liberada), con=Depends(conexao), cif=Depends(_cifrador)):
    """Meus encontros (os mais recentes primeiro). Só a própria pessoa vê."""
    return await encontros.listar(con, cif, eu)


@router.post("/encontros", response_model=Encontro, status_code=status.HTTP_201_CREATED)
async def criar(
    request: Request,
    dados: NovoEncontro,
    eu: UUID = Depends(conta_liberada),
    con=Depends(conexao),
    cif=Depends(_cifrador),
):
    """Registra um encontro e avisa o contato de confiança de que ele foi indicado."""
    exigir_limite("encontro", 10, str(eu), janela_s=86400, anonimizar=False)
    try:
        encontros.validar_horarios(dados.inicio_em, dados.checkin_ate, datetime.now(UTC))
    except encontros.EncontroInvalido as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    if dados.com is not None and not await repo.sao_conexao(con, eu, dados.com):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conexão não encontrada")
    encontro_id = await encontros.criar(
        con,
        cif,
        eu,
        com=dados.com,
        local=dados.local,
        observacoes=dados.observacoes,
        como_te_conhecem=dados.como_te_conhecem,
        contato_email=dados.contato_email,
        inicio=dados.inicio_em,
        checkin=dados.checkin_ate,
    )
    await request.app.state.carteiro.enviar(
        encontros.mensagem_de_indicacao(dados.contato_email, dados.como_te_conhecem)
    )
    return next(e for e in await encontros.listar(con, cif, eu) if e["id"] == encontro_id)


async def _mudar(con, eu: UUID, encontro_id: UUID, nova: str) -> None:
    if not await encontros.mudar_situacao(con, eu, encontro_id, nova):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Encontro não encontrado ou já encerrado")


@router.post("/encontros/{encontro_id}/checkin", status_code=status.HTTP_204_NO_CONTENT)
async def checkin(encontro_id: UUID, eu: UUID = Depends(conta_liberada), con=Depends(conexao)):
    """Está tudo bem: o alerta não será enviado."""
    await _mudar(con, eu, encontro_id, "confirmado_ok")


@router.post("/encontros/{encontro_id}/cancelar", status_code=status.HTTP_204_NO_CONTENT)
async def cancelar(encontro_id: UUID, eu: UUID = Depends(conta_liberada), con=Depends(conexao)):
    await _mudar(con, eu, encontro_id, "cancelado")
