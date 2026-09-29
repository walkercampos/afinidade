from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from .. import fotos
from .. import repository as repo
from ..catalogo import Catalogo
from ..db import conexao
from ..deps import cifrador, exigir_perfil_visivel
from ..ratelimit import exigir_limite
from ..schemas import Foto, RespostaSolicitacao, SolicitacaoAcesso
from ..security import conta_atual, conta_liberada
from .descoberta import fotos_por_conta

router = APIRouter(tags=["fotos"])

_TIPOS_ACEITOS = {"image/jpeg", "image/png", "image/webp"}
_SEM_CACHE = {"Cache-Control": "no-store, private", "Content-Disposition": "inline"}


def _foto(linha, nitida: bool) -> Foto:
    return Foto(id=linha["id"], hash=linha["hash"], nitida=nitida, url=f"/api/fotos/{linha['id']}/imagem")


@router.post("/fotos", response_model=Foto, status_code=status.HTTP_201_CREATED)
async def enviar_foto(request: Request, eu: UUID = Depends(conta_atual), con=Depends(conexao), cif=Depends(cifrador)):
    """Corpo = bytes da imagem (Content-Type image/jpeg, image/png ou image/webp; até 5 MB).

    O servidor remove todos os metadados (inclusive GPS), redimensiona e gera a versão
    borrada. Máximo de 3 fotos por conta.
    """
    exigir_limite("foto", 20, str(eu), janela_s=3600, anonimizar=False)
    if request.headers.get("content-type", "").split(";")[0].strip() not in _TIPOS_ACEITOS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Envie image/jpeg, image/png ou image/webp")
    if int(request.headers.get("content-length") or 0) > fotos.MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Imagem maior que 5 MB")
    dados = bytearray()
    async for pedaco in request.stream():  # lê com teto, mesmo sem Content-Length confiável
        dados += pedaco
        if len(dados) > fotos.MAX_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Imagem maior que 5 MB")
    try:
        nitida, borrada, sha = fotos.processar(bytes(dados))
    except fotos.ImagemInvalida as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    linha = await fotos.salvar(con, cif, eu, nitida, borrada, sha)
    if linha is None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Máximo de {fotos.MAX_FOTOS_POR_CONTA} fotos")
    return _foto(linha, True)


@router.get("/fotos", response_model=list[Foto])
async def minhas_fotos(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    return [_foto(linha, True) for linha in await fotos.listar_de(con, eu)]


@router.delete("/fotos/{foto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def apagar_foto(foto_id: UUID, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    if not await fotos.apagar(con, eu, foto_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foto não encontrada")


@router.get("/fotos/{foto_id}/imagem")
async def imagem(foto_id: UUID, eu: UUID = Depends(conta_atual), con=Depends(conexao), cif=Depends(cifrador)):
    """Versão nítida para o dono e para quem ele autorizou; borrada para os demais.
    Quem não pode ver o perfil (bloqueio, conta em revisão) recebe 404."""
    dono = await fotos.dono_da_foto(con, foto_id)
    if dono is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foto não encontrada")
    if dono == eu:
        nitida = True
    else:
        await exigir_perfil_visivel(con, eu, dono)
        nitida = dono in await fotos.donos_que_liberaram(con, eu, [dono])
    conteudo = await fotos.ler_imagem(con, cif, foto_id, nitida=nitida)
    return Response(conteudo, media_type="image/webp", headers=_SEM_CACHE)


@router.get("/perfis/{alvo}/fotos", response_model=list[Foto])
async def fotos_do_perfil(alvo: UUID, eu: UUID = Depends(conta_liberada), con=Depends(conexao)):
    await exigir_perfil_visivel(con, eu, alvo)
    return (await fotos_por_conta(con, eu, [alvo]))[alvo]


@router.post("/perfis/{alvo}/fotos/solicitar")
async def solicitar_acesso(alvo: UUID, eu: UUID = Depends(conta_liberada), con=Depends(conexao)):
    """Pede ao dono para ver as fotos nítidas. Só o dono pode aprovar."""
    exigir_limite("pedido-foto", 30, str(eu), janela_s=86_400, anonimizar=False)
    await exigir_perfil_visivel(con, eu, alvo)
    return {"status": await fotos.solicitar(con, alvo, eu)}


@router.get("/fotos/solicitacoes", response_model=list[SolicitacaoAcesso])
async def solicitacoes(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Pedidos pendentes de acesso às MINHAS fotos."""
    pedidos = await fotos.pendentes(con, eu)
    perfis = {p["conta_id"]: p for p in [await repo.buscar_perfil(con, x["visualizador_id"]) for x in pedidos] if p}
    cat = await Catalogo.para(con, list(perfis.values()))
    return [
        SolicitacaoAcesso(
            visualizador=cat.publico(perfis[x["visualizador_id"]]), status=x["status"], criado_em=x["criado_em"]
        )
        for x in pedidos
        if x["visualizador_id"] in perfis
    ]


@router.post("/fotos/solicitacoes/{visualizador}", status_code=status.HTTP_204_NO_CONTENT)
async def responder(
    visualizador: UUID, dados: RespostaSolicitacao, eu: UUID = Depends(conta_atual), con=Depends(conexao)
):
    """Aprova ou nega um pedido. Também serve para revogar um acesso já aprovado (aprovar=false)."""
    if not await fotos.responder(con, eu, visualizador, dados.aprovar):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado")
