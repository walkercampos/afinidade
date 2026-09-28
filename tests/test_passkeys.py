"""Biometria (passkeys) depois do cadastro por e-mail, com criptografia real (autenticador de software)."""

import pytest

from app import admin
from tests.autenticador import Autenticador, b64u
from tests.conftest import bearer, criar_conta, entrar_por_email

RP, ORIGEM = "testserver", "http://testserver"


@pytest.fixture
def aparelho():
    return Autenticador(RP, ORIGEM)


def ativar_biometria(client, headers, aparelho, nome=None):
    opcoes = client.post("/api/passkeys/opcoes", headers=headers).json()
    return client.post(
        "/api/passkeys",
        headers=headers,
        json={"desafio_id": opcoes["desafio_id"], "nome": nome, "credencial": aparelho.criar(opcoes["opcoes"])},
    )


def conta_com_biometria(client, aparelho, **kw):
    r = criar_conta(client, **kw)
    assert r.status_code == 200, r.text
    assert ativar_biometria(client, bearer(r), aparelho).status_code == 201
    return r


def entrar_com_biometria(client, aparelho, **kw):
    opcoes = client.post("/api/auth/passkey/login/opcoes").json()
    r = client.post(
        "/api/auth/passkey/login",
        json={"desafio_id": opcoes["desafio_id"], "credencial": aparelho.assinar(opcoes["opcoes"], **kw)},
    )
    client.cookies.clear()
    return r


def test_cadastro_por_passkey_sem_email_nao_existe_mais(client):
    assert client.post("/api/auth/passkey/registro/opcoes", json={}).status_code in (404, 405)


def test_opcoes_exigem_passkey_descobrivel_e_verificacao_do_usuario(client):
    r = criar_conta(client, handle="opcoes_pk")
    opcoes = client.post("/api/passkeys/opcoes", headers=bearer(r)).json()["opcoes"]
    assert opcoes["rp"] == {"id": RP, "name": "Afinidade"}
    assert opcoes["authenticatorSelection"]["residentKey"] == "required"
    assert opcoes["authenticatorSelection"]["userVerification"] == "required"
    assert opcoes["user"]["name"] == "opcoes_pk"  # só o pseudônimo vai para o aparelho, nunca o e-mail
    assert len(opcoes["challenge"]) >= 43
    login = client.post("/api/auth/passkey/login/opcoes").json()["opcoes"]
    assert login["userVerification"] == "required" and login.get("allowCredentials", []) == []


def test_email_primeiro_depois_biometria(client, aparelho, db):
    r = criar_conta(client, handle="bio_depois")
    assert r.json()["novo"] is True
    assert ativar_biometria(client, bearer(r), aparelho, "Celular").status_code == 201
    webauthn_id = db.fetchval("SELECT webauthn_id FROM contas WHERE handle = 'bio_depois'")
    assert aparelho.user_handle == webauthn_id and len(webauthn_id) == 32  # id opaco, não o da conta

    entrou = entrar_com_biometria(client, aparelho)
    assert entrou.status_code == 200 and entrou.json()["handle"] == "bio_depois"
    assert entrou.json()["novo"] is False
    assert client.get("/api/passkeys", headers=bearer(entrou)).json()[0]["usado_em"] is not None


def test_desafio_so_vale_uma_vez(client, aparelho):
    conta_com_biometria(client, aparelho)
    opcoes = client.post("/api/auth/passkey/login/opcoes").json()
    corpo = {"desafio_id": opcoes["desafio_id"], "credencial": aparelho.assinar(opcoes["opcoes"])}
    assert client.post("/api/auth/passkey/login", json=corpo).status_code == 200
    client.cookies.clear()
    replay = client.post("/api/auth/passkey/login", json=corpo)
    assert replay.status_code == 401 and "Desafio" in replay.json()["detail"]


def test_desafio_expirado(client, aparelho, db):
    conta_com_biometria(client, aparelho)
    opcoes = client.post("/api/auth/passkey/login/opcoes").json()
    db.execute(
        "UPDATE desafios_webauthn SET expira_em = now() - interval '1 second' WHERE id = $1::uuid",
        opcoes["desafio_id"],
    )
    corpo = {"desafio_id": opcoes["desafio_id"], "credencial": aparelho.assinar(opcoes["opcoes"])}
    assert client.post("/api/auth/passkey/login", json=corpo).status_code == 401


def test_desafio_de_cadastro_de_biometria_nao_serve_para_login(client, aparelho):
    r = conta_com_biometria(client, aparelho)
    opcoes = client.post("/api/passkeys/opcoes", headers=bearer(r)).json()
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
    conta_com_biometria(client, aparelho)
    assert entrar_com_biometria(client, aparelho, **ataque).status_code == 401


def test_cadastro_de_biometria_vindo_de_outra_origem_e_recusado(client):
    r = criar_conta(client)
    opcoes = client.post("/api/passkeys/opcoes", headers=bearer(r)).json()
    credencial = Autenticador(RP, ORIGEM).criar(opcoes["opcoes"], origem="https://site-falso.example")
    resp = client.post(
        "/api/passkeys", headers=bearer(r), json={"desafio_id": opcoes["desafio_id"], "credencial": credencial}
    )
    assert resp.status_code == 400


