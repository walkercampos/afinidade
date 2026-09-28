import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url: str
    jwt_secret: str
    jwt_expira_min: int
    candidatos_prefetch: int
    producao: bool
    limite_auth_por_min: int
    limite_api_por_min: int


def carregar_config() -> Config:
    segredo = os.environ.get("JWT_SECRET", "")
    if len(segredo) < 32:
        raise RuntimeError("Defina JWT_SECRET com pelo menos 32 caracteres (veja .env.example).")
    return Config(
        database_url=os.environ.get("DATABASE_URL", "postgresql://matchmaking:matchmaking@localhost:5432/matchmaking"),
        jwt_secret=segredo,
        jwt_expira_min=int(os.environ.get("JWT_EXPIRA_MIN", "1440")),
        # Quantos candidatos o SQL entrega (já filtrados pelas camadas 1 e 2) para o
        # Python pontuar na camada 3 antes de ordenar e cortar.
        candidatos_prefetch=int(os.environ.get("CANDIDATOS_PREFETCH", "500")),
        # Em produção: cookie Secure, HSTS e /docs desligado.
        producao=os.environ.get("AMBIENTE", "producao") == "producao",
        limite_auth_por_min=int(os.environ.get("LIMITE_AUTH_POR_MIN", "10")),
        limite_api_por_min=int(os.environ.get("LIMITE_API_POR_MIN", "120")),
    )
