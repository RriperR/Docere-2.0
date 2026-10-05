"""Порт хранения уведомлений и адресных задач врача."""

from typing import Protocol
from uuid import UUID

from app.application.use_cases.notifications.dtos import AttentionTask, Notification


class NotificationRepositoryPort(Protocol):
    """Персистентность входящих без бизнес-правил в HTTP routers."""

    def list_notifications(self, user_id: UUID, offset: int, limit: int) -> tuple[list[Notification], int]:
        """Получить страницу собственных уведомлений.

        Args:
            user_id: Пользователь, для которого выполняется операция.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница собственных уведомлений и их общее число.
        """
        ...

    def counts(self, user_id: UUID) -> tuple[int, int, int]:
        """Вернуть число уведомлений, непрочитанное и версию активности случаев.

        Args:
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            Общее число уведомлений, непрочитанное и сумма последовательностей доступных по членству случаев.
        """
        ...

    def read(self, user_id: UUID, notification_id: UUID | None) -> bool:
        """Прочитать одно своё уведомление либо все свои уведомления.

        Args:
            user_id: Пользователь, для которого выполняется операция.
            notification_id: Собственное уведомление; None означает отметить все свои уведомления.

        Returns:
            True, если своё уведомление найдено или запрошено прочтение всех своих уведомлений.
        """
        ...

    def attention(self, user_id: UUID, offset: int, limit: int) -> tuple[list[AttentionTask], int]:
        """Выбрать ожидающие ответа приглашения и адресные запросы.

        Args:
            user_id: Пользователь, для которого выполняется операция.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница приглашений и запросов мнения с актуальной доступностью их целей.
        """
        ...
