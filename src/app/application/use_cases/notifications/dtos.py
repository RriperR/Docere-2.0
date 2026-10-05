"""Проекции событий и адресных задач без копирования клинических данных."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Notification:
    """Ссылка на доменное событие, не содержащая медицинский текст."""

    id: UUID
    event_type: str
    case_id: UUID
    subject_id: UUID | None
    created_at: datetime
    read_at: datetime | None


@dataclass(frozen=True)
class AttentionTask:
    """Идентификаторы ожидающего ответа приглашения или запроса."""

    case_id: UUID
    subject_id: UUID
    event_type: str


@dataclass(frozen=True)
class NotificationView:
    """Уведомление с проверенной целью либо нейтральная карточка после отзыва."""

    id: UUID
    event_type: str
    case_id: UUID | None
    subject_id: UUID | None
    created_at: datetime
    read_at: datetime | None
    available: bool


@dataclass(frozen=True)
class AttentionView:
    """Адресная задача с актуальной доступностью целевого случая."""

    event_type: str
    case_id: UUID | None
    subject_id: UUID | None
    available: bool


@dataclass(frozen=True)
class NotificationCounts:
    """Непрочитанные события и версия входящих для сверки через SSE."""

    unread: int
    version: str
    id: UUID
