"""Сценарий регистрации пользователя."""

from __future__ import annotations

from datetime import date

from app.application.ports.repositories.auth.port import AuthRepositoryPort
from app.application.ports.repositories.patient_passports.port import PatientPassportRepositoryPort
from app.application.ports.security.password_hasher import PasswordHasherPort
from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.auth.errors import EmailAlreadyExistsError


class RegisterUserUseCase:
    """Зарегистрировать нового пользователя с ролью пациента."""

    def __init__(
        self,
        repository: AuthRepositoryPort,
        patient_passport_repository: PatientPassportRepositoryPort,
        password_hasher: PasswordHasherPort,
    ) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий пользователей.
            patient_passport_repository: Репозиторий паспортов пациентов.
            password_hasher: Сервис хеширования паролей.
        """
        self._repository = repository
        self._patient_passport_repository = patient_passport_repository
        self._password_hasher = password_hasher

    def execute(
        self,
        *,
        fio: str,
        email: str,
        phone: str,
        password: str,
        date_of_birth: date | None,
    ) -> AuthenticatedUserDTO:
        """Создать нового пациента.

        Args:
            fio: ФИО пользователя.
            email: Email пользователя.
            phone: Телефон пользователя.
            password: Пароль в открытом виде.
            date_of_birth: Дата рождения пользователя.

        Returns:
            DTO созданного пользователя.

        Raises:
            EmailAlreadyExistsError: Если пользователь с таким email уже существует.
        """
        existing_user = self._repository.find_by_email(email=email)
        if existing_user is not None:
            raise EmailAlreadyExistsError

        password_hash = self._password_hasher.hash_password(plain_password=password)
        created_user = self._repository.create_patient_user(
            fio=fio,
            email=email,
            phone=phone,
            password_hash=password_hash,
            date_of_birth=date_of_birth,
        )
        self._patient_passport_repository.create_confirmed_passport(
            user_id=created_user.id,
            fio=created_user.fio,
            date_of_birth=created_user.date_of_birth,
            email=created_user.email,
            phone=created_user.phone,
            confirmed_at=created_user.created_at,
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
