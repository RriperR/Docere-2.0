"""Типизированные результаты сценариев и запросов клинического разбора."""

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from app.domain.clinical_cases import CaseConclusion, CaseMember, CaseMessage, ClinicalCase


@dataclass(frozen=True)
class PageDTO[T]:
    """Страница серверной выборки с общим числом элементов до пагинации."""

    items: list[T]
    total: int


@dataclass(frozen=True)
class DiscussionPage(PageDTO[CaseMessage]):
    """Страница реплик и последовательность событий, прочитанная вместе с ней."""

    sequence: int


@dataclass(frozen=True)
class DoctorSummary:
    """Публичные сведения активного врача для приглашения."""

    id: UUID
    name: str
    email: str


@dataclass(frozen=True)
class MaterialSummary:
    """Метаданные выбранной записи без загрузки документов."""

    id: UUID
    title: str | None
    clinical_summary: str | None
    event_date: date
    record_type: str
    status: str


@dataclass(frozen=True)
class CaseActivityEntry:
    """Событие журнала с автором и ссылкой на объект, без клинического текста."""

    id: UUID
    sequence: int
    event_type: str
    actor_id: UUID
    actor_name: str
    subject_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class ClosurePreview:
    """Число открытых запросов и версия разбора перед подтверждением закрытия."""

    open_requests: int
    version: int


@dataclass(frozen=True)
class PublicationPreview:
    """Предпросмотр записи и provenance выбранной версии итога."""

    title: str
    clinical_summary: str
    conclusion_id: UUID
    conclusion_version: int
    source_ids: list[UUID]
    published_record_id: UUID | None


@dataclass(frozen=True)
class PublicationResult:
    """Идентификатор опубликованной записи и факт её создания этим запросом."""

    record_id: UUID
    created: bool


@dataclass(frozen=True)
class CaseView:
    """Безопасная проекция: клинический контекст присутствует только при полном доступе."""

    id: UUID
    status: str
    membership_status: str
    coordinator_id: UUID
    coordinator_name: str
    material_count: int
    accessible: bool
    case: ClinicalCase | None
    unread_messages: int = 0
    patient_name: str | None = None
    management_members: tuple[CaseMember, ...] = ()
    invitation_terms: str = 'Координатор сможет добавлять новые материалы этого пациента в совместный разбор.'


@dataclass(frozen=True)
class MaterialFilters:
    """Серверные фильтры без OCR и чтения содержимого PDF."""

    query: str = ''
    record_type: str | None = None
    status: str | None = None
    date_from: date | None = None
    date_to: date | None = None


@dataclass(frozen=True)
class ConclusionView(CaseConclusion):
    """Версия итога с защищёнными отображаемыми сведениями об источниках."""

    sources: list[MaterialSummary] = field(default_factory=list)
