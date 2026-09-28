"""Passkeys de ponta a ponta com um autenticador de software (criptografia real)."""

import pytest

from app import admin
from tests.autenticador import Autenticador, b64u
from tests.conftest import SENHA

RP, ORIGEM = "testserver", "http://testserver"
CADASTRO = {"data_nascimento": "1990-05-01", "confirmo_maior_de_idade": True, "consinto_dados_sensiveis": True}


@pytest.fixture
def aparelho():
    return Autenticador(RP, ORIGEM)


def criar_conta_com_passkey(client, aparelho, **extra):
    r = client.post("/api/auth/passkey/registro/opcoes", json={**CADASTRO, **extra})
    assert r.status_code == 200, r.text
    opcoes = r.json()
    r = client.post(
        "/api/auth/passkey/registro",
        json={"desafio_id": opcoes["desafio_id"], "credencial": aparelho.criar(opcoes["opcoes"])},
    )
    client.cookies.clear()
    return r


def entrar_com_passkey(client, aparelho, **kw):
    opcoes = client.post("/api/auth/passkey/login/opcoes").json()
    r = client.post(
        "/api/auth/passkey/login",
        json={"desafio_id": opcoes["desafio_id"], "credencial": aparelho.assinar(opcoes["opcoes"], **kw)},
    )
    client.cookies.clear()
    return r


def bearer(r):
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_opcoes_exigem_passkey_descobrivel_e_verificacao_do_usuario(client):
    opcoes = client.post("/api/auth/passkey/registro/opcoes", json=CADASTRO).json()["opcoes"]
    assert opcoes["rp"] == {"id": RP, "name": "Afinidade"}
    assert opcoes["authenticatorSelection"]["residentKey"] == "required"
    assert opcoes["authenticatorSelection"]["userVerification"] == "required"
    assert opcoes["user"]["name"].startswith("anon_")  # só o pseudônimo vai para o aparelho
    assert len(opcoes["challenge"]) >= 43  # 32+ bytes aleatórios
    login = client.post("/api/auth/passkey/login/opcoes").json()["opcoes"]
    assert login["userVerification"] == "required" and login.get("allowCredentials", []) == []


def test_cadastro_e_login_sem_senha(client, aparelho, db):
    r = criar_conta_com_passkey(client, aparelho, handle="sem_senha_1")
    assert r.status_code == 201, r.text
    assert r.json()["handle"] == "sem_senha_1"
    conta = db.fetchrow("SELECT senha_hash, webauthn_id FROM contas WHERE handle = 'sem_senha_1'")
    assert conta["senha_hash"] is None and len(conta["webauthn_id"]) == 32
    # o user.id do aparelho é o webauthn_id opaco, não o id da conta
    assert aparelho.user_handle == conta["webauthn_id"]

    r = entrar_com_passkey(client, aparelho)
    assert r.status_code == 200, r.text
    assert client.get("/api/perfil", headers=bearer(r)).status_code == 404  # logado, perfil ainda não criado
    # não há senha que funcione nessa conta
    assert client.post("/api/auth/login", json={"handle": "sem_senha_1", "senha": SENHA}).status_code == 401
    client.cookies.clear()


def test_apelido_aleatorio_e_apelido_ocupado(client, aparelho, pessoa):
    r = criar_conta_com_passkey(client, aparelho)
    assert r.status_code == 201 and r.json()["handle"].startswith("anon_")
    ocupado = pessoa()
    r = client.post("/api/auth/passkey/registro/opcoes", json={**CADASTRO, "handle": ocupado.handle})
    assert r.status_code == 409


def test_menor_de_idade_nem_recebe_opcoes(client):
    r = client.post("/api/auth/passkey/registro/opcoes", json={**CADASTRO, "data_nascimento": "2015-01-01"})
    assert r.status_code == 422


def test_desafio_so_vale_uma_vez(client, aparelho):
    criar_conta_com_passkey(client, aparelho)
    opcoes = client.post("/api/auth/passkey/login/opcoes").json()
    corpo = {"desafio_id": opcoes["desafio_id"], "credencial": aparelho.assinar(opcoes["opcoes"])}
    assert client.post("/api/auth/passkey/login", json=corpo).status_code == 200
    client.cookies.clear()
    replay = client.post("/api/auth/passkey/login", json=corpo)
    assert replay.status_code == 401 and "Desafio" in replay.json()["detail"]


