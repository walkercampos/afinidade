"""Passkeys (WebAuthn): login sem senha, resistente a phishing, sem e-mail e sem terceiros.

Como funciona, em uma frase: o servidor manda um desafio aleatório; o aparelho da pessoa assina
esse desafio com uma chave privada que nunca sai dele (depois de confirmar digital, rosto ou PIN);
o servidor confere a assinatura com a chave pública guardada no cadastro.

A verificação criptográfica é feita pela biblioteca `webauthn` (py_webauthn, Duo Security).
Este módulo cuida do resto: desafios de uso único, armazenamento e regras do app.
"""

import json
import secrets
from datetime import timedelta
from uuid import UUID

from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .config import Config

VALIDADE_DESAFIO = timedelta(minutes=5)
TIMEOUT_MS = 120_000
RP_NOME = "Afinidade"
MAX_JSON_CREDENCIAL = 16_384  # respostas legítimas têm poucos KB
_TRANSPORTES_VALIDOS = {t.value for t in AuthenticatorTransport}

# Exigimos passkey "descobrível" (dá para entrar sem digitar o apelido) e verificação do
# usuário (digital, rosto ou PIN): o aparelho sozinho não basta, precisa ser a pessoa.
_SELECAO = AuthenticatorSelectionCriteria(
    resident_key=ResidentKeyRequirement.REQUIRED,
    user_verification=UserVerificationRequirement.REQUIRED,
)


class PasskeyInvalida(ValueError):
    """Resposta do autenticador recusada (assinatura, origem, desafio, formato...)."""


def novo_webauthn_id() -> bytes:
    return secrets.token_bytes(32)


# ---------- desafios de uso único ----------


async def criar_desafio(con, tipo: str, desafio: bytes, *, conta_id: UUID | None = None, dados=None) -> UUID:
    return await con.fetchval(
        """INSERT INTO desafios_webauthn (desafio, tipo, conta_id, dados, expira_em)
           VALUES ($1, $2, $3, $4::jsonb, now() + $5::interval) RETURNING id""",
        desafio,
        tipo,
        conta_id,
        json.dumps(dados) if dados is not None else None,
        VALIDADE_DESAFIO,
    )


async def consumir_desafio(con, desafio_id: UUID, tipo: str, *, conta_id: UUID | None = None):
    """Apaga e devolve o desafio numa única operação: um desafio nunca vale duas vezes,
    nem para outro tipo de operação, nem para outra conta."""
    linha = await con.fetchrow(
        """DELETE FROM desafios_webauthn
           WHERE id = $1 AND tipo = $2 AND conta_id IS NOT DISTINCT FROM $3 AND expira_em > now()
           RETURNING desafio, dados""",
        desafio_id,
        tipo,
        conta_id,
    )
    if linha is None:
        raise PasskeyInvalida("Desafio inválido ou expirado. Tente de novo.")
    return linha["desafio"], json.loads(linha["dados"]) if linha["dados"] else None


async def apagar_desafios_expirados(con) -> int:
    status = await con.execute("DELETE FROM desafios_webauthn WHERE expira_em <= now()")
    return int(status.split()[-1])


# ---------- cerimônias ----------


def opcoes_registro(cfg: Config, *, webauthn_id: bytes, apelido: str, excluir: list[bytes]) -> tuple[dict, bytes]:
    """Opções para o navegador criar uma passkey (navigator.credentials.create)."""
    opcoes = generate_registration_options(
        rp_id=cfg.webauthn_rp_id,
        rp_name=RP_NOME,
        user_id=webauthn_id,
        user_name=apelido,  # aparece no gerenciador de senhas do aparelho: é só o pseudônimo
        user_display_name=apelido,
        authenticator_selection=_SELECAO,
        exclude_credentials=[PublicKeyCredentialDescriptor(id=i) for i in excluir],
        timeout=TIMEOUT_MS,
    )
    return json.loads(options_to_json(opcoes)), opcoes.challenge


def opcoes_login(cfg: Config) -> tuple[dict, bytes]:
    """Opções para entrar (navigator.credentials.get). Lista vazia = o aparelho oferece as
    passkeys que tiver para este site, e a pessoa não precisa digitar o apelido."""
    opcoes = generate_authentication_options(
        rp_id=cfg.webauthn_rp_id,
        user_verification=UserVerificationRequirement.REQUIRED,
        timeout=TIMEOUT_MS,
    )
    return json.loads(options_to_json(opcoes)), opcoes.challenge


