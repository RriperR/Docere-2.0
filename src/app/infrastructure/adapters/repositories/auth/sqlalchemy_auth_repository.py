"""SQLAlchemy-реализация репозитория пользователей."""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.application.ports.repositories.auth.dtos import AuthUserDTO
from app.application.ports.repositories.auth.port import AuthRepositoryPort
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus


class SqlAlchemyAuthRepositoryAdapter(AuthRepositoryPort):
    """Репозиторий для чтения и создания пользователей."""

    def __init__(self, session: Session) -> None:
        """Инициализировать репозиторий.

        Args:
            session: Активная SQLAlchemy-сессия.
        """
        self._session = session

    def find_by_email(self, email: str) -> AuthUserDTO | None:
        """Найти пользователя по email.

        Args:
            email: Email пользователя.

        Returns:
            Пользователь, если найден, иначе `None`.
        """
        normalized_email = email.strip().lower()
        user_row = self._session.scalar(
            select(UserRow).where(UserRow.email == normalized_email),
        )
        if user_row is None:
            return None
        return self._to_domain(user_row)

    def create_patient_user(
        self,
        fio: str,
        email: str,
        phone: str,
        password_hash: str,
        date_of_birth: date | None,
    ) -> AuthUserDTO:
        """Создать нового пользователя-пациента.

        Args:
            fio: ФИО пользователя.
            email: Email пользователя.
            phone: Телефон пользователя.
            password_hash: Хеш пароля.
            date_of_birth: Дата рождения, если указана.

        Returns:
            Созданный пользователь доменного типа.
        """
        normalized_email = email.strip().lower()
        user_row = UserRow(
            id=uuid4(),
            fio=fio,
            email=normalized_email,
            phone=phone,
            date_of_birth=date_of_birth,
            password_hash=password_hash,
            role=UserRole.PATIENT,
            status=UserStatus.ACTIVE,
        )
        self._session.add(user_row)
        self._session.flush()
        return self._to_domain(user_row)

    def create_admin_user(
        self,
        fio: str,
        email: str,
        phone: str,
        password_hash: str,
    ) -> AuthUserDTO:
        """Создать нового пользователя-администратора.

        Args:
            fio: ФИО пользователя.
            email: Email пользователя.
            phone: Телефон пользователя.
            password_hash: Хеш пароля.

        Returns:
            Созданный пользователь доменного типа.
        """
        normalized_email = email.strip().lower()
        user_row = UserRow(
            id=uuid4(),
            fio=fio,
            email=normalized_email,
            phone=phone,
            date_of_birth=None,
            password_hash=password_hash,
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        self._session.add(user_row)
        self._session.flush()
        return self._to_domain(user_row)

    def create_staff_user(
        self,
        fio: str,
        email: str,
        phone: str,
        password_hash: str,
        role: str,
    ) -> AuthUserDTO:
        """Создать врача или администратора.

        Args:
            fio: ФИО пользователя.
            email: Email пользователя.
            phone: Телефон пользователя.
            password_hash: Хеш пароля.
            role: Роль пользователя.

        Returns:
            Созданный пользователь доменного типа.
        """
        normalized_email = email.strip().lower()
        user_row = UserRow(
            id=uuid4(),
            fio=fio,
            email=normalized_email,
            phone=phone,
            date_of_birth=None,
            password_hash=password_hash,
            role=UserRole(role),
            status=UserStatus.ACTIVE,
        )
        self._session.add(user_row)
        self._session.flush()
        return self._to_domain(user_row)

    def find_by_id(self, user_id: UUID) -> AuthUserDTO | None:
        """Найти пользователя по идентификатору.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Пользователь, если найден, иначе `None`.
        """
        user_row = self._session.get(UserRow, user_id)
        if user_row is None:
            return None
        return self._to_domain(user_row)

    def list_users(self, *, limit: int) -> tuple[AuthUserDTO, ...]:
        """Вернуть последних пользователей.

        Args:
            limit: Максимальное количество пользователей.

        Returns:
            Пользователи, отсортированные по дате создания.
        """
        rows = self._session.scalars(
            select(UserRow).order_by(desc(UserRow.created_at), desc(UserRow.id)).limit(limit),
        ).all()
        return tuple(self._to_domain(row) for row in rows)

    def set_status(self, *, user_id: UUID, status: str) -> AuthUserDTO | None:
        """Изменить статус пользователя.

        Args:
            user_id: Идентификатор пользователя.
            status: Новый статус учетной записи.

        Returns:
            Обновленный пользователь или `None`, если пользователь не найден.
        """
        user_row = self._session.get(UserRow, user_id)
        if user_row is None:
            return None
        user_row.status = UserStatus(status)
        self._session.flush()
        return self._to_domain(user_row)

    @staticmethod
    def _to_domain(user_row: UserRow) -> AuthUserDTO:
        """Преобразовать ORM-модель пользователя в application-снимок.

        Args:
            user_row: ORM-строка пользователя.

        Returns:
            Снимок пользователя для application-слоя.
        """
        return AuthUserDTO(
            id=user_row.id,
            fio=user_row.fio,
            email=user_row.email,
            phone=user_row.phone,
            date_of_birth=user_row.date_of_birth,
            password_hash=user_row.password_hash,
            role=str(user_row.role),
            status=str(user_row.status),
            created_at=user_row.created_at,
            updated_at=user_row.updated_at,
        )
