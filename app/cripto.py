"""Cifragem em repouso (AES-256-GCM) para mensagens do chat e evidências de denúncias.

Não é criptografia ponta a ponta: o servidor tem a chave. O que ela protege é o cenário
mais comum de vazamento — dump do banco, backup exposto, acesso indevido ao provedor do
banco —, já que a chave vive só na variável de ambiente do servidor da API.
"""

import hashlib
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_VERSAO = b"\x01"  # permite trocar algoritmo/chave no futuro sem perder o que já existe


class Cifrador:
    def __init__(self, segredo: str):
        # Deriva 32 bytes de um segredo de qualquer formato, com separação de domínio.
        self._aead = AESGCM(hashlib.sha256(b"matchmaking/mensagens/v1|" + segredo.encode()).digest())

    def cifrar_bytes(self, dados: bytes, contexto: bytes) -> bytes:
        """`contexto` (AAD) amarra o conteúdo cifrado ao lugar dele: copiar o blob para outra
        conversa, denúncia ou foto faz a decifragem falhar."""
        nonce = secrets.token_bytes(12)
        return _VERSAO + nonce + self._aead.encrypt(nonce, dados, contexto)

    def decifrar_bytes(self, blob: bytes, contexto: bytes) -> bytes:
        if blob[:1] != _VERSAO:
            raise ValueError("Versão de cifragem desconhecida")
        try:
            return self._aead.decrypt(blob[1:13], blob[13:], contexto)
        except InvalidTag as e:
            raise ValueError("Conteúdo adulterado ou contexto incorreto") from e

    def cifrar(self, texto: str, contexto: bytes) -> bytes:
        return self.cifrar_bytes(texto.encode(), contexto)

    def decifrar(self, blob: bytes, contexto: bytes) -> str:
        return self.decifrar_bytes(blob, contexto).decode()
