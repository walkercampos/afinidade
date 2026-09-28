import asyncio
import json
from pathlib import Path
from unittest import mock

import pytest

from app import email as em
from app.config import ConfigEmail, _email
from app.verificacao import hash_email, normalizar_email


def cfg(**kw):
    base = {"provedor": "arquivo", "remetente": "App <a@b.co>", "app_url": "https://x.app"}
    return ConfigEmail(**{**base, **kw})


def test_hash_do_email_depende_da_chave():
    a = hash_email("k" * 32, "ana@x.com")
    assert a == hash_email("k" * 32, "ana@x.com") and len(a) == 32
    assert a != hash_email("j" * 32, "ana@x.com")  # sem a chave, não dá para montar dicionário


@pytest.mark.parametrize("bruto,esperado", [(" A@B.CO ", "a@b.co"), ("x.y+z@dominio.com.br", "x.y+z@dominio.com.br")])
def test_normalizacao(bruto, esperado):
    assert normalizar_email(bruto) == esperado


def test_carteiro_arquivo(tmp_path: Path):
    c = em.CarteiroArquivo(str(tmp_path / "caixa"))
    asyncio.run(c.enviar(em.mensagem_de_acesso("a@b.co", "123456", "https://x/#/verificar/t")))
    [arquivo] = list((tmp_path / "caixa").iterdir())
    assert "123456" in arquivo.read_text() and "Para: a@b.co" in arquivo.read_text()


def test_carteiro_resend_monta_a_requisicao():
    c = em.CarteiroResend("chave-secreta", "App <a@b.co>")
    resposta = mock.MagicMock(status=200)
    resposta.__enter__.return_value = resposta
    with mock.patch("urllib.request.urlopen", return_value=resposta) as urlopen:
        asyncio.run(c.enviar(em.Mensagem("d@e.co", "Assunto", "Texto")))
    pedido = urlopen.call_args.args[0]
    assert pedido.full_url == "https://api.resend.com/emails"
    assert pedido.get_header("Authorization") == "Bearer chave-secreta"
    assert json.loads(pedido.data) == {"from": "App <a@b.co>", "to": ["d@e.co"], "subject": "Assunto", "text": "Texto"}


def test_carteiro_resend_falha_vira_falha_no_envio():
    c = em.CarteiroResend("k", "a@b.co")
    with mock.patch("urllib.request.urlopen", side_effect=OSError("rede")), pytest.raises(em.FalhaNoEnvio):
        asyncio.run(c.enviar(em.Mensagem("d@e.co", "A", "T")))


def test_carteiro_smtp_sempre_usa_tls():
    c = em.CarteiroSMTP(cfg(provedor="smtp", smtp_host="smtp.x", smtp_usuario="u", smtp_senha="s"))
    with mock.patch("smtplib.SMTP") as smtp:
        asyncio.run(c.enviar(em.Mensagem("d@e.co", "A", "T")))
    conexao = smtp.return_value.__enter__.return_value
    conexao.starttls.assert_called_once()
    conexao.login.assert_called_once_with("u", "s")
    enviado = conexao.send_message.call_args.args[0]
    assert enviado["To"] == "d@e.co" and enviado["Subject"] == "A"


def test_carteiro_smtp_falha_vira_falha_no_envio():
    c = em.CarteiroSMTP(cfg(provedor="smtp", smtp_host="smtp.x", smtp_usuario="u", smtp_senha="s"))
    with mock.patch("smtplib.SMTP", side_effect=OSError), pytest.raises(em.FalhaNoEnvio):
        asyncio.run(c.enviar(em.Mensagem("d@e.co", "A", "T")))


def test_criar_carteiro():
    assert isinstance(em.criar_carteiro(cfg()), em.CarteiroArquivo)
    assert isinstance(em.criar_carteiro(cfg(provedor="memoria")), em.CarteiroMemoria)
    assert isinstance(em.criar_carteiro(cfg(provedor="resend", resend_api_key="k")), em.CarteiroResend)
    assert isinstance(em.criar_carteiro(cfg(provedor="smtp")), em.CarteiroSMTP)


@pytest.mark.parametrize(
    "producao,env,mensagem",
    [
        (True, {"EMAIL_PROVEDOR": "arquivo"}, "Em produção"),
        (False, {"EMAIL_PROVEDOR": "pombo"}, "desconhecido"),
        (False, {"EMAIL_PROVEDOR": "resend"}, "RESEND_API_KEY"),
        (False, {"EMAIL_PROVEDOR": "smtp", "SMTP_HOST": "h"}, "SMTP_USUARIO"),
    ],
)
def test_configuracao_de_email_invalida_nao_sobe(monkeypatch, producao, env, mensagem):
    for k in ("EMAIL_PROVEDOR", "RESEND_API_KEY", "SMTP_HOST", "SMTP_USUARIO", "SMTP_SENHA"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(RuntimeError, match=mensagem):
        _email(producao, ("https://x.app",))


def test_app_url_padrao_vem_da_origem(monkeypatch):
    monkeypatch.delenv("APP_URL", raising=False)
    monkeypatch.setenv("EMAIL_PROVEDOR", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "k")
    assert _email(True, ("https://x.app",)).app_url == "https://x.app"
