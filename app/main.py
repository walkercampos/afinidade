from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, status

from . import repository as repo
from .config import carregar_config
from .db import aplicar_schema, conexao, criar_pool
from .matcher import PerfilMatch, calcular_match, score_mutuo
from .schemas import (
    Candidato, Compatibilidade, ItemCatalogo, Login, PerfilEntrada, PerfilProprio, PerfilPublico,
    Registro, ResultadoCurtida, Simulacao, TagsInteresses, Token,
)
from .security import conta_atual, emitir_token, gerar_hash_senha, verificar_senha


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.config = carregar_config()
    app.state.pool = await criar_pool(app.state.config.database_url)
    await aplicar_schema(app.state.pool)
    yield
    await app.state.pool.close()


app = FastAPI(title="Matchmaking API", version="0.1.0", lifespan=lifespan)


# ---------- helpers ----------

class _Catalogo:
    """Resolve IDs -> slugs de gêneros e tags para um lote de perfis com duas consultas."""

    def __init__(self, generos: dict[int, str], tags: dict[int, str]):
        self.generos, self.tags = generos, tags

    @classmethod
    async def para(cls, con, linhas):
        ids_genero = {g for l in linhas for g in [l["genero_id"], *l["busca_por"]]}
        ids_tag = {t for l in linhas for t in [*l["tags_quero"], *l["tags_curioso"], *l["tags_limite"]]}
        return cls(await repo.slugs_por_id(con, "generos", ids_genero), await repo.slugs_por_id(con, "tags", ids_tag))

    def tags_de(self, ids) -> list[str]:
        return sorted(self.tags[i] for i in ids)

    def publico(self, linha) -> PerfilPublico:
        return PerfilPublico(
            id=linha["conta_id"], nome_exibicao=linha["nome_exibicao"], bio=linha["bio"],
            genero=self.generos[linha["genero_id"]],
            quero=self.tags_de(linha["tags_quero"]), curioso=self.tags_de(linha["tags_curioso"]),
        )


def _compatibilidade(eu: PerfilMatch, outro: PerfilMatch, cat: _Catalogo) -> Compatibilidade:
    r = calcular_match(eu, outro)
    return Compatibilidade(
        match_valido=r.match_valido, score_porcentagem=r.score_porcentagem,
        score_mutuo=score_mutuo(eu, outro), tags_em_comum=cat.tags_de(r.tags_em_comum), motivo=r.motivo,
    )


async def _meu_perfil(con, conta_id: UUID):
    perfil = await repo.buscar_perfil(con, conta_id)
    if perfil is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Crie seu perfil em PUT /perfil primeiro")
    return perfil


async def _perfil_alvo(con, eu: UUID, alvo: UUID):
    if alvo == eu:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Operação inválida sobre o próprio perfil")
    perfil = await repo.buscar_perfil_visivel(con, eu, alvo)
    if perfil is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil não encontrado")
    return perfil


# ---------- autenticação ----------

@app.post("/auth/registro", response_model=Token, status_code=status.HTTP_201_CREATED)
async def registrar(dados: Registro, con=Depends(conexao)):
    conta_id = await repo.criar_conta(con, dados.handle, gerar_hash_senha(dados.senha))
    if conta_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Handle já em uso")
    cfg = app.state.config
    return Token(access_token=emitir_token(conta_id, cfg.jwt_secret, cfg.jwt_expira_min))


