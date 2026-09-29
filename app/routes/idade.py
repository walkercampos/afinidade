from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from .. import idade
from ..config import config
from ..db import conexao
from ..ratelimit import exigir_limite
from ..schemas import IdadeIniciada, ResultadoSimulado, SituacaoIdade
from ..security import conta_atual

router = APIRouter(tags=["verificação de idade"])


@router.get("/idade", response_model=SituacaoIdade)
async def situacao(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Se a verificação é obrigatória, se já foi feita e se há uma tentativa em andamento."""
    return await idade.situacao(con, eu)


@router.post("/idade/iniciar", response_model=IdadeIniciada)
async def iniciar(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Começa uma verificação: devolve a URL do provedor para onde a pessoa deve ir."""
    provedor = idade.criar_provedor()
    if provedor is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Verificação de idade indisponível no momento.")
    if (await idade.situacao(con, eu))["verificada"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Sua idade já foi verificada.")
    exigir_limite("idade", 5, str(eu), janela_s=86400, anonimizar=False)
    return {"url": await idade.iniciar(con, provedor, eu)}


@router.post("/idade/simulado/{sessao}", status_code=status.HTTP_204_NO_CONTENT)
async def concluir_simulado(
    sessao: str, dados: ResultadoSimulado, eu: UUID = Depends(conta_atual), con=Depends(conexao)
):
    """Só fora de produção e com o provedor simulado: faz o papel do webhook do provedor."""
    if config().producao or config().idade_provedor != "simulado":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    if not await idade.concluir(con, sessao, dados.aprovar, conta=eu):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tentativa não encontrada ou expirada")
