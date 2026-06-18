"""SQLAlchemy-репозиторий медицинских записей."""

from __future__ import annotations

from datetime import date
from typing import cast
from uuid import UUID

from sqlalchemy import case, exists, or_, Select, select
from sqlalchemy.orm import Session

from app.application.ports.repositories.medical_records.dtos import AccessibleMedicalRecordDTO
from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.domain.entities.file_attachment import FileAttachment, FileAttachmentCategory
from app.domain.entities.medical_record import MedicalRecord, MedicalRecordStatus, MedicalRecordType
from app.domain.entities.patient_passport import PatientPassport, PatientPassportStatus
from app.domain.entities.practitioner_passport import PractitionerPassport, PractitionerPassportStatus
from app.domain.entities.record_comment import RecordComment
from app.infrastructure.db.models.medical_records.file_attachment import (
    FileAttachmentRow,
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
from app.infrastructure.db.models.medical_records.practitioner_passport import (
    PractitionerPassportRow,
    PractitionerPassportStatusRow,
)
from app.infrastructure.db.models.medical_records.record_comment import RecordCommentRow
from app.infrastructure.db.models.medical_records.user_record_link import (
    UserRecordLinkRow,
    UserRecordLinkSourceRow,
)


class SqlAlchemyMedicalRecordRepositoryAdapter(MedicalRecordRepositoryPort):
    """Репозиторий для чтения и создания медицинских записей."""

    def __init__(self, session: Session) -> None:
        """Привязать репозиторий к активной SQLAlchemy-сессии."""
        self._session = session

    def get_patient_passport(self, patient_passport_id: UUID) -> PatientPassport | None:
        """Вернуть паспорт пациента по идентификатору.

        Returns:
            Паспорт пациента или ``None``.
        """
        row = self._session.get(PatientPassportRow, patient_passport_id)
        if row is None:
            return None
        return self._to_patient_passport(row)

    def user_can_access_patient_passport(
        self,
        *,
        user_id: UUID,
        user_role: str,
        patient_passport_id: UUID,
    ) -> bool:
        """Проверить, что паспорт пациента доступен пользователю.

        Returns:
            ``True``, если паспорт виден пользователю в его списке карточек.
        """
        access_conditions = [UserRecordLinkRow.user_id == user_id]
        if user_role == 'patient':
            access_conditions.append(PatientPassportRow.patient_user_id == user_id)
        else:
            access_conditions.append(PatientPassportRow.created_by_user_id == user_id)

        return (
            self._session.scalar(
                select(PatientPassportRow.id)
                .outerjoin(UserRecordLinkRow, UserRecordLinkRow.patient_passport_id == PatientPassportRow.id)
                .where(
                    PatientPassportRow.id == patient_passport_id,
                    or_(*access_conditions),
                )
                .limit(1),
            )
            is not None
        )

    def get_practitioner_passport(self, practitioner_passport_id: UUID) -> PractitionerPassport | None:
        """Вернуть паспорт врача по идентификатору.

        Returns:
            Паспорт врача или ``None``.
        """
        row = self._session.get(PractitionerPassportRow, practitioner_passport_id)
        if row is None:
            return None
        return self._to_practitioner_passport(row)

    def get_or_create_practitioner_passport_for_user(
        self,
        user_id: UUID,
        full_name: str,
        email: str | None,
        phone: str | None,
    ) -> PractitionerPassport:
        """Вернуть паспорт внутреннего врача, создав его при необходимости.

        Returns:
            Найденный или созданный паспорт врача.
        """
        row = self._session.scalar(
            select(PractitionerPassportRow).where(PractitionerPassportRow.user_id == user_id),
        )
        if row is None:
            row = PractitionerPassportRow(
                created_by_user_id=user_id,
                user_id=user_id,
                full_name=full_name,
                email=email,
                phone=phone,
                status=PractitionerPassportStatusRow.CONFIRMED,
            )
            self._session.add(row)
            self._session.flush()
        return self._to_practitioner_passport(row)

    def create_practitioner_passport(
        self,
        created_by_user_id: UUID,
        full_name: str,
        specialty: str | None,
        organization: str | None,
        position: str | None,
        email: str | None,
        phone: str | None,
    ) -> PractitionerPassport:
        """Создать паспорт внешнего врача.

        Returns:
            Созданный паспорт врача.
        """
        row = PractitionerPassportRow(
            created_by_user_id=created_by_user_id,
            user_id=None,
            full_name=full_name,
            specialty=specialty,
            organization=organization,
            position=position,
            email=email,
            phone=phone,
            status=PractitionerPassportStatusRow.DRAFT,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_practitioner_passport(row)

    def create_record(
        self,
        creator_user_id: UUID,
        patient_passport_id: UUID,
        author_practitioner_passport_id: UUID | None,
        record_type: str,
        event_date: date,
        title: str | None,
        appointment_location: str | None,
        clinical_summary: str | None,
        payload_json: dict[str, object],
    ) -> AccessibleMedicalRecordDTO:
        """Создать медицинскую запись и ссылку доступа для автора.

        Returns:
            Доступная проекция только что созданной записи.
        """
        record_row = MedicalRecordRow(
            creator_user_id=creator_user_id,
            author_practitioner_passport_id=author_practitioner_passport_id,
            status=MedicalRecordStatusRow.UNCONFIRMED,
            record_type=MedicalRecordTypeRow(record_type),
            event_date=event_date,
            title=title,
            appointment_location=appointment_location,
            clinical_summary=clinical_summary,
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

        author_practitioner_row = (
            self._session.get(PractitionerPassportRow, author_practitioner_passport_id)
            if author_practitioner_passport_id is not None
            else None
        )
        return self._assemble_accessible_record(
            record_row=record_row,
            patient_passport_id=patient_passport_id,
            author_practitioner_row=author_practitioner_row,
        )

    def get_accessible_record(
        self,
        record_id: UUID,
        user_id: UUID,
    ) -> AccessibleMedicalRecordDTO | None:
        """Вернуть медицинскую запись, если пользователь имеет к ней доступ.

        Returns:
            Доступная проекция записи или ``None``.
        """
        query = self._accessible_record_query(record_id=record_id, user_id=user_id)
        row = self._session.execute(query).first()
        if row is None:
            return None

        record_row, patient_passport_id, author_practitioner_row = row
        return self._assemble_accessible_record(
            record_row=record_row,
            patient_passport_id=patient_passport_id,
            author_practitioner_row=author_practitioner_row,
        )

    def add_comment(
        self,
        record_id: UUID,
        author_user_id: UUID,
        body: str,
    ) -> RecordComment:
        """Добавить комментарий к медицинской записи.

        Returns:
            Созданная сущность комментария.
        """
        row = RecordCommentRow(
            record_id=record_id,
            author_user_id=author_user_id,
            body=body,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_record_comment(row)

    def record_exists(self, record_id: UUID) -> bool:
        """Проверить существование медицинской записи.

        Returns:
            ``True``, если запись существует, иначе ``False``.
        """
        return bool(
            self._session.scalar(
                select(exists().where(MedicalRecordRow.id == record_id)),
            ),
        )

    def _assemble_accessible_record(
        self,
        record_row: MedicalRecordRow,
        patient_passport_id: UUID | None,
        author_practitioner_row: PractitionerPassportRow | None,
    ) -> AccessibleMedicalRecordDTO:
        """Собрать проекцию записи с комментариями и вложениями.

        Паспорт автора передаётся уже загруженным (через join в access-запросе или
        прямой выборкой при создании), поэтому отдельного round-trip за ним нет.

        Returns:
            Доступная проекция записи со вложенными сущностями.
        """
        comments = tuple(
            self._to_record_comment(comment_row)
            for comment_row in self._session.scalars(
                select(RecordCommentRow)
                .where(RecordCommentRow.record_id == record_row.id)
                .order_by(RecordCommentRow.created_at.asc()),
            )
        )
        attachments = tuple(
            self._to_file_attachment(attachment_row)
            for attachment_row in self._session.scalars(
                select(FileAttachmentRow)
                .where(FileAttachmentRow.record_id == record_row.id)
                .order_by(FileAttachmentRow.uploaded_at.asc()),
            )
        )
        return AccessibleMedicalRecordDTO(
            record=self._to_medical_record(record_row),
            patient_passport_id=patient_passport_id,
            author_practitioner_passport=(
                self._to_practitioner_passport(author_practitioner_row) if author_practitioner_row is not None else None
            ),
            comments=comments,
            attachments=attachments,
        )

    def _accessible_record_query(
        self,
        record_id: UUID,
        user_id: UUID,
    ) -> Select[tuple[MedicalRecordRow, UUID | None, PractitionerPassportRow | None]]:
        """Собрать запрос записи с фильтрацией по доступу.

        Паспорт автора подтягивается тем же запросом через outer join, чтобы не
        делать отдельную выборку при сборке проекции.

        Returns:
            SQLAlchemy-запрос для поиска доступной записи.
        """
        priority_expression = case(
            (
                (PatientPassportRow.status == PatientPassportStatusRow.CONFIRMED)
                & (PatientPassportRow.patient_user_id.is_not(None)),
                0,
            ),
            else_=1,
        )
        query = (
            select(MedicalRecordRow, UserRecordLinkRow.patient_passport_id, PractitionerPassportRow)
            .join(UserRecordLinkRow, UserRecordLinkRow.record_id == MedicalRecordRow.id)
            .outerjoin(
                PatientPassportRow,
                PatientPassportRow.id == UserRecordLinkRow.patient_passport_id,
            )
            .outerjoin(
                PractitionerPassportRow,
                PractitionerPassportRow.id == MedicalRecordRow.author_practitioner_passport_id,
            )
            .where(
                MedicalRecordRow.id == record_id,
                UserRecordLinkRow.user_id == user_id,
            )
            .order_by(priority_expression, UserRecordLinkRow.created_at.desc())
            .limit(1)
        )
        # author-паспорт приходит через outer join, поэтому на уровне типов он nullable.
        return cast('Select[tuple[MedicalRecordRow, UUID | None, PractitionerPassportRow | None]]', query)

    @staticmethod
    def _to_medical_record(row: MedicalRecordRow) -> MedicalRecord:
        return MedicalRecord(
            id=row.id,
            creator_user_id=row.creator_user_id,
            author_practitioner_passport_id=row.author_practitioner_passport_id,
            status=MedicalRecordStatus(row.status.value),
            record_type=MedicalRecordType(row.record_type.value),
            event_date=row.event_date,
            title=row.title,
            appointment_location=row.appointment_location,
            clinical_summary=row.clinical_summary,
            payload_json=row.payload_json,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_patient_passport(row: PatientPassportRow) -> PatientPassport:
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

    @staticmethod
    def _to_practitioner_passport(row: PractitionerPassportRow) -> PractitionerPassport:
        return PractitionerPassport(
            id=row.id,
            created_by_user_id=row.created_by_user_id,
            user_id=row.user_id,
            full_name=row.full_name,
            specialty=row.specialty,
            organization=row.organization,
            position=row.position,
            email=row.email,
            phone=row.phone,
            status=PractitionerPassportStatus(row.status.value),
            confirmed_at=row.confirmed_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_record_comment(row: RecordCommentRow) -> RecordComment:
        return RecordComment(
            id=row.id,
            record_id=row.record_id,
            author_user_id=row.author_user_id,
            body=row.body,
            created_at=row.created_at,
        )

    @staticmethod
    def _to_file_attachment(row: FileAttachmentRow) -> FileAttachment:
        return FileAttachment(
            id=row.id,
            record_id=row.record_id,
            uploaded_by_user_id=row.uploaded_by_user_id,
            category=FileAttachmentCategory(row.category.value),
            storage_key=row.storage_key,
            mime_type=row.mime_type,
            size_bytes=row.size_bytes,
            uploaded_at=row.uploaded_at,
        )
