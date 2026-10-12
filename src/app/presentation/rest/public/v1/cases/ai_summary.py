"""Защищённое API фоновой сводки явно выбранных материалов."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.clinical_cases.ai_summary import CaseSummaryUseCase
from app.domain.case_ai import CaseSummaryRun
from app.infrastructure.adapters.repositories.case_ai import SqlAlchemyCaseSummaryRepository
from app.infrastructure.config.settings import get_settings
from app.presentation.rest.public.v1.cases.dependencies import case_transaction, get_case_context
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)


def no_summary_cache(response: Response) -> None:
    """Запретить кэширование личных клинических результатов на HTTP-границе."""
    response.headers['Cache-Control'] = 'private, no-store'


router = APIRouter(dependencies=[Depends(no_summary_cache)])


class StartSummarySchema(BaseModel):
    """Выбор врача, версия и явное согласие на передачу документов."""

    model_config = ConfigDict(extra='forbid')
    record_ids: list[UUID] = Field(min_length=1, max_length=100)
    idempotency_key: UUID
    version: int = Field(ge=1)
    consent: bool


def get_summary_use_case(session: Session = db_session_dependency) -> CaseSummaryUseCase:
    """Собрать сценарий с общей политикой ACL случая.

    Returns:
        Прикладной сценарий личной сводки текущего врача.
    """
    return CaseSummaryUseCase(
        get_case_context(session), SqlAlchemyCaseSummaryRepository(session), get_settings().import_ai.options()
    )


summary_dependency = Depends(get_summary_use_case)


@router.post('/{case_id}/ai-summary/runs', status_code=202, response_model=CaseSummaryRun)
def start_summary(
    case_id: UUID,
    payload: StartSummarySchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseSummaryUseCase = summary_dependency,
    session: Session = db_session_dependency,
) -> CaseSummaryRun:
    """Запустить анализ только выбранных записей после согласия врача.

    Returns:
        Новый или идемпотентно повторённый запуск для опроса прогресса.
    """
    with case_transaction(session):
        return uc.start(
            case_id, actor.id, tuple(payload.record_ids), payload.idempotency_key, payload.version, payload.consent
        )


@router.get('/{case_id}/ai-summary', response_model=CaseSummaryRun | None)
def latest_summary(
    case_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseSummaryUseCase = summary_dependency,
    session: Session = db_session_dependency,
) -> CaseSummaryRun | None:
    """Восстановить последнюю собственную сводку после перезагрузки страницы.

    Returns:
        Последний запуск либо None; чужие результаты никогда не возвращаются.
    """
    with case_transaction(session):
        return uc.get(case_id, actor.id)


@router.get('/{case_id}/ai-summary/runs/{run_id}', response_model=CaseSummaryRun)
def get_summary(
    case_id: UUID,
    run_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseSummaryUseCase = summary_dependency,
    session: Session = db_session_dependency,
) -> CaseSummaryRun | None:
    """Перечитать состояние после проверки членства и всех материалов.

    Returns:
        Собственный запуск с источниками без секретов и ключей хранилища.
    """
    with case_transaction(session):
        return uc.get(case_id, actor.id, run_id)


@router.post('/{case_id}/ai-summary/runs/{run_id}/cancel', response_model=CaseSummaryRun)
def cancel_summary(
    case_id: UUID,
    run_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseSummaryUseCase = summary_dependency,
    session: Session = db_session_dependency,
) -> CaseSummaryRun:
    """Отменить оставшиеся документы; поздние ответы не меняют сохранённую сводку.

    Returns:
        Состояние после отмены собственного запуска.
    """
    with case_transaction(session):
        return uc.cancel(case_id, actor.id, run_id)
