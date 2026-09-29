"""Fluxos principais da API (cadastro, perfil, descoberta, curtidas, bloqueio, segurança)."""

import pytest

from app import VERSAO
from tests.conftest import CADASTRO, bearer, criar_conta, entrar_por_email, novo_email

pytestmark = pytest.mark.usefixtures("client")


def registrar(client, handle, genero, busca_por, quero=(), curioso=(), limite=()):
    r = criar_conta(client, f"{handle}@teste.invalid", handle)
    assert r.status_code == 200, r.text
    h = bearer(r)
    r = client.put(
        "/api/perfil",
        headers=h,
        json={
            "nome_exibicao": handle.title(),
            "genero": genero,
            "busca_por": busca_por,
            "tags_interesses": {"quero": list(quero), "curioso": list(curioso), "limite_absoluto": list(limite)},
        },
    )
    assert r.status_code == 200, r.text
    return h, r.json()["id"]


def test_fluxo_completo(client):
    alfa, _ = registrar(
        client,
        "alfa",
        "homem-cis",
        ["mulher-cis", "mulher-trans"],
        quero=["bondage", "leather", "dirty-talk"],
        curioso=["impact-play", "voyeurism"],
        limite=["ageplay", "urophilia"],
    )
    beta, beta_id = registrar(
        client,
        "beta",
        "mulher-cis",
        ["homem-cis"],
        quero=["bondage", "dirty-talk", "impact-play"],
        curioso=["leather"],
        limite=["urophilia"],
    )
    # Busca outro gênero -> fora pela camada 1
    registrar(client, "gama", "mulher-cis", ["mulher-cis"], quero=["bondage"])
    # Quer algo que é limite de alfa -> fora pela camada 2
    registrar(client, "delta", "mulher-trans", ["homem-cis"], quero=["bondage", "urophilia"])
    # Compatível, mas com afinidade menor
    _, eps_id = registrar(client, "epsilon", "mulher-trans", ["homem-cis", "mulher-cis"], curioso=["bondage"])

    # Outros módulos de teste criam pessoas no mesmo banco: olhamos só as deste teste.
    def ids_do_teste(feed):
        return [c["perfil"]["id"] for c in feed if c["perfil"]["id"] in {beta_id, eps_id}]

    feed = [c for c in client.get("/api/descobrir", headers=alfa).json() if c["perfil"]["id"] in {beta_id, eps_id}]
    assert ids_do_teste(feed) == [beta_id, eps_id]
    top = feed[0]["compatibilidade"]
    assert top["score_porcentagem"] == 91
    assert top["tags_em_comum"] == ["bondage", "dirty-talk", "impact-play", "leather"]
    assert "limite_absoluto" not in feed[0]["perfil"]

    # Curtida recíproca vira conexão
    assert client.post(f"/api/perfis/{beta_id}/curtir", headers=alfa).json() == {"conexao": False}
    alfa_id = client.get("/api/perfil", headers=alfa).json()["id"]
    assert client.post(f"/api/perfis/{alfa_id}/curtir", headers=beta).json() == {"conexao": True}
    assert [p["id"] for p in client.get("/api/conexoes", headers=alfa).json()] == [beta_id]
    # Quem já foi curtido sai do feed
    assert ids_do_teste(client.get("/api/descobrir", headers=alfa).json()) == [eps_id]

    # Bloqueio desfaz a conexão e esconde o perfil nas duas direções
    assert client.post(f"/api/perfis/{alfa_id}/bloquear", headers=beta).status_code == 204
    assert client.get("/api/conexoes", headers=alfa).json() == []
    assert client.get(f"/api/perfis/{beta_id}", headers=alfa).status_code == 404
    assert client.get(f"/api/perfis/{alfa_id}", headers=beta).status_code == 404


def test_nao_pode_curtir_quem_nao_passa_nos_filtros(client):
    h, _ = registrar(client, "zeta", "homem-cis", ["mulher-cis"], quero=["urophilia"])
    alvo_id = client.get("/api/perfil", headers=bearer(entrar_por_email(client, "alfa@teste.invalid"))).json()["id"]
    r = client.post(f"/api/perfis/{alvo_id}/curtir", headers=h)
    assert r.status_code == 403


