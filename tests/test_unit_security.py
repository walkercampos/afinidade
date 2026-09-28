from uuid import uuid4

import jwt

from app.security import HASH_FALSO, emitir_token, gerar_hash_senha, verificar_senha


def test_hash_de_senha():
    h = gerar_hash_senha("senha-forte-123")
    assert h.startswith("scrypt$") and "senha-forte-123" not in h
    assert verificar_senha("senha-forte-123", h)
    assert not verificar_senha("senha-forte-124", h)


def test_sal_diferente_a_cada_hash():
    assert gerar_hash_senha("x" * 10) != gerar_hash_senha("x" * 10)


def test_hash_corrompido_nao_quebra():
    assert not verificar_senha("qualquer", "lixo")
    assert not verificar_senha("qualquer", HASH_FALSO)


def test_token_carrega_conta_e_versao():
    conta = uuid4()
    payload = jwt.decode(emitir_token(conta, 7, "k" * 32, 60), "k" * 32, algorithms=["HS256"])
    assert payload["sub"] == str(conta) and payload["ver"] == 7 and payload["exp"] > payload["iat"]


def test_token_nao_aceita_algoritmo_none():
    falso = jwt.encode({"sub": str(uuid4()), "ver": 0}, key=None, algorithm="none")
    try:
        jwt.decode(falso, "k" * 32, algorithms=["HS256"])
        raise AssertionError("token sem assinatura foi aceito")
    except jwt.PyJWTError:
        pass
