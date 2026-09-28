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
    return await con.fetchrow("SELECT id, senha_hash, token_versao FROM contas WHERE handle = $1", handle)


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
    """Perfil de `alvo`, se estiver visível e não houver bloqueio em nenhuma direção."""
    return await con.fetchrow(
        f"SELECT p.* FROM perfis p WHERE p.conta_id = $2 AND p.visivel AND {_SEM_BLOQUEIO}",
        observador, alvo,
    )


async def buscar_candidatos(con, eu, limite: int):
    """Camadas 1 e 2 do algoritmo executadas no banco (com índices GIN).

    Retorna apenas perfis que:
      - têm um gênero que eu busco, e buscam o meu gênero;
      - não QUEREM nada que seja limite meu, e não têm limite em nada que eu QUERO;
      - não estão bloqueados (em nenhuma direção) nem já foram curtidos por mim.
    """
    return await con.fetch(
        f"""
        SELECT p.* FROM perfis p
        WHERE p.visivel
          AND p.conta_id <> $1
          AND p.genero_id = ANY($2::smallint[])
          AND p.busca_por @> ARRAY[$3::smallint]
          AND NOT (p.tags_quero && $4::integer[])
          AND NOT (p.tags_limite && $5::integer[])
          AND {_SEM_BLOQUEIO}
          AND NOT EXISTS (SELECT 1 FROM curtidas c WHERE c.de_id = $1 AND c.para_id = p.conta_id)
        ORDER BY p.ativo_em DESC
        LIMIT $6
        """,
        eu["conta_id"], eu["busca_por"], eu["genero_id"], eu["tags_limite"], eu["tags_quero"], limite,
    )


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
    async with con.transaction():
        await con.execute(
            "INSERT INTO bloqueios (bloqueador_id, bloqueado_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", de, para
        )
        await con.execute(
            "DELETE FROM curtidas WHERE (de_id = $1 AND para_id = $2) OR (de_id = $2 AND para_id = $1)", de, para
        )


async def listar_conexoes(con, eu: UUID):
    return await con.fetch(
        f"""
        SELECT p.* FROM curtidas minha
        JOIN curtidas deles ON deles.de_id = minha.para_id AND deles.para_id = minha.de_id
        JOIN perfis p ON p.conta_id = minha.para_id
        WHERE minha.de_id = $1 AND {_SEM_BLOQUEIO}
        ORDER BY GREATEST(minha.criado_em, deles.criado_em) DESC
        """,
        eu,
    )
