"""Контракты репозитория пользователей для use-case аутентификации."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuthUser:
    """Снимок пользователя для application-слоя."""

    id: UUID
    fio: str
    email: str
    phone: str
    date_of_birth: date | None
    password_hash: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


class AuthRepositoryPort:
    """Порт репозитория для операций поиска и создания пользователей."""

    def find_by_email(self, email: str) -> AuthUser | None:
        """Найти пользователя по email.

        Args:
            email: Email пользователя.

        Returns:
            Пользователь, если найден, иначе `None`.
        """
        raise NotImplementedError

    def create_patient_user(
        self,
        fio: str,
        email: str,
        phone: str,
        password_hash: str,
        date_of_birth: date | None,
    ) -> AuthUser:
        """Создать пользователя-пациента.

        Args:
            fio: ФИО пользователя.
            email: Email пользователя.
            phone: Телефон пользователя.
            password_hash: Хеш пароля.
            date_of_birth: Дата рождения, если указана.

        Returns:
            Созданный пользователь.
        """
        raise NotImplementedError

    def find_by_id(self, user_id: UUID) -> AuthUser | None:
        """Найти пользователя по идентификатору.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Пользователь, если найден, иначе `None`.
        """
        raise NotImplementedError
