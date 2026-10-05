"""Защищённое HTTP API совместных клинических разборов."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.clinical_cases import CaseView, ClinicalCasesUseCase
from app.presentation.rest.public.v1.cases.dependencies import case_transaction, cases_dependency
from app.presentation.rest.public.v1.cases.schemas import CaseCreateSchema, DraftSchema, InviteSchema, MaterialsSchema
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)

router = APIRouter(prefix='/cases', tags=['clinical-cases'])
offset_query = Query(default=0, ge=0)
limit_query = Query(default=20, ge=1, le=100)
search_query = Query(min_length=2, max_length=100)


@router.get('')
def list_cases(
    scope: Literal['all', 'coordinator', 'participating'] = 'all',
    status: Literal['draft', 'active', 'closed'] | None = None,
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> dict[str, object]:
    """Получить страницу безопасных карточек.

    Returns:
        Результат операции в контексте доступа текущего пользователя.
    """
    with case_transaction(session):
        return uc.list_cases(actor.id, scope=scope, status=status, offset=offset, limit=limit)


@router.get('/doctors')
def search_doctors(
    query: str = search_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> list[dict[str, str]]:
    """Найти зарегистрированных активных врачей для приглашения.

    Returns:
        Результат операции в контексте доступа текущего пользователя.
    """
    with case_transaction(session):
        uc.require_doctor(actor.id)
        return uc.repository.search_doctors(actor.id, query)


@router.get('/patients/{patient_id}/available-records')
def available_records(
    patient_id: UUID,
    query: str = '',
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> dict[str, object]:
    """Выбрать страницу собственных доступных записей для нового разбора.

    Returns:
        Результат операции в контексте доступа текущего пользователя.
    """
    with case_transaction(session):
        uc.require_doctor(actor.id)
        return uc.repository.available_materials(patient_id, actor.id, query, offset, limit)


@router.post('', status_code=201)
def create_case(
    payload: CaseCreateSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Создать черновик выбранного пациента.

    Returns:
        Результат операции в контексте доступа текущего пользователя.
    """
    with case_transaction(session):
        return uc.create(
            actor.id, payload.patient_id, payload.title, payload.question, payload.record_ids, payload.previous_case_id
        )


@router.get('/{case_id}')
def get_case(
    case_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Получить клиническое пространство или нейтральную карточку приглашения.

    Returns:
        Результат операции в контексте доступа текущего пользователя.
    """
    with case_transaction(session):
        return uc.view(uc.load(case_id, actor.id), actor.id)


@router.patch('/{case_id}')
def update_draft(
    case_id: UUID,
    payload: DraftSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Изменить черновик с проверкой версии.

    Returns:
        Результат операции в контексте доступа текущего пользователя.
    """
    with case_transaction(session):
        return uc.update_draft(case_id, actor.id, payload.version, payload.title, payload.question, payload.record_ids)


@router.post('/{case_id}/materials')
def add_materials(
    case_id: UUID,
    payload: MaterialsSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Добавить материал с атомарной выдачей прав всем действующим участникам.

    Returns:
        Результат операции в контексте доступа текущего пользователя.
    """
    with case_transaction(session):
        return uc.add_materials(case_id, actor.id, payload.version, payload.record_ids)


@router.post('/{case_id}/invitations')
def invite(
    case_id: UUID,
    payload: InviteSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Пригласить врача без раскрытия медицинских сведений.

    Returns:
        Результат операции в контексте доступа текущего пользователя.
    """
    with case_transaction(session):
        return uc.invite(case_id, actor.id, payload.user_id, payload.version)


@router.post('/{case_id}/invitations/{action}')
def respond(
    case_id: UUID,
    action: Literal['accept', 'decline'],
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Ответить на приглашение; повторное принятие не создаёт дополнительных прав.

    Returns:
        Результат операции в контексте доступа текущего пользователя.
    """
    with case_transaction(session):
        return uc.membership(case_id, actor.id, action)


@router.post('/{case_id}/members/{user_id}/{action}')
def manage_member(
    case_id: UUID,
    user_id: UUID,
    action: Literal['cancel', 'remove'],
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Отменить приглашение или исключить участника с каскадным отзывом прав.

    Returns:
        Результат операции в контексте доступа текущего пользователя.
    """
    with case_transaction(session):
        return uc.membership(case_id, actor.id, action, user_id)


@router.post('/{case_id}/leave')
def leave(
    case_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Выйти из случая, сохранив независимые права на записи.

    Returns:
        Результат операции в контексте доступа текущего пользователя.
    """
    with case_transaction(session):
        return uc.membership(case_id, actor.id, 'leave')