@app.post("/auth/login", response_model=Token)
async def login(dados: Login, con=Depends(conexao)):
    conta = await repo.buscar_conta_por_handle(con, dados.handle)
    if conta is None or not verificar_senha(dados.senha, conta["senha_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais inválidas")
    cfg = app.state.config
    return Token(access_token=emitir_token(conta["id"], cfg.jwt_secret, cfg.jwt_expira_min))


@app.delete("/conta", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_conta(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    await repo.excluir_conta(con, eu)


# ---------- catálogo ----------

@app.get("/catalogo/generos", response_model=list[ItemCatalogo])
async def catalogo_generos(con=Depends(conexao)):
    return [dict(l) for l in await repo.listar_catalogo(con, "generos")]


@app.get("/catalogo/tags", response_model=list[ItemCatalogo])
async def catalogo_tags(con=Depends(conexao)):
    return [dict(l) for l in await repo.listar_catalogo(con, "tags")]


# ---------- perfil próprio ----------

@app.put("/perfil", response_model=PerfilProprio)
async def salvar_perfil(dados: PerfilEntrada, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    t = dados.tags_interesses
    try:
        generos = await repo.ids_por_slug(con, "generos", [dados.genero, *dados.busca_por])
        tags = await repo.ids_por_slug(con, "tags", [*t.quero, *t.curioso, *t.limite_absoluto])
    except repo.SlugDesconhecido as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    await repo.salvar_perfil(
        con, eu, nome_exibicao=dados.nome_exibicao, bio=dados.bio, visivel=dados.visivel,
        genero_id=generos[dados.genero], busca_por=sorted({generos[g] for g in dados.busca_por}),
        tags_quero=[tags[s] for s in t.quero], tags_curioso=[tags[s] for s in t.curioso],
        tags_limite=[tags[s] for s in t.limite_absoluto],
    )
    return await ler_perfil(eu, con)


@app.get("/perfil", response_model=PerfilProprio)
async def ler_perfil(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    p = await repo.buscar_perfil(con, eu)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil ainda não criado")
    cat = await _Catalogo.para(con, [p])
    return PerfilProprio(
        id=eu, nome_exibicao=p["nome_exibicao"], bio=p["bio"], visivel=p["visivel"],
        genero=cat.generos[p["genero_id"]], busca_por=sorted(cat.generos[g] for g in p["busca_por"]),
        tags_interesses=TagsInteresses(
            quero=cat.tags_de(p["tags_quero"]), curioso=cat.tags_de(p["tags_curioso"]),
            limite_absoluto=cat.tags_de(p["tags_limite"]),
        ),
    )


# ---------- descoberta e conexões ----------

@app.get("/descobrir", response_model=list[Candidato])
async def descobrir(limite: int = Query(20, ge=1, le=100), eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    meu = await _meu_perfil(con, eu)
    await repo.marcar_atividade(con, eu)
    linhas = await repo.buscar_candidatos(con, meu, app.state.config.candidatos_prefetch)

    eu_match = repo.para_perfil_match(meu)
    pontuados = []
    for linha in linhas:
        outro = repo.para_perfil_match(linha)
        r = calcular_match(eu_match, outro)
        if r.match_valido:  # o SQL já filtrou; mantido como rede de segurança
            pontuados.append((score_mutuo(eu_match, outro), r.score_porcentagem, linha))
    # Linhas vêm ordenadas por atividade; sort estável preserva isso como desempate.
    pontuados.sort(key=lambda x: (x[0], x[1]), reverse=True)
    escolhidos = [linha for *_, linha in pontuados[:limite]]

    cat = await _Catalogo.para(con, escolhidos)
    return [
        Candidato(perfil=cat.publico(l), compatibilidade=_compatibilidade(eu_match, repo.para_perfil_match(l), cat))
        for l in escolhidos
    ]


@app.get("/perfis/{alvo}", response_model=Candidato)
async def ver_perfil(alvo: UUID, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    meu = await _meu_perfil(con, eu)
    outro = await _perfil_alvo(con, eu, alvo)
    cat = await _Catalogo.para(con, [meu, outro])
    return Candidato(
        perfil=cat.publico(outro),
        compatibilidade=_compatibilidade(repo.para_perfil_match(meu), repo.para_perfil_match(outro), cat),
    )


@app.post("/perfis/{alvo}/curtir", response_model=ResultadoCurtida)
async def curtir(alvo: UUID, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    meu = await _meu_perfil(con, eu)
    outro = await _perfil_alvo(con, eu, alvo)
    # Só é possível curtir quem passa pelas camadas 1 e 2: ninguém recebe interesse
    # de quem não busca, nem de quem quer praticar algo que é seu limite absoluto.
    r = calcular_match(repo.para_perfil_match(meu), repo.para_perfil_match(outro))
    if not r.match_valido:
        raise HTTPException(status.HTTP_403_FORBIDDEN, r.motivo)
    return ResultadoCurtida(conexao=await repo.curtir(con, eu, alvo))


@app.post("/perfis/{alvo}/bloquear", status_code=status.HTTP_204_NO_CONTENT)
async def bloquear(alvo: UUID, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    if alvo == eu:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Operação inválida sobre o próprio perfil")
    if await repo.buscar_perfil(con, alvo) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil não encontrado")
    await repo.bloquear(con, eu, alvo)


@app.get("/conexoes", response_model=list[PerfilPublico])
async def conexoes(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    linhas = await repo.listar_conexoes(con, eu)
    cat = await _Catalogo.para(con, linhas)
    return [cat.publico(l) for l in linhas]


# ---------- utilitário ----------

@app.post("/match/simular")
async def simular(dados: Simulacao):
    """Roda o algoritmo sobre dois payloads no formato do script original (sem banco)."""
    a = PerfilMatch.de_dict(dados.usuario_a.model_dump())
    b = PerfilMatch.de_dict(dados.usuario_b.model_dump())
    return {**calcular_match(a, b).to_dict(), "score_mutuo": score_mutuo(a, b)}
