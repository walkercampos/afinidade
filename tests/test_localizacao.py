from app import geo

SP = (-23.5505, -46.6333)
SP_PERTO = (-23.5610, -46.6560)  # ~3 km
CAMPINAS = (-22.9056, -47.0608)  # ~85 km
RIO = (-22.9068, -43.1729)  # ~360 km


def test_geohash_e_faixas():
    assert geo.codificar(57.64911, 10.40744, 11) == "u4pruydqqvj"  # exemplo canônico
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


def test_barra_de_distancia_troca_so_o_raio(pessoa, db):
    sem_local = pessoa()
    r = sem_local.put("/api/perfil/distancia", json={"distancia_max_km": 25})
    assert r.status_code == 409  # sem localização o filtro esconderia todo mundo

    eu = pessoa("homem-trans", ["mulher-trans"], quero=["leather"], local=SP)
    campinas = pessoa("mulher-trans", ["homem-trans"], quero=["leather"], local=CAMPINAS)
    antes = db.fetchval("SELECT geohash FROM perfis WHERE conta_id = $1::uuid", eu.id)

    assert eu.put("/api/perfil/distancia", json={"distancia_max_km": 50}).json()["distancia_max_km"] == 50
    assert campinas.id not in _ids(eu)  # ~85 km
    assert eu.put("/api/perfil/distancia", json={"distancia_max_km": 100}).status_code == 200
    assert campinas.id in _ids(eu)
    assert eu.put("/api/perfil/distancia", json={"distancia_max_km": None}).json()["distancia_max_km"] is None

    # A região não muda: a barra nunca envia coordenadas
    assert db.fetchval("SELECT geohash FROM perfis WHERE conta_id = $1::uuid", eu.id) == antes
    for invalido in (0, 4, 501, "longe"):
        assert eu.put("/api/perfil/distancia", json={"distancia_max_km": invalido}).status_code == 422


# --- Ataque de trilateração -------------------------------------------------------------
# O atacante muda a própria posição várias vezes e anota, para cada posição, se a vítima
# aparece (com o filtro de distância no mínimo) e em que faixa de distância. Na versão
# clássica do ataque, três medições bastam para achar alguém a poucos metros.
#
# Aqui a garantia é mais forte do que "fica difícil": duas vítimas em pontos DIFERENTES do
# MESMO quadrado (~5 km) geram respostas idênticas para toda posição do atacante. Logo, nenhuma
# quantidade de medições revela mais do que o quadrado.

_METADE_CELULA = 180 / 2**12 / 2  # 5 caracteres = 12 bits de latitude e 13 de longitude: ~0,022°


def _cantos_opostos_da_mesma_celula(lat, lon):
    clat, clon = geo.centro(geo.codificar(lat, lon))
    margem = _METADE_CELULA * 0.9
    a, b = (clat - margem, clon - margem), (clat + margem, clon + margem)
    assert geo.codificar(*a) == geo.codificar(*b)
    assert geo.distancia_km(*a, *b) > 5  # pontos bem distantes entre si
    return a, b


def _sondagens(centro):
    """16 posições do atacante: 4 direções x 4 raios (1, 3, 6 e 12 km)."""
    lat, lon = centro
    grau_km = 1 / 111.0
    return [
        (lat + dy * r * grau_km, lon + dx * r * grau_km)
        for r in (1, 3, 6, 12)
        for dy, dx in ((1, 0), (0, 1), (-1, 0), (0, -1))
    ]


def _observar(atacante, alvo_id):
    cards = atacante.get("/api/descobrir", params={"limite": 100}).json()
    card = next((c for c in cards if c["perfil"]["id"] == alvo_id), None)
    return (card is not None, card and card["compatibilidade"]["distancia_km"])


def test_trilateracao_nao_revela_mais_que_o_quadrado(pessoa):
    canto_a, canto_b = _cantos_opostos_da_mesma_celula(*SP)
    vitima_a = pessoa("agenero", ["travesti"], quero=["wax-play"], local=canto_a)
    vitima_b = pessoa("agenero", ["travesti"], quero=["wax-play"], local=canto_b)
    atacante = pessoa("travesti", ["agenero"], quero=["wax-play"], local=SP)

    observacoes = []
    for lat, lon in _sondagens(SP):
        r = atacante.put("/api/perfil/localizacao", json={"lat": lat, "lon": lon, "distancia_max_km": 5})
        assert r.status_code == 200, r.text
        vista_a, vista_b = _observar(atacante, vitima_a.id), _observar(atacante, vitima_b.id)
        assert vista_a == vista_b, f"posição do atacante {lat:.4f},{lon:.4f} distingue as vítimas"
        observacoes.append(vista_a)

    # O teste só vale se as sondagens de fato mudam o que o atacante vê
    assert len(set(observacoes)) > 1


def test_limite_de_trocas_de_localizacao(pessoa):
    p = pessoa()
    for _ in range(20):
        assert p.put("/api/perfil/localizacao", json={"lat": SP[0], "lon": SP[1]}).status_code == 200
    r = p.put("/api/perfil/localizacao", json={"lat": SP[0], "lon": SP[1]})
    assert r.status_code == 429
    # Apagar a localização continua liberado (é uma ação de privacidade)
    assert p.delete("/api/perfil/localizacao").status_code == 204
