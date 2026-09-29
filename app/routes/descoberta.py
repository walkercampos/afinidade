from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from .. import descoberta, fotos, geo
from .. import repository as repo
from ..catalogo import Catalogo
from ..config import config
from ..db import conexao
from ..deps import exigir_perfil, exigir_perfil_visivel
from ..matcher import PerfilMatch, calcular_match, score_mutuo, similaridade, tags_mesmo_nivel
from ..schemas import Candidato, Compatibilidade, Foto, Ordem, PerfilPublico, ResultadoCurtida, Simulacao
from ..security import Sessao, conta_atual, conta_liberada, exigir_liberada, sessao_atual

router = APIRouter(tags=["descoberta"])

HEADER_CURSOR = "X-Proximo-Cursor"


def _compatibilidade(eu: PerfilMatch, outro: PerfilMatch, cat: Catalogo, distancia: float | None) -> Compatibilidade:
    r = calcular_match(eu, outro)
    return Compatibilidade(
        match_valido=r.match_valido,
        score_porcentagem=r.score_porcentagem,
        score_mutuo=score_mutuo(eu, outro),
        similaridade=similaridade(eu, outro),
        tags_em_comum=cat.tags_de(r.tags_em_comum),
        tags_mesmo_nivel=cat.tags_de(tags_mesmo_nivel(eu, outro)),
        distancia_km=geo.faixa_km(distancia),
        motivo=r.motivo,
    )


def _distancia(a, b) -> float | None:
    if a["lat_aprox"] is None or b["lat_aprox"] is None:
        return None
    return geo.distancia_km(a["lat_aprox"], a["lon_aprox"], b["lat_aprox"], b["lon_aprox"])


async def fotos_por_conta(con, eu: UUID, contas: list[UUID]) -> dict[UUID, list[Foto]]:
    liberadas = await fotos.donos_que_liberaram(con, eu, contas)
    resultado: dict[UUID, list[Foto]] = {c: [] for c in contas}
    for f in await fotos.listar_de_varias(con, contas):
        resultado[f["conta_id"]].append(
            Foto(id=f["id"], hash=f["hash"], nitida=f["conta_id"] in liberadas, url=f"/api/fotos/{f['id']}/imagem")
        )
    return resultado


async def _listar(con, sessao: Sessao, ordem: str, limite: int, cursor: str | None, response: Response):
    eu = sessao.conta_id
    # Primeiro o perfil (409 leva para "Crie seu perfil"), depois a idade (403 leva para a
    # verificação): quem acabou de criar a conta monta o perfil antes de verificar.
    meu = await exigir_perfil(con, eu)
    exigir_liberada(sessao)
    await repo.marcar_atividade(con, eu)
    try:
        posicao = descoberta.decodificar_cursor(cursor) if cursor else None
    except descoberta.CursorInvalido as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    linhas = await descoberta.buscar_candidatos(
        con, meu, ordem=ordem, limite=limite, cursor=posicao, inatividade_dias=config().inatividade_max_dias
    )
    if len(linhas) == limite:
        response.headers[HEADER_CURSOR] = descoberta.codificar_cursor(linhas[-1], ordem)

    cat = await Catalogo.para(con, linhas)
    fotos_de = await fotos_por_conta(con, eu, [linha["conta_id"] for linha in linhas])
    eu_match = repo.para_perfil_match(meu)
    return [
        Candidato(
            perfil=cat.publico(linha),
            compatibilidade=_compatibilidade(eu_match, repo.para_perfil_match(linha), cat, linha["distancia"]),
            fotos=fotos_de[linha["conta_id"]],
        )
        for linha in linhas
    ]


@router.get("/descobrir", response_model=list[Candidato])
async def descobrir(
    response: Response,
    ordem: Ordem = "compatibilidade",
    limite: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=300),
    sessao: Sessao = Depends(sessao_atual),
    con=Depends(conexao),
):
    """Perfis compatíveis (gênero mútuo, sem conflito de limites, dentro da distância).

    `ordem`: compatibilidade (padrão), afinidade (gostos parecidos) ou recentes.
    Paginação: se houver mais resultados, o header `X-Proximo-Cursor` traz o valor a
    enviar em `cursor` na próxima chamada.
    """
    return await _listar(con, sessao, ordem, limite, cursor, response)


@router.get("/afins", response_model=list[Candidato])
async def afins(
    response: Response,
    limite: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=300),
    sessao: Sessao = Depends(sessao_atual),
    con=Depends(conexao),
):
    """Pessoas com as mesmas preferências que você (atalho para /descobrir?ordem=afinidade)."""
    return await _listar(con, sessao, "afinidade", limite, cursor, response)


@router.get("/perfis/{alvo}", response_model=Candidato)
async def ver_perfil(alvo: UUID, eu: UUID = Depends(conta_liberada), con=Depends(conexao)):
    meu = await exigir_perfil(con, eu)
    outro = await exigir_perfil_visivel(con, eu, alvo)
    cat = await Catalogo.para(con, [meu, outro])
    return Candidato(
        perfil=cat.publico(outro),
        compatibilidade=_compatibilidade(
            repo.para_perfil_match(meu), repo.para_perfil_match(outro), cat, _distancia(meu, outro)
        ),
        fotos=(await fotos_por_conta(con, eu, [alvo]))[alvo],
    )


@router.post("/perfis/{alvo}/curtir", response_model=ResultadoCurtida)
async def curtir(alvo: UUID, eu: UUID = Depends(conta_liberada), con=Depends(conexao)):
    meu = await exigir_perfil(con, eu)
    outro = await exigir_perfil_visivel(con, eu, alvo)
    # Só dá para curtir quem passa por TODOS os filtros (gênero, limites, distância):
    # ninguém recebe interesse de quem não busca, de quem quer algo que é seu limite
    # absoluto ou de quem está fora da distância que você escolheu.
    r = calcular_match(repo.para_perfil_match(meu), repo.para_perfil_match(outro))
    if not r.match_valido:
        raise HTTPException(status.HTTP_403_FORBIDDEN, r.motivo)
    if await descoberta.buscar_elegivel(con, meu, alvo) is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Perfil fora dos filtros de distância")
    return ResultadoCurtida(conexao=await repo.curtir(con, eu, alvo))


@router.post("/perfis/{alvo}/bloquear", status_code=status.HTTP_204_NO_CONTENT)
async def bloquear(alvo: UUID, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    if alvo == eu:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Operação inválida sobre o próprio perfil")
    if not await repo.existe_conta(con, alvo):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil não encontrado")
    await repo.bloquear(con, eu, alvo)


@router.get("/conexoes", response_model=list[PerfilPublico])
async def conexoes(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    linhas = await repo.listar_conexoes(con, eu)
    cat = await Catalogo.para(con, linhas)
    return [cat.publico(linha) for linha in linhas]


@router.post("/match/simular")
async def simular(dados: Simulacao):
    """Roda o algoritmo sobre dois payloads no formato do script original (sem banco)."""
    a = PerfilMatch.de_dict(dados.usuario_a.model_dump())
    b = PerfilMatch.de_dict(dados.usuario_b.model_dump())
    return {**calcular_match(a, b).to_dict(), "score_mutuo": score_mutuo(a, b), "similaridade": similaridade(a, b)}
