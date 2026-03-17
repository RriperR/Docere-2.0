"""SQLAlchemy-репозиторий медицинских записей."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import case, exists, Select, select
from sqlalchemy.orm import Session

from app.application.ports.repositories.medical_records.dtos import (
    AccessibleMedicalRecordDTO,
)
from app.application.ports.repositories.medical_records.port import (
    MedicalRecordRepositoryPort,
)
from app.domain.entities.medical_record import (
    MedicalRecord,
    MedicalRecordStatus,
    MedicalRecordType,
)
from app.domain.entities.patient_passport import (
    PatientPassport,
    PatientPassportStatus,
)
from app.infrastructure.db.models.medical_records.medical_record import (
    MedicalRecordRow,
    MedicalRecordStatusRow,
    MedicalRecordTypeRow,
)
from app.infrastructure.db.models.medical_records.patient_passport import (
    PatientPassportRow,
    PatientPassportStatusRow,
)
from app.infrastructure.db.models.medical_records.user_record_link import (
    UserRecordLinkRow,
    UserRecordLinkSourceRow,
)


class SqlAlchemyMedicalRecordRepositoryAdapter(MedicalRecordRepositoryPort):
    """Репозиторий для чтения и создания медицинских записей."""

    def __init__(self, session: Session) -> None:
        """Инициализировать репозиторий.

        Args:
            session: Активная SQLAlchemy-сессия.
        """
        self._session = session

    def get_patient_passport(self, patient_passport_id: UUID) -> PatientPassport | None:
        """Получить паспорт пациента по идентификатору.

        Args:
            patient_passport_id: Идентификатор паспортной карточки.

        Returns:
            Паспорт пациента или `None`.
        """
        row = self._session.get(PatientPassportRow, patient_passport_id)
        if row is None:
            return None
        return self._to_patient_passport(row)

    def create_record(
        self,
        creator_user_id: UUID,
        patient_passport_id: UUID,
        record_type: str,
        event_date: date,
        title: str | None,
        payload_json: dict[str, object],
    ) -> AccessibleMedicalRecordDTO:
        """Создать запись и базовый доступ автора к ней.

        Args:
            creator_user_id: Идентификатор автора.
            patient_passport_id: Паспортная карточка для контекста автора.
            record_type: Тип записи.
            event_date: Дата медицинского события.
            title: Заголовок записи.
            payload_json: Содержимое записи.

        Returns:
            Созданная запись в пользовательском контексте автора.
        """
        record_row = MedicalRecordRow(
            creator_user_id=creator_user_id,
            status=MedicalRecordStatusRow.UNCONFIRMED,
            record_type=MedicalRecordTypeRow(record_type),
            event_date=event_date,
            title=title,
            payload_json=payload_json,
        )
        self._session.add(record_row)
        self._session.flush()

        access_row = UserRecordLinkRow(
            user_id=creator_user_id,
            record_id=record_row.id,
            patient_passport_id=patient_passport_id,
            source=UserRecordLinkSourceRow.CREATOR,
        )
        self._session.add(access_row)
        self._session.flush()

        return AccessibleMedicalRecordDTO(
            record=self._to_medical_record(record_row),
            patient_passport_id=patient_passport_id,
        )

    def get_accessible_record(
        self,
        record_id: UUID,
        user_id: UUID,
    ) -> AccessibleMedicalRecordDTO | None:
        """Получить запись, если пользователь имеет к ней доступ.

        Args:
            record_id: Идентификатор записи.
            user_id: Идентификатор пользователя.

        Returns:
            Запись в пользовательском контексте или `None`.
        """
        query = self._accessible_record_query(record_id=record_id, user_id=user_id)
        row = self._session.execute(query).first()
        if row is None:
            return None

        record_row, patient_passport_id = row
        return AccessibleMedicalRecordDTO(
            record=self._to_medical_record(record_row),
            patient_passport_id=patient_passport_id,
        )

    def record_exists(self, record_id: UUID) -> bool:
        """Проверить существование записи.

        Args:
            record_id: Идентификатор записи.

        Returns:
            `True`, если запись существует.
        """
        return bool(
            self._session.scalar(
                select(exists().where(MedicalRecordRow.id == record_id)),
            ),
        )

    def _accessible_record_query(
        self,
        record_id: UUID,
        user_id: UUID,
    ) -> Select[tuple[MedicalRecordRow, UUID | None]]:
        """Собрать запрос доступной записи с приоритетом подтвержденного паспорта.

        Args:
            record_id: Идентификатор записи.
            user_id: Идентификатор пользователя.

        Returns:
            SQLAlchemy-запрос.
        """
        priority_expression = case(
            (
                (PatientPassportRow.status == PatientPassportStatusRow.CONFIRMED)
                & (PatientPassportRow.patient_user_id.is_not(None)),
                0,
            ),
            else_=1,
        )
        return (
            select(MedicalRecordRow, UserRecordLinkRow.patient_passport_id)
            .join(UserRecordLinkRow, UserRecordLinkRow.record_id == MedicalRecordRow.id)
            .outerjoin(
                PatientPassportRow,
                PatientPassportRow.id == UserRecordLinkRow.patient_passport_id,
            )
            .where(
                MedicalRecordRow.id == record_id,
                UserRecordLinkRow.user_id == user_id,
            )
            .order_by(priority_expression, UserRecordLinkRow.created_at.desc())
            .limit(1)
        )

    @staticmethod
    def _to_medical_record(row: MedicalRecordRow) -> MedicalRecord:
        """Преобразовать ORM-модель в доменную сущность записи.

        Args:
            row: ORM-строка записи.

        Returns:
            Доменная сущность записи.
        """
        return MedicalRecord(
            id=row.id,
            creator_user_id=row.creator_user_id,
            status=MedicalRecordStatus(row.status.value),
            record_type=MedicalRecordType(row.record_type.value),
            event_date=row.event_date,
            title=row.title,
            payload_json=row.payload_json,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_patient_passport(row: PatientPassportRow) -> PatientPassport:
        """Преобразовать ORM-модель в доменную сущность паспорта.

        Args:
            row: ORM-строка паспорта.

        Returns:
            Доменная сущность паспорта.
        """
        return PatientPassport(
            id=row.id,
            created_by_user_id=row.created_by_user_id,
            patient_user_id=row.patient_user_id,
            fio=row.fio,
            date_of_birth=row.date_of_birth,
            email=row.email,
            phone=row.phone,
            status=PatientPassportStatus(row.status.value),
            confirmed_at=row.confirmed_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
