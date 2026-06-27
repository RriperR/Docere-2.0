"""Сценарий свободного обновления профиля с описанием изменений."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.application.ports.repositories.user_profiles.dtos import UserProfileDTO
from app.application.ports.repositories.user_profiles.port import UserProfileRepositoryPort
from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.auth.errors import UserNotFoundError


class ProfileValidationError(Exception):
    """Новые профильные данные не прошли бизнес-валидацию."""


@dataclass(frozen=True, slots=True)
class UpdateProfileResultDTO:
    """Обновлённый профиль и поля, изменившиеся относительно прежнего состояния."""

    user: AuthenticatedUserDTO
    changes: dict[str, dict[str, object | None]]


class UpdateProfileUseCase:
    """Обновить профиль без изменения роли или статуса пользователя."""

    def __init__(self, repository: UserProfileRepositoryPort) -> None:
        """Инициализировать сценарий.

        Args:
            repository: Репозиторий согласованного профиля.
        """
        self._repository = repository

    def execute(
        self,
        *,
        user_id: UUID,
        fio: str,
        phone: str,
        date_of_birth: date | None,
        specialty: str | None,
    ) -> UpdateProfileResultDTO:
        """Нормализовать, сохранить и описать изменения профиля.

        Returns:
            Обновлённый публичный профиль и audit diff.

        Raises:
            UserNotFoundError: Если пользователь не найден.
            ProfileValidationError: Если ФИО или специализация некорректны.
        """
        current = self._repository.get_profile(user_id=user_id)
        if current is None:
            raise UserNotFoundError

        normalized_fio = ' '.join(fio.split())
        normalized_phone = phone.strip()
        normalized_specialty = ' '.join((specialty or '').split()) or None
        if not normalized_fio or len(normalized_fio) > 255 or len(normalized_phone) > 32:
            raise ProfileValidationError
        if current.role == 'doctor' and (
            normalized_specialty is None or len(normalized_specialty) < 2 or len(normalized_specialty) > 255
        ):
            raise ProfileValidationError
        if current.role != 'doctor':
            normalized_specialty = None

        updated = self._repository.update_profile(
            user_id=user_id,
            fio=normalized_fio,
            phone=normalized_phone,
            date_of_birth=date_of_birth,
            specialty=normalized_specialty,
        )
        if updated is None:
            raise UserNotFoundError
        return UpdateProfileResultDTO(
            user=_to_authenticated_user(updated),
            changes=_profile_changes(current, updated),
        )


def _to_authenticated_user(profile: UserProfileDTO) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        id=profile.id,
        fio=profile.fio,
        email=profile.email,
        phone=profile.phone,
        date_of_birth=profile.date_of_birth,
        role=profile.role,
        status=profile.status,
        specialty=profile.specialty,
    )


def _profile_changes(
    before: UserProfileDTO,
    after: UserProfileDTO,
) -> dict[str, dict[str, object | None]]:
    changes: dict[str, dict[str, object | None]] = {}
    values = {
        'fio': (before.fio, after.fio),
        'phone': (before.phone, after.phone),
        'date_of_birth': (_date_value(before.date_of_birth), _date_value(after.date_of_birth)),
        'specialty': (before.specialty, after.specialty),
    }
    for field, (old_value, new_value) in values.items():
        if old_value != new_value:
            changes[field] = {'before': old_value, 'after': new_value}
    return changes


def _date_value(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None