def test_desafio_expirado(client, aparelho, db):
    criar_conta_com_passkey(client, aparelho)
    opcoes = client.post("/api/auth/passkey/login/opcoes").json()
    db.execute(
        "UPDATE desafios_webauthn SET expira_em = now() - interval '1 second' WHERE id = $1::uuid", opcoes["desafio_id"]
    )
    corpo = {"desafio_id": opcoes["desafio_id"], "credencial": aparelho.assinar(opcoes["opcoes"])}
    assert client.post("/api/auth/passkey/login", json=corpo).status_code == 401


def test_desafio_de_cadastro_nao_serve_para_login(client, aparelho):
    criar_conta_com_passkey(client, aparelho)
    opcoes = client.post("/api/auth/passkey/registro/opcoes", json=CADASTRO).json()
    corpo = {"desafio_id": opcoes["desafio_id"], "credencial": aparelho.assinar(opcoes["opcoes"])}
    assert client.post("/api/auth/passkey/login", json=corpo).status_code == 401


@pytest.mark.parametrize(
    "ataque",
    [
        {"origem": "https://site-falso.example"},  # phishing: outro site pedindo a assinatura
        {"rp_id": "site-falso.example"},
    ],
)
def test_phishing_e_recusado(client, aparelho, ataque):
    criar_conta_com_passkey(client, aparelho)
    assert entrar_com_passkey(client, aparelho, **ataque).status_code == 401


def test_cadastro_de_outra_origem_e_recusado(client):
    falso = Autenticador(RP, ORIGEM)
    r = client.post("/api/auth/passkey/registro/opcoes", json=CADASTRO).json()
    credencial = falso.criar(r["opcoes"], origem="https://site-falso.example")
    resp = client.post("/api/auth/passkey/registro", json={"desafio_id": r["desafio_id"], "credencial": credencial})
    assert resp.status_code == 400


def test_assinatura_de_outra_chave_e_recusada(client, aparelho):
    criar_conta_com_passkey(client, aparelho)
    impostor = Autenticador(RP, ORIGEM)
    impostor.credencial_id = aparelho.credencial_id  # mesmo id, chave privada diferente
    impostor.user_handle = aparelho.user_handle
    assert entrar_com_passkey(client, impostor).status_code == 401


def test_passkey_desconhecida(client):
    assert entrar_com_passkey(client, Autenticador(RP, ORIGEM)).status_code == 401


def test_contador_que_nao_avanca_indica_clone(client, aparelho):
    criar_conta_com_passkey(client, aparelho)
    assert entrar_com_passkey(client, aparelho).status_code == 200
    assert entrar_com_passkey(client, aparelho).status_code == 200
    # um clone da chave teria o contador parado/atrasado
    aparelho.contador -= 1
    assert entrar_com_passkey(client, aparelho).status_code == 401


def test_sem_verificacao_do_usuario_e_recusado(client):
    so_presenca = Autenticador(RP, ORIGEM, verificar_usuario=False)
    opcoes = client.post("/api/auth/passkey/registro/opcoes", json=CADASTRO).json()
    corpo = {"desafio_id": opcoes["desafio_id"], "credencial": so_presenca.criar(opcoes["opcoes"])}
    assert client.post("/api/auth/passkey/registro", json=corpo).status_code == 400


def test_resposta_malformada_ou_enorme(client):
    opcoes = client.post("/api/auth/passkey/login/opcoes").json()
    assert (
        client.post(
            "/api/auth/passkey/login", json={"desafio_id": opcoes["desafio_id"], "credencial": {"rawId": "!!!"}}
        ).status_code
        == 401
    )
    opcoes = client.post("/api/auth/passkey/registro/opcoes", json=CADASTRO).json()
    enorme = {"rawId": "a", "lixo": "x" * 20_000}
    assert (
        client.post(
            "/api/auth/passkey/registro", json={"desafio_id": opcoes["desafio_id"], "credencial": enorme}
        ).status_code
        == 400
    )


