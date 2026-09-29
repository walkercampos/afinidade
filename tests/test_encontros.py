"""Parte 9: encontro compartilhado com contato de confiança, check-in e alerta."""

import asyncio
from datetime import UTC, datetime, timedelta

import asyncpg

from app import encontros

CONTATO = "irma@teste.invalid"


def _quando(horas: float) -> str:
    return (datetime.now(UTC) + timedelta(hours=horas)).isoformat()


def _novo(p, **extra):
    dados = {
        "local": "Café Central, Rua das Flores 100",
        "observacoes": "Primeiro encontro, volto de táxi",
        "como_te_conhecem": "Ana, sua irmã",
        "contato_email": CONTATO,
        "inicio_em": _quando(1),
        "checkin_ate": _quando(4),
        **extra,
    }
    return p.post("/api/encontros", json=dados)


def _caixa(client, para=CONTATO):
    return [m for m in client.app.state.carteiro.caixa if m.para == para]


def _disparar(client) -> int:
    from tests.conftest import URL

    async def rodar():
        con = await asyncpg.connect(URL)
        try:
            return await encontros.disparar_alertas(con, client.app.state.cifrador_encontros, client.app.state.carteiro)
        finally:
            await con.close()

    return asyncio.run(rodar())


def test_registrar_avisa_o_contato_e_guarda_cifrado(client, conexao_entre, db):
    a, b = conexao_entre()
    antes = len(_caixa(client))
    r = _novo(a, com=b.id)
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["situacao"] == "agendado" and e["local"].startswith("Café Central") and e["com_handle"] == b.handle
    # O contato recebe só o aviso de indicação, sem local nem horário
    [aviso] = _caixa(client)[antes:]
    assert (
        "contato de confiança" in aviso.assunto and "Café Central" not in aviso.texto and "Ana, sua irmã" in aviso.texto
    )
    # No banco, local e e-mail do contato só cifrados
    linha = db.fetchrow("SELECT detalhes, contato_confianca FROM encontros WHERE id = $1::uuid", e["id"])
    assert b"Caf" not in linha["detalhes"] and b"irma@" not in linha["contato_confianca"]
    assert [x["id"] for x in a.get("/api/encontros").json()] == [e["id"]]
    assert b.get("/api/encontros").json() == []  # a outra pessoa não vê


def test_horarios_e_conexao_validados(conexao_entre, pessoa):
    a, b = conexao_entre()
    casos = [
        {"checkin_ate": _quando(0.5)},  # antes do início
        {"checkin_ate": _quando(26)},  # mais de 24 h depois do início
        {"inicio_em": _quando(-13), "checkin_ate": _quando(1)},  # começou há mais de 12 h
        {"inicio_em": _quando(-5), "checkin_ate": _quando(-1)},  # check-in já passou
        {"inicio_em": _quando(24 * 61), "checkin_ate": _quando(24 * 61 + 1)},  # antecedência demais
        {"inicio_em": "2026-10-01T20:00:00"},  # sem fuso horário
    ]
    for extra in casos:
        assert _novo(a, **extra).status_code == 422, extra
    estranha = pessoa()
    assert _novo(a, com=estranha.id).status_code == 404  # só com uma conexão de verdade
    assert _novo(a, contato_email="nao-e-email").status_code == 422
    assert _novo(a).status_code == 201  # sem "com quem" também vale


def test_sem_checkin_o_contato_recebe_o_alerta_uma_vez(client, conexao_entre, db):
    a, b = conexao_entre()
    e = _novo(a, com=b.id).json()
    assert _disparar(client) == 0  # ainda no prazo
    db.execute(
        "UPDATE encontros SET inicio_em = now() - interval '3 hours', checkin_ate = now() - interval '1 minute'"
        " WHERE id = $1::uuid",
        e["id"],
    )
    antes = len(_caixa(client))
    assert _disparar(client) == 1
    [alerta] = _caixa(client)[antes:]
    assert alerta.assunto.startswith("Alerta") and "Café Central" in alerta.texto and f"@{b.handle}" in alerta.texto
    assert "190" in alerta.texto and "180" in alerta.texto
    assert _disparar(client) == 0  # uma vez só
    assert a.get("/api/encontros").json()[0]["situacao"] == "alerta_enviado"


def test_checkin_e_cancelamento_evitam_o_alerta(client, conexao_entre, db, pessoa):
    a, b = conexao_entre()
    ok, cancelado = _novo(a).json(), _novo(a).json()
    intrusa = pessoa()
    assert intrusa.post(f"/api/encontros/{ok['id']}/checkin").status_code == 404
    assert a.post(f"/api/encontros/{ok['id']}/checkin").status_code == 204
    assert a.post(f"/api/encontros/{cancelado['id']}/cancelar").status_code == 204
    assert a.post(f"/api/encontros/{ok['id']}/cancelar").status_code == 404  # já encerrado
    db.execute(
        "UPDATE encontros SET checkin_ate = now() - interval '1 minute', inicio_em = now() - interval '2 hours'"
        " WHERE conta_id = $1::uuid",
        a.id,
    )
    assert _disparar(client) == 0
    assert {x["situacao"] for x in a.get("/api/encontros").json()} == {"confirmado_ok", "cancelado"}


def test_falha_num_envio_nao_atrasa_os_outros(client, conexao_entre, db, monkeypatch):
    a, _ = conexao_entre()
    ruim = _novo(a, contato_email="quebrado@teste.invalid").json()
    bom = _novo(a).json()
    db.execute(
        "UPDATE encontros SET inicio_em = now() - interval '2 hours', checkin_ate = now() - interval '1 minute'"
        " WHERE conta_id = $1::uuid",
        a.id,
    )
    carteiro = client.app.state.carteiro
    original = carteiro.enviar

    async def falhar_para_um(m):
        if m.para == "quebrado@teste.invalid":
            raise RuntimeError("caixa de e-mail inexistente")
        await original(m)

    monkeypatch.setattr(carteiro, "enviar", falhar_para_um)
    assert _disparar(client) == 1  # o outro alerta saiu
    situacoes = dict(db.fetch("SELECT id::text, situacao FROM encontros WHERE conta_id = $1::uuid", a.id))
    assert situacoes == {ruim["id"]: "agendado", bom["id"]: "alerta_enviado"}  # o que falhou tenta de novo
    monkeypatch.undo()
    assert _disparar(client) == 1
