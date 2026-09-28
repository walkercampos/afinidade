"""Cadastro e acesso por e-mail: privacidade, anti-enumeração e uso único."""

import re

from app.verificacao import MAX_TENTATIVAS
from tests.conftest import CADASTRO, bearer, confirmar, criar_conta, entrar_por_email, novo_email, ultimo_email


def caixa(client):
    return client.app.state.carteiro.caixa


def test_email_nunca_fica_gravado_em_texto(client, db):
    email = "Privada.Pessoa@Exemplo.com"
    r = criar_conta(client, email, "email_privado")
    assert r.status_code == 200
    conta = db.fetchrow("SELECT * FROM contas WHERE handle = 'email_privado'")
    assert len(conta["email_hash"]) == 32
    assert "exemplo" not in repr(dict(conta)).lower()
    colunas = db.fetch(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND column_name ILIKE '%email%'"
    )
    assert {(c["table_name"], c["column_name"]) for c in colunas} == {
        ("contas", "email_hash"),
        ("verificacoes_email", "email_hash"),
    }


def test_resposta_igual_com_ou_sem_conta(client, pessoa):
    existente = pessoa()
    antes = len(caixa(client))
    com = client.post("/api/auth/email/entrar", json={"email": existente.email})
    sem = client.post("/api/auth/email/entrar", json={"email": novo_email()})
    assert com.status_code == sem.status_code == 202
    assert com.json().keys() == sem.json().keys() == {"verificacao_id"}
    assert len(caixa(client)) == antes + 1  # só quem tem conta recebe e-mail
    # o id "falso" se comporta como um código expirado
    r = client.post(
        "/api/auth/email/confirmar", json={"verificacao_id": sem.json()["verificacao_id"], "codigo": "000000"}
    )
    assert r.status_code == 400


def test_cadastro_com_email_ja_usado_entra_na_conta_existente(client, pessoa):
    p = pessoa()
    r = client.post("/api/auth/email/cadastro", json={**CADASTRO, "email": p.email, "handle": "outro_apelido"})
    assert r.status_code == 202  # ninguém descobre que o e-mail já tem conta
    entrou = confirmar(client, r.json()["verificacao_id"], p.email)
    assert entrou.json()["handle"] == p.handle and entrou.json()["novo"] is False


def test_email_normalizado_encontra_a_mesma_conta(client):
    r = criar_conta(client, "ana.normal@exemplo.com")
    assert entrar_por_email(client, "  Ana.Normal@EXEMPLO.com ").json()["handle"] == r.json()["handle"]


def test_codigo_errado_tem_limite_de_tentativas(client, pessoa):
    p = pessoa()
    pedido = client.post("/api/auth/email/entrar", json={"email": p.email}).json()
    codigo, _ = ultimo_email(client, p.email)
    errado = "000000" if codigo != "000000" else "111111"
    for _ in range(MAX_TENTATIVAS - 1):
        r = client.post("/api/auth/email/confirmar", json={**pedido, "codigo": errado})
        assert r.status_code == 400 and r.json()["detail"] == "Código incorreto."
    # a quinta tentativa errada destrói a verificação: nem o código certo vale mais
    r = client.post("/api/auth/email/confirmar", json={**pedido, "codigo": errado})
    assert "Peça um novo" in r.json()["detail"]
    assert client.post("/api/auth/email/confirmar", json={**pedido, "codigo": codigo}).status_code == 400


def test_codigo_vale_uma_vez_e_expira(client, pessoa, db):
    p = pessoa()
    pedido = client.post("/api/auth/email/entrar", json={"email": p.email}).json()
    codigo, _ = ultimo_email(client, p.email)
    assert client.post("/api/auth/email/confirmar", json={**pedido, "codigo": codigo}).status_code == 200
    client.cookies.clear()
    assert client.post("/api/auth/email/confirmar", json={**pedido, "codigo": codigo}).status_code == 400

    pedido = client.post("/api/auth/email/entrar", json={"email": p.email}).json()
    codigo, _ = ultimo_email(client, p.email)
    db.execute("UPDATE verificacoes_email SET expira_em = now() - interval '1 second'")
    assert client.post("/api/auth/email/confirmar", json={**pedido, "codigo": codigo}).status_code == 400


