"""Tarefas administrativas pela linha de comando (rodam com as mesmas variáveis de ambiente da API).

python -m app.admin moderador <apelido>        # dá o papel de moderador(a)
python -m app.admin usuario <apelido>          # remove o papel
python -m app.admin migrar                     # aplica migrações pendentes
python -m app.admin recifrar                   # depois de trocar uma chave (docs/operacao.md)
"""

import asyncio
import sys

from . import contato
from .config import config
from .db import criar_pool, migrar
from .email import criar_carteiro


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


async def _recifrar() -> int:
    from . import contato, encontros, rotacao
    from .cripto import Cifrador

    cfg = config()
    cifradores = {
        "mensagens": Cifrador(cfg.chave_mensagens, anteriores=cfg.chaves_mensagens_anteriores),
        "email": contato.criar_cifrador(cfg.chave_email, cfg.chaves_email_anteriores),
        "encontros": encontros.criar_cifrador(cfg.chave_mensagens, cfg.chaves_mensagens_anteriores),
    }
    pool = await criar_pool(cfg.database_url)
    try:
        async with pool.acquire() as con:
            feitos = await rotacao.recifrar(con, cifradores)
    finally:
        await pool.close()
    for coluna, n in feitos.items():
        print(f"{coluna}: {n} recifrado(s)")
    print("Pronto. Rode de novo: quando tudo der 0, a chave antiga pode sair de *_ANTERIORES.")
    return 0


async def _avisar(handle: str, assunto: str, mensagem: str) -> int:
    cfg = config()
    pool = await criar_pool(cfg.database_url)
    try:
        async with pool.acquire() as con:
            conta_id = await con.fetchval("SELECT id FROM contas WHERE handle = $1", handle.lower())
            enviado = conta_id is not None and await contato.enviar_aviso(
                con,
                contato.criar_cifrador(cfg.chave_email),
                criar_carteiro(cfg.email),
                conta_id=conta_id,
                assunto=assunto,
                texto=mensagem,
                enviado_por="cli",
            )
    finally:
        await pool.close()
    if not enviado:
        print(f"Conta '{handle}' não encontrada ou sem e-mail cadastrado", file=sys.stderr)
        return 1
    print(f"Aviso enviado para '{handle}' (registrado em contatos_log)")
    return 0


def main(argv: list[str]) -> int:
    match argv:
        case ["moderador" | "usuario" as papel, handle]:
            return asyncio.run(_definir_papel(handle, papel))
        case ["migrar"]:
            return asyncio.run(_migrar())
        case ["recifrar"]:
            return asyncio.run(_recifrar())
        case ["avisar", handle, assunto, mensagem]:
            return asyncio.run(_avisar(handle, assunto, mensagem))
        case _:
            print(__doc__, file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
