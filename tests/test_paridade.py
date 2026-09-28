"""O ranking roda em SQL (descoberta.py) e os detalhes em Python (matcher.py).
Este teste garante que os dois calculam EXATAMENTE a mesma coisa."""

import random

from app.matcher import PerfilMatch, calcular_match, score_mutuo, similaridade

TAGS = [
    "bondage",
    "leather",
    "latex",
    "dirty-talk",
    "impact-play",
    "wax-play",
    "roleplay",
    "voyeurism",
    "exibicionismo",
    "podolatria",
]


def _perfil_aleatorio(rng):
    tags = rng.sample(TAGS, rng.randint(0, len(TAGS)))
    cortes = sorted(rng.randint(0, len(tags)) for _ in range(2))
    return tags[: cortes[0]], tags[cortes[0] : cortes[1]], tags[cortes[1] :]


def test_sql_e_python_dao_os_mesmos_scores(pessoa):
    rng = random.Random(42)  # noqa: S311 (reprodutibilidade, não criptografia)
    eu_tags = (["bondage", "leather", "dirty-talk"], ["impact-play", "voyeurism"], ["podolatria"])
    eu = pessoa("genero-fluido", ["agenero"], quero=eu_tags[0], curioso=eu_tags[1], limite=eu_tags[2])
    outros = {}
    for _ in range(60):
        q, c, lim = _perfil_aleatorio(rng)
        p = pessoa("agenero", ["genero-fluido"], quero=q, curioso=c, limite=lim)
        outros[p.id] = PerfilMatch.criar(p.id, 1, {1}, q, c, lim)

    eu_match = PerfilMatch.criar(eu.id, 1, {1}, *eu_tags)
    esperados = {i: m for i, m in outros.items() if calcular_match(eu_match, m).match_valido}

    vistos = {}
    cursor = None
    while True:
        r = eu.get("/api/descobrir", params={"limite": 7, **({"cursor": cursor} if cursor else {})})
        assert r.status_code == 200, r.text
        for c in r.json():
            vistos[c["perfil"]["id"]] = c["compatibilidade"]
        cursor = r.headers.get("X-Proximo-Cursor")
        if not cursor:
            break

    # Camadas 1 e 2 no SQL == no Python (nem a mais, nem a menos)
    assert set(vistos) == set(esperados)
    for i, compat in vistos.items():
        m = esperados[i]
        assert compat["score_porcentagem"] == calcular_match(eu_match, m).score_porcentagem
        assert compat["score_mutuo"] == score_mutuo(eu_match, m)
        assert compat["similaridade"] == similaridade(eu_match, m)


def test_paginacao_segue_a_ordem_sem_repetir(pessoa):
    eu = pessoa("travesti", ["nao-binarie"], quero=["bondage", "latex"], curioso=["roleplay"])
    for tags in (["bondage"], ["bondage", "latex"], ["latex"], [], ["roleplay"], ["bondage", "latex", "roleplay"]):
        pessoa("nao-binarie", ["travesti"], quero=tags)

    for ordem, chave in (("compatibilidade", "score_mutuo"), ("afinidade", "similaridade")):
        ids, notas, cursor = [], [], None
        while True:
            r = eu.get("/api/descobrir", params={"ordem": ordem, "limite": 2, **({"cursor": cursor} if cursor else {})})
            ids += [c["perfil"]["id"] for c in r.json()]
            notas += [c["compatibilidade"][chave] for c in r.json()]
            if not (cursor := r.headers.get("X-Proximo-Cursor")):
                break
        assert len(ids) == len(set(ids)) == 6
        assert notas == sorted(notas, reverse=True)

    assert eu.get("/api/descobrir", params={"cursor": "lixo"}).status_code == 400


def test_afins_ordena_por_gostos_parecidos(pessoa):
    eu = pessoa("agenero", ["travesti"], quero=["wax-play", "latex"], curioso=["roleplay"])
    igual = pessoa("travesti", ["agenero"], quero=["wax-play", "latex"], curioso=["roleplay"])
    parecido = pessoa("travesti", ["agenero"], quero=["wax-play"], curioso=["latex", "voyeurism"])
    diferente = pessoa("travesti", ["agenero"], quero=["podolatria"])
    feed = [c for c in eu.get("/api/afins").json() if c["perfil"]["id"] in {igual.id, parecido.id, diferente.id}]
    assert [c["perfil"]["id"] for c in feed] == [igual.id, parecido.id, diferente.id]
    assert feed[0]["compatibilidade"]["similaridade"] == 100
    assert feed[0]["compatibilidade"]["tags_mesmo_nivel"] == ["latex", "roleplay", "wax-play"]
    assert feed[2]["compatibilidade"]["similaridade"] == 0
