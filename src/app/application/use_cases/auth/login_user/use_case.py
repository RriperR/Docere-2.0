"""Сценарий входа пользователя по email и паролю."""

from __future__ import annotations

from app.application.ports.repositories.auth.port import AuthRepositoryPort
from app.application.ports.security.password_hasher import PasswordHasherPort
from app.application.ports.security.token_service import TokenServicePort
from app.application.use_cases.auth.common.dtos import AuthTokenDTO
from app.application.use_cases.auth.errors import InvalidCredentialsError


class LoginUserUseCase:
    """Проверить учетные данные и выдать пару access/refresh токенов."""

    def __init__(
        self,
        repository: AuthRepositoryPort,
        password_hasher: PasswordHasherPort,
        token_service: TokenServicePort,
    ) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий пользователей.
            password_hasher: Сервис проверки паролей.
            token_service: Сервис выпуска токенов.
        """
        self._repository = repository
        self._password_hasher = password_hasher
        self._token_service = token_service

    def execute(self, *, email: str, password: str) -> AuthTokenDTO:
        """Аутентифицировать пользователя и вернуть токены.

        Args:
            email: Email пользователя.
            password: Пароль в открытом виде.

        Returns:
            DTO с access и refresh токенами.

        Raises:
            InvalidCredentialsError: Если email или пароль некорректны,
                либо пользователь заблокирован.
        """
        user = self._repository.find_by_email(email=email)
        if user is None or user.status != 'active':
            raise InvalidCredentialsError

        is_valid_password = self._password_hasher.verify_password(
            plain_password=password,
            password_hash=user.password_hash,
        )
        if not is_valid_password:
            raise InvalidCredentialsError

        access_token = self._token_service.create_access_token(user_id=user.id)
        refresh_token = self._token_service.create_refresh_token(user_id=user.id)
        return AuthTokenDTO(access_token=access_token, refresh_token=refresh_token)