def test_pedido_novo_invalida_o_anterior(client, pessoa):
    p = pessoa()
    primeiro = client.post("/api/auth/email/entrar", json={"email": p.email}).json()
    codigo_antigo, _ = ultimo_email(client, p.email)
    client.post("/api/auth/email/entrar", json={"email": p.email})
    r = client.post("/api/auth/email/confirmar", json={**primeiro, "codigo": codigo_antigo})
    assert r.status_code == 400


def test_link_magico_uso_unico(client):
    email = novo_email()
    client.post("/api/auth/email/cadastro", json={**CADASTRO, "email": email})
    _, token = ultimo_email(client, email)
    mensagem = caixa(client)[-1].texto
    assert "http://testserver/#/verificar/" in mensagem  # token no fragmento: não vai para logs/Referer
    r = client.post("/api/auth/email/link", json={"token": token})
    client.cookies.clear()
    assert r.status_code == 200 and r.json()["novo"] is True
    assert client.post("/api/auth/email/link", json={"token": token}).status_code == 400
    assert client.post("/api/auth/email/link", json={"token": "x" * 43}).status_code == 400


def test_texto_do_email_e_discreto(client):
    email = novo_email()
    client.post("/api/auth/email/cadastro", json={**CADASTRO, "email": email})
    m = caixa(client)[-1]
    assert m.assunto == "Seu código de acesso"
    assert not re.search(r"afinidade|fetiche|sexo|namoro", (m.assunto + m.texto).lower())


def test_limite_de_envios_por_email(client, pessoa):
    p = pessoa()  # o cadastro já contou 1 envio
    codigos = [client.post("/api/auth/email/entrar", json={"email": p.email}).status_code for _ in range(5)]
    assert codigos == [202, 202, 202, 202, 429]


def test_apelido_do_cadastro_pendente_tomado_antes_da_confirmacao(client):
    email_a, email_b = novo_email(), novo_email()
    a = client.post("/api/auth/email/cadastro", json={**CADASTRO, "email": email_a, "handle": "disputado"}).json()
    b = client.post("/api/auth/email/cadastro", json={**CADASTRO, "email": email_b, "handle": "disputado"}).json()
    assert confirmar(client, a["verificacao_id"], email_a).status_code == 200
    assert confirmar(client, b["verificacao_id"], email_b).status_code == 409


def test_duas_verificacoes_de_cadastro_do_mesmo_email(client, db):
    # Pedidos em sequência: o segundo invalida o primeiro. Mas se a conta nascer por outro caminho
    # antes de confirmar, quem tem o código entra na conta que já existe.
    email = novo_email()
    pedido = client.post("/api/auth/email/cadastro", json={**CADASTRO, "email": email}).json()
    codigo, _ = ultimo_email(client, email)
    from app.config import config
    from app.verificacao import hash_email

    db.execute(
        "INSERT INTO contas (handle, email_hash, adulto_confirmado_em, consentimento_em) VALUES ($1, $2, now(), now())",
        "chegou_antes",
        hash_email(config().email_pepper, email),
    )
    r = client.post("/api/auth/email/confirmar", json={**pedido, "codigo": codigo})
    client.cookies.clear()
    assert r.status_code == 200 and r.json()["handle"] == "chegou_antes"


def test_sessao_por_email_funciona_e_limpeza(client, db):
    import asyncio

    import asyncpg

    from app import verificacao
    from tests.conftest import URL

    r = criar_conta(client)
    assert client.get("/api/perfil", headers=bearer(r)).status_code == 404  # logado, sem perfil ainda
    client.post("/api/auth/email/entrar", json={"email": novo_email()})
    client.post("/api/auth/email/cadastro", json={**CADASTRO, "email": novo_email()})
    db.execute("UPDATE verificacoes_email SET expira_em = now() - interval '1 minute'")

    async def limpar():
        con = await asyncpg.connect(URL)
        try:
            return await verificacao.apagar_expiradas(con)
        finally:
            await con.close()

    assert asyncio.run(limpar()) >= 1
