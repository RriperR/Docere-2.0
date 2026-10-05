"""Чтение входящих с повторной проверкой доступа к клиническому случаю."""

from uuid import UUID

from app.application.ports.notifications import NotificationRepositoryPort
from app.application.use_cases.clinical_cases.context import CaseContext
from app.application.use_cases.clinical_cases.dtos import PageDTO
from app.application.use_cases.notifications.dtos import (
    AttentionView,
    Notification,
    NotificationCounts,
    NotificationView,
)
from app.domain.clinical_cases import CaseError


class NotificationsUseCase:
    """Отобразить события с актуальной авторизацией их целевого случая."""

    def __init__(self, repository: NotificationRepositoryPort, cases: CaseContext) -> None:
        """Инициализировать хранилище и проверку доступа к случаям.

        Args:
            repository: Хранилище собственных уведомлений и адресных задач.
            cases: Общая проверка доступа к целевому случаю.
        """
        self.repository, self.cases = repository, cases

    def projection(self, item: Notification, user_id: UUID) -> NotificationView:
        """Скрыть идентификаторы цели, если пользователь больше не может её открыть.

        Args:
            item: Уведомление, цель которого нужно проверить заново.
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            Карточка события с проверенной ссылкой либо нейтральное уведомление без целевых идентификаторов.
        """
        available = False
        try:
            case = self.cases.load(item.case_id, user_id)
            available = self.cases.accessible(case, user_id)
            member = case.member(user_id)
            if item.event_type == 'invitation' and member and member.status == 'pending':
                available = case.status == 'active' and self.cases.repository.is_doctor(case.coordinator_id)
        except CaseError:
            pass
        return NotificationView(
            item.id,
            item.event_type if available else 'unavailable',
            item.case_id if available else None,
            item.subject_id if available else None,
            item.created_at,
            item.read_at,
            available,
        )

    def list_notifications(self, user_id: UUID, offset: int, limit: int) -> PageDTO[NotificationView]:
        """Прочитать страницу без копирования вопроса, пациента или документов.

        Args:
            user_id: Пользователь, для которого выполняется операция.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница собственных уведомлений и их общее число.
        """
        self.cases.require_doctor(user_id)
        items, total = self.repository.list_notifications(user_id, offset, limit)
        return PageDTO([self.projection(item, user_id) for item in items], total)

    def count(self, user_id: UUID) -> NotificationCounts:
        """Получить непрочитанное и стабильную версию метаданных для SSE.

        Args:
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            Число непрочитанных уведомлений и версия совокупной активности входящих.
        """
        self.cases.require_doctor(user_id)
        total, unread, activity = self.repository.counts(user_id)
        return NotificationCounts(unread, f'{total}-{unread}-{activity}', user_id)

    def read(self, user_id: UUID, notification_id: UUID | None = None) -> None:
        """Прочтение не является принятием приглашения или ответом на запрос.

        Args:
            user_id: Пользователь, для которого выполняется операция.
            notification_id: Собственное уведомление; None означает отметить все свои уведомления.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        self.cases.require_doctor(user_id)
        if not self.repository.read(user_id, notification_id):
            raise CaseError('Уведомление не найдено', 404)

    def attention(self, user_id: UUID, offset: int, limit: int) -> PageDTO[AttentionView]:
        """Получить действующие задачи с повторной проверкой цели при выводе.

        Args:
            user_id: Пользователь, для которого выполняется операция.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница приглашений и запросов мнения с актуальной доступностью их целей.
        """
        self.cases.require_doctor(user_id)
        tasks, total = self.repository.attention(user_id, offset, limit)
        items: list[AttentionView] = []
        for task in tasks:
            available = False
            try:
                case = self.cases.load(task.case_id, user_id)
                if task.event_type == 'invitation':
                    member = case.member(user_id)
                    available = bool(
                        member
                        and member.status == 'pending'
                        and case.status == 'active'
                        and self.cases.repository.is_doctor(case.coordinator_id)
                    )
                else:
                    available = self.cases.accessible(case, user_id)
            except CaseError:
                pass
            items.append(
                AttentionView(
                    task.event_type if available else 'unavailable',
                    task.case_id if available else None,
                    task.subject_id if available else None,
                    available,
                )
            )
        return PageDTO(items, total)
