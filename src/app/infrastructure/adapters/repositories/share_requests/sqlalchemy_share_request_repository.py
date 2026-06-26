"""SQLAlchemy-репозиторий sharing-запросов медицинских записей."""

from __future__ import annotations

from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.application.ports.repositories.share_requests.dtos import (
    CreateShareRequestResultDTO,
    RecordShareDTO,
    ShareRequestDTO,
    ShareUserDTO,
)
from app.application.ports.repositories.share_requests.port import ShareRequestRepositoryPort
from app.application.use_cases.share_requests.errors import (
    SharedRecordNotFoundError,
    ShareRequestAccessDeniedError,
    ShareRequestNotFoundError,
    ShareTargetNotFoundError,
)
from app.domain.entities.medical_record import MedicalRecordStatus
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus
from app.infrastructure.db.models.medical_records.file_attachment import FileAttachmentRow
from app.infrastructure.db.models.medical_records.medical_record import MedicalRecordRow
from app.infrastructure.db.models.medical_records.patient_passport import PatientPassportRow
from app.infrastructure.db.models.medical_records.record_comment import RecordCommentRow
from app.infrastructure.db.models.medical_records.record_share import (
    RecordShareRequestRow,
    RecordShareRow,
    RecordShareStatusRow,
)
from app.infrastructure.db.models.medical_records.user_record_link import (
    UserRecordLinkRow,
    UserRecordLinkSourceRow,
)


