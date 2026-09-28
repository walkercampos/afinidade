import pytest

from app.config import _webauthn


def test_producao_sem_dominio_das_passkeys_nao_sobe(monkeypatch):
    monkeypatch.delenv("WEBAUTHN_RP_ID", raising=False)
    monkeypatch.delenv("WEBAUTHN_ORIGENS", raising=False)
    with pytest.raises(RuntimeError, match="WEBAUTHN_RP_ID"):
        _webauthn(producao=True)


def test_dev_usa_localhost(monkeypatch):
    monkeypatch.delenv("WEBAUTHN_RP_ID", raising=False)
    monkeypatch.delenv("WEBAUTHN_ORIGENS", raising=False)
    assert _webauthn(producao=False) == ("localhost", ("http://localhost:8000",))


def test_origens_normalizadas(monkeypatch):
    monkeypatch.setenv("WEBAUTHN_RP_ID", "afinidade.app")
    monkeypatch.setenv("WEBAUTHN_ORIGENS", " https://afinidade.app/ , https://www.afinidade.app ,")
    assert _webauthn(producao=True) == ("afinidade.app", ("https://afinidade.app", "https://www.afinidade.app"))
