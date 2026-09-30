"""Semeador do teste de carga (carga/semear.py): nunca toca produção e gera dados coerentes."""

import pytest

from carga.semear import DestinoProibido, conferir_destino, gerar_contas, id_da_conta, par_de

BANCO_OK = "postgresql://u:s@localhost:5432/afinidade_carga"


@pytest.mark.parametrize("ambiente", ["producao", "produção", "PRODUCAO", " production ", "prod", ""])
def test_recusa_ambiente_de_producao(ambiente):
    with pytest.raises(DestinoProibido, match="produção"):
        conferir_destino(BANCO_OK, ambiente)


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://u:s@localhost:5432/afinidade",
        "postgresql://u:s@localhost:5432/matchmaking",
        "postgresql://u:s@localhost:5432/carga_afinidade",  # "carga" no começo não basta
        "postgresql://u:s@localhost:5432/afinidade_carga_backup",
        "postgresql://u:s@localhost:5432/",
        "postgresql://u:s@localhost:5432",
    ],
)
def test_recusa_banco_que_nao_termina_em_carga(dsn):
    with pytest.raises(DestinoProibido, match="_carga"):
        conferir_destino(dsn, "dev")


def test_aceita_banco_de_carga_fora_de_producao():
    assert conferir_destino(BANCO_OK, "dev") == "afinidade_carga"
    assert conferir_destino("postgresql://u:s@db.exemplo:6543/x_carga?sslmode=require", "homologacao") == "x_carga"


def test_ids_estaveis_e_distintos():
    assert id_da_conta(7) == id_da_conta(7)
    assert len({id_da_conta(i) for i in range(1000)}) == 1000


def test_pares_sao_simetricos():
    assert [par_de(i) for i in range(6)] == [1, 0, 3, 2, 5, 4]
    for i in range(100):
        assert par_de(par_de(i)) == i


def test_gerar_contas_coerente_com_as_regras_do_banco():
    generos, tags = [1, 2, 3], list(range(1, 15))
    contas = gerar_contas(11, generos, tags)
    assert len(contas) == 11
    assert contas[-1]["par"] == -1  # total ímpar: a última fica sem par
    assert all(0 <= c["par"] < 11 for c in contas[:-1])
    for c in contas:
        assert c["handle"].startswith("carga_") and 3 <= len(c["handle"]) <= 30
        assert c["genero_id"] in generos and c["busca_por"] == generos
        niveis = [set(c["tags_quero"]), set(c["tags_curioso"]), set(c["tags_limite"])]
        # a restrição tags_niveis_disjuntos do banco
        assert not (niveis[0] & niveis[1] or niveis[0] & niveis[2] or niveis[1] & niveis[2])
        assert len(c["geohash"]) == 5
        assert -24 < c["lat"] < -23 and -47 < c["lon"] < -46  # Grande São Paulo


def test_gerar_contas_deterministico_e_valida_minimo():
    assert gerar_contas(5, [1], [1, 2, 3, 4, 5, 6]) == gerar_contas(5, [1], [1, 2, 3, 4, 5, 6])
    assert gerar_contas(5, [1], list(range(10)), semente=1) != gerar_contas(5, [1], list(range(10)), semente=2)
    with pytest.raises(ValueError):
        gerar_contas(1, [1], [1])
