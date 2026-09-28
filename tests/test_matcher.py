from app.matcher import (
    MOTIVO_GENERO, MOTIVO_LIMITES, PerfilMatch, calcular_match, score_mutuo,
)

ALFA = {
    "id": "1", "nome": "User_Alfa", "genero": "Homem Cis", "busca_por": ["Mulher Cis", "Mulher Trans"],
    "tags_interesses": {
        "quero": ["Bondage", "Leather", "Dirty Talk"],
        "curioso": ["Impact Play", "Voyeurism"],
        "limite_absoluto": ["Ageplay", "Urophilia"],
    },
}
BETA = {
    "id": "2", "nome": "User_Beta", "genero": "Mulher Cis", "busca_por": ["Homem Cis"],
    "tags_interesses": {
        "quero": ["Bondage", "Dirty Talk", "Impact Play"],
        "curioso": ["Leather"],
        "limite_absoluto": ["Urophilia"],
    },
}


def test_exemplo_do_script_original():
    r = calcular_match(PerfilMatch.de_dict(ALFA), PerfilMatch.de_dict(BETA)).to_dict()
    # 2 quero mútuos (6) + Leather quero/curioso (2) + Impact Play quero/curioso (2) = 10 de 11
    assert r == {
        "match_valido": True,
        "score_porcentagem": 91,
        "tags_em_comum": ["Bondage", "Dirty Talk", "Impact Play", "Leather"],
        "motivo": "Compatibilidade calculada com sucesso",
    }


def test_score_e_assimetrico_e_mutuo_e_a_media():
    a, b = PerfilMatch.de_dict(ALFA), PerfilMatch.de_dict(BETA)
    # B: max = 3*3 + 1*1 = 10; score = 6 + 2 + 2 = 10 -> 100
    assert calcular_match(b, a).score_porcentagem == 100
    assert score_mutuo(a, b) == score_mutuo(b, a) == round((91 + 100) / 2)


def test_filtro_de_genero_exige_reciprocidade():
    a = PerfilMatch.criar(1, "h", {"m"})
    b = PerfilMatch.criar(2, "m", {"nb"})
    r = calcular_match(a, b)
    assert (r.match_valido, r.motivo) == (False, MOTIVO_GENERO)
    assert score_mutuo(a, b) == 0


def test_limite_absoluto_bloqueia_nas_duas_direcoes():
    a = PerfilMatch.criar(1, "x", {"x"}, quero={"t1"})
    b = PerfilMatch.criar(2, "x", {"x"}, limite_absoluto={"t1"})
    assert calcular_match(a, b).motivo == MOTIVO_LIMITES
    assert calcular_match(b, a).motivo == MOTIVO_LIMITES


def test_curiosidade_sobre_limite_do_outro_nao_bloqueia_nem_pontua():
    a = PerfilMatch.criar(1, "x", {"x"}, curioso={"t1"}, quero={"t2"})
    b = PerfilMatch.criar(2, "x", {"x"}, limite_absoluto={"t1"}, quero={"t2"})
    r = calcular_match(a, b)
    assert r.match_valido and r.tags_em_comum == ("t2",)
    assert r.score_porcentagem == 75  # 3 de (3 + 1)


def test_sem_interesses_da_zero_sem_dividir_por_zero():
    a = PerfilMatch.criar(1, "x", {"x"})
    b = PerfilMatch.criar(2, "x", {"x"}, quero={"t"})
    assert calcular_match(a, b).score_porcentagem == 0


def test_score_limitado_a_100():
    # A curioso em t1 (max 1), B quer t1 -> ganha 2
    a = PerfilMatch.criar(1, "x", {"x"}, curioso={"t1"})
    b = PerfilMatch.criar(2, "x", {"x"}, quero={"t1"})
    assert calcular_match(a, b).score_porcentagem == 100
