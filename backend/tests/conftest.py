import pytest

from app import db


@pytest.fixture
def banco(tmp_path, monkeypatch):
    """Cada teste usa um banco e um arquivo de token próprios, sem tocar nos dados reais."""
    monkeypatch.setenv("TRADER_DB", str(tmp_path / "teste.db"))
    monkeypatch.setenv("TRADER_TOKEN_ARQUIVO", str(tmp_path / "token.txt"))
    monkeypatch.delenv("BRAPI_TOKEN", raising=False)
    db.inicializar()
    return tmp_path
