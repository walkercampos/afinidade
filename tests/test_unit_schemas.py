from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas import Localizacao, Registro, TagsInteresses

BASE = {"senha": "senha-forte-123", "confirmo_maior_de_idade": True, "consinto_dados_sensiveis": True}


def _nascido_ha(anos: int, dias_a_mais: int = 0) -> date:
    hoje = date.today()
    try:
        d = hoje.replace(year=hoje.year - anos)
    except ValueError:  # 29/02
        d = hoje.replace(year=hoje.year - anos, day=28)
    return d - timedelta(days=dias_a_mais)


def test_maioridade_no_limite_exato():
    Registro(**BASE, data_nascimento=_nascido_ha(18))  # faz 18 hoje: pode
    with pytest.raises(ValidationError):
        Registro(**BASE, data_nascimento=_nascido_ha(18) + timedelta(days=1))  # faz 18 amanhã


@pytest.mark.parametrize("campo", ["confirmo_maior_de_idade", "consinto_dados_sensiveis"])
def test_confirmacoes_obrigatorias(campo):
    with pytest.raises(ValidationError):
        Registro(**{**BASE, campo: False}, data_nascimento=_nascido_ha(30))


@pytest.mark.parametrize("handle", ["ab", "a" * 31, "com espaço", "ação", "x;drop"])
def test_handles_invalidos(handle):
    with pytest.raises(ValidationError):
        Registro(**BASE, handle=handle, data_nascimento=_nascido_ha(30))


def test_handle_normalizado_e_opcional():
    assert Registro(**BASE, handle="  Fulano_1 ", data_nascimento=_nascido_ha(30)).handle == "fulano_1"
    assert Registro(**BASE, data_nascimento=_nascido_ha(30)).handle is None


def test_tags_sem_duplicatas_e_niveis_disjuntos():
    t = TagsInteresses(quero=["Bondage", "bondage", "latex"])
    assert t.quero == ["bondage", "latex"]
    with pytest.raises(ValidationError):
        TagsInteresses(quero=["latex"], curioso=["latex"])


@pytest.mark.parametrize(
    "dados", [{"lat": 91, "lon": 0}, {"lat": 0, "lon": 181}, {"lat": 0, "lon": 0, "distancia_max_km": 1}]
)
def test_localizacao_fora_dos_limites(dados):
    with pytest.raises(ValidationError):
        Localizacao(**dados)
