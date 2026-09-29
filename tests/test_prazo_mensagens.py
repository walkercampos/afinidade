"""Parte 6: prazo das mensagens acordado entre as duas pessoas."""

from datetime import datetime, timedelta

from app import mensagens
from tests.test_chat import limpar


def _prazo(p, outro):
    return p.get(f"/api/conversas/{outro.id}/prazo")


def _enviar(p, outro, texto="oi"):
    r = p.post(f"/api/conversas/{outro.id}/mensagens", json={"texto": texto})
    assert r.status_code == 201, r.text
    return r.json()


def test_lista_de_prazos_igual_no_python_e_no_banco(client, db):
    for prazo in mensagens.PRAZOS_PERMITIDOS:
        assert db.fetchval("SELECT ttl_mensagem_valido($1)", prazo) is True
    permitidos_no_banco = db.fetch("SELECT m FROM generate_series(1, 300000) m WHERE ttl_mensagem_valido(m::int)")
    assert sorted(r["m"] for r in permitidos_no_banco) == sorted(p for p in mensagens.PRAZOS_PERMITIDOS if p)


def test_situacao_inicial(conexao_entre):
    a, b = conexao_entre()
    s = _prazo(a, b).json()
    assert s["ttl_minutos"] == s["padrao"] == 1440
    assert s["proposta"] is None and None in s["opcoes"] and 5 in s["opcoes"]


def test_mudar_prazo_exige_as_duas_pessoas_e_vale_so_para_as_proximas(conexao_entre, db):
    a, b = conexao_entre()
    antiga = _enviar(a, b, "antes")

    # A propõe 1 hora: nada muda até B confirmar
    s = a.post(f"/api/conversas/{b.id}/prazo", json={"ttl_minutos": 60}).json()
    assert s["ttl_minutos"] == 1440 and s["proposta"]["ttl_minutos"] == 60 and s["proposta"]["minha"] is True
    assert _enviar(a, b, "durante")["ttl_minutos"] == 1440
    # Quem propôs não pode confirmar a própria proposta
    assert a.post(f"/api/conversas/{b.id}/prazo/confirmar").status_code == 409

    # B vê a proposta como da outra pessoa e confirma
    assert _prazo(b, a).json()["proposta"]["minha"] is False
    s = b.post(f"/api/conversas/{a.id}/prazo/confirmar").json()
    assert s["ttl_minutos"] == 60 and s["proposta"] is None

    # Vale para as mensagens enviadas depois, pelos dois lados; as antigas mantêm o prazo delas
    assert _enviar(a, b, "depois")["ttl_minutos"] == 60
    assert _enviar(b, a, "resposta")["ttl_minutos"] == 60
    assert db.fetchval("SELECT ttl_minutos FROM mensagens WHERE id = $1", antiga["id"]) == 1440

    [*_, ultima] = b.get(f"/api/conversas/{a.id}/mensagens").json()
    assert ultima["texto"] == "resposta"
    lidas = {m["texto"]: m for m in b.get(f"/api/conversas/{a.id}/mensagens").json()}
    depois = lidas["depois"]
    assert datetime.fromisoformat(depois["expira_em"]) - datetime.fromisoformat(depois["lida_em"]) == timedelta(hours=1)


def test_nunca_expira(conexao_entre, db):
    a, b = conexao_entre()
    a.post(f"/api/conversas/{b.id}/prazo", json={"ttl_minutos": None})
    b.post(f"/api/conversas/{a.id}/prazo/confirmar")
    m = _enviar(a, b, "para sempre")
    assert m["ttl_minutos"] is None
    [lida] = b.get(f"/api/conversas/{a.id}/mensagens").json()
    assert lida["lida_em"] is not None and lida["expira_em"] is None
    db.execute("UPDATE mensagens SET lida_em = now() - interval '5 years' WHERE id = $1", m["id"])
    limpar()
    assert [x["texto"] for x in a.get(f"/api/conversas/{b.id}/mensagens").json()] == ["para sempre"]


def test_nao_lida_nao_expira(conexao_entre, db):
    a, b = conexao_entre()
    m = _enviar(a, b, "guardada")
    db.execute("UPDATE mensagens SET criado_em = now() - interval '400 days' WHERE id = $1", m["id"])
    limpar()
    assert [x["texto"] for x in b.get(f"/api/conversas/{a.id}/mensagens").json()] == ["guardada"]


def test_propostas_invalidas_recusar_e_desistir(conexao_entre, pessoa):
    a, b = conexao_entre()
    assert a.post(f"/api/conversas/{b.id}/prazo", json={"ttl_minutos": 7}).status_code == 409
    assert a.post(f"/api/conversas/{b.id}/prazo", json={"ttl_minutos": 1440}).status_code == 409  # já é o atual
    assert b.post(f"/api/conversas/{a.id}/prazo/confirmar").status_code == 409  # não há proposta

    # B recusa a proposta de A
    a.post(f"/api/conversas/{b.id}/prazo", json={"ttl_minutos": 5})
    assert b.delete(f"/api/conversas/{a.id}/prazo/proposta").status_code == 204
    assert _prazo(a, b).json()["proposta"] is None

    # Uma proposta nova substitui a anterior, mesmo que venha da outra pessoa
    a.post(f"/api/conversas/{b.id}/prazo", json={"ttl_minutos": 5})
    b.post(f"/api/conversas/{a.id}/prazo", json={"ttl_minutos": 10080})
    assert a.post(f"/api/conversas/{b.id}/prazo/confirmar").json()["ttl_minutos"] == 10080

    # Quem não é conexão não vê nem mexe no prazo
    estranha = pessoa()
    assert _prazo(estranha, a).status_code == 404
    assert estranha.post(f"/api/conversas/{a.id}/prazo", json={"ttl_minutos": 5}).status_code == 404


def test_proposta_vencida_nao_vale_e_e_limpa(conexao_entre, db):
    a, b = conexao_entre()
    a.post(f"/api/conversas/{b.id}/prazo", json={"ttl_minutos": 30})
    db.execute("UPDATE propostas_ttl SET criado_em = now() - interval '8 days', expira_em = now() - interval '1 day'")
    assert _prazo(b, a).json()["proposta"] is None
    assert b.post(f"/api/conversas/{a.id}/prazo/confirmar").status_code == 409
    limpar()
    assert db.fetchval("SELECT count(*) FROM propostas_ttl WHERE proposto_por = $1::uuid", a.id) == 0
