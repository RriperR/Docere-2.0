from app.application.dto.auth_token import AuthToken
from app.application.ports.auth_repository import AuthRepositoryPort
from app.application.ports.password_hasher import PasswordHasherPort
from app.application.ports.token_service import TokenServicePort
from app.application.use_cases.auth_errors import InvalidCredentialsError


class LoginUser:
    def __init__(
        self,
        repository: AuthRepositoryPort,
        password_hasher: PasswordHasherPort,
        token_service: TokenServicePort,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._token_service = token_service

    def execute(self, email: str, password: str) -> AuthToken:
        user = self._repository.find_by_email(email=email)
        if user is None:
            raise InvalidCredentialsError

        if user.status != 'active':
            raise InvalidCredentialsError

        if not self._password_hasher.verify_password(plain_password=password, password_hash=user.password_hash):
            raise InvalidCredentialsError

        access_token = self._token_service.create_access_token(user_id=user.id)
        return AuthToken(access_token=access_token)
