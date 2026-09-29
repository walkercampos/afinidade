"""Recifragem após troca de chave (Parte 4 do plano).

Procedimento completo em docs/operacao.md ("Trocar uma chave de cifragem"):
1. A chave atual vai para CHAVE_*_ANTERIORES e uma chave nova entra em CHAVE_*; deploy.
   A partir daí tudo novo é cifrado com a chave nova, e o antigo continua legível.
2. `python -m app.admin recifrar` passa por todas as colunas cifradas e reescreve com a chave
   nova o que ainda estava na antiga. Pode rodar com o app no ar e pode ser repetido.
3. Quando o comando informar zero pendências, a chave antiga pode sair de CHAVE_*_ANTERIORES.
"""

from collections.abc import Callable
from dataclasses import dataclass

from . import contato, encontros, fotos, mensagens, moderacao
from .cripto import Cifrador


@dataclass(frozen=True)
class Coluna:
    tabela: str
    chave: str  # coluna da chave primária
    coluna: str
    extras: tuple[str, ...]  # colunas necessárias para montar o contexto
    contexto: Callable  # linha -> bytes
    cifrador: str  # "mensagens" | "email" | "encontros"


def _msg(r):
    return mensagens._contexto(r["de_id"], r["para_id"])


def _evidencia(r):
    return moderacao._contexto_evidencia(r["denunciado_id"])


def _email(r):
    return contato._contexto(r["email_hash"])


COLUNAS = (
    Coluna("mensagens", "id", "conteudo", ("de_id", "para_id"), _msg, "mensagens"),
    Coluna("fotos", "id", "nitida", (), lambda r: fotos._contexto(r["id"], "nitida"), "mensagens"),
    Coluna("fotos", "id", "borrada", (), lambda r: fotos._contexto(r["id"], "borrada"), "mensagens"),
    Coluna("denuncias", "id", "evidencias", ("denunciado_id",), _evidencia, "mensagens"),
    Coluna("encontros", "id", "detalhes", (), lambda r: encontros._contexto(r["id"], b"detalhes"), "encontros"),
    Coluna("encontros", "id", "contato_confianca", (), lambda r: encontros._contexto(r["id"], b"contato"), "encontros"),
    Coluna("contas", "id", "email_cifrado", ("email_hash",), _email, "email"),
    Coluna("verificacoes_email", "id", "email_cifrado", ("email_hash",), _email, "email"),
)

LOTE = 500


async def recifrar(con, cifradores: dict[str, Cifrador]) -> dict[str, int]:
    """Reescreve com a chave atual o que ainda estava cifrado com uma chave anterior.
    Devolve quantos valores foram recifrados por tabela.coluna."""
    resultado = {}
    for c in COLUNAS:
        cif = cifradores[c.cifrador]
        total, ultimo = 0, None
        campos = ", ".join(dict.fromkeys((c.chave, c.coluna, *c.extras)))
        while True:
            linhas = await con.fetch(
                f"""SELECT {campos} FROM {c.tabela}
                    WHERE {c.coluna} IS NOT NULL AND ($1::text IS NULL OR {c.chave}::text > $1)
                    ORDER BY {c.chave}::text LIMIT {LOTE}""",
                ultimo,
            )
            if not linhas:
                break
            for linha in linhas:
                novo = cif.recifrar_bytes(linha[c.coluna], c.contexto(linha))
                if novo is not None:
                    # Condicional: se o valor mudou nesse meio-tempo (app no ar), não sobrescreve.
                    await con.execute(
                        f"UPDATE {c.tabela} SET {c.coluna} = $1 WHERE {c.chave} = $2 AND {c.coluna} = $3",
                        novo,
                        linha[c.chave],
                        linha[c.coluna],
                    )
                    total += 1
            ultimo = str(linhas[-1][c.chave])
        resultado[f"{c.tabela}.{c.coluna}"] = total
    return resultado
