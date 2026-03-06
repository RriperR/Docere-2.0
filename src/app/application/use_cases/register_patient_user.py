"""Use-case регистрации пациента."""

from __future__ import annotations

from datetime import date

from app.application.dto.auth_user_view import AuthUserView
from app.application.ports.auth_repository import AuthRepositoryPort
from app.application.ports.password_hasher import PasswordHasherPort
from app.application.use_cases.auth_errors import EmailAlreadyExistsError


class RegisterPatientUser:
    """Зарегистрировать нового пользователя с ролью пациента."""

    def __init__(self, repository: AuthRepositoryPort, password_hasher: PasswordHasherPort) -> None:
        """Инициализировать use-case.

        Args:
            repository: Репозиторий пользователей.
            password_hasher: Сервис хеширования паролей.
        """
        self._repository = repository
        self._password_hasher = password_hasher

    def execute(
        self,
        fio: str,
        email: str,
        phone: str,
        password: str,
        date_of_birth: date | None,
    ) -> AuthUserView:
        """Создать нового пациента.

        Args:
            fio: ФИО пользователя.
            email: Email пользователя.
            phone: Телефон пользователя.
            password: Пароль в открытом виде.
            date_of_birth: Дата рождения, если указана.

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
        return AuthUserView(
            id=created_user.id,
            fio=created_user.fio,
            email=created_user.email,
            phone=created_user.phone,
            date_of_birth=created_user.date_of_birth,
            role=created_user.role,
            status=created_user.status,
        )
