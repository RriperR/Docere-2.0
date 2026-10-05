"""Порты хранения разбора и выдачи прав с происхождением."""

from typing import Protocol
from uuid import UUID

from app.domain.clinical_cases import CaseMessage, ClinicalCase, OpinionRequest


class CaseRepositoryPort(Protocol):
    """Транзакционное хранилище клинических случаев."""

    def get(self, case_id: UUID, *, lock: bool = False) -> ClinicalCase | None:
        """Получить агрегат из хранилища.

        Args:
            case_id: Идентификатор случая.
            lock: Параметр операции.
        """
        ...

    def save(self, case: ClinicalCase) -> None:
        """Сохранить агрегат в текущей транзакции.

        Args:
            case: Агрегат текущего разбора.
        """
        ...

    def list_for(
        self, user_id: UUID, *, scope: str, status: str | None, offset: int, limit: int
    ) -> tuple[list[ClinicalCase], int]:
        """Выбрать страницу случаев пользователя.

        Args:
            user_id: Текущий пользователь.
            scope: Параметр операции.
            status: Параметр операции.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.
        """
        ...

    def is_doctor(self, user_id: UUID) -> bool:
        """Проверить действующую роль врача.

        Args:
            user_id: Текущий пользователь.
        """
        ...

    def doctor_name(self, user_id: UUID) -> str:
        """Получить имя врача.

        Args:
            user_id: Текущий пользователь.
        """
        ...

    def search_doctors(self, user_id: UUID, query: str) -> list[dict[str, str]]:
        """Найти активных врачей.

        Args:
            user_id: Текущий пользователь.
            query: Поисковая строка.
        """
        ...

    def grant(self, case: ClinicalCase, user_id: UUID) -> UUID:
        """Создать права с происхождением от случая.

        Args:
            case: Агрегат текущего разбора.
            user_id: Текущий пользователь.
        """
        ...

    def revoke(self, case: ClinicalCase, user_id: UUID) -> None:
        """Отозвать только права данного случая.

        Args:
            case: Агрегат текущего разбора.
            user_id: Текущий пользователь.
        """
        ...

    def available_materials(
        self, patient_id: UUID, user_id: UUID, query: str, offset: int, limit: int
    ) -> dict[str, object]:
        """Выбрать страницу доступных записей пациента.

        Args:
            patient_id: Параметр операции.
            user_id: Текущий пользователь.
            query: Поисковая строка.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.
        """
        ...

    def message(self, message_id: UUID) -> CaseMessage | None:
        """Получить неизменяемое сообщение.

        Args:
            message_id: Параметр операции.
        """
        ...

    def find_message(self, case_id: UUID, author_id: UUID, key: UUID) -> CaseMessage | None:
        """Найти результат повторного запроса отправки.

        Args:
            case_id: Идентификатор случая.
            author_id: Параметр операции.
            key: Ключ повторной отправки.
        """
        ...

    def add_message(self, message: CaseMessage) -> CaseMessage:
        """Сохранить неизменяемое сообщение.

        Args:
            message: Неизменяемая реплика.
        """
        ...

    def messages(self, case_id: UUID, offset: int, limit: int, query: str = '') -> tuple[list[CaseMessage], int]:
        """Выбрать страницу обсуждения с серверным поиском.

        Args:
            case_id: Идентификатор случая.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.
            query: Поисковая строка.
        """
        ...

    def opinion(self, opinion_id: UUID) -> OpinionRequest | None:
        """Получить адресный запрос.

        Args:
            opinion_id: Адресный запрос.
        """
        ...

    def opinions(self, case_id: UUID, offset: int, limit: int) -> tuple[list[OpinionRequest], int]:
        """Выбрать страницу адресных запросов.

        Args:
            case_id: Идентификатор случая.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.
        """
        ...

    def save_opinion(self, opinion: OpinionRequest) -> None:
        """Сохранить состояние адресного запроса.

        Args:
            opinion: Адресный запрос.
        """
        ...

    def cancel_assignee_opinions(self, case_id: UUID, user_id: UUID) -> None:
        """Отменить открытые запросы вышедшему врачу.

        Args:
            case_id: Идентификатор случая.
            user_id: Текущий пользователь.
        """
        ...

    def emit(
        self, case: ClinicalCase, actor_id: UUID, event_type: str, subject_id: UUID | None, recipients: list[UUID]
    ) -> None:
        """Записать событие в той же транзакции, что и изменение.

        Args:
            case: Агрегат текущего разбора.
            actor_id: Автор действия.
            event_type: Тип доменного действия.
            subject_id: Целевой объект события.
            recipients: Получатели события.
        """
        ...

    def activity(self, case_id: UUID, offset: int, limit: int) -> dict[str, object]:
        """Получить страницу журнала действий без копирования медицинского текста.

        Args:
            case_id: Идентификатор случая.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.
        """
        ...
