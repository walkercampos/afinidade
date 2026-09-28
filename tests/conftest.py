"""Fixtures compartilhadas.

Testes de API rodam contra um PostgreSQL real, apontado por TEST_DATABASE_URL.
ATENÇÃO: o schema `public` desse banco é APAGADO no início da execução.
"""

import asyncio
import itertools
import os

import asyncpg
import pytest

URL = os.environ.get("TEST_DATABASE_URL")
SENHA = "senha-forte-123"
_contador = itertools.count()


@pytest.fixture(scope="session")
def client():
    if not URL:
        pytest.skip("TEST_DATABASE_URL não definido")
    from fastapi.testclient import TestClient

    async def limpar():
        con = await asyncpg.connect(URL)
        await con.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        await con.close()

    asyncio.run(limpar())
    os.environ.update(
        {
            "DATABASE_URL": URL,
            "JWT_SECRET": "x" * 32,
            "CHAVE_MENSAGENS": "y" * 32,
            "AMBIENTE": "dev",
            "LIMITE_AUTH_POR_MIN": "100000",
            "LIMITE_API_POR_MIN": "100000",
        }
    )
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    """Conexão direta ao banco, para verificar o que foi (ou não) gravado."""

    async def abrir():
        return await asyncpg.connect(URL)

    loop = asyncio.new_event_loop()
    con = loop.run_until_complete(abrir())

    class Sincrono:
        def __getattr__(self, nome):
            metodo = getattr(con, nome)
            return lambda *a, **k: loop.run_until_complete(metodo(*a, **k))

    yield Sincrono()
    loop.run_until_complete(con.close())
    loop.close()


class Pessoa:
    def __init__(self, client, handle, headers, id_):
        self.client, self.handle, self.h, self.id = client, handle, headers, id_

    def get(self, url, **kw):
        return self.client.get(url, headers=self.h, **kw)

    def post(self, url, **kw):
        return self.client.post(url, headers={**self.h, **kw.pop("headers", {})}, **kw)

    def put(self, url, **kw):
        return self.client.put(url, headers=self.h, **kw)

    def delete(self, url, **kw):
        return self.client.delete(url, headers=self.h, **kw)


@pytest.fixture
def pessoa(client):
    """Fábrica: pessoa(genero, busca_por, quero=[], curioso=[], limite=[], local=(lat, lon), dist=None)."""

    def criar(
        genero="outro", busca_por=("outro",), quero=(), curioso=(), limite=(), local=None, dist=None, handle=None
    ):
        handle = handle or f"p{next(_contador)}_{os.getpid()}"
        r = client.post(
            "/api/auth/registro",
            json={
                "handle": handle,
                "senha": SENHA,
                "data_nascimento": "1990-05-01",
                "confirmo_maior_de_idade": True,
                "consinto_dados_sensiveis": True,
            },
        )
        assert r.status_code == 201, r.text
        client.cookies.clear()  # os testes usam Bearer; o cookie é testado à parte
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = client.put(
            "/api/perfil",
            headers=h,
            json={
                "nome_exibicao": handle,
                "genero": genero,
                "busca_por": list(busca_por),
                "tags_interesses": {"quero": list(quero), "curioso": list(curioso), "limite_absoluto": list(limite)},
            },
        )
        assert r.status_code == 200, r.text
        p = Pessoa(client, handle, h, r.json()["id"])
        if local:
            r = p.put("/api/perfil/localizacao", json={"lat": local[0], "lon": local[1], "distancia_max_km": dist})
            assert r.status_code == 200, r.text
        return p

    return criar


@pytest.fixture
def conexao_entre(pessoa):
    """Duas pessoas compatíveis que já se curtiram (podem conversar)."""

    def criar(**extra):
        a = pessoa("homem-cis", ["mulher-cis"], quero=["bondage"], **extra)
        b = pessoa("mulher-cis", ["homem-cis"], quero=["bondage"], **extra)
        assert a.post(f"/api/perfis/{b.id}/curtir").json() == {"conexao": False}
        assert b.post(f"/api/perfis/{a.id}/curtir").json() == {"conexao": True}
        return a, b

    return criar
