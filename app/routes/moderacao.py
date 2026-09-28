from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from .. import moderacao
from .. import repository as repo
from ..catalogo import Catalogo
from ..config import config
from ..db import conexao
from ..deps import cifrador
from ..ratelimit import exigir_limite
from ..schemas import ContaNaFila, Decisao, Denuncia
from ..security import conta_atual, moderador

router = APIRouter(tags=["moderação"])


@router.post("/perfis/{alvo}/denunciar", status_code=status.HTTP_204_NO_CONTENT)
async def denunciar(
    alvo: UUID, dados: Denuncia, eu: UUID = Depends(conta_atual), con=Depends(conexao), cif=Depends(cifrador)
):
    """Denuncia e bloqueia na hora. Com `incluir_mensagens`, a conversa recente vai junto
    como evidência para a moderação (é copiada antes de o bloqueio apagá-la)."""
    if alvo == eu:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Operação inválida sobre o próprio perfil")
    cfg = config()
    exigir_limite("denuncia", cfg.limite_denuncias_por_dia, str(eu), janela_s=86_400, anonimizar=False)
    if not await repo.existe_conta(con, alvo):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil não encontrado")
    await moderacao.denunciar(
        con,
        cif,
        denunciante=eu,
        denunciado=alvo,
        motivo=dados.motivo,
        detalhes=dados.detalhes,
        incluir_mensagens=dados.incluir_mensagens,
        limiar=cfg.denuncias_para_revisao,
    )


@router.get("/moderacao/fila", response_model=list[ContaNaFila])
async def fila(_: UUID = Depends(moderador), con=Depends(conexao), cif=Depends(cifrador)):
    itens = await moderacao.fila(con, cif)
    cat = await Catalogo.para(con, [i["perfil"] for i in itens if i["perfil"]])
    return [{**i, "perfil": cat.publico(i["perfil"]) if i["perfil"] else None} for i in itens]


@router.post("/moderacao/contas/{conta}/decisao", status_code=status.HTTP_204_NO_CONTENT)
async def decidir(conta: UUID, dados: Decisao, eu: UUID = Depends(moderador), con=Depends(conexao)):
    if conta == eu:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Não é possível moderar a própria conta")
    if not await moderacao.decidir(con, moderador=eu, conta=conta, acao=dados.acao, observacao=dados.observacao):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada")