class SqlAlchemyShareRequestRepositoryAdapter(ShareRequestRepositoryPort):
    """Репозиторий для команд и запросов sharing medical records."""

    def __init__(self, session: Session) -> None:
        """Инициализировать репозиторий.

        Args:
            session: Активная SQLAlchemy-сессия.
        """
        self._session = session

    def create_share_request(
        self,
        *,
        from_user_id: UUID,
        to_user_email: str,
        record_ids: tuple[UUID, ...],
        message: str | None,
        expires_at: datetime | None,
    ) -> CreateShareRequestResultDTO:
        """Создать sharing-запрос.

        Returns:
            Созданный запрос и список пропущенных записей.

        Raises:
            ShareTargetNotFoundError: Если получатель не найден.
            ShareRequestAccessDeniedError: Если отправителю недоступна запись или выбран сам отправитель.
            SharedRecordNotFoundError: Если запись не найдена.
        """
        target_user = self._get_active_user_by_email(to_user_email)
        if target_user is None:
            raise ShareTargetNotFoundError
        if target_user.id == from_user_id:
            raise ShareRequestAccessDeniedError

        share_contexts: list[tuple[UUID, UUID | None]] = []
        skipped_record_ids: list[UUID] = []
        for record_id in record_ids:
            access_link = self._get_access_link(user_id=from_user_id, record_id=record_id)
            if access_link is None:
                if self._record_exists(record_id):
                    raise ShareRequestAccessDeniedError
                raise SharedRecordNotFoundError

            if self._target_already_has_access(
                user_id=target_user.id,
                record_id=record_id,
            ) or self._has_open_share(to_user_id=target_user.id, record_id=record_id):
                skipped_record_ids.append(record_id)
                continue

            share_contexts.append((record_id, access_link.patient_passport_id))

        if not share_contexts:
            return CreateShareRequestResultDTO(request=None, skipped_record_ids=tuple(skipped_record_ids))

        request_row = RecordShareRequestRow(
            from_user_id=from_user_id,
            to_user_id=target_user.id,
            status=RecordShareStatusRow.PENDING,
            message=message,
            expires_at=expires_at,
        )
        self._session.add(request_row)
        self._session.flush()

        for record_id, patient_passport_id in share_contexts:
            self._session.add(
                RecordShareRow(
                    request_id=request_row.id,
                    record_id=record_id,
                    patient_passport_id=patient_passport_id,
                    status=RecordShareStatusRow.PENDING,
                ),
            )
        self._session.flush()
        return CreateShareRequestResultDTO(
            request=self._to_request_dto(request_row),
            skipped_record_ids=tuple(skipped_record_ids),
        )

    def list_inbox(self, *, user_id: UUID) -> tuple[ShareRequestDTO, ...]:
        """Вернуть входящие sharing-запросы пользователя.

        Returns:
            Входящие запросы.
        """
        rows = self._session.scalars(
            select(RecordShareRequestRow)
            .where(RecordShareRequestRow.to_user_id == user_id)
            .order_by(RecordShareRequestRow.created_at.desc()),
        ).all()
        return tuple(self._to_request_dto(row) for row in rows)

    def list_outbox(self, *, user_id: UUID) -> tuple[ShareRequestDTO, ...]:
        """Вернуть исходящие sharing-запросы пользователя.

        Returns:
            Исходящие запросы.
        """
        rows = self._session.scalars(
            select(RecordShareRequestRow)
            .where(RecordShareRequestRow.from_user_id == user_id)
            .order_by(RecordShareRequestRow.created_at.desc()),
        ).all()
        return tuple(self._to_request_dto(row) for row in rows)

    def accept_request(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Принять pending sharing-запрос.

        Returns:
            Обновленный запрос.

        Raises:
            ShareRequestAccessDeniedError: Если запрос уже истёк или не находится в статусе pending.
        """
        request_row = self._get_request_for_recipient(request_id, user_id)
        self._ensure_pending(request_row)

        now = utc_now()
        if _is_expired(request_row.expires_at, now):
            raise ShareRequestAccessDeniedError
        for share_row in self._get_request_shares(request_row.id):
            if share_row.status != RecordShareStatusRow.PENDING:
                continue
            if not self._target_already_has_access(user_id=user_id, record_id=share_row.record_id):
                existing_link = self._get_existing_record_link(
                    user_id=user_id,
                    record_id=share_row.record_id,
                    patient_passport_id=share_row.patient_passport_id,
                )
                if existing_link is None:
                    self._session.add(
                        UserRecordLinkRow(
                            user_id=user_id,
                            record_id=share_row.record_id,
                            patient_passport_id=share_row.patient_passport_id,
                            source=UserRecordLinkSourceRow.SHARE_ACCEPTED,
                            source_record_share_id=share_row.id,
                            expires_at=request_row.expires_at,
                        ),
                    )
                else:
                    existing_link.source = UserRecordLinkSourceRow.SHARE_ACCEPTED
                    existing_link.source_record_share_id = share_row.id
                    existing_link.expires_at = request_row.expires_at
            share_row.status = RecordShareStatusRow.ACCEPTED
            share_row.responded_at = now
            self._confirm_record_if_patient_accepts_own_doctor_record(share_row=share_row, recipient_user_id=user_id)

        request_row.status = RecordShareStatusRow.ACCEPTED
        request_row.responded_at = now
        self._session.flush()
        return self._to_request_dto(request_row)

    def decline_request(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Отклонить pending sharing-запрос.

        Returns:
            Обновленный запрос.
        """
        request_row = self._get_request_for_recipient(request_id, user_id)
        self._ensure_pending(request_row)

        now = utc_now()
        for share_row in self._get_request_shares(request_row.id):
            if share_row.status == RecordShareStatusRow.PENDING:
                share_row.status = RecordShareStatusRow.DECLINED
                share_row.responded_at = now
        request_row.status = RecordShareStatusRow.DECLINED
        request_row.responded_at = now
        self._session.flush()
        return self._to_request_dto(request_row)

    def cancel_request(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Отменить pending sharing-запрос отправителем.

        Returns:
            Обновленный запрос.
        """
        request_row = self._get_request_for_sender(request_id, user_id)
        self._ensure_pending(request_row)

        now = utc_now()
        for share_row in self._get_request_shares(request_row.id):
            if share_row.status == RecordShareStatusRow.PENDING:
                share_row.status = RecordShareStatusRow.CANCELLED
        request_row.status = RecordShareStatusRow.CANCELLED
        request_row.cancelled_at = now
        self._session.flush()
        return self._to_request_dto(request_row)

    def revoke_request(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Отозвать accepted sharing-запрос отправителем.

        Returns:
            Обновленный запрос.

        Raises:
            ShareRequestAccessDeniedError: Если запрос не находится в статусе accepted.
        """
        request_row = self._get_request_for_sender(request_id, user_id)
        if request_row.status != RecordShareStatusRow.ACCEPTED:
            raise ShareRequestAccessDeniedError

        now = utc_now()
        for share_row in self._get_request_shares(request_row.id):
            if share_row.status != RecordShareStatusRow.ACCEPTED:
                continue
            link_rows = self._session.scalars(
                select(UserRecordLinkRow).where(
                    UserRecordLinkRow.user_id == request_row.to_user_id,
                    UserRecordLinkRow.record_id == share_row.record_id,
                    UserRecordLinkRow.source == UserRecordLinkSourceRow.SHARE_ACCEPTED,
                    UserRecordLinkRow.source_record_share_id == share_row.id,
                ),
            ).all()
            for link_row in link_rows:
                self._session.delete(link_row)
            share_row.status = RecordShareStatusRow.REVOKED
            share_row.revoked_at = now

        request_row.status = RecordShareStatusRow.REVOKED
        request_row.revoked_at = now
        self._session.flush()
        return self._to_request_dto(request_row)

    def _get_active_user_by_email(self, email: str) -> UserRow | None:
        return self._session.scalar(
            select(UserRow).where(
                UserRow.email == email,
                UserRow.status == UserStatus.ACTIVE,
            ),
        )

    def _record_exists(self, record_id: UUID) -> bool:
        return bool(self._session.scalar(select(exists().where(MedicalRecordRow.id == record_id))))

    def _get_access_link(self, *, user_id: UUID, record_id: UUID) -> UserRecordLinkRow | None:
        return self._session.scalar(
            select(UserRecordLinkRow)
            .where(
                UserRecordLinkRow.user_id == user_id,
                UserRecordLinkRow.record_id == record_id,
            )
            .order_by(UserRecordLinkRow.created_at.desc())
            .limit(1),
        )

    def _target_already_has_access(self, *, user_id: UUID, record_id: UUID) -> bool:
        return bool(
            self._session.scalar(
                select(
                    exists().where(
                        UserRecordLinkRow.user_id == user_id,
                        UserRecordLinkRow.record_id == record_id,
                        self._active_access_condition(),
                    ),
                ),
            ),
        )

    def _has_open_share(self, *, to_user_id: UUID, record_id: UUID) -> bool:
        return bool(
            self._session.scalar(
                select(
                    exists()
                    .where(
                        RecordShareRequestRow.id == RecordShareRow.request_id,
                        RecordShareRequestRow.to_user_id == to_user_id,
                        RecordShareRow.record_id == record_id,
                        self._active_share_request_condition(),
                        RecordShareRow.status.in_(
                            [RecordShareStatusRow.PENDING, RecordShareStatusRow.ACCEPTED],
                        ),
                    )
                    .select_from(RecordShareRow),
                ),
            ),
        )

    def _get_existing_record_link(
        self,
        *,
        user_id: UUID,
        record_id: UUID,
        patient_passport_id: UUID | None,
    ) -> UserRecordLinkRow | None:
        query = select(UserRecordLinkRow).where(
            UserRecordLinkRow.user_id == user_id,
            UserRecordLinkRow.record_id == record_id,
        )
        if patient_passport_id is None:
            query = query.where(UserRecordLinkRow.patient_passport_id.is_(None))
        else:
            query = query.where(UserRecordLinkRow.patient_passport_id == patient_passport_id)
        return self._session.scalar(query.limit(1))

    @staticmethod
    def _active_access_condition() -> ColumnElement[bool]:
        return or_(UserRecordLinkRow.expires_at.is_(None), UserRecordLinkRow.expires_at > utc_now())

    @staticmethod
    def _active_share_request_condition() -> ColumnElement[bool]:
        return or_(RecordShareRequestRow.expires_at.is_(None), RecordShareRequestRow.expires_at > utc_now())

    def _confirm_record_if_patient_accepts_own_doctor_record(
        self,
        *,
        share_row: RecordShareRow,
        recipient_user_id: UUID,
    ) -> None:
        if share_row.patient_passport_id is None:
            return

        patient_passport = self._session.get(PatientPassportRow, share_row.patient_passport_id)
        if patient_passport is None or patient_passport.patient_user_id != recipient_user_id:
            return

        record_row = self._session.get(MedicalRecordRow, share_row.record_id)
        if record_row is None or record_row.status == MedicalRecordStatus.CONFIRMED:
            return

        creator = self._session.get(UserRow, record_row.creator_user_id)
        if creator is not None and creator.role == UserRole.DOCTOR:
            record_row.status = MedicalRecordStatus.CONFIRMED
            record_row.confirmed_by_user_id = recipient_user_id
            record_row.confirmed_at = utc_now()

    def _get_request_for_recipient(self, request_id: UUID, user_id: UUID) -> RecordShareRequestRow:
        request_row = self._session.scalar(
            select(RecordShareRequestRow).where(
                RecordShareRequestRow.id == request_id,
                RecordShareRequestRow.to_user_id == user_id,
            ),
        )
        if request_row is None:
            raise ShareRequestNotFoundError
        return request_row

    def _get_request_for_sender(self, request_id: UUID, user_id: UUID) -> RecordShareRequestRow:
        request_row = self._session.scalar(
            select(RecordShareRequestRow).where(
                RecordShareRequestRow.id == request_id,
                RecordShareRequestRow.from_user_id == user_id,
            ),
        )
        if request_row is None:
            raise ShareRequestNotFoundError
        return request_row

    @staticmethod
    def _ensure_pending(request_row: RecordShareRequestRow) -> None:
        if request_row.status != RecordShareStatusRow.PENDING:
            raise ShareRequestAccessDeniedError

    def _get_request_shares(self, request_id: UUID) -> list[RecordShareRow]:
        return list(
            self._session.scalars(
                select(RecordShareRow)
                .where(RecordShareRow.request_id == request_id)
                .order_by(RecordShareRow.created_at.asc()),
            ),
        )

    def _to_request_dto(self, row: RecordShareRequestRow) -> ShareRequestDTO:
        from_user = self._session.get(UserRow, row.from_user_id)
        to_user = self._session.get(UserRow, row.to_user_id)
        if from_user is None or to_user is None:
            raise RuntimeError('Share request references missing user')
        return ShareRequestDTO(
            id=row.id,
            from_user=self._to_user_dto(from_user),
            to_user=self._to_user_dto(to_user),
            status=row.status.value,
            message=row.message,
            expires_at=row.expires_at,
            shares=tuple(self._to_share_dto(share_row) for share_row in self._get_request_shares(row.id)),
            created_at=row.created_at,
            responded_at=row.responded_at,
            cancelled_at=row.cancelled_at,
            revoked_at=row.revoked_at,
        )

    @staticmethod
    def _to_user_dto(row: UserRow) -> ShareUserDTO:
        return ShareUserDTO(
            id=row.id,
            fio=row.fio,
            email=row.email,
            role=UserRole(row.role).value,
        )

    def _to_share_dto(self, row: RecordShareRow) -> RecordShareDTO:
        record = self._session.get(MedicalRecordRow, row.record_id)
        if record is None:
            raise RuntimeError('Record share references missing medical record')
        patient = self._session.get(PatientPassportRow, row.patient_passport_id) if row.patient_passport_id else None
        return RecordShareDTO(
            id=row.id,
            record_id=row.record_id,
            title=record.title,
            record_type=record.record_type.value,
            event_date=record.event_date,
            patient_fio=patient.fio if patient is not None else None,
            patient_passport_id=row.patient_passport_id,
            attachments_count=self._record_attachments_count(row.record_id),
            comments_count=self._record_comments_count(row.record_id),
            status=row.status.value,
            created_at=row.created_at,
            responded_at=row.responded_at,
            revoked_at=row.revoked_at,
        )

    def _record_attachments_count(self, record_id: UUID) -> int:
        return self._session.scalar(
            select(func.count(FileAttachmentRow.id)).where(FileAttachmentRow.record_id == record_id),
        ) or 0

    def _record_comments_count(self, record_id: UUID) -> int:
        return self._session.scalar(
            select(func.count(RecordCommentRow.id)).where(RecordCommentRow.record_id == record_id),
        ) or 0


def _is_expired(expires_at: datetime | None, now: datetime) -> bool:
    if expires_at is None:
        return False
    value = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=UTC)
    return value <= now
