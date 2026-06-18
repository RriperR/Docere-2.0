"""REST-роуты sharing выбранных медицинских записей."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.application.ports.repositories.share_requests.dtos import (
    CreateShareRequestResultDTO,
    ShareRequestDTO,
)
from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.share_requests.errors import (
    SharedRecordNotFoundError,
    ShareRequestAccessDeniedError,
    ShareRequestNotFoundError,
    ShareTargetNotFoundError,
)
from app.application.use_cases.share_requests.use_cases import (
    AcceptShareRequestUseCase,
    CancelShareRequestUseCase,
    CreateShareRequestUseCase,
    DeclineShareRequestUseCase,
    ListInboxShareRequestsUseCase,
    ListOutboxShareRequestsUseCase,
    RevokeShareRequestUseCase,
)
from app.infrastructure.adapters.repositories.audit_events import AuditEventRepositoryAdapter
from app.infrastructure.db.models.auth.user import UserRow, UserStatus
from app.presentation.rest.public.v1.records.dependencies import (
    accept_share_request_use_case_dependency,
    cancel_share_request_use_case_dependency,
    create_share_request_use_case_dependency,
    current_authenticated_user_dependency,
    db_session_dependency,
    decline_share_request_use_case_dependency,
    list_inbox_share_requests_use_case_dependency,
    list_outbox_share_requests_use_case_dependency,
    revoke_share_request_use_case_dependency,
)
from app.presentation.rest.public.v1.share_requests.schemas import (
    CreateShareRequestResponseSchema,
    CreateShareRequestSchema,
    ShareRecipientResponseSchema,
    ShareRequestResponseSchema,
)
from app.presentation.webserver.http_errors import raise_forbidden, raise_not_found

router = APIRouter(prefix='/share-requests', tags=['share-requests'])


@router.post('', response_model=CreateShareRequestResponseSchema, status_code=status.HTTP_201_CREATED)
def create_share_request(
    payload: CreateShareRequestSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: CreateShareRequestUseCase = create_share_request_use_case_dependency,
    session: Session = db_session_dependency,
) -> CreateShareRequestResultDTO:
    """Создать запрос на sharing выбранных медицинских записей.

    Returns:
        Созданный sharing request и список записей, пропущенных как дубли.
    """
    try:
        result = use_case.execute(
            from_user_id=current_user.id,
            to_user_email=str(payload.to_user_email),
            record_ids=tuple(payload.record_ids),
            message=payload.message,
        )
        if result.request is not None:
            AuditEventRepositoryAdapter(session).record(
                actor_user_id=current_user.id,
                event_type='share',
                entity_type='record_share_request',
                entity_id=result.request.id,
                metadata_json={'record_ids': [str(record_id) for record_id in payload.record_ids]},
            )
        session.commit()
        return result
    except ShareTargetNotFoundError:
        session.rollback()
        raise_not_found('Target user not found')
    except SharedRecordNotFoundError:
        session.rollback()
        raise_not_found('Medical record not found')
    except ShareRequestAccessDeniedError:
        session.rollback()
        raise_forbidden('You do not have access to one or more records')
    except Exception:
        session.rollback()
        raise


@router.get('/inbox', response_model=list[ShareRequestResponseSchema])
def list_inbox_share_requests(
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ListInboxShareRequestsUseCase = list_inbox_share_requests_use_case_dependency,
) -> tuple[ShareRequestDTO, ...]:
    """Вернуть входящие sharing-запросы текущего пользователя.

    Returns:
        Список входящих sharing-запросов.
    """
    return use_case.execute(user_id=current_user.id)


@router.get('/outbox', response_model=list[ShareRequestResponseSchema])
def list_outbox_share_requests(
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ListOutboxShareRequestsUseCase = list_outbox_share_requests_use_case_dependency,
) -> tuple[ShareRequestDTO, ...]:
    """Вернуть исходящие sharing-запросы текущего пользователя.

    Returns:
        Список исходящих sharing-запросов.
    """
    return use_case.execute(user_id=current_user.id)


@router.get('/recipients', response_model=list[ShareRecipientResponseSchema])
def search_share_recipients(
    q: str = Query(min_length=1, max_length=255),
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    session: Session = db_session_dependency,
) -> list[UserRow]:
    """Найти пользователей-кандидатов для sharing по ФИО или email.

    Returns:
        Список активных пользователей без текущего пользователя.
    """
    query = f'%{q.strip().lower()}%'
    return list(
        session.scalars(
            select(UserRow)
            .where(
                UserRow.id != current_user.id,
                UserRow.status == UserStatus.ACTIVE,
                or_(UserRow.email.ilike(query), UserRow.fio.ilike(query)),
            )
            .order_by(UserRow.fio.asc())
            .limit(10),
        ),
    )


@router.post('/{request_id}/accept', response_model=ShareRequestResponseSchema)
def accept_share_request(
    request_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: AcceptShareRequestUseCase = accept_share_request_use_case_dependency,
    session: Session = db_session_dependency,
) -> ShareRequestDTO:
    """Принять pending sharing-запрос и выдать фактический доступ.

    Returns:
        Обновленный sharing request.
    """
    try:
        request = use_case.execute(request_id=request_id, user_id=current_user.id)
        AuditEventRepositoryAdapter(session).record(
            actor_user_id=current_user.id,
            event_type='accept',
            entity_type='record_share_request',
            entity_id=request.id,
        )
        session.commit()
        return request
    except ShareRequestNotFoundError:
        session.rollback()
        raise_not_found('Share request not found')
    except ShareRequestAccessDeniedError:
        session.rollback()
        raise_forbidden('Only pending share request can be changed')
    except Exception:
        session.rollback()
        raise


@router.post('/{request_id}/decline', response_model=ShareRequestResponseSchema)
def decline_share_request(
    request_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: DeclineShareRequestUseCase = decline_share_request_use_case_dependency,
    session: Session = db_session_dependency,
) -> ShareRequestDTO:
    """Отклонить pending sharing-запрос.

    Returns:
        Обновленный sharing request.
    """
    try:
        request = use_case.execute(request_id=request_id, user_id=current_user.id)
        AuditEventRepositoryAdapter(session).record(
            actor_user_id=current_user.id,
            event_type='decline',
            entity_type='record_share_request',
            entity_id=request.id,
        )
        session.commit()
        return request
    except ShareRequestNotFoundError:
        session.rollback()
        raise_not_found('Share request not found')
    except ShareRequestAccessDeniedError:
        session.rollback()
        raise_forbidden('Only pending share request can be changed')
    except Exception:
        session.rollback()
        raise


@router.post('/{request_id}/cancel', response_model=ShareRequestResponseSchema)
def cancel_share_request(
    request_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: CancelShareRequestUseCase = cancel_share_request_use_case_dependency,
    session: Session = db_session_dependency,
) -> ShareRequestDTO:
    """Отменить pending sharing-запрос инициатором.

    Returns:
        Обновленный sharing request.
    """
    try:
        request = use_case.execute(request_id=request_id, user_id=current_user.id)
        AuditEventRepositoryAdapter(session).record(
            actor_user_id=current_user.id,
            event_type='cancel',
            entity_type='record_share_request',
            entity_id=request.id,
        )
        session.commit()
        return request
    except ShareRequestNotFoundError:
        session.rollback()
        raise_not_found('Share request not found')
    except ShareRequestAccessDeniedError:
        session.rollback()
        raise_forbidden('Only pending share request can be changed')
    except Exception:
        session.rollback()
        raise


@router.post('/{request_id}/revoke', response_model=ShareRequestResponseSchema)
def revoke_share_request(
    request_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: RevokeShareRequestUseCase = revoke_share_request_use_case_dependency,
    session: Session = db_session_dependency,
) -> ShareRequestDTO:
    """Отозвать ранее принятый sharing-запрос инициатором.

    Returns:
        Обновленный sharing request.
    """
    try:
        request = use_case.execute(request_id=request_id, user_id=current_user.id)
        AuditEventRepositoryAdapter(session).record(
            actor_user_id=current_user.id,
            event_type='revoke',
            entity_type='record_share_request',
            entity_id=request.id,
        )
        session.commit()
        return request
    except ShareRequestNotFoundError:
        session.rollback()
        raise_not_found('Share request not found')
    except ShareRequestAccessDeniedError:
        session.rollback()
        raise_forbidden('Only accepted share request can be revoked')
    except Exception:
        session.rollback()
        raise
