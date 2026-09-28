"""Todo o SQL da aplicação. Cada função recebe uma conexão asyncpg."""
from uuid import UUID

import asyncpg

from .matcher import PerfilMatch

_CATALOGOS = {"generos", "tags"}


class SlugDesconhecido(ValueError):
    def __init__(self, catalogo: str, slugs: set[str]):
        super().__init__(f"Valores inexistentes em '{catalogo}': {sorted(slugs)}")


async def ids_por_slug(con, catalogo: str, slugs: list[str]) -> dict[str, int]:
    assert catalogo in _CATALOGOS
    filtro_ativa = " AND ativa" if catalogo == "tags" else ""
    linhas = await con.fetch(f"SELECT slug, id FROM {catalogo} WHERE slug = ANY($1::text[]){filtro_ativa}", slugs)
    mapa = {l["slug"]: l["id"] for l in linhas}
    faltando = set(slugs) - mapa.keys()
    if faltando:
        raise SlugDesconhecido(catalogo, faltando)
    return mapa


async def slugs_por_id(con, catalogo: str, ids) -> dict[int, str]:
    assert catalogo in _CATALOGOS
    linhas = await con.fetch(f"SELECT id, slug FROM {catalogo} WHERE id = ANY($1::int[])", list(set(ids)))
    return {l["id"]: l["slug"] for l in linhas}


async def listar_catalogo(con, catalogo: str):
    assert catalogo in _CATALOGOS
    if catalogo == "tags":
        return await con.fetch("SELECT slug, rotulo, categoria FROM tags WHERE ativa ORDER BY categoria, rotulo")
    return await con.fetch("SELECT slug, rotulo FROM generos ORDER BY id")


def para_perfil_match(linha) -> PerfilMatch:
    return PerfilMatch.criar(
        linha["conta_id"], linha["genero_id"], linha["busca_por"],
        linha["tags_quero"], linha["tags_curioso"], linha["tags_limite"],
    )


# ---------- contas ----------

async def existe_conta(con, conta_id: UUID) -> bool:
    return await con.fetchval("SELECT EXISTS (SELECT 1 FROM contas WHERE id = $1)", conta_id)


async def criar_conta(con, handle: str, senha_hash: str) -> UUID | None:
    try:
        return await con.fetchval(
            "INSERT INTO contas (handle, senha_hash, adulto_confirmado_em, consentimento_em)"
            " VALUES ($1, $2, now(), now()) RETURNING id",
            handle, senha_hash,
        )
    except asyncpg.UniqueViolationError:
        return None


async def buscar_conta_por_handle(con, handle: str):
    return await con.fetchrow("SELECT id, senha_hash, token_versao, situacao FROM contas WHERE handle = $1", handle)


async def invalidar_sessoes(con, conta_id: UUID) -> None:
    await con.execute("UPDATE contas SET token_versao = token_versao + 1 WHERE id = $1", conta_id)


async def excluir_conta(con, conta_id: UUID) -> None:
    # ON DELETE CASCADE remove perfil, curtidas e bloqueios: exclusão real, não soft delete.
    await con.execute("DELETE FROM contas WHERE id = $1", conta_id)


# ---------- perfis ----------

async def salvar_perfil(con, conta_id: UUID, *, nome_exibicao, bio, genero_id, busca_por,
                        tags_quero, tags_curioso, tags_limite, visivel) -> None:
    await con.execute(
        """
        INSERT INTO perfis (conta_id, nome_exibicao, bio, genero_id, busca_por,
                            tags_quero, tags_curioso, tags_limite, visivel, ativo_em)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now())
        ON CONFLICT (conta_id) DO UPDATE SET
            nome_exibicao = EXCLUDED.nome_exibicao, bio = EXCLUDED.bio,
            genero_id = EXCLUDED.genero_id, busca_por = EXCLUDED.busca_por,
            tags_quero = EXCLUDED.tags_quero, tags_curioso = EXCLUDED.tags_curioso,
            tags_limite = EXCLUDED.tags_limite, visivel = EXCLUDED.visivel, ativo_em = now()
        """,
        conta_id, nome_exibicao, bio, genero_id, busca_por, tags_quero, tags_curioso, tags_limite, visivel,
    )


