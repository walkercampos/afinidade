from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from .. import termos
from ..db import conexao
from ..schemas import AceiteTermos, SituacaoTermos, VersaoTermos
from ..security import conta_atual

router = APIRouter(tags=["termos"])


@router.get("/termos", response_model=VersaoTermos)
async def versao():
    """Versão atual dos termos e da política de privacidade (público)."""
    return {"versao": termos.VERSAO_ATUAL, "termos_url": "/termos.html", "privacidade_url": "/privacidade.html"}


@router.get("/termos/situacao", response_model=SituacaoTermos)
async def situacao(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    return await termos.situacao(con, eu)


@router.post("/termos/aceitar", response_model=SituacaoTermos)
async def aceitar(dados: AceiteTermos, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Aceite explícito da versão que a pessoa leu (a versão vai junto, para não aceitar às cegas
    uma versão que mudou enquanto a tela estava aberta)."""
    try:
        await termos.aceitar(con, eu, dados.versao)
    except termos.VersaoDesatualizada as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    return await termos.situacao(con, eu)
