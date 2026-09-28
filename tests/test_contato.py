"""Falar com a pessoa pelo e-mail dela, sem revelar o endereço a quem envia."""

import pytest

from app import admin, contato
from app.cripto import Cifrador


def test_moderacao_envia_aviso_sem_ver_o_email(client, pessoa, db):
    alvo, mod = pessoa(), pessoa()
    admin.main(["moderador", mod.handle])
    antes = len(client.app.state.carteiro.caixa)
    r = mod.post(f"/api/moderacao/contas/{alvo.id}/aviso", json={"assunto": "Aviso da moderação", "mensagem": "Olá!"})
    assert r.status_code == 204 and r.content == b""  # a resposta não traz o endereço
    [enviada] = client.app.state.carteiro.caixa[antes:]
    assert enviada.para == alvo.email and enviada.assunto == "Aviso da moderação" and "Olá!" in enviada.texto
    log = db.fetchrow("SELECT * FROM contatos_log WHERE conta_id = $1::uuid", alvo.id)
    assert log["enviado_por"] == mod.handle and log["assunto"] == "Aviso da moderação"


def test_so_moderadores_podem_avisar(pessoa):
    a, b = pessoa(), pessoa()
    assert (
        a.post(f"/api/moderacao/contas/{b.id}/aviso", json={"assunto": "Oi oi", "mensagem": "spam"}).status_code == 404
    )


def test_aviso_para_conta_sem_email(client, pessoa, db):
    alvo, mod = pessoa(), pessoa()
    admin.main(["moderador", mod.handle])
    db.execute("UPDATE contas SET email_cifrado = NULL WHERE id = $1::uuid", alvo.id)
    r = mod.post(f"/api/moderacao/contas/{alvo.id}/aviso", json={"assunto": "Aviso", "mensagem": "Olá, tudo bem?"})
    assert r.status_code == 404


def test_linha_de_comando_avisar(client, pessoa, db, monkeypatch, capsys):
    # A CLI cria o próprio carteiro a partir da configuração: nos testes, o de memória.
    from app.email import CarteiroMemoria

    caixa = CarteiroMemoria()
    monkeypatch.setattr(admin, "criar_carteiro", lambda _cfg: caixa)
    p = pessoa()
    assert admin.main(["avisar", p.handle, "Sua conta", "Mensagem da equipe"]) == 0
    assert caixa.caixa[0].para == p.email
    assert db.fetchval("SELECT enviado_por FROM contatos_log WHERE conta_id = $1::uuid", p.id) == "cli"
    assert admin.main(["avisar", "ninguem_aqui", "A", "B"]) == 1


def test_mascarar():
    assert contato.mascarar("ana.souza@gmail.com") == "a****@gmail.com"
    assert contato.mascarar("jo@x.co") == "j****@x.co"  # mesmo tamanho de máscara: não revela o comprimento


def test_chaves_de_dominios_diferentes_nao_se_abrem():
    mesma = "s" * 32
    blob = Cifrador(mesma, b"matchmaking/mensagens/v1").cifrar("oi", b"ctx")
    with pytest.raises(ValueError):
        contato.criar_cifrador(mesma).decifrar(blob, b"ctx")
