from pathlib import Path

import asyncpg
from fastapi import Request

DIR_DB = Path(__file__).resolve().parent.parent / "db"
DIR_MIGRACOES = DIR_DB / "migrations"
# Número arbitrário e fixo: garante que só uma réplica aplique migrações por vez.
_LOCK_MIGRACOES = 72_61_33_01


# asyncpg prepara cada consulta; a partir da 6ª execução o PostgreSQL pode trocar o plano sob
# medida por um "genérico", que não sabe quais filtros opcionais ($n IS NULL) valem. Na
# descoberta isso ignorava o índice por atividade: 61 ms em vez de 7 ms por busca (teste de
# carga, docs/carga/). Planejar sempre sob medida custa frações de milissegundo.
CONFIG_SESSAO = {"plan_cache_mode": "force_custom_plan"}


async def criar_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=10, server_settings=CONFIG_SESSAO)


async def migrar(pool: asyncpg.Pool) -> list[str]:
    """Aplica, em ordem e numa única transação, as migrações ainda não aplicadas.

    Cada arquivo de db/migrations roda uma única vez (registrado em schema_migrations).
    Nunca edite uma migração já publicada: crie a próxima (0006_..., 0007_...).
    O seed do catálogo é idempotente e roda a cada inicialização.
    """
    async with pool.acquire() as con, con.transaction():
        await con.execute("SELECT pg_advisory_xact_lock($1)", _LOCK_MIGRACOES)
        await con.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " versao text PRIMARY KEY, aplicada_em timestamptz NOT NULL DEFAULT now())"
        )
        aplicadas = {r["versao"] for r in await con.fetch("SELECT versao FROM schema_migrations")}
        novas = []
        for arquivo in sorted(DIR_MIGRACOES.glob("*.sql")):
            if arquivo.stem not in aplicadas:
                await con.execute(arquivo.read_text())
                await con.execute("INSERT INTO schema_migrations (versao) VALUES ($1)", arquivo.stem)
                novas.append(arquivo.stem)
        await con.execute((DIR_DB / "seed.sql").read_text())
        return novas


async def conexao(request: Request):
    async with request.app.state.pool.acquire() as con:
        yield con
