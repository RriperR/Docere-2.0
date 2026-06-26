"""Репозиторий записи событий аудита."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.application.ports.repositories.audit_events.dtos import AuditEventDTO
from app.application.ports.repositories.audit_events.port import AuditEventRepositoryPort
from app.infrastructure.db.models.audit_event import AuditEventRow
from app.infrastructure.db.models.auth.user import UserRow


class AuditEventRepositoryAdapter(AuditEventRepositoryPort):
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

    def list_recent(self, *, limit: int) -> tuple[AuditEventDTO, ...]:
        """Вернуть последние события аудита.

        Args:
            limit: Максимальное количество событий.

        Returns:
            Последние события с публичными данными actor-пользователя.
        """
        rows = self._session.execute(
            select(AuditEventRow, UserRow.fio, UserRow.email)
            .outerjoin(UserRow, UserRow.id == AuditEventRow.actor_user_id)
            .order_by(desc(AuditEventRow.created_at), desc(AuditEventRow.id))
            .limit(limit),
        ).all()
        return tuple(
            AuditEventDTO(
                id=row.id,
                actor_user_id=row.actor_user_id,
                actor_fio=actor_fio,
                actor_email=actor_email,
                event_type=row.event_type,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                metadata_json=row.metadata_json,
                created_at=row.created_at,
            )
            for row, actor_fio, actor_email in rows
        )
