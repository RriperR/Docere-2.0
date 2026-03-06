"""Фабрики подключения к БД и жизненный цикл SQLAlchemy-сессии."""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.settings import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Создать и закешировать SQLAlchemy Engine.

    Returns:
        Объект `Engine`.
    """
    settings = get_settings()
    return create_engine(settings.database.url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Создать и закешировать фабрику SQLAlchemy-сессий.

    Returns:
        Фабрика сессий SQLAlchemy.
    """
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    """Предоставить сессию БД в виде dependency.

    Yields:
        Активная SQLAlchemy-сессия.
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def clear_db_session_cache() -> None:
    """Очистить кеши engine и session-factory."""
    get_session_factory.cache_clear()
    get_engine.cache_clear()
