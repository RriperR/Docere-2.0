"""REST управления AI-анализом импорта без передачи секретов клиенту."""

from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.import_jobs.ai import ImportAiUseCase
from app.domain.import_ai import AiRun, ImportAiError
from app.infrastructure.adapters.repositories.import_ai import SqlAlchemyImportAiRepository
from app.infrastructure.config.settings import get_settings
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)

router = APIRouter()


class StartAiSchema(BaseModel):
    """Явно выбранные документы и версия формы."""

    file_ids: list[str] = Field(min_length=1, max_length=100)
    idempotency_key: UUID
    version: int = Field(ge=1)


class AiDocumentSchema(BaseModel):
    """Проверенные предложения одного документа."""

    file_id: str
    path: str
    filename: str
    status: str
    page_count: int
    checksum: str | None
    result: dict[str, object]
    error_code: str | None
    usage: dict[str, int]


class AiRunSchema(BaseModel):
    """Состояние фонового анализа без авторизационного токена."""

    id: UUID
    job_id: UUID
    status: str
    model: str
    provider: str
    prompt_version: str
    created_at: str
    documents: list[AiDocumentSchema]


def get_ai_use_case(session: Session = db_session_dependency) -> ImportAiUseCase:
    """Создать application-сценарий с безопасной конфигурацией.

    Returns:
        Управление AI-запусками.
    """
    return ImportAiUseCase(SqlAlchemyImportAiRepository(session), get_settings().import_ai.options())


ai_use_case_dependency = Depends(get_ai_use_case)


@router.get('/ai-capabilities')
def ai_capabilities(current_user: AuthenticatedUserDTO = current_authenticated_user_dependency) -> dict[str, object]:
    """Описать доступность AI, не раскрывая адрес API и токен.

    Returns:
        Признак настройки и ограничения.

    Raises:
        HTTPException: Пользователь не может импортировать документы.
    """
    if current_user.role not in {'doctor', 'admin'}:
        raise HTTPException(403, 'Импорт недоступен')
    options = get_settings().import_ai.options()
    return {**asdict(options), 'formats': ['application/pdf', 'image/png', 'image/jpeg']}


@router.post('/imports/{job_id}/ai-runs', response_model=AiRunSchema, status_code=202)
def start_ai(
    job_id: UUID,
    payload: StartAiSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ImportAiUseCase = ai_use_case_dependency,
    session: Session = db_session_dependency,
) -> AiRun:
    """Создать доставляемый запуск выбранных документов.

    Returns:
        Новый запуск или идемпотентный повтор.

    Raises:
        HTTPException: Доступ, версия или выбор документов недопустимы.
    """
    try:
        result = use_case.start(
            job_id,
            current_user.id,
            current_user.role,
            tuple(payload.file_ids),
            payload.idempotency_key,
            payload.version,
        )
        session.commit()
        return result
    except ImportAiError as exc:
        session.rollback()
        raise HTTPException(exc.status, {'code': exc.code}) from exc


@router.get('/imports/{job_id}/ai-runs/{run_id}', response_model=AiRunSchema)
def get_ai(
    job_id: UUID,
    run_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ImportAiUseCase = ai_use_case_dependency,
) -> AiRun:
    """Получить результат после проверки действующего доступа.

    Returns:
        Предложения и прогресс.

    Raises:
        HTTPException: Запуск недоступен.
    """
    try:
        return use_case.repository.get(job_id, run_id, current_user.id, current_user.role)
    except ImportAiError as exc:
        raise HTTPException(exc.status, {'code': exc.code}) from exc


@router.post('/imports/{job_id}/ai-runs/{run_id}/cancel', response_model=AiRunSchema)
def cancel_ai(
    job_id: UUID,
    run_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ImportAiUseCase = ai_use_case_dependency,
    session: Session = db_session_dependency,
) -> AiRun:
    """Отменить оставшуюся обработку.

    Returns:
        Состояние запуска с сохранёнными завершёнными документами.

    Raises:
        HTTPException: Запуск недоступен.
    """
    try:
        result = use_case.repository.cancel(job_id, run_id, current_user.id, current_user.role)
        session.commit()
        return result
    except ImportAiError as exc:
        session.rollback()
        raise HTTPException(exc.status, {'code': exc.code}) from exc


@router.get('/imports/{job_id}/ai-runs', response_model=list[AiRunSchema])
def list_ai(
    job_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(5, ge=1, le=20),
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ImportAiUseCase = ai_use_case_dependency,
) -> tuple[AiRun, ...]:
    """Вернуть страницу предыдущих AI-запусков.

    Returns:
        Запуски с актуальной проверкой доступа.

    Raises:
        HTTPException: Импорт недоступен.
    """
    try:
        return use_case.repository.list_runs(job_id, current_user.id, current_user.role, offset, limit)
    except ImportAiError as exc:
        raise HTTPException(exc.status, {'code': exc.code}) from exc
