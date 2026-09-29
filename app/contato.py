"""E-mail da pessoa: cifrado no banco, aberto só para enviar um aviso, e todo envio registrado.

- Busca/login: `email_hash` (HMAC, em verificacao.py). Não precisa abrir nada.
- Falar com a pessoa: `email_cifrado` (AES-256-GCM com CHAVE_EMAIL). A decifragem acontece só
  dentro de `enviar_aviso`; o endereço nunca é devolvido pela API nem mostrado a moderadores.
"""

from uuid import UUID

from .cripto import Cifrador
from .email import Mensagem

DOMINIO = b"matchmaking/email/v1"


def criar_cifrador(chave: str, anteriores: tuple[str, ...] = ()) -> Cifrador:
    return Cifrador(chave, DOMINIO, anteriores)


def _contexto(email_hash: bytes) -> bytes:
    # Amarra o texto cifrado ao hash da própria conta: trocar o blob entre contas não funciona.
    return b"email|" + email_hash


def cifrar_email(cif: Cifrador, email: str, email_hash: bytes) -> bytes:
    return cif.cifrar(email, _contexto(email_hash))


def decifrar_email(cif: Cifrador, blob: bytes, email_hash: bytes) -> str:
    return cif.decifrar(blob, _contexto(email_hash))


def mascarar(email: str) -> str:
    """ana.souza@gmail.com -> a****@gmail.com. Sempre 4 asteriscos: não revela nem o tamanho."""
    usuario, dominio = email.split("@", 1)
    return usuario[0] + "****@" + dominio


async def email_da_conta(con, cif: Cifrador, conta_id: UUID) -> str | None:
    linha = await con.fetchrow("SELECT email_hash, email_cifrado FROM contas WHERE id = $1", conta_id)
    if linha is None or linha["email_cifrado"] is None:
        return None
    return decifrar_email(cif, linha["email_cifrado"], linha["email_hash"])


def mensagem_de_aviso(para: str, assunto: str, texto: str) -> Mensagem:
    return Mensagem(
        para=para,
        assunto=assunto,
        texto=f"{texto}\n\n—\nVocê recebeu este e-mail porque ele é o e-mail de acesso da sua conta.",
    )


async def enviar_aviso(
    con, cif: Cifrador, carteiro, *, conta_id: UUID, assunto: str, texto: str, enviado_por: str
) -> bool:
    """Envia um aviso para o e-mail da conta. False se a conta não existe ou não tem e-mail cifrado."""
    email = await email_da_conta(con, cif, conta_id)
    if email is None:
        return False
    await carteiro.enviar(mensagem_de_aviso(email, assunto, texto))
    await con.execute(
        "INSERT INTO contatos_log (conta_id, enviado_por, assunto) VALUES ($1, $2, $3)",
        conta_id,
        enviado_por[:60],
        assunto[:120],
    )
    return True
