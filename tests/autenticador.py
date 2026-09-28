"""Autenticador WebAuthn de software, só para testes.

Faz o que o chip do celular faz: cria um par de chaves ES256, assina os desafios do servidor e
monta as estruturas binárias (clientDataJSON, authenticatorData, attestationObject em CBOR).
Permite testar a criptografia de ponta a ponta sem navegador.
"""

import base64
import hashlib
import json
import secrets
import struct

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

UP, UV, BE, BS, AT = 0x01, 0x04, 0x08, 0x10, 0x40


def b64u(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def de_b64u(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


class Autenticador:
    def __init__(self, rp_id: str, origem: str, *, verificar_usuario: bool = True, sincronizada: bool = True):
        self.rp_id, self.origem = rp_id, origem
        self.flags_extra = (UV if verificar_usuario else 0) | ((BE | BS) if sincronizada else 0)
        self.chave = ec.generate_private_key(ec.SECP256R1())
        self.credencial_id = secrets.token_bytes(32)
        self.contador = 0
        self.user_handle: bytes | None = None

    def _cose(self) -> bytes:
        n = self.chave.public_key().public_numbers()
        return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: n.x.to_bytes(32, "big"), -3: n.y.to_bytes(32, "big")})

    def _client_data(self, tipo: str, desafio_b64: str, origem: str | None) -> bytes:
        return json.dumps(
            {"type": tipo, "challenge": desafio_b64, "origin": origem or self.origem, "crossOrigin": False}
        ).encode()

    def _auth_data(self, flags: int, extra: bytes = b"", rp_id: str | None = None) -> bytes:
        return (
            hashlib.sha256((rp_id or self.rp_id).encode()).digest()
            + bytes([flags])
            + struct.pack(">I", self.contador)
            + extra
        )

    def criar(self, opcoes: dict, *, origem: str | None = None) -> dict:
        """Equivalente a navigator.credentials.create(opcoes) + credential.toJSON()."""
        self.user_handle = de_b64u(opcoes["user"]["id"])
        dados_credencial = bytes(16) + struct.pack(">H", len(self.credencial_id)) + self.credencial_id + self._cose()
        auth_data = self._auth_data(UP | AT | self.flags_extra, dados_credencial)
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": b64u(self.credencial_id),
            "rawId": b64u(self.credencial_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64u(self._client_data("webauthn.create", opcoes["challenge"], origem)),
                "attestationObject": b64u(attestation),
                "transports": ["internal", "hybrid"],
            },
            "clientExtensionResults": {},
            "authenticatorAttachment": "platform",
        }

    def assinar(
        self, opcoes: dict, *, origem: str | None = None, rp_id: str | None = None, avancar_contador: bool = True
    ) -> dict:
        """Equivalente a navigator.credentials.get(opcoes) + credential.toJSON()."""
        if avancar_contador:
            self.contador += 1
        auth_data = self._auth_data(UP | self.flags_extra, rp_id=rp_id)
        client_data = self._client_data("webauthn.get", opcoes["challenge"], origem)
        assinatura = self.chave.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": b64u(self.credencial_id),
            "rawId": b64u(self.credencial_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64u(client_data),
                "authenticatorData": b64u(auth_data),
                "signature": b64u(assinatura),
                "userHandle": b64u(self.user_handle or b""),
            },
            "clientExtensionResults": {},
            "authenticatorAttachment": "platform",
        }
