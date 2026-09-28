"""Verificação de e-mail com código de 6 dígitos ou link de uso único (sem senha).

O e-mail nunca é gravado em texto: para achar a conta usamos HMAC-SHA256(EMAIL_PEPPER, e-mail);
para poder falar com a pessoa, o e-mail vai cifrado (ver contato.py). Código e token só em hash.
"""

import hashlib
import hmac
import json
import re
import secrets
from datetime import timedelta
from uuid import UUID

VALIDADE = timedelta(minutes=15)
MAX_TENTATIVAS = 5  # 6 dígitos + 5 tentativas = 1 chance em 200 mil por código
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


class VerificacaoInvalida(ValueError):
    pass


def normalizar_email(email: str) -> str:
    """Minúsculas e sem espaços: "Ana@Mail.com " e "ana@mail.com" são a mesma conta."""
    email = email.strip().lower()
    if len(email) > 254 or not _EMAIL.match(email):
        raise ValueError("E-mail inválido")
    return email


def hash_email(pepper: str, email: str) -> bytes:
    return hmac.new(pepper.encode(), b"email|" + email.encode(), hashlib.sha256).digest()


def _hash_codigo(pepper: str, verificacao_id: UUID, codigo: str) -> bytes:
    # Amarrado ao id: o mesmo código em outra verificação tem outro hash.
    return hmac.new(pepper.encode(), b"codigo|" + verificacao_id.bytes + codigo.encode(), hashlib.sha256).digest()


def _hash_token(token: str) -> bytes:
    return hashlib.sha256(b"token|" + token.encode()).digest()


async def criar(
    con, pepper: str, email_hash: bytes, email_cifrado: bytes, *, conta_id: UUID | None, dados: dict | None
):
    """Cria a verificação e devolve (id, código, token) em claro, só para ir no e-mail."""
    verificacao_id = await con.fetchval("SELECT gen_random_uuid()")
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    token = secrets.token_urlsafe(32)
    # Um pedido novo invalida os anteriores do mesmo e-mail (só o último código vale).
    await con.execute("DELETE FROM verificacoes_email WHERE email_hash = $1", email_hash)
    await con.execute(
        """INSERT INTO verificacoes_email
               (id, email_hash, email_cifrado, conta_id, dados, codigo_hash, token_hash, expira_em)
           VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, now() + $8::interval)""",
        verificacao_id,
        email_hash,
        email_cifrado,
        conta_id,
        json.dumps(dados) if dados is not None else None,
        _hash_codigo(pepper, verificacao_id, codigo),
        _hash_token(token),
        VALIDADE,
    )
    return verificacao_id, codigo, token


async def confirmar_codigo(con, pepper: str, verificacao_id: UUID, codigo: str):
    """Consome a verificação se o código bater. Errou demais: a verificação é apagada.

    O erro é lançado só DEPOIS de a transação gravar a tentativa: se fosse lançado dentro
    dela, o rollback desfaria o contador e o código teria tentativas ilimitadas.
    """
    async with con.transaction():
        linha = await con.fetchrow(
            "SELECT * FROM verificacoes_email WHERE id = $1 AND expira_em > now() FOR UPDATE", verificacao_id
        )
        if linha is None:
            erro = "Código expirado. Peça um novo."
        elif hmac.compare_digest(linha["codigo_hash"], _hash_codigo(pepper, verificacao_id, codigo)):
            await con.execute("DELETE FROM verificacoes_email WHERE id = $1", verificacao_id)
            return linha
        elif linha["tentativas"] + 1 >= MAX_TENTATIVAS:
            await con.execute("DELETE FROM verificacoes_email WHERE id = $1", verificacao_id)
            erro = "Código incorreto. Peça um novo código."
        else:
            await con.execute("UPDATE verificacoes_email SET tentativas = tentativas + 1 WHERE id = $1", verificacao_id)
            erro = "Código incorreto."
    raise VerificacaoInvalida(erro)


async def confirmar_token(con, token: str):
    linha = await con.fetchrow(
        "DELETE FROM verificacoes_email WHERE token_hash = $1 AND expira_em > now() RETURNING *", _hash_token(token)
    )
    if linha is None:
        raise VerificacaoInvalida("Link inválido ou expirado. Peça um novo.")
    return linha


async def apagar_expiradas(con) -> int:
    status = await con.execute("DELETE FROM verificacoes_email WHERE expira_em <= now()")
    return int(status.split()[-1])
