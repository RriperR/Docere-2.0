"""Контракт репозитория пользователей для сценариев аутентификации."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.application.ports.repositories.auth.dtos import AuthUserDTO


class AuthRepositoryPort:
    """Порт репозитория для поиска и создания пользователей."""

    def find_by_email(self, email: str) -> AuthUserDTO | None:
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
    ) -> AuthUserDTO:
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

    def create_admin_user(
        self,
        fio: str,
        email: str,
        phone: str,
        password_hash: str,
    ) -> AuthUserDTO:
        """Создать пользователя-администратора.

        Args:
            fio: ФИО пользователя.
            email: Email пользователя.
            phone: Телефон пользователя.
            password_hash: Хеш пароля.

        Returns:
            Созданный пользователь.
        """
        raise NotImplementedError

    def create_staff_user(
        self,
        fio: str,
        email: str,
        phone: str,
        password_hash: str,
        role: str,
    ) -> AuthUserDTO:
        """Создать врача или администратора.

        Args:
            fio: ФИО пользователя.
            email: Email пользователя.
            phone: Телефон пользователя.
            password_hash: Хеш пароля.
            role: Роль пользователя (`doctor` или `admin`).

        Returns:
            Созданный пользователь.
        """
        raise NotImplementedError

    def find_by_id(self, user_id: UUID) -> AuthUserDTO | None:
        """Найти пользователя по идентификатору.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Пользователь, если найден, иначе `None`.
        """
        raise NotImplementedError

    def list_users(self, *, limit: int) -> tuple[AuthUserDTO, ...]:
        """Вернуть последних пользователей.

        Args:
            limit: Максимальное количество пользователей.

        Returns:
            Пользователи, отсортированные по дате создания.
        """
        raise NotImplementedError

    def set_status(self, *, user_id: UUID, status: str) -> AuthUserDTO | None:
        """Изменить статус пользователя.

        Args:
            user_id: Идентификатор пользователя.
            status: Новый статус учетной записи.

        Returns:
            Обновленный пользователь или `None`, если пользователь не найден.
        """
        raise NotImplementedError

    def set_password_hash(self, *, user_id: UUID, password_hash: str) -> bool:
        """Заменить хеш пароля пользователя.

        Args:
            user_id: Идентификатор пользователя.
            password_hash: Новый безопасный хеш пароля.

        Returns:
            `True`, если пользователь найден и хеш обновлен.
        """
        raise NotImplementedError
