"""Защищённое HTTP API совместных клинических разборов."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.clinical_cases import CaseView, ClinicalCasesUseCase
from app.application.use_cases.medical_records.create_medical_record.use_case import CreateMedicalRecordUseCase
from app.domain.clinical_cases import CaseConclusion, CaseMessage, OpinionRequest
from app.presentation.rest.public.v1.cases.dependencies import case_transaction, cases_dependency
from app.presentation.rest.public.v1.cases.materials import router as materials_router
from app.presentation.rest.public.v1.cases.schemas import (
    CaseCreateSchema,
    CloseSchema,
    ConclusionSchema,
    DiscussionReadSchema,
    DraftSchema,
    InviteSchema,
    MaterialsSchema,
    MessageSchema,
    OpinionSchema,
    PublishSchema,
)
from app.presentation.rest.public.v1.records.dependencies import (
    create_medical_record_use_case_dependency,
    current_authenticated_user_dependency,
    db_session_dependency,
)

router = APIRouter(prefix='/cases', tags=['clinical-cases'])
offset_query = Query(default=0, ge=0)
limit_query = Query(default=20, ge=1, le=100)
search_query = Query(min_length=2, max_length=100)
optional_query = Query(default='', max_length=200)


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

    Args:
        scope: Параметр операции.
        status: Параметр операции.
        offset: Число пропускаемых элементов.
        limit: Размер страницы.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.
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

    Args:
        query: Поисковая строка.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.
    """
    with case_transaction(session):
        uc.require_doctor(actor.id)
        return uc.repository.search_doctors(actor.id, query)


@router.get('/patients/{patient_id}/available-records')
def available_records(
    patient_id: UUID,
    query: str = optional_query,
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> dict[str, object]:
    """Выбрать страницу собственных доступных записей для нового разбора.

    Returns:
        Результат операции в контексте доступа текущего пользователя.

    Args:
        patient_id: Параметр операции.
        query: Поисковая строка.
        offset: Число пропускаемых элементов.
        limit: Размер страницы.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.
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

    Args:
        payload: Проверенный HTTP payload.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.
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

    Args:
        case_id: Идентификатор случая.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.
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

    Args:
        case_id: Идентификатор случая.
        payload: Проверенный HTTP payload.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.
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

    Args:
        case_id: Идентификатор случая.
        payload: Проверенный HTTP payload.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.
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

    Args:
        case_id: Идентификатор случая.
        payload: Проверенный HTTP payload.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.
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

    Args:
        case_id: Идентификатор случая.
        action: Параметр операции.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.
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

    Args:
        case_id: Идентификатор случая.
        user_id: Текущий пользователь.
        action: Параметр операции.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.
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

    Args:
        case_id: Идентификатор случая.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.
    """
    with case_transaction(session):
        return uc.membership(case_id, actor.id, 'leave')


@router.get('/{case_id}/messages')
def get_messages(
    case_id: UUID,
    query: str = optional_query,
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> dict[str, object]:
    """Прочитать страницу защищённого обсуждения.

    Args:
        case_id: Идентификатор случая.
        query: Поисковая строка.
        offset: Число пропускаемых элементов.
        limit: Размер страницы.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.discussion(case_id, actor.id, offset, limit, query)


@router.post('/{case_id}/messages', status_code=201)
def send_message(
    case_id: UUID,
    payload: MessageSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseMessage:
    """Отправить реплику или ответ адресному запросу идемпотентно.

    Args:
        case_id: Идентификатор случая.
        payload: Проверенный HTTP payload.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.send_message(
            case_id,
            actor.id,
            payload.body,
            payload.idempotency_key,
            payload.parent_id,
            payload.record_id,
            payload.attachment_id,
            payload.opinion_id,
        )


@router.get('/{case_id}/opinions')
def get_opinions(
    case_id: UUID,
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> dict[str, object]:
    """Прочитать страницу адресных запросов.

    Args:
        case_id: Идентификатор случая.
        offset: Число пропускаемых элементов.
        limit: Размер страницы.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.list_opinions(case_id, actor.id, offset, limit)


@router.post('/{case_id}/opinions', status_code=201)
def request_opinion(
    case_id: UUID,
    payload: OpinionSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> OpinionRequest:
    """Запросить мнение другого участника.

    Args:
        case_id: Идентификатор случая.
        payload: Проверенный HTTP payload.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.request_opinion(case_id, actor.id, payload.assignee_id, payload.question, payload.record_id)


@router.post('/{case_id}/opinions/{opinion_id}/cancel')
def cancel_opinion(
    case_id: UUID,
    opinion_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> OpinionRequest:
    """Отменить запрос автором или координатором.

    Args:
        case_id: Идентификатор случая.
        opinion_id: Адресный запрос.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.cancel_opinion(case_id, actor.id, opinion_id)


@router.get('/{case_id}/activity')
def get_activity(
    case_id: UUID,
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> dict[str, object]:
    """Прочитать страницу журнала действий.

    Args:
        case_id: Идентификатор случая.
        offset: Число пропускаемых элементов.
        limit: Размер страницы.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.activity(case_id, actor.id, offset, limit)


@router.get('/{case_id}/conclusions')
def conclusions(
    case_id: UUID,
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> dict[str, object]:
    """Получить версии итога с пагинацией.

    Args:
        case_id: Идентификатор случая.
        offset: Число пропускаемых элементов.
        limit: Размер страницы.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.list_conclusions(case_id, actor.id, offset, limit)


@router.post('/{case_id}/conclusions', status_code=201)
def save_conclusion(
    case_id: UUID,
    payload: ConclusionSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseConclusion:
    """Сохранить новую неизменяемую версию итога.

    Args:
        case_id: Идентификатор случая.
        payload: Проверенный HTTP payload.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.save_conclusion(
            case_id,
            actor.id,
            payload.version,
            payload.summary,
            payload.findings,
            payload.next_actions,
            payload.source_ids,
        )


@router.get('/{case_id}/closure-preview')
def closure_preview(
    case_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> dict[str, object]:
    """Проверить открытые запросы перед завершением.

    Args:
        case_id: Идентификатор случая.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.closure_preview(case_id, actor.id)


@router.post('/{case_id}/close')
def close_case(
    case_id: UUID,
    payload: CloseSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Завершить разбор, сохранив участникам доступ для чтения.

    Args:
        case_id: Идентификатор случая.
        payload: Проверенный HTTP payload.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.close(case_id, actor.id, payload.version, payload.cancel_open_requests)


@router.get('/{case_id}/publication-preview')
def publication_preview(
    case_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> dict[str, object]:
    """Показать предпросмотр самостоятельной медицинской записи.

    Args:
        case_id: Идентификатор случая.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.publication_preview(case_id, actor.id)


@router.post('/{case_id}/publish')
def publish(
    case_id: UUID,
    payload: PublishSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
    creator: CreateMedicalRecordUseCase = create_medical_record_use_case_dependency,
) -> dict[str, object]:
    """Опубликовать итог с датой события через существующий сценарий записи.

    Args:
        case_id: Идентификатор случая.
        payload: Проверенный HTTP payload.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.
        creator: Параметр операции.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.publish(case_id, actor, payload.event_date, creator)


router.include_router(materials_router)


@router.post('/{case_id}/discussion/read')
def mark_read(
    case_id: UUID,
    payload: DiscussionReadSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> dict[str, bool]:
    """Отметить просмотренную позицию обсуждения монотонно.

    Args:
        case_id: Идентификатор случая.
        payload: Проверенный HTTP payload.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        uc.mark_read(case_id, actor.id, payload.sequence)
        return {'read': True}
