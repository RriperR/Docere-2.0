"""Порты хранения разбора и выдачи прав с происхождением."""

from typing import Protocol
from uuid import UUID

from app.application.use_cases.clinical_cases.dtos import (
    CaseActivityEntry,
    DoctorSummary,
    MaterialFilters,
    MaterialSummary,
    PageDTO,
)
from app.domain.clinical_cases import CaseConclusion, CaseMessage, ClinicalCase, OpinionRequest


class CaseRepositoryPort(Protocol):
    """Транзакционное хранилище клинических случаев."""

    def get(self, case_id: UUID, *, lock: bool = False) -> ClinicalCase | None:
        """Получить агрегат из хранилища.

        Args:
            case_id: Идентификатор клинического случая.
            lock: Заблокировать строку случая до завершения транзакции изменения.

        Returns:
            Сохранённый агрегат или None, если идентификатор не существует.
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
            user_id: Пользователь, для которого выполняется операция.
            scope: Отбор всех случаев, координируемых или с участием пользователя.
            status: Состояние случая для фильтрации.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Случаи выбранной страницы и общее число случаев до пагинации.
        """
        ...

    def is_doctor(self, user_id: UUID) -> bool:
        """Проверить действующую роль врача.

        Args:
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            True только для зарегистрированного активного пользователя с ролью врача.
        """
        ...

    def has_material_access(self, record_ids: list[UUID], user_id: UUID) -> bool:
        """Проверить весь набор материалов без загрузки клинического содержимого.

        Args:
            record_ids: Идентификаторы выбранных записей.
            user_id: Пользователь, чей доступ проверяется.

        Returns:
            True, если есть действующее право на каждую запись; для пустого набора True.
        """
        ...

    def doctor_name(self, user_id: UUID) -> str:
        """Получить имя врача.

        Args:
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            Публичное имя врача либо нейтральная подпись, если профиль отсутствует.
        """
        ...

    def search_doctors(self, user_id: UUID, query: str) -> list[DoctorSummary]:
        """Найти активных врачей.

        Args:
            user_id: Пользователь, для которого выполняется операция.
            query: Текст для поиска по разрешённым полям.

        Returns:
            Список активных врачей, соответствующих имени или email, кроме самого пользователя.
        """
        ...

    def grant(self, case: ClinicalCase, user_id: UUID, record_ids: list[UUID] | None = None) -> UUID:
        """Создать права с происхождением от случая.

        Args:
            case: Агрегат текущего разбора.
            user_id: Пользователь, для которого выполняется операция.
            record_ids: Выбранные записи одного пациента.

        Returns:
            Идентификатор принятого sharing-запроса, помеченного происхождением от случая.
        """
        ...

    def revoke(self, case: ClinicalCase, user_id: UUID) -> None:
        """Отозвать только права данного случая.

        Args:
            case: Агрегат текущего разбора.
            user_id: Пользователь, для которого выполняется операция.
        """
        ...

    def available_materials(
        self, patient_id: UUID, user_id: UUID, query: str, offset: int, limit: int
    ) -> PageDTO[MaterialSummary]:
        """Выбрать страницу доступных записей пациента.

        Args:
            patient_id: Идентификатор конкретного паспорта пациента.
            user_id: Пользователь, для которого выполняется операция.
            query: Текст для поиска по разрешённым полям.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница доступных врачу записей выбранного пациента и их общее число.
        """
        ...

    def message(self, message_id: UUID) -> CaseMessage | None:
        """Получить неизменяемое сообщение.

        Args:
            message_id: Идентификатор реплики в обсуждении случая.

        Returns:
            Реплика по идентификатору либо None; проверка контекста выполняется в use case.
        """
        ...

    def find_message(self, case_id: UUID, author_id: UUID, key: UUID) -> CaseMessage | None:
        """Найти результат повторного запроса отправки.

        Args:
            case_id: Идентификатор случая.
            author_id: Автор отправленного сообщения.
            key: Ключ повторной отправки.
        """
        ...

    def add_message(self, message: CaseMessage) -> CaseMessage:
        """Сохранить неизменяемое сообщение.

        Args:
            message: Новая неизменяемая реплика со ссылками и ключом идемпотентности.

        Returns:
            Сохранённая реплика с временем создания и именем автора.
        """
        ...

    def messages(self, case_id: UUID, offset: int, limit: int, query: str = '') -> tuple[list[CaseMessage], int]:
        """Выбрать страницу обсуждения с серверным поиском.

        Args:
            case_id: Идентификатор клинического случая.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.
            query: Текст для поиска по разрешённым полям.

        Returns:
            Реплики выбранной страницы и общее число совпадений до пагинации.
        """
        ...

    def opinion(self, opinion_id: UUID) -> OpinionRequest | None:
        """Получить адресный запрос.

        Args:
            opinion_id: Идентификатор адресного запроса мнения.

        Returns:
            Адресный запрос либо None; проверка контекста выполняется в use case.
        """
        ...

    def opinions(self, case_id: UUID, offset: int, limit: int) -> tuple[list[OpinionRequest], int]:
        """Выбрать страницу адресных запросов.

        Args:
            case_id: Идентификатор клинического случая.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Запросы выбранной страницы и их общее число.
        """
        ...

    def save_opinion(self, opinion: OpinionRequest) -> None:
        """Сохранить состояние адресного запроса.

        Args:
            opinion: Адресный запрос с обновлённым состоянием.
        """
        ...

    def cancel_assignee_opinions(self, case_id: UUID, user_id: UUID) -> None:
        """Отменить открытые запросы вышедшему врачу.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
        """
        ...

    def emit(
        self, case: ClinicalCase, actor_id: UUID, event_type: str, subject_id: UUID | None, recipients: list[UUID]
    ) -> None:
        """Записать событие в той же транзакции, что и изменение.

        Args:
            case: Агрегат текущего разбора.
            actor_id: Автор действия для журнала событий.
            event_type: Тип изменения без медицинского текста.
            subject_id: Объект, связанный с событием.
            recipients: Адресаты уведомления; автор исключается при сохранении события.
        """
        ...

    def activity(self, case_id: UUID, offset: int, limit: int) -> PageDTO[CaseActivityEntry]:
        """Получить страницу журнала действий без копирования медицинского текста.

        Args:
            case_id: Идентификатор клинического случая.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница событий с авторами и ссылками без копирования клинического текста.
        """
        ...

    def conclusions(self, case_id: UUID, offset: int, limit: int) -> tuple[list[CaseConclusion], int]:
        """Выбрать страницу версий итога, начиная с последней.

        Args:
            case_id: Идентификатор клинического случая.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Версии итога, начиная с последней, и их общее число.
        """
        ...

    def add_conclusion(self, conclusion: CaseConclusion) -> CaseConclusion:
        """Добавить неизменяемую версию.

        Args:
            conclusion: Новая версия итога со ссылками на материалы.

        Returns:
            Сохранённая новая версия итога с временем создания.
        """
        ...

    def open_opinions(self, case_id: UUID) -> int:
        """Посчитать незавершённые адресные запросы.

        Args:
            case_id: Идентификатор клинического случая.

        Returns:
            Число запросов в состоянии open.
        """
        ...

    def cancel_open_opinions(self, case_id: UUID) -> None:
        """Отменить открытые запросы при явно подтверждённом закрытии.

        Args:
            case_id: Идентификатор клинического случая.
        """
        ...

    def case_materials(
        self, case_id: UUID, filters: MaterialFilters, offset: int, limit: int
    ) -> PageDTO[MaterialSummary]:
        """Найти страницу материалов по описанию, названию и имени вложения.

        Args:
            case_id: Идентификатор клинического случая.
            filters: Поиск по метаданным и фильтры типа, даты события и подтверждения.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница выбранных материалов, удовлетворяющих фильтрам, и общее число совпадений.
        """
        ...

    def unread_messages(self, case_id: UUID, user_id: UUID) -> int:
        """Посчитать реплики после позиции прочтения.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            Число чужих реплик после сохранённой позиции прочтения.
        """
        ...

    def mark_discussion_read(self, case_id: UUID, user_id: UUID, sequence: int) -> None:
        """Монотонно продвинуть позицию прочтения.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            sequence: Последовательность событий, до которой пользователь прочитал обсуждение.
        """
        ...

    def cases_for_user(self, user_id: UUID) -> list[UUID]:
        """Найти разборы, требующие прекращения участия пользователя.

        Args:
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            Идентификаторы координируемых случаев и действующих приглашений/участий.
        """
        ...

    def inactive_users(self, limit: int) -> list[UUID]:
        """Найти утративших роль или заблокированных участников для восстановления инварианта.

        Args:
            limit: Максимальное число элементов страницы.

        Returns:
            Не более limit заблокированных или утративших роль врачей с незавершённым участием.
        """
        ...


class CaseParticipationPort(Protocol):
    """Прекращение участия при блокировке аккаунта."""

    def terminate_user(self, user_id: UUID, actor_id: UUID) -> None:
        """Отозвать участие и его источники ACL в той же транзакции.

        Args:
            user_id: Пользователь, для которого выполняется операция.
            actor_id: Автор действия для журнала событий.
        """
        ...
