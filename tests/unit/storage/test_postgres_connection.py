import pytest

from src.storage import postgres_connection
from src.storage.postgres_connection import (
    DATABASE_URL_ENV,
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    get_database_url_from_env,
    connect_postgres,
)


def test_get_database_url_from_env_returns_database_url(monkeypatch):
    expected_url = "postgresql://compass_user:compass_password@localhost:5433/compass_dev"

    monkeypatch.setenv(DATABASE_URL_ENV, expected_url)

    assert get_database_url_from_env() == expected_url


def test_get_database_url_from_env_raises_when_missing(monkeypatch):
    monkeypatch.delenv(DATABASE_URL_ENV, raising=False)

    with pytest.raises(RuntimeError, match=DATABASE_URL_ENV):
        get_database_url_from_env()


def test_connect_postgres_passes_database_url_and_timeout(monkeypatch):
    captured = {}

    def fake_connect(conninfo, **kwargs):
        captured["conninfo"] = conninfo
        captured["kwargs"] = kwargs
        return "fake-connection"

    monkeypatch.setattr(postgres_connection.psycopg, "connect", fake_connect)

    result = connect_postgres("postgresql://user:password@localhost:5433/db")

    assert result == "fake-connection"
    assert captured["conninfo"] == "postgresql://user:password@localhost:5433/db"
    assert captured["kwargs"]["connect_timeout"] == DEFAULT_CONNECT_TIMEOUT_SECONDS