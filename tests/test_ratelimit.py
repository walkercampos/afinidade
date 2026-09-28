from app.ratelimit import JANELA_S, Limitador


def test_limita_por_identificador_e_reinicia_na_proxima_janela():
    agora = [1000.0]
    lim = Limitador(relogio=lambda: agora[0])
    assert all(lim.permitir("auth", "1.2.3.4", 3) for _ in range(3))
    assert not lim.permitir("auth", "1.2.3.4", 3)
    assert lim.permitir("auth", "5.6.7.8", 3)  # outro IP não é afetado
    assert lim.permitir("login", "1.2.3.4", 3)  # outro escopo também não
    agora[0] += JANELA_S
    assert lim.permitir("auth", "1.2.3.4", 3)


def test_nao_guarda_o_identificador_em_claro():
    lim = Limitador()
    lim.permitir("auth", "203.0.113.9", 5)
    assert not any("203.0.113.9" in k[1] for k in lim._contagens)


def test_janelas_de_tamanhos_diferentes_sao_independentes():
    agora = [0.0]
    lim = Limitador(relogio=lambda: agora[0])
    assert lim.permitir("dia", "x", 1, janela_s=86_400, anonimizar=False)
    assert not lim.permitir("dia", "x", 1, janela_s=86_400, anonimizar=False)
    agora[0] += 7200  # depois da rotação do sal, a janela de um dia continua fechada
    assert not lim.permitir("dia", "x", 1, janela_s=86_400, anonimizar=False)
    assert lim.permitir("min", "x", 1)
