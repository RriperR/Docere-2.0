"""Сценарий обновления пары access/refresh токенов."""

from __future__ import annotations

from app.application.ports.repositories.auth.port import AuthRepositoryPort
from app.application.ports.security.token_service import TokenServicePort
from app.application.use_cases.auth.common.dtos import AuthTokenDTO
from app.application.use_cases.auth.errors import InvalidRefreshTokenError


class RefreshAccessTokenUseCase:
    """Проверить refresh-токен и выдать новую пару токенов."""

    def __init__(
        self,
        repository: AuthRepositoryPort,
        token_service: TokenServicePort,
    ) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий пользователей.
            token_service: Сервис работы с токенами.
        """
        self._repository = repository
        self._token_service = token_service

    def execute(self, *, refresh_token: str) -> AuthTokenDTO:
        """Обновить access/refresh токены по refresh-токену.

        Args:
            refresh_token: Refresh-токен пользователя.

        Returns:
            Новая пара токенов.

        Raises:
            InvalidRefreshTokenError: Если refresh-токен невалиден
                или пользователь неактивен.
        """
        try:
            user_id = self._token_service.decode_refresh_token(token=refresh_token)
        except ValueError as exc:
            raise InvalidRefreshTokenError from exc

        user = self._repository.find_by_id(user_id=user_id)
        if user is None or user.status != 'active':
            raise InvalidRefreshTokenError

        access_token = self._token_service.create_access_token(user_id=user.id)
        new_refresh_token = self._token_service.create_refresh_token(user_id=user.id)
        return AuthTokenDTO(access_token=access_token, refresh_token=new_refresh_token)