def _validar_formato(credencial: dict) -> None:
    if len(json.dumps(credencial)) > MAX_JSON_CREDENCIAL:
        raise PasskeyInvalida("Resposta do autenticador grande demais")


def verificar_registro(cfg: Config, credencial: dict, desafio: bytes):
    _validar_formato(credencial)
    try:
        return verify_registration_response(
            credential=credencial,
            expected_challenge=desafio,
            expected_rp_id=cfg.webauthn_rp_id,
            expected_origin=list(cfg.webauthn_origens),
            require_user_verification=True,
        )
    except (WebAuthnException, ValueError, KeyError, TypeError) as e:
        raise PasskeyInvalida("Não foi possível validar a passkey") from e


def verificar_login(cfg: Config, credencial: dict, desafio: bytes, *, chave_publica: bytes, contador: int):
    _validar_formato(credencial)
    try:
        return verify_authentication_response(
            credential=credencial,
            expected_challenge=desafio,
            expected_rp_id=cfg.webauthn_rp_id,
            expected_origin=list(cfg.webauthn_origens),
            credential_public_key=chave_publica,
            # Se o contador não avançar, a biblioteca recusa: sinal de autenticador clonado.
            credential_current_sign_count=contador,
            require_user_verification=True,
        )
    except (WebAuthnException, ValueError, KeyError, TypeError) as e:
        raise PasskeyInvalida("Não foi possível validar a passkey") from e


def id_da_credencial(credencial: dict) -> bytes:
    try:
        return base64url_to_bytes(str(credencial["rawId"]))
    except (KeyError, ValueError) as e:
        raise PasskeyInvalida("Credencial sem identificador") from e


def transportes(credencial: dict) -> list[str]:
    brutos = (credencial.get("response") or {}).get("transports") or []
    return [t for t in brutos if isinstance(t, str) and t in _TRANSPORTES_VALIDOS][:8]


# ---------- banco ----------


async def salvar(con, conta_id: UUID, verificado, credencial: dict, nome: str | None) -> None:
    total = await con.fetchval("SELECT count(*) FROM passkeys WHERE conta_id = $1", conta_id)
    await con.execute(
        """INSERT INTO passkeys (id, conta_id, chave_publica, contador, transportes, sincronizada, nome)
           VALUES ($1, $2, $3, $4, $5, $6, $7)""",
        verificado.credential_id,
        conta_id,
        verificado.credential_public_key,
        verificado.sign_count,
        transportes(credencial),
        verificado.credential_backed_up,
        (nome or "").strip()[:40] or f"Passkey {total + 1}",
    )


async def buscar(con, credencial_id: bytes):
    return await con.fetchrow(
        """SELECT p.*, c.token_versao, c.situacao, c.handle FROM passkeys p
           JOIN contas c ON c.id = p.conta_id WHERE p.id = $1""",
        credencial_id,
    )


async def registrar_uso(con, credencial_id: bytes, contador: int, sincronizada: bool) -> None:
    await con.execute(
        "UPDATE passkeys SET contador = $2, sincronizada = $3, usado_em = now() WHERE id = $1",
        credencial_id,
        contador,
        sincronizada,
    )


async def listar(con, conta_id: UUID):
    return await con.fetch(
        """SELECT id, nome, sincronizada, criado_em, usado_em FROM passkeys
           WHERE conta_id = $1 ORDER BY criado_em""",
        conta_id,
    )


async def ids_da_conta(con, conta_id: UUID) -> list[bytes]:
    return [linha["id"] for linha in await con.fetch("SELECT id FROM passkeys WHERE conta_id = $1", conta_id)]


async def apagar(con, conta_id: UUID, credencial_id: bytes) -> bool:
    status = await con.execute("DELETE FROM passkeys WHERE id = $1 AND conta_id = $2", credencial_id, conta_id)
    return status != "DELETE 0"


def id_publico(credencial_id: bytes) -> str:
    return bytes_to_base64url(credencial_id)
