from pathlib import Path

import asyncpg
from fastapi import Request

DIR_DB = Path(__file__).resolve().parent.parent / "db"


async def criar_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=10)


async def aplicar_schema(pool: asyncpg.Pool) -> None:
    """Idempotente. Em produção prefira uma ferramenta de migração (Alembic, sqitch, dbmate)."""
    async with pool.acquire() as con:
        await con.execute((DIR_DB / "schema.sql").read_text())
        await con.execute((DIR_DB / "seed.sql").read_text())


async def conexao(request: Request):
    async with request.app.state.pool.acquire() as con:
        yield con
