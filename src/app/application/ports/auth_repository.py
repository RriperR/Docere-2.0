from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuthUser:
    id: UUID
    fio: str
    email: str
    phone: str
    date_of_birth: date | None
    password_hash: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


class AuthRepositoryPort:
    def find_by_email(self, email: str) -> AuthUser | None:
        raise NotImplementedError

    def create_patient_user(
        self,
        fio: str,
        email: str,
        phone: str,
        password_hash: str,
        date_of_birth: date | None,
    ) -> AuthUser:
        raise NotImplementedError

    def find_by_id(self, user_id: UUID) -> AuthUser | None:
        raise NotImplementedError
