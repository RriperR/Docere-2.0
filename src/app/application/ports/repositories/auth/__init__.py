"""Порт репозитория аутентификации."""

from app.application.ports.repositories.auth.dtos import AuthUserDTO
from app.application.ports.repositories.auth.port import AuthRepositoryPort

__all__ = ['AuthRepositoryPort', 'AuthUserDTO']
