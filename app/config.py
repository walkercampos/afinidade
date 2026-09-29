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
    # Denunciantes distintos (com conta de pelo menos 24 h) para ocultar um perfil até revisão.
    denuncias_para_revisao: int
    # Passkeys: o domínio (sem esquema nem porta) e as origens exatas de onde o app é servido.
    webauthn_rp_id: str
    webauthn_origens: tuple[str, ...]
    # E-mail: chave do HMAC (busca), chave da cifragem (para poder enviar avisos) e o envio.
    email_pepper: str
    chave_email: str
    email: "ConfigEmail"


@dataclass(frozen=True)
class ConfigEmail:
    provedor: str  # "arquivo" (dev), "memoria" (testes), "resend" ou "smtp"
    remetente: str
    app_url: str  # base dos links mágicos, ex.: https://afinidade.onrender.com
    pasta: str = "emails-dev"
    resend_api_key: str = ""
    smtp_host: str = ""
    smtp_porta: int = 587
    smtp_usuario: str = ""
    smtp_senha: str = ""


_PROVEDORES_PRODUCAO = {"resend", "smtp"}


def _email(producao: bool, origens: tuple[str, ...]) -> ConfigEmail:
    e = os.environ.get
    cfg = ConfigEmail(
        provedor=e("EMAIL_PROVEDOR", "arquivo"),
        remetente=e("EMAIL_REMETENTE", "Afinidade <nao-responda@localhost>"),
        app_url=e("APP_URL", origens[0]).rstrip("/"),
        pasta=e("EMAIL_PASTA", "emails-dev"),
        resend_api_key=e("RESEND_API_KEY", ""),
        smtp_host=e("SMTP_HOST", ""),
        smtp_porta=int(e("SMTP_PORTA", "587")),
        smtp_usuario=e("SMTP_USUARIO", ""),
        smtp_senha=e("SMTP_SENHA", ""),
    )
    if cfg.provedor not in {"arquivo", "memoria", *_PROVEDORES_PRODUCAO}:
        raise RuntimeError(f"EMAIL_PROVEDOR desconhecido: {cfg.provedor}")
    if producao and cfg.provedor not in _PROVEDORES_PRODUCAO:
        raise RuntimeError("Em produção use EMAIL_PROVEDOR=resend ou smtp (veja docs/autenticacao.md).")
    if cfg.provedor == "resend" and not cfg.resend_api_key:
        raise RuntimeError("Defina RESEND_API_KEY para EMAIL_PROVEDOR=resend.")
    if cfg.provedor == "smtp" and not (cfg.smtp_host and cfg.smtp_usuario and cfg.smtp_senha):
        raise RuntimeError("Defina SMTP_HOST, SMTP_USUARIO e SMTP_SENHA para EMAIL_PROVEDOR=smtp.")
    return cfg


def _segredo(nome: str) -> str:
    valor = os.environ.get(nome, "")
    if len(valor) < 32:
        raise RuntimeError(f"Defina {nome} com pelo menos 32 caracteres aleatórios (veja .env.example).")
    return valor


def _webauthn(producao: bool) -> tuple[str, tuple[str, ...]]:
    rp_id = os.environ.get("WEBAUTHN_RP_ID")
    origens = os.environ.get("WEBAUTHN_ORIGENS")
    if producao and not (rp_id and origens):
        # Falha na subida em vez de subir com passkeys quebradas (ou aceitando qualquer origem).
        raise RuntimeError(
            "Defina WEBAUTHN_RP_ID (ex.: afinidade.onrender.com) e WEBAUTHN_ORIGENS "
            "(ex.: https://afinidade.onrender.com) — veja docs/autenticacao.md."
        )
    rp_id = rp_id or "localhost"
    lista = tuple(o.strip().rstrip("/") for o in (origens or "http://localhost:8000").split(",") if o.strip())
    return rp_id, lista


@cache
def config() -> Config:
    """Lida uma única vez, na primeira chamada (depois que o ambiente já foi configurado)."""
    e = os.environ.get
    producao = e("AMBIENTE", "producao") == "producao"
    rp_id, origens = _webauthn(producao)
    return Config(
        database_url=e("DATABASE_URL", "postgresql://matchmaking:matchmaking@localhost:5432/matchmaking"),
        jwt_secret=_segredo("JWT_SECRET"),
        jwt_expira_min=int(e("JWT_EXPIRA_MIN", "1440")),
        chave_mensagens=_segredo("CHAVE_MENSAGENS"),
        # Em produção: cookie Secure, HSTS e /docs desligado.
        producao=producao,
        limite_auth_por_min=int(e("LIMITE_AUTH_POR_MIN", "10")),
        limite_api_por_min=int(e("LIMITE_API_POR_MIN", "120")),
        limite_mensagens_por_min=int(e("LIMITE_MENSAGENS_POR_MIN", "30")),
        limite_denuncias_por_dia=int(e("LIMITE_DENUNCIAS_POR_DIA", "10")),
        inatividade_max_dias=int(e("INATIVIDADE_MAX_DIAS", "90")),
        denuncias_para_revisao=int(e("DENUNCIAS_PARA_REVISAO", "3")),
        webauthn_rp_id=rp_id,
        webauthn_origens=origens,
        email_pepper=_segredo("EMAIL_PEPPER"),
        chave_email=_segredo("CHAVE_EMAIL"),
        email=_email(producao, origens),
    )
