from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from .. import geo
from .. import repository as repo
from ..catalogo import Catalogo
from ..db import conexao
from ..deps import exigir_perfil
from ..ratelimit import exigir_limite
from ..schemas import (
    Distancia,
    ItemCatalogo,
    Localizacao,
    LocalizacaoSalva,
    PerfilEntrada,
    PerfilProprio,
    TagsInteresses,
)
from ..security import conta_atual

router = APIRouter(tags=["perfil"])


@router.get("/catalogo/generos", response_model=list[ItemCatalogo])
async def catalogo_generos(con=Depends(conexao)):
    return [dict(linha) for linha in await repo.listar_catalogo(con, "generos")]


@router.get("/catalogo/tags", response_model=list[ItemCatalogo])
async def catalogo_tags(con=Depends(conexao)):
    return [dict(linha) for linha in await repo.listar_catalogo(con, "tags")]


@router.put("/perfil", response_model=PerfilProprio)
async def salvar_perfil(dados: PerfilEntrada, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    t = dados.tags_interesses
    try:
        generos = await repo.ids_por_slug(con, "generos", [dados.genero, *dados.busca_por])
        tags = await repo.ids_por_slug(con, "tags", [*t.quero, *t.curioso, *t.limite_absoluto])
    except repo.SlugDesconhecido as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    await repo.salvar_perfil(
        con,
        eu,
        nome_exibicao=dados.nome_exibicao,
        bio=dados.bio,
        visivel=dados.visivel,
        genero_id=generos[dados.genero],
        busca_por=sorted({generos[g] for g in dados.busca_por}),
        tags_quero=[tags[s] for s in t.quero],
        tags_curioso=[tags[s] for s in t.curioso],
        tags_limite=[tags[s] for s in t.limite_absoluto],
    )
    return await ler_perfil(eu, con)


@router.get("/perfil", response_model=PerfilProprio)
async def ler_perfil(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    p = await repo.buscar_perfil(con, eu)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil ainda não criado")
    cat = await Catalogo.para(con, [p])
    return PerfilProprio(
        id=eu,
        nome_exibicao=p["nome_exibicao"],
        bio=p["bio"],
        visivel=p["visivel"],
        genero=cat.generos[p["genero_id"]],
        busca_por=sorted(cat.generos[g] for g in p["busca_por"]),
        tags_interesses=TagsInteresses(
            quero=cat.tags_de(p["tags_quero"]),
            curioso=cat.tags_de(p["tags_curioso"]),
            limite_absoluto=cat.tags_de(p["tags_limite"]),
        ),
        localizacao=LocalizacaoSalva(regiao=p["geohash"], distancia_max_km=p["distancia_max_km"]),
    )


@router.put("/perfil/localizacao", response_model=LocalizacaoSalva)
async def salvar_localizacao(dados: Localizacao, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Recebe a coordenada do aparelho, guarda só a célula de ~5 km e descarta o resto."""
    # Limite de trocas: dificulta "varrer" posições para triangular outras pessoas.
    exigir_limite("localizacao", 20, str(eu), janela_s=3600, anonimizar=False)
    await exigir_perfil(con, eu)
    regiao = geo.codificar(dados.lat, dados.lon)
    lat, lon = geo.centro(regiao)
    await repo.salvar_localizacao(con, eu, regiao, lat, lon, dados.distancia_max_km)
    return LocalizacaoSalva(regiao=regiao, distancia_max_km=dados.distancia_max_km)


@router.put("/perfil/distancia", response_model=LocalizacaoSalva)
async def salvar_distancia(dados: Distancia, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Troca só o raio da barra deslizante, sem pedir a posição de novo."""
    await exigir_perfil(con, eu)
    if not await repo.salvar_distancia(con, eu, dados.distancia_max_km):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ative a localização para escolher uma distância.")
    regiao = (await repo.buscar_perfil(con, eu))["geohash"]
    return LocalizacaoSalva(regiao=regiao, distancia_max_km=dados.distancia_max_km)


@router.delete("/perfil/localizacao", status_code=status.HTTP_204_NO_CONTENT)
async def apagar_localizacao(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    await repo.salvar_localizacao(con, eu, None, None, None, None)
