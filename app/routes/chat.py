from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import mensagens
from .. import repository as repo
from ..catalogo import Catalogo
from ..config import config
from ..db import conexao
from ..deps import cifrador
from ..ratelimit import exigir_limite
from ..schemas import Conversa, Mensagem, NovaMensagem
from ..security import conta_ativa, conta_atual

router = APIRouter(tags=["chat"])


async def _exigir_conexao(con, eu: UUID, outro: UUID) -> None:
    if not await repo.sao_conexao(con, eu, outro):
        # 404: não diz se a pessoa existe, bloqueou você ou só não curtiu de volta.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversa não encontrada")


@router.get("/conversas", response_model=list[Conversa])
async def conversas(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Uma conversa por conexão; as com mensagens mais recentes primeiro."""
    perfis = await repo.listar_conexoes(con, eu)
    resumo = await mensagens.resumo_conversas(con, eu)
    cat = await Catalogo.para(con, perfis)
    itens = [
        Conversa(
            perfil=cat.publico(p),
            nao_lidas=resumo.get(p["conta_id"], (0, None))[0],
            ultima_em=resumo.get(p["conta_id"], (0, None))[1],
        )
        for p in perfis
    ]
    return sorted(itens, key=lambda c: (c.ultima_em is not None, c.ultima_em), reverse=True)


@router.get("/conversas/{outro}/mensagens", response_model=list[Mensagem])
async def ler(
    outro: UUID,
    apos: int = Query(0, ge=0),
    limite: int = Query(50, ge=1, le=100),
    eu: UUID = Depends(conta_atual),
    con=Depends(conexao),
    cif=Depends(cifrador),
):
    """Mensagens a partir do id `apos` (use o último id recebido para buscar só as novas).

    Ler marca as mensagens recebidas como lidas: elas somem para os dois lados em
    `expira_em` (5 minutos depois). O cliente deve removê-las da tela nesse instante.
    """
    await _exigir_conexao(con, eu, outro)
    return await mensagens.listar(con, cif, eu, outro, apos=apos, limite=limite)


@router.post("/conversas/{outro}/mensagens", response_model=Mensagem, status_code=status.HTTP_201_CREATED)
async def enviar(
    outro: UUID, dados: NovaMensagem, eu: UUID = Depends(conta_ativa), con=Depends(conexao), cif=Depends(cifrador)
):
    exigir_limite("mensagem", config().limite_mensagens_por_min, str(eu), anonimizar=False)
    await _exigir_conexao(con, eu, outro)
    return await mensagens.enviar(con, cif, eu, outro, dados.texto)


@router.delete("/conversas/{outro}/mensagens", status_code=status.HTTP_204_NO_CONTENT)
async def apagar_minhas(outro: UUID, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Apaga, para os dois lados, todas as mensagens que EU enviei nessa conversa."""
    await mensagens.apagar_minhas(con, eu, outro)
