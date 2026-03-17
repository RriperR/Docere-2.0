"""Сценарий получения данных текущего пользователя."""

from __future__ import annotations

from app.application.ports.repositories.auth.port import AuthRepositoryPort
from app.application.ports.security.token_service import TokenServicePort
from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.auth.errors import InvalidTokenError, UserNotFoundError


class GetAuthenticatedUserUseCase:
    """Получить пользователя по access-токену."""

    def __init__(
        self,
        repository: AuthRepositoryPort,
        token_service: TokenServicePort,
    ) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий пользователей.
            token_service: Сервис проверки токенов.
        """
        self._repository = repository
        self._token_service = token_service

    def execute(self, *, token: str) -> AuthenticatedUserDTO:
        """Вернуть данные текущего пользователя по токену.

        Args:
            token: Access-токен пользователя.

        Returns:
            Публичное представление пользователя.

        Raises:
            InvalidTokenError: Если токен некорректен или пользователь заблокирован.
            UserNotFoundError: Если пользователь из токена не найден.
        """
        try:
            user_id = self._token_service.decode_access_token(token=token)
        except ValueError as exc:
            raise InvalidTokenError from exc

        user = self._repository.find_by_id(user_id=user_id)
        if user is None:
            raise UserNotFoundError
        if user.status != 'active':
            raise InvalidTokenError

        return AuthenticatedUserDTO(
            id=user.id,
            fio=user.fio,
            email=user.email,
            phone=user.phone,
            date_of_birth=user.date_of_birth,
            role=user.role,
            status=user.status,
        )
