"""REST-роуты sharing выбранных медицинских записей."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.infrastructure.db.models._time import moscow_now
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus
from app.infrastructure.db.models.medical_records.medical_record import MedicalRecordRow
from app.infrastructure.db.models.medical_records.record_share import (
    RecordShareRequestRow,
    RecordShareRow,
    RecordShareStatusRow,
)
from app.infrastructure.db.models.medical_records.user_record_link import (
    UserRecordLinkRow,
    UserRecordLinkSourceRow,
)
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)
from app.presentation.rest.public.v1.share_requests.schemas import (
    CreateShareRequestResponseSchema,
    CreateShareRequestSchema,
    RecordShareResponseSchema,
    ShareRequestResponseSchema,
    ShareUserResponseSchema,
)
from app.presentation.webserver.http_errors import raise_forbidden, raise_not_found

router = APIRouter(prefix='/share-requests', tags=['share-requests'])


@router.post('', response_model=CreateShareRequestResponseSchema, status_code=status.HTTP_201_CREATED)
def create_share_request(
    payload: CreateShareRequestSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    session: Session = db_session_dependency,
) -> CreateShareRequestResponseSchema:
    """Создать запрос на sharing выбранных записей.

    Returns:
        Созданный sharing request и список записей, пропущенных как дубли.
    """
    target_user = _get_active_user_by_email(session, str(payload.to_user_email))
    if target_user is None:
        raise_not_found('Target user not found')
    if target_user.id == current_user.id:
        raise_forbidden('Cannot share records with yourself')

    seen_record_ids = tuple(dict.fromkeys(payload.record_ids))
    share_contexts: list[tuple[UUID, UUID | None]] = []
    skipped_record_ids: list[UUID] = []

    for record_id in seen_record_ids:
        access_link = _get_access_link(session, user_id=current_user.id, record_id=record_id)
        if access_link is None:
            if _record_exists(session, record_id):
                raise_forbidden('You do not have access to one or more records')
            raise_not_found('Medical record not found')

        if _target_already_has_access(session, user_id=target_user.id, record_id=record_id) or _has_open_share(
            session,
            to_user_id=target_user.id,
            record_id=record_id,
        ):
            skipped_record_ids.append(record_id)
            continue

        share_contexts.append((record_id, access_link.patient_passport_id))

    if not share_contexts:
        return CreateShareRequestResponseSchema(
            request=None,
            skipped_record_ids=tuple(skipped_record_ids),
        )

    request_row = RecordShareRequestRow(
        from_user_id=current_user.id,
        to_user_id=target_user.id,
        status=RecordShareStatusRow.PENDING,
        message=payload.message.strip() if payload.message else None,
    )
    session.add(request_row)
    session.flush()

    for record_id, patient_passport_id in share_contexts:
        session.add(
            RecordShareRow(
                request_id=request_row.id,
                record_id=record_id,
                patient_passport_id=patient_passport_id,
                status=RecordShareStatusRow.PENDING,
            ),
        )

    session.commit()
    session.refresh(request_row)
    return CreateShareRequestResponseSchema(
        request=_to_request_response(session, request_row),
        skipped_record_ids=tuple(skipped_record_ids),
    )


@router.get('/inbox', response_model=list[ShareRequestResponseSchema])
def list_inbox_share_requests(
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    session: Session = db_session_dependency,
) -> list[ShareRequestResponseSchema]:
    """Вернуть входящие sharing-запросы текущего пользователя.

    Returns:
        Список входящих sharing-запросов.
    """
    request_rows = session.scalars(
        select(RecordShareRequestRow)
        .where(RecordShareRequestRow.to_user_id == current_user.id)
        .order_by(RecordShareRequestRow.created_at.desc()),
    ).all()
    return [_to_request_response(session, row) for row in request_rows]


@router.get('/outbox', response_model=list[ShareRequestResponseSchema])
def list_outbox_share_requests(
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    session: Session = db_session_dependency,
) -> list[ShareRequestResponseSchema]:
    """Вернуть исходящие sharing-запросы текущего пользователя.

    Returns:
        Список исходящих sharing-запросов.
    """
    request_rows = session.scalars(
        select(RecordShareRequestRow)
        .where(RecordShareRequestRow.from_user_id == current_user.id)
        .order_by(RecordShareRequestRow.created_at.desc()),
    ).all()
    return [_to_request_response(session, row) for row in request_rows]


@router.post('/{request_id}/accept', response_model=ShareRequestResponseSchema)
def accept_share_request(
    request_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    session: Session = db_session_dependency,
) -> ShareRequestResponseSchema:
    """Принять pending sharing-запрос и выдать фактический доступ.

    Returns:
        Обновлённый sharing request.
    """
    request_row = _get_request_for_recipient(session, request_id, current_user.id)
    _ensure_pending(request_row)

    now = moscow_now()
    share_rows = _get_request_shares(session, request_row.id)
    for share_row in share_rows:
        if share_row.status != RecordShareStatusRow.PENDING:
            continue
        if not _target_already_has_access(session, user_id=current_user.id, record_id=share_row.record_id):
            session.add(
                UserRecordLinkRow(
                    user_id=current_user.id,
                    record_id=share_row.record_id,
                    patient_passport_id=share_row.patient_passport_id,
                    source=UserRecordLinkSourceRow.SHARE_ACCEPTED,
                    source_record_share_id=share_row.id,
                ),
            )
        share_row.status = RecordShareStatusRow.ACCEPTED
        share_row.responded_at = now

    request_row.status = RecordShareStatusRow.ACCEPTED
    request_row.responded_at = now
    session.commit()
    session.refresh(request_row)
    return _to_request_response(session, request_row)


@router.post('/{request_id}/decline', response_model=ShareRequestResponseSchema)
def decline_share_request(
    request_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    session: Session = db_session_dependency,
) -> ShareRequestResponseSchema:
    """Отклонить pending sharing-запрос.

    Returns:
        Обновлённый sharing request.
    """
    request_row = _get_request_for_recipient(session, request_id, current_user.id)
    _ensure_pending(request_row)

    now = moscow_now()
    for share_row in _get_request_shares(session, request_row.id):
        if share_row.status == RecordShareStatusRow.PENDING:
            share_row.status = RecordShareStatusRow.DECLINED
            share_row.responded_at = now
    request_row.status = RecordShareStatusRow.DECLINED
    request_row.responded_at = now
    session.commit()
    session.refresh(request_row)
    return _to_request_response(session, request_row)


@router.post('/{request_id}/cancel', response_model=ShareRequestResponseSchema)
def cancel_share_request(
    request_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    session: Session = db_session_dependency,
) -> ShareRequestResponseSchema:
    """Отменить pending sharing-запрос инициатором.

    Returns:
        Обновлённый sharing request.
    """
    request_row = _get_request_for_sender(session, request_id, current_user.id)
    _ensure_pending(request_row)

    now = moscow_now()
    for share_row in _get_request_shares(session, request_row.id):
        if share_row.status == RecordShareStatusRow.PENDING:
            share_row.status = RecordShareStatusRow.CANCELLED
    request_row.status = RecordShareStatusRow.CANCELLED
    request_row.cancelled_at = now
    session.commit()
    session.refresh(request_row)
    return _to_request_response(session, request_row)


@router.post('/{request_id}/revoke', response_model=ShareRequestResponseSchema)
def revoke_share_request(
    request_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    session: Session = db_session_dependency,
) -> ShareRequestResponseSchema:
    """Отозвать ранее принятый sharing-запрос инициатором.

    Returns:
        Обновлённый sharing request.
    """
    request_row = _get_request_for_sender(session, request_id, current_user.id)
    if request_row.status != RecordShareStatusRow.ACCEPTED:
        raise_forbidden('Only accepted share request can be revoked')

    now = moscow_now()
    for share_row in _get_request_shares(session, request_row.id):
        if share_row.status != RecordShareStatusRow.ACCEPTED:
            continue
        link_rows = session.scalars(
            select(UserRecordLinkRow).where(
                UserRecordLinkRow.user_id == request_row.to_user_id,
                UserRecordLinkRow.record_id == share_row.record_id,
                UserRecordLinkRow.source == UserRecordLinkSourceRow.SHARE_ACCEPTED,
                UserRecordLinkRow.source_record_share_id == share_row.id,
            ),
        ).all()
        for link_row in link_rows:
            session.delete(link_row)
        share_row.status = RecordShareStatusRow.REVOKED
        share_row.revoked_at = now

    request_row.status = RecordShareStatusRow.REVOKED
    request_row.revoked_at = now
    session.commit()
    session.refresh(request_row)
    return _to_request_response(session, request_row)


def _get_active_user_by_email(session: Session, email: str) -> UserRow | None:
    return session.scalar(
        select(UserRow).where(
            UserRow.email == email.strip().lower(),
            UserRow.status == UserStatus.ACTIVE,
        ),
    )


def _record_exists(session: Session, record_id: UUID) -> bool:
    return bool(session.scalar(select(exists().where(MedicalRecordRow.id == record_id))))


def _get_access_link(session: Session, *, user_id: UUID, record_id: UUID) -> UserRecordLinkRow | None:
    return session.scalar(
        select(UserRecordLinkRow)
        .where(
            UserRecordLinkRow.user_id == user_id,
            UserRecordLinkRow.record_id == record_id,
        )
        .order_by(UserRecordLinkRow.created_at.desc())
        .limit(1),
    )


def _target_already_has_access(session: Session, *, user_id: UUID, record_id: UUID) -> bool:
    return bool(
        session.scalar(
            select(
                exists().where(
                    UserRecordLinkRow.user_id == user_id,
                    UserRecordLinkRow.record_id == record_id,
                ),
            ),
        ),
    )


def _has_open_share(session: Session, *, to_user_id: UUID, record_id: UUID) -> bool:
    return bool(
        session.scalar(
            select(
                exists()
                .where(
                    RecordShareRequestRow.id == RecordShareRow.request_id,
                    RecordShareRequestRow.to_user_id == to_user_id,
                    RecordShareRow.record_id == record_id,
                    RecordShareRow.status.in_(
                        [RecordShareStatusRow.PENDING, RecordShareStatusRow.ACCEPTED],
                    ),
                )
                .select_from(RecordShareRow),
            ),
        ),
    )


def _get_request_for_recipient(session: Session, request_id: UUID, user_id: UUID) -> RecordShareRequestRow:
    request_row = session.scalar(
        select(RecordShareRequestRow).where(
            RecordShareRequestRow.id == request_id,
            RecordShareRequestRow.to_user_id == user_id,
        ),
    )
    if request_row is None:
        raise_not_found('Share request not found')
    return request_row


def _get_request_for_sender(session: Session, request_id: UUID, user_id: UUID) -> RecordShareRequestRow:
    request_row = session.scalar(
        select(RecordShareRequestRow).where(
            RecordShareRequestRow.id == request_id,
            RecordShareRequestRow.from_user_id == user_id,
        ),
    )
    if request_row is None:
        raise_not_found('Share request not found')
    return request_row


def _ensure_pending(request_row: RecordShareRequestRow) -> None:
    if request_row.status != RecordShareStatusRow.PENDING:
        raise_forbidden('Only pending share request can be changed')


def _get_request_shares(session: Session, request_id: UUID) -> list[RecordShareRow]:
    return list(
        session.scalars(
            select(RecordShareRow)
            .where(RecordShareRow.request_id == request_id)
            .order_by(RecordShareRow.created_at.asc()),
        ),
    )


def _to_request_response(session: Session, row: RecordShareRequestRow) -> ShareRequestResponseSchema:
    from_user = session.get(UserRow, row.from_user_id)
    to_user = session.get(UserRow, row.to_user_id)
    if from_user is None or to_user is None:
        raise RuntimeError('Share request references missing user')
    return ShareRequestResponseSchema(
        id=row.id,
        from_user=_to_user_response(from_user),
        to_user=_to_user_response(to_user),
        status=row.status.value,
        message=row.message,
        shares=tuple(_to_share_response(share_row) for share_row in _get_request_shares(session, row.id)),
        created_at=row.created_at,
        responded_at=row.responded_at,
        cancelled_at=row.cancelled_at,
        revoked_at=row.revoked_at,
    )


def _to_user_response(row: UserRow) -> ShareUserResponseSchema:
    return ShareUserResponseSchema(
        id=row.id,
        fio=row.fio,
        email=row.email,
        role=UserRole(row.role).value,
    )


def _to_share_response(row: RecordShareRow) -> RecordShareResponseSchema:
    return RecordShareResponseSchema(
        id=row.id,
        record_id=row.record_id,
        patient_passport_id=row.patient_passport_id,
        status=row.status.value,
        created_at=row.created_at,
        responded_at=row.responded_at,
        revoked_at=row.revoked_at,
    )
