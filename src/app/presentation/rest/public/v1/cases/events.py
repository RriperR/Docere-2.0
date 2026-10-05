"""Авторизованные SSE метаданных случаев и уведомлений с повторной проверкой ACL."""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from time import monotonic
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError

from app.application.use_cases.auth.errors import InvalidTokenError, UserNotFoundError
from app.domain.clinical_cases import CaseError
from app.infrastructure.db.session import get_session_factory
from app.presentation.rest.public.v1.auth.dependencies import (
    bearer_token_extraction_dependency,
    get_authenticated_user_use_case,
)
from app.presentation.rest.public.v1.cases.dependencies import get_case_context
from app.presentation.rest.public.v1.notifications.dependencies import get_notifications_use_case

router = APIRouter()
POLL_SECONDS = 2
HEARTBEAT_SECONDS = 10
CONNECTION_SECONDS = 60
cursor_header = Header(default=None, alias='Last-Event-ID')


def read_snapshot(token: str, case_id: UUID | None) -> tuple[str, dict[str, object]]:
    """Прочитать снимок в короткой сессии; медицинский текст не попадает в поток.

    Args:
        token: JWT из Bearer-заголовка, проверяемый при каждом чтении.
        case_id: Идентификатор клинического случая.

    Returns:
        Курсор версии и метаданные объекта без клинического содержимого.
    """
    with get_session_factory()() as session:
        actor = get_authenticated_user_use_case(session=session).execute(token=token)
        if case_id:
            uc = get_case_context(session=session)
            case = uc.load(case_id, actor.id)
            uc.require_context(case, actor.id)
            return str(case.sequence), {'id': str(case.id), 'version': case.version, 'sequence': case.sequence}
        snapshot = get_notifications_use_case(session=session).count(actor.id)
        return snapshot.version, {'id': str(actor.id), 'version': snapshot.version}


async def changes(
    request: Request, token: str, case_id: UUID | None, cursor: str, initial: tuple[str, dict[str, object]]
) -> AsyncIterator[str]:
    """Посылать изменения, heartbeat и безопасный сигнал утраты доступа.

    Args:
        request: HTTP-запрос для проверки разрыва SSE-соединения.
        token: JWT из Bearer-заголовка, проверяемый при каждом чтении.
        case_id: Идентификатор клинического случая.
        cursor: Последняя версия, успешно полученная клиентом.
        initial: Снимок метаданных, проверенный перед отправкой HTTP 200.

    Yields:
        Метаданные SSE, heartbeat или безопасный сигнал завершения соединения.
    """
    started = heartbeat = monotonic()
    snapshot = initial
    while not await request.is_disconnected():
        version, data = snapshot
        if version != cursor:
            yield f'id: {version}\nevent: changed\ndata: {json.dumps(data)}\n\n'
            cursor = version
        now = monotonic()
        if now - started >= CONNECTION_SECONDS:
            return
        if now - heartbeat >= HEARTBEAT_SECONDS:
            yield ': heartbeat\n\n'
            heartbeat = now
        await asyncio.sleep(POLL_SECONDS)
        try:
            snapshot = await asyncio.to_thread(read_snapshot, token, case_id)
        except (InvalidTokenError, UserNotFoundError):
            yield 'event: auth-expired\ndata: {}\n\n'
            return
        except CaseError:
            yield 'event: access-revoked\ndata: {}\n\n'
            return
        except SQLAlchemyError:
            yield 'event: retry\ndata: {}\n\n'
            return


async def subscribe(request: Request, token: str, case_id: UUID | None, last_event_id: str | None) -> StreamingResponse:
    """Проверить авторизацию до отправки HTTP 200 и восстановить последнюю версию.

    Args:
        request: HTTP-запрос для проверки разрыва SSE-соединения.
        token: JWT из Bearer-заголовка, проверяемый при каждом чтении.
        case_id: Идентификатор клинического случая.
        last_event_id: Курсор предыдущего соединения из заголовка Last-Event-ID.

    Returns:
        SSE-ответ с проверенной начальной авторизацией и ограниченным временем соединения.

    Raises:
        HTTPException: Если доступ запрещён, ссылка недействительна или возник конфликт изменения.
    """
    if last_event_id is not None and (
        len(last_event_id) > 40 or not re.fullmatch(r'[0-9]+(?:-[0-9]+){0,2}', last_event_id)
    ):
        raise HTTPException(400, 'Некорректный Last-Event-ID')
    try:
        initial = await asyncio.to_thread(read_snapshot, token, case_id)
    except (InvalidTokenError, UserNotFoundError) as exc:
        raise HTTPException(401, 'Недействительный токен') from exc
    except CaseError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    return StreamingResponse(
        changes(request, token, case_id, last_event_id or '', initial),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache, no-store', 'X-Accel-Buffering': 'no'},
    )


@router.get('/cases/{case_id}/events')
async def case_events(
    request: Request,
    case_id: UUID,
    token: str = bearer_token_extraction_dependency,
    last_event_id: str | None = cursor_header,
) -> StreamingResponse:
    """Подписаться с Bearer-заголовком; JWT в URL не принимается.

    Args:
        request: HTTP-запрос для проверки разрыва SSE-соединения.
        case_id: Идентификатор клинического случая.
        token: JWT из Bearer-заголовка, проверяемый при каждом чтении.
        last_event_id: Курсор предыдущего соединения из заголовка Last-Event-ID.

    Returns:
        SSE метаданных случая с повторной проверкой доступа.
    """
    return await subscribe(request, token, case_id, last_event_id)


@router.get('/notifications/events')
async def notification_events(
    request: Request, token: str = bearer_token_extraction_dependency, last_event_id: str | None = cursor_header
) -> StreamingResponse:
    """Получать только идентификатор адресата и версию его уведомлений.

    Args:
        request: HTTP-запрос для проверки разрыва SSE-соединения.
        token: JWT из Bearer-заголовка, проверяемый при каждом чтении.
        last_event_id: Курсор предыдущего соединения из заголовка Last-Event-ID.

    Returns:
        SSE версии собственных входящих без медицинского текста.
    """
    return await subscribe(request, token, None, last_event_id)
