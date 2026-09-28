from app import admin


def test_promover_e_rebaixar(pessoa, db):
    p = pessoa()
    assert admin.main(["moderador", p.handle.upper()]) == 0
    assert db.fetchval("SELECT papel FROM contas WHERE id = $1::uuid", p.id) == "moderador"
    assert admin.main(["usuario", p.handle]) == 0
    assert db.fetchval("SELECT papel FROM contas WHERE id = $1::uuid", p.id) == "usuario"


def test_conta_inexistente_e_uso_errado(client, capsys):
    assert admin.main(["moderador", "ninguem_aqui"]) == 1
    assert admin.main([]) == 2
    assert admin.main(["migrar"]) == 0
    assert "nenhuma" in capsys.readouterr().out
