"""Normalización de URLs de base de datos y validaciones de producción.

Este módulo probaba antes una función `ensure_railway_tcp_proxy_ssl` que nunca
llegó a existir en `app/core/config.py`: el import fallaba y rompía la
colección completa de pytest.

No se implementó esa función a propósito: añadir `?sslmode=require` a la URL
rompe el driver, porque el dialecto `asyncpg` de SQLAlchemy no reconoce ese
parámetro y lo pasa tal cual a `asyncpg.connect()`. Para los endpoints TCP de
Railway basta con el comportamiento por defecto de asyncpg (`ssl="prefer"`),
que negocia TLS cuando el servidor lo ofrece.

Lo que sí se prueba aquí es lo que el módulo hace de verdad.
"""

import pytest
from pydantic import ValidationError

from app.core.config import (
    Settings,
    normalize_async_database_url,
    to_sync_database_url,
)


def test_normaliza_el_esquema_postgres_corto() -> None:
    url = "postgres://u:p@db.proxy.rlwy.net:12345/railway"
    assert normalize_async_database_url(url).startswith("postgresql+asyncpg://")


def test_normaliza_postgresql_a_asyncpg() -> None:
    url = "postgresql://u:p@localhost:5432/diet_agent"
    assert normalize_async_database_url(url) == (
        "postgresql+asyncpg://u:p@localhost:5432/diet_agent"
    )


def test_la_normalizacion_es_idempotente() -> None:
    once = normalize_async_database_url("postgres://u:p@host:1/db")
    assert normalize_async_database_url(once) == once


def test_devuelve_la_url_sin_cambios_si_no_es_postgres() -> None:
    assert normalize_async_database_url("sqlite+aiosqlite:///file.db") == (
        "sqlite+aiosqlite:///file.db"
    )


def test_to_sync_convierte_asyncpg_a_psycopg2() -> None:
    url = "postgresql+asyncpg://u:p@host:5432/db"
    assert to_sync_database_url(url) == "postgresql://u:p@host:5432/db"


def test_los_settings_normalizan_la_url_al_construirse() -> None:
    s = Settings(
        ENV="development",
        JWT_SECRET="x" * 64,
        DATABASE_URL="postgres://u:p@host:5432/db",
    )
    assert s.DATABASE_URL.startswith("postgresql+asyncpg://")


def test_produccion_sigue_exigiendo_secretos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(
            ENV="production",
            JWT_SECRET="change-me",
            DATABASE_URL="postgresql+asyncpg://u:p@host:5432/db",
        )
