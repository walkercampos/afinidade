import pytest

from app.cripto import Cifrador


@pytest.fixture
def cif():
    return Cifrador("s" * 32)


def test_ida_e_volta(cif):
    blob = cif.cifrar("olá 👋", b"ctx")
    assert cif.decifrar(blob, b"ctx") == "olá 👋"


def test_mesmo_texto_gera_blobs_diferentes(cif):
    # nonce aleatório: sem isso, mensagens iguais seriam reconhecíveis no banco
    assert cif.cifrar("oi", b"ctx") != cif.cifrar("oi", b"ctx")


def test_contexto_errado_falha(cif):
    # impede copiar o blob de uma conversa/foto para outra
    with pytest.raises(ValueError):
        cif.decifrar(cif.cifrar("oi", b"conversa-a"), b"conversa-b")


def test_adulteracao_falha(cif):
    blob = bytearray(cif.cifrar("oi", b"ctx"))
    blob[-1] ^= 1
    with pytest.raises(ValueError):
        cif.decifrar(bytes(blob), b"ctx")


def test_chave_errada_falha(cif):
    with pytest.raises(ValueError):
        Cifrador("t" * 32).decifrar(cif.cifrar("oi", b"ctx"), b"ctx")


def test_versao_desconhecida_falha(cif):
    blob = cif.cifrar("oi", b"ctx")
    with pytest.raises(ValueError):
        cif.decifrar(b"\x02" + blob[1:], b"ctx")
