"""SSE со снимками статуса импорта, heartbeat и повторной проверкой доступа."""

import asyncio
import json
from collections.abc import AsyncIterator
from time import monotonic
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError

from app.application.use_cases.auth.errors import InvalidTokenError, UserNotFoundError
from app.application.use_cases.import_jobs.errors import ImportJobNotFoundError
from app.application.use_cases.import_jobs.progress import GetImportProgressUseCase
from app.domain.entities.import_job import ImportJobProgress
from app.infrastructure.adapters.repositories.import_jobs.sqlalchemy_import_job_repository import (
    SqlAlchemyImportJobRepositoryAdapter,
)
from app.infrastructure.db.session import get_session_factory
from app.presentation.rest.public.v1.auth.dependencies import (
    bearer_token_extraction_dependency,
    get_authenticated_user_use_case,
)

router = APIRouter()
POLL_SECONDS = 2
HEARTBEAT_SECONDS = 10
CONNECTION_SECONDS = 60
cursor_header = Header(default=None, alias='Last-Event-ID')


def read_progress(token: str, job_id: UUID) -> ImportJobProgress:
    """Открыть короткую сессию; соединение БД не удерживается SSE-клиентом.

    Args:
        token: Access-токен подписчика.
        job_id: Идентификатор задания.

    Returns:
        Разрешённая текущему пользователю проекция.
    """
    with get_session_factory()() as session:
        return GetImportProgressUseCase(
            auth=get_authenticated_user_use_case(session=session),
            jobs=SqlAlchemyImportJobRepositoryAdapter(session),
        ).execute(token=token, job_id=job_id)


def encode_progress(progress: ImportJobProgress) -> str:
    """Закодировать снимок; event id стабилен между процессами API.

    Args:
        progress: Доступный подписчику снимок статуса.

    Returns:
        SSE-кадр без содержимого медицинского архива.
    """
    data = json.dumps({'id': str(progress.id), 'status': progress.status.value, 'version': progress.version})
    return f'id: {progress.version}\nevent: status\ndata: {data}\n\n'


async def progress_events(
    request: Request,
    token: str,
    job_id: UUID,
    initial: ImportJobProgress,
    cursor: int,
) -> AsyncIterator[str]:
    """Выдать последний снимок и изменения; пропущенные промежуточные статусы объединяются.

    Args:
        request: HTTP-запрос для определения отключения клиента.
        token: Токен для повторной проверки доступа.
        job_id: Идентификатор задания.
        initial: Снимок, проверенный перед открытием потока.
        cursor: Последняя версия, полученная клиентом.

    Yields:
        SSE-кадры, heartbeat и сообщения о необходимости переподключения.
    """
    started = heartbeat = monotonic()
    progress = initial
    while not await request.is_disconnected():
        if progress.version != cursor:
            yield encode_progress(progress)
            cursor = progress.version
        if progress.processing_finished:
            yield 'event: done\ndata: {}\n\n'
            return
        now = monotonic()
        if now - started >= CONNECTION_SECONDS:
            return  # Обновление токена, балансировка и bounded lifetime соединения.
        if now - heartbeat >= HEARTBEAT_SECONDS:
            yield ': heartbeat\n\n'
            heartbeat = now
        await asyncio.sleep(POLL_SECONDS)
        try:
            progress = await asyncio.to_thread(read_progress, token, job_id)
        except (InvalidTokenError, UserNotFoundError):
            yield 'event: auth-expired\ndata: {}\n\n'
            return
        except ImportJobNotFoundError:
            yield 'event: access-revoked\ndata: {}\n\n'
            return
        except SQLAlchemyError:
            yield 'event: retry\ndata: {}\n\n'
            return


@router.get('/imports/{job_id}/events')
async def import_job_events(
    request: Request,
    job_id: UUID,
    token: str = bearer_token_extraction_dependency,
    last_event_id: str | None = cursor_header,
) -> StreamingResponse:
    """Подписаться на статус с Bearer-авторизацией и восстановлением по версии.

    Args:
        request: Входящий HTTP-запрос.
        job_id: Идентификатор задания.
        token: Access-токен из заголовка Authorization.
        last_event_id: Последняя версия, полученная клиентом.

    Returns:
        SSE-поток снимков статуса.

    Raises:
        HTTPException: Неверный курсор, недействительный токен или недоступное задание.
    """
    if last_event_id is not None and (
        not last_event_id.isascii() or not last_event_id.isdigit() or len(last_event_id) > 19
    ):
        raise HTTPException(status_code=400, detail='Invalid Last-Event-ID')
    try:
        initial = await asyncio.to_thread(read_progress, token, job_id)
    except (InvalidTokenError, UserNotFoundError) as exc:
        raise HTTPException(status_code=401, detail='Invalid or expired token') from exc
    except ImportJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail='Import job not found') from exc
    return StreamingResponse(
        progress_events(request, token, job_id, initial, int(last_event_id or 0)),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache, no-store', 'X-Accel-Buffering': 'no'},
    )
