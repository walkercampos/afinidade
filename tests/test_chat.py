from datetime import datetime, timedelta


def test_so_conexoes_conversam(pessoa):
    a = pessoa("homem-cis", ["mulher-cis"], quero=["latex"])
    b = pessoa("mulher-cis", ["homem-cis"], quero=["latex"])
    a.post(f"/api/perfis/{b.id}/curtir")  # curtida só de um lado
    assert a.post(f"/api/conversas/{b.id}/mensagens", json={"texto": "oi"}).status_code == 404


def test_mensagem_cifrada_no_banco(conexao_entre, db):
    a, b = conexao_entre()
    a.post(f"/api/conversas/{b.id}/mensagens", json={"texto": "segredo-muito-especifico"})
    blob = db.fetchval("SELECT conteudo FROM mensagens WHERE de_id = $1::uuid", a.id)
    assert b"segredo-muito-especifico" not in blob and len(blob) > 20


def test_some_24_horas_depois_de_lida_por_padrao(conexao_entre, db):
    a, b = conexao_entre()
    enviada = a.post(f"/api/conversas/{b.id}/mensagens", json={"texto": "oi"}).json()
    assert enviada["lida_em"] is None and enviada["expira_em"] is None
    assert enviada["ttl_minutos"] == 1440

    # Ler marca como lida e inicia as 24 horas
    [recebida] = b.get(f"/api/conversas/{a.id}/mensagens").json()
    lida = datetime.fromisoformat(recebida["lida_em"])
    assert datetime.fromisoformat(recebida["expira_em"]) - lida == timedelta(hours=24)
    # Quem enviou também vê o prazo (e deve apagar da tela no mesmo instante)
    assert a.get(f"/api/conversas/{b.id}/mensagens").json()[0]["expira_em"] == recebida["expira_em"]

    # Passado o prazo, some da API na hora, mesmo antes da limpeza física...
    db.execute("UPDATE mensagens SET lida_em = now() - interval '24 hours 1 second' WHERE id = $1", enviada["id"])
    assert a.get(f"/api/conversas/{b.id}/mensagens").json() == []
    assert b.get(f"/api/conversas/{a.id}/mensagens").json() == []
    # ... e a limpeza periódica remove do banco
    assert limpar() >= 1
    assert db.fetchval("SELECT count(*) FROM mensagens WHERE id = $1", enviada["id"]) == 0


def limpar() -> int:
    import asyncio

    import asyncpg

    from app import mensagens
    from tests.conftest import URL

    async def rodar():
        con = await asyncpg.connect(URL)
        try:
            return await mensagens.apagar_expiradas(con)
        finally:
            await con.close()

    return asyncio.run(rodar())


def test_conversas_e_novas_mensagens(conexao_entre):
    a, b = conexao_entre()
    m1 = a.post(f"/api/conversas/{b.id}/mensagens", json={"texto": "um"}).json()
    a.post(f"/api/conversas/{b.id}/mensagens", json={"texto": "dois"})
    conversa = next(c for c in b.get("/api/conversas").json() if c["perfil"]["id"] == a.id)
    assert conversa["nao_lidas"] == 2
    novas = b.get(f"/api/conversas/{a.id}/mensagens", params={"apos": m1["id"]}).json()
    assert [m["texto"] for m in novas] == ["dois"]


def test_bloqueio_apaga_a_conversa(conexao_entre, db):
    a, b = conexao_entre()
    a.post(f"/api/conversas/{b.id}/mensagens", json={"texto": "oi"})
    b.post(f"/api/perfis/{a.id}/bloquear")
    assert db.fetchval("SELECT count(*) FROM mensagens WHERE de_id = ANY($1::uuid[])", [a.id, b.id]) == 0
    assert a.post(f"/api/conversas/{b.id}/mensagens", json={"texto": "?"}).status_code == 404


def test_denuncia_leva_evidencias_cifradas(conexao_entre, db, pessoa):
    from app import admin

    a, b = conexao_entre()
    b.post(f"/api/conversas/{a.id}/mensagens", json={"texto": "mensagem abusiva"})
    a.post(f"/api/perfis/{b.id}/denunciar", json={"motivo": "assedio", "incluir_mensagens": True})
    blob = db.fetchval("SELECT evidencias FROM denuncias WHERE denunciado_id = $1::uuid", b.id)
    assert blob and b"abusiva" not in blob

    mod = pessoa()
    admin.main(["moderador", mod.handle])
    item = next(i for i in mod.get("/api/moderacao/fila").json() if i["conta_id"] == b.id)
    [evidencia] = item["denuncias"][0]["evidencias"]
    assert evidencia["texto"] == "mensagem abusiva" and evidencia["de"] == "denunciado"


def test_apagar_minhas_mensagens(conexao_entre):
    a, b = conexao_entre()
    a.post(f"/api/conversas/{b.id}/mensagens", json={"texto": "minha"})
    b.post(f"/api/conversas/{a.id}/mensagens", json={"texto": "dela"})
    assert a.delete(f"/api/conversas/{b.id}/mensagens").status_code == 204
    assert [m["texto"] for m in b.get(f"/api/conversas/{a.id}/mensagens").json()] == ["dela"]
