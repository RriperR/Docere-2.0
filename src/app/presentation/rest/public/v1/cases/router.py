"""Защищённое HTTP API совместных клинических разборов."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.clinical_cases.dtos import (
    CaseView,
    DoctorSummary,
    PageDTO,
)
from app.application.use_cases.clinical_cases.management import ClinicalCasesUseCase
from app.presentation.rest.public.v1.cases.ai_summary import router as ai_summary_router
from app.presentation.rest.public.v1.cases.conclusions import router as conclusions_router
from app.presentation.rest.public.v1.cases.dependencies import case_transaction, cases_dependency
from app.presentation.rest.public.v1.cases.discussion import router as discussion_router
from app.presentation.rest.public.v1.cases.materials import router as materials_router
from app.presentation.rest.public.v1.cases.responses import (
    CaseViewResponse,
    DoctorResponse,
    PageResponse,
)
from app.presentation.rest.public.v1.cases.schemas import (
    CaseCreateSchema,
    DraftSchema,
    InviteSchema,
    MaterialsSchema,
)
from app.presentation.rest.public.v1.cases.work_drafts import router as work_drafts_router
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)

router = APIRouter(prefix='/cases', tags=['clinical-cases'])
offset_query = Query(default=0, ge=0)
limit_query = Query(default=20, ge=1, le=100)
search_query = Query(min_length=2, max_length=100)


@router.get('', response_model=PageResponse[CaseViewResponse])
def list_cases(
    scope: Literal['all', 'coordinator', 'participating'] = 'all',
    status: Literal['draft', 'active', 'closed'] | None = None,
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> PageDTO[CaseView]:
    """Получить страницу безопасных карточек.

    Args:
        scope: Отбор всех случаев, координируемых или с участием пользователя.
        status: Состояние случая для фильтрации.
        offset: Число элементов, пропускаемых перед страницей.
        limit: Максимальное число элементов страницы.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Страница безопасных карточек, проверенных для текущего пользователя.
    """
    with case_transaction(session):
        return uc.list_cases(actor.id, scope=scope, status=status, offset=offset, limit=limit)


@router.get('/doctors', response_model=list[DoctorResponse])
def search_doctors(
    query: str = search_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> list[DoctorSummary]:
    """Найти зарегистрированных активных врачей для приглашения.

    Args:
        query: Текст для поиска по разрешённым полям.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Список активных врачей, соответствующих имени или email, кроме самого пользователя.
    """
    with case_transaction(session):
        return uc.search_doctors(actor.id, query)


@router.post('', status_code=201, response_model=CaseViewResponse)
def create_case(
    payload: CaseCreateSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Создать черновик выбранного пациента.

    Args:
        payload: Проверенное тело HTTP-запроса.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.
    """
    with case_transaction(session):
        return uc.create(
            actor.id, payload.patient_id, payload.title, payload.question, payload.record_ids, payload.previous_case_id
        )


@router.get('/{case_id}', response_model=CaseViewResponse)
def get_case(
    case_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Получить клиническое пространство или нейтральную карточку приглашения.

    Args:
        case_id: Идентификатор клинического случая.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Полная карточка либо нейтральное приглашение при отсутствии доступа к контексту.
    """
    with case_transaction(session):
        return uc.context.view(uc.context.load(case_id, actor.id), actor.id)


@router.patch('/{case_id}', response_model=CaseViewResponse)
def update_draft(
    case_id: UUID,
    payload: DraftSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Изменить черновик с проверкой версии.

    Args:
        case_id: Идентификатор клинического случая.
        payload: Проверенное тело HTTP-запроса.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.
    """
    with case_transaction(session):
        return uc.update_draft(case_id, actor.id, payload.version, payload.title, payload.question, payload.record_ids)


@router.post('/{case_id}/materials', response_model=CaseViewResponse)
def add_materials(
    case_id: UUID,
    payload: MaterialsSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Добавить материал с атомарной выдачей прав всем действующим участникам.

    Args:
        case_id: Идентификатор клинического случая.
        payload: Проверенное тело HTTP-запроса.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.
    """
    with case_transaction(session):
        return uc.add_materials(case_id, actor.id, payload.version, payload.record_ids)


@router.post('/{case_id}/invitations', response_model=CaseViewResponse)
def invite(
    case_id: UUID,
    payload: InviteSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Пригласить врача без раскрытия медицинских сведений.

    Args:
        case_id: Идентификатор клинического случая.
        payload: Проверенное тело HTTP-запроса.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.
    """
    with case_transaction(session):
        return uc.invite(case_id, actor.id, payload.user_id, payload.version)


@router.post('/{case_id}/invitations/{action}', response_model=CaseViewResponse)
def respond(
    case_id: UUID,
    action: Literal['accept', 'decline'],
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Ответить на приглашение; повторное принятие не создаёт дополнительных прав.

    Args:
        case_id: Идентификатор клинического случая.
        action: Действие с приглашением или членством.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.
    """
    with case_transaction(session):
        return uc.membership(case_id, actor.id, action)


@router.post('/{case_id}/members/{user_id}/{action}', response_model=CaseViewResponse)
def manage_member(
    case_id: UUID,
    user_id: UUID,
    action: Literal['cancel', 'remove'],
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Отменить приглашение или исключить участника с каскадным отзывом прав.

    Args:
        case_id: Идентификатор клинического случая.
        user_id: Врач, приглашение или участие которого изменяет координатор.
        action: Действие с приглашением или членством.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.
    """
    with case_transaction(session):
        return uc.membership(case_id, actor.id, action, user_id)


@router.post('/{case_id}/leave', response_model=CaseViewResponse)
def leave(
    case_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Выйти из случая, сохранив независимые права на записи.

    Args:
        case_id: Идентификатор клинического случая.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.
    """
    with case_transaction(session):
        return uc.membership(case_id, actor.id, 'leave')


router.include_router(ai_summary_router)
router.include_router(work_drafts_router)
router.include_router(materials_router)
router.include_router(discussion_router)
router.include_router(conclusions_router)
