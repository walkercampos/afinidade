from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.staticfiles import StaticFiles

from . import repository as repo
from .config import carregar_config
from .db import aplicar_schema, conexao, criar_pool
from .matcher import PerfilMatch, calcular_match, score_mutuo
from .schemas import (
    Candidato, Compatibilidade, ItemCatalogo, Login, PerfilEntrada, PerfilProprio, PerfilPublico,
    Registro, ResultadoCurtida, Simulacao, TagsInteresses, Token,
)
from .ratelimit import exigir_limite, ip_do_cliente
from .security import (
    HASH_FALSO, apagar_cookie_sessao, conta_atual, emitir_token, gerar_hash_senha, gravar_cookie_sessao,
    verificar_senha,
)

DIR_STATIC = Path(__file__).resolve().parent.parent / "static"
CONFIG = carregar_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.config = CONFIG
    app.state.pool = await criar_pool(CONFIG.database_url)
    await aplicar_schema(app.state.pool)
    yield
    await app.state.pool.close()


# Em produção a documentação interativa fica desligada: menos superfície exposta.
_docs = {} if not CONFIG.producao else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="Matchmaking API", version="0.2.0", lifespan=lifespan, **_docs)
api = APIRouter(prefix="/api")

_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
    "font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)


@app.middleware("http")
async def cabecalhos_de_seguranca(request: Request, call_next):
    response = await call_next(request)
    h = response.headers
    # /docs (só em dev) carrega Swagger de CDN e não funcionaria com a CSP estrita.
    if not request.url.path.startswith(("/docs", "/redoc")):
        h["Content-Security-Policy"] = _CSP
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=(), interest-cohort=()"
    h["Cross-Origin-Opener-Policy"] = "same-origin"
    h["Cross-Origin-Resource-Policy"] = "same-origin"
    if request.url.path.startswith("/api"):
        h["Cache-Control"] = "no-store"
    if CONFIG.producao:
        h["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


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

def _iniciar_sessao(response: Response, conta_id: UUID, versao: int) -> Token:
    token = emitir_token(conta_id, versao, CONFIG.jwt_secret, CONFIG.jwt_expira_min)
    gravar_cookie_sessao(response, token, CONFIG)
    return Token(access_token=token)


@api.post("/auth/registro", response_model=Token, status_code=status.HTTP_201_CREATED)
async def registrar(dados: Registro, request: Request, response: Response, con=Depends(conexao)):
    exigir_limite("auth", CONFIG.limite_auth_por_min, ip_do_cliente(request))
    conta_id = await repo.criar_conta(con, dados.handle, gerar_hash_senha(dados.senha))
    if conta_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Handle já em uso")
    return _iniciar_sessao(response, conta_id, 0)


@api.post("/auth/login", response_model=Token)
async def login(dados: Login, request: Request, response: Response, con=Depends(conexao)):
    exigir_limite("auth", CONFIG.limite_auth_por_min, ip_do_cliente(request))
    # Também por handle: impede força bruta distribuída em vários IPs contra uma conta.
    exigir_limite("login-handle", CONFIG.limite_auth_por_min, dados.handle)
    conta = await repo.buscar_conta_por_handle(con, dados.handle)
    senha_ok = verificar_senha(dados.senha, conta["senha_hash"] if conta else HASH_FALSO)
    if conta is None or not senha_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais inválidas")
    return _iniciar_sessao(response, conta["id"], conta["token_versao"])


@api.post("/auth/sair", status_code=status.HTTP_204_NO_CONTENT)
async def sair(response: Response, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    """Encerra a sessão em todos os dispositivos."""
    await repo.invalidar_sessoes(con, eu)
    apagar_cookie_sessao(response, CONFIG)


@api.delete("/conta", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_conta(response: Response, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    await repo.excluir_conta(con, eu)
    apagar_cookie_sessao(response, CONFIG)


# ---------- catálogo ----------

@api.get("/catalogo/generos", response_model=list[ItemCatalogo])
async def catalogo_generos(con=Depends(conexao)):
    return [dict(l) for l in await repo.listar_catalogo(con, "generos")]


@api.get("/catalogo/tags", response_model=list[ItemCatalogo])
async def catalogo_tags(con=Depends(conexao)):
    return [dict(l) for l in await repo.listar_catalogo(con, "tags")]


# ---------- perfil próprio ----------

@api.put("/perfil", response_model=PerfilProprio)
async def salvar_perfil(dados: PerfilEntrada, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    t = dados.tags_interesses
    try:
        generos = await repo.ids_por_slug(con, "generos", [dados.genero, *dados.busca_por])
        tags = await repo.ids_por_slug(con, "tags", [*t.quero, *t.curioso, *t.limite_absoluto])
    except repo.SlugDesconhecido as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    await repo.salvar_perfil(
        con, eu, nome_exibicao=dados.nome_exibicao, bio=dados.bio, visivel=dados.visivel,
        genero_id=generos[dados.genero], busca_por=sorted({generos[g] for g in dados.busca_por}),
        tags_quero=[tags[s] for s in t.quero], tags_curioso=[tags[s] for s in t.curioso],
        tags_limite=[tags[s] for s in t.limite_absoluto],
    )
    return await ler_perfil(eu, con)


@api.get("/perfil", response_model=PerfilProprio)
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

@api.get("/descobrir", response_model=list[Candidato])
async def descobrir(limite: int = Query(20, ge=1, le=100), eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    meu = await _meu_perfil(con, eu)
    await repo.marcar_atividade(con, eu)
    linhas = await repo.buscar_candidatos(con, meu, CONFIG.candidatos_prefetch)

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


@api.get("/perfis/{alvo}", response_model=Candidato)
async def ver_perfil(alvo: UUID, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    meu = await _meu_perfil(con, eu)
    outro = await _perfil_alvo(con, eu, alvo)
    cat = await _Catalogo.para(con, [meu, outro])
    return Candidato(
        perfil=cat.publico(outro),
        compatibilidade=_compatibilidade(repo.para_perfil_match(meu), repo.para_perfil_match(outro), cat),
    )


@api.post("/perfis/{alvo}/curtir", response_model=ResultadoCurtida)
async def curtir(alvo: UUID, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    meu = await _meu_perfil(con, eu)
    outro = await _perfil_alvo(con, eu, alvo)
    # Só é possível curtir quem passa pelas camadas 1 e 2: ninguém recebe interesse
    # de quem não busca, nem de quem quer praticar algo que é seu limite absoluto.
    r = calcular_match(repo.para_perfil_match(meu), repo.para_perfil_match(outro))
    if not r.match_valido:
        raise HTTPException(status.HTTP_403_FORBIDDEN, r.motivo)
    return ResultadoCurtida(conexao=await repo.curtir(con, eu, alvo))


@api.post("/perfis/{alvo}/bloquear", status_code=status.HTTP_204_NO_CONTENT)
async def bloquear(alvo: UUID, eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    if alvo == eu:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Operação inválida sobre o próprio perfil")
    if await repo.buscar_perfil(con, alvo) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil não encontrado")
    await repo.bloquear(con, eu, alvo)


@api.get("/conexoes", response_model=list[PerfilPublico])
async def conexoes(eu: UUID = Depends(conta_atual), con=Depends(conexao)):
    linhas = await repo.listar_conexoes(con, eu)
    cat = await _Catalogo.para(con, linhas)
    return [cat.publico(l) for l in linhas]


# ---------- utilitário ----------

@api.post("/match/simular")
async def simular(dados: Simulacao):
    """Roda o algoritmo sobre dois payloads no formato do script original (sem banco)."""
    a = PerfilMatch.de_dict(dados.usuario_a.model_dump())
    b = PerfilMatch.de_dict(dados.usuario_b.model_dump())
    return {**calcular_match(a, b).to_dict(), "score_mutuo": score_mutuo(a, b)}


app.include_router(api)
# Front-end estático no mesmo domínio: sem CORS, e o cookie SameSite=Strict funciona.
app.mount("/", StaticFiles(directory=DIR_STATIC, html=True), name="static")
