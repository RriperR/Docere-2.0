"""Сценарий создания врача или администратора через admin API."""

from __future__ import annotations

from app.application.ports.repositories.auth.port import AuthRepositoryPort
from app.application.ports.security.password_hasher import PasswordHasherPort
from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.auth.errors import EmailAlreadyExistsError


class StaffUserAccessDeniedError(Exception):
    """Текущий пользователь не может создавать staff-аккаунты."""


class StaffUserValidationError(Exception):
    """Некорректные данные staff-пользователя."""


class CreateStaffUserUseCase:
    """Создать врача или администратора от имени администратора."""

    def __init__(self, repository: AuthRepositoryPort, password_hasher: PasswordHasherPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий пользователей.
            password_hasher: Сервис хеширования паролей.
        """
        self._repository = repository
        self._password_hasher = password_hasher

    def execute(
        self,
        *,
        actor_role: str,
        fio: str,
        email: str,
        phone: str,
        password: str,
        role: str,
    ) -> AuthenticatedUserDTO:
        """Создать staff-пользователя.

        Args:
            actor_role: Роль текущего пользователя.
            fio: ФИО создаваемого пользователя.
            email: Email создаваемого пользователя.
            phone: Телефон создаваемого пользователя.
            password: Начальный пароль.
            role: Роль создаваемого пользователя.

        Returns:
            Публичный профиль созданного пользователя.

        Raises:
            StaffUserAccessDeniedError: Если текущий пользователь не администратор.
            StaffUserValidationError: Если роль создаваемого пользователя не поддерживается.
            EmailAlreadyExistsError: Если email занят.
        """
        if actor_role != 'admin':
            raise StaffUserAccessDeniedError
        if role not in {'doctor', 'admin'}:
            raise StaffUserValidationError
        normalized_email = email.strip().lower()
        if self._repository.find_by_email(email=normalized_email) is not None:
            raise EmailAlreadyExistsError

        created_user = self._repository.create_staff_user(
            fio=fio.strip(),
            email=normalized_email,
            phone=phone.strip(),
            password_hash=self._password_hasher.hash_password(plain_password=password),
            role=role,
        )
        return AuthenticatedUserDTO(
            id=created_user.id,
            fio=created_user.fio,
            email=created_user.email,
            phone=created_user.phone,
            date_of_birth=created_user.date_of_birth,
            role=created_user.role,
            status=created_user.status,
        )
