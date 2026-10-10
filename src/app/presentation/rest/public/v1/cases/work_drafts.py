"""HTTP-граница личных форм: автор определяется исключительно аутентификацией."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.clinical_cases.work_drafts import CaseWorkDraftsUseCase
from app.domain.case_drafts import CaseDraftContent, CaseWorkDraft, DraftKind
from app.presentation.rest.public.v1.cases.dependencies import case_transaction, drafts_dependency
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)

router = APIRouter()


class WorkDraftContentSchema(BaseModel):
    """Ограниченные поля формы и ссылки на выбранные материалы."""

    model_config = ConfigDict(from_attributes=True, extra='forbid')
    text: str = Field(default='', max_length=10000)
    findings: str = Field(default='', max_length=10000)
    next_actions: str = Field(default='', max_length=10000)
    record_ids: list[UUID] = Field(default_factory=list, max_length=100)
    parent_id: UUID | None = None
    opinion_id: UUID | None = None
    assignee_id: UUID | None = None
    attachment_id: UUID | None = None
    idempotency_key: UUID | None = None


class WorkDraftRequest(BaseModel):
    """Версия личной формы независима от версии общего случая."""

    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=0)
    content: WorkDraftContentSchema


class WorkDraftResponse(BaseModel):
    """Личный черновик не включается в общую выдачу случая."""

    model_config = ConfigDict(from_attributes=True)
    version: int
    content: WorkDraftContentSchema
    updated_at: datetime | None
    expires_at: datetime | None


@router.get('/{case_id}/work-drafts/{kind}', response_model=WorkDraftResponse)
def get_draft(
    case_id: UUID,
    kind: DraftKind,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseWorkDraftsUseCase = drafts_dependency,
    session: Session = db_session_dependency,
) -> CaseWorkDraft:
    """Прочитать личную форму после повторной проверки полного доступа.

    Args:
        case_id: Клинический случай.
        kind: Вид незавершённой формы.
        actor: Автор из аутентификации.
        uc: Прикладной сценарий личных форм.
        session: Текущая транзакция.

    Returns:
        Личная форма; чужой user_id в API отсутствует.
    """
    with case_transaction(session):
        return uc.get(case_id, actor.id, kind)


@router.put('/{case_id}/work-drafts/{kind}', response_model=WorkDraftResponse)
def save_draft(
    case_id: UUID,
    kind: DraftKind,
    payload: WorkDraftRequest,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseWorkDraftsUseCase = drafts_dependency,
    session: Session = db_session_dependency,
) -> CaseWorkDraft:
    """Сохранить форму с конфликтом версий вместо потери текста другой вкладки.

    Args:
        case_id: Клинический случай.
        kind: Вид незавершённой формы.
        payload: Версия и ограниченное содержимое формы.
        actor: Автор из аутентификации.
        uc: Прикладной сценарий личных форм.
        session: Текущая транзакция.

    Returns:
        Следующая версия личной формы со сроком хранения.
    """
    content = payload.content
    with case_transaction(session):
        return uc.save(
            case_id,
            actor.id,
            kind,
            payload.version,
            CaseDraftContent(
                content.text,
                content.findings,
                content.next_actions,
                tuple(content.record_ids),
                content.parent_id,
                content.opinion_id,
                content.assignee_id,
                content.attachment_id,
                content.idempotency_key,
            ),
        )
