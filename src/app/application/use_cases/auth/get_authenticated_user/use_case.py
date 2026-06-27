"""Сценарий получения данных текущего пользователя."""

from __future__ import annotations

from app.application.ports.repositories.auth.port import AuthRepositoryPort
from app.application.ports.repositories.user_profiles.port import UserProfileRepositoryPort
from app.application.ports.security.token_service import TokenServicePort
from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.auth.errors import InvalidTokenError, UserNotFoundError


class GetAuthenticatedUserUseCase:
    """Получить пользователя по access-токену."""

    def __init__(
        self,
        repository: AuthRepositoryPort,
        profile_repository: UserProfileRepositoryPort,
        token_service: TokenServicePort,
    ) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий пользователей.
            profile_repository: Репозиторий полного профиля.
            token_service: Сервис проверки токенов.
        """
        self._repository = repository
        self._profile_repository = profile_repository
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

        profile = self._profile_repository.get_profile(user_id=user.id)
        if profile is None:
            raise UserNotFoundError
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