def test_validacoes(client):
    menor = client.post(
        "/api/auth/email/cadastro", json={**CADASTRO, "email": novo_email(), "data_nascimento": "2015-01-01"}
    )
    assert menor.status_code == 422

    h, _ = registrar(client, "eta", "agenero", ["agenero"])
    mesmo_nivel = client.put(
        "/api/perfil",
        headers=h,
        json={
            "nome_exibicao": "Eta",
            "genero": "agenero",
            "busca_por": ["agenero"],
            "tags_interesses": {"quero": ["bondage"], "limite_absoluto": ["bondage"]},
        },
    )
    assert mesmo_nivel.status_code == 422
    inexistente = client.put(
        "/api/perfil",
        headers=h,
        json={
            "nome_exibicao": "Eta",
            "genero": "agenero",
            "busca_por": ["agenero"],
            "tags_interesses": {"quero": ["nao-existe"]},
        },
    )
    assert inexistente.status_code == 422
    assert client.get("/api/descobrir").status_code == 401


def test_excluir_conta_remove_tudo(client):
    h, _ = registrar(client, "theta", "outro", ["outro"])
    assert client.delete("/api/conta", headers=h).status_code == 204
    assert client.get("/api/perfil", headers=h).status_code == 401
    # O e-mail sai junto: cadastrar de novo com ele cria uma conta NOVA
    r = criar_conta(client, "theta@teste.invalid")
    assert r.json()["novo"] is True and r.json()["handle"] != "theta"


def test_simular(client):
    from tests.test_matcher import ALFA, BETA

    r = client.post("/api/match/simular", json={"usuario_a": ALFA, "usuario_b": BETA}).json()
    assert r["score_porcentagem"] == 91 and r["score_mutuo"] == 96


def test_cabecalhos_de_seguranca_e_front(client):
    r = client.get("/")
    assert r.status_code == 200 and "<main" in r.text
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert client.get("/api/catalogo/tags").headers["cache-control"] == "no-store"


def test_cookie_httponly_e_csrf(client):
    c = client
    try:
        email = novo_email()
        pedido = c.post("/api/auth/email/cadastro", json={**CADASTRO, "email": email}).json()
        from tests.conftest import ultimo_email

        codigo, _ = ultimo_email(c, email)
        r = c.post("/api/auth/email/confirmar", json={"verificacao_id": pedido["verificacao_id"], "codigo": codigo})
        cookie = r.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie
        corpo = {"nome_exibicao": "Iota", "genero": "outro", "busca_por": ["outro"]}
        # Cookie sem o header anti-CSRF é recusado em escrita, aceito em leitura.
        assert c.put("/api/perfil", json=corpo).status_code == 403
        assert c.put("/api/perfil", json=corpo, headers={"X-CSRF": "1"}).status_code == 200
        assert c.get("/api/perfil").status_code == 200
    finally:
        c.cookies.clear()


def test_sair_invalida_tokens_antigos(client):
    h, _ = registrar(client, "kappa", "outro", ["outro"])
    assert client.post("/api/auth/sair", headers=h).status_code == 204
    assert client.get("/api/perfil", headers=h).status_code == 401
    assert client.get("/api/perfil", headers=bearer(entrar_por_email(client, "kappa@teste.invalid"))).status_code == 200


def test_consentimento_obrigatorio(client):
    r = client.post(
        "/api/auth/email/cadastro", json={**CADASTRO, "email": novo_email(), "consinto_dados_sensiveis": False}
    )
    assert r.status_code == 422


def test_apelido_gerado_automaticamente(client):
    email = novo_email()
    r = criar_conta(client, email)
    assert r.status_code == 200 and r.json()["novo"] is True
    handle = r.json()["handle"]
    assert handle.startswith("anon_") and len(handle) == 13
    assert entrar_por_email(client, email).json()["handle"] == handle


def test_apelido_repetido(client, pessoa):
    p = pessoa()
    r = client.post("/api/auth/email/cadastro", json={**CADASTRO, "email": novo_email(), "handle": p.handle})
    assert r.status_code == 409


def test_saude(client):
    assert client.get("/api/saude").json() == {"status": "ok", "versao": "dev", "lancamento": VERSAO}
