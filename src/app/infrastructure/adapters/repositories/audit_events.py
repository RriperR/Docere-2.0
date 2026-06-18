"""Репозиторий записи событий аудита."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.infrastructure.db.models.audit_event import AuditEventRow


class AuditEventRepositoryAdapter:
    """Репозиторий append-only событий аудита."""

    def __init__(self, session: Session) -> None:
        """Инициализировать репозиторий.

        Args:
            session: Активная SQLAlchemy-сессия.
        """
        self._session = session

    def record(
        self,
        *,
        actor_user_id: UUID | None,
        event_type: str,
        entity_type: str,
        entity_id: UUID,
        metadata_json: dict[str, object] | None = None,
    ) -> None:
        """Записать событие аудита.

        Args:
            actor_user_id: Пользователь, выполнивший действие.
            event_type: Тип события.
            entity_type: Тип сущности.
            entity_id: Идентификатор сущности.
            metadata_json: Дополнительные данные.
        """
        self._session.add(
            AuditEventRow(
                actor_user_id=actor_user_id,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                metadata_json=metadata_json or {},
            ),
        )
