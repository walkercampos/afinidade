"""Um teste por erro já encontrado. Nome do teste = o erro que ele impede de voltar."""

import pytest

from app import descoberta
from app.matcher import PerfilMatch, _porcentagem, calcular_match
from app.ratelimit import Limitador


def test_arredondamento_meio_para_cima_igual_ao_postgres():
    # round() do Python daria 12 (meio para o par); o Postgres dá 13. Os dois lados usam _porcentagem.
    assert _porcentagem(1, 8) == 13
    assert _porcentagem(10, 11) == 91


def test_operador_contem_explicito_com_intarray():
    # Com a extensão intarray, `smallint[] @> smallint[]` fica ambíguo e a consulta quebra.
    eu = {
        "conta_id": None,
        "tags_quero": [],
        "tags_curioso": [],
        "tags_limite": [],
        "lat_aprox": None,
        "lon_aprox": None,
        "distancia_max_km": None,
        "busca_por": [1],
        "genero_id": 1,
    }
    sql, _ = descoberta._consulta(eu)
    assert "busca_por OPERATOR(pg_catalog.@>)" in sql


def test_rotacao_do_sal_nao_zera_limites_longos():
    agora = [0.0]
    lim = Limitador(relogio=lambda: agora[0])
    assert lim.permitir("dia", "conta", 1, janela_s=86_400, anonimizar=False)
    agora[0] += 7200
    assert not lim.permitir("dia", "conta", 1, janela_s=86_400, anonimizar=False)


def test_mesma_tag_em_dois_niveis_nao_bloqueia_a_si_mesmo():
    # Antes da validação, "quero" + "limite" na mesma tag gerava conflito com qualquer um.
    from pydantic import ValidationError

    from app.schemas import TagsInteresses

    with pytest.raises(ValidationError):
        TagsInteresses(quero=["x"], limite_absoluto=["x"])


def test_perfil_sem_interesses_nao_divide_por_zero():
    a = PerfilMatch.criar(1, "x", {"x"})
    b = PerfilMatch.criar(2, "x", {"x"}, quero={"t"})
    assert calcular_match(a, b).score_porcentagem == 0


def test_apelido_e_tag_com_maiusculas_sao_normalizados_antes_de_validar():
    # O pattern era checado antes do lower(): "Fulano_1" dava 422 no cadastro/login.
    from app.schemas import Cadastro, TagsInteresses

    c = Cadastro(
        email="a@b.co",
        handle=" Fulano_1 ",
        data_nascimento="1990-01-01",
        confirmo_maior_de_idade=True,
        consinto_dados_sensiveis=True,
    )
    assert c.handle == "fulano_1"
    assert TagsInteresses(quero=["Bondage"]).quero == ["bondage"]


def test_tentativas_de_codigo_sao_gravadas_mesmo_recusando():
    # O erro era lançado dentro da transação: o rollback desfazia o contador de tentativas e o
    # código de 6 dígitos ficava com tentativas ilimitadas (força bruta). Coberto de ponta a ponta
    # em tests/test_email.py::test_codigo_errado_tem_limite_de_tentativas; aqui, a regra no código:
    import inspect

    from app import verificacao

    fonte = inspect.getsource(verificacao.confirmar_codigo)
    assert fonte.rstrip().endswith("raise VerificacaoInvalida(erro)")


def test_websocket_sem_compressao_na_imagem():
    """Teste de carga: a compressão por mensagem do WebSocket guardava um buffer zlib por conexão
    (77 KB -> 43 KB por canal sem ela). Os avisos têm ~60 bytes: comprimir não ganha nada."""
    from pathlib import Path

    cmd = next(
        linha
        for linha in (Path(__file__).parent.parent / "Dockerfile").read_text().splitlines()
        if linha.startswith("CMD ")
    )
    assert "--ws-per-message-deflate false" in cmd
