"""Massa de teste (carga/massa.py): nunca toca produção nem banco remoto e gera dados coerentes."""

import re

import pytest

from carga.massa import DestinoProibido, conferir_destino, gerar_curtidas, gerar_pessoas, id_da_pessoa, main

GENEROS = [(1, "homem-cis"), (2, "mulher-cis"), (3, "nao-binarie"), (4, "casal")]
TAGS = list(range(1, 15))


@pytest.mark.parametrize("ambiente", ["producao", "produção", "PRODUCAO", " production ", "prod", ""])
def test_recusa_ambiente_de_producao(ambiente):
    with pytest.raises(DestinoProibido, match="produção"):
        conferir_destino("postgresql://u:s@localhost:5432/matchmaking", ambiente)


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://u:s@ep-algo.neon.tech/neondb",
        "postgresql://u:s@10.0.0.5:5432/matchmaking",
        "postgresql://u:s@/matchmaking",
    ],
)
def test_recusa_banco_que_nao_e_local(dsn):
    with pytest.raises(DestinoProibido, match="local"):
        conferir_destino(dsn, "dev")


def test_aceita_banco_local_e_exige_nome():
    assert conferir_destino("postgresql://u:s@localhost:5432/matchmaking", "dev") == "matchmaking"
    assert conferir_destino("postgresql://u:s@db:5432/matchmaking", "dev") == "matchmaking"
    with pytest.raises(DestinoProibido, match="nome do banco"):
        conferir_destino("postgresql://u:s@localhost:5432/", "dev")


def test_pessoas_respeitam_as_regras_do_banco():
    pessoas = gerar_pessoas(300, GENEROS, TAGS)
    assert len({p["id"] for p in pessoas}) == 300
    assert len({p["handle"] for p in pessoas}) == 300
    for p in pessoas:
        assert re.fullmatch(r"[a-z0-9_]{3,30}", p["handle"]) and p["handle"].startswith("massa_")
        assert 1 <= len(p["nome"]) <= 40
        assert p["bio"] is None or len(p["bio"]) <= 500
        assert p["busca_por"] and set(p["busca_por"]) <= {g for g, _ in GENEROS}
        niveis = [set(p["tags_quero"]), set(p["tags_curioso"]), set(p["tags_limite"])]
        assert niveis[0] and not (niveis[0] & niveis[1] or niveis[0] & niveis[2] or niveis[1] & niveis[2])
        assert (p["geohash"] is None) == (p["lat"] is None) == (p["lon"] is None)
    # variedade de verdade: vários gêneros, nomes, cidades e gente sem localização
    assert len({p["genero_id"] for p in pessoas}) == len(GENEROS)
    assert len({p["nome"] for p in pessoas}) > 40
    assert any(p["geohash"] is None for p in pessoas) and len({p["geohash"][:3] for p in pessoas if p["geohash"]}) > 4
    assert all(" & " in p["nome"] for p in pessoas if p["genero_id"] == 4)


def test_pessoas_deterministicas_e_minimos():
    assert gerar_pessoas(20, GENEROS, TAGS)[5]["handle"] == gerar_pessoas(20, GENEROS, TAGS)[5]["handle"]
    assert id_da_pessoa(3) == id_da_pessoa(3) != id_da_pessoa(4)
    with pytest.raises(ValueError, match="2 pessoas"):
        gerar_pessoas(1, GENEROS, TAGS)
    with pytest.raises(ValueError, match="4 interesses"):
        gerar_pessoas(5, GENEROS, [1, 2, 3])


def test_curtidas_sem_auto_curtida_e_alvo_recebe_parte():
    pessoas = gerar_pessoas(200, GENEROS, TAGS)
    alvo = id_da_pessoa(999_999)
    curtidas = gerar_curtidas(pessoas, alvo=alvo)
    assert all(de != para for de, para in curtidas)
    assert len(set(curtidas)) == len(curtidas)
    recebidas = sum(1 for _, para in curtidas if para == alvo)
    assert 40 < recebidas < 120  # ~40% de 200
    assert not any(para == alvo for _, para in gerar_curtidas(pessoas))


def test_main_recusa_sem_tocar_no_banco(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:s@ep-algo.neon.tech/neondb")
    monkeypatch.setenv("AMBIENTE", "dev")
    assert main(["massa", "50"]) == 2
    assert "Recusado" in capsys.readouterr().err
