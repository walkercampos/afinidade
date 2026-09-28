"""Tarefas administrativas pela linha de comando (rodam com as mesmas variáveis de ambiente da API).

    python -m app.admin moderador <apelido>        # dá o papel de moderador(a)
    python -m app.admin usuario <apelido>          # remove o papel
    python -m app.admin migrar                     # aplica migrações pendentes
"""
import asyncio
import sys

from .config import config
from .db import criar_pool, migrar


async def _definir_papel(handle: str, papel: str) -> int:
    pool = await criar_pool(config().database_url)
    try:
        status = await pool.execute("UPDATE contas SET papel = $2 WHERE handle = $1", handle.lower(), papel)
    finally:
        await pool.close()
    if status == "UPDATE 0":
        print(f"Conta '{handle}' não encontrada", file=sys.stderr)
        return 1
    print(f"'{handle}' agora é {papel}")
    return 0


async def _migrar() -> int:
    pool = await criar_pool(config().database_url)
    try:
        novas = await migrar(pool)
    finally:
        await pool.close()
    print("Aplicadas: " + (", ".join(novas) if novas else "nenhuma (banco já atualizado)"))
    return 0


def main(argv: list[str]) -> int:
    match argv:
        case ["moderador" | "usuario" as papel, handle]:
            return asyncio.run(_definir_papel(handle, papel))
        case ["migrar"]:
            return asyncio.run(_migrar())
        case _:
            print(__doc__, file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
