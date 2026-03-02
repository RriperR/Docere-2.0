from __future__ import annotations

from datetime import date

from app.application.dto.auth_user_view import AuthUserView
from app.application.ports.auth_repository import AuthRepositoryPort
from app.application.ports.password_hasher import PasswordHasherPort
from app.application.use_cases.auth_errors import EmailAlreadyExistsError


class RegisterPatientUser:
    def __init__(self, repository: AuthRepositoryPort, password_hasher: PasswordHasherPort) -> None:
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
