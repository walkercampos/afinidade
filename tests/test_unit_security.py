from uuid import uuid4

import jwt

from app.security import emitir_token


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
