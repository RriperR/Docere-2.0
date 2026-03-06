"""Use-case получения данных текущего аутентифицированного пользователя."""

from app.application.dto.auth_user_view import AuthUserView
from app.application.ports.auth_repository import AuthRepositoryPort
from app.application.ports.token_service import TokenServicePort
from app.application.use_cases.auth_errors import InvalidTokenError, UserNotFoundError


class GetAuthenticatedUser:
    """Получить пользователя по access-токену."""

    def __init__(self, repository: AuthRepositoryPort, token_service: TokenServicePort) -> None:
        """Инициализировать use-case.

        Args:
            repository: Репозиторий пользователей.
            token_service: Сервис проверки токенов.
        """
        self._repository = repository
        self._token_service = token_service

    def execute(self, token: str) -> AuthUserView:
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

        return AuthUserView(
            id=user.id,
            fio=user.fio,
            email=user.email,
            phone=user.phone,
            date_of_birth=user.date_of_birth,
            role=user.role,
            status=user.status,
        )
