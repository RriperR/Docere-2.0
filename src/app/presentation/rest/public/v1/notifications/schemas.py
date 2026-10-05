"""Публичные схемы входящих без копирования медицинских сведений."""

from datetime import datetime
from uuid import UUID

from app.presentation.rest.public.v1.cases.responses import ResponseSchema


class NotificationResponse(ResponseSchema):
    """Уведомление с доступной целью либо нейтральная карточка."""

    id: UUID
    event_type: str
    case_id: UUID | None
    subject_id: UUID | None
    created_at: datetime
    read_at: datetime | None
    available: bool


class AttentionResponse(ResponseSchema):
    """Приглашение или запрос мнения с повторно проверенной доступностью."""

    event_type: str
    case_id: UUID | None
    subject_id: UUID | None
    available: bool


class NotificationCountResponse(ResponseSchema):
    """Счётчик собственных уведомлений и версия входящих для SSE."""

    unread: int
    version: str
    id: UUID
