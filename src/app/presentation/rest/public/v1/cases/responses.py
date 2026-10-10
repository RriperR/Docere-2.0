"""Публичные схемы ответов клинических случаев, независимые от ORM."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResponseSchema(BaseModel):
    """Читать поля прикладного DTO, проверяя выходной HTTP-контракт."""

    model_config = ConfigDict(from_attributes=True)


class PageResponse[T](ResponseSchema):
    """Пагинированная коллекция с общим числом элементов."""

    items: list[T]
    total: int


class CaseMemberResponse(ResponseSchema):
    """Приглашение или участие врача в выбранном случае."""

    user_id: UUID
    status: str
    name: str
    share_request_id: UUID | None
    read_sequence: int


class ClinicalCaseResponse(ResponseSchema):
    """Клинический контекст, разрешённый только при доступе ко всем материалам."""

    id: UUID
    patient_id: UUID
    coordinator_id: UUID
    title: str
    question: str
    status: Literal['draft', 'active', 'closed']
    version: int
    previous_case_id: UUID | None
    record_ids: list[UUID]
    members: list[CaseMemberResponse]
    created_at: datetime | None
    sequence: int
    published_record_id: UUID | None


class CaseViewResponse(ResponseSchema):
    """Полная или нейтральная карточка, выбранная проверкой доступа на сервере."""

    id: UUID
    status: Literal['draft', 'active', 'closed']
    membership_status: str
    coordinator_id: UUID
    coordinator_name: str
    material_count: int
    accessible: bool
    case: ClinicalCaseResponse | None
    unread_messages: int
    patient_name: str | None
    management_members: list[CaseMemberResponse]
    invitation_terms: str


class DoctorResponse(ResponseSchema):
    """Активный зарегистрированный врач для отправки приглашения."""

    id: UUID
    name: str
    email: str


class MaterialResponse(ResponseSchema):
    """Метаданные записи в поиске и выборе материалов."""

    id: UUID
    title: str | None
    clinical_summary: str | None
    event_date: date
    record_type: str
    status: str


class MessageResponse(ResponseSchema):
    """Неизменяемая реплика с проверенными ссылками на материалы."""

    id: UUID
    case_id: UUID
    author_id: UUID
    body: str
    idempotency_key: UUID
    sequence: int
    parent_id: UUID | None
    record_id: UUID | None
    attachment_id: UUID | None
    opinion_id: UUID | None
    created_at: datetime | None
    author_name: str


class DiscussionResponse(PageResponse[MessageResponse]):
    """Страница обсуждения с курсором событий случая."""

    sequence: int


class OpinionResponse(ResponseSchema):
    """Адресный запрос и его состояние без подмены ответственного врача."""

    id: UUID
    case_id: UUID
    requester_id: UUID
    assignee_id: UUID
    question: str
    status: Literal['open', 'answered', 'cancelled']
    record_id: UUID | None
    reason: str | None
    response_message_id: UUID | None
    created_at: datetime | None


class ActivityResponse(ResponseSchema):
    """Запись журнала без копирования клинического текста."""

    id: UUID
    sequence: int
    event_type: str
    actor_id: UUID
    actor_name: str
    subject_id: UUID | None
    created_at: datetime


class ConclusionResponse(ResponseSchema):
    """Версия итога с автором, временем и материалами-источниками."""

    id: UUID
    case_id: UUID
    number: int
    author_id: UUID
    summary: str
    findings: str
    next_actions: str
    source_ids: list[UUID]
    sources: list[MaterialResponse] = []
    created_at: datetime | None


class ClosurePreviewResponse(ResponseSchema):
    """Открытые запросы и версия для подтверждения закрытия."""

    open_requests: int
    version: int


class PublicationPreviewResponse(ResponseSchema):
    """Предпросмотр будущей самостоятельной записи и её происхождения."""

    title: str
    clinical_summary: str
    conclusion_id: UUID
    conclusion_version: int
    source_ids: list[UUID]
    published_record_id: UUID | None


class PublicationResponse(ResponseSchema):
    """Идентификатор записи и результат идемпотентной публикации."""

    record_id: UUID
    created: bool
