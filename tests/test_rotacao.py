"""Parte 4: troca de chave de cifragem sem perder nada."""

import asyncio

import asyncpg
import pytest

from app import rotacao
from app.cripto import Cifrador


def test_chave_nova_le_o_antigo_e_recifra():
    antiga = Cifrador("a" * 32)
    blob = antiga.cifrar("segredo", b"ctx")
    nova = Cifrador("b" * 32, anteriores=("a" * 32,))
    assert nova.decifrar(blob, b"ctx") == "segredo"  # o antigo continua legível
    recifrado = nova.recifrar_bytes(blob, b"ctx")
    assert recifrado is not None and recifrado != blob
    assert Cifrador("b" * 32).decifrar(recifrado, b"ctx") == "segredo"  # já não depende da antiga
    assert nova.recifrar_bytes(recifrado, b"ctx") is None  # nada a fazer
    with pytest.raises(ValueError):
        Cifrador("b" * 32).decifrar(blob, b"ctx")  # sem a anterior, o antigo não abre
    with pytest.raises(ValueError):
        nova.decifrar(blob, b"outro-contexto")  # contexto continua valendo


def test_recifrar_o_banco_inteiro(client, conexao_entre, db, monkeypatch):
    """Simula a troca: o app cifra com a chave "atual" dos testes; depois a chave muda e o
    comando recifra tudo. Com a chave nova sozinha, tudo continua legível pela API."""
    a, b = conexao_entre()
    a.post(f"/api/conversas/{b.id}/mensagens", json={"texto": "antes da troca"})
    from app import encontros
    from tests.test_encontros import _novo

    _novo(a)
    app = client.app
    velhos = {
        "mensagens": app.state.cifrador,
        "email": app.state.cifrador_email,
        "encontros": app.state.cifrador_encontros,
    }
    from app import contato

    novos = {
        "mensagens": Cifrador("nova-chave-de-mensagens-32-caracteres!!", anteriores=("y" * 32,)),
        "email": contato.criar_cifrador("nova-chave-de-email-32-caracteres!!!!", ("e" * 32,)),
        "encontros": encontros.criar_cifrador("nova-chave-de-mensagens-32-caracteres!!", ("y" * 32,)),
    }
    from tests.conftest import URL

    async def rodar():
        con = await asyncpg.connect(URL)
        try:
            return await rotacao.recifrar(con, novos)
        finally:
            await con.close()

    feitos = asyncio.run(rodar())
    assert (
        feitos["mensagens.conteudo"] >= 1 and feitos["encontros.detalhes"] >= 1 and feitos["contas.email_cifrado"] >= 2
    )
    assert all(n == 0 for n in asyncio.run(rodar()).values())  # segunda passada: nada pendente

    # O app passa a usar só as chaves novas (sem as anteriores) e tudo continua legível
    monkeypatch.setattr(app.state, "cifrador", Cifrador("nova-chave-de-mensagens-32-caracteres!!"))
    monkeypatch.setattr(app.state, "cifrador_email", contato.criar_cifrador("nova-chave-de-email-32-caracteres!!!!"))
    monkeypatch.setattr(
        app.state, "cifrador_encontros", encontros.criar_cifrador("nova-chave-de-mensagens-32-caracteres!!")
    )
    assert [m["texto"] for m in b.get(f"/api/conversas/{a.id}/mensagens").json()] == ["antes da troca"]
    assert a.get("/api/encontros").json()[0]["local"].startswith("Café")
    assert a.get("/api/conta").json()["email"].endswith("@teste.invalid")
    # Restaura o estado para os outros testes (as chaves "velhas" dos testes)
    for nome, cif in velhos.items():
        monkeypatch.setattr(
            app.state,
            {"mensagens": "cifrador", "email": "cifrador_email", "encontros": "cifrador_encontros"}[nome],
            cif,
        )
    # ...e devolve o banco para a chave antiga, para os próximos testes que leem dados antigos
    voltar = {
        "mensagens": Cifrador("y" * 32, anteriores=("nova-chave-de-mensagens-32-caracteres!!",)),
        "email": contato.criar_cifrador("e" * 32, ("nova-chave-de-email-32-caracteres!!!!",)),
        "encontros": encontros.criar_cifrador("y" * 32, ("nova-chave-de-mensagens-32-caracteres!!",)),
    }

    async def desfazer():
        con = await asyncpg.connect(URL)
        try:
            return await rotacao.recifrar(con, voltar)
        finally:
            await con.close()

    asyncio.run(desfazer())