async def buscar_perfil(con, conta_id: UUID):
    return await con.fetchrow("SELECT * FROM perfis WHERE conta_id = $1", conta_id)


async def marcar_atividade(con, conta_id: UUID) -> None:
    await con.execute("UPDATE perfis SET ativo_em = now() WHERE conta_id = $1", conta_id)


_SEM_BLOQUEIO = """
    NOT EXISTS (
        SELECT 1 FROM bloqueios b
        WHERE (b.bloqueador_id = $1 AND b.bloqueado_id = p.conta_id)
           OR (b.bloqueador_id = p.conta_id AND b.bloqueado_id = $1)
    )
"""


async def buscar_perfil_visivel(con, observador: UUID, alvo: UUID):
    """Perfil de `alvo`, se estiver visível, com conta ativa e sem bloqueio em nenhuma direção."""
    return await con.fetchrow(
        f"""SELECT p.* FROM perfis p JOIN contas ct ON ct.id = p.conta_id AND ct.situacao = 'ativa'
            WHERE p.conta_id = $2 AND p.visivel AND {_SEM_BLOQUEIO}""",
        observador, alvo,
    )


async def salvar_localizacao(con, conta_id: UUID, geohash, lat, lon, distancia_max_km) -> bool:
    status = await con.execute(
        "UPDATE perfis SET geohash = $2, lat_aprox = $3, lon_aprox = $4, distancia_max_km = $5 WHERE conta_id = $1",
        conta_id, geohash, lat, lon, distancia_max_km,
    )
    return status != "UPDATE 0"


# ---------- interações ----------

async def curtir(con, de: UUID, para: UUID) -> bool:
    """Registra a curtida e diz se ela formou uma conexão (curtida recíproca)."""
    async with con.transaction():
        await con.execute(
            "INSERT INTO curtidas (de_id, para_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", de, para
        )
        return await con.fetchval(
            "SELECT EXISTS (SELECT 1 FROM curtidas WHERE de_id = $1 AND para_id = $2)", para, de
        )


async def bloquear(con, de: UUID, para: UUID) -> None:
    """Bloqueio apaga tudo o que ligava as duas pessoas: conexão, conversa e acesso a fotos."""
    async with con.transaction():
        await con.execute(
            "INSERT INTO bloqueios (bloqueador_id, bloqueado_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", de, para
        )
        for tabela, a, b in (("curtidas", "de_id", "para_id"), ("mensagens", "de_id", "para_id"),
                             ("acessos_fotos", "dono_id", "visualizador_id")):
            await con.execute(
                f"DELETE FROM {tabela} WHERE ({a} = $1 AND {b} = $2) OR ({a} = $2 AND {b} = $1)", de, para
            )


async def sao_conexao(con, a: UUID, b: UUID) -> bool:
    """Curtida recíproca, sem bloqueio, e as duas contas ativas."""
    return await con.fetchval(
        """SELECT EXISTS (
               SELECT 1 FROM curtidas x JOIN curtidas y ON y.de_id = x.para_id AND y.para_id = x.de_id
               JOIN contas ca ON ca.id = x.de_id AND ca.situacao = 'ativa'
               JOIN contas cb ON cb.id = x.para_id AND cb.situacao = 'ativa'
               WHERE x.de_id = $1 AND x.para_id = $2
                 AND NOT EXISTS (SELECT 1 FROM bloqueios b WHERE (b.bloqueador_id = $1 AND b.bloqueado_id = $2)
                                                            OR (b.bloqueador_id = $2 AND b.bloqueado_id = $1)))""",
        a, b,
    )


async def listar_conexoes(con, eu: UUID):
    return await con.fetch(
        f"""
        SELECT p.* FROM curtidas minha
        JOIN curtidas deles ON deles.de_id = minha.para_id AND deles.para_id = minha.de_id
        JOIN perfis p ON p.conta_id = minha.para_id
        JOIN contas ct ON ct.id = p.conta_id AND ct.situacao = 'ativa'
        WHERE minha.de_id = $1 AND {_SEM_BLOQUEIO}
        ORDER BY GREATEST(minha.criado_em, deles.criado_em) DESC
        """,
        eu,
    )
