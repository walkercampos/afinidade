"""Cifragem em repouso (AES-256-GCM): mensagens do chat, fotos, evidências de denúncias e e-mails.

Não é criptografia ponta a ponta: o servidor tem a chave. O que ela protege é o cenário
mais comum de vazamento — dump do banco, backup exposto, acesso indevido ao provedor do
banco —, já que a chave vive só na variável de ambiente do servidor da API.
"""

import hashlib
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_VERSAO = b"\x01"  # permite trocar algoritmo/chave no futuro sem perder o que já existe


def _chave(segredo: str, dominio: bytes) -> AESGCM:
    # Deriva 32 bytes de um segredo de qualquer formato. O domínio separa os usos: a chave
    # dos e-mails nunca abre mensagens, e vice-versa, mesmo se alguém reusar o segredo.
    return AESGCM(hashlib.sha256(dominio + b"|" + segredo.encode()).digest())


class Cifrador:
    """Cifra sempre com a chave atual. `anteriores` permite TROCAR a chave (rotação): o que foi
    cifrado com uma chave antiga continua legível até ser recifrado (`python -m app.admin
    recifrar`), e só então a chave antiga pode ser descartada. Ver docs/operacao.md."""

    def __init__(self, segredo: str, dominio: bytes = b"matchmaking/mensagens/v1", anteriores: tuple[str, ...] = ()):
        self._aead = _chave(segredo, dominio)
        self._antigas = [_chave(s, dominio) for s in anteriores if s and s != segredo]

    def cifrar_bytes(self, dados: bytes, contexto: bytes) -> bytes:
        """`contexto` (AAD) amarra o conteúdo cifrado ao lugar dele: copiar o blob para outra
        conversa, denúncia ou foto faz a decifragem falhar."""
        nonce = secrets.token_bytes(12)
        return _VERSAO + nonce + self._aead.encrypt(nonce, dados, contexto)

    def _abrir(self, blob: bytes, contexto: bytes) -> tuple[bytes, bool]:
        """(dados, cifrado_com_a_chave_atual)."""
        if blob[:1] != _VERSAO:
            raise ValueError("Versão de cifragem desconhecida")
        for i, aead in enumerate([self._aead, *self._antigas]):
            try:
                return aead.decrypt(blob[1:13], blob[13:], contexto), i == 0
            except InvalidTag:
                continue
        raise ValueError("Conteúdo adulterado, contexto incorreto ou chave desconhecida")

    def decifrar_bytes(self, blob: bytes, contexto: bytes) -> bytes:
        return self._abrir(blob, contexto)[0]

    def recifrar_bytes(self, blob: bytes, contexto: bytes) -> bytes | None:
        """Se o blob foi cifrado com uma chave antiga, devolve-o cifrado com a atual; senão None."""
        dados, atual = self._abrir(blob, contexto)
        return None if atual else self.cifrar_bytes(dados, contexto)

    def cifrar(self, texto: str, contexto: bytes) -> bytes:
        return self.cifrar_bytes(texto.encode(), contexto)

    def decifrar(self, blob: bytes, contexto: bytes) -> str:
        return self.decifrar_bytes(blob, contexto).decode()
