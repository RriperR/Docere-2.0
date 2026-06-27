"""Контракт обновления профиля пользователя."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.application.ports.repositories.user_profiles.dtos import UserProfileDTO


class UserProfileRepositoryPort:
    """Порт согласованного чтения и обновления профиля."""

    def get_profile(self, *, user_id: UUID) -> UserProfileDTO | None:
        """Вернуть профиль пользователя или ``None``."""
        raise NotImplementedError

    def update_profile(
        self,
        *,
        user_id: UUID,
        fio: str,
        phone: str,
        date_of_birth: date | None,
        specialty: str | None,
    ) -> UserProfileDTO | None:
        """Обновить пользователя и связанные медицинские паспорта."""
        raise NotImplementedError
