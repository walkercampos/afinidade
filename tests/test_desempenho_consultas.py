"""Regressões do teste de carga (docs/carga/): as consultas quentes precisam PODER usar índice.

Num banco de teste pequeno o PostgreSQL prefere ler a tabela inteira (é mais barato), então cada
teste desliga a leitura sequencial: se a consulta ainda assim ler a tabela inteira, é porque não
existe caminho por índice, e em produção o custo cresce com o tamanho da tabela.
"""

import uuid

from app import descoberta
from app import mensagens as M

A, B = uuid.uuid4(), uuid.uuid4()


def _plano(db, sql, *args):
    db.execute("SET enable_seqscan = off")
    try:
        return "\n".join(r[0] for r in db.fetch("EXPLAIN " + sql, *args))
    finally:
        db.execute("RESET enable_seqscan")


def test_mensagens_da_conversa_usam_o_indice_do_par(client, db):
    plano = _plano(
        db,
        f"SELECT m.id FROM mensagens m WHERE {M._DA_CONVERSA} AND {M._VISIVEL} AND m.id > $3 ORDER BY m.id LIMIT $4",
        A,
        B,
        0,
        50,
    )
    assert "Seq Scan on mensagens" not in plano, plano
    assert "mensagens_conversa_idx" in plano


def test_lista_de_conversas_usa_indices_de_remetente_e_destinatario(client, db):
    plano = _plano(
        db,
        f"""SELECT CASE WHEN m.de_id = $1 THEN m.para_id ELSE m.de_id END, count(*)
            FROM mensagens m WHERE (m.de_id = $1 OR m.para_id = $1) AND {M._VISIVEL} GROUP BY 1""",
        A,
    )
    assert "Seq Scan on mensagens" not in plano, plano


def test_par_da_conversa_nao_depende_da_ordem(client, conexao_entre):
    """A reescrita com LEAST/GREATEST continua achando as mensagens dos dois lados."""
    a, b = conexao_entre()
    assert a.post(f"/api/conversas/{b.id}/mensagens", json={"texto": "de a"}).status_code == 201
    assert b.post(f"/api/conversas/{a.id}/mensagens", json={"texto": "de b"}).status_code == 201
    textos_a = [m["texto"] for m in a.get(f"/api/conversas/{b.id}/mensagens").json()]
    textos_b = [m["texto"] for m in b.get(f"/api/conversas/{a.id}/mensagens").json()]
    assert textos_a == textos_b == ["de a", "de b"]


def test_descoberta_nao_precisa_ler_todos_os_perfis(client, db):
    eu = {
        "conta_id": A,
        "tags_quero": [1],
        "tags_curioso": [],
        "tags_limite": [],
        "lat_aprox": None,
        "lon_aprox": None,
        "distancia_max_km": None,
        "busca_por": [1, 2],
        "genero_id": 1,
    }
    sql, params = descoberta._consulta(eu, limite=20, inatividade_dias=30)
    plano = _plano(db, sql, *params)
    # Qual índice o planejador escolhe num banco minúsculo varia; o que importa é existir caminho
    # sem ler a tabela inteira. Com 30 mil perfis ele usa perfis_ativos_idx (docs/carga/).
    assert "Seq Scan on perfis" not in plano, plano
