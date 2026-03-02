from app.application.dto.auth_user_view import AuthUserView
from app.application.ports.auth_repository import AuthRepositoryPort
from app.application.ports.token_service import TokenServicePort
from app.application.use_cases.auth_errors import InvalidTokenError, UserNotFoundError


class GetAuthenticatedUser:
    def __init__(self, repository: AuthRepositoryPort, token_service: TokenServicePort) -> None:
        self._repository = repository
        self._token_service = token_service

    def execute(self, token: str) -> AuthUserView:
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