def test_assinatura_de_outra_chave_e_recusada(client, aparelho):
    conta_com_biometria(client, aparelho)
    impostor = Autenticador(RP, ORIGEM)
    impostor.credencial_id = aparelho.credencial_id  # mesmo id, chave privada diferente
    impostor.user_handle = aparelho.user_handle
    assert entrar_com_biometria(client, impostor).status_code == 401


def test_passkey_desconhecida(client):
    assert entrar_com_biometria(client, Autenticador(RP, ORIGEM)).status_code == 401


def test_contador_que_nao_avanca_indica_clone(client, aparelho):
    conta_com_biometria(client, aparelho)
    assert entrar_com_biometria(client, aparelho).status_code == 200
    assert entrar_com_biometria(client, aparelho).status_code == 200
    aparelho.contador -= 1  # um clone da chave teria o contador parado/atrasado
    assert entrar_com_biometria(client, aparelho).status_code == 401


def test_sem_verificacao_do_usuario_e_recusado(client):
    r = criar_conta(client)
    assert ativar_biometria(client, bearer(r), Autenticador(RP, ORIGEM, verificar_usuario=False)).status_code == 400


def test_resposta_malformada_ou_enorme(client):
    opcoes = client.post("/api/auth/passkey/login/opcoes").json()
    corpo = {"desafio_id": opcoes["desafio_id"], "credencial": {"rawId": "!!!"}}
    assert client.post("/api/auth/passkey/login", json=corpo).status_code == 401
    r = criar_conta(client)
    opcoes = client.post("/api/passkeys/opcoes", headers=bearer(r)).json()
    enorme = {"desafio_id": opcoes["desafio_id"], "credencial": {"rawId": "a", "lixo": "x" * 20_000}}
    assert client.post("/api/passkeys", headers=bearer(r), json=enorme).status_code == 400


def test_varias_passkeys_listar_e_remover(client, pessoa):
    p = pessoa()
    celular, notebook = Autenticador(RP, ORIGEM), Autenticador(RP, ORIGEM, sincronizada=False)
    assert ativar_biometria(client, p.h, celular, "Celular").status_code == 201
    assert ativar_biometria(client, p.h, notebook).status_code == 201
    # a próxima cerimônia exclui as passkeys que já existem (o aparelho não duplica)
    opcoes = p.post("/api/passkeys/opcoes").json()["opcoes"]
    esperados = {b64u(celular.credencial_id), b64u(notebook.credencial_id)}
    assert {c["id"] for c in opcoes["excludeCredentials"]} == esperados
    assert celular.user_handle == notebook.user_handle  # mesmo user.id em todas as passkeys da conta

    lista = p.get("/api/passkeys").json()
    assert [(x["nome"], x["sincronizada"]) for x in lista] == [("Celular", True), ("Passkey 2", False)]
    assert p.delete(f"/api/passkeys/{lista[0]['id']}").status_code == 204
    assert entrar_com_biometria(client, celular).status_code == 401
    # remover a última é permitido: o e-mail continua dando acesso
    assert p.delete(f"/api/passkeys/{lista[1]['id']}").status_code == 204
    assert entrar_por_email(client, p.email).status_code == 200
    assert p.delete("/api/passkeys/naoexiste").status_code == 404
    assert p.delete("/api/passkeys/***").status_code == 404


def test_desafio_de_adicionar_e_da_propria_conta(client, pessoa):
    a, b = pessoa(), pessoa()
    opcoes = a.post("/api/passkeys/opcoes").json()
    credencial = Autenticador(RP, ORIGEM).criar(opcoes["opcoes"])
    # B tenta usar o desafio de A para pendurar uma passkey na própria conta
    corpo = {"desafio_id": opcoes["desafio_id"], "credencial": credencial}
    assert b.post("/api/passkeys", json=corpo).status_code == 400


def test_mesma_passkey_nao_entra_duas_vezes(client, pessoa):
    p = pessoa()
    aparelho = Autenticador(RP, ORIGEM)
    assert ativar_biometria(client, p.h, aparelho).status_code == 201
    assert ativar_biometria(client, p.h, aparelho).status_code == 409


def test_conta_banida_nao_entra_por_biometria(client, aparelho, pessoa, db):
    conta_com_biometria(client, aparelho, handle="vai_ser_banida")
    conta_id = db.fetchval("SELECT id::text FROM contas WHERE handle = 'vai_ser_banida'")
    mod = pessoa()
    admin.main(["moderador", mod.handle])
    assert mod.post(f"/api/moderacao/contas/{conta_id}/decisao", json={"acao": "banir"}).status_code == 204
    assert entrar_com_biometria(client, aparelho).status_code == 403


def test_excluir_conta_apaga_as_passkeys(client, aparelho, db):
    r = conta_com_biometria(client, aparelho)
    assert client.delete("/api/conta", headers=bearer(r)).status_code == 204
    client.cookies.clear()
    assert db.fetchval("SELECT count(*) FROM passkeys WHERE id = $1", aparelho.credencial_id) == 0
    assert entrar_com_biometria(client, aparelho).status_code == 401


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
