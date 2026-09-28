from app import geo

SP = (-23.5505, -46.6333)
SP_PERTO = (-23.5610, -46.6560)       # ~3 km
CAMPINAS = (-22.9056, -47.0608)       # ~85 km
RIO = (-22.9068, -43.1729)            # ~360 km


def test_geohash_e_faixas():
    assert geo.codificar(57.64911, 10.40744, 11) == "u4pruydqqvj"   # exemplo canônico
    assert geo.faixa_km(0.4) == 5 and geo.faixa_km(5.1) == 10 and geo.faixa_km(None) is None
    assert round(geo.distancia_km(*SP, *RIO)) in range(355, 365)


def test_coordenada_exata_nunca_e_gravada(pessoa, db):
    p = pessoa(local=SP)
    linha = db.fetchrow("SELECT geohash, lat_aprox, lon_aprox FROM perfis WHERE conta_id = $1::uuid", p.id)
    assert linha["geohash"] == geo.codificar(*SP)
    assert (linha["lat_aprox"], linha["lon_aprox"]) == geo.centro(linha["geohash"]) != SP
    assert p.get("/api/perfil").json()["localizacao"] == {"regiao": linha["geohash"], "distancia_max_km": None}


def _ids(p):
    return {c["perfil"]["id"] for c in p.get("/api/descobrir", params={"limite": 100}).json()}


def test_distancia_maxima_vale_para_os_dois_lados(pessoa):
    eu = pessoa("homem-trans", ["mulher-trans"], quero=["latex"], local=SP, dist=50)
    perto = pessoa("mulher-trans", ["homem-trans"], quero=["latex"], local=SP_PERTO)
    longe = pessoa("mulher-trans", ["homem-trans"], quero=["latex"], local=RIO)
    sem_local = pessoa("mulher-trans", ["homem-trans"], quero=["latex"])
    # Campinas está a ~85 km: fora dos MEUS 50 km
    campinas = pessoa("mulher-trans", ["homem-trans"], quero=["latex"], local=CAMPINAS)
    vistos = _ids(eu)
    assert perto.id in vistos
    assert not vistos & {longe.id, sem_local.id, campinas.id}

    # Quem não definiu limite vê todo mundo, mas respeita o limite do outro lado
    livre = pessoa("homem-trans", ["mulher-trans"], quero=["latex"], local=RIO)
    restrita = pessoa("mulher-trans", ["homem-trans"], quero=["latex"], local=SP, dist=10)
    assert restrita.id not in _ids(livre)
    assert livre.post(f"/api/perfis/{restrita.id}/curtir").status_code == 403

    card = next(c for c in eu.get("/api/descobrir").json() if c["perfil"]["id"] == perto.id)
    assert card["compatibilidade"]["distancia_km"] == 5


def test_apagar_localizacao(pessoa, db):
    p = pessoa(local=SP, dist=20)
    assert p.delete("/api/perfil/localizacao").status_code == 204
    assert db.fetchval("SELECT geohash FROM perfis WHERE conta_id = $1::uuid", p.id) is None
