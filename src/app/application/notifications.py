"""Внутрисистемные уведомления с повторной проверкой доступа к цели."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.use_cases.clinical_cases import ClinicalCasesUseCase
from app.domain.clinical_cases import CaseError


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


class NotificationRepositoryPort(Protocol):
    """Персистентность входящих без бизнес-правил в HTTP routers."""

    def list_notifications(self, user_id: UUID, offset: int, limit: int) -> tuple[list[Notification], int]:
        """Получить страницу собственных уведомлений.

        Args:
            user_id: Текущий пользователь.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.
        """
        ...

    def counts(self, user_id: UUID) -> tuple[int, int, int]:
        """Вернуть число уведомлений, непрочитанное и версию активности случаев.

        Args:
            user_id: Текущий пользователь.
        """
        ...

    def read(self, user_id: UUID, notification_id: UUID | None) -> bool:
        """Прочитать одно своё уведомление либо все свои уведомления.

        Args:
            user_id: Текущий пользователь.
            notification_id: Параметр операции.
        """
        ...

    def attention(self, user_id: UUID, offset: int, limit: int) -> tuple[list[AttentionTask], int]:
        """Выбрать ожидающие ответа приглашения и адресные запросы.

        Args:
            user_id: Текущий пользователь.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.
        """
        ...


class NotificationsUseCase:
    """Отобразить события с актуальной авторизацией их целевого случая."""

    def __init__(self, repository: NotificationRepositoryPort, cases: ClinicalCasesUseCase) -> None:
        """Инициализировать хранилище и проверку доступа к случаям.

        Args:
            repository: Параметр операции.
            cases: Параметр операции.
        """
        self.repository, self.cases = repository, cases

    def projection(self, item: Notification, user_id: UUID) -> dict[str, object]:
        """Скрыть идентификаторы цели, если пользователь больше не может её открыть.

        Args:
            item: Параметр операции.
            user_id: Текущий пользователь.

        Returns:
            Результат сценария в контексте текущего пользователя.
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
        return {
            'id': item.id,
            'event_type': item.event_type if available else 'unavailable',
            'case_id': item.case_id if available else None,
            'subject_id': item.subject_id if available else None,
            'created_at': item.created_at,
            'read_at': item.read_at,
            'available': available,
        }

    def list_notifications(self, user_id: UUID, offset: int, limit: int) -> dict[str, object]:
        """Прочитать страницу без копирования вопроса, пациента или документов.

        Args:
            user_id: Текущий пользователь.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.

        Returns:
            Результат сценария в контексте текущего пользователя.
        """
        self.cases.require_doctor(user_id)
        items, total = self.repository.list_notifications(user_id, offset, limit)
        return {'items': [self.projection(item, user_id) for item in items], 'total': total}

    def count(self, user_id: UUID) -> dict[str, object]:
        """Получить непрочитанное и стабильную версию метаданных для SSE.

        Args:
            user_id: Текущий пользователь.

        Returns:
            Результат сценария в контексте текущего пользователя.
        """
        self.cases.require_doctor(user_id)
        total, unread, activity = self.repository.counts(user_id)
        return {'unread': unread, 'version': f'{total}-{unread}-{activity}', 'id': user_id}

    def read(self, user_id: UUID, notification_id: UUID | None = None) -> None:
        """Прочтение не является принятием приглашения или ответом на запрос.

        Args:
            user_id: Текущий пользователь.
            notification_id: Параметр операции.

        Raises:
            CaseError: При нарушении условий операции.
        """
        self.cases.require_doctor(user_id)
        if not self.repository.read(user_id, notification_id):
            raise CaseError('Уведомление не найдено', 404)

    def attention(self, user_id: UUID, offset: int, limit: int) -> dict[str, object]:
        """Получить действующие задачи с повторной проверкой цели при выводе.

        Args:
            user_id: Текущий пользователь.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.

        Returns:
            Результат сценария в контексте текущего пользователя.
        """
        self.cases.require_doctor(user_id)
        tasks, total = self.repository.attention(user_id, offset, limit)
        items: list[dict[str, object]] = []
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
                {
                    'event_type': task.event_type if available else 'unavailable',
                    'case_id': task.case_id if available else None,
                    'subject_id': task.subject_id if available else None,
                    'available': available,
                }
            )
        return {'items': items, 'total': total}
