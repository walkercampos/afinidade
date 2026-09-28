"""Envio de e-mails. Um "carteiro" por provedor, escolhido por EMAIL_PROVEDOR.

- arquivo : desenvolvimento. Cada e-mail vira um .txt em EMAIL_PASTA (abra para ver o código).
- memoria : testes automáticos. Guarda os e-mails numa lista.
- resend  : produção. API HTTPS do Resend (plano gratuito); só a biblioteca padrão, sem SDK.
- smtp    : produção. Qualquer servidor SMTP com STARTTLS (Brevo, Mailgun, SES, provedor próprio).

Privacidade: o provedor de e-mail vê o destinatário e o conteúdo (o código). Por isso o texto é
neutro e não diz do que se trata o app.
"""

import asyncio
import json
import logging
import smtplib
import ssl
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from .config import ConfigEmail

log = logging.getLogger("matchmaking.email")


class FalhaNoEnvio(RuntimeError):
    pass


@dataclass
class Mensagem:
    para: str
    assunto: str
    texto: str


class CarteiroArquivo:
    def __init__(self, pasta: str):
        self.pasta = Path(pasta)

    async def enviar(self, m: Mensagem) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        nome = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".txt"
        (self.pasta / nome).write_text(f"Para: {m.para}\nAssunto: {m.assunto}\n\n{m.texto}\n", encoding="utf-8")
        log.info("E-mail de desenvolvimento salvo em %s", self.pasta / nome)


@dataclass
class CarteiroMemoria:
    caixa: list[Mensagem] = field(default_factory=list)

    async def enviar(self, m: Mensagem) -> None:
        self.caixa.append(m)


class CarteiroResend:
    URL = "https://api.resend.com/emails"

    def __init__(self, api_key: str, remetente: str):
        self.api_key, self.remetente = api_key, remetente

    def _enviar(self, m: Mensagem) -> None:
        corpo = json.dumps({"from": self.remetente, "to": [m.para], "subject": m.assunto, "text": m.texto}).encode()
        pedido = urllib.request.Request(  # noqa: S310 (URL fixa, https)
            self.URL,
            data=corpo,
            method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(pedido, timeout=10) as r:  # noqa: S310
                if r.status >= 300:
                    raise FalhaNoEnvio(f"Resend respondeu {r.status}")
        except OSError as e:
            raise FalhaNoEnvio("Falha ao falar com o Resend") from e

    async def enviar(self, m: Mensagem) -> None:
        await asyncio.to_thread(self._enviar, m)


class CarteiroSMTP:
    def __init__(self, cfg: ConfigEmail):
        self.cfg = cfg

    def _enviar(self, m: Mensagem) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.cfg.remetente, m.para, m.assunto
        msg.set_content(m.texto)
        try:
            with smtplib.SMTP(self.cfg.smtp_host, self.cfg.smtp_porta, timeout=10) as s:
                s.starttls(context=ssl.create_default_context())  # nunca envia sem TLS
                s.login(self.cfg.smtp_usuario, self.cfg.smtp_senha)
                s.send_message(msg)
        except (OSError, smtplib.SMTPException) as e:
            raise FalhaNoEnvio("Falha no envio SMTP") from e

    async def enviar(self, m: Mensagem) -> None:
        await asyncio.to_thread(self._enviar, m)


def criar_carteiro(cfg: ConfigEmail):
    return {
        "arquivo": lambda: CarteiroArquivo(cfg.pasta),
        "memoria": CarteiroMemoria,
        "resend": lambda: CarteiroResend(cfg.resend_api_key, cfg.remetente),
        "smtp": lambda: CarteiroSMTP(cfg),
    }[cfg.provedor]()


def mensagem_de_acesso(para: str, codigo: str, link: str) -> Mensagem:
    """Texto neutro de propósito: o assunto aparece na tela de bloqueio do celular."""
    return Mensagem(
        para=para,
        assunto="Seu código de acesso",
        texto=(
            f"Seu código de acesso é: {codigo}\n\n"
            f"Ou abra este link neste aparelho:\n{link}\n\n"
            "O código e o link valem por 15 minutos e só podem ser usados uma vez.\n"
            "Se não foi você, ignore este e-mail: nada acontece sem o código."
        ),
    )
