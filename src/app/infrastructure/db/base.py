"""Базовые ORM-классы инфраструктурного слоя."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый declarative-класс SQLAlchemy."""

    pass
