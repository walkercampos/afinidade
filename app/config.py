import os
from dataclasses import dataclass
from functools import cache


@dataclass(frozen=True)
class Config:
    database_url: str
    jwt_secret: str
    jwt_expira_min: int
    chave_mensagens: str
    producao: bool
    limite_auth_por_min: int
    limite_api_por_min: int
    limite_mensagens_por_min: int
    limite_denuncias_por_dia: int
    # Perfis sem atividade há mais tempo que isso saem da descoberta (relevância + escala).
    inatividade_max_dias: int
    mensagens_retencao_dias: int
    # Denunciantes distintos (com conta de pelo menos 24 h) para ocultar um perfil até revisão.
    denuncias_para_revisao: int


def _segredo(nome: str) -> str:
    valor = os.environ.get(nome, "")
    if len(valor) < 32:
        raise RuntimeError(f"Defina {nome} com pelo menos 32 caracteres aleatórios (veja .env.example).")
    return valor


@cache
def config() -> Config:
    """Lida uma única vez, na primeira chamada (depois que o ambiente já foi configurado)."""
    e = os.environ.get
    return Config(
        database_url=e("DATABASE_URL", "postgresql://matchmaking:matchmaking@localhost:5432/matchmaking"),
        jwt_secret=_segredo("JWT_SECRET"),
        jwt_expira_min=int(e("JWT_EXPIRA_MIN", "1440")),
        chave_mensagens=_segredo("CHAVE_MENSAGENS"),
        # Em produção: cookie Secure, HSTS e /docs desligado.
        producao=e("AMBIENTE", "producao") == "producao",
        limite_auth_por_min=int(e("LIMITE_AUTH_POR_MIN", "10")),
        limite_api_por_min=int(e("LIMITE_API_POR_MIN", "120")),
        limite_mensagens_por_min=int(e("LIMITE_MENSAGENS_POR_MIN", "30")),
        limite_denuncias_por_dia=int(e("LIMITE_DENUNCIAS_POR_DIA", "10")),
        inatividade_max_dias=int(e("INATIVIDADE_MAX_DIAS", "90")),
        mensagens_retencao_dias=int(e("MENSAGENS_RETENCAO_DIAS", "30")),
        denuncias_para_revisao=int(e("DENUNCIAS_PARA_REVISAO", "3")),
    )
