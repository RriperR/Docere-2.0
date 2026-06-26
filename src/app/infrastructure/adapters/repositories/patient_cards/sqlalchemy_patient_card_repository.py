"""SQLAlchemy-репозиторий динамических карточек пациентов."""

from __future__ import annotations

from datetime import date
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import and_, func, or_, Select, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.application.ports.repositories.medical_records.dtos import AccessibleMedicalRecordDTO
from app.application.ports.repositories.patient_cards.dtos import (
    PatientRecordSummaryDTO,
    PatientSearchResultDTO,
    PatientSummaryDTO,
)
from app.application.ports.repositories.patient_cards.port import PatientCardRepositoryPort
from app.application.use_cases.medical_records.common.dtos import PractitionerPassportDTO
from app.domain.entities.patient_passport import PatientPassportStatus
from app.infrastructure.adapters.repositories.medical_records.sqlalchemy_medical_record_repository import (
    SqlAlchemyMedicalRecordRepositoryAdapter,
)
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.auth.user import UserRow
from app.infrastructure.db.models.medical_records.medical_record import MedicalRecordRow
from app.infrastructure.db.models.medical_records.patient_passport import PatientPassportRow
from app.infrastructure.db.models.medical_records.user_record_link import UserRecordLinkRow


class SqlAlchemyPatientCardRepositoryAdapter(PatientCardRepositoryPort):
    """Репозиторий для чтения и создания карточек пациентов."""

    def __init__(self, session: Session) -> None:
        """Инициализировать репозиторий.

        Args:
            session: Активная SQLAlchemy-сессия.
        """
        self._session = session

    def list_accessible_patients(self, *, user_id: UUID, user_role: str) -> tuple[PatientSummaryDTO, ...]:
        """Вернуть доступные карточки пациентов.

        Returns:
            Краткие представления карточек.
        """
        rows = self._session.scalars(self._accessible_patient_passports_query(user_id, user_role)).all()
        return tuple(self._to_patient_summary(row, user_id) for row in rows)

    def create_patient_passport(
        self,
        *,
        created_by_user_id: UUID,
        fio: str,
        date_of_birth: date | None,
        email: str | None,
        phone: str | None,
    ) -> PatientSummaryDTO:
        """Создать черновой паспорт пациента.

        Returns:
            Краткое представление созданной карточки.
        """
        row = PatientPassportRow(
            created_by_user_id=created_by_user_id,
            patient_user_id=None,
            fio=fio,
            date_of_birth=date_of_birth,
            email=email,
            phone=phone,
            status=PatientPassportStatus.DRAFT,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_patient_summary(row, created_by_user_id)

    def search_patient_passports(
        self,
        *,
        query: str,
        date_of_birth: date | None,
        requested_by_user_id: UUID,
        requested_by_role: str,
        limit: int,
    ) -> tuple[PatientSearchResultDTO, ...]:
        """Найти вероятные совпадения PatientPassport.

        Returns:
            Кандидаты, отсортированные по убыванию похожести.
        """
        rows = self._session.scalars(
            self._accessible_patient_passports_query(requested_by_user_id, requested_by_role)
            .order_by(PatientPassportRow.updated_at.desc())
            .limit(500),
        ).all()
        normalized_query = self._normalize_search_text(query)
        results: list[PatientSearchResultDTO] = []
        for row in rows:
            score = self._patient_match_score(row, normalized_query, date_of_birth)
            if score < 0.45:
                continue
            results.append(
                PatientSearchResultDTO(
                    patient=self._to_patient_summary(row, requested_by_user_id),
                    match_score=round(score, 3),
                ),
            )

        results.sort(key=lambda item: item.match_score, reverse=True)
        return tuple(results[:limit])

    def get_accessible_patient(
        self,
        *,
        patient_id: UUID,
        user_id: UUID,
        user_role: str,
    ) -> PatientSummaryDTO | None:
        """Вернуть карточку, если она доступна пользователю.

        Returns:
            Краткое представление карточки или ``None``.
        """
        row = self._session.scalar(
            self._accessible_patient_passports_query(user_id, user_role).where(PatientPassportRow.id == patient_id),
        )
        if row is None:
            return None
        return self._to_patient_summary(row, user_id)

    def list_patient_records(
        self,
        *,
        patient_id: UUID,
        user_id: UUID,
        user_role: str,
    ) -> tuple[PatientRecordSummaryDTO, ...]:
        """Вернуть записи доступной карточки пациента.

        Returns:
            Краткие представления записей.
        """
        del user_role
        repository = SqlAlchemyMedicalRecordRepositoryAdapter(session=self._session)
        record_ids = self._session.scalars(
            select(UserRecordLinkRow.record_id)
            .join(MedicalRecordRow, MedicalRecordRow.id == UserRecordLinkRow.record_id)
            .where(
                UserRecordLinkRow.user_id == user_id,
                UserRecordLinkRow.patient_passport_id == patient_id,
                self._active_access_condition(),
            )
            .order_by(MedicalRecordRow.event_date.desc(), MedicalRecordRow.created_at.desc()),
        ).all()

        summaries: list[PatientRecordSummaryDTO] = []
        for record_id in record_ids:
            accessible_record = repository.get_accessible_record(record_id=record_id, user_id=user_id)
            if accessible_record is None:
                continue
            summaries.append(self._to_record_summary(accessible_record))
        return tuple(summaries)

    def _accessible_patient_passports_query(
        self,
        user_id: UUID,
        user_role: str,
    ) -> Select[tuple[PatientPassportRow]]:
        if user_role == 'patient':
            return (
                select(PatientPassportRow)
                .outerjoin(UserRecordLinkRow, self._active_patient_link_join())
                .where(
                    or_(
                        PatientPassportRow.patient_user_id == user_id,
                        UserRecordLinkRow.user_id == user_id,
                    ),
                )
                .distinct()
                .order_by(PatientPassportRow.confirmed_at.desc().nullslast(), PatientPassportRow.created_at.desc())
            )

        return (
            select(PatientPassportRow)
            .outerjoin(UserRecordLinkRow, self._active_patient_link_join())
            .where(
                or_(
                    PatientPassportRow.created_by_user_id == user_id,
                    UserRecordLinkRow.user_id == user_id,
                ),
            )
            .distinct()
            .order_by(PatientPassportRow.updated_at.desc())
        )

    def _to_patient_summary(self, row: PatientPassportRow, user_id: UUID) -> PatientSummaryDTO:
        record_count, last_record_date = self._patient_record_stats(row.id, user_id)
        return PatientSummaryDTO(
            id=row.id,
            fio=row.fio,
            date_of_birth=row.date_of_birth,
            email=row.email,
            phone=row.phone,
            status=row.status.value,
            access_context=self._access_context(row, user_id),
            record_count=record_count,
            last_record_date=last_record_date,
        )

    @staticmethod
    def _access_context(row: PatientPassportRow, user_id: UUID) -> str:
        if row.patient_user_id == user_id and row.status == PatientPassportStatus.CONFIRMED:
            return 'own_confirmed'
        if row.created_by_user_id == user_id:
            return 'created'
        return 'shared'

    def _patient_record_stats(self, patient_id: UUID, user_id: UUID) -> tuple[int, date | None]:
        stats = self._session.execute(
            select(
                func.count(func.distinct(UserRecordLinkRow.record_id)),
                func.max(MedicalRecordRow.event_date),
            )
            .join(MedicalRecordRow, MedicalRecordRow.id == UserRecordLinkRow.record_id)
            .where(
                UserRecordLinkRow.user_id == user_id,
                UserRecordLinkRow.patient_passport_id == patient_id,
                self._active_access_condition(),
            ),
        ).one()
        return int(stats[0] or 0), stats[1]

    @staticmethod
    def _active_patient_link_join() -> ColumnElement[bool]:
        return and_(
            UserRecordLinkRow.patient_passport_id == PatientPassportRow.id,
            SqlAlchemyPatientCardRepositoryAdapter._active_access_condition(),
        )

    @staticmethod
    def _active_access_condition() -> ColumnElement[bool]:
        return or_(UserRecordLinkRow.expires_at.is_(None), UserRecordLinkRow.expires_at > utc_now())

    @classmethod
    def _patient_match_score(
        cls,
        row: PatientPassportRow,
        normalized_query: str,
        date_of_birth: date | None,
    ) -> float:
        fields = [
            row.fio,
            row.email or '',
            row.phone or '',
        ]
        field_scores = [cls._text_match_score(normalized_query, cls._normalize_search_text(value)) for value in fields]
        score = max(field_scores)
        if date_of_birth is not None and row.date_of_birth == date_of_birth:
            score = min(1.0, score + 0.2)
        return score

    @staticmethod
    def _text_match_score(query: str, value: str) -> float:
        if not value:
            return 0.0
        if query in value:
            return 1.0
        return SequenceMatcher(None, query, value).ratio()

    @staticmethod
    def _normalize_search_text(value: str) -> str:
        return ' '.join(value.casefold().split())

    def _to_record_summary(self, accessible_record: AccessibleMedicalRecordDTO) -> PatientRecordSummaryDTO:
        record = accessible_record.record
        practitioner = accessible_record.author_practitioner_passport
        creator = self._session.get(UserRow, record.creator_user_id)
        return PatientRecordSummaryDTO(
            id=record.id,
            status=record.status.value,
            record_type=record.record_type.value,
            event_date=record.event_date,
            title=record.title,
            appointment_location=record.appointment_location,
            clinical_summary=record.clinical_summary,
            creator_user_id=record.creator_user_id,
            creator_fio=creator.fio if creator is not None else '',
            author_practitioner_passport=(
                PractitionerPassportDTO(
                    id=practitioner.id,
                    user_id=practitioner.user_id,
                    full_name=practitioner.full_name,
                    specialty=practitioner.specialty,
                    organization=practitioner.organization,
                    position=practitioner.position,
                    email=practitioner.email,
                    phone=practitioner.phone,
                    status=practitioner.status.value,
                )
                if practitioner is not None
                else None
            ),
            comments_count=len(accessible_record.comments),
            attachments_count=len(accessible_record.attachments),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