def test_adicionar_listar_e_remover(client, pessoa, db):
    p = pessoa()  # conta criada com senha
    celular, notebook = Autenticador(RP, ORIGEM), Autenticador(RP, ORIGEM, sincronizada=False)
    for aparelho, nome in ((celular, "Celular"), (notebook, None)):
        opcoes = p.post("/api/passkeys/opcoes").json()
        r = p.post(
            "/api/passkeys",
            json={"desafio_id": opcoes["desafio_id"], "nome": nome, "credencial": aparelho.criar(opcoes["opcoes"])},
        )
        assert r.status_code == 201, r.text
    # a segunda cerimônia exclui a passkey que já existe (o aparelho não duplica)
    opcoes = p.post("/api/passkeys/opcoes").json()["opcoes"]
    assert {c["id"] for c in opcoes["excludeCredentials"]} == {
        b64u(celular.credencial_id),
        b64u(notebook.credencial_id),
    }
    # o mesmo user.id é usado em todas as passkeys da conta
    assert celular.user_handle == notebook.user_handle

    lista = p.get("/api/passkeys").json()
    assert [(x["nome"], x["sincronizada"]) for x in lista] == [("Celular", True), ("Passkey 2", False)]
    assert entrar_com_passkey(client, celular).status_code == 200
    assert p.get("/api/passkeys").json()[0]["usado_em"] is not None

    assert p.delete(f"/api/passkeys/{lista[0]['id']}").status_code == 204
    assert entrar_com_passkey(client, celular).status_code == 401
    assert p.delete("/api/passkeys/naoexiste").status_code == 404
    assert p.delete("/api/passkeys/***").status_code == 404


def test_nao_deixa_remover_a_unica_forma_de_entrar(client, aparelho):
    r = criar_conta_com_passkey(client, aparelho)
    h = bearer(r)
    [unica] = client.get("/api/passkeys", headers=h).json()
    assert client.delete(f"/api/passkeys/{unica['id']}", headers=h).status_code == 409


def test_desafio_de_adicionar_e_da_propria_conta(client, pessoa):
    a, b = pessoa(), pessoa()
    opcoes = a.post("/api/passkeys/opcoes").json()
    credencial = Autenticador(RP, ORIGEM).criar(opcoes["opcoes"])
    # B tenta usar o desafio de A para pendurar uma passkey na própria conta
    assert (
        b.post("/api/passkeys", json={"desafio_id": opcoes["desafio_id"], "credencial": credencial}).status_code == 400
    )


def test_mesma_passkey_nao_entra_duas_vezes(client, pessoa):
    p = pessoa()
    aparelho = Autenticador(RP, ORIGEM)
    for esperado in (201, 409):
        opcoes = p.post("/api/passkeys/opcoes").json()
        r = p.post(
            "/api/passkeys", json={"desafio_id": opcoes["desafio_id"], "credencial": aparelho.criar(opcoes["opcoes"])}
        )
        assert r.status_code == esperado


def test_cadastro_com_passkey_ja_usada_nao_cria_conta(client, aparelho, db):
    criar_conta_com_passkey(client, aparelho)
    antes = db.fetchval("SELECT count(*) FROM contas")
    r = criar_conta_com_passkey(client, aparelho)  # mesmo aparelho, mesma credencial
    assert r.status_code == 409
    assert db.fetchval("SELECT count(*) FROM contas") == antes  # a transação desfez a conta


def test_conta_banida_nao_entra_por_passkey(client, aparelho, pessoa, db):
    criar_conta_com_passkey(client, aparelho, handle="vai_ser_banida")
    conta_id = db.fetchval("SELECT id::text FROM contas WHERE handle = 'vai_ser_banida'")
    mod = pessoa()
    admin.main(["moderador", mod.handle])
    assert mod.post(f"/api/moderacao/contas/{conta_id}/decisao", json={"acao": "banir"}).status_code == 204
    assert entrar_com_passkey(client, aparelho).status_code == 403


def test_excluir_conta_apaga_as_passkeys(client, aparelho, db):
    r = criar_conta_com_passkey(client, aparelho, handle="apagar_tudo_pk")
    assert client.delete("/api/conta", headers=bearer(r)).status_code == 204
    client.cookies.clear()
    assert db.fetchval("SELECT count(*) FROM passkeys WHERE id = $1", aparelho.credencial_id) == 0
    assert entrar_com_passkey(client, aparelho).status_code == 401


def test_limpeza_de_desafios_expirados(client, db):
    import asyncio

    import asyncpg

    from app import passkeys
    from tests.conftest import URL

    client.post("/api/auth/passkey/login/opcoes")
    db.execute("UPDATE desafios_webauthn SET expira_em = now() - interval '1 minute'")

    async def limpar():
        con = await asyncpg.connect(URL)
        try:
            return await passkeys.apagar_desafios_expirados(con)
        finally:
            await con.close()

    assert asyncio.run(limpar()) >= 1
    assert db.fetchval("SELECT count(*) FROM desafios_webauthn WHERE expira_em <= now()") == 0
